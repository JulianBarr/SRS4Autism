import csv
import re
import nltk
from collections import defaultdict

# Ensure you have the CMU pronouncing dictionary
try:
    nltk.data.find('corpora/cmudict.zip')
except LookupError:
    nltk.download('cmudict')

from nltk.corpus import cmudict

# --- Configuration ---
DATA_DIR = '../data/content_db/'
BLENDEL_FILES = ['blendel.dat', 'blendel2.dat'] # Your raw lists
EXAMPLES_FILE = 'blendel_egs.dat' # Your example words
OUTPUT_CSV = '../data/content_db/phonics_patterns.csv'

def load_blendel_patterns():
    """Reads the raw .dat files and returns a set of unique patterns."""
    patterns = set()
    for filename in BLENDEL_FILES:
        try:
            with open(DATA_DIR + filename, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        # parts[0] is ID, parts[1] is pattern
                        pattern = parts[1].strip()
                        patterns.add(pattern)
        except FileNotFoundError:
            print(f"Warning: {filename} not found. Skipping.")
    return sorted(list(patterns))

def load_examples():
    """Reads blendel_egs.dat into a dictionary: pattern -> list of words."""
    examples_map = defaultdict(list)
    try:
        with open(DATA_DIR + EXAMPLES_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or ' ' not in line: 
                    continue
                
                # Format: "ai rain,tail,wait..."
                parts = line.split(' ', 1)
                pattern = parts[0].strip()
                words_str = parts[1]
                
                # Split words by comma
                words = [w.strip() for w in words_str.split(',') if w.strip()]
                examples_map[pattern] = words
    except FileNotFoundError:
        print(f"Warning: {EXAMPLES_FILE} not found.")
        
    return examples_map

def enrich_with_cmudict(pattern, existing_words):
    """
    Finds more simple words for a pattern if we don't have enough.
    (This is a basic heuristic search)
    """
    if len(existing_words) >= 5:
        return existing_words

    # Basic heuristic: Search for the pattern string in common words
    # A real implementation would use grapheme-to-phoneme alignment
    # For now, we'll just return what we have to avoid noise.
    return existing_words

def determine_category(pattern):
    """Guesses the phonics category."""
    vowels = "aeiou"
    if len(pattern) == 1:
        return "Short Vowel" if pattern in vowels else "Consonant"
    
    if pattern.endswith('e') and len(pattern) == 3 and '_' in pattern:
        return "Split Digraph (Magic E)" # e.g. a_e
        
    if all(c in vowels or c == 'y' or c == 'w' for c in pattern):
        return "Vowel Team" # e.g. ai, ay, ee, oa
        
    return "Consonant Digraph/Blend" # e.g. sh, ch, bl

def generate_csv():
    patterns = load_blendel_patterns()
    examples_map = load_examples()
    
    print(f"Found {len(patterns)} unique patterns.")
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header matching our new Anki note structure
        writer.writerow(['Pattern', 'Category', 'AnchorWord', 'ExampleWords', 'KG_ID', 'Skill'])
        
        for pat in patterns:
            # Get examples
            words = examples_map.get(pat, [])
            
            # If we have no examples from your file, try to find the pattern in the keys
            # (Sometimes keys in egs file might differ slightly)
            if not words:
                # Try simple variations
                pass 

            # Pick an anchor word (the first one is usually best)
            anchor = words[0] if words else ""
            
            # The rest are examples
            example_list = ", ".join(words[1:6]) if len(words) > 1 else ""
            
            # Category
            category = determine_category(pat)
            
            # KG ID
            kg_id = f"phonics-{pat}"
            
            # Skill type for KG_Map
            skill = "phonics_decoding"
            
            writer.writerow([pat, category, anchor, example_list, kg_id, skill])

    print(f"Successfully created {OUTPUT_CSV}")

if __name__ == "__main__":
    generate_csv()
