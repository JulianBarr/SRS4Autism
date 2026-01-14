import re
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_clean.ttl"

def main():
    print(f"🧹 Sanitizing {INPUT_FILE.name} (V3 Aggressive)....")
    
    if not INPUT_FILE.exists():
        print("❌ Error: Input file not found.")
        return

    fixed_count = 0
    line_num = 0
    
    # Regex to find Prefixed URIs (QNames) that might be broken.
    # Group 1: Prefix (e.g., "srs-inst:gp-")
    # Group 2: The "Dirty" Local Part (until the next space, semicolon, or dot)
    # This version is more aggressive, capturing more potential URI issues.
    uri_pattern = re.compile(r'(srs-(?:inst|kg):[a-zA-Z0-9\-_]*)([^;\.>\)\]\s]*)(?=[\s;\.>\)\]])|(<\S+>)')
    
    # Regex to find and clean literal strings (e.g., "Some dirty string").
    # This will clean characters within the quotes.
    literal_pattern = re.compile(r'"([^"]*)"')

    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            line_num += 1
            
            def sanitize_uri_match(match):
                # Handle full URI matches (e.g., <http://example.com/some dirty uri>)
                if match.group(3): # The full URI group
                    # Do NOT sanitize full http/https URIs, they should be valid already.
                    return match.group(0)

                # Handle prefixed URI matches (e.g., srs-inst:gp-Some Dirty Name)
                prefix = match.group(1)
                dirty_suffix = match.group(2)

                # Always clean spaces and non-ASCII chars for prefixed URIs
                clean_suffix = re.sub(r'[ \(\)\'"%]|[^\w\-]', '_', dirty_suffix)
                clean_suffix = re.sub(r'_+', '_', clean_suffix).strip('_')
                return f"{prefix}{clean_suffix}"
            
            def sanitize_literal_match(match):
                dirty_literal = match.group(1)
                # Clean non-ASCII characters, but allow spaces within literals
                clean_literal = re.sub(r'[^\x00-\x7F]', ' ', dirty_literal) 
                clean_literal = re.sub(r'\s+', ' ', clean_literal).strip() 
                return f'"{clean_literal}"'

            # Apply URI sanitizer
            new_line = uri_pattern.sub(sanitize_uri_match, line)
            # Apply literal sanitizer
            new_line = literal_pattern.sub(sanitize_literal_match, new_line)
            
            if new_line != line:
                fixed_count += 1
                if fixed_count <= 3: 
                    print(f"  [L{line_num}] Fixed: ...{line.strip()[-30:]} -> ...{new_line.strip()[-30:]}")
            
            outfile.write(new_line)

    print(f"\n✅ Done! Fixed {fixed_count} lines.")
    print(f"  Saved to: {OUTPUT_FILE.name}")

if __name__ == "__main__":
    main()
