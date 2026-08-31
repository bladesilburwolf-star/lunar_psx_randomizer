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

**Randomization policy:** buy=0 records (padding/find-only/key items) are never given an invented price — mirrors PSX convention. Sell is always `buy // 2`. Stat values > 255 look like packed multi-field data, not simple ATK, so they're left alone.

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
| `0x02004980` | Item/equipment inventory |
| `0x02004A5D` | Item flags |
| `0x02004DE4` | Cards |
| `0x02004DC8` | Gallery |

---

## Enemy table (research in progress)

Claude's binary scan found pointer tables at `0x7FB29C` (2589 pointers), `0x7F8288` (1091 pointers), `0x7F9D0C` (451 pointers). The item table lives at `0x7FA424`. The enemy master table is expected nearby. **Run `gba_scan_enemy_table.py`** to locate candidates.

---

## GBA toolchain

```
Lunar Legend GBA/
├── gba_extract_item_table.py    # dump item table → .bin + .csv
├── gba_item_randomizer.py       # randomize prices + stats, patch ROM (GUI + CLI)
├── gba_scan_enemy_table.py       # scan ROM for enemy stat table candidates
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

# 3. Scan for enemy table (once, to confirm offset/stride)
python3 gba_scan_enemy_table.py lunar.gba

# 4. Randomize enemies (using confirmed offset/stride from step 3)
python3 gba_enemy_randomizer.py --cli --rom lunar_rand.gba --offset 0x7FA000 \
    --stride 0x20 --count 128 --seed 42 --out lunar_full_rand.gba
```

---

## Cross-platform consistency

These GBA tools mirror the PSX conventions established by Grok + Claude:
- **Seed-based** reproducibility (same seed → same result)
- **Buy = 0 records untouched** (no invented prices on padding/key items)
- **Sell = buy // 2** (preserves the game's own economy rule on both platforms)
- **Multiplier ranges** with sensible defaults (price ×[0.60, 1.75], stats ×[0.80, 1.35])
- **GUI + CLI** modes (Python tkinter, matches PSX tools)
- **CSV reports** for verification

---

## Next steps (for the team)

1. **Confirm enemy table:** Run `gba_scan_enemy_table.py` on the real ROM, inspect `gba_enemies_top_candidate.csv`, and lock in the offset/stride/field map.
2. **Shop inventories:** Still open on both PSX and GBA — lists of item IDs per town/shop.
3. **Character base stats:** The ROM source for the `0x02004AC2`-region base stats has not been located. Search for a table of 8 character blocks × 128 bytes with HP/MP/stats matching Alex lv1, Luna lv1, etc.
4. **Text decoding:** GBA uses a custom/compressed font encoding; item/character names are not ASCII. Needed if we want to display names in the GUI.
5. **Unified GUI:** Once GBA enemy table is confirmed, consider a combined GBA tab in the Java `LunarRandomizer` app (or a Python unified launcher) so users can randomize both PSX and GBA from one interface.
