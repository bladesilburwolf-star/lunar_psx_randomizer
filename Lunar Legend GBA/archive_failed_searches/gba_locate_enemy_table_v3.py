#!/usr/bin/env python3
"""
gba_locate_enemy_table_v3.py - focused enemy table locator

Improvements over v1:
  - Drops noisy anchors (Deathcap 15/1/7 matches everywhere)
  - Uses ONLY distinctive anchors whose (HP,EXP,SIL) triple is rare
  - Records exact byte offsets of each matched field
  - Tests all common strides and reports alignment score
  - Magic Emperor (6800 HP = 0x1A90) is the key discriminator

Distinctive anchors:
  BurgDog:       30 HP,  8 EXP, 15 Sil
  Pirate1:       50 HP,  7 EXP, 21 Sil
  Pirate2:       60 HP,  7 EXP, 21 Sil
  Killfish:      50 HP,  7 EXP, 46 Sil   (SIL=46 is rare)
  Ammonite:      50 HP, 12 EXP, 70 Sil   (SIL=70 is rare)
  FatSnake:      40 HP,  6 EXP, 40 Sil
  Wisp:          40 HP, 12 EXP, 56 Sil   (SIL=56 is rare)
  MagicEmperor:  6800 HP                (0x1A90 - extremely rare)

Usage:
  python gba_locate_enemy_table_v3.py lunar.gba
  python gba_locate_enemy_table_v3.py lunar.gba --dump
  python gba_locate_enemy_table_v3.py lunar.gba --dump-region 0x579e50,0x57a100
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

GBA_ROM_SIZE = 8 * 1024 * 1024

# (name, hp, exp, sil) - sil=None means HP-only anchor
ANCHORS = [
    ("BurgDog",       30,   8,  15),
    ("Pirate1",        50,   7,  21),
    ("Pirate2",        60,   7,  21),
    ("Killfish",       50,   7,  46),
    ("Ammonite",       50,  12,  70),
    ("FatSnake",       40,   6,  40),
    ("Wisp",           40,  12,  56),
    ("MagicEmperor", 6800, None, None),
]

STRIDES = [0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def search_anchor_full(rom, hp, exp, sil, tol):
    """Find all u16 positions where HP matches, then check if EXP and SIL
    appear nearby (within +/- 64 bytes). Record exact offsets."""
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len - 2:
        v = read_u16(rom, base)
        if abs(v - hp) <= tol:
            exp_off = None
            sil_off = None
            for delta in range(-64, 65, 2):
                off = base + delta
                if exp is not None and exp_off is None:
                    ev = read_u16(rom, off)
                    if abs(ev - exp) <= tol:
                        exp_off = delta
                if sil is not None and sil_off is None:
                    sv = read_u16(rom, off)
                    if abs(sv - sil) <= tol:
                        sil_off = delta
            matched = 1
            if exp_off is not None:
                matched += 1
            if sil_off is not None:
                matched += 1
            # Only record if at least 2 of 3 matched (or HP-only anchor)
            if sil is None or matched >= 2:
                results.append((base, exp_off, sil_off, matched))
        base += 2
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Locate Lunar Legend GBA enemy table (v3 - focused)")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--tolerance", type=int, default=2)
    ap.add_argument("--search-window", type=int, default=64,
                    help="Bytes to search around HP hit for EXP/SIL")
    ap.add_argument("--out", default="gba_anchor_v3_hits.csv")
    ap.add_argument("--dump", action="store_true",
                    help="Dump u16 fields around best region at each stride")
    ap.add_argument("--dump-region", default=None,
                    help="Dump specific region: START,END (hex)")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print("WARNING: ROM is only " + str(len(rom)) + " bytes")

    print("=" * 60)
    print("gba_locate_enemy_table_v3 - focused anchor search")
    print("=" * 60)
    print("  tolerance=" + str(args.tolerance) + "  search_window=" + str(args.search_window))
    print("  " + str(len(ANCHORS)) + " distinctive anchors (noisy anchors excluded)")
    print()

    all_hits = []
    hits_by_anchor = {}

    for name, hp, exp, sil in ANCHORS:
        print("  " + name + " (HP=" + str(hp), end="")
        if exp is not None:
            print(", EXP=" + str(exp), end="")
        if sil is not None:
            print(", Sil=" + str(sil), end="")
        print(")... ", end="")

        hits = search_anchor_full(rom, hp, exp, sil, args.tolerance)
        hits_by_anchor[name] = hits
        for (base, exp_off, sil_off, matched) in hits:
            all_hits.append({
                "anchor": name, "base": base,
                "exp_off": exp_off, "sil_off": sil_off, "matched": matched
            })
        print(str(len(hits)) + " hits")

    print()
    print("Total hits: " + str(len(all_hits)))

    # Write all hits
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anchor", "base_offset", "hp_at", "exp_off", "sil_off", "matched"])
        for h in all_hits:
            w.writerow([h["anchor"], hex(h["base"]), "0",
                        hex(h["exp_off"]) if h["exp_off"] is not None else "",
                        hex(h["sil_off"]) if h["sil_off"] is not None else "",
                        h["matched"]])
    print("Wrote hits -> " + str(args.out))

    # Find regions where MULTIPLE different anchors cluster
    all_hits.sort(key=lambda h: h["base"])

    # Sliding window: find 4KB regions with most distinct anchors
    print()
    print("=" * 60)
    print("Top 4KB regions by distinct anchor count:")
    print("=" * 60)

    regions = []
    for i in range(len(all_hits)):
        anchors_in_window = set()
        count_in_window = 0
        for j in range(i, len(all_hits)):
            if all_hits[j]["base"] - all_hits[i]["base"] > 4096:
                break
            anchors_in_window.add(all_hits[j]["anchor"])
            count_in_window += 1
        if len(anchors_in_window) >= 2:
            regions.append({
                "start": all_hits[i]["base"],
                "anchors": len(anchors_in_window),
                "hits": count_in_window,
                "anchor_names": sorted(anchors_in_window)
            })

    # Deduplicate overlapping regions (keep best)
    regions.sort(key=lambda r: r["anchors"], reverse=True)
    top_regions = []
    for r in regions:
        overlap = False
        for t in top_regions:
            if abs(r["start"] - t["start"]) < 4096:
                overlap = True
                break
        if not overlap:
            top_regions.append(r)
        if len(top_regions) >= 15:
            break

    for i, r in enumerate(top_regions):
        print("  [" + str(i) + "] 0x" + format(r["start"], "06x") +
              "  anchors=" + str(r["anchors"]) +
              "  hits=" + str(r["hits"]) +
              "  {" + ", ".join(r["anchor_names"]) + "}")

    if not top_regions:
        print("  (no regions with 2+ distinct anchors found)")
        print()
        print("  Single-anchor MagicEmperor hits:")
        for h in all_hits:
            if h["anchor"] == "MagicEmperor":
                print("    0x" + format(h["base"], "06x"))
        print()
        print("  All anchor hit counts:")
        for name in hits_by_anchor:
            print("    " + name + ": " + str(len(hits_by_anchor[name])))
        return 0

    # For the best region, test stride alignment
    best = top_regions[0]
    region_start = best["start"]
    region_end = region_start + 4096

    print()
    print("=" * 60)
    print("Best region: 0x" + format(region_start, "06x") +
          " (" + str(best["anchors"]) + " distinct anchors)")
    print("=" * 60)

    # Show individual hits in the best region
    region_hits = [h for h in all_hits if region_start <= h["base"] < region_end]
    print()
    print("Hits in best region:")
    for h in region_hits:
        print("  " + h["anchor"] + " @ 0x" + format(h["base"], "06x") +
              "  exp_off=" + (hex(h["exp_off"]) if h["exp_off"] is not None else "-") +
              "  sil_off=" + (hex(h["sil_off"]) if h["sil_off"] is not None else "-"))

    # Test stride alignment
    print()
    print("Stride alignment test (different-anchor pairs divisible by stride):")
    region_anchor_hits = {}
    for h in region_hits:
        region_anchor_hits.setdefault(h["anchor"], []).append(h["base"])

    for stride in STRIDES:
        align = 0
        total = 0
        names = list(region_anchor_hits.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for a in region_anchor_hits[names[i]]:
                    for b in region_anchor_hits[names[j]]:
                        diff = abs(b - a)
                        if diff > 0:
                            total += 1
                            if diff % stride == 0:
                                align += 1
        if total > 0:
            pct = align * 100 // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print("  stride=0x" + format(stride, "02x") +
                  " (" + str(stride) + "B)  " + str(align) + "/" + str(total) +
                  " = " + str(pct) + "%  [" + bar + "]")

    # Dump
    if args.dump or args.dump_region:
        if args.dump_region:
            ds, de = args.dump_region.split(",")
            dump_start = int(ds, 16)
            dump_end = int(de, 16)
        else:
            dump_start = max(0, region_start - 128)
            dump_end = min(len(rom), region_end + 128)

        print()
        print("Dumping 0x" + format(dump_start, "06x") + "..0x" + format(dump_end, "06x") +
              " at multiple strides...")

        for stride in [0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38]:
            nw = stride // 2
            nrecs = (dump_end - dump_start) // stride
            fname = "gba_anchor_v3_dump_s" + format(stride, "x") + ".csv"
            with open(fname, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "offset"] + ["u" + str(i) for i in range(nw)])
                for i in range(nrecs):
                    off = dump_start + i * stride
                    if off + stride > len(rom):
                        break
                    vals = [read_u16(rom, off + j * 2) for j in range(nw)]
                    w.writerow([i, hex(off)] + vals)
            print("  Wrote " + fname + " (" + str(nrecs) + " records)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
