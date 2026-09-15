#!/usr/bin/env python3
"""
lunadata_gui.py – Extractor for Lunar: Silver Star Story Complete (PS1)
LUNADATA.FIL virtual filesystem

Pure Python 3 + optional tkinter GUI.
Same style as bincue_gui.py so it can later be dropped into the randomizer GUI.

Format (from CaitSith2 / community notes):
  Header 32 bytes:
    0x00     1  = 0x2E
    0x01-13 19  = 0x00
    0x14     4  num_files (LE)
    0x18     4  total_length (LE)
    0x1C     4  reserved
  Then num_files × 32-byte entries:
    0x00    20  filename (null-padded)
    0x14     4  cluster (data @ cluster * 0x800)
    0x18     4  file size
    0x1C     4  unknown (often timestamp)
"""

from __future__ import annotations

import os
import struct
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

# tkinter is optional so the core can be imported headless
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None  # type: ignore


CLUSTER_SIZE = 0x800  # 2048 bytes


@dataclass
class FilEntry:
    name: str
    cluster: int
    size: int
    unknown: int

    @property
    def offset(self) -> int:
        return self.cluster * CLUSTER_SIZE


@dataclass
class LunaDataFil:
    path: Path
    num_files: int
    total_length: int
    entries: List[FilEntry]


def parse_lunadata(fil_path: Path) -> LunaDataFil:
    """Parse a LUNADATA.FIL and return its directory."""
    fil_path = fil_path.resolve()
    data = fil_path.read_bytes()

    if len(data) < 32:
        raise ValueError("File too small to be a LUNADATA.FIL")

    magic = data[0]
    if magic != 0x2E:
        # Still try – some dumps may differ slightly
        pass

    num_files = struct.unpack_from("<I", data, 0x14)[0]
    total_length = struct.unpack_from("<I", data, 0x18)[0]

    if num_files == 0 or num_files > 100_000:
        raise ValueError(f"Suspicious number of files: {num_files}")

    entries: List[FilEntry] = []
    for i in range(num_files):
        off = 32 + i * 32
        if off + 32 > len(data):
            raise ValueError(f"Truncated directory at entry {i}")

        raw_name = data[off : off + 20]
        name = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
        if not name:
            name = f"unnamed_{i:04d}"

        cluster = struct.unpack_from("<I", data, off + 0x14)[0]
        size = struct.unpack_from("<I", data, off + 0x18)[0]
        unknown = struct.unpack_from("<I", data, off + 0x1C)[0]

        entries.append(FilEntry(name=name, cluster=cluster, size=size, unknown=unknown))

    return LunaDataFil(
        path=fil_path,
        num_files=num_files,
        total_length=total_length,
        entries=entries,
    )


def extract_entry(
    fil: LunaDataFil,
    entry: FilEntry,
    out_path: Path,
    *,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """Extract one file from the FIL to out_path."""
    if entry.size <= 0:
        out_path.write_bytes(b"")
        if progress_cb:
            progress_cb(0, 0)
        return

    offset = entry.offset
    with open(fil.path, "rb") as src:
        src.seek(offset)
        remaining = entry.size
        chunk = 1024 * 1024
        with open(out_path, "wb") as dst:
            written = 0
            while remaining > 0:
                to_read = min(chunk, remaining)
                buf = src.read(to_read)
                if not buf:
                    break
                dst.write(buf)
                remaining -= len(buf)
                written += len(buf)
                if progress_cb:
                    progress_cb(written, entry.size)


def extract_all(
    fil: LunaDataFil,
    out_dir: Path,
    *,
    selected: Optional[List[FilEntry]] = None,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> int:
    """
    Extract files to out_dir.
    Returns number of files written.
    progress_cb(filename, current, total) is called for each file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = selected if selected is not None else fil.entries
    count = 0
    for entry in targets:
        # Keep original name; create subdirs if name contains path separators (rare)
        safe_name = entry.name.replace("\\", "/").lstrip("/")
        dest = out_dir / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _prog(cur, tot, name=entry.name):
            if progress_cb:
                progress_cb(name, cur, tot)

        extract_entry(fil, entry, dest, progress_cb=_prog)
        count += 1
    return count


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

if HAS_TK:

    class LunaDataApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("LUNADATA.FIL Extractor – Lunar Silver Star Story")
            self.geometry("900x600")
            self.minsize(780, 480)

            self.fil: Optional[LunaDataFil] = None
            self.output_dir = Path.cwd()

            self._build_ui()

        def _build_ui(self):
            toolbar = ttk.Frame(self, padding=6)
            toolbar.pack(side=tk.TOP, fill=tk.X)

            ttk.Button(toolbar, text="Open LUNADATA.FIL…", command=self.open_fil).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(toolbar, text="Set Output Folder…", command=self.choose_output).pack(
                side=tk.LEFT, padx=(0, 6)
            )

            self.out_label = ttk.Label(
                toolbar, text=f"Output: {self.output_dir}", foreground="#555"
            )
            self.out_label.pack(side=tk.LEFT, padx=8)

            # File list
            list_frame = ttk.Frame(self, padding=6)
            list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            columns = ("name", "size", "cluster", "offset")
            self.tree = ttk.Treeview(
                list_frame, columns=columns, show="headings", selectmode="extended"
            )
            self.tree.heading("name", text="Filename")
            self.tree.heading("size", text="Size")
            self.tree.heading("cluster", text="Cluster")
            self.tree.heading("offset", text="Offset")

            self.tree.column("name", width=320)
            self.tree.column("size", width=110, anchor=tk.E)
            self.tree.column("cluster", width=100, anchor=tk.E)
            self.tree.column("offset", width=120, anchor=tk.E)

            vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            # Bottom controls
            bottom = ttk.Frame(self, padding=6)
            bottom.pack(side=tk.BOTTOM, fill=tk.X)

            ttk.Button(
                bottom, text="Extract Selected", command=lambda: self.extract(True)
            ).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(
                bottom, text="Extract All", command=lambda: self.extract(False)
            ).pack(side=tk.LEFT, padx=(0, 12))

            self.progress = ttk.Progressbar(bottom, mode="determinate", length=240)
            self.progress.pack(side=tk.LEFT, padx=8)

            self.status = ttk.Label(bottom, text="Ready – open a LUNADATA.FIL")
            self.status.pack(side=tk.LEFT, padx=8)

            # Log
            log_frame = ttk.LabelFrame(self, text="Log", padding=4)
            log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)
            self.log = tk.Text(log_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
            self.log.pack(fill=tk.X)

        def log_msg(self, msg: str):
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        def open_fil(self):
            path = filedialog.askopenfilename(
                title="Select LUNADATA.FIL",
                filetypes=[
                    ("LUNADATA.FIL", "LUNADATA.FIL"),
                    ("FIL files", "*.FIL"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return
            try:
                self.fil = parse_lunadata(Path(path))
                self._populate_tree()
                self.status.configure(
                    text=f"Loaded {self.fil.path.name} – {self.fil.num_files} file(s)"
                )
                self.log_msg(
                    f"Opened: {self.fil.path}  ({self.fil.num_files} entries, "
                    f"declared size {self.fil.total_length:,} bytes)"
                )
            except Exception as e:
                messagebox.showerror("Parse error", str(e))
                self.log_msg(f"ERROR: {e}")

        def choose_output(self):
            d = filedialog.askdirectory(title="Output folder")
            if d:
                self.output_dir = Path(d)
                self.out_label.configure(text=f"Output: {self.output_dir}")

        def _populate_tree(self):
            self.tree.delete(*self.tree.get_children())
            if not self.fil:
                return
            for i, e in enumerate(self.fil.entries):
                size_str = f"{e.size:,}" if e.size else "0"
                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(i),
                    values=(e.name, size_str, e.cluster, f"0x{e.offset:X}"),
                )

        def extract(self, selected_only: bool):
            if not self.fil:
                messagebox.showinfo("No file", "Open a LUNADATA.FIL first.")
                return

            if selected_only:
                sel = self.tree.selection()
                if not sel:
                    messagebox.showinfo(
                        "Nothing selected", "Select one or more files in the list."
                    )
                    return
                entries = [self.fil.entries[int(i)] for i in sel]
            else:
                entries = list(self.fil.entries)

            def worker():
                total = len(entries)
                for i, entry in enumerate(entries):
                    self.after(
                        0,
                        lambda i=i, e=entry: self.status.configure(
                            text=f"Extracting {e.name} ({i+1}/{total})…"
                        ),
                    )

                    def prog(name, cur, tot):
                        pct = int(100 * cur / tot) if tot else 100
                        self.after(0, lambda: self.progress.configure(value=pct))

                    try:
                        extract_all(
                            self.fil,
                            self.output_dir,
                            selected=[entry],
                            progress_cb=prog,
                        )
                        self.after(
                            0, lambda n=entry.name: self.log_msg(f"Wrote {n}")
                        )
                    except Exception as ex:
                        self.after(
                            0,
                            lambda e=entry, ex=ex: self.log_msg(
                                f"ERROR {e.name}: {ex}"
                            ),
                        )

                self.after(
                    0,
                    lambda: (
                        self.progress.configure(value=0),
                        self.status.configure(text="Done"),
                        messagebox.showinfo(
                            "Finished",
                            f"Extracted {total} file(s) to\n{self.output_dir}",
                        ),
                    ),
                )

            threading.Thread(target=worker, daemon=True).start()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("\nUsage:  python3 lunadata_gui.py          # launch GUI")
        print("        from lunadata_gui import parse_lunadata, extract_all")
        return

    if not HAS_TK:
        print("ERROR: tkinter is not available.")
        print("On Debian/Ubuntu/Mint install it with:")
        print("    sudo apt install python3-tk")
        print("Then re-run this script.")
        sys.exit(1)

    app = LunaDataApp()
    app.mainloop()


if __name__ == "__main__":
    main()
