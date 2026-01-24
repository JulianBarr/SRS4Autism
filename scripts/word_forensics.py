import re
from pathlib import Path

RESCUED = Path("knowledge_graph/world_model_rescued.ttl")
MASTER = Path("knowledge_graph/world_model_final_master.ttl")

def get_stats(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        "words": len(re.findall(r' a (?:ns1|srs-kg):Word', content)),
        "logic_city_space": len(re.findall(r'"Logic City"', content)),
        "logic_city_underscore": len(re.findall(r'"Logic_City"', content)),
        "hsk_levels": len(re.findall(r'hskLevel \d', content)),
        "bad_chars": len(re.findall(r'srs-kg:img-[^\s;.]+[\(\)]', content)),
        "size_mb": file_path.stat().st_size / (1024 * 1024)
    }

def audit():
    print(f"🧐 comparing Files...")
    r_stats = get_stats(RESCUED)
    m_stats = get_stats(MASTER)

    print(f"\n--- {RESCUED.name} (Current) ---")
    print(f"Words: {r_stats['words']}")
    print(f"Logic City tags (Correct): {r_stats['logic_city_space']}")
    print(f"Logic City tags (Broken): {r_stats['logic_city_underscore']}")
    print(f"HSK Level tags: {r_stats['hsk_levels']}")
    print(f"IDs with bad ( ) characters: {r_stats['bad_chars']}")
    print(f"File Size: {r_stats['size_mb']:.2f} MB")

    print(f"\n--- {MASTER.name} (Proposed) ---")
    print(f"Words: {m_stats['words']}")
    print(f"Logic City tags (Correct): {m_stats['logic_city_space']}")
    print(f"Logic City tags (Broken): {m_stats['logic_city_underscore']}")
    print(f"HSK Level tags: {m_stats['hsk_levels']}")
    print(f"IDs with bad ( ) characters: {m_stats['bad_chars']}")
    print(f"File Size: {m_stats['size_mb']:.2f} MB")

if __name__ == "__main__":
    audit()
