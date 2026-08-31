#!/usr/bin/env python3
"""
patch_exe.py – Inject a randomized enemy table into SLUS_006.28

Pipeline:
  1. Slice gearbolt payload at EXE+0x1000
  2. Decompress (external gearbolt_decmp or bundled logic)
  3. Overwrite 128×38-byte table at decompressed+0x97F68
  4. Recompress
  5. Rebuild SLUS = header[0:0x1000] + padded payload

Requires:
  - gearbolt_decmp / gearbolt_cmp on PATH, or at /tmp/gearbolt_*
  - Or will try to build them from wdtools if present

Usage:
  python3 patch_exe.py SLUS_006.28 enemy_master_randomized.bin -o SLUS_006.28.patched
  python3 patch_exe.py /path/to/SLUS_006.28 enemy_master_randomized.bin
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import struct
import sys
import tempfile
from pathlib import Path

PAYLOAD_OFF = 0x1000
TABLE_OFF = 0x97F68
TABLE_SIZE = 0x1300  # 128 * 0x26


def find_tool(name: str) -> str:
    for p in [
        shutil.which(name),
        f"/tmp/{name}",
        str(Path(__file__).resolve().parent / name),
    ]:
        if p and Path(p).is_file():
            return p
    raise FileNotFoundError(
        f"Need '{name}' binary. Build from wdtools gearbolt_decmp/cmp "
        f"or place it in /tmp/{name}"
    )


def decompress(tool: str, src: Path, dst: Path) -> None:
    r = subprocess.run([tool, str(src), str(dst)], capture_output=True, text=True)
    if r.returncode != 0 or not dst.is_file() or dst.stat().st_size < 1000:
        raise RuntimeError(f"decompress failed: {r.stderr or r.stdout}")


def compress(tool: str, src: Path, dst: Path) -> None:
    r = subprocess.run([tool, str(src), str(dst)], capture_output=True, text=True)
    print(r.stderr.strip() or r.stdout.strip())
    if r.returncode != 0 or not dst.is_file() or dst.stat().st_size < 1000:
        raise RuntimeError(f"compress failed: {r.stderr or r.stdout}")


def patch(exe_path: Path, table_path: Path, out_path: Path) -> None:
    table = table_path.read_bytes()
    if len(table) != TABLE_SIZE:
        raise ValueError(f"table must be {TABLE_SIZE} bytes, got {len(table)}")

    exe = exe_path.read_bytes()
    if exe[:8] != b"PS-X EXE":
        raise ValueError("Not a PS-X EXE")

    decmp_tool = find_tool("gearbolt_decmp")
    cmp_tool = find_tool("gearbolt_cmp")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        slice_path = td / "slice.bin"
        decomp_path = td / "decomp.bin"
        patched_path = td / "patched.bin"
        payload_path = td / "payload.bin"

        slice_path.write_bytes(exe[PAYLOAD_OFF:])
        print(f"Decompressing payload ({slice_path.stat().st_size} bytes)…")
        decompress(decmp_tool, slice_path, decomp_path)
        decomp = bytearray(decomp_path.read_bytes())
        # Trim trailing garbage from prior recompress if any
        if len(decomp) > 690176:
            decomp = decomp[:690176]
        print(f"  decompressed {len(decomp)} bytes")

        if TABLE_OFF + TABLE_SIZE > len(decomp):
            raise RuntimeError("decompress too small for enemy table")

        # Show before/after for enemy #1 (Albino slot)
        def show(label, blob, idx=1):
            o = TABLE_OFF + idx * 0x26
            hp, atk, df = struct.unpack_from("<3H", blob, o + 2)
            exp, sil = struct.unpack_from("<2H", blob, o + 0x1A)
            print(f"  {label} enemy#{idx}: HP={hp} ATK={atk} DEF={df} EXP={exp} SIL={sil}")

        show("before", decomp)
        decomp[TABLE_OFF : TABLE_OFF + TABLE_SIZE] = table
        show("after ", decomp)

        patched_path.write_bytes(decomp)
        print("Recompressing…")
        compress(cmp_tool, patched_path, payload_path)
        payload = payload_path.read_bytes()

        orig_payload_len = len(exe) - PAYLOAD_OFF
        if len(payload) < orig_payload_len:
            payload = payload + b"\x00" * (orig_payload_len - len(payload))
        elif len(payload) > orig_payload_len:
            print(f"  note: payload {len(payload)} > original {orig_payload_len} (EXE grows)")

        out = exe[:PAYLOAD_OFF] + payload
        out_path.write_bytes(out)
        print(f"Wrote {out_path} ({len(out)} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch enemy table into SLUS_006.28")
    ap.add_argument("exe", type=Path, help="Original SLUS_006.28")
    ap.add_argument("table", type=Path, help="Randomized table (4864 bytes)")
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()
    out = args.output or Path("SLUS_006.28.patched")
    try:
        patch(args.exe, args.table, out)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
