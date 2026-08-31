#!/usr/bin/env python3
"""
gba_locate_enemy_table.py – find the enemy master table using known stat anchors

Blind scanning (v1, v2) found only index tables and growth tables. This tool
takes the opposite approach: search for KNOWN enemy stat values from game
guides, then find where multiple enemies' stats cluster together — that cluster
IS the enemy table.

Anchor enemies (from Shotgunnova's guide, GameFAQs faq/45134):
  Deathcap:   ~15 HP, 1 EXP, 7 Sil     (first enemy, Saith area)
  Burg Dog:   ~30 HP, 8 EXP, 15 Sil
  Fly Trap:   ~30 HP, 4 EXP, 10 Sil
  Pirate 1:   ~50 HP, 7 EXP, 21 Sil
  Pirate 2:   ~60 HP, 7 EXP, 21 Sil
  Killfish:   ~50 HP, 7 EXP, 46 Sil    (Meribia Sewers)
  Ammonite:   ~50 HP, 12 EXP, 70 Sil   (Meribia Sewers)
  FatSnake:   ~40 HP, 6 EXP, 40 Sil    (Meribia Sewers)
  Wisp:       ~40 HP, 12 EXP, 56 Sil   (Meribia Sewers)
  Magic Emperor: 6800 HP               (final boss)

Strategy:
  1. For each anchor, search the ENTIRE ROM for u16 windows containing that
     enemy's HP, EXP, and SIL within a configurable window (default 40 bytes).
  2. Find ROM offsets where MULTIPLE anchors match nearby — that region is
     almost certainly the enemy table.
  3. With --dump, output u16 fields around the best cluster at several strides.

The HP values use +/- tolerance (default 2) since guide values are approximate.

Usage:
  python3 gba_locate_enemy_table.py lunar.gba
  python3 gba_locate_enemy_table.py lunar.gba --tolerance 3 --window 48 --dump
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GBA_ROM_SIZE = 8 * 1024 * 1024

ANCHORS = [
    ("Deathcap",      15,   1,  7),
    ("Burg Dog",      30,   8, 15),
    ("Fly Trap",      30,   4, 10),
    ("Pirate 1",      50,   7, 21),
    ("Pirate 2",      60,   7, 21),
    ("Killfish",      50,   7, 46),
    ("Ammonite",      50,  12, 70),
    ("FatSnake",      40,   6, 40),
    ("Wisp",          40,  12, 56),
    ("Magic Emperor", 6800, None, None),
]


def read_u16(rom, off):
    if off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def find_value_in_window(rom, start, window, target, tolerance):
    hits = []
    i = 0
    while i < window - 1:
        v = read_u16(rom, start + i)
        if v < 0:
            break
        if abs(v - target) <= tolerance:
            hits.append(i)
        i += 2
    return hits


def search_anchor(rom, hp, exp, sil, tolerance, window):
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len - window:
        hp_hits = find_value_in_window(rom, base, window, hp, tolerance)
        if not hp_hits:
            base += 2
            continue

        for hp_off in hp_hits:
            exp_off = None
            sil_off = None

            if exp is not None:
                exp_hits = find_value_in_window(rom, base, window, exp, tolerance)
                if exp_hits:
                    exp_off = exp_hits[0]

            if sil is not None:
                sil_hits = find_value_in_window(rom, base, window, sil, tolerance)
                if sil_hits:
                    sil_off = sil_hits[0]

            matched = 1
            if exp_off is not None:
                matched += 1
            if sil_off is not None:
                matched += 1

            if matched >= 2:
                results.append({
                    "base": base,
                    "hp_off": hp_off,
                    "exp_off": exp_off,
                    "sil_off": sil_off,
                    "matched": matched,
                })
        base += 2
    return results


def cluster_hits(all_hits, cluster_range):
    if not all_hits:
        return []

    all_hits.sort(key=lambda h: h["base"])

    clusters = []
    current = {"start": all_hits[0]["base"], "end": all_hits[0]["base"],
               "hits": [all_hits[0]], "anchors": set([all_hits[0]["anchor"]])}

    for h in all_hits[1:]:
        if h["base"] - current["end"] <= cluster_range:
            current["end"] = h["base"]
            current["hits"].append(h)
            current["anchors"].add(h["anchor"])
        else:
            clusters.append(current)
            current = {"start": h["base"], "end": h["base"],
                       "hits": [h], "anchors": set([h["anchor"]])}
    clusters.append(current)

    clusters.sort(key=lambda c: len(c["anchors"]), reverse=True)
    return clusters


def main():
    ap = argparse.ArgumentParser(
        description="Locate Lunar Legend GBA enemy table using known stat anchors")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--tolerance", type=int, default=2,
                    help="HP/EXP/SIL match tolerance")
    ap.add_argument("--window", type=int, default=40,
                    help="Byte window to search for stats of one enemy")
    ap.add_argument("--cluster-range", type=int, default=1024,
                    help="Max gap between hits to count as same cluster")
    ap.add_argument("--out", default="gba_enemy_anchor_hits.csv",
                    help="Output CSV for all hits")
    ap.add_argument("--dump", action="store_true",
                    help="Dump u16 fields around best cluster at several strides")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print("WARNING: ROM is only " + str(len(rom)) + " bytes")

    print("Searching ROM for known enemy stat anchors...")
    print("  tolerance=" + str(args.tolerance) + "  window=" + str(args.window) + " bytes")
    print("  " + str(len(ANCHORS)) + " anchor enemies\n")

    all_hits = []
    for name, hp, exp, sil in ANCHORS:
        desc = " (HP=" + str(hp)
        if exp is not None:
            desc += ", EXP=" + str(exp)
        if sil is not None:
            desc += ", Sil=" + str(sil)
        desc += ")..."
        print("  " + name + desc, end=" ")

        if hp >= 1000:
            count = 0
            base = 0
            while base < len(rom) - 2:
                v = read_u16(rom, base)
                if abs(v - hp) <= args.tolerance:
                    all_hits.append({
                        "anchor": name, "base": base,
                        "hp_off": 0, "exp_off": None, "sil_off": None,
                        "matched": 1,
                    })
                    count += 1
                base += 2
            print(str(count) + " hits (HP-only)")
        else:
            hits = search_anchor(rom, hp, exp, sil, args.tolerance, args.window)
            for h in hits:
                h["anchor"] = name
                all_hits.append(h)
            print(str(len(hits)) + " hits")

    print("\nTotal hits: " + str(len(all_hits)))

    if not all_hits:
        print("\nNo matches found. Try increasing --tolerance or --window.")
        return 0

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anchor", "base_offset", "hp_off", "exp_off", "sil_off", "matched"])
        for h in all_hits:
            w.writerow([h["anchor"], hex(h["base"]),
                        hex(h["hp_off"]) if h["hp_off"] is not None else "",
                        hex(h["exp_off"]) if h["exp_off"] is not None else "",
                        hex(h["sil_off"]) if h["sil_off"] is not None else "",
                        h["matched"]])
    print("Wrote all hits -> " + str(args.out))

    clusters = cluster_hits(all_hits, args.cluster_range)
    print("\nClusters (by distinct anchors matched):")
    for i, c in enumerate(clusters[:10]):
        anchor_list = sorted(c["anchors"])
        print("  [" + str(i) + "] " + hex(c["start"]) + ".." + hex(c["end"]) +
              "  anchors=" + str(len(c["anchors"])) + "  hits=" + str(len(c["hits"])) +
              "  {" + ", ".join(anchor_list) + "}")

    if not clusters:
        return 0

    best = clusters[0]
    print("\nBest cluster: " + hex(best["start"]) + ".." + hex(best["end"]) +
          " (" + str(len(best["anchors"])) + " distinct enemies matched)")

    if args.dump:
        dump_start = max(0, best["start"] - 256)
        dump_end = min(len(rom), best["end"] + 256)
        for stride in [0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28]:
            nw = stride // 2
            nrecs = (dump_end - dump_start) // stride
            fname = "gba_enemy_anchor_dump_s" + format(stride, 'x') + ".csv"
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
