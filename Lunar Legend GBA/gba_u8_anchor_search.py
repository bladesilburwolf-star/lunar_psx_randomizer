#!/usr/bin/env python3
"""
gba_u8_anchor_search.py - search for enemy stats as u8 (single byte) values

All previous search tools assumed u16 (2-byte) values. But enemy stats
like HP=50, EXP=7, SIL=46 easily fit in a single byte (u8). If the ROM
stores them as u8, u16 searches would completely miss them because they
read every other byte as part of a 2-byte value.

This tool searches for the EXACT byte values of known enemy stat triples
within a tight window, reading individual bytes (u8) instead of u16.

It also tests mixed u8/u16 layouts (e.g. HP as u8, EXP as u8, but SIL as u16).

Usage:
  python gba_u8_anchor_search.py lunar.gba
  python gba_u8_anchor_search.py lunar.gba --max-gap 12
  python gba_u8_anchor_search.py lunar.gba --dump-region 0x86f000,0x89f000
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

GBA_ROM_SIZE = 8 * 1024 * 1024

# Known enemy stats: (name, HP, EXP, SIL)
ANCHORS = [
    ("BurgDog",   30,   8,  15),
    ("Pirate1",   50,   7,  21),
    ("Pirate2",   60,   7,  21),
    ("Killfish",  50,   7,  46),
    ("Ammonite",  50,  12,  70),
    ("FatSnake",  40,   6,  40),
    ("Wisp",      40,  12,  56),
]

MAGIC_EMPEROR_HP = 6800  # too large for u8, must be u16

STRIDES = [0x08, 0x0A, 0x0C, 0x0E, 0x10, 0x12, 0x14, 0x16, 0x18, 0x1A,
           0x1C, 0x1E, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40]


def read_u8(rom, off):
    if off < 0 or off >= len(rom):
        return -1
    return rom[off]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def search_u8_triple(rom, hp, exp, sil, max_gap=12):
    """Search for HP as u8 byte, then check if EXP and SIL appear as u8
    bytes within max_gap bytes. Only record if ALL THREE found."""
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len:
        if rom[base] == hp:
            exp_off = None
            sil_off = None
            for delta in range(-max_gap, max_gap + 1):
                off = base + delta
                if 0 <= off < rom_len:
                    v = rom[off]
                    if v == exp and exp_off is None:
                        exp_off = delta
                    if v == sil and sil_off is None:
                        sil_off = delta
            if exp_off is not None and sil_off is not None:
                results.append({
                    "base": base,
                    "exp_off": exp_off,
                    "sil_off": sil_off,
                })
        base += 1
    return results


def search_mixed_triple(rom, hp, exp, sil, max_gap=16):
    """Search for HP as u8, then EXP and SIL as either u8 or u16 nearby."""
    results = []
    rom_len = len(rom)
    base = 0
    while base < rom_len:
        if rom[base] == hp:
            exp_off = None
            sil_off = None
            exp_type = None
            sil_type = None
            for delta in range(-max_gap, max_gap + 1):
                off = base + delta
                if 0 <= off < rom_len:
                    # Check u8
                    v8 = rom[off]
                    if exp_off is None and v8 == exp:
                        exp_off = delta
                        exp_type = "u8"
                    if sil_off is None and v8 == sil:
                        sil_off = delta
                        sil_type = "u8"
                    # Check u16 (LE)
                    if off + 2 <= rom_len:
                        v16 = struct.unpack_from("<H", rom, off)[0]
                        if exp_off is None and v16 == exp:
                            exp_off = delta
                            exp_type = "u16"
                        if sil_off is None and v16 == sil:
                            sil_off = delta
                            sil_type = "u16"
            if exp_off is not None and sil_off is not None:
                results.append({
                    "base": base,
                    "exp_off": exp_off,
                    "sil_off": sil_off,
                    "exp_type": exp_type,
                    "sil_type": sil_type,
                })
        base += 1
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Search Lunar Legend GBA for enemy stats as u8 bytes")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--max-gap", type=int, default=12,
                    help="Max bytes between HP and EXP/SIL (tight window)")
    ap.add_argument("--mode", choices=["u8", "mixed"], default="u8",
                    help="u8=all three as bytes; mixed=HP u8, EXP/SIL u8 or u16")
    ap.add_argument("--out", default="gba_u8_hits.csv")
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
    print("gba_u8_anchor_search - single-byte stat value search")
    print("=" * 64)
    print("  max_gap=" + str(args.max_gap) + " bytes  mode=" + args.mode)
    print("  Searching for (HP, EXP, SIL) as u8 bytes within tight window")
    print()

    all_hits = []

    for name, hp, exp, sil in ANCHORS:
        print("  " + name + " (HP=" + str(hp) + ", EXP=" + str(exp) +
              ", SIL=" + str(sil) + ")... ", end="")

        if args.mode == "u8":
            hits = search_u8_triple(rom, hp, exp, sil, args.max_gap)
        else:
            hits = search_mixed_triple(rom, hp, exp, sil, args.max_gap)

        for h in hits:
            h["anchor"] = name
            all_hits.append(h)
        print(str(len(hits)) + " hits")

    print()
    print("Total hits: " + str(len(all_hits)))

    if not all_hits:
        print("No matches. Try --mode mixed or --max-gap 16")
        return 0

    # Sort by offset
    all_hits.sort(key=lambda h: h["base"])

    # Write hits CSV
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        cols = ["anchor", "base_offset", "exp_off", "sil_off"]
        if args.mode == "mixed":
            cols += ["exp_type", "sil_type"]
        w.writerow(cols)
        for h in all_hits:
            row = [h["anchor"], hex(h["base"]),
                   hex(h["exp_off"]), hex(h["sil_off"])]
            if args.mode == "mixed":
                row += [h.get("exp_type", ""), h.get("sil_type", "")]
            w.writerow(row)
    print("Wrote " + args.out)

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
        if len(seen) >= 20:
            break

    # Field offset patterns per anchor
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
                                                 key=lambda x: -x[1])[:10]:
            extra = ""
            if args.mode == "mixed":
                h0 = [h for h in anchor_hits
                      if h["exp_off"] == exp_off and h["sil_off"] == sil_off][0]
                extra = "  [" + h0.get("exp_type", "") + "/" + h0.get("sil_type", "") + "]"
            print("    exp_off=" + hex(exp_off) + " sil_off=" + hex(sil_off) +
                  " : " + str(count) + " hits" + extra)

    # Stride analysis for best cluster
    if regions:
        best = regions[0]
        print()
        print("=" * 64)
        print("Best cluster: 0x" + format(best["start"], "06x") +
              " (" + str(best["anchors"]) + " anchors, " +
              str(best["hits"]) + " hits)")
        print("=" * 64)

        cluster_hits = [h for h in all_hits
                       if best["start"] <= h["base"] < best["start"] + 4096]

        # Test stride alignment
        print()
        print("Stride alignment (different-anchor HP offset differences):")
        anchor_offsets = {}
        for h in cluster_hits:
            anchor_offsets.setdefault(h["anchor"], []).append(h["base"])

        for stride in STRIDES:
            align = 0
            total = 0
            names = list(anchor_offsets.keys())
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    for a in anchor_offsets[names[i]]:
                        for b in anchor_offsets[names[j]]:
                            diff = abs(b - a)
                            if diff > 0:
                                total += 1
                                if diff % stride == 0:
                                    align += 1
            if total > 0:
                pct = align * 100 // total
                if pct >= 20:
                    bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
                    print("  stride=0x" + format(stride, "02x") +
                          "  " + str(align) + "/" + str(total) +
                          " = " + str(pct) + "%  [" + bar + "]")

    # Dump region
    if args.dump_region:
        ds, de = args.dump_region.split(",")
        dump_start = int(ds, 16)
        dump_end = int(de, 16)

        print()
        print("Dumping 0x" + format(dump_start, "06x") + "..0x" + format(dump_end, "06x") +
              " at multiple strides...")

        for stride in STRIDES:
            nw = stride  # u8 fields per record
            nrecs = (dump_end - dump_start) // stride
            if nrecs < 2 or nrecs > 4000:
                continue
            fname = "gba_u8_dump_s" + format(stride, "x") + ".csv"
            with open(fname, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "offset"] + ["b" + str(i) for i in range(nw)])
                for i in range(nrecs):
                    off = dump_start + i * stride
                    if off + stride > len(rom):
                        break
                    vals = [rom[off + j] for j in range(nw)]
                    w.writerow([i, hex(off)] + vals)
            print("  Wrote " + fname + " (" + str(nrecs) + " records)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
