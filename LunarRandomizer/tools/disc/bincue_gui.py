#!/usr/bin/env python3
"""
bincue_gui.py – View & Extract BIN/CUE disc images

Pure Python 3 + tkinter. Designed to be used standalone or imported
into a larger randomizer GUI (same pattern as previous tools).

Supports:
  - Single-file and multi-file (one BIN per track) CUE sheets
  - Data tracks → ISO (user data) or raw
  - Audio tracks → WAV (with header) or RAW (CDR)
  - Common modes: MODE1/2048, MODE1/2352, MODE2/2352, AUDIO, etc.
  - Replace track contents in-place (ISO user-data or raw)
  - Inject/replace a file inside an extracted ISO (iso_replace_file)
"""

from __future__ import annotations

import os
import re
import struct
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# tkinter is optional so the core parser/extractor can be imported
# even in headless environments (or when python3-tk is not installed).
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None  # type: ignore


# ---------------------------------------------------------------------------
# Core data structures & CUE parsing / extraction
# ---------------------------------------------------------------------------

SECTORS_PER_SECOND = 75


def time_to_sectors(t: str) -> int:
    """Convert MM:SS:FF to absolute sector number."""
    parts = t.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid time stamp: {t}")
    m, s, f = (int(x) for x in parts)
    return (m * 60 + s) * SECTORS_PER_SECOND + f


def sectors_to_time(sectors: int) -> str:
    """Convert sector count to MM:SS:FF."""
    frames = sectors % SECTORS_PER_SECOND
    total_sec = sectors // SECTORS_PER_SECOND
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins:02d}:{secs:02d}:{frames:02d}"


@dataclass
class Index:
    number: int
    time: str
    sector: int


@dataclass
class Track:
    number: int
    mode: str                     # e.g. "MODE1/2352", "AUDIO"
    indexes: List[Index] = field(default_factory=list)
    file_path: Optional[Path] = None
    file_offset_sectors: int = 0  # where this track starts inside its BIN
    # computed later
    start_sector: int = 0
    end_sector: int = 0
    length_sectors: int = 0

    @property
    def is_audio(self) -> bool:
        return self.mode.upper() == "AUDIO" or self.mode.upper().startswith("AUDIO")

    @property
    def sector_size(self) -> int:
        m = self.mode.upper()
        if "2048" in m:
            return 2048
        if "2336" in m:
            return 2336
        if "2352" in m or self.is_audio:
            return 2352
        # fallback – most raw dumps are 2352
        return 2352

    @property
    def user_data_offset(self) -> int:
        """Byte offset inside a sector where user data starts."""
        m = self.mode.upper()
        if "MODE1/2048" in m:
            return 0
        if "MODE1/2352" in m:
            return 16
        if "MODE2/2352" in m:
            return 24          # common for PSX / Mode2 Form1
        if "MODE2/2336" in m:
            return 0
        if self.is_audio:
            return 0
        return 0

    @property
    def user_data_size(self) -> int:
        if self.is_audio:
            return 2352
        m = self.mode.upper()
        if "2048" in m:
            return 2048
        if "MODE2/2352" in m:
            return 2048        # Form1 user data
        if "2336" in m:
            return 2336
        return 2048


@dataclass
class CueSheet:
    cue_path: Path
    files: List[Path] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    title: str = ""
    performer: str = ""


def parse_cue(cue_path: Path) -> CueSheet:
    """Parse a .cue file into a CueSheet object."""
    cue_path = cue_path.resolve()
    text = cue_path.read_text(encoding="utf-8", errors="replace")

    sheet = CueSheet(cue_path=cue_path)
    current_file: Optional[Path] = None
    current_track: Optional[Track] = None
    file_sector_base = 0          # cumulative sectors for multi-file images

    # Simple line-based parser (robust enough for real-world Redump / Alcohol / etc.)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("REM"):
            # still capture TITLE / PERFORMER from REM if present
            if line.upper().startswith("REM TITLE"):
                sheet.title = line[9:].strip().strip('"')
            elif line.upper().startswith("REM PERFORMER"):
                sheet.performer = line[13:].strip().strip('"')
            continue

        # FILE "name.bin" BINARY
        m = re.match(r'FILE\s+"?([^"]+)"?\s+(\w+)', line, re.IGNORECASE)
        if m:
            fname = m.group(1)
            fpath = (cue_path.parent / fname).resolve()
            sheet.files.append(fpath)
            current_file = fpath
            # for multi-file cues each FILE starts at sector 0 of that BIN
            file_sector_base = 0
            continue

        # TRACK nn MODE
        m = re.match(r'TRACK\s+(\d+)\s+(\S+)', line, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            mode = m.group(2)
            current_track = Track(number=num, mode=mode, file_path=current_file)
            sheet.tracks.append(current_track)
            continue

        # INDEX nn MM:SS:FF
        m = re.match(r'INDEX\s+(\d+)\s+(\d+:\d+:\d+)', line, re.IGNORECASE)
        if m and current_track is not None:
            idx_num = int(m.group(1))
            tstr = m.group(2)
            sector = time_to_sectors(tstr)
            current_track.indexes.append(Index(number=idx_num, time=tstr, sector=sector))
            continue

        # TITLE / PERFORMER at disc or track level
        m = re.match(r'TITLE\s+"?(.*?)"?\s*$', line, re.IGNORECASE)
        if m:
            if current_track is None:
                sheet.title = m.group(1)
            continue
        m = re.match(r'PERFORMER\s+"?(.*?)"?\s*$', line, re.IGNORECASE)
        if m:
            if current_track is None:
                sheet.performer = m.group(1)
            continue

    # ------------------------------------------------------------------
    # Compute absolute start/end sectors for every track
    # ------------------------------------------------------------------
    # We treat INDEX 01 as the real start of the track (INDEX 00 is pregap).
    # For single-BIN images the INDEX times are absolute from the start of the disc.
    # For multi-file images each FILE’s INDEX times are relative to that file.

    if not sheet.tracks:
        raise ValueError("No tracks found in CUE sheet")

    # Detect single vs multi-file
    multi_file = len(sheet.files) > 1 or any(
        t.file_path != sheet.tracks[0].file_path for t in sheet.tracks
    )

    if multi_file:
        # Each track lives in its own BIN; INDEX times are relative to that BIN
        for t in sheet.tracks:
            if not t.indexes:
                raise ValueError(f"Track {t.number} has no INDEX")
            # prefer INDEX 01, fall back to first index
            idx01 = next((i for i in t.indexes if i.number == 1), t.indexes[0])
            t.start_sector = idx01.sector
            t.file_offset_sectors = idx01.sector
            # length will be filled after we know the next track or file size
    else:
        # Classic single-BIN: INDEX times are absolute disc addresses
        for t in sheet.tracks:
            if not t.indexes:
                raise ValueError(f"Track {t.number} has no INDEX")
            idx01 = next((i for i in t.indexes if i.number == 1), t.indexes[0])
            t.start_sector = idx01.sector
            t.file_offset_sectors = idx01.sector

    # Compute end / length
    for i, t in enumerate(sheet.tracks):
        if i + 1 < len(sheet.tracks):
            next_t = sheet.tracks[i + 1]
            if multi_file and t.file_path != next_t.file_path:
                # end of this file – use file size
                if t.file_path and t.file_path.is_file():
                    fsize = t.file_path.stat().st_size
                    t.length_sectors = (fsize // t.sector_size) - t.file_offset_sectors
                else:
                    t.length_sectors = 0
            else:
                t.length_sectors = next_t.start_sector - t.start_sector
        else:
            # last track – use remaining file size
            if t.file_path and t.file_path.is_file():
                fsize = t.file_path.stat().st_size
                t.length_sectors = (fsize // t.sector_size) - t.file_offset_sectors
            else:
                t.length_sectors = 0
        t.end_sector = t.start_sector + t.length_sectors

    return sheet


def write_wav_header(f, data_size: int, sample_rate: int = 44100, channels: int = 2, bits: int = 16):
    """Write a standard 44-byte WAV header for CD audio (44.1 kHz stereo 16-bit)."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    # RIFF chunk
    f.write(b"RIFF")
    f.write(struct.pack("<I", 36 + data_size))
    f.write(b"WAVE")
    # fmt chunk
    f.write(b"fmt ")
    f.write(struct.pack("<I", 16))          # chunk size
    f.write(struct.pack("<H", 1))           # PCM
    f.write(struct.pack("<H", channels))
    f.write(struct.pack("<I", sample_rate))
    f.write(struct.pack("<I", byte_rate))
    f.write(struct.pack("<H", block_align))
    f.write(struct.pack("<H", bits))
    # data chunk
    f.write(b"data")
    f.write(struct.pack("<I", data_size))


def extract_track(
    track: Track,
    out_path: Path,
    *,
    audio_as_wav: bool = True,
    data_as_iso: bool = True,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Extract a single track to out_path.
    progress_cb(current_bytes, total_bytes) is called periodically.
    """
    if not track.file_path or not track.file_path.is_file():
        raise FileNotFoundError(f"BIN file not found: {track.file_path}")

    sector_size = track.sector_size
    start_byte = track.file_offset_sectors * sector_size
    total_bytes = track.length_sectors * sector_size

    if total_bytes <= 0:
        raise ValueError(f"Track {track.number} has zero length")

    with open(track.file_path, "rb") as src:
        src.seek(start_byte)

        if track.is_audio:
            if audio_as_wav:
                # Write WAV header then raw PCM (little-endian)
                with open(out_path, "wb") as dst:
                    write_wav_header(dst, total_bytes)
                    remaining = total_bytes
                    chunk = 1024 * 1024
                    while remaining > 0:
                        to_read = min(chunk, remaining)
                        data = src.read(to_read)
                        if not data:
                            break
                        dst.write(data)
                        remaining -= len(data)
                        if progress_cb:
                            progress_cb(total_bytes - remaining, total_bytes)
            else:
                # RAW CDR
                with open(out_path, "wb") as dst:
                    remaining = total_bytes
                    chunk = 1024 * 1024
                    while remaining > 0:
                        to_read = min(chunk, remaining)
                        data = src.read(to_read)
                        if not data:
                            break
                        dst.write(data)
                        remaining -= len(data)
                        if progress_cb:
                            progress_cb(total_bytes - remaining, total_bytes)
        else:
            # Data track
            if data_as_iso:
                # Strip sector headers / EDC / ECC → pure user data
                user_off = track.user_data_offset
                user_sz = track.user_data_size
                with open(out_path, "wb") as dst:
                    written = 0
                    for _ in range(track.length_sectors):
                        sector = src.read(sector_size)
                        if len(sector) < sector_size:
                            break
                        dst.write(sector[user_off : user_off + user_sz])
                        written += user_sz
                        if progress_cb and written % (user_sz * 512) == 0:
                            progress_cb(written, track.length_sectors * user_sz)
                    if progress_cb:
                        progress_cb(track.length_sectors * user_sz, track.length_sectors * user_sz)
            else:
                # Full raw sectors
                with open(out_path, "wb") as dst:
                    remaining = total_bytes
                    chunk = 1024 * 1024
                    while remaining > 0:
                        to_read = min(chunk, remaining)
                        data = src.read(to_read)
                        if not data:
                            break
                        dst.write(data)
                        remaining -= len(data)
                        if progress_cb:
                            progress_cb(total_bytes - remaining, total_bytes)


def _bcd(n: int) -> int:
    """Binary-coded decimal for sector headers (0–99)."""
    return ((n // 10) << 4) | (n % 10)


def _msf_from_lba(lba: int) -> Tuple[int, int, int]:
    """Absolute MSF from LBA (LBA 0 = 00:02:00)."""
    total = lba + 150
    m = total // (75 * 60)
    s = (total // 75) % 60
    f = total % 75
    return m, s, f


def build_data_sector(
    user_data: bytes,
    *,
    lba: int,
    mode: str,
    template: Optional[bytes] = None,
) -> bytes:
    """
    Build one 2352-byte data sector from 2048 bytes of user data.

    If *template* is provided (an original sector), sync/header/subheader
    are copied from it and only the user payload is replaced — ECC/EDC
    are left as-is (fine for emulators; burners may care less).
    """
    sector_size = 2352
    m = mode.upper()
    user = user_data[:2048].ljust(2048, b"\x00")

    if template is not None and len(template) >= sector_size:
        out = bytearray(template[:sector_size])
        if "MODE1/2352" in m:
            out[16:16 + 2048] = user
        elif "MODE2/2352" in m:
            out[24:24 + 2048] = user
        else:
            # MODE1/2048 image stored raw — just return user
            return user
        return bytes(out)

    # Build from scratch
    out = bytearray(sector_size)
    # Sync
    out[0] = 0x00
    out[1:11] = b"\xFF" * 10
    out[11] = 0x00
    mm, ss, ff = _msf_from_lba(lba)
    out[12] = _bcd(mm)
    out[13] = _bcd(ss)
    out[14] = _bcd(ff)

    if "MODE1" in m:
        out[15] = 0x01
        out[16:16 + 2048] = user
        # EDC/ECC left zero — OK for most emulators
    elif "MODE2" in m:
        out[15] = 0x02
        # Subheader (Form1): file=0, channel=0, submode=0x08 (data), coding=0, then copy
        out[16] = 0x00
        out[17] = 0x00
        out[18] = 0x08
        out[19] = 0x00
        out[20:24] = out[16:20]
        out[24:24 + 2048] = user
    else:
        out[16:16 + 2048] = user

    return bytes(out)


def replace_track(
    track: Track,
    replacement_path: Path,
    *,
    data_as_iso: bool = True,
    allow_shrink: bool = True,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Replace the contents of *track* inside its BIN with *replacement_path*.

    For data tracks with data_as_iso=True the replacement is treated as a
    2048-byte/sector ISO (or any file image). It is written back into the
    raw 2352-byte sectors, preserving original sync/header when possible.

    For audio or raw mode the replacement is written as a byte-for-byte
    image starting at the track's offset. Size must not exceed the track
    length (extra is truncated; shortfall is zero-padded if allow_shrink).

    Returns a summary dict: {bytes_written, sectors_written, path, ...}.
    """
    if not track.file_path or not track.file_path.is_file():
        raise FileNotFoundError(f"BIN file not found: {track.file_path}")

    replacement_path = Path(replacement_path)
    if not replacement_path.is_file():
        raise FileNotFoundError(f"Replacement not found: {replacement_path}")

    repl = replacement_path.read_bytes()
    sector_size = track.sector_size
    start_byte = track.file_offset_sectors * sector_size
    track_bytes = track.length_sectors * sector_size

    summary = {
        "track": track.number,
        "bin": str(track.file_path),
        "replacement": str(replacement_path),
        "bytes_written": 0,
        "sectors_written": 0,
    }

    # ---- Audio or raw data dump ----
    if track.is_audio or not data_as_iso:
        if len(repl) > track_bytes:
            repl = repl[:track_bytes]
        elif len(repl) < track_bytes:
            if not allow_shrink:
                raise ValueError(
                    f"Replacement is {len(repl)} bytes but track holds {track_bytes}"
                )
            repl = repl + b"\x00" * (track_bytes - len(repl))

        with open(track.file_path, "r+b") as bin_f:
            bin_f.seek(start_byte)
            bin_f.write(repl)
        summary["bytes_written"] = len(repl)
        summary["sectors_written"] = len(repl) // sector_size
        if progress_cb:
            progress_cb(len(repl), len(repl))
        return summary

    # ---- Data track, ISO / user-data mode ----
    user_sz = track.user_data_size
    capacity = track.length_sectors * user_sz
    if len(repl) > capacity:
        repl = repl[:capacity]
    elif len(repl) < capacity and not allow_shrink:
        raise ValueError(
            f"Replacement is {len(repl)} bytes but track user-data holds {capacity}"
        )

    # Read original sectors as templates so headers stay intact
    with open(track.file_path, "rb") as src:
        src.seek(start_byte)
        templates = [src.read(sector_size) for _ in range(track.length_sectors)]

    sectors_out: List[bytes] = []
    offset = 0
    for i in range(track.length_sectors):
        chunk = repl[offset : offset + user_sz]
        if len(chunk) < user_sz:
            chunk = chunk + b"\x00" * (user_sz - len(chunk))
        offset += user_sz
        tmpl = templates[i] if i < len(templates) else None
        if sector_size == 2048:
            sectors_out.append(chunk[:2048])
        else:
            # Absolute LBA ≈ track start on disc; for header rebuild only
            lba = track.start_sector + i
            sectors_out.append(
                build_data_sector(chunk, lba=lba, mode=track.mode, template=tmpl)
            )
        if progress_cb and (i + 1) % 512 == 0:
            progress_cb(i + 1, track.length_sectors)

    blob = b"".join(sectors_out)
    with open(track.file_path, "r+b") as bin_f:
        bin_f.seek(start_byte)
        bin_f.write(blob)

    summary["bytes_written"] = len(blob)
    summary["sectors_written"] = len(sectors_out)
    summary["user_bytes"] = min(len(repl), capacity)
    if progress_cb:
        progress_cb(track.length_sectors, track.length_sectors)
    return summary




# ---------------------------------------------------------------------------
# ISO 9660 helpers – find / replace a file inside a 2048-byte/sector image
# ---------------------------------------------------------------------------

def _iso_find_pvd(iso: bytes) -> int:
    """Return byte offset of the Primary Volume Descriptor."""
    for s in range(16, min(32, len(iso) // 2048)):
        off = s * 2048
        if off + 6 <= len(iso) and iso[off] == 1 and iso[off + 1 : off + 6] == b"CD001":
            return off
    raise ValueError("ISO 9660 Primary Volume Descriptor not found")


def _iso_walk_dir(
    iso: bytes,
    extent_lba: int,
    size: int,
    target_upper: str,
    path_prefix: str = "",
) -> Optional[Tuple[int, int, int, int]]:
    """
    Recursively search directory records.
    Returns (file_lba, file_size, dirent_offset, name_len) or None.
    """
    start = extent_lba * 2048
    data_end = min(start + size, len(iso))
    pos = start
    while pos < data_end:
        length = iso[pos]
        if length == 0:
            pos = ((pos // 2048) + 1) * 2048
            continue
        if pos + length > len(iso):
            break
        flags = iso[pos + 25]
        loc = struct.unpack_from("<I", iso, pos + 2)[0]
        datalen = struct.unpack_from("<I", iso, pos + 10)[0]
        name_len = iso[pos + 32]
        raw_name = iso[pos + 33 : pos + 33 + name_len]
        if raw_name in (b"\x00", b"\x01"):
            pos += length
            continue
        name = raw_name.split(b";")[0].decode("ascii", errors="replace")
        is_dir = bool(flags & 0x02)
        full = f"{path_prefix}{name}"
        if is_dir:
            found = _iso_walk_dir(iso, loc, datalen, target_upper, full + "/")
            if found is not None:
                return found
        else:
            if name.upper() == target_upper or full.upper() == target_upper:
                return (loc, datalen, pos, name_len)
            if name.upper() == target_upper:
                return (loc, datalen, pos, name_len)
        pos += length
    return None


def iso_find_file(iso: bytes, filename: str) -> Tuple[int, int, int]:
    """
    Locate *filename* (e.g. 'SLUS_006.28' or 'SYSTEM.CNF') in an ISO image.
    Returns (lba, size_bytes, dirent_byte_offset).
    """
    pvd = _iso_find_pvd(iso)
    root_extent = struct.unpack_from("<I", iso, pvd + 158)[0]
    root_size = struct.unpack_from("<I", iso, pvd + 166)[0]
    target = filename.upper().lstrip("/")
    found = _iso_walk_dir(iso, root_extent, root_size, target)
    if found is None:
        raise FileNotFoundError(f"{filename!r} not found in ISO image")
    lba, size, dirent_off, _ = found
    return lba, size, dirent_off


def iso_list_files(iso: bytes, max_depth: int = 4) -> List[Tuple[str, int, int, bool]]:
    """Return list of (path, lba, size, is_dir)."""
    pvd = _iso_find_pvd(iso)
    root_extent = struct.unpack_from("<I", iso, pvd + 158)[0]
    root_size = struct.unpack_from("<I", iso, pvd + 166)[0]
    results: List[Tuple[str, int, int, bool]] = []

    def walk(extent: int, size: int, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        start = extent * 2048
        end = min(start + size, len(iso))
        pos = start
        while pos < end:
            length = iso[pos]
            if length == 0:
                pos = ((pos // 2048) + 1) * 2048
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
            path = f"{prefix}{name}"
            results.append((path, loc, datalen, is_dir))
            if is_dir:
                walk(loc, datalen, path + "/", depth + 1)
            pos += length

    walk(root_extent, root_size, "", 0)
    return results


def iso_replace_file(
    iso_path: Path,
    filename: str,
    new_data: bytes,
    *,
    must_fit: bool = True,
) -> dict:
    """
    Replace a file inside an ISO 9660 image **in place**.

    New data is written over the existing extent. Shorter data is zero-padded;
    longer data raises ValueError when must_fit is True (directory size is
    not updated — keep the patched file the same size).
    """
    iso_path = Path(iso_path)
    iso = bytearray(iso_path.read_bytes())
    lba, size, dirent_off = iso_find_file(bytes(iso), filename)

    if len(new_data) > size and must_fit:
        raise ValueError(
            f"{filename} extent is {size} bytes but replacement is {len(new_data)} bytes. "
            "Keep the patched file the same size (pad if needed)."
        )

    payload = new_data[:size].ljust(size, b"\x00")
    start = lba * 2048
    end = start + size
    if end > len(iso):
        raise ValueError("File extent exceeds ISO size – corrupt image?")

    iso[start:end] = payload
    iso_path.write_bytes(iso)
    return {
        "file": filename,
        "lba": lba,
        "original_size": size,
        "written": len(payload),
        "path": str(iso_path),
        "dirent_offset": dirent_off,
    }


# ---------------------------------------------------------------------------
# GUI (only defined when tkinter is available)
# ---------------------------------------------------------------------------

if HAS_TK:

    
    class BinCueApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("BIN/CUE Viewer, Extractor & Replacer")
            self.geometry("920x620")
            self.minsize(800, 500)
    
            self.sheet: Optional[CueSheet] = None
            self.output_dir = Path.cwd()
    
            self._build_ui()
    
        def _build_ui(self):
            # ---- Top toolbar ----
            toolbar = ttk.Frame(self, padding=6)
            toolbar.pack(side=tk.TOP, fill=tk.X)
    
            ttk.Button(toolbar, text="Open CUE…", command=self.open_cue).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(toolbar, text="Set Output Folder…", command=self.choose_output).pack(side=tk.LEFT, padx=(0, 6))
    
            self.out_label = ttk.Label(toolbar, text=f"Output: {self.output_dir}", foreground="#555")
            self.out_label.pack(side=tk.LEFT, padx=8)
    
            # ---- Options ----
            opts = ttk.LabelFrame(self, text="Extraction options", padding=6)
            opts.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)
    
            self.audio_wav = tk.BooleanVar(value=True)
            self.data_iso = tk.BooleanVar(value=True)
    
            ttk.Checkbutton(opts, text="Audio → WAV (otherwise RAW)", variable=self.audio_wav).pack(side=tk.LEFT, padx=8)
            ttk.Checkbutton(opts, text="Data → ISO / user-data (otherwise raw sectors)", variable=self.data_iso).pack(side=tk.LEFT, padx=8)
    
            # ---- Track list ----
            list_frame = ttk.Frame(self, padding=6)
            list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
            columns = ("num", "type", "mode", "start", "length", "size", "file")
            self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
            self.tree.heading("num", text="#")
            self.tree.heading("type", text="Type")
            self.tree.heading("mode", text="Mode")
            self.tree.heading("start", text="Start")
            self.tree.heading("length", text="Length")
            self.tree.heading("size", text="Size")
            self.tree.heading("file", text="BIN file")
    
            self.tree.column("num", width=40, anchor=tk.CENTER)
            self.tree.column("type", width=70, anchor=tk.CENTER)
            self.tree.column("mode", width=110)
            self.tree.column("start", width=90, anchor=tk.CENTER)
            self.tree.column("length", width=90, anchor=tk.CENTER)
            self.tree.column("size", width=100, anchor=tk.E)
            self.tree.column("file", width=280)
    
            vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
    
            # ---- Bottom controls ----
            bottom = ttk.Frame(self, padding=6)
            bottom.pack(side=tk.BOTTOM, fill=tk.X)
    
            ttk.Button(bottom, text="Extract Selected", command=lambda: self.extract(selected_only=True)).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(bottom, text="Extract All", command=lambda: self.extract(selected_only=False)).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(bottom, text="Replace Selected…", command=self.replace_selected).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(bottom, text="Inject File into ISO…", command=self.inject_into_iso).pack(side=tk.LEFT, padx=(0, 12))
    
            self.progress = ttk.Progressbar(bottom, mode="determinate", length=220)
            self.progress.pack(side=tk.LEFT, padx=8)
    
            self.status = ttk.Label(bottom, text="Ready – open a .cue file")
            self.status.pack(side=tk.LEFT, padx=8)
    
            # ---- Log ----
            log_frame = ttk.LabelFrame(self, text="Log", padding=4)
            log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)
            self.log = tk.Text(log_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
            self.log.pack(fill=tk.X)
    
        def log_msg(self, msg: str):
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)
    
        def open_cue(self):
            path = filedialog.askopenfilename(
                title="Select CUE sheet",
                filetypes=[("CUE sheets", "*.cue"), ("All files", "*.*")],
            )
            if not path:
                return
            try:
                self.sheet = parse_cue(Path(path))
                self._populate_tree()
                self.status.configure(text=f"Loaded {self.sheet.cue_path.name} – {len(self.sheet.tracks)} track(s)")
                self.log_msg(f"Opened: {self.sheet.cue_path}")
                if self.sheet.title:
                    self.log_msg(f"Title: {self.sheet.title}")
                missing = [f for f in self.sheet.files if not f.is_file()]
                if missing:
                    self.log_msg("WARNING – missing BIN files:")
                    for m in missing:
                        self.log_msg(f"  {m}")
                    messagebox.showwarning("Missing BIN", "Some BIN files referenced by the CUE could not be found.")
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
            if not self.sheet:
                return
            for t in self.sheet.tracks:
                typ = "AUDIO" if t.is_audio else "DATA"
                size_bytes = t.length_sectors * (t.user_data_size if not t.is_audio else t.sector_size)
                size_str = f"{size_bytes / (1024*1024):.1f} MiB" if size_bytes else "—"
                fname = t.file_path.name if t.file_path else "?"
                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(t.number),
                    values=(
                        f"{t.number:02d}",
                        typ,
                        t.mode,
                        sectors_to_time(t.start_sector),
                        sectors_to_time(t.length_sectors),
                        size_str,
                        fname,
                    ),
                )
    


        def inject_into_iso(self):
            """Replace a named file inside an extracted ISO (same size required)."""
            iso_path = filedialog.askopenfilename(
                title="Select extracted ISO / data-track image",
                filetypes=[("ISO images", "*.iso *.img *.bin"), ("All files", "*.*")],
            )
            if not iso_path:
                return
            iso_path = Path(iso_path)
            try:
                files = iso_list_files(iso_path.read_bytes())
            except Exception as e:
                messagebox.showerror("Not an ISO", f"Could not read ISO 9660 structure:\n{e}")
                return

            file_entries = [(n, lba, sz) for n, lba, sz, is_dir in files if not is_dir]
            if not file_entries:
                messagebox.showinfo("Empty", "No files found in ISO.")
                return

            # Simple chooser dialog
            dlg = tk.Toplevel(self)
            dlg.title("Select file to replace")
            dlg.geometry("520x360")
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(dlg, text=f"ISO: {iso_path.name}").pack(anchor=tk.W, padx=8, pady=4)
            frame = ttk.Frame(dlg)
            frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
            cols = ("name", "lba", "size")
            tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
            tree.heading("name", text="File")
            tree.heading("lba", text="LBA")
            tree.heading("size", text="Size")
            tree.column("name", width=280)
            tree.column("lba", width=80, anchor=tk.E)
            tree.column("size", width=100, anchor=tk.E)
            vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            for n, lba, sz in file_entries:
                tree.insert("", tk.END, iid=n, values=(n, lba, f"{sz:,}"))

            # Prefer SLUS / EXE selection
            for n, _, _ in file_entries:
                if n.upper().startswith("SLUS") or n.upper().endswith(".28"):
                    tree.selection_set(n)
                    tree.see(n)
                    break

            def do_inject():
                sel = tree.selection()
                if not sel:
                    messagebox.showinfo("Select", "Select a file in the list.", parent=dlg)
                    return
                target_name = sel[0]
                repl = filedialog.askopenfilename(
                    title=f"Replacement for {target_name}",
                    parent=dlg,
                )
                if not repl:
                    return
                repl_path = Path(repl)
                try:
                    data = repl_path.read_bytes()
                    summary = iso_replace_file(iso_path, target_name, data, must_fit=True)
                    self.log_msg(
                        f"Injected {repl_path.name} → {target_name} "
                        f"(LBA {summary['lba']}, {summary['written']:,} bytes)"
                    )
                    messagebox.showinfo(
                        "Injected",
                        f"Replaced {target_name} in\n{iso_path}\n\n"
                        f"LBA {summary['lba']}  size {summary['written']:,} bytes\n\n"
                        "Now use Replace Selected to write this ISO back into the BIN.",
                        parent=dlg,
                    )
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Inject failed", str(e), parent=dlg)

            bf = ttk.Frame(dlg)
            bf.pack(fill=tk.X, padx=8, pady=8)
            ttk.Button(bf, text="Choose replacement…", command=do_inject).pack(side=tk.LEFT)
            ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)

        
        def replace_selected(self):
            """Replace one selected track inside its BIN with a chosen file."""
            if not self.sheet:
                messagebox.showinfo("No CUE", "Open a CUE file first.")
                return
            sel = self.tree.selection()
            if len(sel) != 1:
                messagebox.showinfo(
                    "Select one track",
                    "Select exactly one track to replace.",
                )
                return
            track = next(
                (t for t in self.sheet.tracks if str(t.number) == sel[0]), None
            )
            if track is None:
                return

            path = filedialog.askopenfilename(
                title=f"Replacement for track {track.number:02d}",
                filetypes=[
                    ("ISO / BIN / data", "*.iso *.bin *.img *.dat *"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return

            repl_path = Path(path)
            # Capacity hint
            if track.is_audio or not self.data_iso.get():
                capacity = track.length_sectors * track.sector_size
            else:
                capacity = track.length_sectors * track.user_data_size
            size = repl_path.stat().st_size
            msg = (
                f"Replace track {track.number:02d} ({track.mode}) in\n"
                f"  {track.file_path}\n\n"
                f"with\n  {repl_path.name} ({size:,} bytes)\n\n"
                f"Track capacity: {capacity:,} bytes\n"
            )
            if size > capacity:
                msg += "\nWARNING: replacement is LARGER and will be truncated."
            elif size < capacity:
                msg += "\nReplacement is smaller; remaining sectors will be zero-padded."
            msg += "\n\nThe BIN file will be modified in place. Continue?"
            if not messagebox.askyesno("Confirm replace", msg):
                return

            def worker():
                def prog(cur, tot):
                    pct = int(100 * cur / tot) if tot else 0
                    self.after(0, lambda: self.progress.configure(value=pct))

                try:
                    summary = replace_track(
                        track,
                        repl_path,
                        data_as_iso=(not track.is_audio) and self.data_iso.get(),
                        progress_cb=prog,
                    )
                    self.after(
                        0,
                        lambda: (
                            self.progress.configure(value=0),
                            self.status.configure(text="Replace done"),
                            self.log_msg(
                                f"Replaced track {track.number:02d} ← {repl_path.name} "
                                f"({summary.get('user_bytes', summary['bytes_written']):,} bytes)"
                            ),
                            messagebox.showinfo(
                                "Replaced",
                                f"Track {track.number:02d} updated in\n{track.file_path}",
                            ),
                        ),
                    )
                except Exception as e:
                    self.after(
                        0,
                        lambda: (
                            self.progress.configure(value=0),
                            self.status.configure(text="Replace failed"),
                            self.log_msg(f"ERROR replace track {track.number}: {e}"),
                            messagebox.showerror("Replace failed", str(e)),
                        ),
                    )

            self.status.configure(text=f"Replacing track {track.number:02d}…")
            threading.Thread(target=worker, daemon=True).start()


        def extract(self, selected_only: bool):
            if not self.sheet:
                messagebox.showinfo("No CUE", "Open a CUE file first.")
                return
    
            if selected_only:
                sel = self.tree.selection()
                if not sel:
                    messagebox.showinfo("Nothing selected", "Select one or more tracks in the list.")
                    return
                tracks = [t for t in self.sheet.tracks if str(t.number) in sel]
            else:
                tracks = list(self.sheet.tracks)
    
            # Run extraction in a background thread so the UI stays responsive
            def worker():
                total = len(tracks)
                for i, t in enumerate(tracks):
                    self.after(0, lambda i=i, t=t: self.status.configure(
                        text=f"Extracting track {t.number:02d} ({i+1}/{total})…"
                    ))
                    ext = ".wav" if (t.is_audio and self.audio_wav.get()) else \
                          ".iso" if (not t.is_audio and self.data_iso.get()) else \
                          ".bin"
                    out_name = f"track{t.number:02d}{ext}"
                    out_path = self.output_dir / out_name
    
                    def prog(cur, tot, track=t):
                        pct = int(100 * cur / tot) if tot else 0
                        self.after(0, lambda: self.progress.configure(value=pct))
    
                    try:
                        extract_track(
                            t,
                            out_path,
                            audio_as_wav=self.audio_wav.get(),
                            data_as_iso=self.data_iso.get(),
                            progress_cb=prog,
                        )
                        self.after(0, lambda p=out_path: self.log_msg(f"Wrote {p.name}"))
                    except Exception as e:
                        self.after(0, lambda e=e, t=t: self.log_msg(f"ERROR track {t.number}: {e}"))
    
                self.after(0, lambda: (
                    self.progress.configure(value=0),
                    self.status.configure(text="Done"),
                    messagebox.showinfo("Finished", f"Extracted {total} track(s) to\n{self.output_dir}"),
                ))
    
            threading.Thread(target=worker, daemon=True).start()
    
    
    # Entry point

def main():
    # Allow running headless for quick tests / import
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("\nUsage:  python3 bincue_gui.py          # launch GUI")
        print("        from bincue_gui import parse_cue, extract_track, replace_track")
        return

    if not HAS_TK:
        print("ERROR: tkinter is not available.")
        print("On Debian/Ubuntu/Mint install it with:")
        print("    sudo apt install python3-tk")
        print("Then re-run this script.")
        sys.exit(1)

    app = BinCueApp()
    app.mainloop()


if __name__ == "__main__":
    main()
