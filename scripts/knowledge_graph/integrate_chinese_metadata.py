#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrate Chinese word metadata from multiple sources into the Knowledge Graph.

This script integrates:
1. SUBTLEX-CH: Word frequency data (for frequencyRank)
2. MELD-SCH: Concreteness ratings (for concreteness)
3. CCLOOW: Age of Acquisition data (for ageOfAcquisition)

Usage:
    # Integrate all datasets
    python integrate_chinese_metadata.py --sublex-file path/to/SUBTLEX-CH.txt --meld-file path/to/MELD-SCH.csv --ccloow-file path/to/CCLOOW.csv
    
    # Integrate only specific datasets
    python integrate_chinese_metadata.py --sublex-file path/to/SUBTLEX-CH.txt
    python integrate_chinese_metadata.py --meld-file path/to/MELD-SCH.csv
    python integrate_chinese_metadata.py --ccloow-file path/to/CCLOOW.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, Set, Optional

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, XSD
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

KG_FILE = project_root / "knowledge_graph" / "world_model_cwn.ttl"
ONTOLOGY_FILE = project_root / "knowledge_graph" / "ontology" / "srs_schema.ttl"

SRS_KG = Namespace("http://srs4autism.com/schema/")


def normalize_chinese_word(word: str) -> str:
    """Normalize Chinese word for matching (remove spaces, punctuation)."""
    if not word:
        return ""
    # Remove spaces, punctuation, keep only Chinese characters
    word = re.sub(r'[^\u4e00-\u9fff]', '', word)
    return word.strip()


def load_sublex_ch(sublex_file: Path) -> Dict[str, Dict[str, float]]:
    """
    Load SUBTLEX-CH frequency data.
    
    Expected format: Tab-separated with columns: Word, WCount, W/million, logW, W-CD, W-CD%, logW-CD
    Returns: Dict mapping word -> {'frequency': float, 'rank': int}
    """
    sublex_map = {}
    
    if not sublex_file or not sublex_file.exists():
        print(f"⚠️  SUBTLEX-CH file not found: {sublex_file}")
        return sublex_map
    
    print(f"📊 Loading SUBTLEX-CH frequency data from: {sublex_file}")
    
    try:
        # SUBTLEX-CH-WF is typically GB2312/GBK encoded
        encodings = ['gb2312', 'gbk', 'gb18030', 'utf-8', 'iso-8859-1']
        file_handle = None
        encoding_used = None
        
        for enc in encodings:
            try:
                file_handle = sublex_file.open('r', encoding=enc, errors='replace')
                # Try to read first few lines to verify encoding
                first_lines = []
                for _ in range(5):
                    line = file_handle.readline()
                    if line:
                        first_lines.append(line)
                file_handle.seek(0)
                # Check if we can decode Chinese characters properly
                if any('\u4e00' <= char <= '\u9fff' for line in first_lines for char in line):
                    encoding_used = enc
                    break
                file_handle.close()
                file_handle = None
            except Exception:
                if file_handle:
                    file_handle.close()
                    file_handle = None
                continue
        
        if not file_handle:
            # Fallback to utf-8 with errors='ignore'
            file_handle = sublex_file.open('r', encoding='utf-8', errors='ignore')
            encoding_used = 'utf-8 (with errors ignored)'
        
        print(f"   Using encoding: {encoding_used}")
        
        # Skip metadata lines (lines that start with quotes or are empty)
        line = file_handle.readline()
        while line and (line.strip().startswith('"') or not line.strip() or 
                       'Total word count' in line or 'Context number' in line):
            line = file_handle.readline()
        
        # Parse header line
        header = line.strip().split('\t')
        if len(header) < 2:
            # Try comma-separated
            header = line.strip().split(',')
        
        # Find column indices
        word_col = None
        freq_col = None
        
        for i, col in enumerate(header):
            col_lower = col.lower().strip()
            if col_lower in ('word', '词', '词语'):
                word_col = i
            elif col_lower in ('wcount', 'count', 'freq', 'frequency', '频次', '频率'):
                freq_col = i
        
        if word_col is None:
            # Assume first column is word
            word_col = 0
        if freq_col is None:
            # Assume second column is frequency (WCount)
            freq_col = 1
        
        print(f"   Word column: {word_col}, Frequency column: {freq_col}")
        
        # Read data
        delimiter = '\t' if '\t' in line else ','
        rank = 1
        lines_processed = 0
        
        for line_num, line in enumerate(file_handle, start=1):
            line = line.strip()
            if not line or line.startswith('"'):
                continue
            
            # Skip lines that look like metadata
            if 'Total' in line or 'Context' in line:
                continue
            
            parts = line.split(delimiter)
            if len(parts) < 2:
                continue
            
            word = parts[word_col].strip() if word_col < len(parts) else ''
            if not word:
                continue
            
            # Skip if word doesn't contain Chinese characters
            if not any('\u4e00' <= char <= '\u9fff' for char in word):
                continue
            
            word_normalized = normalize_chinese_word(word)
            if not word_normalized:
                continue
            
            # Get frequency (WCount column)
            if freq_col < len(parts):
                freq_str = parts[freq_col].strip()
            else:
                continue
            
            if freq_str:
                try:
                    # Remove thousand separators and convert
                    freq_str = freq_str.replace(',', '').replace(' ', '')
                    frequency = float(freq_str)
                    sublex_map[word_normalized] = {
                        'frequency': frequency,
                        'rank': rank
                    }
                    rank += 1
                    lines_processed += 1
                except (ValueError, TypeError):
                    continue
        
        file_handle.close()
        print(f"   Processed {lines_processed} data lines")
        
        print(f"✅ Loaded {len(sublex_map)} frequency entries from SUBTLEX-CH")
        return sublex_map
    
    except Exception as e:
        print(f"❌ Error loading SUBTLEX-CH: {e}")
        import traceback
        traceback.print_exc()
        return sublex_map


def load_meld_sch(meld_file: Path) -> Dict[str, float]:
    """
    Load MELD-SCH concreteness data.
    
    Expected format: Word, Concreteness (or similar)
    Returns: Dict mapping word -> concreteness value (float)
    """
    meld_map = {}
    
    if not meld_file or not meld_file.exists():
        print(f"⚠️  MELD-SCH file not found: {meld_file}")
        return meld_map
    
    print(f"📊 Loading MELD-SCH concreteness data from: {meld_file}")
    
    try:
        with meld_file.open('r', encoding='utf-8') as f:
            # Try to detect delimiter
            first_line = f.readline()
            f.seek(0)
            
            delimiter = '\t' if '\t' in first_line else ','
            reader = csv.DictReader(f, delimiter=delimiter)
            
            for row in reader:
                word = row.get('Word', '').strip() or row.get('word', '').strip()
                if not word:
                    continue
                
                word_normalized = normalize_chinese_word(word)
                if not word_normalized:
                    continue
                
                # Try different concreteness column names
                conc_str = (row.get('Concreteness', '') or row.get('concreteness', '') or
                           row.get('Conc', '') or row.get('conc', '') or
                           row.get('Rating', '') or row.get('rating', '')).strip()
                
                if conc_str:
                    try:
                        concreteness = float(conc_str)
                        # MELD-SCH typically uses 1-7 scale, normalize to 1-5 if needed
                        if concreteness > 5:
                            concreteness = 1 + (concreteness - 1) * 4 / 6  # Map 1-7 to 1-5
                        meld_map[word_normalized] = concreteness
                    except (ValueError, TypeError):
                        continue
        
        print(f"✅ Loaded {len(meld_map)} concreteness entries from MELD-SCH")
        return meld_map
    
    except Exception as e:
        print(f"❌ Error loading MELD-SCH: {e}")
        return meld_map


def load_ccloow(ccloow_file: Path) -> Dict[str, float]:
    """
    Load CCLOOW (Chinese Children's Lexicon of Oral Words) AoA data.
    
    Expected format: Word, AoA (or similar)
    Returns: Dict mapping word -> AoA value (float, in years)
    """
    ccloow_map = {}
    
    if not ccloow_file or not ccloow_file.exists():
        print(f"⚠️  CCLOOW file not found: {ccloow_file}")
        return ccloow_map
    
    print(f"📊 Loading CCLOOW AoA data from: {ccloow_file}")
    
    try:
        with ccloow_file.open('r', encoding='utf-8') as f:
            # Try to detect delimiter
            first_line = f.readline()
            f.seek(0)
            
            delimiter = '\t' if '\t' in first_line else ','
            reader = csv.DictReader(f, delimiter=delimiter)
            
            for row in reader:
                word = row.get('Word', '').strip() or row.get('word', '').strip()
                if not word:
                    continue
                
                word_normalized = normalize_chinese_word(word)
                if not word_normalized:
                    continue
                
                # Try different AoA column names
                aoa_str = (row.get('AoA', '') or row.get('aoa', '') or
                          row.get('Age', '') or row.get('age', '') or
                          row.get('AgeOfAcquisition', '')).strip()
                
                if aoa_str:
                    try:
                        aoa = float(aoa_str)
                        ccloow_map[word_normalized] = aoa
                    except (ValueError, TypeError):
                        continue
        
        print(f"✅ Loaded {len(ccloow_map)} AoA entries from CCLOOW")
        return ccloow_map
    
    except Exception as e:
        print(f"❌ Error loading CCLOOW: {e}")
        return ccloow_map


def update_words_with_metadata(
    graph: Graph,
    sublex_map: Optional[Dict[str, Dict[str, float]]] = None,
    meld_map: Optional[Dict[str, float]] = None,
    ccloow_map: Optional[Dict[str, float]] = None,
    skip_existing: bool = False
) -> Dict[str, int]:
    """
    Update Chinese words in graph with metadata.
    
    Returns:
        Dict with counts: {'updated_freq': int, 'updated_conc': int, 'updated_aoa': int, 'not_found': int}
    """
    stats = {
        'updated_freq': 0,
        'updated_conc': 0,
        'updated_aoa': 0,
        'not_found': 0
    }
    
    # Find all Chinese words in the graph
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    
    print("\n🔍 Finding Chinese words in knowledge graph...")
    words_processed = 0
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        
        # Get labels
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        chinese_label = None
        
        for label in labels:
            label_str = str(label)
            # Check if it contains Chinese characters
            if chinese_char_pattern.search(label_str):
                chinese_label = label_str
                break
        
        if not chinese_label:
            continue  # Not a Chinese word
        
        word_normalized = normalize_chinese_word(chinese_label)
        if not word_normalized:
            continue
        
        words_processed += 1
        updated = False
        
        # Update frequency from SUBTLEX-CH
        if sublex_map and word_normalized in sublex_map:
            freq_data = sublex_map[word_normalized]
            
            # Check if frequency already exists
            existing_freq = list(graph.objects(word_uri_ref, SRS_KG.frequencyRank))
            if existing_freq and skip_existing:
                pass  # Skip
            else:
                # Add frequency rank
                graph.set((word_uri_ref, SRS_KG.frequencyRank,
                          Literal(int(freq_data['rank']), datatype=XSD.integer)))
                # Optionally add raw frequency
                if 'frequency' in freq_data:
                    graph.set((word_uri_ref, SRS_KG.frequency,
                              Literal(float(freq_data['frequency']), datatype=XSD.float)))
                stats['updated_freq'] += 1
                updated = True
        
        # Update concreteness from MELD-SCH
        if meld_map and word_normalized in meld_map:
            conc_value = meld_map[word_normalized]
            
            # Check if concreteness already exists
            existing_conc = list(graph.objects(word_uri_ref, SRS_KG.concreteness))
            if existing_conc and skip_existing:
                pass  # Skip
            else:
                graph.set((word_uri_ref, SRS_KG.concreteness,
                          Literal(float(conc_value), datatype=XSD.float)))
                stats['updated_conc'] += 1
                updated = True
        
        # Update AoA from CCLOOW
        if ccloow_map and word_normalized in ccloow_map:
            aoa_value = ccloow_map[word_normalized]
            
            # Check if AoA already exists
            existing_aoa = list(graph.objects(word_uri_ref, SRS_KG.ageOfAcquisition))
            if existing_aoa and skip_existing:
                pass  # Skip
            else:
                graph.set((word_uri_ref, SRS_KG.ageOfAcquisition,
                          Literal(float(aoa_value), datatype=XSD.float)))
                stats['updated_aoa'] += 1
                updated = True
        
        if not updated and (sublex_map or meld_map or ccloow_map):
            stats['not_found'] += 1
        
        if words_processed % 1000 == 0:
            print(f"   Processed {words_processed} words...")
    
    print(f"✅ Processed {words_processed} Chinese words")
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Integrate Chinese word metadata (SUBTLEX-CH, MELD-SCH, CCLOOW) into Knowledge Graph'
    )
    parser.add_argument(
        '--sublex-file',
        type=Path,
        default=None,
        help='Path to SUBTLEX-CH file (frequency data)'
    )
    parser.add_argument(
        '--meld-file',
        type=Path,
        default=None,
        help='Path to MELD-SCH file (concreteness data)'
    )
    parser.add_argument(
        '--ccloow-file',
        type=Path,
        default=None,
        help='Path to CCLOOW file (AoA data)'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge with existing KG file (world_model_merged.ttl)'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip words that already have metadata values'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Output KG file path (default: same as input)'
    )
    
    args = parser.parse_args()
    
    if not args.sublex_file and not args.meld_file and not args.ccloow_file:
        parser.error("At least one data file must be provided (--sublex-file, --meld-file, or --ccloow-file)")
    
    print("=" * 80)
    print("Chinese Word Metadata Integration")
    print("=" * 80)
    print()
    
    # Load data files
    sublex_map = load_sublex_ch(args.sublex_file) if args.sublex_file else None
    meld_map = load_meld_sch(args.meld_file) if args.meld_file else None
    ccloow_map = load_ccloow(args.ccloow_file) if args.ccloow_file else None
    
    if not sublex_map and not meld_map and not ccloow_map:
        print("❌ No data loaded. Exiting.")
        sys.exit(1)
    
    print()
    
    # Load existing knowledge graph
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    kg_file_to_use = KG_FILE
    if args.merge:
        kg_file_to_use = project_root / 'knowledge_graph' / 'world_model_merged.ttl'
    
    if kg_file_to_use.exists():
        print(f"📚 Loading existing knowledge graph from: {kg_file_to_use}")
        try:
            graph.parse(str(kg_file_to_use), format="turtle")
            print(f"✅ Loaded existing graph with {len(graph)} triples")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse KG file: {e}")
            print("   Starting with empty graph...")
    else:
        print(f"⚠️  Knowledge graph file not found: {kg_file_to_use}")
        print("   Starting with empty graph...")
    
    print()
    
    # Load ontology schema
    if ONTOLOGY_FILE.exists():
        try:
            graph.parse(str(ONTOLOGY_FILE), format="turtle")
            print("✅ Ontology schema loaded")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse schema: {e}")
    print()
    
    # Update words with metadata
    print("🔄 Updating words with metadata...")
    stats = update_words_with_metadata(
        graph,
        sublex_map=sublex_map,
        meld_map=meld_map,
        ccloow_map=ccloow_map,
        skip_existing=args.skip_existing
    )
    
    print()
    print("=" * 80)
    print("Integration Statistics:")
    print("=" * 80)
    if sublex_map:
        print(f"📊 Frequency (SUBTLEX-CH): {stats['updated_freq']} words updated")
    if meld_map:
        print(f"🎯 Concreteness (MELD-SCH): {stats['updated_conc']} words updated")
    if ccloow_map:
        print(f"🧠 AoA (CCLOOW): {stats['updated_aoa']} words updated")
    print(f"❌ Words not found in datasets: {stats['not_found']}")
    print()
    
    # Save updated graph
    output_file = args.output or kg_file_to_use
    
    # Backup existing file
    if output_file.exists():
        try:
            from scripts.knowledge_graph.kg_backup import backup_kg_file
            backup_kg_file(output_file, create_timestamped=True)
        except ImportError:
            print("⚠️  Warning: Could not import backup utility, skipping backup")
    
    print(f"💾 Saving updated knowledge graph to: {output_file}")
    try:
        graph.serialize(destination=str(output_file), format="turtle")
        print(f"✅ Saved {len(graph)} triples to {output_file}")
    except Exception as e:
        print(f"❌ Error saving graph: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("✅ Chinese Metadata Integration Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

