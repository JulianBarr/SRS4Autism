import re, csv, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_41M = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
COMPLETE_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
HSK_CSV = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"
FINAL_MASTER = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def slugify_id(text):
    """Slugs only the local part, preserving colons for prefixes."""
    if ':' in text:
        prefix, local = text.split(':', 1)
        # Only slugify the local part, keep prefix as is
        # Allow Unicode characters (\w matches alphanumeric + _)
        local = re.sub(r'[^\w-]', '_', local)
        local = re.sub(r'_+', '_', local).strip('_')
        return f"{prefix}:{local}"
    text = re.sub(r'[^\w-]', '_', text)
    return re.sub(r'_+', '_', text).strip('_')

def main():
    start_time = time.time()
    
    # 1. Load HSK Levels from CSV (Source of Truth)
    hsk_map = {}
    print(f"🎯 Loading HSK CSV from {HSK_CSV}...")
    with open(HSK_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row = {k.strip(): v for k, v in row.items()}
            if 'word' in row and 'hsk_level' in row:
                hsk_map[row['word']] = row['hsk_level']
    print(f"   Loaded {len(hsk_map)} HSK entries.")

    # 2. Load Wikidata IDs from 11MB file
    wd_map = {}
    print(f"🧬 Extracting Wikidata IDs from {COMPLETE_11M}...")
    with open(COMPLETE_11M, 'r', encoding='utf-8') as f:
        # Simple extraction: find label and Q-id in the same block
        blocks = f.read().split('.\n')
        for b in blocks:
            zhs = re.findall(r'\"([^\"]+)\"@zh', b)
            wd = re.search(r'(Q\d+)', b)
            if zhs and wd:
                for z in zhs: wd_map[z] = wd.group(1)
    print(f"   Loaded {len(wd_map)} Wikidata mappings.")

    # 3. Process 41MB Base
    print(f"📚 Processing 41MB Base file...")
    with open(BACKUP_41M, 'r', encoding='utf-8') as f:
        content = f.read()

    literals = []
    
    def replace_literal(m):
        literals.append(m.group(0))
        return f" LTRL{len(literals)-1}LTRL "

    # Match triple-quoted strings first, then single-quoted strings
    # Note: Triple quotes allow newlines and unescaped quotes inside.
    pattern = r'("""[\s\S]*?"""(?:@[a-zA-Z-]+|(?:\^\^<[^>]+>))?|"(?:\\.|[^"\\])*"(?:@[a-zA-Z-]+|(?:\^\^<[^>]+>))?)'
    content = re.sub(pattern, replace_literal, content)

    def clean_block(block):
        block = block.strip()
        if not block: return ""
        if block.startswith("@prefix"): return block + " ."
        
        def restore_lits(text):
            return re.sub(r'LTRL(\d+)LTRL', lambda m: literals[int(m.group(1))], text)

        # Split into subject and predicate-objects
        # Make 'a' splitter stricter to avoid matching 'a' in English text IDs
        parts = re.split(r'(\s+a\s+(?:srs-kg:|srs-inst:|owl:|rdfs:|rdf:|skos:|xsd:)[^\s;]+|\s+;|\s+rdfs:label)', block, 1)
        if len(parts) > 1:
            raw_subj = parts[0].strip()
            # Restore literals in subject so they get slugified (removing quotes)
            raw_subj = restore_lits(raw_subj)
            subject = slugify_id(raw_subj)

            rest_str = "".join(parts[1:])
            
            # Clean URI references in the rest of the block
            
            # 1. Aggressive cleaning for Objects (srs-inst or hyphenated srs-kg)
            # Hyphenated srs-kg are likely Objects (concepts, words), not Predicates.
            # Captures until a terminator or another likely token.
            the_rest = re.sub(r'(srs-inst:|srs-kg:[^\s;,\n\[\]()]*?-)(.*?)(?=[;,\n]|\s+\.|\s+a\s+|\s+(?:srs-inst|srs-kg|rdfs|rdf|owl|xsd|skos):)', 
                             lambda m: m.group(1) + re.sub(r'[^\w-]', '_', restore_lits(m.group(2))).strip('_'), 
                             rest_str)

            # 2. Strict cleaning for Predicates (non-hyphenated srs-kg) and other remaining URIs
            # This handles srs-kg:ageOfAcquisition (no hyphen) -> stops at space
            the_rest = re.sub(r'(srs-kg:)([^\s;,\n\[\]()]+)', 
                             lambda m: m.group(1) + re.sub(r'[^\w-]', '_', restore_lits(m.group(2))).strip('_'), 
                             the_rest)

            block = subject + " " + the_rest
        
        # INJECT Metadata
        zh_marker = re.search(r'LTRL(\d+)LTRL(?=@zh)', block)
        if zh_marker:
            literal_content = literals[int(zh_marker.group(1))]
            # Extract text between quotes
            word_text = re.search(r'"([^"]+)"', literal_content).group(1)
            
            block = block.rstrip(' .')
            if word_text in wd_map: 
                block += f' ;\n    srs-kg:wikidataId "{wd_map[word_text]}"'
            if word_text in hsk_map: 
                block += f' ;\n    srs-kg:hskLevel {hsk_map[word_text]}'
        
        return block.rstrip(' .') + " ."

    print("🛠  Synthesizing Master KG...")
    final_blocks = [clean_block(b) for b in content.split(' .') if b.strip()]
    result = "\n\n".join(filter(None, final_blocks))
    result = re.sub(r'LTRL(\d+)LTRL', lambda m: literals[int(m.group(1))], result)
    
    with open(FINAL_MASTER, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"✨ SUCCESS! Final Master created at {FINAL_MASTER}")

if __name__ == "__main__":
    main()
