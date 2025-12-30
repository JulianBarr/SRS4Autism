import csv
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()
REPORT_PATH = PROJECT_ROOT / "logs" / "vision_cleanup_report.csv"

def debug_csv():
    print(f"🔍 Inspecting: {REPORT_PATH}")
    
    if not REPORT_PATH.exists():
        print("❌ File not found!")
        return

    try:
        with open(REPORT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        print(f"📄 Total lines in file: {len(lines)}")
        print(f"📋 Header row: {lines[0].strip()}")
        
        # Check specific problem words
        targets = ["if", "smoke", "cigarette", "倘", "烟"]
        found_targets = {t: False for t in targets}
        
        reader = csv.DictReader(lines)
        
        print("\n--- Scanning Rows for Block Actions ---")
        blocked_count = 0
        
        for i, row in enumerate(reader):
            word = row.get('English_Word', '').strip()
            reviewed = row.get('Reviewed', '').strip()
            match = row.get('Match?', '').strip()
            new_file = row.get('New_Filename', '').strip()
            
            # Print detail for our problem children
            if word.lower() in targets:
                found_targets[word.lower()] = True
                print(f"🎯 FOUND '{word}':")
                print(f"   - Reviewed: '{reviewed}'")
                print(f"   - Match?: '{match}'")
                print(f"   - New_Filename: '{new_file}'")
                
                # Replicate the logic exactly
                is_reviewed = reviewed.lower() == 'true'
                is_match = match.lower() == 'true'
                is_delete = new_file.upper() == 'DELETE'
                
                should_block = is_reviewed and (not is_match or is_delete)
                
                if should_block:
                    print(f"   ✅ LOGIC: WOULD BLOCK")
                    blocked_count += 1
                else:
                    print(f"   ❌ LOGIC: WOULD NOT BLOCK (Why? Rev={is_reviewed}, Match={is_match}, Del={is_delete})")

    except Exception as e:
        print(f"❌ CRASHED: {e}")

if __name__ == "__main__":
    debug_csv()
