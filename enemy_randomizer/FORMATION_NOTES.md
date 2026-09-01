# Monster formation / encounter table research notes

## Goal

Find the data that decides WHICH monster IDs (from the confirmed 128-entry
enemy table at decomp 0x97F68) appear together in a given battle, so we can
shuffle encounter composition -- not just enemy stats.

## Status: not found yet

This is a fundamentally harder search than the enemy/item stat tables were.
Those had a strong self-verifying invariant (`sell == buy // 2`, or level/
HP/ATK falling in narrow FAQ-confirmed ranges) that let a scoring scan zero
in on the right offset with high confidence. Formation data has no
equivalent invariant to check against -- "is this byte a valid enemy ID"
is true for roughly half of all possible byte values, so a naive scan is
extremely noisy.

## What was checked

### 1. D1_BTL / D1_MAP per-stage files

`DISC1_DATA/D1_BTL/BTL_0NN.DAT` (47 files, ~45-95 KB each) and
`DISC1_DATA/D1_MAP/MAP_0NN.BIN` (97 files, similar size) were inspected.
Header bytes (first 32 x u16 LE) show some consistent structure across
files -- e.g. the 2nd value is always `11`, values at fixed positions are
always exactly `0x4000` -- suggesting a directory/header table of some
kind, but the bulk of each file is high-entropy (looks compressed, no
plain-text or obviously-formatted data visible). These are almost
certainly compiled per-stage bundles (background art + sprite refs +
scripts), not a clean formation list. Not pursued further -- reverse
engineering an unknown compressed asset-bundle format is a much bigger
project than the EXE table work, and no public documentation was found
for it (see "Public docs" below).

### 2. Decompressed EXE, statistical scan

Ran a scoring scan of the full decompressed exe payload (690,176 bytes)
across many (stride, slot-count) hypotheses, looking for a "count of
plausible small values" and later a stricter "long run + concentrated
value distribution" test (real formation data should be dominated by a
handful of common early-game enemy IDs, since those monsters get reused
across dozens of random encounters).

- Naive version (byte in 0-127 or 0xFF, single window): **53,524 hits**
  at score>=38/40. Useless -- far too weak a filter.
- Stricter version (run>=100 records, top-5 values cover >=35% of all
  slot uses): 13,481 raw hits, deduplicated to a handful of standout
  regions. Two of the strongest were plain ASCII text in the exe (e.g.
  bytes spelling out words -- values 97/101/110/116/111/114 = 'a','e',
  'n','t','o','r'), correctly identified and discarded as false
  positives. Two others were narrow-range (2-8, or 1-2 dominating)
  small-integer arrays -- too narrow/uniform to plausibly represent 128
  distinct monster IDs, more likely tile/palette/flag data.
- One weak, **unconfirmed** lead: stride=8, 6 slots, base ~0x9A9C8,
  values clustered in 12-21 (occasional 96), run=283, concentration=0.44.
  Not verified against any real encounter (e.g. by cross-referencing
  which monsters a specific early dungeon uses per a walkthrough). Do
  not treat this as located -- it's a "maybe, worth a follow-up look"
  only.

### Public docs

Searched romhacking.net and other ROM-hacking sources for existing
documentation of this game's battle/formation format. One
romhacking.net thread title turned up ("Lunar Silver Star Story +
Eternal Blue PSX - Hex Edit Offsets") but the forum blocks automated
fetches and no thread content was recoverable via search snippets.
Worth revisiting manually (a human browser visit, not a fetch tool) --
if that thread has real offsets this whole search could become trivial,
the same way the almarsguides item-ID page cracked the item table
naming.

## What shipped instead: full-record identity shuffle

Since the formation table isn't confirmed, `enemy_randomizer.py` /
`EnemyTable.java` now support `shuffle_identity`: permutes ENTIRE 38-byte
monster records (type, level, every stat) across table slots, instead of
just scaling or swapping individual stat values. This guarantees every
monster definition in the game still exists exactly once, just reassigned
to a different table index.

**Important caveat, not yet resolved:** whether this actually changes
which sprite/name/AI shows up in a fight depends on whether the game's
formation/battle-loading code references monsters by this table's index
as the single canonical key, or by some other identifier. If sprite/name
selection uses a different key than this stat table's index, this feature
will scramble *stats* attached to each visual monster without changing
which monster you actually see -- still a legitimate difficulty-shuffle
feature, just not the "different monster shows up" effect the visual
formation shuffle would give. Confirming this either way requires either:
locating the actual formation table (see above), or testing in an
emulator/CDmage and observing whether a shuffled build shows mismatched
sprites vs. stats in a fight.

## Recommended next steps, in order of likely payoff

1. **Manual browser check of the romhacking.net thread** linked above --
   cheapest possible win if it pans out.
2. **Ghidra disassembly of the PSX exe** (not the GBA ROM -- a different,
   smaller, and non-OOM-prone target) focused on the battle-initiation
   code path. The actual load instruction for formation data would give
   the real offset directly, no guessing required. This is the same
   technique that would help confirm/deny the GBA enemy table too.
2b. Even a partial disassembly around the function that reads the enemy
    stat table (0x97F68) or item table (0x99244) might turn up a nearby
    formation table reference, since related data is often loaded by
    physically nearby code.
3. **Runtime memory tracing in an emulator** (e.g. mGBA/DuckStation with
   memory watch, or the PS1 debugger some emulators expose): start a
   fight, and diff RAM before/after to see where the enemy roster for
   that specific battle gets loaded from. This sidesteps static analysis
   entirely and would give ground truth directly, at the cost of manual
   per-encounter work.
4. If none of the above pan out quickly, revisit the D1_BTL/D1_MAP format
   properly -- likely needs identifying the compression scheme those
   files use (may or may not be the same gearbolt scheme as the exe).
