"""
item_ids.py – confirmed item identity + decoded flavor-field legends for the
Lunar SSSC item table (see NOTES.md for how these were derived/verified).

table_record_index = codebreaker_item_ID + 1

Only the range we've verified against real published data is filled in;
everything else is left unnamed (Item_##) rather than guessed. See
NOTES.md TODO #1 for how to extend this once the rest of the ID list is
recovered.
"""

ITEM_NAMES: dict[int, str] = {
    0: "(pad)",
    1: "Nothing",
    2: "Dagger",
    3: "Short Sword",
    4: "Long Sword",
    5: "Broad Sword",
    6: "Saber",
    7: "Ice Blade",
    8: "Silver Sword",
    9: "Samurai Blade",
    10: "Flame Sword",
    11: "Bastard Sword",
    12: "Great Sword",
    13: "Wind Sword",
    14: "Crystal Sword",
    15: "Dark Sword",
    16: "Master Sword",
    17: "Insane Sword",
    18: "Althena's Sword",
    19: "Mace",
    20: "Flail",
    21: "Ice Mace",
    22: "Water Mace",
    23: "Judgment Mace",
    24: "Holy Mace",
    25: "Dark Mace",
}

# Decoded meaning of the 7 "unknown" bytes at record offset 0x0B-0x11.
# NOT combat stats -- see NOTES.md. Field names reflect confidence level.
FIELD_LAYOUT = {
    0x0B: "sub_id_lo",       # usually 0; deviates with 0x0C on ~3 special items
    0x0C: "sub_id_hi",       # usually 1; see 0x0B
    0x0D: "effect_id",       # elemental/special-effect code, reused across
                              # weapon classes for the same effect (e.g. 44 =
                              # Ice on both Ice Blade and Ice Mace)
    0x0E: "unused",          # always 0 in the weapons section observed so far
    0x0F: "tier",            # 0=starter,1=sword,2=mace,5=legendary (observed)
    0x10: "icon_id",         # sprite/icon index; clusters by weapon shape
    0x11: "unknown",         # no pattern identified yet
}

EFFECT_IDS = {
    0: "(none)",
    44: "Ice",
    43: "Fire",
    45: "Wind",
    29: "HP auto-regen",
    7: "crit-related (unconfirmed)",
    14: "AOE/instant-death-ish (unconfirmed)",
    2: "unconfirmed (Judgment Mace)",
    12: "unconfirmed (Dark Mace)",
}


def name_for(table_index: int) -> str:
    return ITEM_NAMES.get(table_index, f"Item_{table_index}")
