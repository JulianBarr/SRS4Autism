import re, csv
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESCUED_TTL = PROJECT_ROOT / "knowledge_graph" / "world_model_rescued.ttl"
HSK_CSV = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"

def main():
    # 1. Load HSK Source of Truth
    hsk_map = {}
    print(f"📖 Loading HSK Source of Truth from: {HSK_CSV.name}")
    try:
        with open(HSK_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                row = {k.strip(): v for k, v in row.items()}
                if 'word' in row and 'hsk_level' in row:
                    hsk_map[row['word']] = row['hsk_level']
    except FileNotFoundError:
        print(f"❌ Error: {HSK_CSV} not found.")
        return

    # 2. Read existing rescued KG
    print(f"📚 Reading {RESCUED_TTL.name}...")
    try:
        with open(RESCUED_TTL, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Error: {RESCUED_TTL} not found.")
        return

    # 3. Surgical HSK removal 
    # This removes any line declaring hskLevel (handling ns1:, srs-kg:, etc.)
    # We remove it regardless of where it is in the property chain
    print("🧹 Removing incorrect HSK levels...")
    content = re.sub(r';\s*(?:ns\d+|srs-kg):hskLevel\s+\d+', '', content)
    content = re.sub(r'(?:ns\d+|srs-kg):hskLevel\s+\d+\s*;', '', content)
    # Also remove isolated property at end of block
    content = re.sub(r'(?:ns\d+|srs-kg):hskLevel\s+\d+\s*\.', '.', content)

    # 4. Inject correct HSK levels from CSV
    print("🧪 Injecting HSK levels from CSV...")
    # Split by blank lines which separate blocks in this file
    blocks = content.split('\n\n')
    final_blocks = []

    for block in blocks:
        original_block = block
        block = block.strip()
        if not block: 
            # If it was just empty space, preserve it conceptually or skip (rejoin adds \n\n)
            # To match original spacing somewhat better, we could append empty string, but let's just skip
            # and rely on join
            continue
            
        if block.startswith("@prefix"):
            final_blocks.append(block)
            continue
        
        # Look for the Chinese label
        label_match = re.search(r'rdfs:label "([^"]+)"@zh', block)
        if label_match:
            word_text = label_match.group(1)
            if word_text in hsk_map:
                # Detect the prefix used in this block (usually ns1 in rescued.ttl)
                prefix_match = re.search(r'(ns\d+|srs-kg):', block)
                prefix = prefix_match.group(1) if prefix_match else "srs-kg"
                
                # Check if block ends with .
                if block.endswith('.'):
                     # Remove the dot, add property, add dot
                     block = block[:-1].strip() + f' ;\n    {prefix}:hskLevel {hsk_map[word_text]} .'
        
        final_blocks.append(block)

    with open(RESCUED_TTL, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_blocks))
        f.write("\n") # Ensure trailing newline
    
    print(f"✨ SUCCESS! {RESCUED_TTL.name} has been corrected using the CSV.")

if __name__ == "__main__":
    main()
