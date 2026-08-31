#!/usr/bin/env python3
"""
gba_exact_anchor_search.py - search for EXACT enemy stat byte patterns

Previous anchor tools used +/- 64 byte windows, causing false positives by
matching values from different records. This tool searches for the EXACT
u16 LE byte sequences of known enemy stat triples within a TIGHT window
(8-16 bytes), then tests strides to find the table.

It also dumps the promising 0x86F000-0x89F000 region at multiple strides
for manual inspection, since the v3 anchor search found all 7 non-boss
anchors with matched=3 hits clustering there.

Usage:
  python gba_exact_anchor_search.py lunar.gba
  python gba_exact_anchor_search.py lunar.gba --dump-region 0x86f000,0x89f000
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

GBA_ROM_SIZE = 8 * 1024 * 1024

# Known enemy stats: (name, HP, EXP, SIL)
# These are the distinctive anchors - the triple must appear together
ANCHORS = [
    ("BurgDog",   30,   8,  15),
    ("Pirate1",   50,   7,  21),
    ("Pirate2",   60,   7,  21),
    ("Killfish",  50,   7,  46),
    ("Ammonite",  50,  12,  70),
    ("FatSnake",  40,   6,  40),
    ("Wisp",      40,  12,  56),
]

# Also the exact-tolerance Magic Emperor HP
MAGIC_EMPEROR_HP = 6800

STRIDES = [0x0C, 0x0E, 0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x1C, 0x1E, 0x20,
           0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def search_exact_triple(rom, hp, exp, sil, max_gap=16):
    """Search for HP value as u16, then check if EXP and SIL appear as u16
    within max_gap bytes of the HP position. Only record if ALL THREE
    are found within the tight window."""
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len - 2:
        v = read_u16(rom, base)
        if v == hp:
            # Found HP. Search +/- max_gap for EXP and SIL
            exp_off = None
            sil_off = None
            for delta in range(-max_gap, max_gap + 1, 2):
                off = base + delta
                ev = read_u16(rom, off)
                if ev == exp and exp_off is None:
                    exp_off = delta
                if ev == sil and sil_off is None:
                    sil_off = delta
            if exp_off is not None and sil_off is not None:
                results.append({
                    "base": base,
                    "exp_off": exp_off,
                    "sil_off": sil_off,
                })
        base += 2
    return results


def search_exact_triple_tolerance(rom, hp, exp, sil, tol=1, max_gap=16):
    """Same but with small tolerance for approximate guide values."""
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len - 2:
        v = read_u16(rom, base)
        if abs(v - hp) <= tol:
            exp_off = None
            sil_off = None
            for delta in range(-max_gap, max_gap + 1, 2):
                off = base + delta
                ev = read_u16(rom, off)
                if exp_off is None and abs(ev - exp) <= tol:
                    exp_off = delta
                if sil_off is None and abs(ev - sil) <= tol:
                    sil_off = delta
            if exp_off is not None and sil_off is not None:
                results.append({
                    "base": base,
                    "exp_off": exp_off,
                    "sil_off": sil_off,
                    "hp_val": v,
                })
        base += 2
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Search Lunar Legend GBA for exact enemy stat byte patterns")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--max-gap", type=int, default=16,
                    help="Max bytes between HP and EXP/SIL (tight window)")
    ap.add_argument("--tolerance", type=int, default=0,
                    help="Tolerance for approximate guide values (0=exact)")
    ap.add_argument("--dump-region", default=None,
                    help="Dump region START,END (hex) at multiple strides")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print("WARNING: ROM is only " + str(len(rom)) + " bytes")

    print("=" * 64)
    print("gba_exact_anchor_search - tight-window exact triple search")
    print("=" * 64)
    print("  max_gap=" + str(args.max_gap) + " bytes  tolerance=" + str(args.tolerance))
    print("  Searching for EXACT (HP, EXP, SIL) triples within tight window")
    print()

    all_hits = []

    for name, hp, exp, sil in ANCHORS:
        print("  " + name + " (HP=" + str(hp) + ", EXP=" + str(exp) +
              ", SIL=" + str(sil) + ")... ", end="")

        if args.tolerance == 0:
            hits = search_exact_triple(rom, hp, exp, sil, args.max_gap)
        else:
            hits = search_exact_triple_tolerance(rom, hp, exp, sil,
                                                 args.tolerance, args.max_gap)

        for h in hits:
            h["anchor"] = name
            all_hits.append(h)
        print(str(len(hits)) + " exact hits")

    # Search for Magic Emperor HP
    print("  MagicEmperor (HP=" + str(MAGIC_EMPEROR_HP) + ")... ", end="")
    me_hits = []
    base = 0
    while base < len(rom) - 2:
        v = read_u16(rom, base)
        if abs(v - MAGIC_EMPEROR_HP) <= args.tolerance:
            me_hits.append({"base": base, "anchor": "MagicEmperor",
                           "exp_off": None, "sil_off": None, "hp_val": v})
        base += 2
    all_hits.extend(me_hits)
    print(str(len(me_hits)) + " hits")

    print()
    print("Total hits: " + str(len(all_hits)))

    if not all_hits:
        print("No exact triple matches found. Try --tolerance 1 or --max-gap 24")
        return 0

    # Sort by offset
    all_hits.sort(key=lambda h: h["base"])

    # Write hits CSV
    with open("gba_exact_hits.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anchor", "base_offset", "exp_off", "sil_off", "hp_val"])
        for h in all_hits:
            w.writerow([h["anchor"], hex(h["base"]),
                        hex(h["exp_off"]) if h.get("exp_off") is not None else "",
                        hex(h["sil_off"]) if h.get("sil_off") is not None else "",
                        h.get("hp_val", "")])
    print("Wrote gba_exact_hits.csv")

    # Find clusters (different anchors within 4KB)
    print()
    print("=" * 64)
    print("Clusters (different anchors within 4KB):")
    print("=" * 64)

    regions = []
    for i in range(len(all_hits)):
        anchors_in_window = set()
        count = 0
        for j in range(i, len(all_hits)):
            if all_hits[j]["base"] - all_hits[i]["base"] > 4096:
                break
            anchors_in_window.add(all_hits[j]["anchor"])
            count += 1
        if len(anchors_in_window) >= 2:
            regions.append({
                "start": all_hits[i]["base"],
                "anchors": len(anchors_in_window),
                "hits": count,
                "names": sorted(anchors_in_window)
            })

    regions.sort(key=lambda r: r["anchors"], reverse=True)
    seen = []
    for r in regions:
        if any(abs(r["start"] - s) < 4096 for s in seen):
            continue
        seen.append(r["start"])
        print("  0x" + format(r["start"], "06x") +
              "  anchors=" + str(r["anchors"]) +
              "  hits=" + str(r["hits"]) +
              "  {" + ", ".join(r["names"]) + "}")
        if len(seen) >= 15:
            break

    # For each anchor, show its hits grouped by exp_off/sil_off pattern
    print()
    print("=" * 64)
    print("Field offset patterns (exp_off, sil_off) per anchor:")
    print("=" * 64)
    for name, _, _, _ in ANCHORS:
        anchor_hits = [h for h in all_hits if h["anchor"] == name]
        if not anchor_hits:
            continue
        patterns = {}
        for h in anchor_hits:
            key = (h["exp_off"], h["sil_off"])
            patterns[key] = patterns.get(key, 0) + 1
        print()
        print("  " + name + " (" + str(len(anchor_hits)) + " hits):")
        for (exp_off, sil_off), count in sorted(patterns.items(),
                                                 key=lambda x: -x[1]):
            print("    exp_off=" + hex(exp_off) + " sil_off=" + hex(sil_off) +
                  " : " + str(count) + " hits")

    # Dump region
    if args.dump_region:
        ds, de = args.dump_region.split(",")
        dump_start = int(ds, 16)
        dump_end = int(de, 16)

        print()
        print("Dumping 0x" + format(dump_start, "06x") + "..0x" + format(dump_end, "06x") +
              " at multiple strides...")

        for stride in STRIDES:
            nw = stride // 2
            nrecs = (dump_end - dump_start) // stride
            if nrecs < 2 or nrecs > 2000:
                continue
            fname = "gba_exact_dump_s" + format(stride, "x") + ".csv"
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
