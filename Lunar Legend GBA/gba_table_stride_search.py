#!/usr/bin/env python3
"""
gba_table_stride_search.py — Enemy table search for Lunar Legend GBA

Memory-efficient (< 500MB RAM) and reasonably fast.

STRATEGIES:
  1. 6800 anchor: Find MagicEmperor HP=6800 as u16, check strides
  2. Multi-HP: Find positions where multiple enemy HPs appear at stride multiples
  3. Consecutive pairs: Find two known enemies back-to-back at same stride/offsets
     (most selective — requires two full stat sets at adjacent records)

Usage:
    python gba_table_stride_search.py lunar.gba --dump-best
    python gba_table_stride_search.py lunar.gba --strategy 1   # fast
    python gba_table_stride_search.py lunar.gba --strategy 3   # pair search (recommended)
"""

import struct
import sys
import csv
from collections import defaultdict

# Known enemy stats: (name, HP, EXP, SIL)
KNOWN = [
    ("Deathcap",     15,  1,  7),
    ("BurgDog",      30,  8, 15),
    ("FlyTrap",      30,  4, 10),
    ("Pirate1",      50,  7, 21),
    ("Pirate2",      60,  7, 21),
    ("Killfish",     50,  7, 46),
    ("Ammonite",     50, 12, 70),
    ("FatSnake",     40,  6, 40),
    ("Wisp",         40, 12, 56),
    ("MagicEmperor", 6800, 0, 0),
]

ITEM_START = 0x7FA000
ITEM_END   = 0x7FB000
STRIDES = list(range(4, 65))  # 4 to 64


def read_rom(path):
    with open(path, "rb") as f:
        return f.read()


def find_u16(rom, val, excl_start=None, excl_end=None):
    lo, hi = val & 0xFF, (val >> 8) & 0xFF
    return [i for i in range(len(rom) - 1)
            if rom[i] == lo and rom[i+1] == hi
            and not (excl_start and excl_start <= i < excl_end)]


def read_rec(rom, off, stride, hp_off, exp_off, sil_off):
    if off + max(hp_off+1, exp_off, sil_off) >= len(rom) or off < 0:
        return None
    hp = struct.unpack_from("<H", rom, off + hp_off)[0]
    exp = rom[off + exp_off]
    sil = rom[off + sil_off]
    return (hp, exp, sil)


def score_recs(rom, ts, stride, hp_off, exp_off, sil_off, n=40):
    matched = []
    for i in range(n):
        off = ts + i * stride
        r = read_rec(rom, off, stride, hp_off, exp_off, sil_off)
        if r is None:
            break
        for name, e_hp, e_exp, e_sil in KNOWN:
            if r == (e_hp, e_exp, e_sil):
                matched.append((i, name, r[0], r[1], r[2], off))
                break
    return len(matched), matched


def dump_table(rom, ts, stride, hp_off, exp_off, sil_off, n=50):
    print(f"\n{'='*80}")
    print(f"Table: start=0x{ts:06X} stride={stride}")
    print(f"HP@+{hp_off}(u16) EXP@+{exp_off}(u8) SIL@+{sil_off}(u8)")
    print(f"{'='*80}")
    print(f"{'Rec':>3} {'Offset':>10} {'HP':>6} {'EXP':>4} {'SIL':>4}  {'Raw bytes':<48}  Match")
    print("-" * 100)
    for i in range(n):
        off = ts + i * stride
        if off + stride > len(rom) or off < 0:
            break
        r = read_rec(rom, off, stride, hp_off, exp_off, sil_off)
        if r is None:
            break
        hp, exp, sil = r
        raw = " ".join(f"{rom[off+j]:02X}" for j in range(min(stride, 24)))
        m = ""
        for name, e_hp, e_exp, e_sil in KNOWN:
            if (hp, exp, sil) == (e_hp, e_exp, e_sil):
                m = name
        print(f"{i:>3} 0x{off:08X} {hp:>6} {exp:>4} {sil:>4}  {raw}  {m}")


# ===== Strategy 1: 6800 anchor =====
def s1_6800(rom):
    print("\n" + "="*70)
    print("STRATEGY 1: 6800 (MagicEmperor HP) anchor")
    print("="*70)
    occ = find_u16(rom, 6800, ITEM_START, ITEM_END)
    print(f"  6800 found at {len(occ)} positions (excl. item table)")
    for o in occ[:20]:
        print(f"    0x{o:06X}")

    results, seen = [], set()
    for pos in occ:
        for stride in STRIDES:
            for hp_off in range(stride - 1):
                for rec_n in range(31):
                    ts = pos - hp_off - rec_n * stride
                    if ts < 0:
                        break
                    # Quick check: another known HP at stride multiple
                    found = False
                    for _, e_hp, _, _ in KNOWN:
                        for cr in range(31):
                            co = ts + cr * stride + hp_off
                            if co + 1 < len(rom) and co != pos:
                                if struct.unpack_from("<H", rom, co)[0] == e_hp:
                                    found = True
                                    break
                        if found:
                            break
                    if not found:
                        continue
                    # Full check with all exp/sil offsets
                    for exp_off in range(stride):
                        if exp_off in (hp_off, hp_off+1):
                            continue
                        for sil_off in range(stride):
                            if sil_off in (hp_off, hp_off+1, exp_off):
                                continue
                            sc, m = score_recs(rom, ts, stride, hp_off, exp_off, sil_off)
                            if sc >= 3:
                                key = (ts, stride, hp_off, exp_off, sil_off)
                                if key not in seen:
                                    seen.add(key)
                                    results.append((sc, ts, stride, hp_off, exp_off, sil_off, m))
    results.sort(key=lambda x: -x[0])
    _print_results("Strategy 1", results)
    return results


# ===== Strategy 2: Multi-HP scan =====
def s2_multi_hp(rom):
    print("\n" + "="*70)
    print("STRATEGY 2: Multi-HP stride scan")
    print("="*70)
    hp_pos = {}
    for _, hp, _, _ in KNOWN:
        if hp not in hp_pos:
            hp_pos[hp] = find_u16(rom, hp, ITEM_START, ITEM_END)
    for hp in sorted(hp_pos):
        print(f"  HP={hp}: {len(hp_pos[hp])} positions")

    results, seen = [], set()
    sorted_hps = sorted(hp_pos.keys(), key=lambda h: len(hp_pos[h]))

    for stride in STRIDES:
        # Use rarest HP as anchor
        for anchor_hp in sorted_hps[:3]:
            for pos in hp_pos[anchor_hp]:
                # Check if other HPs appear at stride multiples
                matches = [(0, anchor_hp)]
                for other_hp in hp_pos:
                    if other_hp == anchor_hp:
                        continue
                    for op in hp_pos[other_hp]:
                        diff = op - pos
                        if diff > 0 and diff % stride == 0 and diff // stride <= 30:
                            matches.append((diff // stride, other_hp))
                            break
                if len(matches) < 3:
                    continue
                for hp_off in range(stride - 1):
                    ts = pos - hp_off
                    if ts < 0:
                        continue
                    for exp_off in range(stride):
                        if exp_off in (hp_off, hp_off+1):
                            continue
                        for sil_off in range(stride):
                            if sil_off in (hp_off, hp_off+1, exp_off):
                                continue
                            sc, m = score_recs(rom, ts, stride, hp_off, exp_off, sil_off)
                            if sc >= 3:
                                key = (ts, stride, hp_off, exp_off, sil_off)
                                if key not in seen:
                                    seen.add(key)
                                    results.append((sc, ts, stride, hp_off, exp_off, sil_off, m))
        if stride % 16 == 0:
            print(f"  stride={stride}: {len(results)} candidates")
    results.sort(key=lambda x: -x[0])
    _print_results("Strategy 2", results)
    return results


# ===== Strategy 3: Consecutive pairs =====
def s3_pairs(rom):
    """
    Search for two known enemies appearing in consecutive records.
    For each pair (A, B) of known enemies, search for positions where:
      Record N:   HP=A_hp(u16) EXP=A_exp(u8) SIL=A_sil(u8)
      Record N+1: HP=B_hp(u16) EXP=B_exp(u8) SIL=B_sil(u8)
    at the same (hp_off, exp_off, sil_off) within stride.

    This is VERY selective because it requires 6 values to match simultaneously.
    """
    print("\n" + "="*70)
    print("STRATEGY 3: Consecutive enemy pair search")
    print("="*70)

    # Generate all ordered pairs of known enemies (excluding MagicEmperor as
    # first record since its HP=6800 is rare — handle separately)
    pairs = []
    for a in KNOWN:
        for b in KNOWN:
            if a[0] == b[0]:
                continue
            # Skip pairs that are too similar (HP and EXP both same)
            if a[1] == b[1] and a[2] == b[2]:
                continue  # e.g., Pirate1->Pirate2 (same EXP/SIL, different HP — actually OK)
            pairs.append((a, b))

    # Also add Pirate1->Pirate2 and Pirate2->Pirate1 (same EXP/SIL, different HP)
    for a in KNOWN:
        for b in KNOWN:
            if a[0] != b[0] and a[1] == b[1] and a[2] == b[2] and a[1] != b[1]:
                if (a, b) not in pairs:
                    pairs.append((a, b))

    print(f"  Testing {len(pairs)} enemy pairs across {len(STRIDES)} strides")

    # Pre-index all HP u16 positions (one-time scan, not per-pair)
    hp_index = {}
    for _, hp, _, _ in KNOWN:
        if hp not in hp_index:
            hp_index[hp] = find_u16(rom, hp, ITEM_START, ITEM_END)
    for hp in sorted(hp_index):
        print(f"    HP={hp}: {len(hp_index[hp])} positions")

    results, seen = [], set()

    for stride in STRIDES:
        for (a_name, a_hp, a_exp, a_sil), (b_name, b_hp, b_exp, b_sil) in pairs:
            # Use pre-indexed positions
            a_hp_pos = hp_index.get(a_hp, [])

            for hp_pos in a_hp_pos:
                for hp_off in range(stride - 1):
                    rec_a = hp_pos - hp_off
                    if rec_a < 0:
                        continue
                    rec_b = rec_a + stride
                    if rec_b + stride > len(rom):
                        continue

                    # Check B's HP at rec_b + hp_off
                    b_hp_val = struct.unpack_from("<H", rom, rec_b + hp_off)[0]
                    if b_hp_val != b_hp:
                        continue

                    # A's HP matches, B's HP matches at +stride!
                    # Now check EXP and SIL at all possible offsets
                    for exp_off in range(stride):
                        if exp_off in (hp_off, hp_off + 1):
                            continue
                        # Check A's EXP
                        if rom[rec_a + exp_off] != a_exp:
                            continue
                        # Check B's EXP
                        if rom[rec_b + exp_off] != b_exp:
                            continue

                        for sil_off in range(stride):
                            if sil_off in (hp_off, hp_off + 1, exp_off):
                                continue
                            # Check A's SIL
                            if rom[rec_a + sil_off] != a_sil:
                                continue
                            # Check B's SIL
                            if rom[rec_b + sil_off] != b_sil:
                                continue

                            # FULL MATCH! Both A and B at consecutive records!
                            # Now check the full table from this position
                            sc, m = score_recs(rom, rec_a, stride, hp_off, exp_off, sil_off)
                            if sc >= 2:  # At least the pair matches
                                key = (rec_a, stride, hp_off, exp_off, sil_off)
                                if key not in seen:
                                    seen.add(key)
                                    results.append((sc, rec_a, stride, hp_off, exp_off, sil_off, m,
                                                    f"{a_name}->{b_name}"))

        if stride % 8 == 0:
            print(f"  stride={stride}: {len(results)} candidates")

    results.sort(key=lambda x: -x[0])
    _print_results("Strategy 3 (pairs)", results)
    return results


def _print_results(name, results):
    print(f"\n  {name}: {len(results)} candidates with matches")
    for i, r in enumerate(results[:30]):
        sc, ts, stride, hp_off, exp_off, sil_off = r[0], r[1], r[2], r[3], r[4], r[5]
        matched = r[6]
        extra = r[7] if len(r) > 7 else ""
        print(f"\n  #{i+1}: score={sc}, start=0x{ts:06X}, stride={stride} {extra}")
        print(f"    HP@+{hp_off}(u16) EXP@+{exp_off}(u8) SIL@+{sil_off}(u8)")
        for idx, nm, hp, exp, sil, off in matched:
            print(f"    Rec{idx} @0x{off:06X}: {nm} (HP={hp},EXP={exp},SIL={sil})")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <rom> [--dump-best] [--strategy N]")
        print(f"  Strategy: 1=6800 anchor, 2=multi-HP, 3=pairs, 0=all")
        sys.exit(1)

    rom_path = sys.argv[1]
    dump_best = "--dump-best" in sys.argv
    strategy = 0
    if "--strategy" in sys.argv:
        strategy = int(sys.argv[sys.argv.index("--strategy") + 1])

    rom = read_rom(rom_path)
    print(f"ROM: {len(rom)} bytes (0x{len(rom):X})")
    print(f"Excluding item table: 0x{ITEM_START:06X}-0x{ITEM_END:06X}")

    all_res = []
    if strategy in (0, 1):
        all_res.extend(s1_6800(rom))
    if strategy in (0, 2):
        all_res.extend(s2_multi_hp(rom))
    if strategy in (0, 3):
        all_res.extend(s3_pairs(rom))

    # Deduplicate
    seen = set()
    unique = []
    for r in all_res:
        key = (r[1], r[2], r[3], r[4], r[5])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: -x[0])

    print(f"\n{'='*70}")
    print(f"FINAL: {len(unique)} unique candidates")
    print(f"{'='*70}")
    for i, r in enumerate(unique[:20]):
        sc, ts, stride, hp_off, exp_off, sil_off = r[0], r[1], r[2], r[3], r[4], r[5]
        matched = r[6]
        extra = r[7] if len(r) > 7 else ""
        print(f"\n  #{i+1}: score={sc} start=0x{ts:06X} stride={stride} {extra}")
        print(f"    HP@+{hp_off} EXP@+{exp_off} SIL@+{sil_off}")
        for idx, nm, hp, exp, sil, off in matched:
            print(f"    Rec{idx} @0x{off:06X}: {nm} (HP={hp},E={exp},S={sil})")

    with open("gba_stride_search_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank","score","table_start","stride","hp_off","exp_off","sil_off","matched"])
        for i, r in enumerate(unique[:200]):
            mstr = "|".join(f"{n}@{r2}(HP={h},E={e},S={s})" for r2,n,h,e,s,o in r[6])
            w.writerow([i+1, r[0], f"0x{r[1]:06X}", r[2], r[3], r[4], r[5], mstr])
    print(f"\nSaved to gba_stride_search_results.csv")

    if dump_best and unique:
        for i, r in enumerate(unique[:5]):
            print(f"\n=== Candidate {i+1} ===")
            dump_table(rom, r[1], r[2], r[3], r[4], r[5])
        best = unique[0]
        with open("gba_stride_best_dump.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["record","offset","hp","exp","sil","raw_bytes","match"])
            ts, stride, hp_off, exp_off, sil_off = best[1], best[2], best[3], best[4], best[5]
            for i in range(60):
                off = ts + i * stride
                if off + stride > len(rom):
                    break
                r2 = read_rec(rom, off, stride, hp_off, exp_off, sil_off)
                if r2 is None:
                    break
                hp, exp, sil = r2
                raw = " ".join(f"{rom[off+j]:02X}" for j in range(min(stride, 32)))
                m = ""
                for name, e_hp, e_exp, e_sil in KNOWN:
                    if (hp, exp, sil) == (e_hp, e_exp, e_sil):
                        m = name
                w.writerow([i, f"0x{off:08X}", hp, exp, sil, raw, m])
        print(f"Best dump saved to gba_stride_best_dump.csv")


if __name__ == "__main__":
    main()
