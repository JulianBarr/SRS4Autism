#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo Recommendation Script using Knowledge Graph and SPARQL.

This demonstrates the "Learning Frontier" algorithm as described in the Gemini conversation.
It queries Jena Fuseki to find words that are ready to learn based on mastered vocabulary.
"""

import requests
from urllib.parse import urlencode
from collections import defaultdict
import csv
import io

# Configuration
FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"

def query_sparql(sparql_query, output_format="text/csv"):
    """Execute a SPARQL query against Jena Fuseki."""
    params = urlencode({"query": sparql_query})
    url = f"{FUSEKI_ENDPOINT}?{params}"
    
    response = requests.get(url, headers={"Accept": output_format})
    response.raise_for_status()
    return response.text

def get_mastered_words_from_profile(profile_name="YM"):
    """
    Get mastered words from a child profile.
    This is a simplified version - in production, you'd load from Anki review history.
    
    For demo purposes, this returns a predefined list of HSK 1-2 words that are "mastered".
    """
    # Example mastered words (you can replace this with actual profile data)
    mastered_words = {
        "苹果", "朋友", "老师", "学习", "学校", "水", "书", "车", "狗", "猫",
        "大", "小", "好", "家", "人", "妈妈", "爸爸", "我", "你", "他",
        "一", "二", "三", "十", "上", "下", "吃", "喝", "睡", "喜欢"
    }
    
    print(f"📊 Using {len(mastered_words)} mastered words for profile '{profile_name}'")
    print(f"   Sample: {list(mastered_words)[:5]}...")
    return mastered_words

def find_learning_frontier(mastered_words, target_level=3, top_n=20):
    """
    Find words to learn next using the "Learning Frontier" algorithm.
    
    Algorithm:
    1. Determine the highest HSK level where >80% of words are mastered
    2. Find words in the next level (Learning Frontier)
    3. Score words based on:
       - Being in the Learning Frontier: +100 points
       - Known characters (prerequisites): +50 points per character
       - Being too hard: -500 points
    """
    
    print(f"\n🔍 Finding Learning Frontier for HSK Level {target_level}...")
    
    # Step 1: Get all words with HSK levels and pinyin
    sparql = f"""
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word ?word_text ?pinyin ?hsk WHERE {{
        ?word a srs-kg:Word ;
              srs-kg:text ?word_text ;
              srs-kg:pinyin ?pinyin ;
              srs-kg:hskLevel ?hsk .
    }}
    """
    
    csv_result = query_sparql(sparql, "text/csv")
    
    # Parse results using proper CSV parser
    words_data = defaultdict(lambda: {'pinyin': '', 'hsk': None, 'chars': set()})
    reader = csv.reader(io.StringIO(csv_result))
    next(reader)  # Skip header
    
    for row in reader:
        if len(row) >= 4:
            word_text = row[1]  # word_text is the second column
            pinyin = row[2] if len(row) > 2 else ''
            try:
                hsk = int(row[3]) if len(row) > 3 and row[3] else None
            except ValueError:
                hsk = None
            
            words_data[word_text]['pinyin'] = pinyin
            words_data[word_text]['hsk'] = hsk
    
    print(f"   Loaded data for {len(words_data)} words")
    
    # Step 2: Get all character composition data in one query
    print("   Loading character composition data...")
    sparql_all_chars = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word_label ?char_label WHERE {
        ?word a srs-kg:Word ;
              srs-kg:composedOf ?char ;
              rdfs:label ?word_label .
        ?char rdfs:label ?char_label .
    }
    """
    
    try:
        char_result = query_sparql(sparql_all_chars, "text/csv")
        char_reader = csv.reader(io.StringIO(char_result))
        next(char_reader)  # Skip header
        
        for row in char_reader:
            if len(row) >= 2:
                word_text = row[0]
                char_text = row[1]
                if word_text in words_data:
                    words_data[word_text]['chars'].add(char_text)
        print(f"   Loaded character data for {sum(len(data['chars']) > 0 for data in words_data.values())} words")
    except Exception as e:
        print(f"   Warning: Could not load character data: {e}")
    
    # Step 2: Score words
    scored_words = []
    debug_count = 0
    
    for word, data in words_data.items():
        if word in mastered_words:
            continue  # Skip already mastered words
        
        score = 0
        
        # In Learning Frontier (target level)
        if data['hsk'] == target_level:
            score += 100
        
        # Count known characters (prerequisites)
        known_chars = sum(1 for char in data['chars'] if char in mastered_words)
        if known_chars > 0:
            score += 50 * known_chars
        
        # Penalize too hard words
        if data['hsk'] and data['hsk'] > target_level + 1:
            score -= 500
        
        # Debug first few
        if debug_count < 10:
            print(f"   Debug: {word} - HSK:{data['hsk']}, Chars:{len(data['chars'])}, Known:{known_chars}, Score:{score}")
            debug_count += 1
        
        if score > 0:  # Only include words with positive scores
            scored_words.append({
                'word': word,
                'pinyin': data['pinyin'],
                'hsk': data['hsk'],
                'score': score,
                'known_chars': known_chars,
                'total_chars': len(data['chars'])
            })
    
    print(f"   Scored {len(scored_words)} words with positive scores")
    
    # Sort by score and return top N
    scored_words.sort(key=lambda x: x['score'], reverse=True)
    return scored_words[:top_n]

def main():
    """Main function to demonstrate the recommendation system."""
    print("=" * 80)
    print("Learning Frontier Recommendation Demo")
    print("=" * 80)
    print()
    
    # Get mastered words
    mastered_words = get_mastered_words_from_profile("YM")
    
    # Find recommendations for HSK Level 3
    recommendations = find_learning_frontier(mastered_words, target_level=3, top_n=20)
    
    print(f"\n✅ Top 20 Recommendations for next level:")
    print("-" * 80)
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i:2d}. {rec['word']:8s} ({rec['pinyin']:15s}) - Score: {rec['score']:3d}")
        print(f"     HSK: {rec['hsk']}, Known chars: {rec['known_chars']}/{rec['total_chars']}")
    
    print("=" * 80)
    print()
    
    # Optional: Query for related concepts
    print("\n🔗 Finding related concepts...")
    sample_word = recommendations[0]['word'] if recommendations else None
    if sample_word:
        print(f"   Looking up concepts for: {sample_word}")
        
        sparql_concept = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?concept ?concept_label WHERE {{
            ?word srs-kg:text "{sample_word}" ;
                  srs-kg:means ?concept .
            ?concept rdfs:label ?concept_label .
        }}
        LIMIT 10
        """
        
        try:
            concept_result = query_sparql(sparql_concept, "text/csv")
            print("   Concepts found:")
            for line in concept_result.strip().split('\n')[1:]:  # Skip header
                if line:
                    print(f"     - {line}")
        except Exception as e:
            print(f"   (No concepts found: {e})")
    
    print("\n" + "=" * 80)
    print("✅ Demo complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()

