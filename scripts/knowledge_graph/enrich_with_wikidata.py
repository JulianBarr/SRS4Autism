#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrich knowledge graph concepts with Wikidata Q-IDs.

This script:
1. Loads Chinese words from the knowledge graph
2. Gets English translations from CC-CEDICT
3. Searches Wikidata API for matching concepts
4. Links concepts to Wikidata Q-IDs
5. Updates the knowledge graph

Based on the strategy from "Align different languages to the single global concept.md"
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, OWL
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import CC-CEDICT loader
try:
    from scripts.knowledge_graph.load_cc_cedict import (
        load_cedict_file, get_english_translations, find_cedict_file
    )
except ImportError:
    print("⚠️  Warning: Could not import CC-CEDICT loader")
    print("   Make sure load_cc_cedict.py is in the same directory")

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_cwn.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'
CHECKPOINT_FILE = project_root / 'data' / 'content_db' / 'wikidata_enrichment_checkpoint.json'

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")
WIKIDATA_PROP = Namespace("http://www.wikidata.org/prop/direct/")

# Wikidata API endpoints
WIKIDATA_SEARCH_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_QUERY_API = "https://query.wikidata.org/sparql"


def search_wikidata(search_term, language='en', limit=5):
    """
    Search Wikidata for a term and return matching Q-IDs.
    
    Args:
        search_term: Term to search for (e.g., "cat")
        language: Language code (default: 'en')
        limit: Maximum number of results (default: 5)
    
    Returns: List of dicts with 'id', 'label', 'description'
    """
    params = {
        'action': 'wbsearchentities',
        'search': search_term,
        'language': language,
        'format': 'json',
        'limit': limit
    }
    
    query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
    url = f"{WIKIDATA_SEARCH_API}?{query_string}"
    
    try:
        request = Request(url)
        request.add_header('User-Agent', 'SRS4Autism/1.0 (https://github.com/your-repo)')
        
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            results = []
            for item in data.get('search', []):
                results.append({
                    'id': item.get('id'),  # e.g., 'Q146'
                    'label': item.get('label'),  # e.g., 'cat'
                    'description': item.get('description', '')  # e.g., 'domesticated species...'
                })
            
            return results
    except (URLError, HTTPError) as e:
        print(f"    ⚠️  Error searching Wikidata for '{search_term}': {e}")
        return []
    except Exception as e:
        print(f"    ⚠️  Unexpected error searching Wikidata: {e}")
        return []


def get_wikidata_labels(qid, languages=['en', 'zh']):
    """
    Get multilingual labels for a Wikidata Q-ID.
    
    Args:
        qid: Wikidata Q-ID (e.g., 'Q146')
        languages: List of language codes
    
    Returns: Dict mapping language -> label
    """
    lang_str = '|'.join(languages)
    params = {
        'action': 'wbgetentities',
        'ids': qid,
        'props': 'labels',
        'languages': lang_str,
        'format': 'json'
    }
    
    query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
    url = f"{WIKIDATA_SEARCH_API}?{query_string}"
    
    try:
        request = Request(url)
        request.add_header('User-Agent', 'SRS4Autism/1.0')
        
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            entities = data.get('entities', {})
            entity = entities.get(qid, {})
            labels = entity.get('labels', {})
            
            result = {}
            for lang in languages:
                if lang in labels:
                    result[lang] = labels[lang].get('value', '')
            
            return result
    except Exception as e:
        print(f"    ⚠️  Error getting labels for {qid}: {e}")
        return {}


def find_best_wikidata_match(english_term, chinese_word=None):
    """
    Find the best Wikidata Q-ID match for an English term.
    
    Strategy:
    1. Search Wikidata using the full English term (not just first word)
    2. If Chinese word provided, validate matches by checking Chinese labels
    3. Prefer exact matches, then partial matches
    4. Avoid overly generic matches (like "Chinese" language for "Chinese person")
    
    Args:
        english_term: English translation (e.g., "Chinese person", "cat")
        chinese_word: Optional Chinese word for validation
    
    Returns: Q-ID string (e.g., "Q146") or None
    """
    if not english_term:
        return None
    
    # Clean the search term - use full phrase if meaningful, otherwise first word
    # Remove common words like "the", "a", "an", "to", "of"
    cleaned = re.sub(r'\b(the|a|an|to|of|in|on|at|for|with|by)\b', '', english_term.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Extract meaningful words (3+ chars)
    search_words = re.findall(r'\b[a-zA-Z]{3,}\b', cleaned)
    if not search_words:
        return None
    
    # Try full phrase first if it has multiple words, otherwise use first word
    if len(search_words) > 1:
        search_terms = [' '.join(search_words), search_words[0]]
    else:
        search_terms = [search_words[0]]
    
    # Search Wikidata with each term
    all_results = []
    for search_term in search_terms:
        results = search_wikidata(search_term, language='en', limit=10)
        if results:
            all_results.extend(results)
            # If we found results with full phrase, prefer those
            if len(search_terms) > 1 and search_term == search_terms[0]:
                break
    
    if not all_results:
        return None
    
    # Remove duplicates while preserving order
    seen = set()
    unique_results = []
    for result in all_results:
        if result['id'] not in seen:
            seen.add(result['id'])
            unique_results.append(result)
    
    # If we have a Chinese word, validate matches
    if chinese_word and len(chinese_word) > 0:
        # Check each result for Chinese label match
        for result in unique_results:
            qid = result['id']
            labels = get_wikidata_labels(qid, languages=['zh'])
            
            if 'zh' in labels:
                zh_label = labels['zh']
                # Exact match is best
                if zh_label == chinese_word:
                    return qid
                # Word appears in label (e.g., "中國人" in "中國人種")
                if chinese_word in zh_label:
                    return qid
                # Label appears in word (e.g., "中國" in "中國人")
                if zh_label in chinese_word and len(zh_label) >= 2:
                    return qid
    
    # If no Chinese validation or no match found, prefer more specific results
    # Filter out overly generic results based on description
    for result in unique_results:
        description = result.get('description', '').lower()
        label = result.get('label', '').lower()
        
        # Skip if it's too generic (e.g., "language" for "Chinese person")
        if description:
            generic_terms = ['language', 'country', 'region', 'group']
            if any(term in description for term in generic_terms) and len(description) < 30:
                continue
        
        # Prefer results with descriptions (more specific)
        if description and len(description) > 15:
            return result['id']
    
    # Fallback to first result
    return unique_results[0]['id']


def load_checkpoint():
    """Load checkpoint of processed concepts."""
    if not CHECKPOINT_FILE.exists():
        return {
            'succeeded': set(),
            'failed_retriable': set(),  # Network errors, timeouts - should retry
            'failed_permanent': set()   # No match found, no translations - skip
        }
    
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Backward compatibility: if old format, migrate it
            if 'processed_concepts' in data:
                old_set = set(data.get('processed_concepts', []))
                return {
                    'succeeded': old_set,
                    'failed_retriable': set(),
                    'failed_permanent': set()
                }
            return {
                'succeeded': set(data.get('succeeded', [])),
                'failed_retriable': set(data.get('failed_retriable', [])),
                'failed_permanent': set(data.get('failed_permanent', []))
            }
    except Exception as e:
        print(f"  ⚠️  Warning: Could not load checkpoint: {e}")
        return {
            'succeeded': set(),
            'failed_retriable': set(),
            'failed_permanent': set()
        }


def save_checkpoint(checkpoint_data):
    """Save checkpoint of processed concepts.
    
    Args:
        checkpoint_data: dict with 'succeeded', 'failed_retriable', 'failed_permanent' sets
    """
    try:
        data = {
            'succeeded': list(checkpoint_data['succeeded']),
            'failed_retriable': list(checkpoint_data['failed_retriable']),
            'failed_permanent': list(checkpoint_data['failed_permanent']),
            'timestamp': time.time()
        }
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️  Warning: Could not save checkpoint: {e}")


def is_retriable_error(error_str):
    """Check if an error is retriable (network/timeout) vs permanent (no match)."""
    if not error_str:
        return False
    error_lower = error_str.lower()
    retriable_keywords = [
        'timeout', 'timed out', 'network', 'unreachable', 
        'connection', 'handshake', 'urlopen error', 
        'http error', 'ssl', 'socket'
    ]
    return any(keyword in error_lower for keyword in retriable_keywords)


def enrich_concept_with_wikidata(graph, concept_uri, qid):
    """
    Add Wikidata Q-ID to a concept node.
    
    Args:
        graph: RDF graph
        concept_uri: URI of the concept node
        qid: Wikidata Q-ID (e.g., 'Q146')
    """
    # Add wikidataId property
    graph.add((concept_uri, SRS_KG.wikidataId, Literal(qid)))
    
    # Add owl:sameAs link to Wikidata entity
    wikidata_uri = WIKIDATA[qid]
    graph.add((concept_uri, OWL.sameAs, wikidata_uri))
    
    # Get multilingual labels and add them
    labels = get_wikidata_labels(qid, languages=['en', 'zh'])
    if 'en' in labels:
        graph.add((concept_uri, RDFS.label, Literal(labels['en'], lang='en')))
    if 'zh' in labels:
        graph.add((concept_uri, RDFS.label, Literal(labels['zh'], lang='zh')))


def process_single_word(word_info):
    """
    Process a single word to find and return Wikidata Q-ID.
    This function is designed to be called in parallel.
    Note: CC-CEDICT is loaded inside to avoid pickling issues.
    
    Returns: dict with 'concept_str', 'qid', 'chinese_text', 'success', 'error'
    """
    chinese_text = word_info['chinese_text']
    concept_str = word_info['concept_str']
    
    try:
        # Load CC-CEDICT once per thread (threading shares memory, so we can use a module-level cache)
        # This avoids reloading in each call within the same thread
        import threading
        thread_id = threading.current_thread().ident
        
        # Use a module-level cache keyed by thread ID
        if not hasattr(process_single_word, '_cedict_cache_by_thread'):
            process_single_word._cedict_cache_by_thread = {}
        
        if thread_id not in process_single_word._cedict_cache_by_thread:
            from scripts.knowledge_graph.load_cc_cedict import find_cedict_file, load_cedict_file
            cedict_file = find_cedict_file()
            if not cedict_file:
                return {
                    'concept_str': concept_str,
                    'qid': None,
                    'chinese_text': chinese_text,
                    'success': False,
                    'error': 'CC-CEDICT not found'
                }
            # Cache it per thread (threads share memory, but this ensures one load per thread)
            process_single_word._cedict_cache_by_thread[thread_id] = load_cedict_file(cedict_file)
        
        cedict_data = process_single_word._cedict_cache_by_thread[thread_id]
        
        # Get English translations from CC-CEDICT
        translations = get_english_translations(cedict_data, chinese_text)
        
        if not translations:
            return {
                'concept_str': concept_str,
                'qid': None,
                'chinese_text': chinese_text,
                'success': False,
                'error': 'No translations found'
            }
        
        # Try first translation with Chinese word for validation
        qid = None
        if translations:
            qid = find_best_wikidata_match(translations[0], chinese_word=chinese_text)
        
        if qid:
            return {
                'concept_str': concept_str,
                'qid': qid,
                'chinese_text': chinese_text,
                'success': True,
                'error': None
            }
        else:
            return {
                'concept_str': concept_str,
                'qid': None,
                'chinese_text': chinese_text,
                'success': False,
                'error': 'No Wikidata match found'
            }
    except Exception as e:
        return {
            'concept_str': concept_str,
            'qid': None,
            'chinese_text': chinese_text,
            'success': False,
            'error': str(e)
        }


def main():
    """Main function to enrich concepts with Wikidata Q-IDs."""
    import sys
    sys.stdout.flush()
    
    print("=" * 80, flush=True)
    print("Enrich Knowledge Graph with Wikidata Concepts", flush=True)
    print("=" * 80, flush=True)
    print(flush=True)
    
    # Load CC-CEDICT
    print("Step 1: Loading CC-CEDICT dictionary...", flush=True)
    cedict_file = find_cedict_file()
    if not cedict_file:
        print("❌ CC-CEDICT file not found.")
        print("   Please download from: https://www.mdbg.net/chinese/dictionary?page=cc-cedict")
        print("   Save as: data/cedict_ts.u8")
        sys.exit(1)
    
    cedict_data = load_cedict_file(cedict_file)
    if not cedict_data:
        print("❌ Failed to load CC-CEDICT data")
        sys.exit(1)
    print()
    
    # Load knowledge graph
    print("Step 2: Loading knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("wd", WIKIDATA)
    graph.bind("wdt", WIKIDATA_PROP)
    
    if KG_FILE.exists():
        try:
            print(f"  Parsing {KG_FILE.name} ({KG_FILE.stat().st_size / 1024 / 1024:.1f} MB)...", flush=True)
            graph.parse(str(KG_FILE), format="turtle")
            print(f"  ✅ Loaded {len(graph)} triples", flush=True)
        except Exception as e:
            print(f"  ❌ ERROR: Could not parse KG file: {e}", flush=True)
            print(f"     The file may be corrupted. Check line ~289942", flush=True)
            print("     Starting with empty graph...", flush=True)
            import traceback
            traceback.print_exc()
    else:
        print(f"  ⚠️  Knowledge graph file not found: {KG_FILE}", flush=True)
        print("     Starting with empty graph...", flush=True)
    
    # Load ontology schema
    if ONTOLOGY_FILE.exists():
        try:
            graph.parse(str(ONTOLOGY_FILE), format="turtle")
            print("  ✅ Schema loaded")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not parse schema: {e}")
    print()
    
    # Load checkpoint
    print("Step 3: Loading checkpoint (if exists)...")
    checkpoint_data = load_checkpoint()
    total_processed = len(checkpoint_data['succeeded']) + len(checkpoint_data['failed_retriable']) + len(checkpoint_data['failed_permanent'])
    if total_processed > 0:
        print(f"  ✅ Found checkpoint:")
        print(f"     - Succeeded: {len(checkpoint_data['succeeded'])}")
        print(f"     - Failed (will retry): {len(checkpoint_data['failed_retriable'])}")
        print(f"     - Failed (permanent): {len(checkpoint_data['failed_permanent'])}")
        print(f"     - Total: {total_processed}")
    else:
        print("  ℹ️  No checkpoint found, starting fresh")
    print()
    
    # Find all Chinese words without Wikidata concepts
    print("Step 4: Finding Chinese words to enrich...")
    words_to_process = []
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        # Get Chinese text
        chinese_text = None
        for _, _, text_literal in graph.triples((word_uri, SRS_KG.text, None)):
            chinese_text = str(text_literal).strip()
            break
        
        if not chinese_text:
            continue
        
        # Get concept
        concept_uri = None
        for _, _, concept in graph.triples((word_uri, SRS_KG.means, None)):
            concept_uri = concept
            break
        
        if not concept_uri:
            continue
        
        # Check if concept already has Wikidata ID in graph
        has_wikidata = False
        for _, _, qid in graph.triples((concept_uri, SRS_KG.wikidataId, None)):
            has_wikidata = True
            break
        
        # Check if already processed (from checkpoint)
        concept_str = str(concept_uri)
        
        # Skip if succeeded or permanently failed
        if concept_str in checkpoint_data['succeeded'] or concept_str in checkpoint_data['failed_permanent']:
            continue
        
        # If it has wikidata but is in failed_retriable, remove it (it succeeded in a previous run)
        if has_wikidata and concept_str in checkpoint_data['failed_retriable']:
            checkpoint_data['failed_retriable'].discard(concept_str)
            checkpoint_data['succeeded'].add(concept_str)
            continue
        
        # Process if: no wikidata, OR it's in failed_retriable (will retry)
        if not has_wikidata or concept_str in checkpoint_data['failed_retriable']:
            words_to_process.append({
                'word_uri': word_uri,
                'chinese_text': chinese_text,
                'concept_uri': concept_uri,
                'concept_str': concept_str
            })
    
    print(f"  Found {len(words_to_process)} words to process")
    skipped = len(checkpoint_data['succeeded']) + len(checkpoint_data['failed_permanent'])
    if skipped > 0:
        print(f"  (Skipped {skipped} already processed: {len(checkpoint_data['succeeded'])} succeeded, {len(checkpoint_data['failed_permanent'])} permanent failures)")
    retrying = len(checkpoint_data['failed_retriable'])
    if retrying > 0:
        print(f"  (Retrying {retrying} concepts that had network errors)")
    print()
    
    if not words_to_process:
        print("✅ All concepts already have Wikidata Q-IDs!")
        return
    
    # Process words
    print("Step 5: Enriching concepts with Wikidata Q-IDs...")
    
    # Check for parallel processing option
    num_workers = int(os.environ.get('WIKIDATA_WORKERS', '4'))  # Default 4 workers
    use_parallel = num_workers > 1 and len(words_to_process) > 100
    
    if use_parallel:
        print(f"  Using {num_workers} parallel workers for faster processing")
        print("  (Set WIKIDATA_WORKERS environment variable to change, e.g., export WIKIDATA_WORKERS=8)")
    else:
        print("  Using single-threaded processing")
        print("  (Set WIKIDATA_WORKERS=4 to enable parallel processing)")
    
    print("  Press Ctrl+C to stop - progress will be saved and can be resumed")
    print()
    
    enriched_count = 0
    failed_count = 0
    start_time = time.time()
    last_save_time = start_time
    
    try:
        if use_parallel:
            # Parallel processing
            print(f"  Processing {len(words_to_process)} words with {num_workers} workers...")
            
            # Process function doesn't need cedict_data (loads it internally)
            # Process in batches to show progress and save checkpoints
            batch_size = 50  # Smaller batches to reduce memory and improve progress visibility
            processed_count = 0
            
            for batch_start in range(0, len(words_to_process), batch_size):
                batch = words_to_process[batch_start:batch_start + batch_size]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(words_to_process) + batch_size - 1) // batch_size
                
                print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} words)...", flush=True)
                
                # Process batch in parallel using threads (avoids pickling issues)
                results = []
                try:
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        # Submit all tasks
                        future_to_word = {executor.submit(process_single_word, word): word for word in batch}
                        
                        # Collect results as they complete
                        for future in as_completed(future_to_word):
                            try:
                                result = future.result()
                                results.append(result)
                            except Exception as e:
                                word = future_to_word[future]
                                print(f"    ⚠️  Error processing {word.get('chinese_text', 'unknown')}: {e}")
                                results.append({
                                    'concept_str': word.get('concept_str', ''),
                                    'qid': None,
                                    'chinese_text': word.get('chinese_text', ''),
                                    'success': False,
                                    'error': str(e)
                                })
                    
                    # Sort results to match input order
                    result_map = {r['concept_str']: r for r in results}
                    results = [result_map.get(word['concept_str'], {
                        'concept_str': word['concept_str'],
                        'qid': None,
                        'chinese_text': word['chinese_text'],
                        'success': False,
                        'error': 'Result not found'
                    }) for word in batch]
                except Exception as e:
                    print(f"    ⚠️  Error in parallel processing: {e}")
                    print(f"    Falling back to sequential processing for this batch...")
                    # Fallback to sequential
                    results = [process_single_word(word) for word in batch]
                
                # Process results and update graph
                for result in results:
                    processed_count += 1
                    concept_str = result['concept_str']
                    chinese_text = result['chinese_text']
                    
                    if result['success'] and result['qid']:
                        # Find the concept URI and enrich it
                        for word_info in words_to_process:
                            if word_info['concept_str'] == concept_str:
                                enrich_concept_with_wikidata(graph, word_info['concept_uri'], result['qid'])
                                enriched_count += 1
                                print(f"    ✅ Linked {chinese_text} → {result['qid']}")
                                break
                        # Mark as succeeded
                        checkpoint_data['failed_retriable'].discard(concept_str)
                        checkpoint_data['failed_permanent'].discard(concept_str)
                        checkpoint_data['succeeded'].add(concept_str)
                    else:
                        failed_count += 1
                        error_msg = result.get('error', 'Unknown error')
                        if result['error'] and 'No translations' not in result['error']:
                            print(f"    ⚠️  {chinese_text}: {error_msg}")
                        
                        # Categorize failure
                        if is_retriable_error(error_msg):
                            # Network/timeout error - mark for retry
                            checkpoint_data['succeeded'].discard(concept_str)
                            checkpoint_data['failed_permanent'].discard(concept_str)
                            checkpoint_data['failed_retriable'].add(concept_str)
                        else:
                            # Permanent failure (no match, no translations) - skip in future
                            checkpoint_data['succeeded'].discard(concept_str)
                            checkpoint_data['failed_retriable'].discard(concept_str)
                            checkpoint_data['failed_permanent'].add(concept_str)
                
                # Show progress
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                remaining = len(words_to_process) - processed_count
                eta_minutes = (remaining / rate / 60) if rate > 0 else 0
                
                print(f"  [{processed_count}/{len(words_to_process)}] Batch complete | "
                      f"Rate: {rate:.1f}/min | "
                      f"ETA: {eta_minutes:.1f}min | "
                      f"✅ {enriched_count} | ❌ {failed_count}")
                
                # Save checkpoint after each batch
                save_checkpoint(checkpoint_data)
                try:
                    graph.serialize(destination=str(KG_FILE), format="turtle")
                    print(f"    💾 Checkpoint saved ({processed_count} words processed)")
                except Exception as e:
                    print(f"    ⚠️  Could not save graph: {e}")
        
        else:
            # Single-threaded processing (original code)
            for idx, word_info in enumerate(words_to_process, 1):
                chinese_text = word_info['chinese_text']
                concept_uri = word_info['concept_uri']
                concept_str = word_info['concept_str']
                
                # Show detailed progress
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = len(words_to_process) - idx
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_minutes = eta_seconds / 60
                
                # Progress every word (with details every 10)
                if idx % 10 == 0 or idx == 1:
                    print(f"  [{idx}/{len(words_to_process)}] {chinese_text} | "
                          f"Rate: {rate:.1f}/min | "
                          f"ETA: {eta_minutes:.1f}min | "
                          f"✅ {enriched_count} | ❌ {failed_count}")
                elif idx % 5 == 0:
                    # Brief progress every 5
                    print(f"  [{idx}/{len(words_to_process)}] Processing... ({rate:.1f}/min, {eta_minutes:.1f}min remaining)")
                
                # Get English translations from CC-CEDICT
                try:
                    translations = get_english_translations(cedict_data, chinese_text)
                    
                    if not translations:
                        failed_count += 1
                        checkpoint_data['succeeded'].discard(concept_str)
                        checkpoint_data['failed_retriable'].discard(concept_str)
                        checkpoint_data['failed_permanent'].add(concept_str)
                        continue
                    
                    # Try each translation until we find a Wikidata match
                    # Use first translation with Chinese word for validation
                    qid = None
                    error_msg = None
                    if translations:
                        try:
                            qid = find_best_wikidata_match(translations[0], chinese_word=chinese_text)
                        except Exception as e:
                            error_msg = str(e)
                    
                    if qid:
                        enrich_concept_with_wikidata(graph, concept_uri, qid)
                        enriched_count += 1
                        print(f"    ✅ Linked {chinese_text} → {qid}")
                        # Success
                        checkpoint_data['failed_retriable'].discard(concept_str)
                        checkpoint_data['failed_permanent'].discard(concept_str)
                        checkpoint_data['succeeded'].add(concept_str)
                    else:
                        failed_count += 1
                        if error_msg:
                            print(f"    ⚠️  {chinese_text}: {error_msg}")
                        else:
                            print(f"    ⚠️  No Wikidata match for {chinese_text}")
                        
                        # Categorize failure
                        final_error = error_msg or f"No Wikidata match for {chinese_text}"
                        if is_retriable_error(final_error):
                            checkpoint_data['succeeded'].discard(concept_str)
                            checkpoint_data['failed_permanent'].discard(concept_str)
                            checkpoint_data['failed_retriable'].add(concept_str)
                        else:
                            checkpoint_data['succeeded'].discard(concept_str)
                            checkpoint_data['failed_retriable'].discard(concept_str)
                            checkpoint_data['failed_permanent'].add(concept_str)
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    print(f"    ⚠️  Error processing {chinese_text}: {error_msg}")
                    # Categorize error
                    if is_retriable_error(error_msg):
                        checkpoint_data['succeeded'].discard(concept_str)
                        checkpoint_data['failed_permanent'].discard(concept_str)
                        checkpoint_data['failed_retriable'].add(concept_str)
                    else:
                        checkpoint_data['succeeded'].discard(concept_str)
                        checkpoint_data['failed_retriable'].discard(concept_str)
                        checkpoint_data['failed_permanent'].add(concept_str)
                
                # Save checkpoint every 50 words or every 5 minutes
                current_time = time.time()
                if idx % 50 == 0 or (current_time - last_save_time) > 300:
                    save_checkpoint(checkpoint_data)
                    # Also save graph periodically
                    try:
                        graph.serialize(destination=str(KG_FILE), format="turtle")
                        last_save_time = current_time
                        print(f"    💾 Checkpoint saved ({idx} words processed)")
                    except Exception as e:
                        print(f"    ⚠️  Could not save graph: {e}")
                
                # Rate limiting - be nice to Wikidata API
                # Reduced from 0.5s to 0.2s since we reduced API calls per word
                time.sleep(0.2)  # 200ms delay between words
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("  Saving checkpoint and graph...")
        save_checkpoint(checkpoint_data)
        try:
            graph.serialize(destination=str(KG_FILE), format="turtle")
            total = len(checkpoint_data['succeeded']) + len(checkpoint_data['failed_retriable']) + len(checkpoint_data['failed_permanent'])
            print(f"  ✅ Checkpoint saved: {total} concepts processed")
            print(f"     - Succeeded: {len(checkpoint_data['succeeded'])}")
            print(f"     - Will retry: {len(checkpoint_data['failed_retriable'])}")
            print(f"     - Permanent failures: {len(checkpoint_data['failed_permanent'])}")
            print(f"  ✅ Graph saved")
            print(f"\n  To resume, run the script again - it will continue from where it left off")
            print(f"  Concepts with network errors will be automatically retried")
        except Exception as e:
            print(f"  ❌ Error saving: {e}")
        return
    
    # Final save
    print()
    print(f"✅ Enriched {enriched_count} concepts with Wikidata Q-IDs")
    if failed_count > 0:
        print(f"⚠️  Failed to find Wikidata matches for {failed_count} words")
    print()
    
    # Save checkpoint and graph
    print("Step 6: Saving final checkpoint and knowledge graph...")
    save_checkpoint(checkpoint_data)
    try:
        graph.serialize(destination=str(KG_FILE), format="turtle")
        total = len(checkpoint_data['succeeded']) + len(checkpoint_data['failed_retriable']) + len(checkpoint_data['failed_permanent'])
        print(f"  ✅ Checkpoint saved: {total} concepts")
        print(f"     - Succeeded: {len(checkpoint_data['succeeded'])}")
        print(f"     - Will retry: {len(checkpoint_data['failed_retriable'])}")
        print(f"     - Permanent failures: {len(checkpoint_data['failed_permanent'])}")
        print(f"  ✅ Graph saved to: {KG_FILE}")
        print(f"  ✅ Total triples: {len(graph)}")
        if checkpoint_data['failed_retriable']:
            print(f"\n  ℹ️  {len(checkpoint_data['failed_retriable'])} concepts had network errors and will be retried on next run")
    except Exception as e:
        print(f"  ❌ Error saving knowledge graph: {e}")
        import traceback
        traceback.print_exc()
    
    # Clean up checkpoint if complete (all succeeded or permanently failed, nothing to retry)
    if not checkpoint_data['failed_retriable']:
        try:
            CHECKPOINT_FILE.unlink()
            print("  ✅ Checkpoint file removed (processing complete, nothing to retry)")
        except:
            pass
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

