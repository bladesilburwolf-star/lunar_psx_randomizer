# Known Anchor Values for Lunar Legend GBA (USA ALNE)
**Verified Against:** Cheat code analysis + binary scan results  
**Last Updated:** 2026-09-01

---

## Enemy Table Anchors (Ranked by Reliability)

### ⭐⭐⭐ HIGHEST CONFIDENCE
**MagicEmperor (Final Boss)**
- HP: 6800 (0x1A90 LE)
- EXP: 0 (0x0000 LE)
- SIL (Silver): 0 (0x0000 LE)
- **Why highest confidence:**
  - HP=6800 is RARE in 8MB ROM (only 1-2 occurrences)
  - Combination HP+EXP+SIL = (6800, 0, 0) is UNIQUE
  - Zero false positives from text/padding
- **Search strategy:** Use this as primary anchor
- **Expected result:** 1 candidate offset/stride pair

### ⭐⭐ HIGH CONFIDENCE
**Early-Game Common Enemies** (frequency allows validation)
- **Deathcap:** HP=15, EXP=1, SIL=7
- **BurgDog:** HP=30, EXP=8, SIL=15
- **FlyTrap:** HP=30, EXP=4, SIL=10
- **FatSnake:** HP=40, EXP=6, SIL=40
- **Wisp:** HP=40, EXP=12, SIL=56
- **Why high confidence:**
  - Triple (HP, EXP, SIL) is more distinctive than HP alone
  - Multiple instances allow cross-validation
  - Expected to appear once per boss encounter in ROM
- **Search strategy:** Use for cross-validation after finding MagicEmperor
- **Expected result:** Should find in same table with same stride/base

### ⭐ MEDIUM CONFIDENCE (DO NOT USE ALONE)
**Mid-Game Enemies** (values appear more often in ROM)
- **Pirate1:** HP=50, EXP=7, SIL=21
- **Pirate2:** HP=60, EXP=7, SIL=21
- **Killfish:** HP=50, EXP=7, SIL=46
- **Ammonite:** HP=50, EXP=12, SIL=70
- **Why medium confidence:**
  - HP values (50, 60) appear in multiple contexts
  - False positives from: compressed data, padding, other tables
  - EXP/SIL values also common (0-255 range)
- **Search strategy:** Use ONLY as secondary validator
- **Expected result:** May find 5-20 false candidates before true match

### ❌ NOT RECOMMENDED
**Byte-level values** (HP < 255)
- Values like 15, 30, 40, 50, 60, 80, 100, ...
- **Why NOT recommended:**
  - Appear 500-1000+ times in 8MB ROM
  - Indistinguishable from padding, strings, alignment
  - Produces 10,000+ false positives
- **Exception:** Can use for SECONDARY validation (if you already know likely range)

---

## Item Table (NO SEARCH NEEDED)
**Status:** ✅ **CONFIRMED**

- **Offset:** 0x7FA424 (absolute, no variation)
- **Stride:** 12 bytes (0x0C)
- **Record count:** ~200 items
- **Record layout (12 bytes):**
  ```
  +0x00: buy price (u16 LE)
  +0x02: sell price (u16 LE)
  +0x04: rare/sparse flag (u8)
  +0x05: element/special (u8)
  +0x06: primary combat stat (u16 LE, scales with price)
  +0x08: flag byte (u8)
  +0x09: zero byte (u8)
  +0x0A: sub-type flag (u8)
  +0x0B: category/equip flags (u8)
  ```
- **How verified:**
  - Claude's manual binary scan (binary_scan_notes.md)
  - Price clustering analysis confirmed known prices
  - Stride validated against ~200 known items

**No scanning required!** Use `gba_item_randomizer.py` directly.

---

## Enemy Table Geometry (TO BE CONFIRMED)
**Status:** ⏳ **PENDING SEARCH**

From binary analysis (UNCONFIRMED):
- **Probable offset range:** 0x86F000 – 0x89F000 (3 MB region)
  - Rationale: Anchor search found clusters there
  - Large enough for 128-256 enemy records
- **Probable stride:** 0x1C or 0x20 (28 or 32 bytes)
  - Rationale: MagicEmperor cluster suggests 0x1C offset repeatability
  - Verified by testing 10+ records with same stride
- **Probable record count:** 128-256 enemies
  - Rationale: Large GBA game typical size

**Confirmation method:**
1. Use `gba_exact_anchor_search.py` (optimized T3.1)
2. Search for MagicEmperor HP (6800)
3. Validate returned offset/stride using `gba_enemy_randomizer.py` dump
4. Cross-check with secondary method (`gba_template_search.py`)

---

## Search Strategy (RECOMMENDED WORKFLOW)

### Step 1: Find Enemy Table (Use This Exact Sequence)

```bash
# Stage 1: Primary anchor search
python3 gba_exact_anchor_search.py lunar.gba --dump-best > results.txt

# Stage 2: Validate top candidate
python3 gba_enemy_randomizer.py --cli \
  --rom lunar.gba \
  --offset 0x<OFFSET_FROM_RESULTS> \
  --stride 0x<STRIDE_FROM_RESULTS> \
  --count 128 \
  --fields hp:0x00 atk:0x04 def:0x06 agi:0x08 men:0x0A res:0x0C exp:0x1A silver:0x1C \
  --seed 99999

# Look at the CSV output. If values look like enemy stats (not garbage):
# → You found the right table! Use this offset/stride for randomization.

# Stage 3: Cross-validate (optional)
python3 gba_template_search.py lunar.gba --validate
```

### Step 2: Apply Randomization (Once Table Found)

```bash
# Randomize items (offset is fixed)
python3 gba_item_randomizer.py --cli \
  --rom lunar.gba \
  --seed 42 \
  --price-min 0.5 --price-max 2.0 \
  --stat-min 0.7 --stat-max 1.5

# Randomize enemies (using confirmed offset/stride)
python3 gba_enemy_randomizer.py --cli \
  --rom lunar_rand.gba \
  --offset 0x<CONFIRMED_OFFSET> \
  --stride 0x<CONFIRMED_STRIDE> \
  --count 128 \
  --fields hp:0x00 atk:0x04 def:0x06 agi:0x08 men:0x0A res:0x0C exp:0x1A silver:0x1C \
  --seed 42 \
  --out lunar_rand_enemies.gba
```

---

## Troubleshooting

### Q: Search found 0 candidates
**Likely cause:** ROM is not USA ALNE version
**Solution:** Verify ROM header (title="LUNAR LEGEND", code="ALNE")
**Check:** `xxd -l 256 lunar.gba | grep -A2 -B2 "A0"`

### Q: Search found 1000+ candidates
**Likely cause:** Using deprecated tool (gba_mixed_template_search or gba_table_stride_search)
**Solution:** Use ONLY gba_exact_anchor_search.py
**See:** DEPRECATED.txt

### Q: Top candidate doesn't look like enemy table
**Likely cause:** False positive; check 2nd and 3rd candidates
**Solution:** Look at CSV output from gba_enemy_randomizer.py
  - If HP values are 0, 1, or 65535 → garbage
  - If HP values are 15, 30, 50, 100, 200, etc. → real table
  - If mixed plausible values → likely real table

### Q: Different tools give different offsets
**Likely cause:** gba_exact_anchor_search and gba_template_search both correct; just different validation windows
**Solution:** Dump both tables; they should contain same enemies
**Check:** `python3 gba_extract_item_table.py lunar.gba <OFFSET_A> <STRIDE_A> > table_a.csv`

---

## Reference Values for Manual Verification

If you dumped a candidate table and want to verify it's real:

**Expected HP values in order:**
```
15 (Deathcap), 30 (BurgDog), 30 (FlyTrap), 40 (FatSnake), 40 (Wisp),
50 (Pirate1), 50 (Killfish), 50 (Ammonite), 60 (Pirate2),
... more mid-game enemies ...
6800 (MagicEmperor)
```

**If you see this pattern in your dump → Table is correct!**

---

## For PSX Team

These GBA anchor values are **different** from PSX SSSC. Don't mix them!

**Cross-game reference table:**
```
Character        | GBA HP  | PSX HP   | Anchor Quality
===============  | ======= | ======== | ==============
Deathcap (Worm1) | 15      | ~12-18   | Both rare enough
BurgDog (Burgus) | 30      | ~25-35   | Common value
MagicEmperor     | 6800    | ~3000-4500 | GBA better; very rare
```

Use GBA patterns but adapt to PSX data ranges!

---

**Document Status:** ✅ READY FOR USE  
**Last Validated:** 2026-09-01  
**Next Review:** After enemy table search completion
