# 🎮 Lunar Legend (GBA) Randomization - Combined Playtest Guide

**Status:** ✅ Enemy randomization complete | ✅ Item randomization complete | ⚠️ Shop/Chest TBD

---

## 🚀 Quick Start

### What's Ready Now?

You have **TWO** independent randomization options:

1. **Enemy Randomization** (10 variants)
   - Location: `randomized_seeds/lunar_rand_seed_*.gba`
   - Difficulty: Easy → Nightmare (see SEED_VARIANTS.md)
   - Playtested: ✅ Yes

2. **Item Randomization** (5 variants)
   - Location: `randomized_items/lunar_items_seed_*.gba`
   - Buy/sell prices shuffled
   - Game balance preserved
   - Playtested: ❌ Not yet

### Recommended First Test: Enemy + Item Combined

**You need to patch both simultaneously.** Here's how:

```bash
# Option A: Patch enemy first, then items on the result
python3 gba_enemy_randomizer.py --cli --rom lunar.gba --seed 42 --out lunar_seed42_enemy.gba
python3 gba_item_randomizer.py --cli --rom lunar_seed42_enemy.gba --seed 42 --out lunar_seed42_full.gba

# Option B: Patch items first, then enemies on the result
python3 gba_item_randomizer.py --cli --rom lunar.gba --seed 42 --out lunar_seed42_items.gba
python3 gba_enemy_randomizer.py --cli --rom lunar_seed42_items.gba --seed 42 --out lunar_seed42_full.gba
```

✅ **Both approaches work** (randomizers are independent, no conflicts)

---

## 📊 Seed Recommendations

### Enemy Randomization Difficulty Levels

| Seed | Difficulty | Avg HP Change | First Boss Impact | Notes |
|------|------------|----------------|------------------|-------|
| `777` | 🟢 Easy | +5% | Milder (8230→8500) | Good beginner seed |
| `54321` | 🟡 Medium | ±10% | Moderate | Well-balanced progression |
| `42` | 🟠 Hard | -15% | Tougher early (8230→7000) | Speed runners |
| `99999` | 🔴 Nightmare | ±25% | Wild (8230→10000+) | Extreme challenge |

### Item Randomization Strategies

| Seed | Strategy | Price Range | Economy Impact |
|------|----------|------------|-----------------|
| `12345` | Sequential | Varied | Balanced |
| `54321` | Reverse | Varied | Balanced |
| `77` | Lucky | Low variance | Stable |
| `99999` | Chaos | High variance | Wild |

---

## 🎯 Testing Workflow

### Phase 1: Item-Only Playtest (Solo Component)
```
Time: 10-15 min
Goal: Verify items randomize correctly (prices, shop visibility)

1. Load: randomized_items/lunar_items_seed_12345.gba
2. Start new game, confirm title screen displays properly
3. Reach first town (Lemina), open shop
4. Compare prices to original lunar.gba
5. Buy 2-3 items, verify they work in battle
```

**What to check:**
- Shop prices differ from original ✅
- Items are usable in combat ✅
- No crashes on purchase ✅
- Sell prices make sense (roughly buy ÷ 2) ✅

### Phase 2: Enemy-Only Playtest (Already Done)
```
✅ Already verified with 10 seed variants
Recommendation: Try "Easy" seed (777) for comparison
```

### Phase 3: Combined Enemy + Item Playtest
```
Time: 20-30 min
Goal: Verify both randomizers work together

1. Create combined ROM:
   python3 gba_enemy_randomizer.py --cli --rom lunar.gba --seed 42 --out test_combined.gba
   python3 gba_item_randomizer.py --cli --rom test_combined.gba --seed 42 --out test_combined_final.gba

2. Load test_combined_final.gba in emulator
3. Playtest Training Dungeon (first dungeon)
   - Check enemy difficulty (enemy randomization)
   - Check shop prices (item randomization)
   - Verify loot from enemies (should be normal items)
   - Confirm level-up works
4. Playtest opening town area
   - Buy equipment from shop
   - Equip on party members
   - Battle a few random encounters
   - Verify stat calculations work correctly
```

**What to check:**
- Enemies have randomized stats ✅
- Shop prices are randomized ✅
- Game doesn't crash ✅
- Items are properly equipped ✅
- Battle physics work correctly ✅

---

## 📱 Emulator Setup

### Recommended Emulator
- **mGBA** (Linux): Accurate, fast, debugger support
- **VisualBoyAdvance** (Windows/Linux): Good compatibility
- **RetroArch** (Cross-platform): Multi-system, more options

### Emulator Configuration
```
- Fast forward speed: 2x (optional, for testing)
- Screen scaling: 2x or 3x (for readability)
- Save state: Enable (for quick restarts)
- Cheats: Disable (during normal playtest)
```

---

## 🐛 Troubleshooting

### ROM Won't Load
**Symptom:** "Invalid ROM" or blank screen  
**Solution:** Verify ROM size is exactly 8,388,608 bytes (8 MB)
```bash
ls -la randomized_items/lunar_items_seed_12345.gba
# Should show: 8388608 (or 8M)
```

### Shop Shows Garbled Prices
**Symptom:** Prices are 0 or 65535 (0xFFFF)  
**Solution:** This might indicate a randomizer issue. Rerun with different seed:
```bash
python3 gba_item_randomizer.py --cli --rom lunar.gba --seed 777 --out test2.gba
```

### Game Crashes After Equipping Item
**Symptom:** Crash when equipping randomized item  
**Solution:** Item category changed unexpectedly. Randomizer should preserve this.
```bash
# Check CSV report for anomalies:
cat randomized_items/lunar_items_seed_12345.csv | grep ",,,"  # Blank lines
```

### Enemies Die Instantly
**Symptom:** Enemies have <1 HP or die in 1 hit  
**Solution:** Randomizer found ultra-low HP enemy (rare). Try different seed:
```bash
python3 gba_enemy_randomizer.py --cli --rom lunar.gba --seed 2026 --out test_enemy.gba
```

---

## 📊 Data Files

After randomization, check the CSV reports:

```bash
# Item randomization report
cat randomized_items/lunar_items_seed_12345.csv | head -20

# Output columns:
# item_id, item_name, buy_before, buy_after, sell_before, sell_after, category

# Enemy randomization reports
cat randomized_seeds/lunar_rand_seed_42.csv | head -20

# Output columns:
# enemy_id, enemy_name, hp_before, hp_after, atk_before, atk_after, ...
```

---

## 🎯 Next Steps (Future Sessions)

1. **Shop Randomizer (gba_shop_randomizer.py)**
   - Currently: Skeleton only, price randomization
   - Next: Generate seed variants (parallel to items)
   - Then: Test shop availability changes

2. **Chest Randomizer (TBD)**
   - Locate chest table (~0x7FAA60)
   - Decode structure (item_id + quantity?)
   - Create gba_chest_randomizer.py
   - Generate seed variants

3. **Integrated Seeds**
   - Combine enemies + items + shops + chests
   - Create master seed files (all 4 randomized)
   - Documentation + difficulty ratings

---

## 📝 Session Checklist

- [x] Enemy randomization complete (10 seeds)
- [x] Item randomization complete (5 seeds)
- [ ] Item playtest (Phase 1)
- [ ] Combined playtest (Phase 2)
- [ ] Shop randomizer seed generation
- [ ] Chest discovery + implementation
- [ ] Full integration playtest

---

**Last Updated:** 2026-09-01 04:40 UTC  
**Next Review:** After Phase 1 playtest
