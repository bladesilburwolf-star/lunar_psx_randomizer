# Lunar Randomizer — project notes (kept)

## Layout

```
LunarRandomizer/
  LunarRandomizer.jar     # multi-tab GUI (run this)
  build.sh
  data/psx/               # enemy_master.bin, item_master.bin, SLUS_006.28
  tools/psx/              # extract + gearbolt + patch scripts
  tools/gba/              # GBA item scripts + lunar.gba
  tools/disc/             # bincue_gui, tuximage, lunadata_gui
  docs/                   # research (PSX item, GBA, r2, Ghidra)
  src/                    # Java sources
```

## PSX (Silver Star Story Complete)

| Table | Decomp EXE offset | Record | Notes |
|-------|-------------------|--------|-------|
| Enemies | 0x97F68 | 128 × 38 bytes | HP/ATK/DEF/EXP/Silver |
| Item economy | 0x99244 | 72 × 18 bytes | buy/sell; sell = buy//2 |

ATK/DEF on equipment is a **separate** table (not in economy records).

Patch order: enemies first, then items on the same decompressed EXE, then inject SLUS once.

## GBA (Lunar Legend USA ALNE)

| Table | ROM offset | Record | Notes |
|-------|------------|--------|-------|
| Items | 0x7FA424 | ~200 × 12 bytes | buy, sell, ATK@+6 combined |
| Shop/drop candidate | 0x7FA8C0 | 16-byte | needs more decode |
| Enemies | unknown | — | pattern search failed; use Ghidra/r2 |

Pointers into item region use **0x087FA418** (not 0x087FA424). Ghidra may mis-disassemble 0x7FA424 as code — undefine and mark data.

## Removed on purpose

- Failed GBA enemy search scripts (`archive_failed_searches`)
- Duplicate randomizer folders at repo root
- Randomized test CSV/bin noise
- Scattered STATUS / binary_scan drafts (superseded by docs/)
