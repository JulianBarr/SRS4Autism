#!/usr/bin/env python3
"""
Phase 4: Universal Migration (Final Fix)
----------------------------------------
Improvements:
1. Regex now captures 'srs-kg:imageFilePath' (recovering ~3500 images).
2. Regex captures 'rdf:type' alias for 'a' (recovering more subjects).
3. Robustly handles URI generation.
"""

import re
import sys
import hashlib
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

try:
    from pypinyin import lazy_pinyin, Style
except ImportError:
    print("ERROR: pypinyin not installed. Run: pip install pypinyin")
    sys.exit(1)

# Namespaces
SRS_INST = Namespace("http://srs4autism.com/instance/")
SRS_KG = Namespace("http://srs4autism.com/schema/")

# Paths
REPO_ROOT = Path(__file__).parent.parent
TARGET_FILE = REPO_ROOT / "knowledge_graph/world_model_complete.ttl"
SOURCE_FILE = REPO_ROOT / "knowledge_graph/world_model_legacy_backup.ttl"
OUTPUT_FILE = REPO_ROOT / "knowledge_graph/world_model_v2_enriched.ttl"

# Regex Patterns
# 1. Subject Definition: "srs-inst:foo a srs-kg:Word" OR "srs-inst:foo rdf:type srs-kg:Word"
RE_SUBJECT = re.compile(r'^\s*(\S+)\s+(?:a|rdf:type)\s+(\S+)')

# 2. Images: Catch ALL variants (image, imageFileName, imageFilePath, hasVisualization)
RE_IMAGE = re.compile(r'(?:srs-kg:image|srs-kg:imageFileName|srs-kg:imageFilePath|hasVisualization)\s+[<"]?([^">]+)[">]?')

def clean_uri_key(uri_str):
    return uri_str.replace('<', '').replace('>', '').replace('srs-inst:', '').strip()

def clean_pinyin_for_uri(text):
    if not text: return "unknown"
    parts = lazy_pinyin(text, style=Style.NORMAL)
    clean = "".join(parts).lower()
    return re.sub(r'[^a-z0-9]', '', clean)

def clean_english_for_uri(text):
    if not text: return "unknown"
    clean = text.lower()
    return re.sub(r'[^a-z0-9]', '', clean)

def is_chinese(text):
    return any('\u4e00' <= c <= '\u9fff' for c in text)

def get_hash_uri(prefix, text):
    hash_digest = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
    return SRS_INST[f"{prefix}_{hash_digest}"]

def main():
    print("🚀 STARTING UNIVERSAL MIGRATION (FINAL)...")
    
    # 1. Load V2 Skeleton
    print(f"📖 Loading V2 Skeleton...")
    g = Graph()
    g.parse(TARGET_FILE, format="turtle")
    g.bind("srs-inst", SRS_INST)
    g.bind("srs-kg", SRS_KG)
    
    existing_text_map = {}
    for w in g.subjects(RDF.type, SRS_KG.Word):
        for label in g.objects(w, RDFS.label):
            existing_text_map[str(label)] = w

    # 2. Scrape Legacy File
    print(f"🕵️  Scraping Legacy Data...")
    
    words = {}      
    sentences = {}  
    grammar = {}    
    
    current_subject = None
    current_type = None
    
    with open(SOURCE_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            
            # A. Detect New Block
            m_subj = RE_SUBJECT.match(line)
            if m_subj:
                raw_subj, raw_type = m_subj.groups()
                current_subject = clean_uri_key(raw_subj)
                
                if "Word" in raw_type or "Concept" in raw_type:
                    current_type = "word"
                    if current_subject not in words: words[current_subject] = {'imgs': []}
                elif "Sentence" in raw_type:
                    current_type = "sentence"
                    if current_subject not in sentences: sentences[current_subject] = {'imgs': []}
                elif "GrammarPoint" in raw_type:
                    current_type = "grammar"
                    if current_subject not in grammar: grammar[current_subject] = {'imgs': []}
                else:
                    current_type = "other"
                continue

            # B. Extract Properties
            if current_subject:
                # Images
                m_img = RE_IMAGE.search(line)
                if m_img:
                    img_file = Path(m_img.group(1)).name
                    if current_type == "word": words[current_subject]['imgs'].append(img_file)
                    elif current_type == "sentence": sentences[current_subject]['imgs'].append(img_file)
                    elif current_type == "grammar": grammar[current_subject]['imgs'].append(img_file)

                # Text Content
                if "rdfs:label" in line or "srs-kg:text" in line:
                    if '"' in line:
                        parts = line.split('"')
                        if len(parts) >= 2:
                            text = parts[1]
                            if current_type == "word": words[current_subject]['text'] = text
                            elif current_type == "sentence": sentences[current_subject]['text'] = text
                            elif current_type == "grammar": grammar[current_subject]['title'] = text
                
                # Pinyin / HSK
                if current_type == "word":
                    if "pinyin" in line and '"' in line:
                         words[current_subject]['pinyin'] = line.split('"')[1]
                    if "hskLevel" in line:
                         m_hsk = re.search(r'(\d+)', line)
                         if m_hsk: words[current_subject]['hsk'] = m_hsk.group(1)

    print(f"   ✓ Scraped: {len(words)} Words, {len(sentences)} Sentences, {len(grammar)} Grammar Points.")

    # 3. Inject Data
    print("⚡ Injecting Data into Graph...")
    
    # A. Words
    count_words = 0
    for k, v in words.items():
        if 'text' not in v: continue
        text = v['text']
        
        uri = None
        if text in existing_text_map:
            uri = existing_text_map[text]
        else:
            if is_chinese(text):
                clean_py = clean_pinyin_for_uri(text)
                uri = SRS_INST[f"word_zh_{clean_py}"]
                g.add((uri, RDFS.label, Literal(text, lang="zh")))
                if 'pinyin' in v:
                    g.add((uri, SRS_KG.pinyin, Literal(v['pinyin'])))
            else:
                clean_en = clean_english_for_uri(text)
                if not clean_en or len(clean_en) > 50: continue
                uri = SRS_INST[f"word_en_{clean_en}"]
                g.add((uri, RDFS.label, Literal(text, lang="en")))
            
            g.add((uri, RDF.type, SRS_KG.Word))
            count_words += 1
        
        for img in v['imgs']:
            g.add((uri, SRS_KG.hasVisualization, Literal(img)))
        if 'hsk' in v:
            g.add((uri, SRS_KG.hskLevel, Literal(v['hsk'], datatype=XSD.integer)))

    # B. Sentences
    count_sent = 0
    for k, v in sentences.items():
        if 'text' not in v: continue
        uri = get_hash_uri("sentence", v['text'])
        g.add((uri, RDF.type, SRS_KG.Sentence))
        g.add((uri, SRS_KG.text, Literal(v['text'], lang="zh")))
        for img in v['imgs']:
            g.add((uri, SRS_KG.hasVisualization, Literal(img)))
        count_sent += 1

    # C. Grammar
    count_gp = 0
    for k, v in grammar.items():
        if 'title' not in v: continue
        uri = get_hash_uri("gp", v['title'])
        g.add((uri, RDF.type, SRS_KG.GrammarPoint))
        g.add((uri, RDFS.label, Literal(v['title'])))
        for img in v['imgs']:
            g.add((uri, SRS_KG.hasVisualization, Literal(img)))
        count_gp += 1

    print(f"   ✓ Injected: {count_words} New Words, {count_sent} Sentences, {count_gp} Grammar Points.")

    # 4. Save
    print(f"💾 Saving to {OUTPUT_FILE.name}...")
    g.serialize(OUTPUT_FILE, format="turtle")
    print("✅ DONE.")

if __name__ == "__main__":
    main()
