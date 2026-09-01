#!/usr/bin/env python3
"""
Seed Comparison Utility - Compare enemy stats across randomized ROM variants
Usage: python3 seed_compare.py [seed1] [seed2] [--enemy N] [--stat hp|atk|def|all]
"""

import csv
import sys
from pathlib import Path
from tabulate import tabulate

def load_seed_csv(seed):
    """Load CSV report for a given seed."""
    csv_file = Path(f"lunar_rand_seed_{seed}.csv")
    if not csv_file.exists():
        print(f"❌ CSV not found: {csv_file}")
        return None
    
    with open(csv_file) as f:
        return list(csv.DictReader(f))

def compare_seeds(seed1, seed2, enemy_idx=None, stat="all"):
    """Compare two seeds."""
    data1 = load_seed_csv(seed1)
    data2 = load_seed_csv(seed2)
    
    if not data1 or not data2:
        return
    
    print(f"\n📊 Comparison: Seed {seed1} vs Seed {seed2}")
    print("=" * 100)
    
    if enemy_idx is not None:
        # Compare single enemy
        if enemy_idx < len(data1) and enemy_idx < len(data2):
            e1 = data1[enemy_idx]
            e2 = data2[enemy_idx]
            
            comparison = [
                ["Enemy Index", enemy_idx, enemy_idx],
                ["Offset", e1['offset'], e2['offset']],
                ["HP", f"{e1['hp_old']} → {e1['hp_new']}", f"{e2['hp_old']} → {e2['hp_new']}"],
                ["ATK", f"{e1['atk_old']} → {e1['atk_new']}", f"{e2['atk_old']} → {e2['atk_new']}"],
                ["DEF", f"{e1['def_old']} → {e1['def_new']}", f"{e2['def_old']} → {e2['def_new']}"],
                ["AGI", f"{e1['agi_old']} → {e1['agi_new']}", f"{e2['agi_old']} → {e2['agi_new']}"],
            ]
            print(tabulate(comparison, headers=["Field", f"Seed {seed1}", f"Seed {seed2}"], tablefmt="grid"))
        else:
            print(f"❌ Enemy {enemy_idx} not found")
    else:
        # Summary comparison
        hp1 = [int(e['hp_new']) for e in data1]
        hp2 = [int(e['hp_new']) for e in data2]
        
        summary = [
            ["Total Enemies", len(data1), len(data2)],
            ["Avg HP (New)", f"{sum(hp1)/len(hp1):.0f}", f"{sum(hp2)/len(hp2):.0f}"],
            ["Min HP", min(hp1), min(hp2)],
            ["Max HP", max(hp1), max(hp2)],
            ["Difficulty Diff", f"+{sum(hp2) - sum(hp1):.0f} total HP", ""],
        ]
        print(tabulate(summary, headers=["Metric", f"Seed {seed1}", f"Seed {seed2}"], tablefmt="grid"))

def list_seeds():
    """List all available seed variants."""
    csv_files = sorted(Path(".").glob("lunar_rand_seed_*.csv"))
    if not csv_files:
        print("❌ No seed CSV files found")
        return
    
    print("\n✅ Available Seed Variants:")
    print()
    for csv_file in csv_files:
        seed = csv_file.stem.replace("lunar_rand_seed_", "")
        gba_file = Path(f"lunar_rand_seed_{seed}.gba")
        
        with open(csv_file) as f:
            rows = list(csv.DictReader(f))
        
        hp_new = [int(r['hp_new']) for r in rows]
        avg_hp = sum(hp_new) / len(hp_new) if hp_new else 0
        
        print(f"  Seed {seed:<8} | {gba_file.name} | Avg HP: {avg_hp:.0f}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        list_seeds()
        sys.exit(0)
    
    if sys.argv[1] == "--list":
        list_seeds()
    elif len(sys.argv) >= 3:
        seed1, seed2 = sys.argv[1], sys.argv[2]
        enemy_idx = None
        stat = "all"
        
        if "--enemy" in sys.argv:
            idx = sys.argv.index("--enemy")
            enemy_idx = int(sys.argv[idx + 1])
        
        if "--stat" in sys.argv:
            idx = sys.argv.index("--stat")
            stat = sys.argv[idx + 1]
        
        compare_seeds(seed1, seed2, enemy_idx, stat)
    else:
        print(__doc__)
