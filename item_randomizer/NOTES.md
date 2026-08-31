# Item table research notes

## Confirmed: the price/economy table

- Location: decompressed exe payload offset **0x99244**, immediately after
  the enemy table (which `patch_exe.py` already confirmed at 0x97F68).
- **72 records x 18 bytes (0x12) = 1296 bytes.**
- `buy_price` (u16 @ 0x00), `sell_price` (u16 @ 0x02) — sell is *always*
  exactly `buy // 2` for all 72 records, no exceptions.
- Found originally by scanning for real prices pulled from period FAQs
  (Short Sword 200, Long Sword 360, Broad Sword 600, Flail 2600, Samurai
  Blade 2800, etc.) and confirming an 18-byte stride around the hits.

## Confirmed: record index = item ID

Found an authoritative item/equipment ID table used for this exact game's
Codebreaker/GameShark codes (almarsguides.com — this reflects the game's
own internal memory representation of "which item is this", since cheat
codes have to poke the real in-memory ID). Mapping:

    table_record_index = codebreaker_item_ID + 1

Verified against **six** independently-sourced real prices, all exact
matches: Dagger=100, Short Sword=200, Long Sword=360, Broad Sword=600,
Samurai Blade=2800, Flail=2600. Also matches non-numeric facts: Althena's
Sword (ID 0x11, table idx 18) has buy=0/sell=0, and every guide marks it
"Buy: ---" (find-only item, never sold) -- exactly what we'd expect.

ID list captured so far (0x00-0x19, i.e. table indices 1-26), from
almarsguides' Codebreaker page (page is paginated/truncated in every fetch
attempt so far -- see TODO below):

    00 Nothing        0A Bastard Sword   14 Ice Mace
    01 Dagger          0B Great Sword     15 Water Mace
    02 Short Sword      0C Wind Sword     16 Judgment Mace
    03 Long Sword       0D Crystal Sword  17 Holy Mace
    04 Broad Sword      0E Dark Sword     18 Dark Mace
    05 Saber            0F Master Sword   19 Sling
    06 Ice Blade        10 Insane Sword   1A Poison Darts
    07 Silver Sword      11 Althena's Sword ... (bows, canes follow,
    08 Samurai Blade     12 Mace              see source page)
    09 Flame Sword       13 Flail

Source page (truncates mid-list in every fetch/search snippet so far --
worth trying again with a direct browser or archive.org):
https://www.almarsguides.com/retro/walkthroughs/PS1/Games/LunarTheSilverStarStoryComplete/CodeBreaker/ModifierDigits/ItemsAndEquipment/

## Decoded (partially): the 7 "unknown" bytes (offset 0x0B-0x11)

These are NOT the ATK/DEF combat stat bonus. Decoded so far, cross-checked
against item descriptions from the PSX equipment guide (Shotgunnova,
GameFAQs) and Lunar Legend GBA descriptions:

  - **0x0D = elemental / special-effect ID.** Same numeric code reused
    across weapon classes for the same effect:
      - 44 = Ice          (Ice Blade AND Ice Mace both have 44)
      - 43 = Fire          (Flame Sword)
      - 45 = Wind          (Wind Sword)
      - 29 = HP auto-regen  (Althena's Sword AND Holy Mace both have 29 --
             these are the only two items any guide describes as
             auto-healing HP)
      - 7  = crit-related?  (Master Sword -- guide: "ups critical hits")
      - 14 = AOE/instant-death-ish? (Insane Sword -- guide: "Kiai Slice")
      - 2, 12 = unconfirmed (Judgment Mace, Dark Mace)
      - 0 = no special effect
  - **0x0F = rarity/weapon-class tier.** 0=starter (Dagger), 1=normal
    sword, 2=mace, 5=only on the 3 clear "legendary" items in this slice
    (Insane Sword, Althena's Sword, Holy Mace).
  - **0x10 = icon/sprite ID.** Clusters exactly by weapon silhouette (every
    single mace shares value 4; swords split into a few icon groups).
  - 0x0B/0x0C: almost always (0, 1); both deviate together only on the
    same 3 "special" items noted above. Purpose unclear -- possibly a
    2-byte sub-ID for unique/quest items.
  - 0x0E: always 0 in the weapons section. Unused here, or only used by
    a different item category (armor/accessories/consumables).
  - 0x11: no clear pattern yet.

## Conclusion / what's still missing

**The real ATK/DEF/RES/MEN stat bonuses are not in this table.** No byte
here scales with weapon tier the way Attack Power should (weapons run from
~5 ATK to 130+ ATK per published stat lists; nothing in these 7 bytes
climbs anywhere close to that range). This table is item *economy +
flavor* data (price, element, rarity, icon) -- the actual combat stat
table is a **separate, not-yet-located** table elsewhere in the exe.

## TODO for next session

1. Re-fetch the almarsguides Codebreaker item-ID page (or find it on
   archive.org) to get the full 0x00-0x47 ID list covering armor,
   accessories, and consumables, so all 72 records can be named, not just
   the first 26.
2. Search for the actual equip-stat table. Likely candidates:
   - Elsewhere in the same decompressed exe payload (the enemy table and
     this economy table are adjacent -- a stat table may be adjacent too,
     just search before 0x97F68 or after 0x99754).
   - Could be keyed by the SAME item ID (0x00-0x47ish) with a different,
     probably larger, record size to fit ATK/DEF/RES/MEN/usable-by-flags.
   - GBA Lunar Legend's data files may be much easier to dump/document
     than this PSX gearbolt-compressed exe and could give exact stat
     values to search for as anchors, the same way real prices were used
     to find *this* table.
3. Once the stat table is found, extend item_randomizer.py to shuffle it
   too (currently it only randomizes buy/sell price, which is safe to
   ship on its own in the meantime).
