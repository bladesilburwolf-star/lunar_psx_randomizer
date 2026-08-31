#!/usr/bin/env python3
"""
gba_scan_enemy_table_v2.py – improved enemy table locator for Lunar Legend GBA

The first scanner (gba_scan_enemy_table.py) found a candidate at 0x7fa8c0 that
turned out to be an item-adjacent table (shop inventory / drops) with buy/sell
pairs — NOT enemy stats. ALL 9 original candidates were in or adjacent to the
item table region (0x7FA000-0x7FB000); none were the real enemy stat table.

This v2 scanner fixes that with three improvements:
  1. ANTI buy/sell filter: if u16[i] == u16[i+1] * 2 (or vice versa), penalize
     the score — enemy stat tables do NOT contain sell=buy//2 pairs.
  2. Enemy-specific signature: HP should be in 5–9999 (enemies have real HP),
     and packed item-flag bytes (high byte in {0x01,0x0A,0x10,0x18,0x20,0x21,
     0x40,0xA1,0xFF}) are penalized — those belong to item tables, not enemies.
  3. Full-ROM scan: search the entire 8 MiB ROM, skipping the known item-data
     region (0x7FA000-0x7FB000). The enemy table is NOT near the item table.

Usage:
  python3 gba_scan_enemy_table_v2.py lunar.gba
  python3 gba_scan_enemy_table_v2.py lunar.gba --min-score 5 --strides 0x10 0x18 0x20 0x28
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path
from typing import List, Optional, Tuple

GBA_ROM_SIZE = 8 * 1024 * 1024
ITEM_TABLE_OFFSET = 0x7FA424
ITEM_REGION_START = 0x7FA000
ITEM_REGION_END = 0x7FB000


def read_u16(rom: bytes, off: int) -> int:
    if off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def is_buy_sell_pair(a: int, b: int) -> bool:
    """True if (a,b) looks like a buy/sell pair (one is roughly half the other)."""
    if a <= 0 or b <= 0:
        return False
    if a == b * 2 or b == a * 2:
        return True
    if a == (b * 2 + 1) or b == (a * 2 + 1):
        return True
    return False


ITEM_FLAG_BYTES = {0x01, 0x0A, 0x10, 0x18, 0x20, 0x21, 0x40, 0xA1, 0xFF}


def score_enemy_record(rom: bytes, off: int, stride: int) -> Tuple[int, dict, list]:
    """Score a candidate enemy record. Higher = more likely to be enemy stats."""
    score = 0
    fields = {}
    flags = []
    nw = stride // 2
    vals = [read_u16(rom, off + i * 2) for i in range(nw)]

    for i, v in enumerate(vals):
        fields[f"u16_{i}"] = v

    # --- Positive signals ---
    hp = vals[0]
    if 5 <= hp <= 9999:
        score += 2
        flags.append("hp_ok")
    elif hp == 0:
        score -= 1

    stat_count = 0
    for v in vals[1:6]:
        if 1 <= v <= 999:
            stat_count += 1
            score += 1
    if stat_count >= 3:
        score += 1
        flags.append(f"stats={stat_count}")

    for v in vals[6:]:
        if 1 <= v <= 65535 and v > 10:
            score += 1
            flags.append("exp_candidate")
            break

    # --- NEGATIVE signals (anti-false-positive) ---
    pair_count = 0
    for i in range(nw - 1):
        if is_buy_sell_pair(vals[i], vals[i + 1]):
            pair_count += 1
    if pair_count >= 1:
        score -= 3
        flags.append(f"buy_sell_pairs={pair_count}")

    if len(set(vals)) == 1 and vals[0] != 0:
        score -= 2

    packed_count = 0
    for v in vals:
        hi = (v >> 8) & 0xFF
        lo = v & 0xFF
        if hi in ITEM_FLAG_BYTES and lo < 0x80 and hi != 0:
            packed_count += 1
    if packed_count >= 3:
        score -= 2
        flags.append(f"packed_item_ids={packed_count}")

    if 1 <= hp <= 4:
        score -= 1

    return score, fields, flags


def _make_hit(rom: bytes, stride: int, start: int, length: int) -> dict:
    total = 0
    sample = []
    for i in range(min(length, 8)):
        off = start + i * stride
        s, fields, flags = score_enemy_record(rom, off, stride)
        total += s
        nw = stride // 2
        u16s = [read_u16(rom, off + j * 2) for j in range(nw)]
        sample.append({
            "idx": i,
            "offset": hex(off),
            "values": u16s,
            "flags": flags,
        })
    return {
        "stride": stride,
        "start": start,
        "length": length,
        "end": start + length * stride,
        "score_per_record": round(total / min(length, 8), 1),
        "sample": sample,
    }


def scan_full_rom(rom: bytes, strides: List[int], min_score: int,
                  min_run: int = 5) -> List[dict]:
    hits = []
    for stride in strides:
        off = 0
        run_start = -1
        run_len = 0
        while off + stride <= len(rom):
            if ITEM_REGION_START <= off < ITEM_REGION_END:
                off = ITEM_REGION_END
                if run_start >= 0 and run_len >= min_run:
                    hits.append(_make_hit(rom, stride, run_start, run_len))
                run_start = -1
                run_len = 0
                continue

            s, fields, flags = score_enemy_record(rom, off, stride)
            if s >= min_score:
                if run_start < 0:
                    run_start = off
                run_len += 1
            else:
                if run_start >= 0 and run_len >= min_run:
                    hits.append(_make_hit(rom, stride, run_start, run_len))
                run_start = -1
                run_len = 0
            off += stride

        if run_start >= 0 and run_len >= min_run:
            hits.append(_make_hit(rom, stride, run_start, run_len))

    hits.sort(key=lambda h: h["score_per_record"], reverse=True)
    return hits[:30]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scan full Lunar Legend GBA ROM for enemy stat table (v2)")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--strides", nargs="+", default=None,
                    help="Hex strides, e.g. 0x10 0x18 0x20 0x28 0x30")
    ap.add_argument("--min-score", type=int, default=5,
                    help="Minimum score per record to count as a hit")
    ap.add_argument("--min-run", type=int, default=5,
                    help="Minimum consecutive hits to count as a table")
    ap.add_argument("--out", default="gba_enemy_candidates_v2.csv",
                    help="Output CSV path")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print(f"WARNING: ROM is only {len(rom)} bytes")

    strides_hex = args.strides or [
        "0x10", "0x14", "0x18", "0x1C", "0x20", "0x24", "0x28", "0x2C", "0x30",
        "0x34", "0x38",
    ]
    strides = [int(s, 16) for s in strides_hex]

    print(f"Full-ROM scan (skipping item region 0x7FA000-0x7FB000)")
    print(f"Strides: {[hex(s) for s in strides]}  min_score={args.min_score}  min_run={args.min_run}")
    hits = scan_full_rom(rom, strides, args.min_score, args.min_run)

    if not hits:
        print("\nNo candidate enemy tables found.")
        print("Try lowering --min-score or --min-run, or adding more strides.")
        return 0

    print(f"\nFound {len(hits)} candidate(s), ranked by score:\n")
    for i, h in enumerate(hits):
        print(f"[{i}] stride={hex(h['stride'])}  start={hex(h['start'])}  "
              f"records={h['length']}  end={hex(h['end'])}  "
              f"avg_score={h['score_per_record']}")
        for s in h["sample"][:3]:
            vals_str = " ".join(f"{v:5d}" for v in s["values"])
            print(f"  +{s['idx']} @ {s['offset']}: {vals_str}  [{','.join(s['flags'])}]")
        print()

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "stride", "start", "length", "end", "avg_score"])
        for i, h in enumerate(hits):
            w.writerow([i, hex(h["stride"]), hex(h["start"]), h["length"],
                        hex(h["end"]), h["score_per_record"]])
    print(f"Wrote candidate summary -> {args.out}")

    for rank, h in enumerate(hits[:3]):
        detail = Path(args.out).with_name(f"gba_enemy_v2_candidate_{rank}.csv")
        with open(detail, "w", newline="") as f:
            w = csv.writer(f)
            stride = h["stride"]
            nw = stride // 2
            w.writerow(["index", "offset"] + [f"u16_{i}" for i in range(nw)])
            for i in range(h["length"]):
                off = h["start"] + i * stride
                vals = [read_u16(rom, off + j * 2) for j in range(nw)]
                w.writerow([i, hex(off)] + vals)
        print(f"Wrote candidate {rank} detail -> {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
