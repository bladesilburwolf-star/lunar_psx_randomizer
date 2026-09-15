# radare2 notes — Lunar Legend GBA (USA ALNE)

**Not in the GitHub repo** (CoPilot planned it; not packed). Installed in the
Linux sandbox via apt as `radare2` 5.5.0 (`r2`, `rabin2`, `rax2`).

Ghidra was too heavy for this environment (OOM on full decompile). r2 is the
lightweight option for both sandbox and client-side Win7/Linux work.

## Open the ROM with GBA base address

GBA carts map at `0x08000000`. Always set the base so file offset ↔ VA is:

```
file_offset + 0x08000000 = virtual address
```

```bash
r2 -e bin.baddr=0x08000000 lunar.gba
```

One-shot commands (no interactive session):

```bash
r2 -q -e scr.color=0 -e bin.baddr=0x08000000 -c 'COMMANDS' lunar.gba
```

## Known anchors

| What | File offset | VA |
|------|-------------|-----|
| Item table (12-byte) | `0x7FA424` | `0x087FA424` |
| Shop/drop candidate (16-byte) | `0x7FA8C0` | `0x087FA8C0` |
| ROM title string | `0xA0` | `0x080000A0` |
| Entry branch | `0x0` | `0x08000000` → `0x080000C0` |

```bash
# Hex dump item table
r2 -q -e bin.baddr=0x08000000 -c 's 0x087FA424; px 96' lunar.gba

# Disassemble from real entry (after header)
r2 -q -e bin.baddr=0x08000000 -c 's 0x080000C0; pd 40' lunar.gba

# Search for u16 LE value 0x0064 (100) near item region
r2 -q -e bin.baddr=0x08000000 -c '/x 64 00' lunar.gba
```

## Light analysis (avoid full aa on 8MB if RAM is tight)

```
aaa          # full auto — can be slow / heavy
aa           # lighter function discovery
aF           # analyze function at current seek
pd 32        # print disasm
px 64        # hex
ps           # string at seek
```

Scoped approach for enemy table hunting:

1. Find code that loads battle HP (cheat RAM anchors from RESEARCH_NOTES:
   character block ~`0x02004AC2`, stride `0x80`).
2. In r2: search for immediate loads of those RAM addresses, then follow
   xrefs back to data pointers into the ROM (`0x08xxxxxx`).
3. That ROM pointer is more reliable than blind pattern scans on stats.

Example search for ARM `ldr` patterns toward WRAM is advanced; start with:

```
# bytes of address 0x02004AC2 little-endian: c2 4a 00 02
r2 -q -e bin.baddr=0x08000000 -c '/x c2 4a 00 02' lunar.gba
```

## Windows client

Install from https://github.com/radareorg/radare2/releases or `choco install radare2`
if available. Same commands; GUI optional (`iaito` / Cutter) is heavier than CLI.

## vs Ghidra

| | r2 | Ghidra |
|--|----|--------|
| RAM | low | high (failed here at 2–4GB) |
| Speed | interactive / scripts | batch project |
| Decompile | limited (pdd / r2ghidra plugin) | strong |
| Best for | seek, search, xref, patch | deep struct recovery |

For this project: **r2 first** for anchors and xrefs; Ghidra only if a
machine with 8GB+ is available for a scoped project.
