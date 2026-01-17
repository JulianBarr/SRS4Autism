import re
from pathlib import Path

# Update these paths to match your actual filenames
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_LEGACY = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_clean.ttl"
NEW_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl" # Update if named differently
FINAL_OUTPUT = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def main():
    print("🧬 Step 1: Indexing Metadata from 11MB file...")
    meta_lookup = {}
    
    # Regex patterns for extraction
    zh_regex = re.compile(r'\"([^\"]+)\"@zh')
    wd_regex = re.compile(r'srs-kg:wikidataId\s+\"([^\"]+)\"')
    hsk_regex = re.compile(r'srs-kg:hskLevel\s+(\d)')

    if not NEW_11M.exists():
        print(f"❌ Error: {NEW_11M} not found!")
        return

    with open(NEW_11M, 'r', encoding='utf-8') as f:
        # Split by blocks ending in a dot followed by a newline
        content = f.read()
        blocks = content.split('.\n')
        for block in blocks:
            zh_chars = zh_regex.findall(block)
            wd = wd_regex.search(block)
            hsk = hsk_regex.search(block)
            
            if zh_chars and (wd or hsk):
                metadata = {
                    "wd": wd.group(1) if wd else None,
                    "hsk": hsk.group(1) if hsk else None
                }
                for char in zh_chars:
                    # Note: If a character appears multiple times with different WD IDs, 
                    # the last one wins. Usually fine for HSK vocab.
                    meta_lookup[char] = metadata

    print(f"✅ Indexed {len(meta_lookup)} unique characters for enrichment.")

    print(f"🔗 Step 2: Merging into 41MB Clean Legacy...")
    if not CLEAN_LEGACY.exists():
        print(f"❌ Error: {CLEAN_LEGACY} not found!")
        return

    enriched_count = 0
    with open(CLEAN_LEGACY, 'r', encoding='utf-8') as f_in, \
         open(FINAL_OUTPUT, 'w', encoding='utf-8') as f_out:
        
        # We read the cleaned legacy in blocks
        content = f_in.read()
        blocks = content.split('.\n')
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # Look for Chinese characters in the legacy block
            zh_match = zh_regex.search(block)
            if zh_match:
                char = zh_match.group(1)
                if char in meta_lookup:
                    meta = meta_lookup[char]
                    
                    # Remove the trailing dot to append properties
                    # We ensure we don't accidentally remove a dot inside a string
                    block = block.rstrip()
                    if block.endswith('.'):
                        block = block[:-1]
                    
                    # Inject Wikidata ID if available
                    if meta['wd']:
                        block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                    
                    # Inject HSK Level if available
                    if meta['hsk']:
                        block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'
                    
                    block += " ."
                    enriched_count += 1
                else:
                    # No metadata found, just ensure it ends correctly
                    if not block.endswith('.'):
                        block += " ."
            else:
                # No Chinese character found (e.g., Grammar only), preserve as is
                if not block.endswith('.'):
                    block += " ."
            
            f_out.write(block + "\n\n")

    print(f"\n✨ SUCCESS!")
    print(f"📊 Enriched {enriched_count} semantic nodes with Wikidata/HSK metadata.")
    print(f"📂 Final Master KG: {FINAL_OUTPUT.name}")

if __name__ == "__main__":
    main()
