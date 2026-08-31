#!/usr/bin/env python3
"""
gba_template_search.py - Find enemy table by template matching

Instead of searching for individual stat values scattered across the ROM,
this tool uses a distinctive anchor (MagicEmperor HP=6800=0x1A90) and tests
whether a table exists with that value at a fixed stride, with other records
matching known enemy HP values.

This is "template matching": we know what the table should look like (a
sequence of records where HP fields contain 15, 30, 40, 50, 60, ..., 6800),
we just need to find where it is and what stride it uses.

Strategy:
  1. Find all u16 occurrences of the anchor value (0x1A90 = 6800) in the ROM
  2. For each occurrence and each stride (8-64 bytes):
     - Assume this is the HP field of some enemy record
     - Read u16 values at the same field offset in surrounding records
     - Check how many match known enemy HP values
  3. Score each candidate: more unique HP matches = better
  4. For the best candidate, validate by checking EXP and SIL at nearby offsets
  5. Dump the full table for manual inspection

Also tests u8 HP values (single byte) in case stats are stored as bytes.

Usage:
  python gba_template_search.py lunar.gba
  python gba_template_search.py lunar.gba --dump-best
  python gba_template_search.py lunar.gba --mode u8
  python gba_template_search.py lunar.gba --mode u16 --validate
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from pathlib import Path

GBA_ROM_SIZE = 8 * 1024 * 1024

# Known enemy stats: (name, HP, EXP, SIL)
ENEMIES = [
    ("Deathcap",     15,   1,   7),
    ("BurgDog",      30,   8,  15),
    ("FlyTrap",      30,   4,  10),
    ("Pirate1",      50,   7,  21),
    ("Pirate2",      60,   7,  21),
    ("Killfish",     50,   7,  46),
    ("Ammonite",     50,  12,  70),
    ("FatSnake",     40,   6,  40),
    ("Wisp",         40,  12,  56),
    ("MagicEmperor", 6800, 0, 0),  # final boss - HP too large for u8
]

# Known HP values for u16 mode
KNOWN_HPS_U16 = sorted(set(hp for _, hp, _, _ in ENEMIES))
# Known HP values for u8 mode (exclude 6800 - too large for a byte)
KNOWN_HPS_U8 = sorted(set(hp for _, hp, _, _ in ENEMIES if hp <= 255))

# For validation: maps HP -> list of (EXP, SIL) pairs
HP_TO_STATS = {}
for name, hp, exp, sil in ENEMIES:
    HP_TO_STATS.setdefault(hp, []).append((exp, sil, name))

STRIDES = list(range(6, 65, 1))  # 6, 7, 8, ..., 64


def read_u8(rom, off):
    if off < 0 or off >= len(rom):
        return -1
    return rom[off]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def find_u16_occurrences(rom, value):
    """Find all offsets where u16 LE matches value."""
    results = []
    target = struct.pack("<H", value)
    pos = 0
    while True:
        pos = rom.find(target, pos)
        if pos == -1:
            break
        results.append(pos)
        pos += 2
    return results


def find_u8_occurrences(rom, value):
    """Find all offsets where a single byte matches value."""
    results = []
    pos = 0
    while True:
        pos = rom.find(bytes([value]), pos)
        if pos == -1:
            break
        results.append(pos)
        pos += 1
    return results


def score_table_u16(rom, table_start, stride, hp_offset, max_records=200):
    """Read u16 HP values from a table and score how many match known HPs."""
    matches = []
    for i in range(max_records):
        off = table_start + i * stride + hp_offset
        if off + 2 > len(rom):
            break
        v = read_u16(rom, off)
        if v in KNOWN_HPS_U16:
            matches.append((i, off, v))
    return matches


def score_table_u8(rom, table_start, stride, hp_offset, max_records=300):
    """Read u8 HP values from a table and score how many match known HPs."""
    matches = []
    for i in range(max_records):
        off = table_start + i * stride + hp_offset
        if off + 1 > len(rom):
            break
        v = read_u8(rom, off)
        if v in KNOWN_HPS_U8:
            matches.append((i, off, v))
    return matches


def validate_record_u16(rom, record_off, stride, hp_offset):
    """For a record, check if EXP and SIL values appear at nearby offsets."""
    hp_val = read_u16(rom, record_off + hp_offset)
    if hp_val not in HP_TO_STATS:
        return None
    
    results = []
    for exp, sil, name in HP_TO_STATS[hp_val]:
        # Search for EXP and SIL as u16 at offsets within the record
        for exp_off in range(0, stride, 2):
            if exp_off == hp_offset:
                continue
            exp_val = read_u16(rom, record_off + exp_off)
            if exp_val == exp:
                for sil_off in range(0, stride, 2):
                    if sil_off == hp_offset or sil_off == exp_off:
                        continue
                    sil_val = read_u16(rom, record_off + sil_off)
                    if sil_val == sil:
                        results.append({
                            "name": name,
                            "hp_off": hp_offset,
                            "exp_off": exp_off,
                            "sil_off": sil_off,
                        })
    return results


def validate_record_u8(rom, record_off, stride, hp_offset):
    """For a record, check if EXP and SIL appear as u8 at nearby offsets."""
    hp_val = read_u8(rom, record_off + hp_offset)
    if hp_val not in HP_TO_STATS:
        return None
    
    results = []
    for exp, sil, name in HP_TO_STATS[hp_val]:
        for exp_off in range(0, stride):
            if exp_off == hp_offset:
                continue
            exp_val = read_u8(rom, record_off + exp_off)
            if exp_val == exp:
                for sil_off in range(0, stride):
                    if sil_off == hp_offset or sil_off == exp_off:
                        continue
                    sil_val = read_u8(rom, record_off + sil_off)
                    if sil_val == sil:
                        results.append({
                            "name": name,
                            "hp_off": hp_offset,
                            "exp_off": exp_off,
                            "sil_off": sil_off,
                        })
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Find enemy table by template matching against known HP values")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--anchor", default="0x1A90",
                    help="Anchor u16 value (default: 6800 = 0x1A90)")
    ap.add_argument("--mode", choices=["u16", "u8", "both"], default="both",
                    help="u16: search HP as 2-byte; u8: search HP as 1-byte; both: try both")
    ap.add_argument("--max-records", type=int, default=200,
                    help="Max records to scan per candidate")
    ap.add_argument("--dump-best", action="store_true",
                    help="Dump the best candidate table to CSV")
    ap.add_argument("--validate", action="store_true",
                    help="Validate best candidates by checking EXP/SIL")
    ap.add_argument("--out", default="gba_template_hits.csv")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print("WARNING: ROM is only " + str(len(rom)) + " bytes")

    anchor_val = int(args.anchor, 0) if args.anchor.startswith("0x") else int(args.anchor)
    print("=" * 64)
    print("gba_template_search - enemy table template matching")
    print("=" * 64)
    print("  Mode: " + args.mode)
    print("  Anchor (u16): 0x" + format(anchor_val, "04X") + " (" + str(anchor_val) + ")")
    print("  Known HP (u16): " + str(KNOWN_HPS_U16))
    if args.mode in ("u8", "both"):
        print("  Known HP (u8):  " + str(KNOWN_HPS_U8))
    print("  Strides tested: " + str(STRIDES[0]) + "-" + str(STRIDES[-1]))
    print()

    all_candidates = []

    # ---- U16 mode ----
    if args.mode in ("u16", "both"):
        print("--- U16 mode ---")
        anchor_offsets = find_u16_occurrences(rom, anchor_val)
        print("  Anchor (0x1A90) occurrences: " + str(len(anchor_offsets)))

        for anchor_off in anchor_offsets:
            for stride in STRIDES:
                for hp_off in range(0, min(stride, 32), 2):
                    for me_idx in list(range(0, 160, 5)) + [159]:
                        table_start = anchor_off - me_idx * stride - hp_off
                        if table_start < 0:
                            continue
                        matches = score_table_u16(rom, table_start, stride, hp_off,
                                                   args.max_records)
                        matched_hps = set(m[2] for m in matches)
                        score = len(matched_hps)
                        if 6800 in matched_hps:
                            score += 3
                        if len(matched_hps) >= 3:
                            score += 2
                        if len(matched_hps) >= 5:
                            score += 2

                        if score >= 4:
                            all_candidates.append({
                                "mode": "u16",
                                "anchor_off": anchor_off,
                                "table_start": table_start,
                                "stride": stride,
                                "hp_off": hp_off,
                                "me_idx": me_idx,
                                "score": score,
                                "matched_hps": sorted(matched_hps),
                                "n_matches": len(matches),
                                "matches": matches,
                            })
        print("  U16 candidates: " + str(len(all_candidates)))

    # ---- U8 mode ----
    if args.mode in ("u8", "both"):
        print("--- U8 mode ---")
        # In u8 mode, we use distinctive low HP values as anchors instead of 6800
        # Use HP=60 (Pirate2) as anchor since 60 is somewhat distinctive
        # Actually, let's use multiple u8 anchors
        u8_anchors = [60]  # Pirate2 HP=60, fairly distinctive for u8
        # Also use 15 (Deathcap) - very distinctive
        u8_anchors.append(15)
        
        for anchor_hp in u8_anchors:
            print("  U8 anchor: HP=" + str(anchor_hp))
            anchor_offsets_u8 = find_u8_occurrences(rom, anchor_hp)
            print("    occurrences: " + str(len(anchor_offsets_u8)))
            
            # Limit to first 5000 occurrences for speed
            if len(anchor_offsets_u8) > 5000:
                print("    (limiting to first 5000)")
                anchor_offsets_u8 = anchor_offsets_u8[:5000]

            for anchor_off in anchor_offsets_u8:
                for stride in STRIDES:
                    for hp_off in range(0, min(stride, 16)):
                        # For u8, test fewer index positions
                        for me_idx in [0, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100]:
                            table_start = anchor_off - me_idx * stride - hp_off
                            if table_start < 0:
                                continue
                            matches = score_table_u8(rom, table_start, stride, hp_off,
                                                      300)
                            matched_hps = set(m[2] for m in matches)
                            score = len(matched_hps)
                            # No 6800 bonus in u8 mode
                            if len(matched_hps) >= 3:
                                score += 2
                            if len(matched_hps) >= 4:
                                score += 2
                            if len(matched_hps) >= 5:
                                score += 2

                            if score >= 4:
                                all_candidates.append({
                                    "mode": "u8",
                                    "anchor_off": anchor_off,
                                    "table_start": table_start,
                                    "stride": stride,
                                    "hp_off": hp_off,
                                    "me_idx": me_idx,
                                    "score": score,
                                    "matched_hps": sorted(matched_hps),
                                    "n_matches": len(matches),
                                    "matches": matches,
                                })
        print("  U8 candidates (total): " + str(len([c for c in all_candidates if c["mode"] == "u8"])))

    # Sort all candidates by score
    all_candidates.sort(key=lambda c: c["score"], reverse=True)

    # Deduplicate
    seen = set()
    unique = []
    for c in all_candidates:
        key = (c["mode"], c["table_start"], c["stride"], c["hp_off"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    print()
    print("Total unique candidates (score>=4): " + str(len(unique)))

    # Show top 30
    print()
    print("=" * 64)
    print("Top 30 candidates:")
    print("=" * 64)
    for i, c in enumerate(unique[:30]):
        print("  #" + str(i+1) + " [" + c["mode"] + "]" +
              " score=" + str(c["score"]) +
              "  start=0x" + format(c["table_start"], "06x") +
              "  stride=0x" + format(c["stride"], "02x") +
              "  hp_off=0x" + format(c["hp_off"], "02x") +
              "  matched_HPs=" + str(c["matched_hps"]) +
              "  n=" + str(c["n_matches"]))

    # Write CSV
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "mode", "score", "table_start", "stride", "hp_off",
                    "matched_hps", "n_matches"])
        for i, c in enumerate(unique[:200]):
            w.writerow([i+1, c["mode"], c["score"],
                        hex(c["table_start"]), hex(c["stride"]), hex(c["hp_off"]),
                        "|".join(str(h) for h in c["matched_hps"]),
                        c["n_matches"]])
    print("Wrote " + args.out)

    # Validate top candidates
    if args.validate and unique:
        print()
        print("=" * 64)
        print("Validating top 5 candidates (checking EXP/SIL):")
        print("=" * 64)
        for c in unique[:5]:
            print()
            print("  [" + c["mode"] + "] start=0x" + format(c["table_start"], "06x") +
                  " stride=0x" + format(c["stride"], "02x") +
                  " hp_off=0x" + format(c["hp_off"], "02x") +
                  " score=" + str(c["score"]))
            
            # Validate each matched record
            valid_count = 0
            field_patterns = {}
            for idx, off, hp_val in c["matches"][:50]:
                record_off = c["table_start"] + idx * c["stride"]
                if c["mode"] == "u16":
                    results = validate_record_u16(rom, record_off, c["stride"], c["hp_off"])
                else:
                    results = validate_record_u8(rom, record_off, c["stride"], c["hp_off"])
                
                if results:
                    valid_count += 1
                    for r in results:
                        key = (r["exp_off"], r["sil_off"])
                        field_patterns[key] = field_patterns.get(key, 0) + 1
            
            print("    Records with valid EXP+SIL: " + str(valid_count) + "/" +
                  str(min(50, len(c["matches"]))))
            if field_patterns:
                print("    Field offset patterns (exp_off, sil_off):")
                for (exp_off, sil_off), count in sorted(field_patterns.items(),
                                                        key=lambda x: -x[1])[:5]:
                    print("      exp@+0x" + format(exp_off, "02x") +
                          " sil@+0x" + format(sil_off, "02x") +
                          " : " + str(count) + " records")

    # Dump best candidate
    if unique and args.dump_best:
        best = unique[0]
        ts = best["table_start"]
        st = best["stride"]
        ho = best["hp_off"]
        mode = best["mode"]
        print()
        print("=" * 64)
        print("Dumping best: [" + mode + "] start=0x" + format(ts, "06x") +
              " stride=0x" + format(st, "02x") + " hp_off=0x" + format(ho, "02x"))
        print("=" * 64)

        dump_name = "gba_template_dump.csv"
        with open(dump_name, "w", newline="") as f:
            w = csv.writer(f)
            if mode == "u16":
                nfields = st // 2
                w.writerow(["index", "offset"] +
                           ["u" + str(i*2) for i in range(nfields)] +
                           ["hp_match"])
            else:
                nfields = st
                w.writerow(["index", "offset"] +
                           ["b" + str(i) for i in range(nfields)] +
                           ["hp_match"])
            
            for i in range(args.max_records):
                off = ts + i * st
                if off + st > len(rom):
                    break
                if mode == "u16":
                    vals = [read_u16(rom, off + j*2) for j in range(nfields)]
                    hp_val = read_u16(rom, off + ho)
                else:
                    vals = [read_u8(rom, off + j) for j in range(nfields)]
                    hp_val = read_u8(rom, off + ho)
                
                hp_match = ""
                for name, hp, exp, sil in ENEMIES:
                    if hp == hp_val:
                        hp_match = name
                        break
                w.writerow([i, hex(off)] + vals + [hp_match])
        print("Wrote " + dump_name)

        print()
        print("Records with known HP values:")
        for m in best["matches"][:30]:
            print("  idx=" + str(m[0]) + "  off=0x" + format(m[1], "06x") +
                  "  HP=" + str(m[2]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
