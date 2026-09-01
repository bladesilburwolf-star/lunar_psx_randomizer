# GBA enemy table search — consolidated status

## Bottom line: not found after 8 rounds. Stop pattern-brute-forcing it.

Confirmed working, still in the main folder:
- `gba_extract_item_table.py` — item table @ 0x7FA424, 200 records x 12 bytes. Solid.
- `gba_item_randomizer.py` — price + ATK/DEF stat randomizer. Solid, tested.
- `gba_enemy_randomizer.py` — ready to use, but needs a confirmed table
  offset/stride plugged in before it does anything real.

Everything else that was tried lives in `archive_failed_searches/` now,
kept for reference but not meant to be run again as-is.

## Why this is genuinely a harder search than the tables that worked

The PSX enemy table, PSX item table, and GBA item table were all found
because they have a **strong self-verifying invariant** you can check
computationally: PSX items have `sell == buy // 2` on literally every
record, and the PSX item ATK byte was confirmed by cross-referencing the
GBA item table's own ATK stat, 20/20 exact matches. Those invariants let a
scoring scan zero in on the right offset with real confidence, fast.

Enemy stats don't have an equivalent invariant. "Is this a plausible HP
value" is true for a huge fraction of all possible byte/short values, so
any scan built on that alone is inherently noisy — you either get zero
results (filter too strict) or tens of thousands of results (filter too
loose), and every round of this search hit one of those two failure
modes.

## What was tried (all 8 rounds)

1. Blind full-ROM u16 scan → false positives (shop/drop tables)
2. Full-ROM blind scan, take 2 → hit growth/level tables, not enemy stats
3. Deathcap HP=15 anchor → far too common a value, flooded the whole ROM
4. Focused anchors, ±64 byte window → 28K hits, best cluster was graphics data
5. Exact u16 triple search (HP/EXP/SIL together) → 365 hits, no consistent pattern
6. u8-width anchor search → never converged
7. Template matching against Magic Emperor's HP=6800 → never converged
8. (this session) Cheap, bounded stride search anchored on the same
   Magic Emperor HP=6800 value, properly excluding contamination from the
   known item table region → the one "hit" it initially found was 100%
   the item table's own bytes being re-detected; after excluding those,
   zero clean results. One weak 3-exact-match sequence turned up on a
   forward search but it's mostly zero-padding with scattered coincidental
   matches, not a real table pattern. Not worth pursuing further.

## Confirmed real finding worth keeping: the Magic Emperor anchor

HP=6800 (0x1A90) appears **exactly once** in the entire ROM near the
0x7Fxxxx data section, at `0x7FADCC` — 72 bytes after the item table ends
(0x7FAD84). That specific value/location is real and unique, it just
hasn't led to a confirmed table via pattern search. It might still be
useful as a starting point for disassembly (see below), since knowing
*where* a real stat value lives is a good place to look for the *code*
that reads it.

## Performance bug worth knowing about (now archived, don't resurrect)

`gba_table_stride_search.py` had a 6-deep nested loop: for every anchor
position hit, for every stride (61), for every offset-in-record (up to
63), for every record slot (31), for every known enemy (9), for every
comparison record (31) — with even ~100 anchor hits that's on the order
of **3 billion pure-Python inner iterations**. That would run for hours
to days and likely never practically finish. This is almost certainly
what "going in circles / eating PC resources" was actually caused by —
not bad luck, an real algorithmic complexity bug. If any future search
script uses nested loops like this, add early-exit / vectorize with
numpy, or bound the total iteration count up front and print an estimate
before running.

## Recommended path forward (pick one, don't blindly try more variants)

**Option A — Ghidra disassembly.** The only untried approach with a
principled reason to actually work: find the real code that loads
whatever data structure backs a monster in battle, which gives the true
offset directly instead of guessing from the data side. Known blocker:
full ROM auto-analysis + decompile OOMs in a constrained (~2-4GB)
environment. Workaround options: run on a machine with real RAM (8GB+),
or do a *scoped* Ghidra pass (disassembly only, no decompiler, and/or
only auto-analyze the region around the Magic Emperor anchor / item
table rather than the whole 8MB ROM).

**Option B — Deprioritize.** The GBA enemy table isn't blocking anything
currently shippable. Its main proven value so far (cross-referencing the
PSX item ATK byte) is already banked. The PSX enemy and item randomizers
work standalone. If GBA enemy stats aren't needed for a specific near-term
goal, this can sit until there's a good reason to pick it back up (e.g. if
someone gets a working Ghidra setup with enough RAM).

**Not recommended:** another round of hand-tuned pattern/anchor search.
Eight attempts across two different research threads (GLM/Mistral's seven
plus this session's) have now covered blind scanning, anchor-based
scanning, u8 and u16 widths, template matching, and a properly
contamination-filtered targeted search. This specific technique has been
given a fair shot and it isn't converging.
