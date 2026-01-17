import re
from pathlib import Path

# Paths - Ensure these are correct for your machine
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_clean.ttl"

def main():
    print(f"🧹 Sanitizing {INPUT_FILE.name} (Protecting Chinese Characters)...")
    
    if not INPUT_FILE.exists():
        print(f"❌ Error: {INPUT_FILE} not found!")
        return

    # Regex to find URIs like srs-inst:something with spaces
    # It looks for srs-inst: followed by characters until it hits a keyword
    uri_pattern = re.compile(r'(srs-(?:inst|kg):)([^\s;.\n]+)')

    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            # IMPORTANT: Split the line by double quotes.
            # Parts 0, 2, 4... are URIs/Syntax (Outside quotes)
            # Parts 1, 3, 5... are Labels (Inside quotes)
            parts = line.split('"')
            
            for i in range(len(parts)):
                if i % 2 == 0:  # OUTSIDE quotes: Fix the URIs
                    def clean_uri(match):
                        prefix = match.group(1)
                        body = match.group(2)
                        # Replace spaces, parens, and illegal chars with underscores
                        clean_body = re.sub(r'[ \(\)\%]', '_', body)
                        # Remove trailing underscores for a cleaner URI
                        clean_body = clean_body.strip('_')
                        return f"{prefix}{clean_body}"
                    
                    parts[i] = uri_pattern.sub(clean_uri, parts[i])
                
                # if i % 2 != 0: Inside quotes. WE DO NOTHING. 
                # This keeps "你好"@zh perfectly safe.

            outfile.write('"'.join(parts))

    print(f"\n✅ Cleaned file saved to: {OUTPUT_FILE.name}")

if __name__ == "__main__":
    main()
