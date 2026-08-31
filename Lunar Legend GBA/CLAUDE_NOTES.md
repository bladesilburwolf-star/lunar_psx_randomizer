# Lunar Legend (GBA, USA ALNE) — notes for PS1 item cross-ref

Generated for Claude / item randomizer work. ROM at `artifacts/gba_lunar_legend/lunar.gba`.

## Headline finding: combined price+stat table

**Offset `0x7FA424`**, **12-byte records**, ~200 entries scanned.

| Offset | Size | Likely meaning |
|--------|------|----------------|
| +0x00 | u16 | **buy price** |
| +0x02 | u16 | **sell price** (always `buy // 2` when buy > 0 — same rule as PS1) |
| +0x04 | u8 | rare / sparse (often 0) |
| +0x05 | u8 | **element / special?** (0, 0x0E, 0x0F, 0x10, 5, 6, …) |
| +0x06 | u16 | **primary combat stat** (ATK for weapons — scales with price tier) |
| +0x08 | u8 | almost always 1 in early block |
| +0x09 | u8 | 0 |
| +0x0A | u8 | secondary flag / sub-type |
| +0x0B | u8 | **category / equip flags** (0x01, 0x10, 0x20, 0x21, 0xA1, …) |

CSV dump: `gba_item_table_12byte.csv`

### Sample weapons (stat scales with price)

```
buy    sell   stat  flags
10     5      6     0xA1     (starter / knife-tier)
20     10     11    0xA1
100    50     27    0x01     (~Dagger/Short tier)
200—   —      —     —        (GBA prices are rebalanced; not 1:1 with PS1)
600    300    49    0x01
1400   700    60    0x20
4000   2000   50    0x01     (element nibble set)
15000  7500   85    0x20     (endgame-ish)
0      0      75    …        (find-only / key, like Althena's Sword on PS1)
```

### Why this matters for PS1

On **PS1 SSSC**, Claude already found:
- Economy table @ decomp `0x99244`: 72 × **18-byte** records (buy, sell, flavor) — **no ATK/DEF**
- Combat bonuses are a **separate table still missing**

On **GBA**, price and primary stat appear **in the same 12-byte record**.
That suggests PS1 may have split what GBA kept together:
1. Search PS1 decomp near `0x99244` for a parallel table with the same item count (72) and ATK values climbing ~6→85+
2. Or search for u16 sequences matching published SSSC weapon ATK (Dagger +6, Short Sword +11, Long +16, Broad +21, …)

### PS1 weapon ATK anchors (from period FAQs)

```
Dagger +6, Short Sword +11, Long Sword +16, Broad Sword +21,
Saber +27, Silver Sword +33, Samurai +38, Ice Blade +44,
Flame Sword +49, Bastard +50, Great +55, Wind +60, …
Mace +34, Flail +39, Ice Mace +44, …
```

Search decomp EXE for: `06 00 0B 00 10 00 15 00` (u16 LE ATK chain) or
`06 0B 10 15 1B` (u8 chain).

## Economy rule (shared)

Both platforms: **sell = buy // 2** for sold items; **buy=sell=0** for unique/find-only.

## Differences to expect

- GBA prices are **rebalanced** (not identical number-for-number to SSSC)
- GBA item count/order may differ (Legend is a remake, not a port)
- Text is **not plain ASCII** (compressed or custom encoding) — don't expect "Short Sword" strings
- Character lv1 stats (Alex 32/10/20/16) **not found** as raw patterns — different bases or packed growth

## Cheat RAM (runtime, mGBA/VBA)

From public cheat DBs (Japanese board dumps):
- Money: `0x042C38`
- Item/equip flags: `0x044A5D`, `0x044981`
- Alex level: `0x044AC0`
- Luna level: `0x044B00`

Useful for confirming which table index is "current weapon" after equipping.

## Region map (rough)

- `0x7FA000`–`0x7FB000`: dense item/economy data (this table lives here)
- Full ROM is 8 MiB; high entropy throughout (graphics + compressed text)

## Files in this folder

| File | Purpose |
|------|---------|
| `lunar.gba` | USA ROM |
| `gba_item_table_12byte.csv` | Full dump of 12-byte records from 0x7FA424 |
| `binary_scan_notes.md` | Earlier pointer/price scan |
| `STATUS.md` | Ghidra / toolchain status |
| `CLAUDE_NOTES.md` | This document |

## Suggested next searches (PS1)

1. In decomp SLUS: find 72-entry table of u16 ATK bonuses near item economy table
2. Match order: if GBA index order ≈ PS1 item ID order, use GBA `stat_u16` as a hint for expected ATK sequence
3. Shop inventories: still open on both platforms (lists of item IDs per town)

## PS1 decomp ATK-sequence search (negative so far)

Searched decompressed SLUS payload (690176 bytes) for:

- u16 LE: `06 00 0B 00 10 00 15 00 1B 00` (6,11,16,21,27)
- u8: `06 0B 10 15 1B`

**No hits.** So PS1 does **not** store published ATK bonuses as a simple contiguous array of those values (at least not in that exact early-weapon order).

Possible explanations:
- ATK is in a wider struct (with DEF/slot/flags between values)
- Different internal numbers than the FAQ “Attack+N” display values
- Table is indexed differently / compressed / in a file other than the EXE

GBA still helps: same *curve shape* (6→11→16→21→27…) appears as `stat_u16` in the 12-byte records, so the design lineage is real even if packing differs.

## Quick win for Claude

1. Treat GBA `0x7FA424` / 12-byte layout as the “combined” reference model.
2. On PS1, keep randomizing economy @ `0x99244` (done).
3. For ATK/DEF: scan decomp for other 72-entry tables near `0x99244`, or structures where a field climbs roughly with item tier; use GBA `stat_u16` order as a soft oracle, not a byte-exact match.
