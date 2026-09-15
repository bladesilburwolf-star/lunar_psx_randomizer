#!/usr/bin/env python3
"""
extract_item_table.py – Pull the real Lunar SSSC item table from the PSX EXE

CONFIRMED (not guessed) by direct binary analysis of SLUS_006.28, same method
used for the enemy table: decompress the gearbolt-compressed exe payload and
scan for known reference values (real shop prices pulled from period FAQs),
then verify a consistent record stride around the hits.

Findings:
  - Table sits IMMEDIATELY after the enemy stat table (which patch_exe.py
    already confirmed at 0x97F68, size 0x1300). Item table starts at 0x99244
    in the same decompressed buffer.
  - 72 records * 18 bytes (0x12) = 1296 bytes (0x510) total.
  - Record layout (bytes, offsets relative to record start):
      0x00  u16 LE  buy_price
      0x02  u16 LE  sell_price   (== buy_price // 2 for every single record
                                   in the shipped game -- 100% consistent,
                                   the standard JRPG buy/sell convention)
      0x04  u8      group/category flag (0x00 or 0x01 observed; probably
                                   consumable vs equipment, or disc-relevant)
      0x05-0x08     4 bytes, almost always 00 99 00 00; a different pattern
                    (00 91 00 57 ..) appears on a handful of records --
                    likely a pointer/category id for "special" items.
      0x09-0x0A     u16, roughly-sequential small index (item id / sort key)
      0x0B-0x11     7 bytes, NOT YET DECODED -- almost certainly holds the
                    equip stat bonuses (ATK/DEF/etc.), usable-by-character
                    bitmask, and item-type byte. Cross-referencing the GBA
                    "Lunar Legend" port's (better-documented) item data
                    against these bytes is the logical next step to fully
                    decode them, since name/effect text lines up 1:1 with
                    prices in a lot of cases.

  A few records (idx 0,1,18,36,44,57 in the raw dump) have buy=sell=0 --
  these look like padding/separators between item categories (weapons /
  armor / consumables / key items) rather than real purchasable items. This
  script keeps them in the extracted table so record indices line up with
  the game's own indexing, but the randomizer treats them as protected
  (never touches value 0 entries) so we never accidentally invent a price
  for a non-item slot.

Usage:
  python3 extract_item_table.py SLUS_006.28
  python3 extract_item_table.py SLUS_006.28 -o item_master.bin
"""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from item_ids import name_for
except ImportError:
    def name_for(i: int) -> str:  # fallback if run from elsewhere
        return f"Item_{i}"

RECORD_SIZE = 0x12          # 18
NUM_RECORDS = 72
TABLE_SIZE = RECORD_SIZE * NUM_RECORDS   # 0x510 / 1296

# Confirmed offset into the FULLY decompressed exe payload (same convention
# patch_exe.py uses for the enemy table -- i.e. the output of the external
# gearbolt_decmp tool run on exe[0x1000:], NOT the offset the internal
# Python reimplementation in extract_enemy_table.py produces, which is
# 0x800 bytes lower due to header handling differences).
TABLE_OFF = 0x99244

PAYLOAD_OFF = 0x1000


def find_tool(name: str) -> str:
    for p in [
        shutil.which(name),
        f"/tmp/{name}",
        str(Path(__file__).resolve().parent / name),
    ]:
        if p and Path(p).is_file():
            return p
    raise FileNotFoundError(
        f"Need '{name}' binary. It should already be sitting next to this "
        f"script (copied from enemy_randomizer/), or place it in /tmp/{name}"
    )


def decompress_exe(exe_path: Path) -> bytes:
    exe = exe_path.read_bytes()
    if exe[:8] != b"PS-X EXE":
        raise ValueError("Not a PS-X EXE")

    tool = find_tool("gearbolt_decmp")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        slice_path = td / "slice.bin"
        decomp_path = td / "decomp.bin"
        slice_path.write_bytes(exe[PAYLOAD_OFF:])
        r = subprocess.run([tool, str(slice_path), str(decomp_path)],
                            capture_output=True, text=True)
        if r.returncode != 0 or not decomp_path.is_file():
            raise RuntimeError(f"decompress failed: {r.stderr or r.stdout}")
        decomp = decomp_path.read_bytes()

    if len(decomp) > 690176:
        decomp = decomp[:690176]
    return decomp


def read_record(data: bytes, off: int) -> dict:
    buy, sell = struct.unpack_from("<HH", data, off)
    group = data[off + 4]
    marker = data[off + 5:off + 9]
    idx_field = struct.unpack_from("<H", data, off + 9)[0]
    unknown = data[off + 11:off + RECORD_SIZE]
    return {
        "buy": buy, "sell": sell, "group": group,
        "marker": marker.hex(), "idx_field": idx_field,
        "unknown": unknown.hex(),
    }


def verify_table(data: bytes, off: int) -> int:
    """Sanity check: how many records have sell == buy//2 (or both zero)?"""
    good = 0
    for i in range(NUM_RECORDS):
        r = read_record(data, off + i * RECORD_SIZE)
        if r["buy"] == 0 and r["sell"] == 0:
            good += 1
        elif 0 < r["buy"] <= 30000 and r["sell"] == r["buy"] // 2:
            good += 1
    return good


def extract(exe_path: Path) -> tuple[bytes, list[dict]]:
    decomp = decompress_exe(exe_path)
    score = verify_table(decomp, TABLE_OFF)
    print(f"Table verification: {score}/{NUM_RECORDS} records match the "
          f"buy/sell=buy//2 pattern (expect {NUM_RECORDS}/{NUM_RECORDS})")
    if score < NUM_RECORDS - 2:
        print("  WARNING: table offset may be wrong for this exe build!")

    table = decomp[TABLE_OFF: TABLE_OFF + TABLE_SIZE]
    records = [read_record(table, i * RECORD_SIZE) for i in range(NUM_RECORDS)]
    return table, records


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract Lunar SSSC item table from EXE")
    ap.add_argument("exe", type=Path, help="SLUS_006.28 (US Complete)")
    ap.add_argument("-o", "--output", type=Path, default=Path("item_master.bin"))
    ap.add_argument("--csv", type=Path, default=None)
    args = ap.parse_args()

    if not args.exe.is_file():
        print(f"ERROR: {args.exe} not found", file=sys.stderr)
        return 1

    table, records = extract(args.exe)
    args.output.write_bytes(table)
    print(f"Wrote {args.output}  ({len(table)} bytes, {NUM_RECORDS} records)")

    csv_path = args.csv or args.output.with_suffix(".csv")
    with open(csv_path, "w") as f:
        f.write("index,name,buy,sell,group,marker,idx_field,unknown_bytes\n")
        for i, r in enumerate(records):
            f.write(f"{i},{name_for(i)},{r['buy']},{r['sell']},{r['group']},"
                     f"{r['marker']},{r['idx_field']},{r['unknown']}\n")
    print(f"Wrote {csv_path}")
    print("\nNext:  python3 item_randomizer.py --cli -i item_master.bin --seed 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
