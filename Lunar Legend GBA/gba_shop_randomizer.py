#!/usr/bin/env python3
"""
gba_shop_randomizer.py – Lunar Legend (GBA, USA ALNE) shop inventory randomizer

Works on the shop/drop table at ROM offset 0x7FA8C0 (16-byte records).
See SHOP_DROP_TABLE_FINDING.md for discovery notes.

Record structure (16 bytes):
  0x00-0x01  buy_price_1   (u16 LE)  -- First item price
  0x02-0x03  sell_price_1  (u16 LE)  -- Sell price (usually buy // 2)
  0x04-0x05  type/group    (u16 LE)  -- Weapon/Armor/Accessory? (2/3/4)
  0x06-0x07  category+idx  (u16 LE)  -- Category flags (high byte) + item index (low byte)
  0x08-0x0F  secondary     (8 bytes) -- Item prices/drops (needs decode)

Current understanding:
  - Each 16-byte record represents ONE shop slot or enemy drop
  - 52 records total (52 shops or 52 drop entries)
  - Records preserve item category during randomization
  - Prices are recomputed from randomized base values

Randomization strategy:
  1. Randomize buy prices within reasonable bounds (10-15000)
  2. Recalculate sell price = buy // 2
  3. Keep type/category/item index unchanged
  4. Optionally shuffle which items appear in shops (complex, TBD)

Usage (stub):
  python3 gba_shop_randomizer.py --cli --rom lunar.gba --seed 42
  python3 gba_shop_randomizer.py --cli --rom lunar.gba --out lunar_rand.gba --seed 99999
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

# ============================================================================
# CONSTANTS - Shop/Drop Table
# ============================================================================

SHOP_TABLE_OFFSET = 0x7FA8C0
RECORD_SIZE = 0x10  # 16 bytes per shop/drop entry
RECORD_COUNT = 52   # Estimated; v1 scanner found 52 records

# Field offsets within each 16-byte record
FIELD_BUY_PRICE_1 = 0x00    # u16 LE
FIELD_SELL_PRICE_1 = 0x02   # u16 LE
FIELD_TYPE_GROUP = 0x04     # u16 LE (2/3/4 = weapon/armor/accessory?)
FIELD_CATEGORY_IDX = 0x06   # u16 LE (high byte = flags, low byte = item index 0-199)
FIELD_SECONDARY = 0x08      # 8 bytes (prices or packed data, needs decode)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ShopRecord:
    """Represents one shop/drop table entry."""
    offset: int
    buy_price_1: int       # u16
    sell_price_1: int      # u16
    type_group: int        # u16 (2=weapon, 3=armor, 4=accessory)
    category: int          # u8 (high byte of category_idx)
    item_idx: int          # u8 (low byte of category_idx)
    secondary: bytes       # 8 bytes (undecoded for now)
    
    def to_bytes(self) -> bytes:
        """Serialize to 16-byte record."""
        out = bytearray(RECORD_SIZE)
        struct.pack_into('<H', out, FIELD_BUY_PRICE_1, self.buy_price_1)
        struct.pack_into('<H', out, FIELD_SELL_PRICE_1, self.sell_price_1)
        struct.pack_into('<H', out, FIELD_TYPE_GROUP, self.type_group)
        struct.pack_into('<H', out, FIELD_CATEGORY_IDX, (self.category << 8) | self.item_idx)
        out[FIELD_SECONDARY:FIELD_SECONDARY+8] = self.secondary
        return bytes(out)
    
    @staticmethod
    def from_bytes(offset: int, data: bytes) -> ShopRecord:
        """Deserialize from 16-byte record."""
        buy_1 = struct.unpack_from('<H', data, FIELD_BUY_PRICE_1)[0]
        sell_1 = struct.unpack_from('<H', data, FIELD_SELL_PRICE_1)[0]
        type_g = struct.unpack_from('<H', data, FIELD_TYPE_GROUP)[0]
        cat_idx = struct.unpack_from('<H', data, FIELD_CATEGORY_IDX)[0]
        category = (cat_idx >> 8) & 0xFF
        item_idx = cat_idx & 0xFF
        secondary = data[FIELD_SECONDARY:FIELD_SECONDARY+8]
        
        return ShopRecord(
            offset=offset,
            buy_price_1=buy_1,
            sell_price_1=sell_1,
            type_group=type_g,
            category=category,
            item_idx=item_idx,
            secondary=secondary
        )

# ============================================================================
# RANDOMIZATION
# ============================================================================

def randomize_shops(rom_data: bytes, seed: int, 
                   price_min: float = 0.5, price_max: float = 2.5) -> bytes:
    """
    Randomize shop/drop table prices.
    
    Args:
        rom_data: Full ROM as bytes
        seed: Random seed
        price_min: Min price multiplier (default 0.5x)
        price_max: Max price multiplier (default 2.5x)
    
    Returns:
        Modified ROM with randomized shop prices
    """
    rng = random.Random(seed)
    rom_out = bytearray(rom_data)
    
    # Read shop records
    shops = []
    for i in range(RECORD_COUNT):
        offset = SHOP_TABLE_OFFSET + (i * RECORD_SIZE)
        record_data = rom_data[offset:offset+RECORD_SIZE]
        shop = ShopRecord.from_bytes(offset, record_data)
        shops.append(shop)
    
    # Randomize prices
    modified = 0
    for shop in shops:
        if shop.buy_price_1 > 0:  # Only randomize sellable items
            factor = rng.uniform(price_min, price_max)
            new_buy = max(1, int(shop.buy_price_1 * factor))
            new_sell = new_buy // 2
            
            shop.buy_price_1 = new_buy
            shop.sell_price_1 = new_sell
            modified += 1
    
    # Write back to ROM
    for shop in shops:
        record_bytes = shop.to_bytes()
        rom_out[shop.offset:shop.offset+RECORD_SIZE] = record_bytes
    
    print(f"Randomized {modified}/{len(shops)} shop entries")
    return bytes(rom_out)

# ============================================================================
# CLI / GUI STUB
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="Lunar Legend (GBA) shop/drop table randomizer")
    ap.add_argument("--cli", action="store_true", help="Headless mode")
    ap.add_argument("--rom", "-r", type=str, help="Input ROM path")
    ap.add_argument("--out", "-o", type=str, help="Output ROM path (default: rom.gba → rom_rand.gba)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    ap.add_argument("--price-min", type=float, default=0.5, help="Min price multiplier")
    ap.add_argument("--price-max", type=float, default=2.5, help="Max price multiplier")
    
    args = ap.parse_args()
    
    if not args.cli:
        print("GUI mode not implemented yet")
        print("Use --cli for headless randomization")
        sys.exit(1)
    
    if not args.rom or not Path(args.rom).exists():
        print(f"❌ ROM not found: {args.rom}")
        sys.exit(1)
    
    # Read ROM
    with open(args.rom, 'rb') as f:
        rom_data = f.read()
    
    # Randomize
    rom_rand = randomize_shops(rom_data, args.seed, args.price_min, args.price_max)
    
    # Write output
    out_path = args.out or (Path(args.rom).stem + "_rand.gba")
    with open(out_path, 'wb') as f:
        f.write(rom_rand)
    
    print(f"✅ Wrote randomized ROM → {out_path}")
    
    # TODO: Generate CSV report with before/after prices

if __name__ == "__main__":
    main()
