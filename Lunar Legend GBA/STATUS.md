# GBA Lunar Legend analysis status

## Present
- `lunar.gba` — USA ROM (ALNE), 8 MB
- `binary_scan_notes.md` — price/pointer/growth scan results
- Ghidra project (import only) at `/tmp/ghidra_lunar_proj` (ephemeral)

## Ghidra
- 12.1.3 installed under `/tmp/ghidra_12.1.3_PUBLIC`
- Import succeeded (ARM:LE:32:v4t)
- Full auto-analysis + decompile gets OOM-killed in this sandbox (~2–4 GB heap not enough for whole ROM decompile)
- Workaround: analyze on a machine with 8+ GB RAM, or analyze subsets / disable DecompilerAnalyzer

## Text
- No plain ASCII item/character names (compressed or custom encoding)
- Cross-ref Claude’s GBA findings when available

## Cheat RAM (for mGBA/VBA)
- Money `0x042C38`
- Alex level `0x044AC0`, Luna `0x044B00`
- Item/equip flags `0x044A5D` / `0x044981`
