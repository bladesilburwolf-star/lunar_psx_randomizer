# Shop/Drop Table Finding (from enemy table scan v1)

The v1 enemy table scanner found a candidate at `0x7fa8c0` (stride 0x10, 52 records)
that turned out to be an **item-adjacent table** — NOT enemy stats. Analysis:

## What it actually is

This table starts at `0x7fa8c0`, just 4 bytes after the item table ends (~`0x7fa8bc`).
Each 16-byte record contains:
- **u16_0/u16_1**: buy/sell price pair #1 (sell = buy // 2)
- **u16_2**: type/group indicator (values 2, 3, 4 across the table — likely weapon/armor/accessory)
- **u16_3**: packed (item_category_flag << 8 | item_index) — flag bytes 0x21, 0x0A, 0x20, 0xA1, 0x18 match the item table's category field
- **u16_4/u16_5**: second data pair (sometimes buy/sell, sometimes packed flags)
- **u16_6/u16_7**: buy/sell price pair #2

This is almost certainly a **shop inventory table** or **enemy drop table** — each
record lists items available in a shop (or dropped by an enemy) with their prices.

## Why all v1 candidates were false positives

All 9 candidates from the v1 scan were in or adjacent to the item table region
(0x7FA000-0x7FB000). The item table (0x7FA424, 12-byte records) and this shop/drop
table (0x7FA8C0, 16-byte records) both contain small numeric values (prices 10-15000)
that overlap the range of enemy stats (HP, ATK, DEF), causing false matches.

## What was done

Created `gba_scan_enemy_table_v2.py` which:
1. Scans the FULL ROM (not just near the item table)
2. Skips the 0x7FA000-0x7FB000 item region entirely
3. Penalizes buy/sell pairs (anti-item-table filter)
4. Penalizes packed item-flag bytes (high byte in item category set)
5. Requires HP in the 5-9999 range and multiple plausible stat fields

## Bonus: this shop/drop table is itself useful

The 16-byte table at 0x7fa8c0 could enable **shop inventory randomization** —
shuffling which items appear in each shop. This is a feature that was listed
as "not started" for both PSX and GBA. The record layout needs further decoding
(item IDs, shop indices) before a randomizer can be built for it.
