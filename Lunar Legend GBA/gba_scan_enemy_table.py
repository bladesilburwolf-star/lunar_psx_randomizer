#!/usr/bin/env python3
"""
gba_scan_enemy_table.py – locate the Lunar Legend (GBA) enemy master table

Claude found the item table at 0x7FA424 (12-byte records, price+stat combined).
The enemy master table has NOT been located yet. This scanner uses clues from
cheat-code RAM structure analysis + Claude's pointer-table findings to find it.

What we know (from cheat codes):
  - Permanent character stat block (RAM 0x02004AC2, stride 0x80):
      +0x00 HP u16, +0x02 MP u16, +0x04..+0x0C five core stats u16 each,
      +0x10 MaxHP u16, +0x12 MaxMP u16, +0x38 EXP (u8)
    The 5 stats are: Atc, Def, Agl, Men, Res (from encrypted Max-Stat codes).
  - In-battle combatant block (RAM 0x02037094, stride 0x190 / 400 bytes):
      +0x00 HP u16, +0x04 MP u16, +0x1C SM (special meter) u8
  - Enemies in battle use the same combatant layout but their *base* stats
    come from a ROM master table loaded into RAM at battle start.

Strategy:
  1. Scan the high ROM region near the item table (0x7F8000–0x7FC000) for tables
     of u16 values in plausible stat ranges (HP 1–9999, ATK/DEF 1–999).
  2. Look for the GBA "enemy stat signature": records where HP, ATK, DEF,
     AGI, MEN, RES, EXP, SILVER appear as ascending-but-varied u16 fields.
  3. Cross-check candidate tables against Claude's pointer table at 0x7FB29C.
  4. Dump all candidates to CSV for manual inspection.

Usage:
  python3 gba_scan_enemy_table.py lunar.gba
  python3 gba_scan_enemy_table.py lunar.gba --region 0x7F0000 0x7FC000 --stride 0x10
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ITEM_TABLE_OFFSET = 0x7FA424
RECORD_SIZE_ITEM = 0x0C
GBA_ROM_SIZE = 8 * 1024 * 1024

STAT_RANGES = {
    "hp": (1, 9999),
    "mp": (0, 999),
    "atk": (1, 999),
    "def": (1, 999),
    "agi": (1, 999),
    "men": (1, 999),
    "res": (1, 999),
    "exp": (1, 99999),
    "silver": (0, 99999),
    "level": (1, 99),
}


def read_u16(rom: bytes, off: int) -> int:
    if off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi


def score_record_as_enemy(rom: bytes, off: int, stride: int) -> Tuple[int, dict]:
    score = 0
    fields: dict = {}
    names = ["hp", "mp", "atk", "def", "agi", "men", "res", "f7", "f8", "exp", "silver"]
    for i, name in enumerate(names):
        v = read_u16(rom, off + i * 2)
        if v < 0:
            break
        fields[name] = v
        lo, hi = STAT_RANGES.get(name, (0, 0xFFFF))
        if _in_range(v, lo, hi):
            score += 1
        elif v == 0 and name in ("mp", "silver"):
            score += 0
        else:
            score -= 1
    if fields.get("hp", 0) >= 10:
        score += 1
    vals = [fields.get(n, -1) for n in ("hp", "mp", "atk")]
    if len(set(vals)) == 1:
        score -= 3
    return score, fields


def dump_run(rom: bytes, start: int, stride: int, count: int) -> List[str]:
    rows: List[str] = []
    for i in range(count):
        off = start + i * stride
        u16s = [read_u16(rom, off + j * 2) for j in range(stride // 2)]
        rows.append(f"  +{i}: " + " ".join(f"{v:5d}" for v in u16s))
    return rows


def scan_region(rom: bytes, start: int, end: int, strides: List[int],
                min_score: int = 4) -> List[dict]:
    hits: List[dict] = []
    for stride in strides:
        off = start
        run_start = -1
        run_len = 0
        while off + stride <= min(end, len(rom)):
            s, fields = score_record_as_enemy(rom, off, stride)
            if s >= min_score:
                if run_start < 0:
                    run_start = off
                run_len += 1
            else:
                if run_start >= 0 and run_len >= 4:
                    hits.append({
                        "stride": stride,
                        "start": run_start,
                        "length": run_len,
                        "end": run_start + run_len * stride,
                        "sample": dump_run(rom, run_start, stride, min(run_len, 4)),
                    })
                run_start = -1
                run_len = 0
            off += stride
        if run_start >= 0 and run_len >= 4:
            hits.append({
                "stride": stride,
                "start": run_start,
                "length": run_len,
                "end": run_start + run_len * stride,
                "sample": dump_run(rom, run_start, stride, min(run_len, 4)),
            })
    hits.sort(key=lambda h: h["length"], reverse=True)
    seen: set = set()
    uniq: List[dict] = []
    for h in hits:
        key = (h["start"] >> 8)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)
    return uniq[:20]


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan Lunar Legend GBA ROM for enemy stat table")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--region", nargs=2, metavar=("START", "END"), default=None,
                    help="Hex region to scan, e.g. 0x7F0000 0x7FC000")
    ap.add_argument("--strides", nargs="+", default=None,
                    help="Hex record strides to try, e.g. 0x10 0x14 0x18 0x1C 0x20")
    ap.add_argument("--min-score", type=int, default=4,
                    help="Minimum plausibility score per record")
    ap.add_argument("--out", default="gba_enemy_candidates.csv",
                    help="Output CSV path")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print(f"WARNING: ROM is only {len(rom)} bytes — expected 8 MiB")

    if args.region:
        start = int(args.region[0], 16)
        end = int(args.region[1], 16)
    else:
        start = 0x7F8000
        end = 0x7FC000

    strides_hex = args.strides or ["0x10", "0x14", "0x18", "0x1C", "0x20", "0x24", "0x28", "0x2C", "0x30"]
    strides = [int(s, 16) for s in strides_hex]

    print(f"Scanning {hex(start)}..{hex(end)} with strides {[hex(s) for s in strides]}")
    hits = scan_region(rom, start, end, strides, args.min_score)

    if not hits:
        print("No candidate enemy tables found in this region.")
        print("Try widening the region or lowering --min-score.")
        return 0

    print(f"\nFound {len(hits)} candidate table(s):\n")
    for i, h in enumerate(hits):
        print(f"[{i}] stride={hex(h['stride'])}  start={hex(h['start'])}  "
              f"records={h['length']}  end={hex(h['end'])}")
        for row in h["sample"][:2]:
            print(row)
        print()

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate", "stride", "start", "length", "end"])
        for i, h in enumerate(hits):
            w.writerow([i, hex(h["stride"]), hex(h["start"]), h["length"], hex(h["end"])])
    print(f"Wrote candidate summary -> {args.out}")

    top = hits[0]
    detail = Path(args.out).with_name("gba_enemies_top_candidate.csv")
    with open(detail, "w", newline="") as f:
        w = csv.writer(f)
        stride = top["stride"]
        nw = stride // 2
        w.writerow(["index", "offset"] + [f"u16_{i}" for i in range(nw)])
        for i in range(top["length"]):
            off = top["start"] + i * stride
            vals = [read_u16(rom, off + j * 2) for j in range(nw)]
            w.writerow([i, hex(off)] + vals)
    print(f"Wrote top-candidate detail -> {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
