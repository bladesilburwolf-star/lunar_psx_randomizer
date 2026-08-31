#!/usr/bin/env python3
"""
gba_dump_region.py – dump raw u16 fields from any ROM region to CSV

Standalone inspector for examining candidate enemy tables (or any data
region) without the scanner's scoring heuristics. Just reads N records
at a given offset/stride and writes every u16 field to CSV.

Usage:
  python3 gba_dump_region.py lunar.gba --offset 0x315b80 --stride 0x20 --count 10
  python3 gba_dump_region.py lunar.gba --offset 0x562598 --stride 0x14 --count 10
  python3 gba_dump_region.py lunar.gba --offset 0x315b80 --stride 0x20 --count 10 --out my_dump.csv
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Dump a ROM region as u16 fields to CSV")
    ap.add_argument("rom", help="Path to lunar.gba ROM")
    ap.add_argument("--offset", required=True, help="Hex offset to start reading (e.g. 0x315b80)")
    ap.add_argument("--stride", required=True, help="Record stride in bytes (e.g. 0x20)")
    ap.add_argument("--count", type=int, default=10, help="Number of records to dump (default 10)")
    ap.add_argument("--out", default=None, help="Output CSV path (auto-named if omitted)")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()

    offset = int(args.offset, 0)
    stride = int(args.stride, 0)
    count = args.count
    nw = stride // 2  # number of u16 fields per record

    if nw < 1:
        print("ERROR: stride must be at least 2 bytes")
        return 1

    if offset + count * stride > len(rom):
        print("WARNING: dump extends past ROM end, truncating")
        count = (len(rom) - offset) // stride

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("dump_" + format(offset, 'x') + "_s" + format(stride, 'x') + ".csv")

    with open(str(out_path), "w", newline="") as f:
        w = csv.writer(f)
        header = ["index", "offset"] + ["u" + str(i) for i in range(nw)]
        w.writerow(header)
        for i in range(count):
            off = offset + i * stride
            if off + stride > len(rom):
                break
            vals = []
            for j in range(nw):
                v = struct.unpack_from("<H", rom, off + j * 2)[0]
                vals.append(v)
            w.writerow([i, hex(off)] + vals)

    print("Dumped " + str(count) + " records (stride " + hex(stride) + ") from " + hex(offset))
    print("Wrote " + str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
