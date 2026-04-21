#!/usr/bin/env python3
"""
Localize English Grammar to Chinese using Gemini

This script:
1. Queries English grammar points from the KG
2. Uses Gemini to generate Chinese explanations
3. Adds Chinese labels/explanations to the KG
4. Uses checkpoint system to handle interruptions
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup Gemini
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
load_dotenv(project_root / "backend" / "gemini.env")

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not found in environment variables")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-pro-preview')

# Define namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")

# File paths
KG_FILE = project_root / "knowledge_graph" / "world_model_english.ttl"
CHECKPOINT_FILE = project_root / "data" / "content_db" / "grammar_localization_checkpoint.json"


def load_checkpoint() -> Dict:
    """Load checkpoint data"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'processed': [], 'failed': []}


def save_checkpoint(checkpoint: Dict):
    """Save checkpoint data"""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def get_english_grammar_points(graph: Graph) -> List[Dict]:
    """Query English grammar points from KG"""
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?uri ?label ?code ?category ?cefr ?sentenceType ?notes WHERE {
        ?uri a srs-kg:GrammarPoint .
        ?uri rdfs:label ?label .
        OPTIONAL { ?uri srs-kg:code ?code }
        OPTIONAL { ?uri srs-kg:category ?category }
        OPTIONAL { ?uri srs-kg:cefrLevel ?cefr }
        OPTIONAL { ?uri srs-kg:sentenceType ?sentenceType }
        OPTIONAL { ?uri srs-kg:notes ?notes }
        FILTER(LANG(?label) = "en")
    }
    ORDER BY ?cefr ?category ?label
    """
    
    results = graph.query(query)
    grammar_points = []
    
    for row in results:
        grammar_points.append({
            'uri': str(row.uri),
            'label': str(row.label),
            'code': str(row.code) if row.code else None,
            'category': str(row.category) if row.category else None,
            'cefr': str(row.cefr) if row.cefr else None,
            'sentence_type': str(row.sentenceType) if row.sentenceType else None,
            'notes': str(row.notes) if row.notes else None
        })
    
    return grammar_points


def generate_chinese_explanation(grammar_point: Dict) -> Optional[str]:
    """Generate Chinese explanation using Gemini"""
    
    # Build prompt with context
    prompt = f"""你是一位专业的英语教师，正在为以中文为母语的学生解释英语语法点。

请为以下英语语法点生成简洁、清晰的中文解释（不超过80个汉字）：

语法点：{grammar_point['label']}
"""
    
    if grammar_point.get('cefr'):
        prompt += f"CEFR等级：{grammar_point['cefr']}\n"
    
    if grammar_point.get('category'):
        category_map = {
            'PP': '现在进行时/be动词',
            'MD': '情态动词',
            'TA': '时态和体',
            'PASS': '被动语态',
            'VP': '动词模式',
            'TO': 'to不定式',
            'SUBJ': '主语',
            'INTF': '程度副词',
            'DT': '限定词',
            'IN': '介词',
            'INT': '疑问词',
            'IMP': '祈使句',
            'CC': '并列连词',
            'CL': '从句'
        }
        category_zh = category_map.get(grammar_point['category'], grammar_point['category'])
        prompt += f"类别：{category_zh}\n"
    
    if grammar_point.get('sentence_type'):
        stype_map = {
            'affirmative_declarative': '肯定陈述句',
            'negative_declarative': '否定陈述句',
            'affirmative_interrogative': '肯定疑问句',
            'negative_interrogative': '否定疑问句',
            'declarative': '陈述句',
            'imperative': '祈使句'
        }
        stype_zh = stype_map.get(grammar_point['sentence_type'], grammar_point['sentence_type'])
        prompt += f"句型：{stype_zh}\n"
    
    prompt += """
要求：
1. 用简单的中文解释这个语法点的用法
2. 如果可能，给出一个简短的中文例句
3. 语言要简洁、适合儿童理解
4. 不超过80个汉字
5. 直接返回解释，不要加"解释："等前缀

示例格式：
"I am" - 表示"我是/我在"，用来介绍自己或描述自己的状态。例如：I am happy（我很开心）
"""
    
    try:
        response = model.generate_content(prompt)
        if response.text:
            return response.text.strip()
        return None
    except Exception as e:
        print(f"  ⚠️  Gemini API error: {e}")
        return None


def localize_grammar_points(graph: Graph, grammar_points: List[Dict], 
                            checkpoint: Dict, batch_size: int = 10,
                            delay: float = 7.0) -> Dict[str, int]:
    """
    Localize grammar points to Chinese
    
    Note: Gemini API has a limit of 10 requests/minute for gemini-2.0-flash-exp.
    With 7-second delay, we can process ~8.5 items/minute safely.
    """
    
    stats = {
        'total': len(grammar_points),
        'processed': len(checkpoint['processed']),
        'localized': 0,
        'failed': len(checkpoint['failed']),
        'skipped': 0
    }
    
    # Calculate estimated time
    remaining = stats['total'] - stats['processed'] - stats['failed']
    estimated_minutes = (remaining * delay) / 60
    
    print(f"\n🌏 Localizing {stats['total']} grammar points to Chinese...")
    print(f"   Already processed: {stats['processed']}")
    print(f"   Failed in previous runs: {stats['failed']}")
    print(f"   Remaining: {remaining}")
    print(f"   ⏱️  Estimated time: {estimated_minutes:.1f} minutes ({estimated_minutes/60:.1f} hours)")
    print(f"   Rate limit: 10 req/min, using {delay}s delay")
    
    for i, gp in enumerate(grammar_points, 1):
        # Skip if already processed
        if gp['uri'] in checkpoint['processed']:
            stats['skipped'] += 1
            continue
        
        # Skip if previously failed
        if gp['uri'] in checkpoint['failed']:
            stats['skipped'] += 1
            continue
        
        # Progress indicator
        if i % 10 == 0 or i == 1:
            print(f"\n  Progress: {i}/{stats['total']} ({i*100//stats['total']}%)")
        
        print(f"  🔄 {gp['label'][:60]}...", end=' ')
        
        # Generate Chinese explanation
        chinese_explanation = generate_chinese_explanation(gp)
        
        if chinese_explanation:
            # Add Chinese label to graph
            grammar_uri = URIRef(gp['uri'])
            graph.add((grammar_uri, RDFS.label, Literal(chinese_explanation, lang='zh')))
            
            stats['localized'] += 1
            stats['processed'] += 1
            checkpoint['processed'].append(gp['uri'])
            
            print(f"✅ {chinese_explanation[:40]}...")
        else:
            stats['failed'] += 1
            checkpoint['failed'].append(gp['uri'])
            print("❌ Failed")
        
        # Save checkpoint every batch_size items
        if i % batch_size == 0:
            save_checkpoint(checkpoint)
            print(f"  💾 Checkpoint saved ({stats['processed']} processed)")
        
        # Rate limiting
        time.sleep(delay)
    
    # Final checkpoint save
    save_checkpoint(checkpoint)
    
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Localize English Grammar to Chinese')
    parser.add_argument('--auto-yes', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("=" * 80)
    print("Localize English Grammar to Chinese")
    print("=" * 80)
    
    # Load checkpoint
    checkpoint = load_checkpoint()
    print(f"\n📂 Loaded checkpoint: {len(checkpoint['processed'])} processed, {len(checkpoint['failed'])} failed")
    
    # Load knowledge graph
    print(f"\n📊 Loading knowledge graph: {KG_FILE}")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("dbo", DBO)
    graph.bind("dbr", DBR)
    
    if not KG_FILE.exists():
        print(f"❌ KG file not found: {KG_FILE}")
        sys.exit(1)
    
    try:
        graph.parse(str(KG_FILE), format="turtle")
        print(f"✅ Loaded {len(graph)} triples")
    except Exception as e:
        print(f"❌ Error loading KG: {e}")
        sys.exit(1)
    
    # Get English grammar points
    grammar_points = get_english_grammar_points(graph)
    print(f"✅ Found {len(grammar_points)} English grammar points")
    
    # Filter out already processed
    remaining = [gp for gp in grammar_points 
                 if gp['uri'] not in checkpoint['processed'] 
                 and gp['uri'] not in checkpoint['failed']]
    
    if not remaining:
        print("\n✅ All grammar points already localized!")
    else:
        print(f"\n🎯 {len(remaining)} grammar points remaining to localize")
        
        # Ask for confirmation (unless auto-yes flag is set)
        if not args.auto_yes:
            response = input("\nStart localization? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Localization cancelled")
                return
        else:
            print("\n▶️  Starting localization (auto-yes enabled)...")
        
        # Localize grammar points
        # Use 7-second delay to stay within 10 requests/minute limit
        stats = localize_grammar_points(graph, grammar_points, checkpoint, 
                                       batch_size=10, delay=7.0)
        
        # Print statistics
        print("\n" + "=" * 80)
        print("📊 Statistics")
        print("=" * 80)
        print(f"Total grammar points: {stats['total']}")
        print(f"Newly localized: {stats['localized']}")
        print(f"Already processed: {stats['skipped']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total processed: {stats['processed']}")
        
        # Save knowledge graph
        print(f"\n💾 Saving knowledge graph to: {KG_FILE}")
        graph.serialize(destination=str(KG_FILE), format="turtle")
        print(f"✅ Saved {len(graph)} triples")
    
    # Show sample localizations
    print("\n" + "=" * 80)
    print("📝 Sample Localizations")
    print("=" * 80)
    
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?labelEn ?labelZh WHERE {
        ?gp a srs-kg:GrammarPoint .
        ?gp rdfs:label ?labelEn .
        ?gp rdfs:label ?labelZh .
        FILTER(LANG(?labelEn) = "en")
        FILTER(LANG(?labelZh) = "zh")
    }
    LIMIT 10
    """
    
    results = graph.query(query)
    for row in results:
        print(f"\nEN: {row.labelEn}")
        print(f"ZH: {row.labelZh}")
    
    print("\n" + "=" * 80)
    print("✅ Localization complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

