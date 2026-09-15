#!/usr/bin/env python3
"""
tuximage.py – Disc image file browser / injector (CDmage-style for Linux)

Open a CUE once, list files inside the data track, replace one file in-place
in the BIN. No extract-to-ISO / rewrite-track round trip (that double-handled
sectors and broke boots).

  python3 tuximage.py                  # GUI
  python3 tuximage.py list  game.cue
  python3 tuximage.py inject game.cue SLUS_006.28 patched.bin

Also opens plain 2048-byte/sector .iso files if you already have one.
"""

from __future__ import annotations

import struct
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None  # type: ignore

# Optional: reuse CUE parser from companion tool
try:
    from bincue_gui import parse_cue, Track, CueSheet
except ImportError:
    parse_cue = None  # type: ignore
    Track = None  # type: ignore
    CueSheet = None  # type: ignore

USER_SECTOR = 2048


# ---------------------------------------------------------------------------
# Sector mapping – read/write 2048-byte logical sectors through a raw track
# ---------------------------------------------------------------------------

@dataclass
class DiscBackend:
    """Abstract view of a 2048-byte/sector filesystem image."""

    label: str

    def size_bytes(self) -> int:
        raise NotImplementedError

    def read_logical(self, lba: int, n_sectors: int = 1) -> bytes:
        raise NotImplementedError

    def write_logical(self, lba: int, data: bytes) -> None:
        raise NotImplementedError

    def flush(self) -> None:
        pass


@dataclass
class IsoFileBackend(DiscBackend):
    """Plain .iso (already 2048 user data per sector)."""

    path: Path
    data: bytearray
    dirty: bool = False

    def size_bytes(self) -> int:
        return len(self.data)

    def read_logical(self, lba: int, n_sectors: int = 1) -> bytes:
        start = lba * USER_SECTOR
        end = start + n_sectors * USER_SECTOR
        return bytes(self.data[start:end])

    def write_logical(self, lba: int, data: bytes) -> None:
        start = lba * USER_SECTOR
        end = start + len(data)
        if end > len(self.data):
            raise ValueError("Write past end of ISO")
        self.data[start:end] = data
        self.dirty = True

    def flush(self) -> None:
        if self.dirty:
            self.path.write_bytes(self.data)
            self.dirty = False


@dataclass
class CueTrackBackend(DiscBackend):
    """
    Data track inside a BIN referenced by a CUE.

    Logical LBA 0 = first sector of the track (INDEX 01).
    Reads/writes only the user-data field of each 2352/2048 sector so
    sync/header/EDC stay untouched (same idea as CDmage file replace).
    """

    bin_path: Path
    track_file_offset_sectors: int  # where track starts in BIN
    track_length_sectors: int
    sector_size: int  # 2352 or 2048
    user_offset: int  # 16 MODE1/2352, 24 MODE2/2352, 0 for 2048
    user_size: int = USER_SECTOR
    mode: str = ""
    dirty: bool = False

    def size_bytes(self) -> int:
        return self.track_length_sectors * self.user_size

    def _bin_byte(self, logical_lba: int) -> int:
        return (self.track_file_offset_sectors + logical_lba) * self.sector_size + self.user_offset

    def read_logical(self, lba: int, n_sectors: int = 1) -> bytes:
        if lba < 0 or lba + n_sectors > self.track_length_sectors:
            raise ValueError(f"LBA {lba}+{n_sectors} outside track")
        out = bytearray()
        with open(self.bin_path, "rb") as f:
            for i in range(n_sectors):
                f.seek(self._bin_byte(lba + i))
                chunk = f.read(self.user_size)
                if len(chunk) < self.user_size:
                    chunk = chunk + b"\x00" * (self.user_size - len(chunk))
                out.extend(chunk)
        return bytes(out)

    def write_logical(self, lba: int, data: bytes) -> None:
        if len(data) % self.user_size != 0:
            # pad last sector
            pad = self.user_size - (len(data) % self.user_size)
            if pad != self.user_size:
                data = data + b"\x00" * pad
        n = len(data) // self.user_size
        if lba < 0 or lba + n > self.track_length_sectors:
            raise ValueError(f"Write LBA {lba}+{n} outside track ({self.track_length_sectors})")
        with open(self.bin_path, "r+b") as f:
            for i in range(n):
                f.seek(self._bin_byte(lba + i))
                f.write(data[i * self.user_size : (i + 1) * self.user_size])
        self.dirty = True

    def flush(self) -> None:
        # writes are direct to BIN; nothing buffered
        self.dirty = False


def backend_from_cue(cue_path: Path, track_number: Optional[int] = None) -> CueTrackBackend:
    if parse_cue is None:
        raise RuntimeError("bincue_gui.py not found – place it next to tuximage.py")
    sheet = parse_cue(cue_path)
    data_tracks = [t for t in sheet.tracks if not t.is_audio]
    if not data_tracks:
        raise ValueError("No data track in CUE")
    if track_number is None:
        track = data_tracks[0]
    else:
        track = next((t for t in sheet.tracks if t.number == track_number), None)
        if track is None or track.is_audio:
            raise ValueError(f"Data track {track_number} not found")
    if not track.file_path or not track.file_path.is_file():
        raise FileNotFoundError(f"BIN not found: {track.file_path}")
    return CueTrackBackend(
        label=f"{cue_path.name}  track {track.number:02d} ({track.mode})",
        bin_path=track.file_path,
        track_file_offset_sectors=track.file_offset_sectors,
        track_length_sectors=track.length_sectors,
        sector_size=track.sector_size,
        user_offset=track.user_data_offset,
        user_size=track.user_data_size if track.user_data_size else USER_SECTOR,
        mode=track.mode,
    )


def backend_from_iso(iso_path: Path) -> IsoFileBackend:
    data = bytearray(iso_path.read_bytes())
    return IsoFileBackend(label=str(iso_path), path=iso_path, data=data)


# ---------------------------------------------------------------------------
# ISO 9660 over a DiscBackend (logical 2048-byte sectors)
# ---------------------------------------------------------------------------

def _read_range(backend: DiscBackend, lba: int, size: int) -> bytes:
    n = (size + USER_SECTOR - 1) // USER_SECTOR
    blob = backend.read_logical(lba, n)
    return blob[:size]


def find_pvd_backend(backend: DiscBackend) -> int:
    """Return logical LBA of PVD."""
    for s in range(16, 32):
        sec = backend.read_logical(s, 1)
        if len(sec) >= 6 and sec[0] == 1 and sec[1:6] == b"CD001":
            return s
    raise ValueError("ISO 9660 Primary Volume Descriptor not found")


def _walk_dir_backend(
    backend: DiscBackend,
    extent_lba: int,
    size: int,
    *,
    target_upper: Optional[str] = None,
    path_prefix: str = "",
    max_depth: int = 8,
    depth: int = 0,
    results: Optional[List[Tuple[str, int, int, bool]]] = None,
) -> Optional[Tuple[int, int]]:
    if results is None:
        results = []
    if depth > max_depth:
        return None

    data = _read_range(backend, extent_lba, size)
    pos = 0
    while pos < len(data):
        length = data[pos]
        if length == 0:
            pos = ((pos // USER_SECTOR) + 1) * USER_SECTOR
            continue
        if pos + length > len(data):
            break
        flags = data[pos + 25]
        loc = struct.unpack_from("<I", data, pos + 2)[0]
        datalen = struct.unpack_from("<I", data, pos + 10)[0]
        name_len = data[pos + 32]
        raw = data[pos + 33 : pos + 33 + name_len]
        if raw in (b"\x00", b"\x01"):
            pos += length
            continue
        name = raw.split(b";")[0].decode("ascii", errors="replace")
        is_dir = bool(flags & 0x02)
        path = f"{path_prefix}{name}"
        if is_dir:
            results.append((path + "/", loc, datalen, True))
            found = _walk_dir_backend(
                backend, loc, datalen,
                target_upper=target_upper,
                path_prefix=path + "/",
                max_depth=max_depth,
                depth=depth + 1,
                results=results,
            )
            if found is not None:
                return found
        else:
            results.append((path, loc, datalen, False))
            if target_upper and (
                name.upper() == target_upper or path.upper() == target_upper
            ):
                return (loc, datalen)
        pos += length
    return None


def list_files(backend: DiscBackend, max_depth: int = 8) -> List[Tuple[str, int, int, bool]]:
    pvd_lba = find_pvd_backend(backend)
    pvd = backend.read_logical(pvd_lba, 1)
    root_extent = struct.unpack_from("<I", pvd, 158)[0]
    root_size = struct.unpack_from("<I", pvd, 166)[0]
    results: List[Tuple[str, int, int, bool]] = []
    _walk_dir_backend(backend, root_extent, root_size, max_depth=max_depth, results=results)
    return results


def find_file(backend: DiscBackend, filename: str) -> Tuple[int, int]:
    pvd_lba = find_pvd_backend(backend)
    pvd = backend.read_logical(pvd_lba, 1)
    root_extent = struct.unpack_from("<I", pvd, 158)[0]
    root_size = struct.unpack_from("<I", pvd, 166)[0]
    target = filename.upper().lstrip("/")
    results: List[Tuple[str, int, int, bool]] = []
    found = _walk_dir_backend(
        backend, root_extent, root_size, target_upper=target, results=results
    )
    if found is not None:
        return found
    for path, lba, sz, is_dir in results:
        if is_dir:
            continue
        if path.rstrip("/").split("/")[-1].upper() == target:
            return lba, sz
    raise FileNotFoundError(f"{filename!r} not found on disc")


def extract_file(backend: DiscBackend, filename: str) -> bytes:
    lba, size = find_file(backend, filename)
    return _read_range(backend, lba, size)


def replace_file(
    backend: DiscBackend,
    filename: str,
    new_data: bytes,
    *,
    must_fit: bool = True,
) -> dict:
    """Overwrite file extent in-place (user data only). Same size or pad."""
    lba, size = find_file(backend, filename)
    if len(new_data) > size and must_fit:
        raise ValueError(
            f"{filename} is {size:,} bytes on disc; replacement is "
            f"{len(new_data):,} bytes. Keep the same size."
        )
    payload = new_data[:size].ljust(size, b"\x00")
    backend.write_logical(lba, payload)
    return {
        "file": filename,
        "lba": lba,
        "original_size": size,
        "written": len(payload),
    }


def volume_info(backend: DiscBackend) -> dict:
    pvd_lba = find_pvd_backend(backend)
    pvd = backend.read_logical(pvd_lba, 1)
    vol_space = struct.unpack_from("<I", pvd, 80)[0]
    vol_name = pvd[40:72].decode("ascii", errors="replace").strip()
    return {
        "pvd_lba": pvd_lba,
        "volume_name": vol_name,
        "volume_sectors": vol_space,
        "image_size": backend.size_bytes(),
        "label": backend.label,
    }


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

if HAS_TK:

    class TuxImageApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("tuximage – disc file inject (CDmage-style)")
            self.geometry("920x600")
            self.minsize(740, 440)

            self.backend: Optional[DiscBackend] = None
            self.source_path: Optional[Path] = None

            self._build_ui()

        def _build_ui(self):
            toolbar = ttk.Frame(self, padding=6)
            toolbar.pack(side=tk.TOP, fill=tk.X)

            ttk.Button(toolbar, text="Open CUE…", command=self.open_cue).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            ttk.Button(toolbar, text="Open ISO…", command=self.open_iso).pack(
                side=tk.LEFT, padx=(0, 12)
            )
            ttk.Button(toolbar, text="Save", command=self.save).pack(
                side=tk.LEFT, padx=(0, 6)
            )

            self.path_label = ttk.Label(
                toolbar, text="Open a .cue (preferred) or .iso", foreground="#555"
            )
            self.path_label.pack(side=tk.LEFT, padx=8)

            info = ttk.Frame(self, padding=(8, 0))
            info.pack(side=tk.TOP, fill=tk.X)
            self.info_label = ttk.Label(info, text="")
            self.info_label.pack(side=tk.LEFT)

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
            self.tree.column("path", width=440)
            self.tree.column("lba", width=90, anchor=tk.E)
            self.tree.column("size", width=110, anchor=tk.E)
            self.tree.column("kind", width=70, anchor=tk.CENTER)

            vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            bottom = ttk.Frame(self, padding=6)
            bottom.pack(side=tk.BOTTOM, fill=tk.X)

            ttk.Button(
                bottom, text="Extract Selected…", command=self.extract_selected
            ).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(
                bottom, text="Replace Selected…", command=self.replace_selected
            ).pack(side=tk.LEFT, padx=(0, 12))

            self.status = ttk.Label(
                bottom, text="CUE → pick file → Replace → done (writes BIN directly)"
            )
            self.status.pack(side=tk.LEFT, padx=8)

            log_frame = ttk.LabelFrame(self, text="Log", padding=4)
            log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)
            self.log = tk.Text(log_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
            self.log.pack(fill=tk.X)

        def log_msg(self, msg: str):
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        def _load_backend(self, backend: DiscBackend, source: Path):
            try:
                info = volume_info(backend)
                files = list_files(backend)
            except Exception as e:
                messagebox.showerror("Open failed", str(e))
                self.log_msg(f"ERROR: {e}")
                return
            self.backend = backend
            self.source_path = source
            self.path_label.configure(text=backend.label)
            nfiles = sum(1 for f in files if not f[3])
            self.info_label.configure(
                text=(
                    f"Volume: {info['volume_name'] or '(none)'}  |  "
                    f"PVD LBA {info['pvd_lba']}  |  "
                    f"{info['volume_sectors']} vol sectors  |  "
                    f"{nfiles} files"
                )
            )
            self.tree.delete(*self.tree.get_children())
            for path, lba, size, is_dir in files:
                self.tree.insert(
                    "",
                    tk.END,
                    iid=path,
                    values=(
                        path,
                        lba,
                        "—" if is_dir else f"{size:,}",
                        "DIR" if is_dir else "FILE",
                    ),
                )
            self.status.configure(text=f"Loaded – {nfiles} files")
            self.log_msg(f"Opened {backend.label}")

        def open_cue(self):
            if parse_cue is None:
                messagebox.showerror(
                    "Missing bincue_gui",
                    "tuximage needs bincue_gui.py in the same folder\n"
                    "to parse CUE sheets.",
                )
                return
            path = filedialog.askopenfilename(
                title="Open CUE sheet",
                filetypes=[("CUE sheets", "*.cue"), ("All files", "*.*")],
            )
            if not path:
                return
            path = Path(path)
            try:
                backend = backend_from_cue(path)
            except Exception as e:
                messagebox.showerror("CUE open failed", str(e))
                self.log_msg(f"ERROR: {e}")
                return
            self._load_backend(backend, path)
            self.log_msg(
                f"Data track → {backend.bin_path.name}  "
                f"mode={backend.mode}  sectors={backend.track_length_sectors}  "
                f"user_off={backend.user_offset}"
            )

        def open_iso(self):
            path = filedialog.askopenfilename(
                title="Open ISO (2048-byte sectors)",
                filetypes=[
                    ("ISO images", "*.iso *.img"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return
            path = Path(path)
            try:
                backend = backend_from_iso(path)
            except Exception as e:
                messagebox.showerror("ISO open failed", str(e))
                return
            self._load_backend(backend, path)

        def _selected_files(self) -> List[str]:
            out = []
            for iid in self.tree.selection():
                vals = self.tree.item(iid, "values")
                if vals and vals[3] == "FILE":
                    out.append(vals[0])
            return out

        def extract_selected(self):
            if not self.backend:
                messagebox.showinfo("No disc", "Open a CUE or ISO first.")
                return
            names = self._selected_files()
            if not names:
                messagebox.showinfo("Select", "Select one or more files.")
                return
            out_dir = filedialog.askdirectory(title="Extract to folder")
            if not out_dir:
                return
            out_dir = Path(out_dir)
            ok = 0
            for name in names:
                try:
                    data = extract_file(self.backend, name)
                    dest = out_dir / Path(name).name
                    dest.write_bytes(data)
                    self.log_msg(f"Extracted {name} ({len(data):,} bytes)")
                    ok += 1
                except Exception as e:
                    self.log_msg(f"ERROR {name}: {e}")
            messagebox.showinfo("Done", f"Extracted {ok} file(s) to\n{out_dir}")

        def replace_selected(self):
            if not self.backend:
                messagebox.showinfo("No disc", "Open a CUE or ISO first.")
                return
            names = self._selected_files()
            if len(names) != 1:
                messagebox.showinfo("Select one", "Select exactly one file to replace.")
                return
            target = names[0]
            try:
                _, orig_size = find_file(self.backend, target)
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            repl = filedialog.askopenfilename(
                title=f"Replacement for {target} ({orig_size:,} bytes on disc)",
            )
            if not repl:
                return
            repl_path = Path(repl)
            data = repl_path.read_bytes()

            if len(data) > orig_size:
                messagebox.showerror(
                    "Too large",
                    f"On disc: {orig_size:,} bytes\n"
                    f"Replacement: {len(data):,} bytes\n\n"
                    "File must be the same size or smaller.",
                )
                return

            msg = (
                f"Replace {target} on disc\n"
                f"  size on disc : {orig_size:,}\n"
                f"  replacement  : {len(data):,}\n\n"
            )
            if isinstance(self.backend, CueTrackBackend):
                msg += f"Writes directly into:\n  {self.backend.bin_path}\n\n"
            if len(data) < orig_size:
                msg += "Shorter file will be zero-padded.\n\n"
            msg += "Continue?"
            if not messagebox.askyesno("Confirm replace", msg):
                return

            try:
                summary = replace_file(self.backend, target, data, must_fit=True)
                self.backend.flush()
                self.log_msg(
                    f"Replaced {target}  LBA={summary['lba']}  "
                    f"wrote {summary['written']:,} bytes"
                )
                if isinstance(self.backend, CueTrackBackend):
                    self.log_msg(f"BIN updated: {self.backend.bin_path}")
                    self.status.configure(text="Done – BIN written (boot the CUE)")
                else:
                    self.status.configure(text="Done – ISO updated in memory, Save if needed")
                messagebox.showinfo(
                    "Replaced",
                    f"{target} updated.\n"
                    f"LBA {summary['lba']}  {summary['written']:,} bytes\n\n"
                    + (
                        f"BIN:\n{self.backend.bin_path}\n\nBoot the original CUE."
                        if isinstance(self.backend, CueTrackBackend)
                        else "Use Save if this is a standalone ISO."
                    ),
                )
            except Exception as e:
                messagebox.showerror("Replace failed", str(e))
                self.log_msg(f"ERROR: {e}")

        def save(self):
            if not self.backend:
                return
            if isinstance(self.backend, IsoFileBackend):
                if not self.backend.dirty:
                    messagebox.showinfo("No changes", "Nothing to save.")
                    return
                self.backend.flush()
                self.log_msg(f"Saved {self.backend.path}")
                messagebox.showinfo("Saved", str(self.backend.path))
            else:
                # CUE backend already wrote through to BIN
                messagebox.showinfo(
                    "Already on disc",
                    "CUE mode writes the BIN immediately on Replace.\n"
                    "Nothing extra to save.",
                )


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return

    if len(sys.argv) >= 3:
        cmd = sys.argv[1].lower()
        src = Path(sys.argv[2])
        if src.suffix.lower() == ".cue":
            backend = backend_from_cue(src)
        else:
            backend = backend_from_iso(src)

        if cmd == "list":
            info = volume_info(backend)
            print(f"{info['label']}")
            print(f"Volume: {info['volume_name']!r}  sectors={info['volume_sectors']}")
            for path, lba, size, is_dir in list_files(backend):
                kind = "DIR " if is_dir else "FILE"
                print(f"  {kind}  LBA={lba:6d}  {size:10,}  {path}")
            return

        if cmd == "extract" and len(sys.argv) >= 4:
            name = sys.argv[3]
            out = Path(sys.argv[sys.argv.index("-o") + 1]) if "-o" in sys.argv else Path(name).name
            blob = extract_file(backend, name)
            out.write_bytes(blob)
            print(f"Wrote {out} ({len(blob):,} bytes)")
            return

        if cmd == "inject" and len(sys.argv) >= 5:
            name = sys.argv[3]
            repl = Path(sys.argv[4]).read_bytes()
            summary = replace_file(backend, name, repl, must_fit=True)
            backend.flush()
            print(
                f"Replaced {name}: LBA {summary['lba']}, "
                f"{summary['written']:,}/{summary['original_size']:,} bytes"
            )
            if isinstance(backend, CueTrackBackend):
                print(f"BIN: {backend.bin_path}")
            return

        print("Unknown command. Use --help.")
        sys.exit(1)

    if not HAS_TK:
        print("ERROR: tkinter not available (sudo apt install python3-tk)")
        sys.exit(1)

    app = TuxImageApp()
    app.mainloop()


if __name__ == "__main__":
    main()
