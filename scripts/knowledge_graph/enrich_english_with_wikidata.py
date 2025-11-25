#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrich English knowledge graph concepts with Wikidata Q-IDs.

This script:
1. Loads English words from the knowledge graph
2. Uses word text or definition to search Wikidata
3. Links concepts to Wikidata Q-IDs
4. Updates the knowledge graph

Similar to enrich_with_wikidata.py but for English words.
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

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_english.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'
CHECKPOINT_FILE = project_root / 'data' / 'content_db' / 'wikidata_enrichment_english_checkpoint.json'

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
        search_term: Term to search for (e.g., "cat", "good morning")
        language: Language code (default: 'en')
        limit: Maximum number of results (default: 5)
    
    Returns: List of dicts with 'id', 'label', 'description'
    Raises: Exception on network errors (to be caught and categorized as retriable)
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
        # Re-raise network errors so they can be categorized as retriable
        raise
    except Exception as e:
        # Re-raise other errors too
        raise


def get_wikidata_labels(qid, languages=['en']):
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


def find_best_wikidata_match(search_terms, word_text=None):
    """
    Find the best Wikidata match for an English word/phrase.
    
    Args:
        search_terms: List of search terms to try (e.g., ["good morning", "good"])
        word_text: Original word text for validation (optional)
    
    Returns: Wikidata Q-ID if found, None otherwise
    Raises: Exception on network errors (to be caught and categorized as retriable)
    """
    if not search_terms:
        return None
    
    # Try each search term in order
    all_results = []
    for term in search_terms:
        if not term or not term.strip():
            continue
        # search_wikidata will raise on network errors - let it propagate
        results = search_wikidata(term.strip(), language='en', limit=5)
        all_results.extend(results)
        
        # If we got results, try to validate with word_text if provided
        if results and word_text:
            # Check if word_text matches any label
            word_lower = word_text.lower().strip()
            for result in results:
                label_lower = result.get('label', '').lower()
                if word_lower == label_lower:
                    # Exact match - return immediately
                    return result['id']
                # Partial match for phrases (e.g., "good morning" matches "Good Morning")
                if word_lower in label_lower or label_lower in word_lower:
                    return result['id']
    
    if not all_results:
        return None
    
    # Remove duplicates while preserving order
    seen = set()
    unique_results = []
    for result in all_results:
        if result['id'] not in seen:
            seen.add(result['id'])
            unique_results.append(result)
    
    # If we have word_text, prefer exact matches
    if word_text:
        word_lower = word_text.lower().strip()
        for result in unique_results:
            label_lower = result.get('label', '').lower()
            if word_lower == label_lower:
                return result['id']
    
    # Filter out overly generic results
    for result in unique_results:
        description = result.get('description', '').lower()
        label = result.get('label', '').lower()
        
        # Skip if it's too generic
        if description:
            generic_terms = ['language', 'country', 'region', 'group', 'thing', 'person']
            if any(term in description for term in generic_terms) and len(description) < 30:
                continue
        
        # Prefer results with descriptions (more specific)
        if description and len(description) > 15:
            return result['id']
    
    # Fallback to first result
    return unique_results[0]['id'] if unique_results else None


def load_checkpoint():
    """Load checkpoint of processed concepts."""
    if not CHECKPOINT_FILE.exists():
        return {
            'succeeded': set(),
            'failed_retriable': set(),  # Network errors, timeouts - should retry
            'failed_permanent': set()   # No match found - skip
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
    labels = get_wikidata_labels(qid, languages=['en'])
    if 'en' in labels:
        graph.add((concept_uri, RDFS.label, Literal(labels['en'], lang='en')))


def process_single_word(word_info):
    """
    Process a single English word to find and return Wikidata Q-ID.
    This function is designed to be called in parallel.
    
    Returns: dict with 'concept_str', 'qid', 'word_text', 'success', 'error'
    """
    word_text = word_info['word_text']
    concept_str = word_info['concept_str']
    definition = word_info.get('definition', '')
    
    try:
        # Build search terms: use definition if available, otherwise use word
        search_terms = []
        if definition and definition.strip():
            search_terms.append(definition.strip())
        search_terms.append(word_text.strip())
        
        # For multi-word phrases, also try the phrase as-is and individual words
        if ' ' in word_text:
            # Add the full phrase first (most specific)
            search_terms.insert(0, word_text.strip())
            # Also try first word (e.g., "good" from "good morning")
            first_word = word_text.split()[0]
            if first_word not in search_terms:
                search_terms.append(first_word)
        
        # Search Wikidata (will raise on network errors)
        qid = find_best_wikidata_match(search_terms, word_text=word_text)
        
        if qid:
            return {
                'concept_str': concept_str,
                'qid': qid,
                'word_text': word_text,
                'success': True,
                'error': None
            }
        else:
            return {
                'concept_str': concept_str,
                'qid': None,
                'word_text': word_text,
                'success': False,
                'error': 'No Wikidata match found'
            }
    except (URLError, HTTPError, Exception) as e:
        # Network errors will be caught here and categorized as retriable
        error_msg = str(e)
        return {
            'concept_str': concept_str,
            'qid': None,
            'word_text': word_text,
            'success': False,
            'error': error_msg
        }


def main():
    """Main function to enrich English concepts with Wikidata Q-IDs."""
    import sys
    sys.stdout.flush()
    
    print("=" * 80, flush=True)
    print("Enrich English Knowledge Graph with Wikidata Concepts", flush=True)
    print("=" * 80, flush=True)
    print(flush=True)
    
    # Load knowledge graph
    print("Step 1: Loading knowledge graph...", flush=True)
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
    print("Step 2: Loading checkpoint (if exists)...")
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
    
    # Find all English words without Wikidata concepts
    print("Step 3: Finding English words to enrich...")
    words_to_process = []
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        # Get English word text
        word_text = None
        for _, _, text_literal in graph.triples((word_uri, RDFS.label, None)):
            if hasattr(text_literal, 'language') and text_literal.language == 'en':
                word_text = str(text_literal).strip()
                break
        # Also try srs-kg:text
        if not word_text:
            for _, _, text_literal in graph.triples((word_uri, SRS_KG.text, None)):
                if hasattr(text_literal, 'language') and text_literal.language == 'en':
                    word_text = str(text_literal).strip()
                    break
                elif not hasattr(text_literal, 'language'):
                    # Assume English if no language tag
                    word_text = str(text_literal).strip()
                    break
        
        if not word_text:
            continue
        
        # Get definition (if available)
        definition = None
        for _, _, def_literal in graph.triples((word_uri, SRS_KG.definition, None)):
            definition = str(def_literal).strip()
            break
        
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
                'word_text': word_text,
                'definition': definition,
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
    print("Step 4: Enriching concepts with Wikidata Q-IDs...")
    
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
            
            batch_size = 50
            processed_count = 0
            
            for batch_start in range(0, len(words_to_process), batch_size):
                batch = words_to_process[batch_start:batch_start + batch_size]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(words_to_process) + batch_size - 1) // batch_size
                
                print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} words)...", flush=True)
                
                # Process batch in parallel
                results = []
                try:
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        future_to_word = {executor.submit(process_single_word, word): word for word in batch}
                        
                        for future in as_completed(future_to_word):
                            try:
                                result = future.result()
                                results.append(result)
                            except Exception as e:
                                word = future_to_word[future]
                                print(f"    ⚠️  Error processing {word.get('word_text', 'unknown')}: {e}")
                                results.append({
                                    'concept_str': word.get('concept_str', ''),
                                    'qid': None,
                                    'word_text': word.get('word_text', ''),
                                    'success': False,
                                    'error': str(e)
                                })
                    
                    # Sort results to match input order
                    result_map = {r['concept_str']: r for r in results}
                    results = [result_map.get(word['concept_str'], {
                        'concept_str': word['concept_str'],
                        'qid': None,
                        'word_text': word['word_text'],
                        'success': False,
                        'error': 'Result not found'
                    }) for word in batch]
                except Exception as e:
                    print(f"    ⚠️  Error in parallel processing: {e}")
                    results = [process_single_word(word) for word in batch]
                
                # Process results and update graph
                for result in results:
                    processed_count += 1
                    concept_str = result['concept_str']
                    word_text = result['word_text']
                    
                    if result['success'] and result['qid']:
                        # Find the concept URI and enrich it
                        for word_info in words_to_process:
                            if word_info['concept_str'] == concept_str:
                                enrich_concept_with_wikidata(graph, word_info['concept_uri'], result['qid'])
                                enriched_count += 1
                                print(f"    ✅ Linked {word_text} → {result['qid']}")
                                break
                        # Mark as succeeded
                        checkpoint_data['failed_retriable'].discard(concept_str)
                        checkpoint_data['failed_permanent'].discard(concept_str)
                        checkpoint_data['succeeded'].add(concept_str)
                    else:
                        failed_count += 1
                        error_msg = result.get('error', 'Unknown error')
                        if result['error']:
                            print(f"    ⚠️  {word_text}: {error_msg}")
                        
                        # Categorize failure
                        if is_retriable_error(error_msg):
                            checkpoint_data['succeeded'].discard(concept_str)
                            checkpoint_data['failed_permanent'].discard(concept_str)
                            checkpoint_data['failed_retriable'].add(concept_str)
                        else:
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
            # Single-threaded processing
            for idx, word_info in enumerate(words_to_process, 1):
                word_text = word_info['word_text']
                concept_uri = word_info['concept_uri']
                concept_str = word_info['concept_str']
                definition = word_info.get('definition', '')
                
                # Show progress
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = len(words_to_process) - idx
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_minutes = eta_seconds / 60
                
                if idx % 10 == 0 or idx == 1:
                    print(f"  [{idx}/{len(words_to_process)}] {word_text} | "
                          f"Rate: {rate:.1f}/min | "
                          f"ETA: {eta_minutes:.1f}min | "
                          f"✅ {enriched_count} | ❌ {failed_count}")
                elif idx % 5 == 0:
                    print(f"  [{idx}/{len(words_to_process)}] Processing... ({rate:.1f}/min, {eta_minutes:.1f}min remaining)")
                
                # Build search terms
                search_terms = []
                if definition and definition.strip():
                    search_terms.append(definition.strip())
                search_terms.append(word_text.strip())
                
                # For multi-word phrases, also try the phrase as-is
                if ' ' in word_text:
                    search_terms.insert(0, word_text.strip())
                
                # Search Wikidata
                try:
                    qid = find_best_wikidata_match(search_terms, word_text=word_text)
                    error_msg = None
                except Exception as e:
                    qid = None
                    error_msg = str(e)
                
                if qid:
                    enrich_concept_with_wikidata(graph, concept_uri, qid)
                    enriched_count += 1
                    print(f"    ✅ Linked {word_text} → {qid}")
                    checkpoint_data['failed_retriable'].discard(concept_str)
                    checkpoint_data['failed_permanent'].discard(concept_str)
                    checkpoint_data['succeeded'].add(concept_str)
                else:
                    failed_count += 1
                    if error_msg:
                        print(f"    ⚠️  {word_text}: {error_msg}")
                    else:
                        print(f"    ⚠️  No Wikidata match for {word_text}")
                    
                    # Categorize failure
                    final_error = error_msg or f"No Wikidata match for {word_text}"
                    if is_retriable_error(final_error):
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
                    try:
                        graph.serialize(destination=str(KG_FILE), format="turtle")
                        last_save_time = current_time
                        print(f"    💾 Checkpoint saved ({idx} words processed)")
                    except Exception as e:
                        print(f"    ⚠️  Could not save graph: {e}")
                
                # Rate limiting
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
    print("Step 5: Saving final checkpoint and knowledge graph...")
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
    
    # Clean up checkpoint if complete
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

