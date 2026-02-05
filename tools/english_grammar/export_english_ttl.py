import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
JSON_PATH = BASE_DIR / "english_grammar_staging.json"
OUTPUT_TTL = BASE_DIR / "english_grammar_layer.ttl"

PREFIXES = """@prefix : <http://srs4autism.com/instance/> .
@prefix srs-kg: <http://srs4autism.com/schema/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]', '_', text).strip('_')

def escape(text):
    if not text: return ""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

def convert(item):
    uri = f":EnGrammar_{slugify(item['grammar_point_en'])}_{item['id']}"
    lines = [f"{uri} a srs-kg:GrammarPoint ;"]
    
    # Labels
    lines.append(f'    rdfs:label "{escape(item["grammar_point_en"])}"@en ;')
    if item.get('grammar_point_cn'):
        lines.append(f'    rdfs:label "{escape(item["grammar_point_cn"])}"@zh ;')
    
    # Explanations
    if item.get('summary_en'):
        lines.append(f'    srs-kg:explanation "{escape(item["summary_en"])}"@en ;')
    if item.get('summary_cn'):
        lines.append(f'    srs-kg:explanation "{escape(item["summary_cn"])}"@zh ;')

    lines.append(f'    srs-kg:cefrLevel "{item.get("level", "Unknown")}" ;')
    lines.append(f'    srs-kg:language "English" ;')
    
    # --- FIX 1: Add Source ID for Sorting ---
    if item.get('source_id'):
        lines.append(f'    srs-kg:sourceId "{item["source_id"]}" ;')

    if item.get('anchor_example'):
        lines.append(f'    srs-kg:anchorExample "{escape(item["anchor_example"])}"@en ;')

    lines.append(f'    srs-kg:sourceType "cefr-j" .')
    return "\n".join(lines)

def main():
    if not JSON_PATH.exists(): return
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"🔄 Exporting {len(data)} items...")
    content = [PREFIXES] + [convert(x) for x in data]
    
    with open(OUTPUT_TTL, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(content))
    print(f"✅ Exported to {OUTPUT_TTL}")

if __name__ == "__main__":
    main()
