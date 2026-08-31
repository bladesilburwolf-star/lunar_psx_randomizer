#!/usr/bin/env python3
"""
extract_enemy_table.py – Pull the real Lunar SSSC enemy stat table from the PSX EXE

From wdtools/notes/lsss_notes (suppertails66):

  regular enemy stats
    - stored in table: 961a8 jp, 97768 us
    - 0x26-byte structs, 0x80 entries total (0x1300 bytes)
  Offsets are relative to the *decompressed* embedded executable
  minus the standard 0x800 PSX EXE header.

The main executable on Disc 1 is typically named:
  SLUS_006.28   (US Complete)
  SLPS_013.97   (JP)

It is compressed with Alfa System's "gearbolt" scheme. This script
decompresses it and slices out the 128-enemy table.

Usage:
  python3 extract_enemy_table.py SLUS_006.28
  python3 extract_enemy_table.py SLUS_006.28 -o enemy_master.bin

Then feed enemy_master.bin into enemy_randomizer.py.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

RECORD_SIZE = 0x26
NUM_ENEMIES = 0x80  # 128
TABLE_SIZE = RECORD_SIZE * NUM_ENEMIES  # 0x1300

# Offsets into decompressed EXE *after* stripping the 0x800 header
US_TABLE_OFF = 0x97768
JP_TABLE_OFF = 0x961A8

PSX_HEADER = 0x800


# ---------------------------------------------------------------------------
# Gearbolt EXE decompressor (from wdtools gearbolt_decmp.cpp)
# ---------------------------------------------------------------------------

def _get_bit(src: bytes, state: dict) -> int:
    if state["mask"] > 0x80:
        state["cmdpos"] = state["getpos"]
        state["getpos"] += 1
        state["mask"] = 0x01
        if state["cmdpos"] >= len(src):
            return 0
    bit = 1 if (src[state["cmdpos"]] & state["mask"]) else 0
    state["mask"] <<= 1
    return bit


def _get_cmd(src: bytes, state: dict) -> str:
    if _get_bit(src, state):
        return "lit"
    if _get_bit(src, state):
        return "lb1"
    return "lb2"


def gearbolt_decompress(src: bytes, max_out: int = 0x100000) -> bytes:
    dst = bytearray(max_out)
    state = {"getpos": 0, "cmdpos": 0, "mask": 0x100, "dstpos": 0}
    sz = len(src)

    while state["getpos"] < sz and state["dstpos"] < max_out:
        cmd = _get_cmd(src, state)
        if state["getpos"] >= sz and cmd != "lit":
            break

        if cmd == "lit":
            if state["getpos"] >= sz:
                break
            dst[state["dstpos"]] = src[state["getpos"]]
            state["dstpos"] += 1
            state["getpos"] += 1

        elif cmd == "lb1":
            if state["getpos"] >= sz:
                break
            lookbyte = src[state["getpos"]]
            state["getpos"] += 1
            length = ((lookbyte & 0xC0) >> 6) + 2
            lookback_pos = state["dstpos"] - (0x100 - (lookbyte | 0xC0))
            if lookback_pos < 0:
                break
            for _ in range(length):
                if state["dstpos"] >= max_out:
                    break
                dst[state["dstpos"]] = dst[lookback_pos]
                state["dstpos"] += 1
                lookback_pos += 1

        else:  # lb2
            if state["getpos"] + 1 >= sz:
                break
            next1 = src[state["getpos"]]
            next2 = src[state["getpos"] + 1]
            state["getpos"] += 2
            lookback = (next1 << 8) | next2
            length = (lookback & 0xF000) >> 12

            if length == 0:
                if state["getpos"] >= sz:
                    break
                length = src[state["getpos"]]
                state["getpos"] += 1
                if length == 0:
                    break
                length += 2
            else:
                length += 2

            lookback_pos = state["dstpos"] - (0x10000 - (lookback | 0xF000))
            if lookback_pos < 0:
                break
            for _ in range(length):
                if state["dstpos"] >= max_out:
                    break
                dst[state["dstpos"]] = dst[lookback_pos]
                state["dstpos"] += 1
                lookback_pos += 1

    return bytes(dst[: state["dstpos"]])


# ---------------------------------------------------------------------------
# Table extraction + validation
# ---------------------------------------------------------------------------

def read_enemy(data: bytes, off: int) -> dict:
    rec = data[off : off + RECORD_SIZE]
    return {
        "type": rec[0],
        "level": rec[1],
        "hp": struct.unpack_from("<H", rec, 0x02)[0],
        "atk": struct.unpack_from("<H", rec, 0x04)[0],
        "def": struct.unpack_from("<H", rec, 0x06)[0],
        "agi": struct.unpack_from("<H", rec, 0x08)[0],
        "wis": struct.unpack_from("<H", rec, 0x0A)[0],
        "mdef": struct.unpack_from("<H", rec, 0x0C)[0],
        "range": rec[0x0E],
        "num_atk": rec[0x10],
        "exp": struct.unpack_from("<H", rec, 0x1A)[0],
        "silver": struct.unpack_from("<H", rec, 0x1C)[0],
    }


def score_table(data: bytes, off: int) -> int:
    """How many of the 128 records look like plausible enemies?"""
    if off + TABLE_SIZE > len(data):
        return 0
    good = 0
    for i in range(NUM_ENEMIES):
        e = read_enemy(data, off + i * RECORD_SIZE)
        if (
            1 <= e["level"] <= 99
            and 5 <= e["hp"] <= 20000
            and 1 <= e["atk"] <= 5000
            and 0 <= e["def"] <= 2000
            and 0 <= e["exp"] <= 20000
            and 0 <= e["silver"] <= 10000
            and e["num_atk"] <= 10
        ):
            good += 1
    return good


def find_table(decomp: bytes, region: str = "us") -> tuple[int, bytes]:
    """
    Return (offset_in_decomp, table_bytes).
    Tries header-stripped and header-included offsets; picks best score.
    """
    primary = US_TABLE_OFF if region == "us" else JP_TABLE_OFF
    candidates = [
        primary,  # notes: minus 0x800 header already
        primary + PSX_HEADER,  # if notes meant absolute in full file
        primary - PSX_HEADER,
    ]
    # also try common RAM→file mappings near 0x800A71A8 style
    candidates += [0xA71A8 - 0x800, 0xA71A8, 0x800A71A8 & 0xFFFFFF]

    best_off, best_score = -1, -1
    for off in candidates:
        if off < 0 or off + TABLE_SIZE > len(decomp):
            continue
        sc = score_table(decomp, off)
        if sc > best_score:
            best_score, best_off = sc, off

    if best_score < 40:
        # brute: scan for best 0x1300 window on 2-byte alignment (slow but one-time)
        print(f"  Primary offsets scored low (best={best_score}). Scanning…")
        step = RECORD_SIZE  # aligned to record size
        for off in range(0, len(decomp) - TABLE_SIZE, step):
            sc = score_table(decomp, off)
            if sc > best_score:
                best_score, best_off = sc, off
                if sc >= 100:
                    break

    if best_off < 0 or best_score < 20:
        raise RuntimeError(
            f"Could not locate enemy table (best score {best_score}). "
            "Is this the correct SLUS/SLPS EXE?"
        )

    print(f"  Table at 0x{best_off:X}  ({best_score}/{NUM_ENEMIES} records look valid)")
    return best_off, decomp[best_off : best_off + TABLE_SIZE]


def extract(exe_path: Path, region: str = "us") -> tuple[bytes, list]:
    raw = exe_path.read_bytes()
    print(f"EXE size: {len(raw):,} bytes")

    # Gearbolt payload on SLUS_006.28 starts at 0x1000 (after PS-X header + small stub)
    best_decomp = b""
    for label, src in [("off1000", raw[0x1000:]), ("full", raw), ("skip800", raw[PSX_HEADER:])]:
        try:
            decomp = gearbolt_decompress(src)
            print(f"  gearbolt ({label}): {len(decomp):,} bytes out")
            if len(decomp) > len(best_decomp):
                best_decomp = decomp
        except Exception as ex:
            print(f"  gearbolt ({label}) failed: {ex}")

    if len(best_decomp) < 0x20000:
        # Maybe already decompressed?
        print("  Treating input as already-decompressed image")
        best_decomp = raw

    off, table = find_table(best_decomp, region=region)
    enemies = [read_enemy(table, i * RECORD_SIZE) for i in range(NUM_ENEMIES)]
    return table, enemies


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract Lunar SSSC enemy stat table from EXE")
    ap.add_argument("exe", type=Path, help="SLUS_006.28 / SLPS_013.97 (or decompressed image)")
    ap.add_argument("-o", "--output", type=Path, default=Path("enemy_master.bin"))
    ap.add_argument("--region", choices=["us", "jp"], default="us")
    ap.add_argument("--csv", type=Path, default=None, help="Also write CSV listing")
    args = ap.parse_args()

    if not args.exe.is_file():
        print(f"ERROR: {args.exe} not found", file=sys.stderr)
        print("Copy SLUS_006.28 from Disc 1 (root of the ISO) next to this script.")
        return 1

    table, enemies = extract(args.exe, region=args.region)
    args.output.write_bytes(table)
    print(f"Wrote {args.output}  ({len(table)} bytes, {NUM_ENEMIES} enemies)")

    # Preview first / last few
    print("\nFirst 8 enemies:")
    print(f"  {'#':>3} {'Lv':>3} {'HP':>6} {'ATK':>5} {'DEF':>5} {'EXP':>5} {'SIL':>5}")
    for i, e in enumerate(enemies[:8]):
        print(f"  {i:3d} {e['level']:3d} {e['hp']:6d} {e['atk']:5d} {e['def']:5d} "
              f"{e['exp']:5d} {e['silver']:5d}")
    print("  …")
    for i, e in enumerate(enemies[-3:], start=NUM_ENEMIES - 3):
        print(f"  {i:3d} {e['level']:3d} {e['hp']:6d} {e['atk']:5d} {e['def']:5d} "
              f"{e['exp']:5d} {e['silver']:5d}")

    csv_path = args.csv or args.output.with_suffix(".csv")
    with open(csv_path, "w") as f:
        f.write("index,type,level,hp,attack,defense,agility,wisdom,mdef,range,num_attacks,exp,silver\n")
        for i, e in enumerate(enemies):
            f.write(
                f"{i},{e['type']},{e['level']},{e['hp']},{e['atk']},{e['def']},"
                f"{e['agi']},{e['wis']},{e['mdef']},{e['range']},{e['num_atk']},"
                f"{e['exp']},{e['silver']}\n"
            )
    print(f"Wrote {csv_path}")
    print("\nNext:  python3 enemy_randomizer.py --cli -i enemy_master.bin --seed 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
