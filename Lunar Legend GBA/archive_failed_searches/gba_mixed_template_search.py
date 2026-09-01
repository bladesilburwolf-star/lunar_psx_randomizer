#!/usr/bin/env python3
"""
gba_mixed_template_search.py - Find enemy table with mixed u16 HP / u8 EXP+SIL

KEY INSIGHT: MagicEmperor HP=6800 (0x1A90) is too large for a single byte,
so the enemy table MUST store HP as u16 (2 bytes). But EXP and SIL values
(1, 7, 8, 12, 21, 46, 70...) fit in a single byte and may be stored as u8.

Previous u16 searches failed because they required ALL THREE values (HP,
EXP, SIL) to be u16. If EXP and SIL are actually u8, the u16 search would
read pairs of bytes and miss the single-byte values.

This tool:
  1. Finds all u16 occurrences of 0x1A90 (6800) in the ROM — MagicEmperor HP
  2. For each occurrence, tests strides 8-64 bytes
  3. At each stride, reads u16 values and checks if they match known HP values
     (15, 30, 40, 50, 60, 6800)
  4. For records with matching HP, checks if u8 EXP and SIL values appear
     at nearby offsets within the record
  5. Reports the best (table_start, stride, hp_offset) with the most matches

This is MUCH faster than the previous template search because:
  - Only 37 u16 anchor positions (MagicEmperor HP=6800)
  - Only ~30 strides × ~16 HP offsets = ~480 tests per anchor
  - Total: ~18K table scans, each reading ~200 u16 values = very fast

Usage:
  python gba_mixed_template_search.py lunar.gba
  python gba_mixed_template_search.py lunar.gba --dump-best
  python gba_mixed_template_search.py lunar.gba --validate
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
    ("MagicEmperor", 6800, 0, 0),
]

# Known HP values as u16
KNOWN_HPS_U16 = {15, 30, 40, 50, 60, 6800}

# Map HP -> list of (EXP, SIL, name) for validation
HP_TO_STATS = {}
for name, hp, exp, sil in ENEMIES:
    HP_TO_STATS.setdefault(hp, []).append((exp, sil, name))

# All known EXP values (u8)
KNOWN_EXPS = {1, 4, 6, 7, 8, 12}
# All known SIL values (u8)
KNOWN_SILS = {7, 10, 15, 21, 40, 46, 56, 70}

STRIDES = list(range(8, 65, 2))


def read_u8(rom, off):
    if off < 0 or off >= len(rom):
        return -1
    return rom[off]


def read_u16(rom, off):
    if off < 0 or off + 2 > len(rom):
        return -1
    return struct.unpack_from("<H", rom, off)[0]


def find_u16_occurrences(rom, value):
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


def scan_table(rom, table_start, stride, hp_offset, max_records=200):
    """Read u16 HP values from table, return list of (idx, offset, hp_val) for known HPs."""
    matches = []
    for i in range(max_records):
        off = table_start + i * stride + hp_offset
        if off + 2 > len(rom):
            break
        v = read_u16(rom, off)
        if v in KNOWN_HPS_U16:
            matches.append((i, off, v))
    return matches


def validate_record(rom, record_off, stride, hp_offset):
    """Check if u8 EXP and SIL values appear at nearby offsets within the record."""
    hp_val = read_u16(rom, record_off + hp_offset)
    if hp_val not in HP_TO_STATS:
        return None

    results = []
    for exp, sil, name in HP_TO_STATS[hp_val]:
        # Search for EXP as u8 at every offset in the record
        for exp_off in range(0, stride):
            if exp_off == hp_offset or exp_off == hp_offset + 1:
                continue  # Skip HP bytes
            if read_u8(rom, record_off + exp_off) == exp:
                # Search for SIL as u8
                for sil_off in range(0, stride):
                    if sil_off in (hp_offset, hp_offset + 1, exp_off):
                        continue
                    if read_u8(rom, record_off + sil_off) == sil:
                        results.append({
                            "name": name,
                            "hp_off": hp_offset,
                            "exp_off": exp_off,
                            "sil_off": sil_off,
                        })
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Find enemy table: HP as u16, EXP/SIL as u8")
    ap.add_argument("rom", help="Path to USA lunar.gba ROM")
    ap.add_argument("--anchor", default="0x1A90",
                    help="Anchor u16 value (default 6800)")
    ap.add_argument("--max-records", type=int, default=200)
    ap.add_argument("--dump-best", action="store_true")
    ap.add_argument("--validate", action="store_true",
                    help="Validate top candidates by checking u8 EXP/SIL")
    ap.add_argument("--out", default="gba_mixed_template_hits.csv")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print("ERROR: ROM not found: " + str(rom_path))
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print("WARNING: ROM is only " + str(len(rom)) + " bytes")

    anchor_val = int(args.anchor, 0)
    print("=" * 64)
    print("gba_mixed_template_search")
    print("  HP as u16, EXP and SIL as u8")
    print("=" * 64)
    print("  Anchor: 0x" + format(anchor_val, "04X") + " (" + str(anchor_val) + ")")
    print("  Known HP (u16): " + str(sorted(KNOWN_HPS_U16)))
    print("  Known EXP (u8):  " + str(sorted(KNOWN_EXPS)))
    print("  Known SIL (u8):  " + str(sorted(KNOWN_SILS)))
    print("  Strides: " + str(STRIDES[0]) + "-" + str(STRIDES[-1]))
    print()

    # Step 1: Find anchor occurrences
    anchor_offsets = find_u16_occurrences(rom, anchor_val)
    print("Anchor occurrences: " + str(len(anchor_offsets)))

    # Step 2: Test each anchor position with each stride and HP offset
    candidates = []

    for anchor_off in anchor_offsets:
        for stride in STRIDES:
            # HP could be at any even offset within the record
            for hp_off in range(0, min(stride, 32), 2):
                # Test different MagicEmperor index positions
                for me_idx in list(range(0, 160, 5)) + [159]:
                    table_start = anchor_off - me_idx * stride - hp_off
                    if table_start < 0:
                        continue

                    matches = scan_table(rom, table_start, stride, hp_off,
                                         args.max_records)
                    matched_hps = set(m[2] for m in matches)
                    score = len(matched_hps)

                    # Bonuses
                    if 6800 in matched_hps:
                        score += 3
                    if len(matched_hps) >= 3:
                        score += 2
                    if len(matched_hps) >= 4:
                        score += 2
                    if len(matched_hps) >= 5:
                        score += 2

                    if score >= 4:
                        candidates.append({
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

    # Sort and deduplicate
    candidates.sort(key=lambda c: c["score"], reverse=True)
    seen = set()
    unique = []
    for c in candidates:
        key = (c["table_start"], c["stride"], c["hp_off"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    print("Candidates (score>=4): " + str(len(unique)))
    print()

    # Show top 20
    print("=" * 64)
    print("Top 20 candidates:")
    print("=" * 64)
    for i, c in enumerate(unique[:20]):
        print("  #" + str(i+1) +
              " score=" + str(c["score"]) +
              "  start=0x" + format(c["table_start"], "06x") +
              "  stride=0x" + format(c["stride"], "02x") +
              "  hp_off=0x" + format(c["hp_off"], "02x") +
              "  ME@idx=" + str(c["me_idx"]) +
              "  HPs=" + str(c["matched_hps"]) +
              "  n=" + str(c["n_matches"]))

    # Write CSV
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "score", "table_start", "stride", "hp_off",
                    "me_idx", "matched_hps", "n_matches"])
        for i, c in enumerate(unique[:200]):
            w.writerow([i+1, c["score"],
                        hex(c["table_start"]), hex(c["stride"]), hex(c["hp_off"]),
                        c["me_idx"], "|".join(str(h) for h in c["matched_hps"]),
                        c["n_matches"]])
    print("Wrote " + args.out)

    # Validate top candidates
    if args.validate and unique:
        print()
        print("=" * 64)
        print("Validating top 5 (checking u8 EXP/SIL):")
        print("=" * 64)
        for c in unique[:5]:
            print()
            print("  start=0x" + format(c["table_start"], "06x") +
                  " stride=0x" + format(c["stride"], "02x") +
                  " hp_off=0x" + format(c["hp_off"], "02x") +
                  " score=" + str(c["score"]) +
                  " HPs=" + str(c["matched_hps"]))

            valid_count = 0
            field_patterns = {}
            for idx, off, hp_val in c["matches"][:50]:
                record_off = c["table_start"] + idx * c["stride"]
                results = validate_record(rom, record_off, c["stride"], c["hp_off"])
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
                    print("      EXP@+0x" + format(exp_off, "02x") +
                          " SIL@+0x" + format(sil_off, "02x") +
                          " : " + str(count) + " records")

    # Dump best
    if unique and args.dump_best:
        best = unique[0]
        ts = best["table_start"]
        st = best["stride"]
        ho = best["hp_off"]
        print()
        print("=" * 64)
        print("Dumping best: start=0x" + format(ts, "06x") +
              " stride=0x" + format(st, "02x") +
              " hp_off=0x" + format(ho, "02x"))
        print("=" * 64)

        dump_name = "gba_mixed_template_dump.csv"
        with open(dump_name, "w", newline="") as f:
            w = csv.writer(f)
            nfields = st // 2
            w.writerow(["index", "offset"] +
                       ["u" + str(i*2) for i in range(nfields)] +
                       ["all_bytes", "hp_match"])
            for i in range(args.max_records):
                off = ts + i * st
                if off + st > len(rom):
                    break
                vals = [read_u16(rom, off + j*2) for j in range(nfields)]
                # Also dump raw bytes for u8 field detection
                raw_bytes = " ".join(format(read_u8(rom, off + j), "02x")
                                    for j in range(st))
                hp_val = read_u16(rom, off + ho)
                hp_match = ""
                for name, hp, exp, sil in ENEMIES:
                    if hp == hp_val:
                        hp_match = name + " (EXP=" + str(exp) + " SIL=" + str(sil) + ")"
                        break
                w.writerow([i, hex(off)] + vals + [raw_bytes, hp_match])
        print("Wrote " + dump_name)

        print()
        print("Records with known HP values:")
        for m in best["matches"][:30]:
            hp_val = m[2]
            stats_info = ""
            if hp_val in HP_TO_STATS:
                for exp, sil, name in HP_TO_STATS[hp_val]:
                    stats_info = name + " (EXP=" + str(exp) + " SIL=" + str(sil) + ")"
                    break
            print("  idx=" + str(m[0]) + "  off=0x" + format(m[1], "06x") +
                  "  HP=" + str(m[2]) + "  " + stats_info)

    return 0


if __name__ == "__main__":
    sys.exit(main())
