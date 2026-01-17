import re
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_41M = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
NEW_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
FINAL_OUTPUT = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def main():
    print("🧬 Step 1: Loading Metadata from 11MB File (Robust Mode)...")
    meta_lookup = {}
    
    # Improved Regex: Catch Q-IDs inside quotes or as URIs
    wd_regex = re.compile(r'wikidataId\s+["<]?([^">\s]+)[" >]?')
    hsk_regex = re.compile(r'hskLevel\s+"?(\d)"?')
    zh_regex = re.compile(r'\"([^\"]+)\"@zh')

    with open(NEW_11M, 'r', encoding='utf-8') as f:
        content = f.read()
        blocks = content.split('.\n')
        for block in blocks:
            zhs = zh_regex.findall(block)
            wd = wd_regex.search(block)
            hsk = hsk_regex.search(block)
            if zhs and (wd or hsk):
                data = {
                    "wd": wd.group(1) if wd else None,
                    "hsk": hsk.group(1) if hsk else None
                }
                for char in zhs:
                    meta_lookup[char] = data

    print(f"✅ Indexed {len(meta_lookup)} characters. Samples: {list(meta_lookup.keys())[:3]}")

    print(f"🛠  Step 2: Processing 41MB Legacy (Surgical Cleaning)...")
    
    with open(LEGACY_41M, 'r', encoding='utf-8') as f_in, \
         open(FINAL_OUTPUT, 'w', encoding='utf-8') as f_out:
        
        # We split by blocks but keep prefixes separate
        content = f_in.read()
        
        # Protect the headers: find the boundary where prefixes end
        header_end = 0
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith(("@prefix", "@base", "PREFIX", "BASE")):
                header_end = content.find(line)
                break
        
        # Write the header exactly as it was
        f_out.write(content[:header_end].strip() + "\n\n")
        
        # Process the rest of the body
        body = content[header_end:]
        blocks = re.split(r'\s+\.\n', body)
        
        for block in blocks:
            block = block.strip()
            if not block: continue
            
            # 1. Clean the Subject (ID)
            # Find the subject (before the first 'a' or ';')
            parts = re.split(r'(\s+a\s+|\s+;)', block, 1)
            if len(parts) > 1:
                subj = parts[0]
                # REPLACE % AND OTHER ILLEGAL CHARS: 
                # Parser error 'illegal hex escape %' fixed here
                clean_subj = re.sub(r'[^a-zA-Z0-9\-_:]', '_', subj)
                clean_subj = re.sub(r'_+', '_', clean_subj).strip('_')
                block = clean_subject = clean_subj + parts[1] + parts[2]

            # 2. Inject Metadata
            zh_match = zh_regex.search(block)
            if zh_match:
                char = zh_match.group(1)
                if char in meta_lookup:
                    meta = meta_lookup[char]
                    block = block.rstrip(' .;')
                    if meta['wd']: block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                    if meta['hsk']: block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'

            # 3. Final dot protection
            block = block.rstrip(' .') + " ."
            f_out.write(block + "\n\n")

    print(f"✨ Master KG created: {FINAL_OUTPUT.name}")

if __name__ == "__main__":
    main()
