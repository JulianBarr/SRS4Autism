import sys
import random
import os
from pathlib import Path

# Force output to print immediately (fix silent death)
sys.stdout.reconfigure(line_buffering=True)

try:
    from rdflib import Graph, RDF
except ImportError:
    print("❌ Error: rdflib is not installed. Run: pip install rdflib")
    sys.exit(1)

# --- CONFIGURATION ---
# We calculate paths relative to the script location
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # Go up: scripts -> analysis -> root

print

# SEARCH for the file if we aren't sure where it is
POSSIBLE_PATHS = [
    PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl",
    PROJECT_ROOT / "data" / "world_model_merged.ttl",
    PROJECT_ROOT / "world_model_merged.ttl"
]

INPUT_FILE = None
for p in POSSIBLE_PATHS:
    if p.exists():
        INPUT_FILE = p
        break

OUTPUT_FILE = PROJECT_ROOT / "world_model_sample.ttl"

def create_representative_sample():
    print(f"Script Running from: {SCRIPT_DIR}")
    print(f"Project Root detected as: {PROJECT_ROOT}")

    if INPUT_FILE is None:
        print("\n❌ CRITICAL ERROR: Could not find 'world_model_merged.ttl'")
        print("Checked locations:")
        for p in POSSIBLE_PATHS:
            print(f"   [ ] {p}")
        return

    print(f"\n✅ Found input file: {INPUT_FILE}")
    print(f"Loading graph... (This takes ~10-20 seconds)")
    
    source_g = Graph()
    source_g.parse(INPUT_FILE, format="turtle")

    print(f"Graph loaded successfully. Total triples: {len(source_g)}")
    
    # --- SAMPLING LOGIC ---
    sample_g = Graph()
    print("Sampling entities...")

    # 1. Grab Classes
    classes = set(source_g.objects(predicate=RDF.type))
    print(f"Found {len(classes)} distinct classes.")

    # 2. Sample 3 entities per class + ALL their properties
    for cls in classes:
        subjects = list(source_g.subjects(predicate=RDF.type, object=cls))
        selection = random.sample(subjects, min(len(subjects), 3))
        
        for subj in selection:
            for p, o in source_g.predicate_objects(subj):
                sample_g.add((subj, p, o))

    # 3. Property Safety Net (Catch hidden properties like Pinyin)
    print("Checking for hidden properties...")
    all_predicates = set(source_g.predicates())
    sampled_predicates = set(sample_g.predicates())
    missing_predicates = all_predicates - sampled_predicates

    for p in missing_predicates:
        triples = list(source_g.triples((None, p, None)))
        selection = random.sample(triples, min(len(triples), 2))
        for s, p, o in selection:
            sample_g.add((s, p, o))

    print(f"Saving sample to {OUTPUT_FILE}...")
    sample_g.serialize(destination=OUTPUT_FILE, format="turtle")
    print(f"Done! Created {OUTPUT_FILE.name} with {len(sample_g)} triples.")

if __name__ == "__main__":
    create_representative_sample()