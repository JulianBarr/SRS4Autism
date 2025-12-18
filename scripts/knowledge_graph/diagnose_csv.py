import csv
from collections import defaultdict
from pathlib import Path

# Path to your report
CSV_PATH = "logs/vision_cleanup_report.csv" # Adjust path if needed

def analyze_csv():
    print(f"🕵️ Scanning {CSV_PATH}...\n")
    
    source_file_usage = defaultdict(list)
    chinese_definitions = defaultdict(list)
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                # Only check confirmed matches
                if row.get('Match?', '').strip() != 'True':
                    continue

                eng = row.get('English_Word', '').strip()
                chn = row.get('Chinese', '').strip()
                old_file = row.get('Old_Filename', '').strip()
                new_file = row.get('New_Filename', '').strip()

                # Track File Usage (for Race Conditions)
                if old_file and new_file:
                    source_file_usage[old_file].append({
                        'line': i,
                        'eng': eng,
                        'dest': new_file
                    })

                # Track Semantic Definitions (for Ambiguity)
                if chn and eng:
                    chinese_definitions[chn].append(eng)

        # REPORT 1: FILE COLLISIONS (The "Missing File" Cause)
        print("🚩 FILE COLLISIONS (One image used for multiple targets):")
        print("-" * 60)
        collisions = 0
        for src, uses in source_file_usage.items():
            destinations = set(u['dest'] for u in uses)
            if len(destinations) > 1:
                collisions += 1
                print(f"❌ Source: {src}")
                for u in uses:
                    print(f"   Line {u['line']}: '{u['eng']}' -> {u['dest']}")
        
        if collisions == 0: print("✅ No file collisions found.")

        # REPORT 2: SEMANTIC CONFLICTS (The "Tie/Knot" Cause)
        print("\n🚩 SEMANTIC CONFLICTS (Same Chinese for different English words):")
        print("-" * 60)
        conflicts = 0
        for chn, eng_list in chinese_to_english_items(): # Helper fix below
             unique_eng = sorted(list(set(eng_list)))
             if len(unique_eng) > 1:
                 conflicts += 1
                 print(f"⚠️  '{chn}' is mapped to: {unique_eng}")

        if conflicts == 0: print("✅ No semantic conflicts found.")

    except FileNotFoundError:
        print(f"❌ Could not find {CSV_PATH}")

# Helper for defaultdict iteration (Python 3 compatibility)
def chinese_to_english_items():
    return chinese_definitions.items()

if __name__ == "__main__":
    analyze_csv()
