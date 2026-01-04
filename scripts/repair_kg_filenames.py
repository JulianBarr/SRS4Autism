from pathlib import Path

# --- CONFIG ---
KG_FILE = Path("knowledge_graph/world_model_complete.ttl").resolve()
# The prefix we want to remove ONLY from imageFileName
BAD_PREFIX = "content/media/objects/"

def repair_filenames():
    print(f"🔧 Repairing {KG_FILE.name}...")
    
    if not KG_FILE.exists():
        print("❌ File not found.")
        return

    with open(KG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_count = 0
    new_lines = []

    for line in lines:
        # We only target lines defining 'srs-kg:imageFileName'
        if "srs-kg:imageFileName" in line and BAD_PREFIX in line:
            # Replace 'content/media/objects/xyz.jpg' with 'xyz.jpg'
            # STRICTLY within this specific line context
            new_line = line.replace(f'"{BAD_PREFIX}', '"')
            new_lines.append(new_line)
            fixed_count += 1
        else:
            new_lines.append(line)

    with open(KG_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"✅ Fixed {fixed_count} lines.")
    print(f"   'imageFileName' now contains clean filenames.")
    print(f"   'imageFilePath' remains full path.")

if __name__ == "__main__":
    repair_filenames()
