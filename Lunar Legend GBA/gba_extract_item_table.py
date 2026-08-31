#!/usr/bin/env python3
"""
gba_extract_item_table.py – extract & dump the Lunar Legend (GBA) item table

Reads the combined price + stat table from a USA ALNE ROM at 0x7FA424
(12-byte records, little-endian) and writes:
  - a .bin blob (raw table bytes, for use with the randomizer's load path or
    cross-platform comparison with the PSX item_master.bin)
  - a human-readable CSV with decoded fields

This mirrors the PSX item_randomizer/extract_item_table.py workflow.

Usage:
  python3 gba_extract_item_table.py lunar.gba
  python3 gba_extract_item_table.py lunar.gba --out-dir dumps --count 200
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path
from typing import List, Optional

ITEM_TABLE_OFFSET = 0x7FA424
RECORD_SIZE = 0x0C  # 12 bytes
DEFAULT_NUM_RECORDS = 200


def _detect_table_extent(rom: bytes, start: int, max_records: int) -> int:
    zero_run = 0
    for i in range(max_records):
        off = start + i * RECORD_SIZE
        if off + RECORD_SIZE > len(rom):
            return i
        buy, sell = struct.unpack_from("<HH", rom, off)
        stat = struct.unpack_from("<H", rom, off + 0x06)[0]
        if buy == 0 and sell == 0 and stat == 0:
            zero_run += 1
            if zero_run >= 4:
                return max(1, i - zero_run + 1)
        else:
            zero_run = 0
    return max_records


def extract(rom: bytes, count: Optional[int] = None):
    if count is None:
        count = _detect_table_extent(rom, ITEM_TABLE_OFFSET, DEFAULT_NUM_RECORDS)
    rows = []
    for i in range(count):
        off = ITEM_TABLE_OFFSET + i * RECORD_SIZE
        if off + RECORD_SIZE > len(rom):
            break
        rec = rom[off:off + RECORD_SIZE]
        buy, sell = struct.unpack_from("<HH", rec, 0x00)
        rare = rec[0x04]
        element = rec[0x05]
        stat = struct.unpack_from("<H", rec, 0x06)[0]
        flag8 = rec[0x08]
        zero9 = rec[0x09]
        subtype = rec[0x0A]
        category = rec[0x0B]
        rows.append({
            "index": i,
            "offset": hex(off),
            "buy": buy,
            "sell": sell,
            "b4_rare": rare,
            "b5_element": element,
            "stat_u16": stat,
            "b8": flag8,
            "b9": zero9,
            "b10_subtype": subtype,
            "flags_b11": hex(category),
            "sell_ok": str(buy > 0 and sell == buy // 2),
            "raw": rec.hex(),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract Lunar Legend GBA item table")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--out-dir", default=".", help="Directory for output files")
    ap.add_argument("--count", type=int, default=None,
                    help="Number of records (auto-detect if omitted)")
    ap.add_argument("--name", default="gba_item_master",
                    help="Base name for output files")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < 8 * 1024 * 1024:
        print(f"WARNING: ROM is only {len(rom)} bytes — expected 8 MiB")

    rows = extract(rom, args.count)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bin_path = out_dir / f"{args.name}.bin"
    blob = b"".join(bytes.fromhex(r["raw"]) for r in rows)
    bin_path.write_bytes(blob)
    print(f"Wrote {len(rows)} records ({len(blob)} bytes) -> {bin_path}")

    csv_path = out_dir / f"{args.name}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote CSV -> {csv_path}")

    priced = sum(1 for r in rows if r["buy"] > 0)
    print(f"  priced records: {priced} / {len(rows)}")
    print(f"  table region: {rows[0]['offset']} .. {rows[-1]['offset']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
