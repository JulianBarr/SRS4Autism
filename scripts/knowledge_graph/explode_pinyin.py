import sys
import urllib.parse
from pathlib import Path
from rdflib import Graph, Namespace, RDF, Literal

# Force Output buffering
sys.stdout.reconfigure(line_buffering=True)

try:
    from pypinyin import pinyin, Style
except ImportError:
    print("❌ Error: Missing libraries. Run: pip install rdflib pypinyin")
    sys.exit(1)

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
# Using the complete file as source and destination
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"

# --- CACHE (The Speed Secret) ---
# We store created URIs here to avoid re-creating them thousands of times
uri_cache = {}

def get_cached_uri(namespace, raw_string):
    """
    Returns a URIRef from cache if it exists, otherwise creates and caches it.
    """
    if not raw_string:
        return None
    
    clean_str = raw_string.strip()
    if not clean_str:
        return None
        
    cache_key = (namespace, clean_str)
    if cache_key in uri_cache:
        return uri_cache[cache_key]
    
    # Create new
    safe_suffix = urllib.parse.quote(clean_str)
    uri = namespace[safe_suffix]
    
    # Store
    uri_cache[cache_key] = uri
    return uri

def run_pinyin_explosion():
    print(f"--- STARTING OPTIMIZED PINYIN EXPLOSION ---")
    print(f"Target: {INPUT_FILE.name}")

    if not INPUT_FILE.exists():
        print(f"❌ File not found: {INPUT_FILE}")
        return

    # 1. Load Graph
    print("[1/4] Loading Graph (This is the slowest part, please wait)...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    print(f"      Loaded {len(g)} triples.")

    triples_to_add = []
    triples_to_remove = []
    
    # 2. Query Words
    print("[2/4] Scanning for Chinese words...")
    q_words = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?w ?label ?old_pinyin WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?label .
        OPTIONAL { ?w srs-kg:pinyin ?old_pinyin }
        FILTER (lang(?label) = "zh")
    }
    """
    
    # Convert query result to list to avoid keeping generator open
    rows = list(g.query(q_words))
    total_words = len(rows)
    print(f"      Found {total_words} Chinese words to process.")

    # Pre-cache Tone URIs (Fixed set)
    tone_nodes = {
        1: SRS_KG["tone-1"],
        2: SRS_KG["tone-2"],
        3: SRS_KG["tone-3"],
        4: SRS_KG["tone-4"],
        5: SRS_KG["tone-5"],
    }

    # 3. Processing Loop
    print("[3/4] Generating Pinyin Nodes...")
    
    for count, row in enumerate(rows):
        if count % 200 == 0:
            print(f"      Progress: {count}/{total_words}...", end='\r')

        word_uri = row.w
        text = str(row.label)
        
        # Mark old string-based pinyin for deletion
        if row.old_pinyin:
            triples_to_remove.append((word_uri, SRS_KG.pinyin, row.old_pinyin))

        # Generate Pinyin Data
        # We fetch all styles at once to avoid re-parsing logic inside loop
        py_list_num = pinyin(text, style=Style.TONE3, errors='ignore')
        py_list_display = pinyin(text, style=Style.TONE, errors='ignore')
        py_list_init = pinyin(text, style=Style.INITIALS, strict=False, errors='ignore')
        py_list_final = pinyin(text, style=Style.FINALS, strict=False, errors='ignore')

        # Iterate through syllables
        limit = min(len(py_list_num), len(py_list_display))
        
        for i in range(limit):
            py_str_num = py_list_num[i][0]
            py_display = py_list_display[i][0]
            initial = py_list_init[i][0] if i < len(py_list_init) else ""
            final = py_list_final[i][0] if i < len(py_list_final) else ""
            
            # Detect Tone
            tone_num = 5
            base_syllable = py_str_num
            
            if py_str_num and py_str_num[-1].isdigit():
                try:
                    tone_num = int(py_str_num[-1])
                    base_syllable = py_str_num[:-1] 
                except ValueError:
                    pass

            # --- NODE CREATION (Cached) ---
            
            # 1. Syllable Node
            syllable_id = f"pinyin-{base_syllable}{tone_num}"
            syllable_uri = get_cached_uri(SRS_KG, syllable_id)
            
            if not syllable_uri: continue

            # Link Word -> Syllable
            triples_to_add.append((word_uri, SRS_KG.hasPinyin, syllable_uri))
            
            # Syllable Properties
            triples_to_add.append((syllable_uri, RDF.type, SRS_KG.PinyinSyllable))
            triples_to_add.append((syllable_uri, SRS_KG.displayText, Literal(py_display)))
            
            # 2. Initial Node
            if initial:
                initial_id = f"initial-{initial}"
                initial_uri = get_cached_uri(SRS_KG, initial_id)
                if initial_uri:
                    triples_to_add.append((syllable_uri, SRS_KG.hasInitial, initial_uri))
                    # Only add type definitions if we haven't seen this URI before
                    # (Though adding duplicates to a set is fine, avoiding it saves memory)
                    triples_to_add.append((initial_uri, RDF.type, SRS_KG.Initial))
                    triples_to_add.append((initial_uri, SRS_KG.text, Literal(initial)))

            # 3. Final Node
            if final:
                final_id = f"final-{final}"
                final_uri = get_cached_uri(SRS_KG, final_id)
                if final_uri:
                    triples_to_add.append((syllable_uri, SRS_KG.hasFinal, final_uri))
                    triples_to_add.append((final_uri, RDF.type, SRS_KG.Final))
                    triples_to_add.append((final_uri, SRS_KG.text, Literal(final)))

            # 4. Tone Node (Pre-cached)
            tone_uri = tone_nodes.get(tone_num, tone_nodes[5])
            triples_to_add.append((syllable_uri, SRS_KG.hasTone, tone_uri))
            # We assume Tone Nodes are defined statically in ontology, 
            # but adding type here ensures safety.
            triples_to_add.append((tone_uri, RDF.type, SRS_KG.Tone))
            triples_to_add.append((tone_uri, SRS_KG.value, Literal(tone_num)))

    print(f"\n      Generated {len(triples_to_add)} new triples.")

    # 4. Applying Changes (Bulk)
    print("[4/4] Updating Graph (Bulk Operation)...")
    
    if triples_to_remove:
        # rdflib doesn't have a fast bulk remove, so we loop, 
        # but this list is usually small
        for t in triples_to_remove:
            g.remove(t)
            
    # Bulk Add (Much faster than looping)
    if triples_to_add:
        for t in triples_to_add:
            g.add(t)

    print(f"      Saving to {OUTPUT_FILE.name}...")
    g.serialize(destination=OUTPUT_FILE, format="turtle")
    print("✅ Done.")

if __name__ == "__main__":
    run_pinyin_explosion()