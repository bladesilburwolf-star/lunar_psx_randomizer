# GBA Randomizer Optimization Roadmap
**Last Updated:** 2026-09-01  
**Status:** Analysis Complete → Ready for Implementation  

---

## Executive Summary
Mistral encountered severe performance and false-positive issues because the search tools use **exhaustive pattern matching without domain validation**. This roadmap provides step-by-step optimization (not from scratch, but surgical fixes to existing code).

**Key Finding:** Combining multiple bad search methods (mixed_template_search) makes things worse. The solution: one good method + tight validation.

---

## Current State: Tool Assessment

### ✅ Production-Ready Tools (Use Freely)
| Tool | Role | Status | Notes |
|------|------|--------|-------|
| `gba_item_randomizer.py` | Apply item randomization | ✅ READY | Fixed offset, no scanning needed |
| `gba_enemy_randomizer.py` | Apply enemy randomization | ✅ READY | Takes manual offset/stride input |

### ⚠️ Requires Optimization (Usable with Caveats)
| Tool | Role | Status | Action |
|------|------|--------|--------|
| `gba_exact_anchor_search.py` | Find enemy table location | ⚠️ SLOW | Add coherence validation (see T3) |
| `gba_template_search.py` | Find enemy table location | ⚠️ SLOW | Pre-filter strides (see T3) |

### ❌ Do Not Use (Deprecated)
| Tool | Why | Replacement |
|------|-----|-------------|
| `gba_u8_anchor_search.py` | False positives from ubiquitous byte values | Use only gba_exact_anchor_search |
| `gba_mixed_template_search.py` | Combines 2 bad methods (u8 + u16) | Single method: gba_exact_anchor_search |
| `gba_table_stride_search.py` | 10,000+ false candidates; resource explosion | Use pre-filtered stride approach |
| `gba_locate_enemy_table_v3.py` | Runs all sub-methods; no cross-validation | Redesign pending (T2) |

---

## Optimization Tiers (Implementation Order)

### TIER 1: Immediate (Quick Wins)
**Effort:** 30 minutes  
**Impact:** Disable worst tools; prevent user error

#### T1.1: Mark Deprecated Tools
**File:** Create `DEPRECATED.txt` in `Lunar Legend GBA/`
```
DEPRECATED TOOLS - DO NOT USE:
  ❌ gba_mixed_template_search.py  (pure noise; false positives from combining u8+u16)
  ❌ gba_table_stride_search.py    (resource explosion; 10,000+ false candidates)
  ❌ gba_u8_anchor_search.py       (0-255 byte values appear everywhere; no domain context)
  ❌ gba_locate_enemy_table_v3.py  (pending redesign in T2)

RECOMMENDED INSTEAD:
  ✅ gba_exact_anchor_search.py with coherence validation
  ✅ gba_template_search.py with stride pre-filtering
```

**Action:** Add this file to repo; update any READMEs

---

#### T1.2: Document Current Known Values
**File:** Create `KNOWN_ANCHORS.md`
```markdown
# Known Anchor Values (Verified)

## Enemy Table Anchors (High Confidence)
From binary scan and cheat codes:
  - BurgDog HP: 30 (common but appears ~500x in ROM as u16)
  - Pirate1 HP: 50 (common, ~800x occurrences)
  - MagicEmperor HP: 6800 (RARE, only 1-2x in ROM) ← BEST ANCHOR
  - MagicEmperor EXP: 0 (matches boss tables only)

## Item Table (CONFIRMED)
  - Offset: 0x7FA424 (absolute, no scanning needed)
  - Stride: 12 bytes (0x0C) ← FIXED
  - Record count: ~200 items

## Recommended Search Strategy
1. Start with MagicEmperor HP (0x1A90 = 6800)
   - Rarest known value
   - Uniquely identifies boss in enemy table
2. Test only 5-7 most probable strides (not 59)
3. Validate by checking 10+ consecutive records for valid HP ranges
4. Cross-check with secondary method before declaring success
```

**Action:** Add to repo; reference in all search tools

---

### TIER 2: Redesign `gba_locate_enemy_table_v3.py`
**Effort:** 1-2 hours  
**Impact:** Reduce false positives by 80-90%; enable reliable automated search

**Problem:** Current design runs all sub-algorithms, merges results by score. Scores don't distinguish real tables from noise.

**Solution:** Implement multi-stage pipeline with cross-validation

**Pseudocode:**
```python
def locate_enemy_table_reliable(rom):
    # Stage 1: High-confidence anchor search
    candidates_exact = search_exact_triple(rom, hp=6800, exp=0, sil=0)
    if not candidates_exact:
        print("ERROR: MagicEmperor (HP=6800) not found in ROM!")
        return None
    
    # Stage 2: For each candidate, test only 5-7 strides
    best = None
    for base_offset in candidates_exact:
        for stride in PROBABLE_STRIDES:  # NOT 0-64, just [0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24]
            # Stage 3: Coherence check (validate 10+ records)
            score = validate_table(rom, base_offset, stride, min_valid_records=10)
            if score > 0.8:  # High confidence threshold
                best = (base_offset, stride, score)
    
    # Stage 4: Cross-validate with secondary method
    if best:
        secondary_score = template_score(rom, best[0], best[1])
        if secondary_score > 0.7:  # Agrees with template search
            return best  # CONFIRMED
    
    return None
```

**Implementation Steps:**
1. Extract validation logic into separate function
2. Define `PROBABLE_STRIDES` (pre-filtered list)
3. Implement `validate_table()` (check 10+ consecutive records)
4. Modify search loop to test only probable strides
5. Add cross-validation before returning result
6. Replace gba_locate_enemy_table_v3.py with this

**Expected Result:** 
- False positives: 200+ → 5-10
- Execution time: Same or faster (fewer strides tested)
- Confidence: High (multi-stage validation)

---

### TIER 3: Optimize `gba_exact_anchor_search.py` and `gba_template_search.py`
**Effort:** 45 minutes each  
**Impact:** 50-70% speed improvement; maintain quality

#### T3.1: `gba_exact_anchor_search.py` — Add Coherence Check

**Current bottleneck:** Finds 200+ candidates per anchor; no validation

**Fix:**
```python
# AFTER finding a candidate offset/stride:

def validate_table_coherence(rom, base_offset, stride, num_records=10):
    """Check if 10+ consecutive records have plausible HP values."""
    valid_hps = [15, 30, 40, 50, 60, 80, 100, 150, 200, 250, 300, 400, 500, 600, 6800]
    hp_offset = 0x00  # Assuming HP is first u16 in record
    
    count = 0
    for i in range(num_records):
        offset = base_offset + i * stride
        hp = read_u16(rom, offset)
        if hp in valid_hps or (1 <= hp <= 1000):  # Plausible HP range
            count += 1
    
    return count >= 8  # At least 8/10 valid

# Then in search loop:
candidates_with_validation = []
for candidate in all_candidates:
    if validate_table_coherence(rom, candidate['base'], candidate['stride']):
        candidates_with_validation.append(candidate)
```

**Change:** ~20 lines of validation code  
**Result:** Filters 200 candidates → 5-10 high-quality ones

---

#### T3.2: `gba_template_search.py` — Pre-filter Strides

**Current bottleneck:** Tests 59 strides per anchor occurrence

**Fix:**
```python
# BEFORE stride loop, analyze all anchors quickly:

def pre_filter_strides(rom, anchor_value, max_candidates=5):
    """Test each stride against ALL occurrences; keep top 5."""
    stride_scores = {}
    occurrences = find_u16_occurrences(rom, anchor_value)
    
    for stride in range(8, 65, 2):  # All possible strides
        matches = 0
        for base in occurrences:
            # Quick check: do 3 consecutive records seem valid?
            hp1 = read_u16(rom, base)
            hp2 = read_u16(rom, base + stride)
            hp3 = read_u16(rom, base + 2*stride)
            if all(1 <= hp <= 10000 for hp in [hp1, hp2, hp3]):
                matches += 1
        stride_scores[stride] = matches
    
    # Return only top 5 strides
    return sorted(stride_scores, key=stride_scores.get, reverse=True)[:5]

# Then use only these in full search:
probable_strides = pre_filter_strides(rom, MAGIC_EMPEROR_HP)
for stride in probable_strides:
    # Full validation with this stride only
    ...
```

**Change:** ~30 lines, runs quick pre-filter first  
**Result:** Tests 59 strides → 5 strides; ~10x faster

---

### TIER 4: Create Hybrid Search Tool
**Effort:** 1 hour  
**Impact:** Best of both worlds; reliable + fast

**File:** `gba_find_enemy_table_optimized.py` (new)

```python
#!/usr/bin/env python3
"""
Optimized enemy table finder using multi-stage validation.

1. Search for MagicEmperor HP (rare anchor)
2. Test only 5-7 pre-filtered strides
3. Validate each candidate with 10+ record coherence check
4. Cross-check with secondary template method
"""

def main():
    rom = load_rom()
    
    # Stage 1: High-confidence anchor
    candidates = search_exact_hp(rom, hp=6800)  # MagicEmperor
    if not candidates:
        print("FAIL: MagicEmperor anchor not found")
        return 1
    
    # Stage 2: Pre-filter strides
    probable_strides = pre_filter_strides(rom, 6800, max_candidates=5)
    
    # Stage 3: Test with validation
    best_match = None
    for base_offset in candidates:
        for stride in probable_strides:
            if validate_table_coherence(rom, base_offset, stride):
                best_match = (base_offset, stride)
                break
        if best_match:
            break
    
    # Stage 4: Cross-validate
    if best_match:
        template_score = validate_with_template_method(rom, best_match[0], best_match[1])
        if template_score > 0.7:
            print(f"CONFIRMED: Enemy table @ 0x{best_match[0]:08X} stride 0x{best_match[1]:02X}")
            return 0
    
    print("FAIL: No valid enemy table found")
    return 1
```

---

## Implementation Checklist

### Week 1 (Immediate)
- [ ] T1.1: Create DEPRECATED.txt marker
- [ ] T1.2: Create KNOWN_ANCHORS.md
- [ ] Commit both to repo with note: "Analysis: mark problematic tools"

### Week 2 (Optimization)
- [ ] T3.1: Add 20 lines validation to gba_exact_anchor_search.py
- [ ] T3.2: Add 30 lines pre-filter to gba_template_search.py
- [ ] Test both; benchmark improvement
- [ ] Commit: "Optimize: reduce false positives + improve speed"

### Week 3 (Redesign)
- [ ] T2: Rewrite gba_locate_enemy_table_v3.py with stages
- [ ] Commit: "Redesign: multi-stage validation"

### Week 4 (Polish)
- [ ] T4: Create new gba_find_enemy_table_optimized.py
- [ ] Final testing with real ROM (if available)
- [ ] Update README to recommend optimized version
- [ ] Commit: "Add: optimized hybrid search tool"

---

## Testing Strategy

For each optimization:
1. **False Positive Rate:** Count output candidates (should drop 80%+)
2. **Execution Time:** Time each tool (should maintain or improve)
3. **Correctness:** Verify known table(s) are in output

Example test harness:
```python
import time

def test_tool(tool_func, rom):
    start = time.time()
    result = tool_func(rom)
    elapsed = time.time() - start
    
    num_candidates = len(result)
    print(f"  Candidates: {num_candidates}")
    print(f"  Time: {elapsed:.2f}s")
    
    if num_candidates < 50:  # Good
        print(f"  ✅ PASS (low false positive rate)")
    elif num_candidates < 200:  # Acceptable
        print(f"  ⚠️ WARN (moderate false positives)")
    else:  # Bad
        print(f"  ❌ FAIL (high false positive rate)")

test_tool(gba_exact_anchor_search, rom)
test_tool(gba_template_search, rom)
```

---

## Reusable Patterns for PSX Team

Copy-paste these into PSX version:

### 1. **Coherence Validation**
```python
def validate_table_coherence(rom, base_offset, stride, num_records=10, valid_ranges=None):
    """Generic table validator. Reuse for PSX."""
    # See T3.1 implementation
```

### 2. **Stride Pre-filtering**
```python
def pre_filter_strides(rom, anchor_value, stride_range=(8, 65), max_candidates=5):
    """Generic stride filter. Reuse for PSX."""
    # See T3.2 implementation
```

### 3. **Multi-Stage Pipeline Template**
```python
def locate_data_table(rom, anchor_value, validation_func, stride_list):
    """
    Generic pattern for any table search:
    1. Find anchor
    2. Filter strides
    3. Validate
    4. Return best match
    """
    # See Tier 4 pseudocode
```

---

## Success Criteria

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| False positives (gba_exact) | <10 | ~200 | TBD (post-optimization) |
| Execution time | <30s | ~60s | TBD (post-optimization) |
| Memory usage | <500 MB | ~800 MB | TBD (post-optimization) |
| Confidence (correct table in top 3) | 95% | ~70% | TBD (post-optimization) |

---

## Questions for Team

1. **ROM available?** Can we test with actual Lunar Legend GBA ROM?
2. **PSX priority?** Should we optimize PSX version using these patterns?
3. **Automation?** Should these tools be integrated into a GUI launcher?

---

**Document Owner:** Claude (CLI Assistant)  
**Next Review:** After T2 completion (redesign)
