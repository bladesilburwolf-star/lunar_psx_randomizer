#!/usr/bin/env python3
"""
gba_dump_candidates.py - dump the most promising enemy table candidate regions

Dumps several regions identified by v2 blind scan + Deathcap anchor analysis
at multiple strides, so the exact enemy table layout can be identified.

The v2 scan and Deathcap anchor hits both point to the 0x559000-0x6A0000 region.
This tool dumps the top candidate sub-regions at strides 0x10-0x30 so we can
manually inspect which stride produces clean enemy-stat-like records.

Usage:
  python gba_dump_candidates.py lunar.gba
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

# Top candidate regions from v2 scan (by record count) + Deathcap cluster analysis
CANDIDATES = [
    # (name, start, end)
    ("v2_rank3_559930",  0x559930, 0x559a50),
    ("v2_rank4_55be90",  0x55be90, 0x55bff0),
    ("v2_rank5_5625a0",  0x5625a0, 0x5627e0),
    ("v2_rank6_563350",  0x563350, 0x563430),
    ("v2_rank7_56a060",  0x56a060, 0x56a230),
    ("v2_rank8_56e790",  0x56e790, 0x56e7f0),
    ("v2_rank9_579e50",  0x579e50, 0x57a0e0),   # largest: 41 records
    ("v2_rank10_5800a0", 0x5800a0, 0x5801d0),
    ("v2_rank20_5910a8", 0x5910a8, 0x591210),
    ("deathcap_597a2",   0x597000, 0x599000),   # dense Deathcap matched=3
    ("deathcap_5a646",   0x5a600, 0x5a700),     # massive matched=3 block
    ("deathcap_5f38a",   0x5f380, 0x5f400),
    ("deathcap_6945a",   0x69450, 0x69480),
]

STRIDES = [0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def main():
    ap = argparse.ArgumentParser(
        description="Dump Lunar Legend GBA enemy table candidate regions")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()

    print("Dumping " + str(len(CANDIDATES)) + " candidate regions at " +
          str(len(STRIDES)) + " strides each")
    print()

    for cname, start, end in CANDIDATES:
        # Pad each region by 64 bytes on each side for context
        ds = max(0, start - 64)
        de = min(len(rom), end + 64)
        for stride in STRIDES:
            nw = stride // 2
            nrecs = (de - ds) // stride
            if nrecs < 2:
                continue
            fname = "dump_" + cname + "_s" + format(stride, "x") + ".csv"
            with open(fname, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "offset"] + ["u" + str(i) for i in range(nw)])
                for i in range(nrecs):
                    off = ds + i * stride
                    if off + stride > len(rom):
                        break
                    vals = [read_u16(rom, off + j * 2) for j in range(nw)]
                    w.writerow([i, hex(off)] + vals)
            print("  " + fname + " (" + str(nrecs) + " records)")

    print()
    print("Done. Look for regions where u16 values look like:")
    print("  - HP values (small numbers 15-200 for normal enemies, 1000-9999 for bosses)")
    print("  - EXP values (small, 1-500)")
    print("  - Silver values (small, 1-200)")
    print("  - Repeated structure (same field positions across records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
