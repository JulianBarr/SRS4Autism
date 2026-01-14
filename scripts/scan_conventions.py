import re
from collections import Counter, defaultdict
import sys

# --- CONFIGURATION ---
FILE_PATH = "knowledge_graph/world_model_complete.ttl"

def forensic_scan(file_path):
    print(f"--- FORENSIC SCAN OF: {file_path} ---")
    
    class_counts = Counter()
    property_counts = Counter()
    subject_patterns = defaultdict(list)
    bad_uri_samples = []
    
    # Regex patterns to capture data from raw text lines
    # 1. Capture "Subject a Class" or "Subject rdf:type Class"
    type_pattern = re.compile(r'^\s*([^\s]+)\s+(?:a|rdf:type)\s+([^\s;]+)')
    
    # 2. Capture "property value" (indented lines)
    prop_pattern = re.compile(r'^\s+([a-zA-Z0-9_\-\.]+:[a-zA-Z0-9_\-\.]+)\s+')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('@') or line.startswith('#'):
                    continue

                # Check for Bad URIs (containing spaces or quotes)
                # Matches: srs-inst:Something Bad
                if "srs-inst:" in line:
                    match = re.search(r'(srs-inst:[^;\.\s]*[\s"][^;\.\s]*)', line)
                    if match and len(bad_uri_samples) < 5:
                        bad_uri_samples.append(f"Line {line_num}: {match.group(1)}")

                # Check Class Definitions
                type_match = type_pattern.match(line)
                if type_match:
                    subj, cls = type_match.groups()
                    class_counts[cls] += 1
                    # Store sample subject URI for this class
                    if len(subject_patterns[cls]) < 3:
                        subject_patterns[cls].append(subj)
                    continue

                # Check Property Usage
                prop_match = prop_pattern.match(line)
                if prop_match:
                    prop = prop_match.group(1)
                    property_counts[prop] += 1

    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # --- REPORT ---
    
    print("\n1. 🚨 INVALID URI EXAMPLES (Fix these first!)")
    if bad_uri_samples:
        for s in bad_uri_samples:
            print(f"  {s}")
    else:
        print("  None found (Scanner might be too simple, or file is clean)")

    print("\n2. 📊 CLASS DISTRIBUTION & NAMING CONVENTIONS")
    for cls, count in class_counts.most_common(20):
        print(f"\n  [{cls}] : {count} instances")
        print(f"    Sample IDs: {', '.join(subject_patterns[cls])}")

    print("\n3. 🔗 PROPERTY USAGE (Top 30)")
    for prop, count in property_counts.most_common(30):
        print(f"  {prop:<30} : {count}")

if __name__ == "__main__":
    forensic_scan(FILE_PATH)
