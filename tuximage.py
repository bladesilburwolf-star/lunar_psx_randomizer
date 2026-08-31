#!/usr/bin/env python3
"""
tuximage.py – ISO 9660 image viewer / extractor / injector for Linux

Pure Python 3 + optional tkinter. Companion to bincue_gui.py:
  bincue  → open CUE, extract/replace whole tracks
  tuximage → open the extracted .iso, list / extract / inject files

Typical Lunar / PSX flow:
  1. bincue_gui  – Extract data track → track01.iso
  2. tuximage    – Inject patched SLUS_006.28 into track01.iso
  3. bincue_gui  – Replace Selected track with the same track01.iso

Same-size inject only (ISO directory size is not rewritten).
"""

from __future__ import annotations

import struct
import sys
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None  # type: ignore


SECTOR = 2048


# ---------------------------------------------------------------------------
# ISO 9660 core
# ---------------------------------------------------------------------------

def find_pvd(iso: bytes) -> int:
    """Byte offset of Primary Volume Descriptor."""
    limit = min(32, len(iso) // SECTOR)
    for s in range(16, limit):
        off = s * SECTOR
        if off + 6 <= len(iso) and iso[off] == 1 and iso[off + 1 : off + 6] == b"CD001":
            return off
    raise ValueError("ISO 9660 Primary Volume Descriptor not found")


def _walk_dir(
    iso: bytes,
    extent_lba: int,
    size: int,
    *,
    target_upper: Optional[str] = None,
    path_prefix: str = "",
    max_depth: int = 8,
    depth: int = 0,
    results: Optional[List[Tuple[str, int, int, bool, int]]] = None,
) -> Optional[Tuple[int, int, int]]:
    """
    Walk directory records.
    If target_upper is set, return (lba, size, dirent_offset) on match.
    Otherwise append (path, lba, size, is_dir, dirent_offset) to results.
    """
    if results is None:
        results = []
    if depth > max_depth:
        return None

    start = extent_lba * SECTOR
    end = min(start + size, len(iso))
    pos = start

    while pos < end:
        if pos >= len(iso):
            break
        length = iso[pos]
        if length == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            continue
        if pos + length > len(iso):
            break

        flags = iso[pos + 25]
        loc = struct.unpack_from("<I", iso, pos + 2)[0]
        datalen = struct.unpack_from("<I", iso, pos + 10)[0]
        name_len = iso[pos + 32]
        raw = iso[pos + 33 : pos + 33 + name_len]

        if raw in (b"\x00", b"\x01"):
            pos += length
            continue

        name = raw.split(b";")[0].decode("ascii", errors="replace")
        is_dir = bool(flags & 0x02)
        path = f"{path_prefix}{name}"

        if is_dir:
            results.append((path + "/", loc, datalen, True, pos))
            found = _walk_dir(
                iso, loc, datalen,
                target_upper=target_upper,
                path_prefix=path + "/",
                max_depth=max_depth,
                depth=depth + 1,
                results=results,
            )
            if found is not None:
                return found
        else:
            results.append((path, loc, datalen, False, pos))
            if target_upper is not None:
                if name.upper() == target_upper or path.upper() == target_upper:
                    return (loc, datalen, pos)

        pos += length

    return None


def list_files(iso: bytes, max_depth: int = 8) -> List[Tuple[str, int, int, bool]]:
    """Return [(path, lba, size, is_dir), ...]"""
    pvd = find_pvd(iso)
    root_extent = struct.unpack_from("<I", iso, pvd + 158)[0]
    root_size = struct.unpack_from("<I", iso, pvd + 166)[0]
    bag: List[Tuple[str, int, int, bool, int]] = []
    _walk_dir(iso, root_extent, root_size, max_depth=max_depth, results=bag)
    return [(p, lba, sz, d) for p, lba, sz, d, _ in bag]


def find_file(iso: bytes, filename: str) -> Tuple[int, int, int]:
    """
    Locate filename (e.g. 'SLUS_006.28').
    Returns (lba, size_bytes, dirent_byte_offset).
    """
    pvd = find_pvd(iso)
    root_extent = struct.unpack_from("<I", iso, pvd + 158)[0]
    root_size = struct.unpack_from("<I", iso, pvd + 166)[0]
    target = filename.upper().lstrip("/")
    bag: List = []
    found = _walk_dir(
        iso, root_extent, root_size, target_upper=target, results=bag
    )
    if found is None:
        # try basename match from full listing
        for path, lba, sz, is_dir, dirent in bag:
            if is_dir:
                continue
            base = path.rstrip("/").split("/")[-1].upper()
            if base == target or path.upper() == target:
                return lba, sz, dirent
        raise FileNotFoundError(f"{filename!r} not found in ISO")
    return found


def extract_file(iso: bytes, filename: str) -> bytes:
    lba, size, _ = find_file(iso, filename)
    start = lba * SECTOR
    return iso[start : start + size]


def replace_file(
    iso: bytearray,
    filename: str,
    new_data: bytes,
    *,
    must_fit: bool = True,
) -> dict:
    """
    Overwrite file extent in-place. Pads with zeros if shorter.
    Raises if longer and must_fit=True (directory record size is not updated).
    """
    lba, size, dirent = find_file(bytes(iso), filename)
    if len(new_data) > size and must_fit:
        raise ValueError(
            f"{filename} is {size:,} bytes on disc; replacement is "
            f"{len(new_data):,} bytes. Keep the same size (pad if needed)."
        )
    payload = new_data[:size].ljust(size, b"\x00")
    start = lba * SECTOR
    end = start + size
    if end > len(iso):
        raise ValueError("File extent past end of image")
    iso[start:end] = payload
    return {
        "file": filename,
        "lba": lba,
        "original_size": size,
        "written": len(payload),
        "dirent_offset": dirent,
    }


def volume_info(iso: bytes) -> dict:
    pvd = find_pvd(iso)
    vol_space = struct.unpack_from("<I", iso, pvd + 80)[0]
    block_size = struct.unpack_from("<H", iso, pvd + 128)[0]
    vol_name = iso[pvd + 40 : pvd + 72].decode("ascii", errors="replace").strip()
    return {
        "pvd_offset": pvd,
        "volume_name": vol_name,
        "volume_sectors": vol_space,
        "block_size": block_size,
        "image_size": len(iso),
        "image_sectors": len(iso) // SECTOR,
    }


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

if HAS_TK:

    class TuxImageApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("tuximage – ISO 9660 Viewer / Injector")
            self.geometry("900x580")
            self.minsize(720, 420)

            self.iso_path: Optional[Path] = None
            self.iso_data: Optional[bytearray] = None
            self.dirty = False

            self._build_ui()

        def _build_ui(self):
            toolbar = ttk.Frame(self, padding=6)
            toolbar.pack(side=tk.TOP, fill=tk.X)

            ttk.Button(toolbar, text="Open ISO…", command=self.open_iso).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(toolbar, text="Save ISO", command=self.save_iso).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(toolbar, text="Save ISO As…", command=self.save_iso_as).pack(
                side=tk.LEFT, padx=(0, 12)
            )

            self.path_label = ttk.Label(toolbar, text="No image loaded", foreground="#555")
            self.path_label.pack(side=tk.LEFT, padx=8)

            # Info bar
            info = ttk.Frame(self, padding=(8, 0))
            info.pack(side=tk.TOP, fill=tk.X)
            self.info_label = ttk.Label(info, text="")
            self.info_label.pack(side=tk.LEFT)

            # File list
            list_frame = ttk.Frame(self, padding=6)
            list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            cols = ("path", "lba", "size", "kind")
            self.tree = ttk.Treeview(
                list_frame, columns=cols, show="headings", selectmode="extended"
            )
            self.tree.heading("path", text="Path")
            self.tree.heading("lba", text="LBA")
            self.tree.heading("size", text="Size")
            self.tree.heading("kind", text="Type")
            self.tree.column("path", width=420)
            self.tree.column("lba", width=90, anchor=tk.E)
            self.tree.column("size", width=110, anchor=tk.E)
            self.tree.column("kind", width=70, anchor=tk.CENTER)

            vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            # Actions
            bottom = ttk.Frame(self, padding=6)
            bottom.pack(side=tk.BOTTOM, fill=tk.X)

            ttk.Button(bottom, text="Extract Selected…", command=self.extract_selected).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(bottom, text="Inject / Replace…", command=self.inject_selected).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(bottom, text="Extract All…", command=self.extract_all).pack(
                side=tk.LEFT, padx=(0, 12)
            )

            self.progress = ttk.Progressbar(bottom, mode="determinate", length=180)
            self.progress.pack(side=tk.LEFT, padx=8)

            self.status = ttk.Label(bottom, text="Open an ISO extracted from bincue_gui")
            self.status.pack(side=tk.LEFT, padx=8)

            log_frame = ttk.LabelFrame(self, text="Log", padding=4)
            log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)
            self.log = tk.Text(log_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
            self.log.pack(fill=tk.X)

        def log_msg(self, msg: str):
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        def open_iso(self):
            if self.dirty:
                if not messagebox.askyesno(
                    "Unsaved changes",
                    "Image was modified. Discard changes and open another?",
                ):
                    return
            path = filedialog.askopenfilename(
                title="Open ISO image",
                filetypes=[
                    ("ISO images", "*.iso *.img *.bin"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return
            path = Path(path)
            try:
                data = bytearray(path.read_bytes())
                info = volume_info(bytes(data))
                files = list_files(bytes(data))
            except Exception as e:
                messagebox.showerror("Open failed", str(e))
                self.log_msg(f"ERROR: {e}")
                return

            self.iso_path = path
            self.iso_data = data
            self.dirty = False
            self.path_label.configure(text=str(path))
            self.info_label.configure(
                text=(
                    f"Volume: {info['volume_name'] or '(none)'}  |  "
                    f"{info['volume_sectors']} sectors (PVD)  |  "
                    f"image {info['image_size']:,} bytes  |  "
                    f"{sum(1 for f in files if not f[3])} files"
                )
            )
            self._populate(files)
            self.status.configure(text=f"Loaded {path.name}")
            self.log_msg(f"Opened {path} ({info['image_size']:,} bytes)")

        def _populate(self, files: List[Tuple[str, int, int, bool]]):
            self.tree.delete(*self.tree.get_children())
            for path, lba, size, is_dir in files:
                kind = "DIR" if is_dir else "FILE"
                self.tree.insert(
                    "",
                    tk.END,
                    iid=path,
                    values=(
                        path,
                        lba,
                        f"{size:,}" if not is_dir else "—",
                        kind,
                    ),
                )

        def _selected_files(self) -> List[str]:
            sel = self.tree.selection()
            out = []
            for iid in sel:
                vals = self.tree.item(iid, "values")
                if vals and vals[3] == "FILE":
                    out.append(vals[0])
            return out

        def extract_selected(self):
            if not self.iso_data:
                messagebox.showinfo("No ISO", "Open an ISO first.")
                return
            names = self._selected_files()
            if not names:
                messagebox.showinfo("Select", "Select one or more files (not directories).")
                return
            out_dir = filedialog.askdirectory(title="Extract to folder")
            if not out_dir:
                return
            out_dir = Path(out_dir)
            ok = 0
            for name in names:
                try:
                    data = extract_file(bytes(self.iso_data), name)
                    dest = out_dir / Path(name).name
                    dest.write_bytes(data)
                    self.log_msg(f"Extracted {name} → {dest.name} ({len(data):,} bytes)")
                    ok += 1
                except Exception as e:
                    self.log_msg(f"ERROR {name}: {e}")
            self.status.configure(text=f"Extracted {ok} file(s)")
            messagebox.showinfo("Done", f"Extracted {ok} file(s) to\n{out_dir}")

        def extract_all(self):
            if not self.iso_data:
                messagebox.showinfo("No ISO", "Open an ISO first.")
                return
            out_dir = filedialog.askdirectory(title="Extract all files to folder")
            if not out_dir:
                return
            out_dir = Path(out_dir)

            def worker():
                files = [f for f in list_files(bytes(self.iso_data)) if not f[3]]
                total = len(files)
                for i, (name, lba, size, _) in enumerate(files):
                    try:
                        data = extract_file(bytes(self.iso_data), name)
                        # preserve relative path under out_dir
                        dest = out_dir / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
                        self.after(
                            0,
                            lambda n=name, d=len(data), i=i: (
                                self.log_msg(f"Extracted {n} ({d:,} bytes)"),
                                self.progress.configure(
                                    value=int(100 * (i + 1) / total)
                                ),
                            ),
                        )
                    except Exception as e:
                        self.after(
                            0, lambda n=name, e=e: self.log_msg(f"ERROR {n}: {e}")
                        )
                self.after(
                    0,
                    lambda: (
                        self.progress.configure(value=0),
                        self.status.configure(text=f"Extracted {total} files"),
                        messagebox.showinfo(
                            "Done", f"Extracted {total} files to\n{out_dir}"
                        ),
                    ),
                )

            self.status.configure(text="Extracting…")
            threading.Thread(target=worker, daemon=True).start()

        def inject_selected(self):
            if not self.iso_data:
                messagebox.showinfo("No ISO", "Open an ISO first.")
                return
            names = self._selected_files()
            if len(names) != 1:
                messagebox.showinfo(
                    "Select one file",
                    "Select exactly one file in the list to replace.",
                )
                return
            target = names[0]
            try:
                _, orig_size, _ = find_file(bytes(self.iso_data), target)
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            repl = filedialog.askopenfilename(
                title=f"Replacement for {target} ({orig_size:,} bytes on disc)",
                filetypes=[("All files", "*.*")],
            )
            if not repl:
                return
            repl_path = Path(repl)
            data = repl_path.read_bytes()

            msg = (
                f"Replace  {target}\n"
                f"  on-disc size : {orig_size:,} bytes\n"
                f"  replacement  : {len(data):,} bytes\n\n"
            )
            if len(data) > orig_size:
                msg += "ERROR: replacement is larger – cannot inject.\n"
                messagebox.showerror("Too large", msg)
                return
            if len(data) < orig_size:
                msg += "Replacement is smaller; will zero-pad to original size.\n\n"
            msg += "Modify the image in memory? (use Save ISO when done)"
            if not messagebox.askyesno("Confirm inject", msg):
                return

            try:
                summary = replace_file(self.iso_data, target, data, must_fit=True)
                self.dirty = True
                self.log_msg(
                    f"Injected {repl_path.name} → {target} "
                    f"(LBA {summary['lba']}, {summary['written']:,} bytes)"
                )
                self.status.configure(text=f"Injected {target} (unsaved)")
                self.path_label.configure(
                    text=f"{self.iso_path}  [modified]"
                )
                messagebox.showinfo(
                    "Injected",
                    f"Replaced {target} in memory.\n\n"
                    f"LBA {summary['lba']}  wrote {summary['written']:,} bytes\n\n"
                    "Click Save ISO, then use bincue_gui → Replace Selected\n"
                    "to write this ISO back into the BIN.",
                )
            except Exception as e:
                messagebox.showerror("Inject failed", str(e))
                self.log_msg(f"ERROR inject: {e}")

        def save_iso(self):
            if not self.iso_data or not self.iso_path:
                messagebox.showinfo("Nothing", "No image loaded.")
                return
            if not self.dirty:
                messagebox.showinfo("No changes", "Image was not modified.")
                return
            self.iso_path.write_bytes(self.iso_data)
            self.dirty = False
            self.path_label.configure(text=str(self.iso_path))
            self.log_msg(f"Saved {self.iso_path}")
            self.status.configure(text="Saved")
            messagebox.showinfo("Saved", f"Wrote\n{self.iso_path}")

        def save_iso_as(self):
            if not self.iso_data:
                messagebox.showinfo("Nothing", "No image loaded.")
                return
            path = filedialog.asksaveasfilename(
                title="Save ISO as",
                defaultextension=".iso",
                filetypes=[("ISO images", "*.iso"), ("All files", "*.*")],
            )
            if not path:
                return
            path = Path(path)
            path.write_bytes(self.iso_data)
            self.iso_path = path
            self.dirty = False
            self.path_label.configure(text=str(path))
            self.log_msg(f"Saved as {path}")
            self.status.configure(text="Saved")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("Usage:")
        print("  python3 tuximage.py                  # GUI")
        print("  python3 tuximage.py list  file.iso")
        print("  python3 tuximage.py extract file.iso SLUS_006.28 -o SLUS_006.28")
        print("  python3 tuximage.py inject  file.iso SLUS_006.28 patched.bin")
        return

    # CLI mode
    if len(sys.argv) >= 3:
        cmd = sys.argv[1].lower()
        iso_path = Path(sys.argv[2])
        data = bytearray(iso_path.read_bytes())

        if cmd == "list":
            info = volume_info(bytes(data))
            print(f"Volume: {info['volume_name']!r}  sectors={info['volume_sectors']}")
            for path, lba, size, is_dir in list_files(bytes(data)):
                kind = "DIR " if is_dir else "FILE"
                print(f"  {kind}  LBA={lba:6d}  {size:10,}  {path}")
            return

        if cmd == "extract" and len(sys.argv) >= 4:
            name = sys.argv[3]
            out = Path(sys.argv[sys.argv.index("-o") + 1]) if "-o" in sys.argv else Path(name).name
            blob = extract_file(bytes(data), name)
            out.write_bytes(blob)
            print(f"Wrote {out} ({len(blob):,} bytes)")
            return

        if cmd == "inject" and len(sys.argv) >= 5:
            name = sys.argv[3]
            repl = Path(sys.argv[4]).read_bytes()
            summary = replace_file(data, name, repl, must_fit=True)
            iso_path.write_bytes(data)
            print(
                f"Injected {name}: LBA {summary['lba']}, "
                f"{summary['written']:,} / {summary['original_size']:,} bytes → {iso_path}"
            )
            return

        print("Unknown command. Use --help.")
        sys.exit(1)

    if not HAS_TK:
        print("ERROR: tkinter not available (sudo apt install python3-tk)")
        print("CLI still works: python3 tuximage.py list file.iso")
        sys.exit(1)

    app = TuxImageApp()
    app.mainloop()


if __name__ == "__main__":
    main()
