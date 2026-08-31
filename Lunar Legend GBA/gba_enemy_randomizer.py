#!/usr/bin/env python3
"""
gba_enemy_randomizer.py – Lunar Legend (GBA) enemy stat randomizer

Patches an enemy master table in the USA ALNE ROM. The exact table offset
and record stride are determined by gba_scan_enemy_table.py — run that first
and pass the confirmed offset/stride here.

The record layout is expected to contain consecutive u16 stat fields
(HP, MP, ATK, DEF, AGI, MEN, RES, ... EXP, SILVER) mirroring the
character stat structure confirmed from cheat-code analysis:
  +0x00 HP u16, +0x02 MP u16, +0x04..+0x0C five stats u16,
  with EXP and SILVER at higher offsets.

Since the GBA enemy layout is still being verified, this tool is
*configurable*: you tell it the offset, stride, and which u16 fields to
randomize (by byte offset within the record). It preserves everything else
byte-for-byte.

Mirrors PSX enemy_randomizer.py / EnemyTable.java conventions:
  - scale stats by a random factor within [min, max] per-stat
  - skip empty/sentinel records (HP <= 0)
  - optional shuffle of stat-packs among similar-level enemies
  - seed-based for reproducibility

Usage (CLI):
  python3 gba_enemy_randomizer.py --cli --rom lunar.gba --offset 0x7FA000 \
      --stride 0x20 --count 128 --seed 42 \
      --fields hp:0x00 atk:0x04 def:0x06 agi:0x08 men:0x0A res:0x0C exp:0x1A silver:0x1C

Usage (GUI):
  python3 gba_enemy_randomizer.py
"""

from __future__ import annotations

import argparse
import csv
import random
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GBA_ROM_SIZE = 8 * 1024 * 1024


def _clamp_u16(v: int) -> int:
    if v < 0:
        return 0
    if v > 0xFFFF:
        return 0xFFFF
    return v


def read_u16(rom: bytes, off: int) -> int:
    return struct.unpack_from("<H", rom, off)[0]


def write_u16(buf: bytearray, off: int, v: int) -> None:
    struct.pack_into("<H", buf, off, _clamp_u16(v))


@dataclass
class FieldSpec:
    name: str
    offset: int
    min_mult: float = 0.75
    max_mult: float = 1.40
    clamp_max: int = 0xFFFF

    @staticmethod
    def parse(spec_str: str) -> "FieldSpec":
        parts = spec_str.split(":")
        if len(parts) < 2:
            raise ValueError(f"bad field spec: {spec_str}")
        name = parts[0]
        offset = int(parts[1], 0)
        fs = FieldSpec(name=name, offset=offset)
        if len(parts) >= 4:
            fs.min_mult = float(parts[2])
            fs.max_mult = float(parts[3])
        return fs


DEFAULT_FIELDS = "hp:0x00 atk:0x04 def:0x06 agi:0x08 men:0x0A res:0x0C exp:0x1A silver:0x1C"


def parse_fields(spec: str) -> List[FieldSpec]:
    return [FieldSpec.parse(s) for s in spec.split()]


@dataclass
class EnemyRecord:
    index: int
    offset: int
    raw: bytes
    stride: int

    def get_u16(self, foff: int) -> int:
        return read_u16(self.raw, foff)

    def set_u16(self, buf: bytearray, foff: int, v: int) -> None:
        write_u16(buf, self.offset + foff, v)

    def is_active(self, hp_offset: int) -> bool:
        return self.get_u16(hp_offset) >= 1


def load_records(rom: bytes, table_offset: int, stride: int, count: int) -> List[EnemyRecord]:
    recs: List[EnemyRecord] = []
    for i in range(count):
        off = table_offset + i * stride
        if off + stride > len(rom):
            break
        recs.append(EnemyRecord(
            index=i, offset=off,
            raw=rom[off:off + stride], stride=stride,
        ))
    return recs


def randomize(rom: bytes, table_offset: int, stride: int, count: int,
              fields: List[FieldSpec], seed: Optional[int],
              shuffle_similar: bool = False, level_band: int = 3,
              level_offset: Optional[int] = None) -> Tuple[bytearray, List[dict]]:
    rng = random.Random(seed)
    out = bytearray(rom)
    recs = load_records(rom, table_offset, stride, count)
    log: List[dict] = []

    new_values: Dict[int, Dict[int, int]] = {}
    for rec in recs:
        if not rec.is_active(fields[0].offset):
            new_values[rec.index] = {}
            continue
        changes: Dict[int, int] = {}
        for fs in fields:
            old = rec.get_u16(fs.offset)
            if old <= 0:
                changes[fs.offset] = old
                continue
            factor = rng.uniform(fs.min_mult, fs.max_mult)
            new = max(1, int(round(old * factor)))
            new = min(new, fs.clamp_max)
            changes[fs.offset] = new
        new_values[rec.index] = changes
        log.append({"index": rec.index, "offset": hex(rec.offset),
                    **{fs.name + "_old": rec.get_u16(fs.offset) for fs in fields},
                    **{fs.name + "_new": changes[fs.offset] for fs in fields}})

    if shuffle_similar and level_offset is not None and len(recs) > 1:
        bands: Dict[int, List[int]] = {}
        for rec in recs:
            if not rec.is_active(fields[0].offset):
                continue
            lvl = rec.get_u16(level_offset)
            key = lvl // max(1, level_band)
            bands.setdefault(key, []).append(rec.index)
        for idxs in bands.values():
            if len(idxs) < 2:
                continue
            packs = []
            for i in idxs:
                packs.append({fo: new_values[i].get(fo, 0) for fo in
                              [fs.offset for fs in fields]})
            random.Random(rng.random()).shuffle(packs)
            for j, i in enumerate(idxs):
                for k, fo in enumerate([fs.offset for fs in fields]):
                    new_values[i][fo] = packs[j][fo]

    for rec in recs:
        changes = new_values.get(rec.index, {})
        for fo, v in changes.items():
            write_u16(out, rec.offset + fo, v)

    return out, log


def run_cli(args) -> int:
    if not args.rom:
        print("ERROR: --rom is required")
        return 1
    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1
    rom = rom_path.read_bytes()
    if len(rom) < GBA_ROM_SIZE:
        print(f"WARNING: ROM is only {len(rom)} bytes")

    fields = parse_fields(args.fields)
    seed = args.seed if args.seed is not None else random.randint(1, 999999)

    patched, log = randomize(
        rom, args.offset, args.stride, args.count,
        fields, seed, args.shuffle, args.band, args.level_offset,
    )

    out_rom = Path(args.out) if args.out else rom_path.with_name(rom_path.stem + "_enemy_rand.gba")
    out_rom.write_bytes(patched)
    print(f"Seed {seed} | {args.count} records @ {hex(args.offset)} stride {hex(args.stride)}")
    print(f"  fields: {[(f.name, hex(f.offset)) for f in fields]}")
    print(f"  active records modified: {len(log)}")
    print(f"Wrote randomized ROM -> {out_rom}")

    csv_path = out_rom.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        if log:
            w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
            w.writeheader()
            w.writerows(log)
    print(f"Wrote report CSV   -> {csv_path}")
    return 0


def run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("tkinter not available – use --cli mode")
        return 1

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Lunar Legend (GBA) — Enemy Randomizer")
            self.geometry("860x700")
            self.rom: Optional[bytes] = None
            self.log: List[dict] = []
            self._build()

        def _build(self):
            top = ttk.Frame(self, padding=8)
            top.pack(fill=tk.X)
            ttk.Button(top, text="Load ROM…", command=self.load_rom).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save ROM…", command=self.save_rom).pack(side=tk.LEFT, padx=2)

            cfg = ttk.LabelFrame(self, text="Table parameters", padding=8)
            cfg.pack(fill=tk.X, padx=8, pady=4)
            self.off_var = tk.StringVar(value="0x7FA000")
            self.stride_var = tk.StringVar(value="0x20")
            self.count_var = tk.StringVar(value="128")
            self.fields_var = tk.StringVar(value=DEFAULT_FIELDS)
            for label, var in [("Table offset (hex)", self.off_var),
                              ("Record stride (hex)", self.stride_var),
                              ("Record count", self.count_var),
                              ("Fields (name:offset …)", self.fields_var)]:
                row = ttk.Frame(cfg)
                row.pack(fill=tk.X, pady=2)
                ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
                ttk.Entry(row, textvariable=var, width=60).pack(side=tk.LEFT, padx=4)

            rng = ttk.LabelFrame(self, text="Randomization", padding=8)
            rng.pack(fill=tk.X, padx=8, pady=4)
            self.seed_var = tk.StringVar(value=str(random.randint(1, 999999)))
            self.shuffle_var = tk.BooleanVar(value=False)
            ttk.Label(rng, text="Seed:").pack(side=tk.LEFT)
            ttk.Entry(rng, textvariable=self.seed_var, width=12).pack(side=tk.LEFT, padx=4)
            ttk.Checkbutton(rng, text="Shuffle similar-level packs",
                            variable=self.shuffle_var).pack(side=tk.LEFT, padx=8)
            ttk.Button(rng, text="Randomize!", command=self.do_randomize).pack(side=tk.LEFT, padx=8)

            cols = ("idx", "offset", "hp_old", "hp_new", "atk_old", "atk_new")
            self.tree = ttk.Treeview(self, columns=cols, show="headings", height=24)
            for c, w in [("idx", 50), ("offset", 80), ("hp_old", 70), ("hp_new", 70),
                         ("atk_old", 70), ("atk_new", 70)]:
                self.tree.heading(c, text=c.upper())
                self.tree.column(c, width=w, anchor=tk.E)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            self.status = ttk.Label(self, text="Load a USA lunar.gba ROM to begin")
            self.status.pack(fill=tk.X, padx=8, pady=4)

        def load_rom(self):
            p = filedialog.askopenfilename(
                title="Lunar Legend USA ROM",
                filetypes=[("GBA ROM", "*.gba"), ("All", "*.*")])
            if not p:
                return
            try:
                self.rom = Path(p).read_bytes()
                self.status.configure(text=f"Loaded {p} ({len(self.rom)} bytes)")
            except Exception as ex:
                messagebox.showerror("Load error", str(ex))

        def save_rom(self):
            if not self.rom or not self.log:
                messagebox.showwarning("No data", "Load ROM and randomize first")
                return
            p = filedialog.asksaveasfilename(
                title="Save randomized ROM", defaultextension=".gba",
                filetypes=[("GBA ROM", "*.gba"), ("All", "*.*")])
            if not p:
                return
            Path(p).write_bytes(self.rom)
            self.status.configure(text=f"Saved {p}")

        def do_randomize(self):
            if not self.rom:
                messagebox.showwarning("No data", "Load a ROM first")
                return
            try:
                off = int(self.off_var.get(), 0)
                stride = int(self.stride_var.get(), 0)
                count = int(self.count_var.get())
                fields = parse_fields(self.fields_var.get())
                seed = int(self.seed_var.get())
            except ValueError as e:
                messagebox.showerror("Parse error", str(e))
                return
            patched, log = randomize(
                self.rom, off, stride, count, fields, seed,
                self.shuffle_var.get())
            self.rom = patched
            self.log = log
            self.tree.delete(*self.tree.get_children())
            for row in log[:200]:
                self.tree.insert("", tk.END, values=(
                    row["index"], row["offset"],
                    row.get("hp_old", ""), row.get("hp_new", ""),
                    row.get("atk_old", ""), row.get("atk_new", "")))
            self.status.configure(text=f"Randomized seed {seed} – {len(log)} records modified")

    app = App()
    app.mainloop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Lunar Legend (GBA) enemy stat randomizer")
    ap.add_argument("--cli", action="store_true")
    ap.add_argument("--rom", "-r")
    ap.add_argument("--out", "-o")
    ap.add_argument("--offset", type=lambda x: int(x, 0), default=0x7FA000,
                    help="ROM offset of enemy table (hex)")
    ap.add_argument("--stride", type=lambda x: int(x, 0), default=0x20,
                    help="Record stride in bytes (hex)")
    ap.add_argument("--count", type=int, default=128)
    ap.add_argument("--fields", default=DEFAULT_FIELDS,
                    help="Field specs: name:offset[:min:max] separated by spaces")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--band", type=int, default=3)
    ap.add_argument("--level-offset", type=lambda x: int(x, 0), default=None,
                    help="Byte offset of level field within record (for shuffle banding)")
    args = ap.parse_args()

    if args.cli or not sys.stdout.isatty():
        return run_cli(args)
    try:
        import tkinter  # noqa: F401
        return run_gui()
    except ImportError:
        return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
