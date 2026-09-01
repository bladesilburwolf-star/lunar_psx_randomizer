#!/usr/bin/env python3
"""
enemy_randomizer.py – Lunar SSSC enemy stat randomizer

Works on the confirmed 38-byte (0x26) enemy record format from lsss_stats:

  0x00  type (1)
  0x01  level (1)
  0x02  HP (2 LE)
  0x04  Attack (2)
  0x06  Defense (2)
  0x08  Agility (2)
  0x0A  Wisdom (2)
  0x0C  Magic Defense (2)
  0x0E  Range (1)
  0x0F  Atk2 (1)
  0x10  NumAttacks (1)
  0x11–0x19  misc (9)
  0x1A  EXP (2)
  0x1C  Silver (2)
  0x1E–0x25  extra (8)

Until the master table is located on disc, this tool:
  • Ships a sample table (early Disc 1 enemies from published guides)
  • Lets you set min/max multipliers per stat
  • Optionally shuffles stats among similar-level enemies
  • Saves a modified binary table + a human-readable report

Usage:
  python3 enemy_randomizer.py                  # GUI
  python3 enemy_randomizer.py --cli --seed 42  # headless test
"""

from __future__ import annotations

import argparse
import csv
import random
import struct
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import List, Optional, Tuple

RECORD_SIZE = 0x26  # 38

# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

@dataclass
class Enemy:
    type_id: int = 0
    level: int = 1
    hp: int = 10
    attack: int = 1
    defense: int = 0
    agility: int = 0
    wisdom: int = 0
    magic_defense: int = 0
    range: int = 1
    atk2: int = 0
    num_attacks: int = 1
    misc: bytes = b"\x00" * 9  # 0x11–0x19
    exp: int = 1
    silver: int = 1
    extra: bytes = b"\x00" * 8  # 0x1E–0x25
    name: str = ""  # optional label (not in binary)

    def pack(self) -> bytes:
        buf = bytearray(RECORD_SIZE)
        buf[0] = self.type_id & 0xFF
        buf[1] = self.level & 0xFF
        struct.pack_into("<H", buf, 0x02, max(0, min(0xFFFF, self.hp)))
        struct.pack_into("<H", buf, 0x04, max(0, min(0xFFFF, self.attack)))
        struct.pack_into("<H", buf, 0x06, max(0, min(0xFFFF, self.defense)))
        struct.pack_into("<H", buf, 0x08, max(0, min(0xFFFF, self.agility)))
        struct.pack_into("<H", buf, 0x0A, max(0, min(0xFFFF, self.wisdom)))
        struct.pack_into("<H", buf, 0x0C, max(0, min(0xFFFF, self.magic_defense)))
        buf[0x0E] = self.range & 0xFF
        buf[0x0F] = self.atk2 & 0xFF
        buf[0x10] = self.num_attacks & 0xFF
        m = self.misc[:9].ljust(9, b"\x00")
        buf[0x11:0x1A] = m
        struct.pack_into("<H", buf, 0x1A, max(0, min(0xFFFF, self.exp)))
        struct.pack_into("<H", buf, 0x1C, max(0, min(0xFFFF, self.silver)))
        e = self.extra[:8].ljust(8, b"\x00")
        buf[0x1E:0x26] = e
        return bytes(buf)

    @classmethod
    def unpack(cls, data: bytes, name: str = "") -> "Enemy":
        if len(data) < RECORD_SIZE:
            raise ValueError("record too short")
        return cls(
            type_id=data[0],
            level=data[1],
            hp=struct.unpack_from("<H", data, 0x02)[0],
            attack=struct.unpack_from("<H", data, 0x04)[0],
            defense=struct.unpack_from("<H", data, 0x06)[0],
            agility=struct.unpack_from("<H", data, 0x08)[0],
            wisdom=struct.unpack_from("<H", data, 0x0A)[0],
            magic_defense=struct.unpack_from("<H", data, 0x0C)[0],
            range=data[0x0E],
            atk2=data[0x0F],
            num_attacks=data[0x10],
            misc=data[0x11:0x1A],
            exp=struct.unpack_from("<H", data, 0x1A)[0],
            silver=struct.unpack_from("<H", data, 0x1C)[0],
            extra=data[0x1E:0x26],
            name=name,
        )


def load_table(path: Path) -> List[Enemy]:
    data = path.read_bytes()
    if len(data) % RECORD_SIZE != 0:
        raise ValueError(
            f"{path}: size {len(data)} is not a multiple of {RECORD_SIZE}"
        )
    enemies = []
    for i in range(0, len(data), RECORD_SIZE):
        enemies.append(Enemy.unpack(data[i : i + RECORD_SIZE], name=f"Enemy_{i // RECORD_SIZE}"))
    return enemies


def save_table(path: Path, enemies: List[Enemy]) -> None:
    blob = b"".join(e.pack() for e in enemies)
    path.write_bytes(blob)


# ---------------------------------------------------------------------------
# Sample early Disc-1 table (from published guides – approximate)
# Used so the tool is testable before the real master table is located.
# ---------------------------------------------------------------------------

SAMPLE_ENEMIES: List[Tuple[str, int, int, int, int, int, int, int]] = [
    # name, level, HP, ATK, DEF, EXP, Silver, type_id
    ("Slime", 1, 12, 8, 2, 2, 4, 1),
    ("Mutant Fly", 2, 18, 12, 3, 3, 6, 2),
    ("Synapse Guard", 3, 28, 18, 5, 5, 10, 3),
    ("Albino Baboon", 4, 47, 63, 8, 7, 22, 4),
    ("Killer Fly", 3, 22, 15, 4, 4, 8, 5),
    ("Killer Wasp", 4, 30, 20, 6, 6, 12, 6),
    ("Mantle Rapper", 5, 40, 28, 8, 8, 15, 7),
    ("Mutant Ant", 5, 35, 25, 10, 7, 14, 8),
    ("Ammonia", 8, 43, 82, 32, 14, 63, 9),
    ("Antorion", 10, 40, 113, 50, 8, 61, 10),
    ("Barrel Snake", 6, 63, 45, 12, 10, 20, 11),
    ("Goblin", 2, 20, 14, 4, 3, 7, 12),
    ("Hobgoblin", 5, 55, 35, 12, 9, 18, 13),
    ("Sewer Rat", 7, 38, 40, 15, 11, 25, 14),
    ("Saline Slimer (base)", 12, 80, 50, 20, 40, 50, 15),
]


def build_sample_table() -> List[Enemy]:
    out: List[Enemy] = []
    for name, lvl, hp, atk, df, exp, sil, tid in SAMPLE_ENEMIES:
        out.append(
            Enemy(
                type_id=tid,
                level=lvl,
                hp=hp,
                attack=atk,
                defense=df,
                agility=max(1, lvl * 3),
                wisdom=max(1, lvl * 2),
                magic_defense=max(0, df // 2),
                range=1,
                atk2=0,
                num_attacks=1,
                exp=exp,
                silver=sil,
                name=name,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Randomization
# ---------------------------------------------------------------------------

@dataclass
class StatRanges:
    """Multipliers applied to original values. 1.0 = unchanged."""
    hp_min: float = 0.75
    hp_max: float = 1.40
    atk_min: float = 0.80
    atk_max: float = 1.35
    def_min: float = 0.75
    def_max: float = 1.40
    exp_min: float = 0.70
    exp_max: float = 1.50
    silver_min: float = 0.70
    silver_max: float = 1.50
    agi_min: float = 0.80
    agi_max: float = 1.30
    wis_min: float = 0.75
    wis_max: float = 1.40
    mdef_min: float = 0.75
    mdef_max: float = 1.40
    # Keep level / type / misc intact by default


def _scale(rng: random.Random, value: int, lo: float, hi: float) -> int:
    if value <= 0:
        return value
    factor = rng.uniform(lo, hi)
    return max(1, int(round(value * factor)))


def randomize_enemies(
    enemies: List[Enemy],
    ranges: StatRanges,
    seed: int,
    shuffle_similar: bool = False,
    level_band: int = 3,
    shuffle_identity: bool = False,
) -> List[Enemy]:
    """Return a new list with scaled (and optionally shuffled) stats.

    shuffle_identity: permutes ENTIRE 38-byte records across table slots
    (type, level, every stat -- the full monster definition), rather than
    just swapping individual stat values among same-level enemies. This is
    the closest thing to "shuffle which monster appears where" achievable
    without a confirmed formation/encounter table (see FORMATION_NOTES.md
    for the current state of that search). Whether this actually changes
    which sprite/name shows up in a given fight depends on whether the
    game's formation system references monsters by this table's index or
    by some other key -- that part is NOT yet confirmed. What IS
    guaranteed: every monster definition in the game still exists exactly
    once, just reassigned to a different slot, so nothing is duplicated or
    lost.
    """
    rng = random.Random(seed)
    result = [Enemy.unpack(e.pack(), name=e.name) for e in enemies]  # deep copy

    if shuffle_identity:
        active_idxs = [i for i, e in enumerate(result) if e.hp >= 5 and e.level >= 1]
        records = [result[i].pack() for i in active_idxs]
        rng.shuffle(records)
        for i, rec in zip(active_idxs, records):
            name = result[i].name  # keep the slot's own label, not the moved-in one
            result[i] = Enemy.unpack(rec, name=name)

    # 1) Scale
    for e in result:
        e.hp = _scale(rng, e.hp, ranges.hp_min, ranges.hp_max)
        e.attack = _scale(rng, e.attack, ranges.atk_min, ranges.atk_max)
        e.defense = _scale(rng, e.defense, ranges.def_min, ranges.def_max)
        e.exp = _scale(rng, e.exp, ranges.exp_min, ranges.exp_max)
        e.silver = _scale(rng, e.silver, ranges.silver_min, ranges.silver_max)
        e.agility = _scale(rng, e.agility, ranges.agi_min, ranges.agi_max)
        e.wisdom = _scale(rng, e.wisdom, ranges.wis_min, ranges.wis_max)
        e.magic_defense = _scale(rng, e.magic_defense, ranges.mdef_min, ranges.mdef_max)

    # 2) Optional: shuffle combat stats among enemies of similar level
    if shuffle_similar and len(result) > 1:
        # group by level band
        bands: dict = {}
        for i, e in enumerate(result):
            key = e.level // max(1, level_band)
            bands.setdefault(key, []).append(i)
        for idxs in bands.values():
            if len(idxs) < 2:
                continue
            # collect packs of (hp, atk, def, exp, silver, agi, wis, mdef)
            packs = [
                (result[i].hp, result[i].attack, result[i].defense,
                 result[i].exp, result[i].silver, result[i].agility,
                 result[i].wisdom, result[i].magic_defense)
                for i in idxs
            ]
            rng.shuffle(packs)
            for i, p in zip(idxs, packs):
                result[i].hp, result[i].attack, result[i].defense, \
                    result[i].exp, result[i].silver, result[i].agility, \
                    result[i].wisdom, result[i].magic_defense = p

    return result


def report(original: List[Enemy], modified: List[Enemy]) -> str:
    lines = []
    lines.append(f"{'Name':<22} {'Lv':>3}  {'HP':>8}  {'ATK':>8}  {'DEF':>8}  "
                  f"{'AGI':>8}  {'WIS':>8}  {'MDEF':>8}  {'EXP':>8}  {'SIL':>8}")
    lines.append("-" * 108)
    for o, m in zip(original, modified):
        def fmt(a, b):
            if a == b:
                return f"{b:8d}"
            return f"{a}->{b}"
        lines.append(
            f"{(m.name or o.name):<22} {m.level:3d}  "
            f"{fmt(o.hp, m.hp):>8}  {fmt(o.attack, m.attack):>8}  "
            f"{fmt(o.defense, m.defense):>8}  "
            f"{fmt(o.agility, m.agility):>8}  {fmt(o.wisdom, m.wisdom):>8}  "
            f"{fmt(o.magic_defense, m.magic_defense):>8}  "
            f"{fmt(o.exp, m.exp):>8}  "
            f"{fmt(o.silver, m.silver):>8}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_cli(args: argparse.Namespace) -> int:
    if args.input:
        enemies = load_table(Path(args.input))
        print(f"Loaded {len(enemies)} enemies from {args.input}")
    else:
        enemies = build_sample_table()
        print(f"Using built-in sample table ({len(enemies)} early Disc-1 enemies)")

    ranges = StatRanges(
        hp_min=args.hp_min, hp_max=args.hp_max,
        atk_min=args.atk_min, atk_max=args.atk_max,
        def_min=args.def_min, def_max=args.def_max,
        exp_min=args.exp_min, exp_max=args.exp_max,
        silver_min=args.sil_min, silver_max=args.sil_max,
        agi_min=args.agi_min, agi_max=args.agi_max,
        wis_min=args.wis_min, wis_max=args.wis_max,
        mdef_min=args.mdef_min, mdef_max=args.mdef_max,
    )
    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    print(f"Seed: {seed}")
    print(f"Ranges: HP {ranges.hp_min}-{ranges.hp_max}  ATK {ranges.atk_min}-{ranges.atk_max}  "
          f"DEF {ranges.def_min}-{ranges.def_max}  EXP {ranges.exp_min}-{ranges.exp_max}  "
          f"SIL {ranges.silver_min}-{ranges.silver_max}  AGI {ranges.agi_min}-{ranges.agi_max}  "
          f"WIS {ranges.wis_min}-{ranges.wis_max}  MDEF {ranges.mdef_min}-{ranges.mdef_max}")
    print(f"Shuffle similar-level: {args.shuffle}")
    print(f"Shuffle identity (full record permutation): {args.shuffle_identity}")

    modified = randomize_enemies(
        enemies, ranges, seed,
        shuffle_similar=args.shuffle,
        level_band=args.level_band,
        shuffle_identity=args.shuffle_identity,
    )

    print()
    print(report(enemies, modified))

    out = Path(args.output) if args.output else Path("enemy_stats_randomized.bin")
    save_table(out, modified)
    print(f"\nWrote binary table → {out}  ({len(modified) * RECORD_SIZE} bytes)")

    # also CSV for inspection
    csv_path = out.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "type", "level", "hp", "attack", "defense",
                     "agility", "wisdom", "mdef", "range", "num_attacks",
                     "exp", "silver"])
        for e in modified:
            w.writerow([e.name, e.type_id, e.level, e.hp, e.attack, e.defense,
                        e.agility, e.wisdom, e.magic_defense, e.range,
                        e.num_attacks, e.exp, e.silver])
    print(f"Wrote report CSV   → {csv_path}")
    return 0


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("tkinter not available – use --cli mode")
        print("  sudo apt install python3-tk")
        return 1

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Lunar SSSC – Enemy Stat Randomizer")
            self.geometry("920x620")
            self.enemies: List[Enemy] = build_sample_table()
            self.modified: Optional[List[Enemy]] = None
            self._build()

        def _build(self):
            top = ttk.Frame(self, padding=8)
            top.pack(fill=tk.X)

            ttk.Button(top, text="Load sample table", command=self.load_sample).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Load binary…", command=self.load_bin).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save binary…", command=self.save_bin).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save CSV…", command=self.save_csv).pack(side=tk.LEFT, padx=2)

            # Ranges
            rng_frame = ttk.LabelFrame(self, text="Stat multipliers (min – max)", padding=8)
            rng_frame.pack(fill=tk.X, padx=8, pady=4)

            self.vars = {}
            defaults = [
                ("HP", "hp", 0.75, 1.40),
                ("ATK", "atk", 0.80, 1.35),
                ("DEF", "def", 0.75, 1.40),
                ("AGI", "agi", 0.80, 1.30),
                ("WIS", "wis", 0.75, 1.40),
                ("MDEF", "mdef", 0.75, 1.40),
                ("EXP", "exp", 0.70, 1.50),
                ("Silver", "sil", 0.70, 1.50),
            ]
            for col, (label, key, lo, hi) in enumerate(defaults):
                ttk.Label(rng_frame, text=label).grid(row=0, column=col*3, padx=4)
                vlo = tk.DoubleVar(value=lo)
                vhi = tk.DoubleVar(value=hi)
                self.vars[f"{key}_min"] = vlo
                self.vars[f"{key}_max"] = vhi
                ttk.Entry(rng_frame, textvariable=vlo, width=6).grid(row=0, column=col*3+1)
                ttk.Entry(rng_frame, textvariable=vhi, width=6).grid(row=0, column=col*3+2)

            opts = ttk.Frame(self, padding=8)
            opts.pack(fill=tk.X)
            self.seed_var = tk.StringVar(value=str(random.randint(1, 999999)))
            ttk.Label(opts, text="Seed:").pack(side=tk.LEFT)
            ttk.Entry(opts, textvariable=self.seed_var, width=12).pack(side=tk.LEFT, padx=4)
            self.shuffle_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(opts, text="Shuffle stats among similar-level enemies",
                            variable=self.shuffle_var).pack(side=tk.LEFT, padx=12)
            ttk.Button(opts, text="Randomize!", command=self.do_randomize).pack(side=tk.LEFT, padx=8)

            opts2 = ttk.Frame(self, padding=(8, 0, 8, 8))
            opts2.pack(fill=tk.X)
            self.shuffle_identity_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                opts2, text="Shuffle monster identity (permute FULL records across slots)",
                variable=self.shuffle_identity_var,
            ).pack(side=tk.LEFT)
            identity_note = ttk.Label(
                opts2,
                text="  Whether this changes which sprite/name shows up in a fight "
                     "depends on the game's (unconfirmed) formation lookup — see FORMATION_NOTES.md",
                foreground="#888888",
            )
            identity_note.pack(side=tk.LEFT, padx=4)

            # Table
            cols = ("name", "lv", "hp", "atk", "df", "exp", "sil")
            self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
            for c, w, a in [
                ("name", 180, tk.W), ("lv", 40, tk.E), ("hp", 100, tk.E),
                ("atk", 100, tk.E), ("df", 100, tk.E), ("exp", 100, tk.E), ("sil", 100, tk.E),
            ]:
                self.tree.heading(c, text=c.upper())
                self.tree.column(c, width=w, anchor=a)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            self.status = ttk.Label(self, text=f"Sample table loaded – {len(self.enemies)} enemies")
            self.status.pack(fill=tk.X, padx=8, pady=4)

            self.refresh_tree(self.enemies)

        def refresh_tree(self, enemies: List[Enemy], original: Optional[List[Enemy]] = None):
            self.tree.delete(*self.tree.get_children())
            for i, e in enumerate(enemies):
                if original and i < len(original):
                    o = original[i]
                    def cell(a, b):
                        return f"{a}→{b}" if a != b else str(b)
                    vals = (e.name, e.level,
                            cell(o.hp, e.hp), cell(o.attack, e.attack),
                            cell(o.defense, e.defense), cell(o.exp, e.exp),
                            cell(o.silver, e.silver))
                else:
                    vals = (e.name, e.level, e.hp, e.attack, e.defense, e.exp, e.silver)
                self.tree.insert("", tk.END, values=vals)

        def load_sample(self):
            self.enemies = build_sample_table()
            self.modified = None
            self.refresh_tree(self.enemies)
            self.status.configure(text=f"Sample table – {len(self.enemies)} enemies")

        def load_bin(self):
            p = filedialog.askopenfilename(
                title="Enemy stats binary (multiple of 38 bytes)",
                filetypes=[("Binary", "*.bin *.dat *"), ("All", "*.*")],
            )
            if not p:
                return
            try:
                self.enemies = load_table(Path(p))
                self.modified = None
                self.refresh_tree(self.enemies)
                self.status.configure(text=f"Loaded {p} – {len(self.enemies)} enemies")
            except Exception as ex:
                messagebox.showerror("Load error", str(ex))

        def save_bin(self):
            data = self.modified or self.enemies
            p = filedialog.asksaveasfilename(
                title="Save randomized table",
                defaultextension=".bin",
                filetypes=[("Binary", "*.bin"), ("All", "*.*")],
            )
            if not p:
                return
            save_table(Path(p), data)
            self.status.configure(text=f"Saved {p}")

        def save_csv(self):
            data = self.modified or self.enemies
            p = filedialog.asksaveasfilename(
                title="Save CSV report",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
            )
            if not p:
                return
            with open(p, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["name", "type", "level", "hp", "attack", "defense",
                            "exp", "silver"])
                for e in data:
                    w.writerow([e.name, e.type_id, e.level, e.hp, e.attack,
                                e.defense, e.exp, e.silver])
            self.status.configure(text=f"Saved {p}")

        def do_randomize(self):
            try:
                seed = int(self.seed_var.get())
            except ValueError:
                messagebox.showerror("Seed", "Seed must be an integer")
                return
            ranges = StatRanges(
                hp_min=self.vars["hp_min"].get(), hp_max=self.vars["hp_max"].get(),
                atk_min=self.vars["atk_min"].get(), atk_max=self.vars["atk_max"].get(),
                def_min=self.vars["def_min"].get(), def_max=self.vars["def_max"].get(),
                exp_min=self.vars["exp_min"].get(), exp_max=self.vars["exp_max"].get(),
                silver_min=self.vars["sil_min"].get(), silver_max=self.vars["sil_max"].get(),
                agi_min=self.vars["agi_min"].get(), agi_max=self.vars["agi_max"].get(),
                wis_min=self.vars["wis_min"].get(), wis_max=self.vars["wis_max"].get(),
                mdef_min=self.vars["mdef_min"].get(), mdef_max=self.vars["mdef_max"].get(),
            )
            self.modified = randomize_enemies(
                self.enemies, ranges, seed,
                shuffle_similar=self.shuffle_var.get(),
                shuffle_identity=self.shuffle_identity_var.get(),
            )
            self.refresh_tree(self.modified, original=self.enemies)
            self.status.configure(
                text=f"Randomized with seed {seed} – {len(self.modified)} enemies"
            )

    app = App()
    app.mainloop()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Lunar SSSC enemy stat randomizer")
    ap.add_argument("--cli", action="store_true", help="Run headless CLI instead of GUI")
    ap.add_argument("--input", "-i", help="Input binary table (38-byte records)")
    ap.add_argument("--output", "-o", help="Output binary path")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--shuffle", action="store_true", help="Shuffle among similar-level enemies")
    ap.add_argument("--shuffle-identity", action="store_true",
                     help="Permute FULL monster records (type/level/all stats) across table slots")
    ap.add_argument("--level-band", type=int, default=3)
    ap.add_argument("--hp-min", type=float, default=0.75)
    ap.add_argument("--hp-max", type=float, default=1.40)
    ap.add_argument("--atk-min", type=float, default=0.80)
    ap.add_argument("--atk-max", type=float, default=1.35)
    ap.add_argument("--def-min", type=float, default=0.75)
    ap.add_argument("--def-max", type=float, default=1.40)
    ap.add_argument("--exp-min", type=float, default=0.70)
    ap.add_argument("--exp-max", type=float, default=1.50)
    ap.add_argument("--sil-min", type=float, default=0.70)
    ap.add_argument("--sil-max", type=float, default=1.50)
    ap.add_argument("--agi-min", type=float, default=0.80)
    ap.add_argument("--agi-max", type=float, default=1.30)
    ap.add_argument("--wis-min", type=float, default=0.75)
    ap.add_argument("--wis-max", type=float, default=1.40)
    ap.add_argument("--mdef-min", type=float, default=0.75)
    ap.add_argument("--mdef-max", type=float, default=1.40)
    args = ap.parse_args()

    if args.cli or not sys.stdout.isatty():
        return run_cli(args)
    # Prefer GUI when available
    try:
        import tkinter  # noqa: F401
        return run_gui()
    except ImportError:
        return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
