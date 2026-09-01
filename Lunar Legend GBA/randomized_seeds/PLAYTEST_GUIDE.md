# 🎮 Quick Start: Testing Randomized ROMs

## Option 1: Quick Playtest (5-10 minutes)

### For Linux/Mac (with emulator in PATH):
```bash
cd ~/copilot-worktrees/lunar_psx_randomizer/bladesilburwolf-star-super-sniffle/"Lunar Legend GBA"/randomized_seeds

# Start with balanced difficulty
visualboyadvance lunar_rand_seed_42.gba &

# Or try hard mode
visualboyadvance lunar_rand_seed_99999.gba &
```

### For Windows (Visual Boy Advance):
1. Open `Visual Boy Advance`
2. File → Open
3. Navigate to: `randomized_seeds/lunar_rand_seed_42.gba` (or your chosen seed)
4. Start playing!

---

## Option 2: Quick Verification (Check if Randomization Worked)

```bash
# View first enemy in both original and seed 42:
head -3 lunar_rand_seed_42.csv

# Expected output:
# index,offset,hp_old,atk_old,...,hp_new,atk_new,...
# 0,0x8d200,397,399,...,<DIFFERENT_VALUE>,...

# Stats should be different in _new columns vs _old columns
```

---

## Option 3: Compare Two Seeds Side-by-Side

```bash
# See how seed 42 and seed 99999 differ:
python3 seed_compare.py 42 99999

# Compare a specific enemy (e.g., enemy #5):
python3 seed_compare.py 42 99999 --enemy 5
```

---

## Expected Behavior in Game

### Visual Indicators Randomization Worked:
- ✅ Enemy HP bars are different from original run
- ✅ Battles take slightly different number of turns to win
- ✅ Enemy attack patterns might differ (stat-based)
- ✅ Experience/silver rewards different (randomized in table)

### What Should NOT Happen:
- ❌ Game crashes on enemy encounter
- ❌ Enemy stats are 0 or 65535 (corrupted)
- ❌ Only first enemy is different (others untouched)

---

## Recommended Test Route

1. **Start new game**
2. **First battle (Training Dungeon)** — Weakest enemy
   - Should randomize normally
   - HP should vary from original
3. **Few more battles** — Check variety of enemies
   - Different enemy types should have different stat changes
   - No crashes or visual glitches
4. **Save/exit** — Stop playtest

**Total time:** ~5-10 minutes

---

## Seed Recommendations

- **First test:** Seed 42 or 777 (moderate changes)
- **Casual playthrough:** Seed 2026 (minimal change, balanced)
- **Challenge run:** Seed 1337 or 99999 (significant difficulty)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| ROM won't load in emulator | Verify file size: `ls -lh lunar_rand_seed_*.gba` should show 8.0M |
| Game crashes on enemy encounter | Enemy table offset may be wrong (confirm in ENEMY_TABLE_CONFIRMED.md) |
| Stats look too high/low | Check CSV report for that seed, see if values are plausible |
| Can't find emulator | Install: `visualboyadvance` or `mgba` via package manager |

---

## Files Ready to Use

```
randomized_seeds/
├── SEED_VARIANTS.md .............. Full documentation (you are here)
├── seed_compare.py ............... Seed comparison tool
├── lunar_rand_seed_42.gba ........ ROM: Seed 42 (balanced)
├── lunar_rand_seed_42.csv ........ Stats report: Seed 42
├── lunar_rand_seed_777.gba ....... ROM: Seed 777 (easier)
├── lunar_rand_seed_777.csv
├── lunar_rand_seed_99999.gba ..... ROM: Seed 99999 (hard mode)
├── lunar_rand_seed_99999.csv
└── ... (4 more seed variants)
```

---

**Ready to test?** Pick a seed and start playing! 🎮
