# Lunar Legend (GBA, USA ALNE) — Research Notes & Toolchain

**Author:** GLM (picking up GBA work from Claude's initial binary scan)
**Date:** 2026-08-31
**ROM:** `lunar.gba` — USA (AGB-ALNE-USA), 8 MiB, CRC32 `885266A2`

---

## What's done (summary)

| Area | Status | Tool |
|------|--------|------|
| Item table located | ✅ Confirmed @ `0x7FA424`, 12-byte records | `gba_extract_item_table.py` |
| Item price randomizer | ✅ Built | `gba_item_randomizer.py` |
| Item stat (ATK/DEF) randomizer | ✅ Built (optional toggle) | `gba_item_randomizer.py` |
| Enemy table located | ⏳ Needs ROM scan to confirm exact offset/stride | `gba_scan_enemy_table.py` |
| Enemy stat randomizer | ✅ Built (configurable offset/stride/fields) | `gba_enemy_randomizer.py` |
| ROM patching | ✅ Direct in-place (GBA stores table uncompressed) | built into randomizers |
| Shop inventory randomization | ❌ Not started | — |
| Character growth/base stats | ❌ Not located in ROM | — |
| Text/encoding | ❌ Custom/compressed encoding, not decoded | — |

---

## Item table (confirmed)

**Location:** ROM offset `0x7FA424`
**Record size:** 12 bytes (`0x0C`), little-endian
**Count:** ~200 (auto-detected by scanning for a run of 4 zero records)

### Record layout

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| +0x00 | u16 | buy price | randomized |
| +0x02 | u16 | sell price | = buy // 2 (recomputed) |
| +0x04 | u8 | rare/sparse flag | often 0, preserved |
| +0x05 | u8 | element/special | 0, 0x0E, 0x0F, 0x10, 5, 6… preserved |
| +0x06 | u16 | primary combat stat (ATK) | optionally randomized (capped ≤255) |
| +0x08 | u8 | flag byte | ~always 1 in early block, preserved |
| +0x09 | u8 | zero byte | preserved |
| +0x0A | u8 | sub-type flag | preserved |
| +0x0B | u8 | category/equip flags | 0x01, 0x10, 0x20, 0x21, 0xA1… preserved |

**Randomization policy:** buy=0 records (padding/find-only/key items) are never given an invented price — mirrors PSX convention. Sell is always `buy // 2`. Stat
 values > 255 look like packed multi-field data, not simple ATK, so they're left alone.

### Why GBA is simpler than PSX

The PSX version stores item/enemy tables inside the **compressed** SLUS executable payload, requiring the gearbolt decompress → patch → recompress → CDmage/tuximage injection chain. The GBA ROM stores the item table **uncompressed in-place**, so we patch the ROM file directly — no compression chain needed.

---

## Cheat-code analysis → stat structure (NEW)

Decoded from almarsguides.com CodeBreaker code pages. CodeBreaker format: `8NNNNNNN VVVV` = write `VVVV` (u16) to RAM `0x02000000 + 0x0NNNNNNN`.

### Permanent character block

**Base RAM:** `0x02004AC2` (Alex HP), **stride:** `0x80` (128 bytes per character)

| Field | Offset from base | Size |
|-------|-----------------|------|
| HP | +0x00 | u16 |
| MP | +0x02 | u16 |
| Stat 1 (Atc) | +0x04 | u16 |
| Stat 2 (Def) | +0x06 | u16 |
| Stat 3 (Agl) | +0x08 | u16 |
| Stat 4 (Men) | +0x0A | u16 |
| Stat 5 (Res) | +0x0C | u16 |
| MaxHP | +0x10 | u16 |
| MaxMP | +0x12 | u16 |
| EXP | +0x38 | u8 |

The "Max Stats" code `43004AC6 03E7 00000005 0002` writes 999 to 5 consecutive u16 addresses starting at `+0x04` — confirming 5 core stats (Atc/Def/Agl/Men/Res).

**Character base addresses (RAM):**

| Char | HP address |
|------|-----------|
| Alex | `0x02004AC2` |
| Luna | `0x02004B02` |
| Nash | `0x02004B42` |
| Kyle | `0x02004C02` |
| Temp | `0x02004C42` |

### In-battle combatant block

**Base RAM:** `0x02037094` (Position 1), **stride:** `0x190` (400 bytes per combatant slot)

| Field | Offset from slot base | Size |
|-------|---------------------|------|
| HP | +0x00 | u16 |
| MP | +0x04 | u16 |
| SM (special meter) | +0x1C | u8 |

This is the *runtime battle* layout — enemies loaded into battle use these slots. Their *base stats* come from a ROM master table.

### Other useful RAM addresses

| Address | Meaning |
|---------|---------|
| `0x02002C38` | Money (Silver) |
| `0x02004980` | Item/equipme
nt inventory |
| `0x02004A5D` | Item flags |
| `0x02004DE4` | Cards |
| `0x02004DC8` | Gallery |

---

## Enemy table (research in progress - region narrowed)

### Scan history

| Version | Tool | Approach | Result |
|---------|------|----------|--------|
| v1 | `gba_scan_enemy_table.py` | Blind scan near item table region | 9 candidates, all in 0x7FA000-0x7FB000 - false positives (shop/drop tables, not enemy stats) |
| v2 | `gba_scan_enemy_table_v2.py` | Full-ROM blind scan with anti-item filters | Top 3: 0x8ee20/0x8ef20 (sequential index), 0x389f90 (growth table) - false positives |
| v1-anchor | `gba_locate_enemy_table.py` | Search for known enemy stats (Deathcap 15/1/7 etc.) | User ran; 20MB CSV output. Deathcap (15/1/7) is too common - floods entire ROM with thousands of hits. |
| v3 | `gba_locate_enemy_table_v3.py` | Focused: drops Deathcap, uses only distinctive anchors | **NEW** - pushed to repo, awaiting user run |

### Key finding: both methods converge on 0x559000-0x6A0000

Two independent analysis methods both point to the same broad region:

1. **v2 blind scan** found many stride-0x10 candidates in 0x559000-0x591000:
   - 0x579e50: 41 records (largest)
   - 0x5625a0: 36 records
   - 0x56a060: 29 records
   - 0x55be90: 22 records
   - 0x559930: 18 records
   - 0x5800a0: 19 records
   - 0x5910a8: 15 records (stride 0x18)

2. **Deathcap anchor matched=3 hits** (HP=15 + EXP=1 + SIL=7 all co-located in 40-byte window):
   Dense clusters throughout 0x590000-0x6A0000, including:
   - 0x597a2-0x597dc (very dense)
   - 0x5a646-0x5a69e (massive block)
   - 0x5f38a-0x6947e (many small clusters)

3. **Ruled out:**
   - 0x315b80 (stride 0x20): sequential counter 8-157 - an index table, not stats
   - 0x562598 (stride 0x14): interleaved incrementing growth curves - a level/growth table
   - 0x8ee20/0x8ef20 (stride 0x10): sequential index values 10-75 - index table

### Preliminary stride analysis (from Deathcap matched=3 offsets)

Examining the 0x5a646 Deathcap cluster: HP at +0x26, EXP at +0x0, SIL at +0x6 within the search window. This suggests a record stride of ~0x28 (40 bytes, 20 u16 fields), with field offsets approximately HP@+0x26, SIL@+4, EXP@+6. However, this analysis from Deathcap alone is unreliable - the v3 tool's stride-alignment test across multiple distinctive anchors will give a definitive answer.

### v3 approach (gba_locate_enemy_table_v3.py)

Drops noisy anchors (Deathcap, Fly Trap - values too common). Uses only distinctive anchors:
- Ammonite: 50 HP, 12 EXP, 70 Sil (SIL=70 rare)
- Killfish: 50 HP, 7 EXP, 46 Sil (SIL=46 rare)
- Wisp: 40 HP, 12 EXP, 56 Sil (SIL=56 rare)
- Magic Emperor: 6800 HP (0x1A90 - extremely rare in ROM data)

The tool finds 4KB regions where 2+ distinctive anchors cluster, then tests stride alignment (0x10-0x40) to find which stride divides the inter-anchor distances.

### Next steps

1. **Run `python gba_locate_enemy_table_v3.py lunar.gba --dump`** - this produces a small, focused console output (not a 20MB CSV) showing the best region and stride alignment scores.
2. **Alternatively/also run `python gba_dump_candidates.py lunar.gba`** - dumps all top candidate regions at strides 0x10-0x28 so we can manually inspect which stride yields clean enemy-stat-like records.
3. Paste the **console output** from the v3 run - it directly identifies the enemy table region, stride, and field offsets.

---

## GBA toolchain

```
Lunar Legend GBA/
├── gba_extract_item_table.py    # dump item table → .bin + .csv
├── gba_item_randomizer.py       # randomize prices + stats, patch ROM (GUI + CLI)
├── gba_scan_enemy_table.py       # v1 blind scan (near item table) - false positives
├── gba_scan_enemy_table_v2.py      # v2 full-ROM blind scan - false positives
├── gba_locate_enemy_table.py       # v1 anchor search (Deathcap floods results)
├── gba_locate_enemy_table_v3.py     # v3 focused anchor search (distinctive anchors only) <- RUN THIS
├── gba_dump_candidates.py          # dump top candidate regions at multiple strides
├── gba_enemy_randomizer.py       # randomize enemy stats, patch ROM (GUI + CLI)
├── RESEARCH_NOTES.md             # this document
├── CLAUDE_NOTES.md               # Claude's original findings
├── STATUS.md                     # Claude's original status (Ghidra)
├── binary_scan_notes.md          # Claude's pointer/price scan
└── gba_item_table_12byte.csv     # Claude's item table dump
```

### Workflow

```bash
# 1. Extract & inspect the item table
python3 gba_extract_item_table.py lunar.gba --out-dir dumps

# 2. Randomize items (prices + optional stats)
python3 gba_item_randomizer.py --cli --rom lunar.gba --seed 42 --out lunar_rand.gba

# 3. Locate enemy table (v3 focused anchor search)
python gba_locate_enemy_table_v3.py lunar.gba --dump
#   -> prints best region + stride alignment to console
#   -> also dumps u16 fields at each stride for manual inspection

# 3b. (alternative) dump top candidate regions for manual inspection
python gba_dump_candidates.py lunar.gba

# 4. Randomize enemies (using confirmed offset/stride from step 3)
python gba_enemy_randomizer.py --cli --rom lunar_rand.gba --offset 0x579e50 \
    --stride 0x28 --count 128 --seed 42 --out lunar_full_rand.gba
```

---

## Cross-platform consistency

These GBA tools mirror the PSX conventions established by Grok + Claude:
- **Seed-based** reproducibility (same seed → same result)
- **Buy = 0 records untouched** (no invented prices on padding/key items)
- **Sell = buy // 2** (preserves the game's own economy rule on both platforms)
- **Multiplier ranges** with sensibl
e defaults (price ×[0.60, 1.75], stats ×[0.80, 1.35])
- **GUI + CLI** modes (Python tkinter, matches PSX tools)
- **CSV reports** for verification

---

## Next steps (for the team)

1. **Confirm enemy table:** Run `python gba_locate_enemy_table_v3.py lunar.gba --dump` on the real ROM. Paste the **console output** - it shows the best region, stride alignment scores, and individual anchor hit positions. The enemy table is expected in 0x559000-0x6A0000. Alternatively run `python gba_dump_candidates.py lunar.gba` and upload a few of the generated dump CSVs (especially 0x579e50 and 0x56a060 at stride 0x28).
2. **Shop inventories:** Still open on both PSX and GBA — lists of item IDs per town/shop.
3. **Character base stats:** The ROM source for the `0x02004AC2`-region base stats has not been located. Search for a table of 8 character blocks × 128 bytes with HP/MP/stats matching Alex lv1, Luna lv1, etc.
4. **Text decoding:** GBA uses a custom/compressed font encoding; item/character names are not ASCII. Needed if we want to display names in the GUI.
5. **Unified GUI:** Once GBA enemy table is confirmed, consider a combined GBA tab in the Java `LunarRandomizer` app (or a Python unified launcher) so users can randomize both PSX and GBA from one interface.
