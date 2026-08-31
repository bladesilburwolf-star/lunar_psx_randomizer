#!/usr/bin/env python3
"""
item_randomizer.py – Lunar SSSC item price randomizer

Works on the confirmed 18-byte (0x12) item record format, 72 records total,
found immediately after the enemy stat table in the decompressed exe
(see extract_item_table.py for how the offset/stride was verified):

  0x00  buy price   (2 LE)
  0x02  sell price  (2 LE)   -- always buy_price // 2 in the shipped game
  0x04  group flag  (1)      -- category-ish, 0x00 / 0x01 observed
  0x05  marker      (4)      -- mostly 00 99 00 00; unknown purpose
  0x09  idx_field   (2 LE)   -- roughly-sequential sort key
  0x0B  unknown     (7)      -- almost certainly equip stat bonuses /
                                 usable-by flags / item type -- NOT
                                 randomized here since it isn't decoded yet.
                                 Left byte-for-byte identical to the source
                                 on every record.

Only buy_price is randomized; sell_price is always recomputed as
buy_price // 2 to preserve the game's own convention (so patched saves
don't show items that are worth more to sell than to buy, etc). Records
with buy_price == 0 are treated as padding/separators and are never
touched, whatever multiplier range is chosen.

Usage:
  python3 item_randomizer.py                  # GUI
  python3 item_randomizer.py --cli --seed 42  # headless test
"""

from __future__ import annotations

import argparse
import csv
import random
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

RECORD_SIZE = 0x12  # 18
NUM_RECORDS = 72


@dataclass
class Item:
    index: int = 0
    buy: int = 0
    sell: int = 0
    group: int = 0
    marker: bytes = b"\x00\x99\x00\x00"
    idx_field: int = 0
    unknown: bytes = b"\x00" * 7
    name: str = ""  # optional label, not stored in the binary

    def pack(self) -> bytes:
        buf = bytearray(RECORD_SIZE)
        struct.pack_into("<H", buf, 0x00, max(0, min(0xFFFF, self.buy)))
        struct.pack_into("<H", buf, 0x02, max(0, min(0xFFFF, self.sell)))
        buf[0x04] = self.group & 0xFF
        buf[0x05:0x09] = self.marker[:4].ljust(4, b"\x00")
        struct.pack_into("<H", buf, 0x09, self.idx_field & 0xFFFF)
        buf[0x0B:0x12] = self.unknown[:7].ljust(7, b"\x00")
        return bytes(buf)

    @classmethod
    def unpack(cls, data: bytes, index: int, name: str = "") -> "Item":
        if len(data) < RECORD_SIZE:
            raise ValueError("record too short")
        buy, sell = struct.unpack_from("<HH", data, 0x00)
        return cls(
            index=index,
            buy=buy,
            sell=sell,
            group=data[0x04],
            marker=data[0x05:0x09],
            idx_field=struct.unpack_from("<H", data, 0x09)[0],
            unknown=data[0x0B:0x12],
            name=name,
        )


def load_table(path: Path) -> List[Item]:
    data = path.read_bytes()
    if len(data) % RECORD_SIZE != 0:
        raise ValueError(f"{path}: size {len(data)} is not a multiple of {RECORD_SIZE}")
    items = []
    for i in range(0, len(data), RECORD_SIZE):
        items.append(Item.unpack(data[i:i + RECORD_SIZE], index=i // RECORD_SIZE,
                                  name=f"Item_{i // RECORD_SIZE}"))
    return items


def save_table(path: Path, items: List[Item]) -> None:
    blob = b"".join(it.pack() for it in items)
    path.write_bytes(blob)


# ---------------------------------------------------------------------------
# Randomization
# ---------------------------------------------------------------------------

@dataclass
class PriceRange:
    """Multiplier applied to original buy price. 1.0 = unchanged."""
    price_min: float = 0.60
    price_max: float = 1.75


def randomize_items(items: List[Item], rng_range: PriceRange, seed: Optional[int]) -> List[Item]:
    rng = random.Random(seed)
    out: List[Item] = []
    for it in items:
        new = Item(**vars(it))
        if it.buy > 0:  # never invent a price on padding/separator slots
            factor = rng.uniform(rng_range.price_min, rng_range.price_max)
            new_buy = max(1, int(round(it.buy * factor)))
            new_buy = min(new_buy, 0xFFFF)
            new.buy = new_buy
            new.sell = new_buy // 2  # preserve the game's own buy/sell convention
        out.append(new)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_cli(args) -> int:
    in_path = Path(args.input) if args.input else None
    if in_path and in_path.is_file():
        items = load_table(in_path)
        print(f"Loaded {len(items)} items from {in_path}")
    else:
        print("ERROR: --input is required (run extract_item_table.py first)")
        return 1

    rng_range = PriceRange(price_min=args.price_min, price_max=args.price_max)
    seed = args.seed if args.seed is not None else random.randint(1, 999999)
    modified = randomize_items(items, rng_range, seed)

    out_path = Path(args.output) if args.output else in_path.with_name(
        in_path.stem + "_randomized.bin")
    save_table(out_path, modified)
    print(f"Seed {seed}  |  price multiplier [{rng_range.price_min}, {rng_range.price_max}]")
    print(f"Wrote randomized binary → {out_path}")

    csv_path = out_path.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "orig_buy", "orig_sell", "new_buy", "new_sell"])
        for o, n in zip(items, modified):
            w.writerow([o.index, o.buy, o.sell, n.buy, n.sell])
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
            self.title("Lunar SSSC – Item Price Randomizer")
            self.geometry("760x620")
            self.items: List[Item] = []
            self.modified: Optional[List[Item]] = None
            self._build()

        def _build(self):
            top = ttk.Frame(self, padding=8)
            top.pack(fill=tk.X)
            ttk.Button(top, text="Load binary…", command=self.load_bin).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save binary…", command=self.save_bin).pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Save CSV…", command=self.save_csv).pack(side=tk.LEFT, padx=2)

            rng_frame = ttk.LabelFrame(self, text="Price multiplier (min – max)", padding=8)
            rng_frame.pack(fill=tk.X, padx=8, pady=4)
            self.min_var = tk.DoubleVar(value=0.60)
            self.max_var = tk.DoubleVar(value=1.75)
            ttk.Label(rng_frame, text="Min").pack(side=tk.LEFT)
            ttk.Entry(rng_frame, textvariable=self.min_var, width=6).pack(side=tk.LEFT, padx=4)
            ttk.Label(rng_frame, text="Max").pack(side=tk.LEFT)
            ttk.Entry(rng_frame, textvariable=self.max_var, width=6).pack(side=tk.LEFT, padx=4)

            opts = ttk.Frame(self, padding=8)
            opts.pack(fill=tk.X)
            self.seed_var = tk.StringVar(value=str(random.randint(1, 999999)))
            ttk.Label(opts, text="Seed:").pack(side=tk.LEFT)
            ttk.Entry(opts, textvariable=self.seed_var, width=12).pack(side=tk.LEFT, padx=4)
            ttk.Button(opts, text="Randomize!", command=self.do_randomize).pack(side=tk.LEFT, padx=8)

            cols = ("idx", "buy", "sell")
            self.tree = ttk.Treeview(self, columns=cols, show="headings", height=24)
            for c, w, a in [("idx", 60, tk.E), ("buy", 300, tk.E), ("sell", 300, tk.E)]:
                self.tree.heading(c, text=c.upper())
                self.tree.column(c, width=w, anchor=a)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            self.status = ttk.Label(self, text="Load item_master.bin to begin (run extract_item_table.py first)")
            self.status.pack(fill=tk.X, padx=8, pady=4)

        def refresh_tree(self, items: List[Item], original: Optional[List[Item]] = None):
            self.tree.delete(*self.tree.get_children())
            for i, it in enumerate(items):
                if original and i < len(original):
                    o = original[i]

                    def cell(a, b):
                        return f"{a}→{b}" if a != b else str(b)
                    vals = (it.index, cell(o.buy, it.buy), cell(o.sell, it.sell))
                else:
                    vals = (it.index, it.buy, it.sell)
                self.tree.insert("", tk.END, values=vals)

        def load_bin(self):
            p = filedialog.askopenfilename(
                title="Item table binary (multiple of 18 bytes)",
                filetypes=[("Binary", "*.bin *.dat"), ("All", "*.*")],
            )
            if not p:
                return
            try:
                self.items = load_table(Path(p))
                self.modified = None
                self.refresh_tree(self.items)
                self.status.configure(text=f"Loaded {p} – {len(self.items)} items")
            except Exception as ex:
                messagebox.showerror("Load error", str(ex))

        def save_bin(self):
            if not self.items:
                messagebox.showwarning("No data", "Load a table first")
                return
            data = self.modified or self.items
            p = filedialog.asksaveasfilename(
                title="Save randomized table", defaultextension=".bin",
                filetypes=[("Binary", "*.bin"), ("All", "*.*")],
            )
            if not p:
                return
            save_table(Path(p), data)
            self.status.configure(text=f"Saved {p}")

        def save_csv(self):
            if not self.items:
                messagebox.showwarning("No data", "Load a table first")
                return
            data = self.modified or self.items
            p = filedialog.asksaveasfilename(
                title="Save CSV report", defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
            )
            if not p:
                return
            with open(p, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "buy", "sell"])
                for it in data:
                    w.writerow([it.index, it.buy, it.sell])
            self.status.configure(text=f"Saved {p}")

        def do_randomize(self):
            if not self.items:
                messagebox.showwarning("No data", "Load a table first")
                return
            try:
                seed = int(self.seed_var.get())
            except ValueError:
                messagebox.showerror("Seed", "Seed must be an integer")
                return
            rng_range = PriceRange(price_min=self.min_var.get(), price_max=self.max_var.get())
            self.modified = randomize_items(self.items, rng_range, seed)
            self.refresh_tree(self.modified, original=self.items)
            self.status.configure(text=f"Randomized with seed {seed} – {len(self.modified)} items")

    app = App()
    app.mainloop()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Lunar SSSC item price randomizer")
    ap.add_argument("--cli", action="store_true", help="Run headless CLI instead of GUI")
    ap.add_argument("--input", "-i", help="Input binary table (18-byte records)")
    ap.add_argument("--output", "-o", help="Output binary path")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--price-min", type=float, default=0.60)
    ap.add_argument("--price-max", type=float, default=1.75)
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
