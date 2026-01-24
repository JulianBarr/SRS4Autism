import re, csv, time
from pathlib import Path

# SETTINGS
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_41M = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
HSK_CSV = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"
OUTPUT_TTL = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def slugify_id(text):
    """Only cleans IDs. Replaces parentheses and spaces with underscores."""
    return re.sub(r'[()\s]', '_', text)

def main():
    start_time = time.time()
    
    # 1. Load HSK Source of Truth
    hsk_map = {}
    print(f"📖 Loading HSK Source of Truth from: {HSK_CSV.name}")
    with open(HSK_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row = {k.strip(): v for k, v in row.items()}
            if 'word' in row and 'hsk_level' in row:
                hsk_map[row['word']] = row['hsk_level']

    # 2. Process the 41MB Backup
    print(f"🚜 Rebuilding Knowledge Graph from legacy backup...")
    with open(BACKUP_41M, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into blocks based on the Turtle terminator " ."
    blocks = content.split(' .')
    final_blocks = []

    # Standard Header
    header = (
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix srs-kg: <http://srs4autism.com/schema/> .\n"
        "@prefix srs-inst: <http://srs4autism.com/instance/> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n\n"
    )

    for block in blocks:
        block = block.strip()
        if not block or block.startswith("@prefix"): continue

        # --- STEP A: PROTECT LITERALS ---
        # We find all strings inside " " and temporarily hide them 
        # so we don't accidentally turn "Logic City" into "Logic_City"
        literals = []
        def hide_literal(m):
            literals.append(m.group(0))
            return f"__LITERAL_{len(literals)-1}__"
        
        # This regex matches "..." and handles escaped quotes
        protected_block = re.sub(r'"(?:\\.|[^"\\])*"(@[a-z-]+|(\^\^xsd:[a-z]+))?', hide_literal, block)

        # --- STEP B: CLEAN IDs ---
        # Now that strings are hidden, we can safely clean IDs (ns1:abc(123) -> ns1:abc_123)
        # We also standardize all prefixes to srs-kg: or srs-inst:
        protected_block = protected_block.replace('ns1:', 'srs-kg:')
        protected_block = protected_block.replace('ns2:', 'srs-inst:')
        
        # Regex to find prefix:localName and clean the localName
        def clean_id(m):
            prefix = m.group(1)
            local = m.group(2)
            return f"{prefix}:{slugify_id(local)}"
        
        protected_block = re.sub(r'(srs-kg|srs-inst):([^\s;.,<>]+)', clean_id, protected_block)

        # --- STEP C: RESTORE LITERALS ---
        # Put the "Logic City" strings back exactly as they were
        for i, lit in enumerate(literals):
            protected_block = protected_block.replace(f"__LITERAL_{i}__", lit)

        # --- STEP D: SURGICAL METADATA INJECTION ---
        # If this is a word block, ensure HSK level is correct based on CSV
        label_match = re.search(r'rdfs:label "([^"]+)"@zh', protected_block)
        if label_match:
            word_text = label_match.group(1)
            # Remove any existing HSK level first to avoid duplicates
            protected_block = re.sub(r';\s*srs-kg:hskLevel\s+\d+', '', protected_block)
            if word_text in hsk_map:
                protected_block = protected_block.rstrip(' .') + f' ;\n    srs-kg:hskLevel {hsk_map[word_text]}'

        final_blocks.append(protected_block + " .")

    # 3. Write Final File
    with open(OUTPUT_TTL, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write("\n\n".join(final_blocks))

    print(f"✨ SUCCESS! Created {OUTPUT_TTL.name}")
    print(f"Total Triples reconstructed: ~{len(final_blocks)}")

if __name__ == "__main__":
    main()
