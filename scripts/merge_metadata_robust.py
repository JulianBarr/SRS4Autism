import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_LEGACY = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_clean.ttl"
NEW_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
FINAL_OUTPUT = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def main():
    print("🧬 Indexing Metadata from 11MB file...")
    meta_lookup = {}
    
    # Very loose regex to catch as many characters as possible
    # Looks for any character inside quotes followed by @zh
    zh_pattern = re.compile(r'"([^"]+)"@zh')
    wd_pattern = re.compile(r'wikidataId\s+"(Q\d+)"')
    hsk_pattern = re.compile(r'hskLevel\s+"?(\d)"?')

    with open(NEW_11M, 'r', encoding='utf-8') as f:
        # Split by blocks properly
        blocks = f.read().split('.\n')
        for block in blocks:
            chars = zh_pattern.findall(block)
            wd = wd_pattern.search(block)
            hsk = hsk_regex = hsk_pattern.search(block)
            
            if chars:
                meta = {
                    "wd": wd.group(1) if wd else None,
                    "hsk": hsk.group(1) if hsk else None
                }
                for c in chars:
                    # Only store if we actually have data to add
                    if meta["wd"] or meta["hsk"]:
                        meta_lookup[c] = meta

    print(f"✅ Found metadata for {len(meta_lookup)} characters.")

    print("🔗 Injecting into 41MB Legacy...")
    enriched = 0
    with open(CLEAN_LEGACY, 'r', encoding='utf-8') as f_in, \
         open(FINAL_OUTPUT, 'w', encoding='utf-8') as f_out:
        
        content = f_in.read()
        blocks = content.split('.\n')
        
        for block in blocks:
            block = block.strip()
            if not block: continue
            
            # Find the character label
            zh_match = zh_pattern.search(block)
            if zh_match:
                char = zh_match.group(1)
                if char in meta_lookup:
                    meta = meta_lookup[char]
                    block = block.rstrip('.')
                    if meta['wd']: block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                    if meta['hsk']: block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'
                    block += " ."
                    enriched += 1
            
            f_out.write(block + ".\n\n")

    print(f"✅ Done! Enriched {enriched} nodes. Saved to {FINAL_OUTPUT.name}")

if __name__ == "__main__":
    main()
