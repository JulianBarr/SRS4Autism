#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
English Vocabulary Recommender Experiment

This script implements a small experiment for the "Integrated Approach" recommender system
described in "An integrated approach for recommender system of language learning.md".

It uses spreading activation on a heterogeneous graph built from:
1. Anki data (mastery scores from _KG_Map)
2. Knowledge Graph (Word -> Concept relationships)
3. Semantic similarity (spaCy) for word-to-word connections
4. Anki tags for topic clustering

Since we don't have word family relationships in the KG, we use:
- Concept nodes as hubs (words sharing concepts are related)
- Semantic similarity edges (spaCy word embeddings)
- Tag-based clustering
"""

import os
import sys
import json
import math
import sqlite3
import zipfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field

# Add project root
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import networkx as nx
    import requests
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, RDFS
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Install with: pip install networkx rdflib requests")
    sys.exit(1)

# Try to import spaCy (optional - will use simpler similarity if not available)
try:
    import spacy
    SPACY_AVAILABLE = True
    print("✅ spaCy available - will use semantic similarity")
except ImportError:
    SPACY_AVAILABLE = False
    print("⚠️  spaCy not available - will skip semantic similarity edges")
    print("   Install with: python -m spacy download en_core_web_md")

from anki_integration.anki_connect import AnkiConnect

# Configuration
KG_FILE = project_root / "knowledge_graph" / "world_model_english.ttl"
ANKI_URL = "http://localhost:8765"
DECK_NAME = "YM::YM_ENG::Vocab"
NOTE_TYPE = "CUMA - Basic (and reversed card)"
DATA_DIR = project_root / "data" / "content_db"
PROFILES_FILE = project_root / "data" / "profiles" / "child_profiles.json"

# Anki package files
ANKI_PACKAGES = [
    DATA_DIR / "English__Vocabulary__1. Basic.apkg",
    DATA_DIR / "English__Vocabulary__2. Level 2.apkg",
]

SRS_KG = Namespace("http://srs4autism.com/schema/")

# Spreading activation parameters
DECAY_FACTOR = 0.5  # Energy decays by 50% per hop
SIMILARITY_THRESHOLD = 0.7  # Minimum similarity for semantic edges
MAX_ITERATIONS = 3  # Number of propagation steps


@dataclass
class WordNode:
    """Represents a word in the graph."""
    word_id: str
    word_text: str
    concept_id: Optional[str] = None
    cefr_level: Optional[str] = None
    concreteness: Optional[float] = None
    frequency: Optional[float] = None  # Zipf scale or similar
    tags: List[str] = field(default_factory=list)
    resistance: float = 5.0  # Default resistance (hard to learn)


@dataclass
class Recommendation:
    """A recommended word with scores."""
    word_id: str
    word_text: str
    activation: float
    resistance: float
    score: float
    reason: str = ""  # Why it was recommended


class EnglishRecommenderExperiment:
    """Main experiment class."""
    
    def __init__(self):
        self.anki = AnkiConnect(ANKI_URL)
        self.kg_graph = None
        self.nx_graph = nx.Graph()
        self.word_nodes: Dict[str, WordNode] = {}
        self.concept_to_words: Dict[str, Set[str]] = defaultdict(set)
        self.mastery_scores: Dict[str, float] = {}
        self.words_in_deck: Set[str] = set()  # Words to exclude (from all notes in deck)
        self.words_in_deck_text: Set[str] = set()  # Word texts found in deck
        self.nlp = None
        
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_md")
                print("✅ Loaded spaCy model")
            except OSError:
                print("⚠️  spaCy model not found. Run: python -m spacy download en_core_web_md")
                self.nlp = None
    
    def load_knowledge_graph(self):
        """Load the English knowledge graph from Turtle file."""
        print("\n📚 Loading knowledge graph...")
        self.kg_graph = Graph()
        self.kg_graph.bind("srs-kg", SRS_KG)
        
        if not KG_FILE.exists():
            print(f"❌ KG file not found: {KG_FILE}")
            return False
        
        try:
            self.kg_graph.parse(str(KG_FILE), format="turtle")
            print(f"✅ Loaded {len(self.kg_graph)} triples")
            return True
        except Exception as e:
            print(f"❌ Error loading KG: {e}")
            return False
    
    def extract_words_from_apkg(self, apkg_path: Path) -> Set[str]:
        """Extract English words from Anki package file."""
        words = set()
        
        if not apkg_path.exists():
            print(f"  ⚠️  Package not found: {apkg_path.name}")
            return words
        
        temp_dir = project_root / 'temp_anki_extract' / apkg_path.stem
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract package
            with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find database file
            db_files = [
                temp_dir / 'collection.anki21',
                temp_dir / 'collection.anki2',
            ]
            
            db_path = None
            for db_file in db_files:
                if db_file.exists():
                    db_path = db_file
                    break
            
            if not db_path:
                print(f"  ⚠️  No database file found in {apkg_path.name}")
                return words
            
            # Read database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get models
            cursor.execute("SELECT models FROM col LIMIT 1")
            row = cursor.fetchone()
            if not row or not row[0]:
                conn.close()
                return words
            
            models_json = json.loads(row[0])
            model_fields = {}
            
            for model_id_str, model_data in models_json.items():
                fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
                model_fields[int(model_id_str)] = fields
            
            # Get notes
            cursor.execute("SELECT mid, flds FROM notes")
            notes = cursor.fetchall()
            
            for mid, flds_str in notes:
                if not flds_str:
                    continue
                
                fields = model_fields.get(mid, [])
                flds = flds_str.split('\x1f')
                
                # Extract words from all fields
                for field_value in flds:
                    if not field_value:
                        continue
                    
                    # Remove HTML tags
                    text = re.sub(r'<[^>]+>', '', field_value)
                    # Remove image tags
                    text = re.sub(r'<img[^>]*>', '', text)
                    
                    # Extract English words (sequences of letters)
                    english_words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
                    
                    for word in english_words:
                        normalized = word.lower().strip()
                        if normalized and len(normalized) >= 2:
                            words.add(normalized)
            
            conn.close()
            
        except Exception as e:
            print(f"  ❌ Error processing {apkg_path.name}: {e}")
        
        return words
    
    def load_mastered_words_from_profile(self) -> Set[str]:
        """Load mastered English words from profile JSON."""
        words = set()
        
        if not PROFILES_FILE.exists():
            print(f"  ⚠️  Profile file not found: {PROFILES_FILE}")
            return words
        
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
            
            # Get first profile (or find specific one)
            if isinstance(profiles, list) and profiles:
                profile = profiles[0]
            elif isinstance(profiles, dict):
                profile = profiles
            else:
                return words
            
            mastered_str = profile.get('mastered_english_words', '')
            if mastered_str:
                # Split comma-separated words
                for word in mastered_str.split(','):
                    normalized = word.strip().lower()
                    if normalized:
                        words.add(normalized)
        
        except Exception as e:
            print(f"  ❌ Error loading profile: {e}")
        
        return words
    
    def load_anki_data(self):
        """Load words from .apkg files and profile, and mastery scores from Anki."""
        print("\n📝 Loading words to exclude...")
        
        # Extract words from .apkg files
        all_words = set()
        for apkg_path in ANKI_PACKAGES:
            print(f"  Extracting from {apkg_path.name}...")
            words = self.extract_words_from_apkg(apkg_path)
            all_words.update(words)
            print(f"    Found {len(words)} words")
        
        # Also load from profile
        print(f"  Loading from profile...")
        profile_words = self.load_mastered_words_from_profile()
        all_words.update(profile_words)
        print(f"    Found {len(profile_words)} words in profile")
        
        print(f"  Total unique words to exclude: {len(all_words)}")
        self.words_in_deck_text = all_words
        
        # Now get mastery scores from Anki (if available)
        if not self.anki.ping():
            print("⚠️  AnkiConnect not available - skipping mastery scores")
            return True
        
        # Get notes with _KG_Map for mastery scores
        query = '_KG_Map:*'
        kg_map_note_ids = self.anki._invoke("findNotes", {"query": query})
        
        if not kg_map_note_ids:
            query = '_KG_Map:'
            kg_map_note_ids = self.anki._invoke("findNotes", {"query": query})
        
        if not kg_map_note_ids:
            print("⚠️  No notes with _KG_Map found")
            return True
        
        print(f"Found {len(kg_map_note_ids)} notes with _KG_Map")
        
        # Get note info in chunks
        kg_map_notes_info = []
        chunk_size = 250
        for i in range(0, len(kg_map_note_ids), chunk_size):
            chunk = kg_map_note_ids[i:i+chunk_size]
            data = self.anki._invoke("notesInfo", {"notes": chunk})
            if data:
                kg_map_notes_info.extend(data)
        
        # Get card info for mastery calculation
        card_ids = []
        for note in kg_map_notes_info:
            card_ids.extend(note.get("cards", []))
        
        cards_map = {}
        if card_ids:
            for i in range(0, len(card_ids), chunk_size):
                chunk = card_ids[i:i+chunk_size]
                data = self.anki._invoke("cardsInfo", {"cards": chunk})
                if data:
                    for card in data:
                        cards_map[card.get("cardId")] = card
        
        # Process notes with _KG_Map for mastery scores
        word_to_mastery: Dict[str, List[float]] = defaultdict(list)
        processed_count = 0
        skipped_no_word = 0
        skipped_no_kg_map = 0
        skipped_no_word_id = 0
        skipped_no_cards = 0
        
        for note in kg_map_notes_info:
            # For now, accept all notes with _KG_Map (we can filter later)
            note_deck = note.get("deckName", "")
            note_type = note.get("modelName", "")
            # Extract word from Back field
            back_field = note.get("fields", {}).get("Back", {}).get("value", "")
            word_text = self._extract_word(back_field)
            if not word_text:
                skipped_no_word += 1
                continue
            
            # Get tags
            tags = note.get("tags", [])
            
            # Parse _KG_Map
            kg_map_field = note.get("fields", {}).get("_KG_Map", {})
            kg_map_str = kg_map_field.get("value", "") if isinstance(kg_map_field, dict) else str(kg_map_field)
            
            if not kg_map_str:
                skipped_no_kg_map += 1
                continue
            
            try:
                kg_map = json.loads(kg_map_str)
            except json.JSONDecodeError as e:
                skipped_no_kg_map += 1
                continue
            
            # Extract word_id and concept_id from kg_map
            word_id = None
            concept_id = None
            
            for entry in kg_map:
                if not isinstance(entry, dict):
                    continue
                
                kg_link = entry.get("kg_link", {})
                if isinstance(kg_link, dict):
                    source = kg_link.get("source", "")
                    target = kg_link.get("target", "")
                    relation = kg_link.get("relation", "")
                    
                    if relation == "concept_to_word":
                        concept_id = source
                        word_id = target
                    elif relation == "word_to_concept":
                        word_id = source
                        concept_id = target
            
            if not word_id:
                skipped_no_word_id += 1
                continue
            
            # Calculate mastery from card states
            note_card_ids = note.get("cards", [])
            mastery_scores = []
            
            for card_id in note_card_ids:
                card = cards_map.get(card_id)
                if not card:
                    continue
                
                # Simple mastery heuristic: based on interval and lapses
                interval = card.get("interval", 0)  # in seconds
                interval_days = interval / 86400.0
                lapses = card.get("lapses", 0)
                reps = card.get("reps", 0)
                
                # Normalize interval (0-1 scale, assuming 120 days = mastered)
                normalized_interval = min(1.0, math.log(interval_days + 1) / math.log(121))
                
                # Penalty for lapses
                lapse_penalty = min(0.3, lapses * 0.1)
                
                mastery = max(0.0, normalized_interval - lapse_penalty)
                mastery_scores.append(mastery)
            
            if mastery_scores:
                avg_mastery = sum(mastery_scores) / len(mastery_scores)
                word_to_mastery[word_id].append(avg_mastery)
                processed_count += 1
                
                # Store word info
                if word_id not in self.word_nodes:
                    self.word_nodes[word_id] = WordNode(
                        word_id=word_id,
                        word_text=word_text,
                        concept_id=concept_id,
                        tags=tags
                    )
                
                # Update concept mapping
                if concept_id:
                    self.concept_to_words[concept_id].add(word_id)
            else:
                skipped_no_cards += 1
        
        # Average mastery scores
        for word_id, scores in word_to_mastery.items():
            self.mastery_scores[word_id] = sum(scores) / len(scores)
        
        print(f"✅ Processed {processed_count} notes with mastery data")
        print(f"   Skipped: {skipped_no_word} (no word), {skipped_no_kg_map} (no _KG_Map), {skipped_no_word_id} (no word_id), {skipped_no_cards} (no cards)")
        print(f"✅ Loaded {len(self.mastery_scores)} words with mastery scores")
        print(f"✅ Found {len(self.words_in_deck_text)} word texts in deck (will match to KG after enrichment)")
        return True
    
    def _extract_word(self, back_field: str) -> Optional[str]:
        """Extract the main word from the Back field."""
        if not back_field:
            return None
        
        # Try to find word in various formats
        # Look for patterns like "word" or **word** or [word]
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', back_field)
        
        # Try to find word in bold or brackets
        match = re.search(r'\*\*([^*]+)\*\*|\[([^\]]+)\]|"([^"]+)"', text)
        if match:
            return match.group(1) or match.group(2) or match.group(3)
        
        # Fallback: first word
        words = text.split()
        if words:
            return words[0].strip('.,!?;:')
        
        return None
    
    def enrich_word_attributes(self):
        """Enrich word nodes with CEFR level, concreteness, frequency from KG."""
        print("\n🔍 Enriching word attributes from KG...")
        
        if not self.kg_graph:
            return
        
        enriched = 0
        for word_uri, _, _ in self.kg_graph.triples((None, RDF.type, SRS_KG.Word)):
            word_id = str(word_uri).split("/")[-1]
            
            if word_id not in self.word_nodes:
                # Get word text
                word_text = None
                for _, _, label in self.kg_graph.triples((word_uri, RDFS.label, None)):
                    if getattr(label, "language", None) == "en":
                        word_text = str(label).strip()
                        break
                
                if not word_text:
                    continue
                
                self.word_nodes[word_id] = WordNode(
                    word_id=word_id,
                    word_text=word_text
                )
            
            node = self.word_nodes[word_id]
            
            # Get CEFR level
            for _, _, level in self.kg_graph.triples((word_uri, SRS_KG.cefrLevel, None)):
                node.cefr_level = str(level)
                break
            
            # Get concreteness
            for _, _, conc in self.kg_graph.triples((word_uri, SRS_KG.concreteness, None)):
                try:
                    node.concreteness = float(conc)
                except (ValueError, TypeError):
                    pass
                break
            
            # Get concept
            for _, _, concept in self.kg_graph.triples((word_uri, SRS_KG.means, None)):
                concept_id = str(concept).split("/")[-1]
                node.concept_id = concept_id
                self.concept_to_words[concept_id].add(word_id)
                break
            
            enriched += 1
        
        # Now match words from deck to KG word_ids
        words_in_deck = set()
        words_in_deck_text = getattr(self, 'words_in_deck_text', set())
        
        if words_in_deck_text:
            # Build word text to word_id mapping
            word_text_to_ids: Dict[str, List[str]] = defaultdict(list)
            for word_id, node in self.word_nodes.items():
                if node.word_text:
                    normalized = node.word_text.lower().strip()
                    word_text_to_ids[normalized].append(word_id)
            
            # Match deck words to KG word_ids
            for word_text in words_in_deck_text:
                normalized = word_text.lower().strip()
                if normalized in word_text_to_ids:
                    for word_id in word_text_to_ids[normalized]:
                        words_in_deck.add(word_id)
            
            print(f"   Matched {len(words_in_deck)} word_ids from deck words to KG")
            self.words_in_deck = words_in_deck
        
        print(f"✅ Enriched {enriched} words")
    
    def calculate_resistance(self, node: WordNode) -> float:
        """Calculate resistance score (higher = harder to learn)."""
        # Formula: R = w1 * (1/Freq) + w2 * (5 - Concreteness) + w3 * Level
        
        freq_term = 0.0
        if node.frequency:
            # Higher frequency = lower resistance
            freq_term = 10.0 / (node.frequency + 0.1)
        else:
            freq_term = 3.0  # Default mid-frequency
        
        conc_term = 0.0
        if node.concreteness:
            # Higher concreteness = lower resistance
            conc_term = 5.0 - node.concreteness
        else:
            conc_term = 2.5  # Default neutral
        
        level_term = 0.0
        if node.cefr_level:
            # A1=1, A2=2, B1=3, B2=4, C1=5, C2=6
            level_map = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
            level_term = level_map.get(node.cefr_level.upper(), 3)
        else:
            level_term = 3.0  # Default intermediate
        
        # Weighted sum
        resistance = 0.4 * freq_term + 0.4 * conc_term + 0.2 * level_term
        return resistance
    
    def build_graph(self):
        """Build the NetworkX graph with nodes and edges."""
        print("\n🕸️  Building graph...")
        
        # Add word nodes
        for word_id, node in self.word_nodes.items():
            node.resistance = self.calculate_resistance(node)
            self.nx_graph.add_node(word_id, **{
                "word_text": node.word_text,
                "resistance": node.resistance,
                "concept_id": node.concept_id
            })
        
        # Add concept hub nodes
        concept_nodes = set()
        concept_hub_count = 0
        for concept_id, word_ids in self.concept_to_words.items():
            # Filter to only words that are actually in the graph
            words_in_graph = [w for w in word_ids if w in self.nx_graph]
            if len(words_in_graph) > 1:  # Only create hub if multiple words share concept
                concept_node = f"CONCEPT:{concept_id}"
                concept_nodes.add(concept_node)
                self.nx_graph.add_node(concept_node, node_type="concept")
                concept_hub_count += 1
                
                # Connect words to concept hub
                for word_id in words_in_graph:
                    self.nx_graph.add_edge(word_id, concept_node, weight=0.8, type="concept_hub")
        
        print(f"  Created {concept_hub_count} concept hubs")
        
        # Add tag-based edges (words with shared tags)
        tag_to_words: Dict[str, Set[str]] = defaultdict(set)
        for word_id, node in self.word_nodes.items():
            for tag in node.tags:
                if tag and not tag.startswith("zhou-yiming"):  # Skip user tags
                    tag_to_words[tag].add(word_id)
        
        for tag, word_ids in tag_to_words.items():
            if len(word_ids) > 1:
                tag_node = f"TAG:{tag}"
                self.nx_graph.add_node(tag_node, node_type="tag")
                for word_id in word_ids:
                    if word_id in self.nx_graph:
                        self.nx_graph.add_edge(word_id, tag_node, weight=0.5, type="tag")
        
        # Add semantic similarity edges (if spaCy available)
        if self.nlp:
            print("  Calculating semantic similarity...")
            word_list = [node.word_text for node in self.word_nodes.values() if node.word_text]
            word_to_id = {node.word_text: node.word_id for node in self.word_nodes.values()}
            
            # Process words with spaCy
            docs = list(self.nlp.pipe(word_list))
            
            # Compare all pairs (this is O(N^2) but manageable for ~1000 words)
            added = 0
            for i, doc1 in enumerate(docs):
                for j, doc2 in enumerate(docs):
                    if i >= j:
                        continue
                    
                    sim = doc1.similarity(doc2)
                    if sim > SIMILARITY_THRESHOLD:
                        word_id1 = word_to_id[word_list[i]]
                        word_id2 = word_to_id[word_list[j]]
                        if word_id1 in self.nx_graph and word_id2 in self.nx_graph:
                            self.nx_graph.add_edge(
                                word_id1, word_id2,
                                weight=sim,
                                type="semantic"
                            )
                            added += 1
            
            print(f"  Added {added} semantic similarity edges")
        
        concept_hubs = sum(1 for n in self.nx_graph.nodes() if n.startswith('CONCEPT:'))
        tag_clusters = sum(1 for n in self.nx_graph.nodes() if n.startswith('TAG:'))
        print(f"✅ Graph built: {len(self.nx_graph.nodes())} nodes, {len(self.nx_graph.edges())} edges")
        print(f"   Concept hubs: {concept_hubs}, Tag clusters: {tag_clusters}")
    
    def spreading_activation(self) -> Dict[str, float]:
        """Run spreading activation algorithm."""
        print("\n⚡ Running spreading activation...")
        
        # Initialize activation with mastery scores
        activation = {node: 0.0 for node in self.nx_graph.nodes()}
        
        for word_id, mastery in self.mastery_scores.items():
            if word_id in activation:
                activation[word_id] = mastery
        
        # Propagate for multiple iterations
        for iteration in range(MAX_ITERATIONS):
            new_activation = activation.copy()
            
            for node in self.nx_graph.nodes():
                if activation[node] <= 0:
                    continue
                
                # Push energy to neighbors
                for neighbor in self.nx_graph.neighbors(node):
                    edge_data = self.nx_graph[node][neighbor]
                    weight = edge_data.get("weight", 0.5)
                    
                    # Energy transfer: current_activation * weight * decay
                    energy_transfer = activation[node] * weight * DECAY_FACTOR
                    new_activation[neighbor] += energy_transfer
            
            activation = new_activation
        
        print(f"✅ Activation propagated through {MAX_ITERATIONS} iterations")
        return activation
    
    def find_learning_frontier(self) -> Optional[str]:
        """Find the learning frontier CEFR level (first level with < 80% mastery)."""
        # Count mastered words by CEFR level
        mastery_by_level: Dict[str, Dict[str, int]] = defaultdict(lambda: {"mastered": 0, "total": 0})
        
        words_in_deck = set(self.mastery_scores.keys())
        words_in_deck.update(getattr(self, 'words_in_deck', set()))
        
        # Count total words and mastered words by level
        for word_id, node in self.word_nodes.items():
            if not node.cefr_level:
                continue
            
            level = node.cefr_level.upper()
            mastery_by_level[level]["total"] += 1
            
            if word_id in words_in_deck:
                mastery_by_level[level]["mastered"] += 1
        
        # Find learning frontier (first level with < 80% mastery)
        cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        target_level = None
        
        print(f"\n📊 Mastery rates by CEFR level:")
        for level in cefr_order:
            if level in mastery_by_level and mastery_by_level[level]["total"] > 0:
                rate = mastery_by_level[level]["mastered"] / mastery_by_level[level]["total"]
                print(f"   CEFR {level}: {mastery_by_level[level]['mastered']}/{mastery_by_level[level]['total']} ({rate*100:.1f}% mastered)")
                
                if rate < 0.8 and target_level is None:  # First level with < 80% mastery
                    target_level = level
                    print(f"   🎯 Learning frontier: CEFR {target_level} ({rate*100:.1f}% mastered)")
        
        if target_level is None:
            # If all levels are > 80%, use highest level
            target_level = cefr_order[-1]
            print(f"   🎯 All levels > 80% mastered, using highest: {target_level}")
        
        return target_level
    
    def generate_recommendations(self, activation: Dict[str, float], top_n: int = 20, 
                                 cefr_weight: float = 0.6, concreteness_weight: float = 0.3,
                                 activation_weight: float = 0.1) -> List[Recommendation]:
        """Generate recommendations based on activation, resistance, CEFR level, and concreteness."""
        print("\n🎯 Generating recommendations...")
        
        # Find learning frontier
        target_cefr = self.find_learning_frontier()
        
        # Get set of words already in Anki deck (to exclude them)
        words_in_deck = set(self.mastery_scores.keys())
        words_in_deck.update(getattr(self, 'words_in_deck', set()))
        print(f"   Excluding {len(words_in_deck)} words found in Anki deck(s)")
        
        recommendations = []
        candidates_considered = 0
        
        # CEFR level scoring (similar to HSK in Chinese recommender)
        cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        target_idx = cefr_order.index(target_cefr) if target_cefr in cefr_order else 2
        
        for word_id, node in self.word_nodes.items():
            # CRITICAL: Skip words that are already in the deck
            if word_id in words_in_deck:
                continue
            
            if word_id not in self.nx_graph:
                continue
            
            # Only recommend words with CEFR levels (from CEFR-J vocabulary)
            if not node.cefr_level:
                continue
            
            candidates_considered += 1
            
            # Get activation from spreading activation (may be 0 if not connected)
            act = activation.get(word_id, 0.0)
            res = node.resistance
            
            # 1. CEFR Level Score (0-100 scale)
            cefr_score = 0.0
            node_level = node.cefr_level.upper()
            if node_level in cefr_order:
                node_idx = cefr_order.index(node_level)
                if node_idx == target_idx:
                    cefr_score = 100.0  # Target level gets highest priority
                elif node_idx == target_idx + 1:
                    cefr_score = 50.0   # Next level gets medium priority
                elif node_idx < target_idx:
                    cefr_score = 25.0   # Lower levels get small bonus (review)
                elif node_idx > target_idx + 1:
                    cefr_score = 0.0    # Too hard gets 0 (excluded)
            
            # 2. Concreteness Score (0-100 scale, higher = more concrete = easier)
            conc_score = 0.0
            if node.concreteness:
                # Concreteness is 1-5 scale, map to 0-100
                conc_score = ((node.concreteness - 1.0) / 4.0) * 100.0
            else:
                # No concreteness data, use neutral (middle of range)
                conc_score = 50.0
            
            # 3. Activation Score (0-100 scale)
            act_score = min(100.0, act * 1000.0) if act > 0 else 0.0  # Scale activation to 0-100
            
            # 4. Concept Bonus (words sharing concepts with learned words)
            concept_bonus = 0.0
            if node.concept_id and node.concept_id in self.concept_to_words:
                shared_words = self.concept_to_words[node.concept_id]
                words_in_deck_sharing_concept = [w for w in shared_words if w in words_in_deck]
                if words_in_deck_sharing_concept:
                    # Bonus: 5 points per learned word sharing concept (max 20 points)
                    concept_bonus = min(20.0, len(words_in_deck_sharing_concept) * 5.0)
            
            # Combined score with weights
            # Normalize weights to sum to 1.0
            total_weight = cefr_weight + concreteness_weight + activation_weight
            if total_weight > 0:
                cefr_weight_norm = cefr_weight / total_weight
                conc_weight_norm = concreteness_weight / total_weight
                act_weight_norm = activation_weight / total_weight
            else:
                cefr_weight_norm = 0.6
                conc_weight_norm = 0.3
                act_weight_norm = 0.1
            
            score = (cefr_weight_norm * cefr_score + 
                    conc_weight_norm * conc_score + 
                    act_weight_norm * act_score + 
                    concept_bonus)
            
            # Determine reason
            reason_parts = []
            if cefr_score >= 100:
                reason_parts.append(f"CEFR {node_level} (target)")
            elif cefr_score >= 50:
                reason_parts.append(f"CEFR {node_level} (next)")
            if conc_score > 70:
                reason_parts.append("high concreteness")
            elif conc_score < 30:
                reason_parts.append("low concreteness")
            if act > 0.01:
                reason_parts.append(f"activation {act:.3f}")
            if concept_bonus > 0:
                reason_parts.append(f"shares concept")
            
            reason = ", ".join(reason_parts) if reason_parts else f"CEFR {node_level}"
            
            recommendations.append(Recommendation(
                word_id=word_id,
                word_text=node.word_text,
                activation=act,
                resistance=res,
                score=score,
                reason=reason
            ))
        
        print(f"   Considered {candidates_considered} candidate words not in deck")
        print(f"   Scoring weights: CEFR={cefr_weight:.1f}, Concreteness={concreteness_weight:.1f}, Activation={activation_weight:.1f}")
        
        # Sort by score
        recommendations.sort(key=lambda x: x.score, reverse=True)
        
        return recommendations[:top_n]
    
    def run(self, top_n: int = 20):
        """Run the complete experiment."""
        print("=" * 80)
        print("English Vocabulary Recommender Experiment")
        print("=" * 80)
        
        # Load data
        if not self.load_knowledge_graph():
            return
        
        if not self.load_anki_data():
            return
        
        # Enrich attributes
        self.enrich_word_attributes()
        
        # Build graph
        self.build_graph()
        
        # Run spreading activation
        activation = self.spreading_activation()
        
        # Generate recommendations
        recommendations = self.generate_recommendations(activation, top_n)
        
        # Print results
        print("\n" + "=" * 80)
        print(f"TOP {top_n} RECOMMENDATIONS")
        print("=" * 80)
        print(f"{'WORD':<25} {'SCORE':<10} {'ACT':<8} {'RES':<8} {'REASON':<30}")
        print("-" * 80)
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{i:2d}. {rec.word_text:<23} {rec.score:.4f}     {rec.activation:.3f}   {rec.resistance:.2f}   {rec.reason[:28]}")
        
        print("\n" + "=" * 80)
        print("Summary Statistics")
        print("=" * 80)
        print(f"Total words in graph: {len(self.word_nodes)}")
        print(f"Words with mastery scores: {len(self.mastery_scores)}")
        print(f"Graph nodes: {len(self.nx_graph.nodes())}")
        print(f"Graph edges: {len(self.nx_graph.edges())}")
        print(f"Concept hubs: {sum(1 for n in self.nx_graph.nodes() if n.startswith('CONCEPT:'))}")
        print(f"Tag clusters: {sum(1 for n in self.nx_graph.nodes() if n.startswith('TAG:'))}")
        
        # Save results to file
        output_dir = project_root / "data" / "logs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "english_recommender_results.json"
        
        results = {
            "recommendations": [
                {
                    "word_id": rec.word_id,
                    "word_text": rec.word_text,
                    "score": rec.score,
                    "activation": rec.activation,
                    "resistance": rec.resistance,
                    "reason": rec.reason
                }
                for rec in recommendations
            ],
            "statistics": {
                "total_words_in_graph": len(self.word_nodes),
                "words_with_mastery": len(self.mastery_scores),
                "graph_nodes": len(self.nx_graph.nodes()),
                "graph_edges": len(self.nx_graph.edges()),
                "concept_hubs": sum(1 for n in self.nx_graph.nodes() if n.startswith('CONCEPT:')),
                "tag_clusters": sum(1 for n in self.nx_graph.nodes() if n.startswith('TAG:'))
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        return recommendations


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="English Vocabulary Recommender Experiment")
    parser.add_argument("--top-n", type=int, default=20, help="Number of recommendations to show")
    args = parser.parse_args()
    
    experiment = EnglishRecommenderExperiment()
    experiment.run(top_n=args.top_n)


if __name__ == "__main__":
    main()

