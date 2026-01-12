from pathlib import Path

def debug_grammar_structure():
    file_path = Path("knowledge_graph/world_model_complete.ttl")
    if not file_path.exists():
        print(f"❌ File not found at: {file_path.absolute()}")
        return

    print(f"🔍 Scanning {file_path.name} for GrammarPoint definitions...")
    
    found_count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        # Read all lines is safe for text files < 500MB
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        # We look for the exact string 'GrammarPoint' to find definitions
        if "GrammarPoint" in line:
            found_count += 1
            print(f"\n--- Match #{found_count} at line {i+1} ---")
            
            # Print context (2 lines before, 10 lines after) to see properties
            start = max(0, i - 2)
            end = min(len(lines), i + 10)
            
            for j in range(start, end):
                prefix = ">> " if j == i else "   "
                print(f"{prefix}{j+1}: {lines[j].rstrip()}")
            
            if found_count >= 3:  # Just show me 3 examples
                break
                
    if found_count == 0:
        print("❌ No 'GrammarPoint' string found in the file. Is it named something else?")

if __name__ == "__main__":
    debug_grammar_structure()
