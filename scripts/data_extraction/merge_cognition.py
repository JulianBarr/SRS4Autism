import os
import json

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    part1_path = os.path.join(base_dir, "22_cognition_enriched_abox_part1.json")
    original_path = os.path.join(base_dir, "22_cognition_enriched_abox.json")
    final_path = os.path.join(base_dir, "22_cognition_enriched_abox_FINAL.json")

    print("Loading data files...")
    with open(part1_path, 'r', encoding='utf-8') as f:
        part1_data = json.load(f)
        
    with open(original_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    # Build lookup dictionaries by index so we can easily find the goals
    def build_lookup(data):
        lookup = {}
        for sub in data.get("submodules", []):
            for obj in sub.get("objectives", []):
                for phasal in obj.get("phasal_objectives", []):
                    idx = phasal.get("index")
                    goals = phasal.get("goals", [])
                    if idx and len(goals) > 0:
                        lookup[idx] = goals
        return lookup

    part1_lookup = build_lookup(part1_data)
    original_lookup = build_lookup(original_data)

    print("Merging data into the correct skeleton...")
    # Use part1_data as the base because it has the NEW, CORRECT skeleton order
    for sub in part1_data.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                idx = phasal.get("index")
                
                # Priority 1: Use the freshly extracted early pages
                if idx in part1_lookup:
                    phasal["goals"] = part1_lookup[idx]
                # Priority 2: Fall back to the successfully extracted later pages
                elif idx in original_lookup:
                    phasal["goals"] = original_lookup[idx]
                else:
                    phasal["goals"] = []

    with open(final_path, 'w', encoding='utf-8') as f:
        json.dump(part1_data, f, ensure_ascii=False, indent=2)

    print(f"Merge complete! 🚀\nYour fully restored data is in: {final_path}")
    print("You can now rename this to 22_cognition_enriched_abox.json and move it to your frontend!")

if __name__ == '__main__':
    main()
