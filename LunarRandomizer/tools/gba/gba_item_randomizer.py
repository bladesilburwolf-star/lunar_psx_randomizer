#!/usr/bin/env python3
"""
gba_item_randomizer.py – Lunar Legend (GBA, USA ALNE) item table randomizer

Works on the combined price + stat item table found at ROM offset 0x7FA424,
12-byte (0x0C) little-endian records (see CLAUDE_NOTES.md / binary_scan_notes.md
in the "Lunar Legend GBA" folder for how this offset/stride was verified).

Record layout (confirmed from Claude's CSV dump):
  0x00  buy price   (u16 LE)
  0x02  sell price  (u16 LE)   -- always buy // 2 in the shipped game
  0x04  rare/sparse flag (u8)  -- often 0
  0x05  element/special  (u8)  -- 0, 0x0E, 0x0F, 0x10, 5, 6, ...
  0x06  primary combat stat (u16 LE) -- ATK for weapons, scales with price tier
  0x08  flag byte (u8)         -- almost always 1 in the early block
  0x09  zero byte (u8)
  0x0A  sub-type flag (u8)
  0x0B  category/equip flags (u8) -- 0x01, 0x10, 0x20, 0x21, 0xA1, ...

Unlike the PSX version (which needs the gearbolt decompress -> patch ->
recompress -> CDmage/tuximage inject chain), the GBA ROM stores this table
uncompressed in-place, so we patch the ROM file directly.

Randomization policy (mirrors PSX item_randomizer.py conventions):
  - buy price is scaled by a random factor within [price_min, price_max].
  - sell price is recomputed as buy // 2 (preserves the game's own convention).
  - the primary combat stat (ATK/DEF/etc.) is optionally scaled by a separate
    factor within [stat_min, stat_max].
  - records with buy == 0 are treated as padding/find-only/key items and are
    never given an invented price (matching PSX behavior).
  - all other bytes are preserved byte-for-byte so equip flags, element,
    category, etc. are untouched (we have NOT decoded them fully yet).

Usage:
  python3 gba_item_randomizer.py                                    # GUI
  python3 gba_item_randomizer.py --cli --rom lunar.gba --seed 42    # headless
  python3 gba_item_randomizer.py --cli --rom lunar.gba --out lunar_rand.gba
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Table geometry (confirmed by Claude's binary scan)
# ---------------------------------------------------------------------------

ITEM_TABLE_OFFSET = 0x7FA424
RECORD_SIZE = 0x0C  # 12 bytes
# Claude scanned ~200 entries; the dense block is clearly a single contiguous
# table. We let load_table() auto-detect the real count by reading until the
# table region ends (see _detect_table_extent), but keep a sane default.
DEFAULT_NUM_RECORDS = 200


@dataclass
class GbaItem:
    """One 12-byte item record from the GBA item table."""

    index: int = 0
    offset: int = 0          # absolute ROM offset of this record
    buy: int = 0
    sell: int = 0
    rare: int = 0            # +0x04
    element: int = 0         # +0x05
    stat: int = 0            # +0x06  primary combat stat (u16)
    flag8: int = 0           # +0x08
    zero9: int = 0           # +0x09
    subtype: int = 0         # +0x0A
    category: int = 0        # +0x0B
    raw: bytes = b""         # original 12 bytes (for round-trip safety)

    # ----- pack / unpack -----

    def pack(self) -> bytes:
        buf = bytearray(RECORD_SIZE)
        struct.pack_into("<H", buf, 0x00, _clamp_u16(self.buy))
        struct.pack_into("<H", buf, 0x02, _clamp_u16(self.sell))
        buf[0x04] = self.rare & 0xFF
        buf[0x05] = self.element & 0xFF
        struct.pack_into("<H", buf, 0x06, _clamp_u16(self.stat))
        buf[0x08] = self.flag8 & 0xFF
        buf[0x09] = self.zero9 & 0xFF
        buf[0x0A] = self.subtype & 0xFF
        buf[0x0B] = self.category & 0xFF
        return bytes(buf)

    @classmethod
    def unpack(cls, data: bytes, index: int, base_offset: int) -> "GbaItem":
        if len(data) < RECORD_SIZE:
            raise ValueError("record too short")
        buy, sell = struct.unpack_from("<HH", data, 0x00)
        stat = struct.unpack_from("<H", data, 0x06)[0]
        return cls(
            index=index,
            offset=base_offset + index * RECORD_SIZE,
            buy=buy,
            sell=sell,
            rare=data[0x04],
            element=data[0x05],
            stat=stat,
            flag8=data[0x08],
            zero9=data[0x09],
            subtype=data[0x0A],
            category=data[0x0B],
            raw=bytes(data[:RECORD_SIZE]),
        )

    def is_priced(self) -> bool:
        """Skip padding / find-only / key items — never invent a price."""
        return self.buy > 0

    def has_stat(self) -> bool:
        """Whether the stat field looks like a real combat bonus to randomize."""
        return 1 <= self.stat <= 255


# ---------------------------------------------------------------------------
# ROM load / patch
# ---------------------------------------------------------------------------

GBA_ROM_SIZE = 8 * 1024 * 1024  # 8 MiB, standard USA ALNE ROM


def validate_rom(data: bytes) -> None:
    if len(data) < GBA_ROM_SIZE:
        raise ValueError(
            f"ROM too small: {len(data)} bytes (expected >= {GBA_ROM_SIZE} for an 8 MiB USA ROM)"
        )
    title = data[0xA0:0xAC]
    code = data[0xAC:0xB0]
    if b"LUNAR" not in title.upper() and code != b"ALNE":
        raise ValueError(
            f"ROM header doesn't look like Lunar Legend USA "
            f"(title={title!r}, code={code!r})"
        )


def load_rom(path: Path) -> bytes:
    data = path.read_bytes()
    validate_rom(data)
    return data


def _detect_table_extent(rom: bytes, start: int, max_records: int) -> int:
    zero_run = 0
    for i in range(max_records):
        off = start + i * RECORD_SIZE
        if off + RECORD_SIZE > len(rom):
            return i
        buy, sell = struct.unpack_from("<HH", rom, off)
        stat = struct.unpack_from("<H", rom, off + 0x06)[0]
        if buy == 0 and sell == 0 and stat == 0:
            zero_run += 1
            if zero_run >= 4:
                return max(1, i - zero_run + 1)
        else:
            zero_run = 0
    return max_records


def load_table(rom: bytes, count: Optional[int] = None) -> List[GbaItem]:
    if count is None:
        count = _detect_table_extent(rom, ITEM_TABLE_OFFSET, DEFAULT_NUM_RECORDS)
    items: List[GbaItem] = []
    for i in range(count):
        off = ITEM_TABLE_OFFSET + i * RECORD_SIZE
        if off + RECORD_SIZE > len(rom):
            break
        rec = rom[off:off + RECORD_SIZE]
        items.append(GbaItem.unpack(rec, i, ITEM_TABLE_OFFSET))
    return items


def patch_rom(rom: bytes, items: List[GbaItem]) -> bytes:
    out = bytearray(rom)
    for it in items:
        rec = it.pack()
        out[it.offset:it.offset + RECORD_SIZE] = rec
    return bytes(out)


# ---------------------------------------------------------------------------
# Randomization
# ---------------------------------------------------------------------------

@dataclass
class Ranges:
    """Multipliers applied to original values. 1.0 = unchanged."""
    price_min: float = 0.60
    price_max: float = 1.75
    stat_min: float = 0.80
    stat_max: float = 1.35
    randomize_stats: bool = True


def _scale(rng: random.Random, value: int, lo: float, hi: float) -> int:
    if value <= 0:
        return value
    factor = rng.uniform(lo, hi)
    return max(1, int(round(value * factor)))


def randomize_items(items: List[GbaItem], ranges: Ranges, seed: Optional[int]) -> List[GbaItem]:
    rng = random.Random(seed)
    out: List[GbaItem] = []
    for it in items:
        new = GbaItem(**{k: getattr(it, k) for k in [
            "index", "offset", "buy", "sell", "rare", "element",
            "stat", "flag8", "zero9", "subtype", "category", "raw"
        ]})
        if it.is_priced():
            new.buy = _clamp_u16(_scale(rng, it.buy, ranges.price_min, ranges.price_max))
            new.sell = new.buy // 2
        if ranges.randomize_stats and it.has_stat():
            new.stat = _clamp_u16(_scale(rng, it.stat, ranges.stat_min, ranges.stat_max))
        out.append(new)
    return out


# ---------------------------------------------------------------------------
# CSV report
# ---------------------------------------------------------------------------

def write_csv(path: Path, original: List[GbaItem], modified: List[GbaItem]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "index", "offset", "orig_buy", "new_buy", "orig_sell", "new_sell",
            "orig_stat", "new_stat", "rare", "element", "flag8", "subtype",
            "category",
        ])
        for o, n in zip(original, modified):
            w.writerow([
                o.index, hex(o.offset), o.buy, n.buy, o.sell, n.sell,
                o.stat, n.stat, o.rare, o.element, o.flag8, o.subtype,
                o.category,
            ])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_cli(args) -> int:
    if not args.rom:
        print("ERROR: --rom is required (path to a USA ALNE lunar.gba)")
        return 1
    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ERROR: ROM not found: {rom_path}")
        return 1

    rom = load_rom(rom_path)
    count = args.count if args.count else None
    items = load_table(rom, count)
    print(f"Loaded {len(items)} item records from {rom_path} @ {hex(ITEM_TABLE_OFFSET)}")

    ranges = Ranges(
        price_min=args.price_min, price_max=args.price_max,
        stat_min=args.stat_min, stat_max=args.stat_max,
        randomize_stats=not args.no_stats,
    )
    seed = args.seed if args.seed is not None else random.randint(1, 999999)
    modified = randomize_items(items, ranges, seed)

    priced = sum(1 for it in modified if it.buy > 0)
    stated = sum(1 for it in modified if 1 <= it.stat <= 255) if ranges.randomize_stats else 0
    print(f"Seed {seed} | price x[{ranges.price_min}, {ranges.price_max}] "
          f"| stat x[{ranges.stat_min}, {ranges.stat_max}]")
    print(f"  priced records touched: {priced}")
    print(f"  stat records touched:   {stated}")

    out_rom = Path(args.out) if args.out else rom_path.with_name(rom_path.stem + "_rand.gba")
    patched = patch_rom(rom, modified)
    out_rom.write_bytes(patched)
    print(f"Wrote randomized ROM -> {out_rom}")

    csv_path = out_rom.with_suffix(".csv")
    write_csv(csv_path, items, modified)
    print(f"Wrote report CSV   -> {csv_path}")
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
            self.title("Lunar Legend (GBA) — Item Randomizer")
            self.geometry("820x660")
            self.rom: Optional[bytes] = None
            self.rom_path: Optional[Path] = None
            self.items: List[GbaItem] = []
            self.modified: Optional[List[GbaItem]] = None
            self._build()

        def _build(self):
            top = ttk.Frame(self, padding=8)
            top.pack(fill=tk.X)
            ttk.Button(top, text="Load ROM…", command=self.load_rom).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save ROM…", command=self.save_rom).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save CSV…", command=self.save_csv).pack(side=tk.LEFT, padx=2)

            rng = ttk.LabelFrame(self, text="Price multiplier (min – max)", padding=8)
            rng.pack(fill=tk.X, padx=8, pady=4)
            self.pmin = tk.DoubleVar(value=0.60)
            self.pmax = tk.DoubleVar(value=1.75)
            ttk.Label(rng, text="Min").pack(side=tk.LEFT)
            ttk.Entry(rng, textvariable=self.pmin, width=6).pack(side=tk.LEFT, padx=4)
            ttk.Label(rng, text="Max").pack(side=tk.LEFT)
            ttk.Entry(rng, textvariable=self.pmax, width=6).pack(side=tk.LEFT, padx=4)

            srng = ttk.LabelFrame(self, text="Stat (ATK/DEF) multiplier (min – max)", padding=8)
            srng.pack(fill=tk.X, padx=8, pady=4)
            self.smin = tk.DoubleVar(value=0.80)
            self.smax = tk.DoubleVar(value=1.35)
            self.stat_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(srng, text="Randomize stats", variable=self.stat_var).pack(side=tk.LEFT, padx=4)
            ttk.Label(srng, text="Min").pack(side=tk.LEFT)
            ttk.Entry(srng, textvariable=self.smin, width=6).pack(side=tk.LEFT, padx=4)
            ttk.Label(srng, text="Max").pack(side=tk.LEFT)
            ttk.Entry(srng, textvariable=self.smax, width=6).pack(side=tk.LEFT, padx=4)

            opts = ttk.Frame(self, padding=8)
            opts.pack(fill=tk.X)
            self.seed_var = tk.StringVar(value=str(random.randint(1, 999999)))
            ttk.Label(opts, text="Seed:").pack(side=tk.LEFT)
            ttk.Entry(opts, textvariable=self.seed_var, width=12).pack(side=tk.LEFT, padx=4)
            ttk.Button(opts, text="Randomize!", command=self.do_randomize).pack(side=tk.LEFT, padx=8)

            cols = ("idx", "buy", "sell", "stat", "cat")
            self.tree = ttk.Treeview(self, columns=cols, show="headings", height=26)
            for c, w, a in [("idx", 50, tk.E), ("buy", 140, tk.E),
                            ("sell", 140, tk.E), ("stat", 120, tk.E),
                            ("cat", 80, tk.E)]:
                self.tree.heading(c, text=c.upper())
                self.tree.column(c, width=w, anchor=a)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            self.status = ttk.Label(self, text="Load a USA lunar.gba ROM to begin")
            self.status.pack(fill=tk.X, padx=8, pady=4)

        def _refresh(self, items: List[GbaItem], original: Optional[List[GbaItem]] = None):
            self.tree.delete(*self.tree.get_children())
            for i, it in enumerate(items):
                if original and i < len(original):
                    o = original[i]
                    def cell(a, b):
                        return f"{a}->{b}" if a != b else str(b)
                    vals = (it.index, cell(o.buy, it.buy), cell(o.sell, it.sell),
                            cell(o.stat, it.stat), hex(it.category))
                else:
                    vals = (it.index, it.buy, it.sell, it.stat, hex(it.category))
                self.tree.insert("", tk.END, values=vals)

        def load_rom(self):
            p = filedialog.askopenfilename(
                title="Lunar Legend USA ROM",
                filetypes=[("GBA ROM", "*.gba"), ("All", "*.*")],
            )
            if not p:
                return
            try:
                self.rom = load_rom(Path(p))
                self.rom_path = Path(p)
                self.items = load_table(self.rom)
                self.modified = None
                self._refresh(self.items)
                self.status.configure(
                    text=f"Loaded {p} – {len(self.items)} records @ {hex(ITEM_TABLE_OFFSET)}")
            except Exception as ex:
                messagebox.showerror("Load error", str(ex))

        def save_rom(self):
            if not self.rom or not self.items:
                messagebox.showwarning("No data", "Load a ROM and randomize first")
                return
            data = self.modified or self.items
            p = filedialog.asksaveasfilename(
                title="Save randomized ROM", defaultextension=".gba",
                filetypes=[("GBA ROM", "*.gba"), ("All", "*.*")],
            )
            if not p:
                return
            patched = patch_rom(self.rom, data)
            Path(p).write_bytes(patched)
            self.status.configure(text=f"Saved {p}")

        def save_csv(self):
            if not self.items:
                messagebox.showwarning("No data", "Load a ROM first")
                return
            data = self.modified or self.items
            p = filedialog.asksaveasfilename(
                title="Save CSV report", defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
            )
            if not p:
                return
            write_csv(Path(p), self.items, data)
            self.status.configure(text=f"Saved {p}")

        def do_randomize(self):
            if not self.rom or not self.items:
                messagebox.showwarning("No data", "Load a ROM first")
                return
            try:
                seed = int(self.seed_var.get())
            except ValueError:
                messagebox.showerror("Seed", "Seed must be an integer")
                return
            ranges = Ranges(
                price_min=self.pmin.get(), price_max=self.pmax.get(),
                stat_min=self.smin.get(), stat_max=self.smax.get(),
                randomize_stats=self.stat_var.get(),
            )
            self.modified = randomize_items(self.items, ranges, seed)
            self._refresh(self.modified, original=self.items)
            self.status.configure(
                text=f"Randomized with seed {seed} – {len(self.modified)} records")

    app = App()
    app.mainloop()
    return 0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clamp_u16(v: int) -> int:
    if v < 0:
        return 0
    if v > 0xFFFF:
        return 0xFFFF
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description="Lunar Legend (GBA) item table randomizer")
    ap.add_argument("--cli", action="store_true", help="Run headless CLI instead of GUI")
    ap.add_argument("--rom", "-r", help="Input USA lunar.gba ROM path")
    ap.add_argument("--out", "-o", help="Output randomized ROM path")
    ap.add_argument("--count", type=int, default=None,
                    help="Number of 12-byte records to read (auto-detect if omitted)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--price-min", type=float, default=0.60)
    ap.add_argument("--price-max", type=float, default=1.75)
    ap.add_argument("--stat-min", type=float, default=0.80)
    ap.add_argument("--stat-max", type=float, default=1.35)
    ap.add_argument("--no-stats", action="store_true",
                    help="Do not randomize the combat stat field")
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
