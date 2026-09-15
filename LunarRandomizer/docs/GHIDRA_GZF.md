# Ghidra project: lunar.gba.gzf

**Source:** user full decomp, committed to `bladesilburwolf-star/lunar_psx_randomizer`  
**Local copy:** `artifacts/gba_lunar_legend/lunar.gba.gzf` (84 MB)

## Verified on import (headless)

| Property | Value |
|----------|--------|
| Language | **ARM:LE:32:v4t** (correct for GBA) |
| Compiler | default |
| Image base | `00000000` (file offsets = addresses in this project) |
| Memory | one block `00000000–007fffff` (8 MiB), rwx |
| Functions | **109 441** (auto-created; many tiny) |
| Defined strings | 90 (game text is not plain ASCII) |

Exports from this GZF (for search without opening Ghidra):

- `ghidra_export/program_info.txt`
- `ghidra_export/functions.txt` — `addr  name  size`
- `ghidra_export/symbols.txt`
- `ghidra_export/strings.txt`

## Open on your Mint box (16 GB)

1. Ghidra → **File → Open Project…** does **not** open a bare `.gzf`  
2. Prefer: **File → Import File…** → select `lunar.gba.gzf` → Ghidra detects **GZF Input Format** and restores the analyzed program  
3. Or: create/open a project, then import the `.gzf` into it  

Addresses in this project are **file offsets** (base 0), not `0x08000000`.  
Item table still at **`0x7FA424`**. In r2 with `bin.baddr=0x08000000` that same data is `0x087FA424`.

## Notable string

- `007f8104` — `"EEPROM_V122"` (save type fingerprint)

## Next use for enemy table

In Ghidra UI:

1. Go to **`0x7FA424`** — confirm item data  
2. Search for references **to** that address (or nearby shop table `0x7FA8C0`)  
3. For enemies: find code writing battle HP (WRAM ~`0x0200…` from cheat notes) and follow the ROM pointer it loads  

With 16 GB RAM you can also run **Analysis → Auto Analyze** again if this GZF was saved mid-pass, or use **Search → For Instruction Patterns**.
