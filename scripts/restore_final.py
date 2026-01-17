import re
from pathlib import Path
import time

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
NEW_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

def clean_uri_greedy(text):
    """
    Cleans URIs by capturing EVERYTHING from the prefix until an RDF terminator.
    This fixes: srs-inst:gp-A1-019-Expressing numbers 11-19 (Teens) a ...
    """
    # Regex logic:
    # 1. Match the prefix (srs-inst: or srs-kg:)
    # 2. Capture everything greedily (.*?)
    # 3. Stop ONLY when we see: ' a ', ' ;', ' .', or a newline.
    pattern = re.compile(r'(srs-inst:|srs-kg:)(.*?)(?=\s+a\s+|\s*[;.\n])', re.DOTALL)

    def replacer(match):
        prefix = match.group(1)
        body = match.group(2)
        # Replace spaces, parens, quotes, and % with underscores
        clean_body = re.sub(r'[^a-zA-Z0-9\-_:]', '_', body)
        # Collapse multiple underscores
        clean_body = re.sub(r'_+', '_', clean_body).strip('_')
        return f"{prefix}{clean_body}"

    return pattern.sub(replacer, text)

def main():
    start_time = time.time()
    
    # 1. INDEX METADATA (11MB)
    print("🧬 Indexing Metadata from 11MB...")
    meta_lookup = {}
    zh_pattern = re.compile(r'\"([^\"]+)\"@zh')
    wd_pattern = re.compile(r'(Q\d+)')
    hsk_pattern = re.compile(r'hskLevel\s+"?(\d)"?')

    with open(NEW_11M, 'r', encoding='utf-8') as f:
        blocks = f.read().split('.\n')
        for block in blocks:
            zhs = zh_pattern.findall(block)
            wd = wd_pattern.search(block)
            hsk = hsk_pattern.search(block)
            if zhs and (wd or hsk):
                meta = {"wd": wd.group(1) if wd else None, "hsk": hsk.group(1) if hsk else None}
                for char in zhs:
                    meta_lookup[char] = meta

    # 2. PROCESS 41MB FILE
    print(f"🚀 Processing {INPUT_FILE.name}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split to protect strings
    segments = re.split(r'("(?:\\.|[^"\\])*")', content)
    
    print("🛠  Greedily cleaning URIs (Subject and Objects)...")
    for i in range(len(segments)):
        if i % 2 == 0:  # Code part
            # Step A: Protect Prefixes (temporary swap)
            segments[i] = segments[i].replace("@prefix srs-inst:", "TEMP_INST_PREFIX")
            segments[i] = segments[i].replace("@prefix srs-kg:", "TEMP_KG_PREFIX")
            
            # Step B: Greedy Clean
            segments[i] = clean_uri_greedy(segments[i])
            
            # Step C: Restore Prefixes
            segments[i] = segments[i].replace("TEMP_INST_PREFIX", "@prefix srs-inst:")
            segments[i] = segments[i].replace("TEMP_KG_PREFIX", "@prefix srs-kg:")
    
    content = "".join(segments)
    
    # 3. MERGE METADATA & FIX PUNCTUATION
    print("🔗 Injecting Metadata & Finalizing Punctuation...")
    blocks = re.split(r'\s*\.\n', content)
    final_output = []
    
    for block in blocks:
        block = block.strip()
        if not block: continue
        if block.startswith("@prefix"):
            final_output.append(block + " .")
            continue
            
        zh_match = zh_pattern.search(block)
        if zh_match:
            char = zh_match.group(1)
            if char in meta_lookup:
                meta = meta_lookup[char]
                block = block.rstrip(' .;')
                if meta['wd']: block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                if meta['hsk']: block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'
        
        # Ensure exactly one dot at the end
        final_output.append(block.rstrip(' .') + " .")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_output))

    print(f"✅ Finished in {time.time() - start_time:.2f}s")
    print(f"📊 Final Master: {OUTPUT_FILE.name}")

if __name__ == "__main__":
    main()
