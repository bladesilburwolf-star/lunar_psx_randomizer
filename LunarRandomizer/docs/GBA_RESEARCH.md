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
| Enemy table located | ⏳ Still searching — 5 rounds of u16 search failed | multiple tools |
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

---

## Cheat-code analysis → stat structure

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

### In-battle combatant block

**Base RAM:** `0x02037094` (Position 1), **stride:** `0x190` (400 bytes per combatant slot)

| Field | Offset from slot base | Size |
|-------|---------------------|------|
| HP | +0x00 | u16 |
| MP | +0x04 | u16 |
| SM (special meter) | +0x1C | u8 |

### Other useful RAM addresses

| Address | Meaning |
|---------|---------|
| `0x02002C38` | Money (Silver) |
| `0x02004980` | Item/equipment inventory |
| `0x02004A5D` | Item flags |
| `0x02004DE4` | Cards |
| `0x02004DC8` | Gallery |

---

## Enemy table search history

### Known enemy stats (from Shotgunnova guide, GameFAQs faq/45134)

| Enemy | HP | EXP | SIL | Area |
|-------|-----|-----|-----|------|
| Deathcap | 15 | 1 | 7 | Saith area |
| Burg Dog | 30 | 8 | 15 | — |
| Fly Trap | 30 | 4 | 10 | — |
| Pirate 1 | 50 | 7 | 21 | — |
| Pirate 2 | 60 | 7 | 21 | — |
| Killfish | 50 | 7 | 46 | Meribia Sewers |
| Ammonite | 50 | 12 | 70 | Meribia Sewers |
| FatSnake | 40 | 6 | 40 | Meribia Sewers |
| Wisp | 40 | 12 | 56 | Meribia Sewers |
| Magic Emperor | 6800 | — | — | Final boss |

### Round 1-5 summary

All 5 rounds assumed u16 (2-byte) values. All failed to find a consistent enemy table:
- Round 1: blind scan near item table → false positives (shop/drop tables)
- Round 2: full-ROM blind scan → growth/level tables, not enemy stats
- Round 3: Deathcap anchor (15/1/7) → too common, flooded entire ROM
- Round 4: focused anchors ±64 byte window → 28K hits, best cluster was graphics data
- Round 5: exact u16 triple search → 365 hits, no consistent (exp_off, sil_off) pattern

**Key observation:** The only MagicEmperor (HP=6800=0x1A90) hit in the 0x7Fxxxx data section is at **0x7FADCC**, only 0x48 (72) bytes after the item table ends (0x7FAD84 if 200 records × 12 bytes). This is the primary anchor for the template search.

### Round 6: u8 anchor search (`gba_u8_anchor_search.py`) — PENDING
All previous rounds assumed u16 values. But enemy stats like HP=50, EXP=7, SIL=46 fit in a single byte (u8). This tool searches for exact byte triples within a tight window.

### Round 7: Template matching search (`gba_template_search.py`) — PENDING
Uses the MagicEmperor anchor (HP=6800=0x1A90) and tests whether a table exists at a fixed stride with other records matching known enemy HP values (15, 30, 40, 50, 60). Tests both u16 and u8 modes. Validates by checking EXP/SIL at nearby offsets.

**Run order:**
1. `python gba_template_search.py lunar.gba --dump-best --validate`
2. `python gba_u8_anchor_search.py lunar.gba`
3. `python gba_u8_anchor_search.py lunar.gba --mode mixed`

---

## GBA toolchain

```
Lunar Legend GBA/
├── gba_extract_item_table.py    # dump item table
├── gba_item_randomizer.py       # randomize prices + stats
├── gba_scan_enemy_table.py       # scan ROM for enemy stat table
├── gba_scan_enemy_table_v2.py    # full-ROM blind scan
├── gba_locate_enemy_table.py     # v1 anchor search
├── gba_locate_enemy_table_v3.py  # v3 focused anchor search
├── gba_exact_anchor_search.py    # exact u16 triple search
├── gba_u8_anchor_search.py       # u8 byte-level stat search
├── gba_template_search.py        # template matching against known HP values
├── gba_dump_candidates.py        # multi-region candidate dumper
├── gba_enemy_randomizer.py       # randomize enemy stats, patch ROM
├── RESEARCH_NOTES.md             # this document
├── CLAUDE_NOTES.md               # Claude's original findings
├── STATUS.md                     # Claude's original status (Ghidra)
├── binary_scan_notes.md          # Claude's pointer/price scan
└── gba_item_table_12byte.csv     # Claude's item table dump
```
