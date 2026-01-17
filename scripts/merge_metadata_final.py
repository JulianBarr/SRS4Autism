import re
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_41M = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
NEW_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
FINAL_OUTPUT = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def main():
    print("🧬 Step 1: Loading Metadata from 11MB File...")
    meta_lookup = {}
    
    # Flexible regex to catch zh labels and metadata in the 11MB file
    zh_regex = re.compile(r'\"([^\"]+)\"@zh')
    wd_regex = re.compile(r'srs-kg:wikidataId\s+\"?([Q0-9]+)\"?')
    hsk_regex = re.compile(r'srs-kg:hskLevel\s+(\d)')

    with open(NEW_11M, 'r', encoding='utf-8') as f:
        blocks = f.read().split('.\n')
        for block in blocks:
            zhs = zh_regex.findall(block)
            wd = wd_regex.search(block)
            hsk = hsk_regex.search(block)
            if zhs:
                data = {
                    "wd": wd.group(1) if wd else None,
                    "hsk": hsk.group(1) if hsk else None
                }
                if data["wd"] or data["hsk"]:
                    for char in zhs:
                        meta_lookup[char] = data

    print(f"✅ Indexed metadata for {len(meta_lookup)} characters.")

    print(f"🛠  Step 2: Processing 41MB Legacy (Cleaning & Merging)...")
    
    with open(LEGACY_41M, 'r', encoding='utf-8') as f_in, \
         open(FINAL_OUTPUT, 'w', encoding='utf-8') as f_out:
        
        # Read the file and split into blocks by '.\n'
        # We use a regex for splitting to catch variations in dots/newlines
        content = f_in.read()
        blocks = re.split(r'\s*\.\n', content)
        
        for block in blocks:
            block = block.strip()
            if not block: continue
            
            # A. HANDLE PREFIXES (Protect them)
            if block.startswith("@prefix"):
                f_out.write(block + " .\n")
                continue

            # B. FIX SUBJECT URIs (The "Expressing Numbers" Grammar Fix)
            # If the block starts with srs-inst: but has spaces before the first 'a'
            if block.startswith("srs-inst:"):
                # Split the block into the Subject and the rest
                # We find the first ' a ' or the first ';'
                parts = re.split(r'(\s+a\s+|\s+;)', block, 1)
                if len(parts) > 1:
                    subject = parts[0]
                    predicate_obj_path = "".join(parts[1:])
                    # Clean the subject: replace illegal chars with underscore
                    clean_subject = re.sub(r'[^a-zA-Z0-9\-_:]', '_', subject)
                    clean_subject = re.sub(r'_+', '_', clean_subject).strip('_')
                    block = clean_subject + predicate_obj_path

            # C. INJECT METADATA
            zh_match = zh_regex.search(block)
            if zh_match:
                char = zh_match.group(1)
                if char in meta_lookup:
                    meta = meta_lookup[char]
                    # Clean up trailing semicolons or dots before injecting
                    block = block.rstrip(' .;')
                    
                    if meta['wd']:
                        block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                    if meta['hsk']:
                        block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'

            # D. FINAL PUNCTUATION (The "Double Dot" Fix)
            # Ensure every block ends with exactly one dot
            block = block.rstrip(' .') + " ."
            f_out.write(block + "\n\n")

    print(f"✨ Process Complete! Saved to {FINAL_OUTPUT.name}")

if __name__ == "__main__":
    main()
