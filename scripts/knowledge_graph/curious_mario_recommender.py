#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Curious Mario recommender engine.

This module implements the heuristic recommendation engine that emerged from the
"CLT Demystified" discussion.  It ties together three data sources:

1.  Anki (via the AnkiConnect API) – treated as the "mastery sensor" for the
    learner.  Notes created by the CUMA authoring tools contain a `_KG_Map`
    field that maps individual cards to knowledge-graph node identifiers.
2.  The Jena Fuseki knowledge graph – treated as the "external world model".
    We query the graph for every candidate node, its label, optional HSK level
    and the prerequisites expressed via `srs-kg:requiresPrerequisite`.
3.  Lightweight Cognitive Load Theory heuristics – we try to keep learners in
    their Zone of Proximal Development (ZPD) by recommending nodes whose
    prerequisites are mastered while the node itself is not yet mastered.

The script can be used as a standalone CLI (`python curious_mario_recommender.py`) or
imported from other modules.  No backend changes are required; everything is
implemented with pure Python and HTTP calls.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union
from pathlib import Path

import requests

# Add the project root to sys.path so we can reach the backend folder
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database.kg_client import KnowledgeGraphClient, KnowledgeGraphError
from anki_integration.anki_connect import AnkiConnect


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CardState:
    """Current spaced-repetition state for a single Anki card."""

    card_id: int
    interval: int
    lapses: int
    reps: int
    ease_factor: Optional[int]


@dataclass
class KnowledgeNode:
    """Node description fetched from the knowledge graph."""

    node_id: str
    iri: str
    label: str
    hsk_level: Optional[int] = None
    cefr_level: Optional[str] = None  # For English words
    concreteness: Optional[float] = None  # 1-5 scale, higher = more concrete
    frequency: Optional[float] = None  # Raw frequency count if available
    frequency_rank: Optional[int] = None  # Lower rank = more frequent
    age_of_acquisition: Optional[float] = None  # AoA in years (from Kuperman et al.)
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """Recommendation output."""

    node_id: str
    label: str
    hsk_level: Optional[int]
    mastery: float
    prereq_mastery: float
    score: float
    missing_prereqs: List[str] = field(default_factory=list)


@dataclass
class RecommenderConfig:
    """Configurable knobs for the heuristics."""

    anki_query: str = '_KG_Map:*'
    kg_field_name: str = "_KG_Map"
    fuseki_endpoint: Optional[str] = None
    node_types: Tuple[str, ...] = ("srs-kg:Word",)
    mastery_threshold: float = 0.85
    prereq_threshold: float = 0.75
    remedial_threshold: float = 0.45
    challenge_weight: float = 0.7
    prereq_weight: float = 0.3
    target_hsk_level: Optional[int] = 3
    hsk_match_bonus: float = 0.1
    hsk_penalty: float = 0.05
    lapse_penalty: float = 0.12
    max_interval_for_norm: int = 120  # days
    ease_factor_scale: int = 3500
    top_n: int = 20
    # English vocabulary parameters
    # Slider: 0.0 = Max Frequency (Utility), 1.0 = Max Concreteness (Ease)
    concreteness_weight: float = 0.5  # Slider position (0.0-1.0), default 0.5 = balanced
    # Note: CEFR is now a hard filter (not a weight), only showing current level and +1
    activation_weight: float = 0.1  # Weight for activation (0.0-1.0)
    auto_detect_language: bool = True  # Auto-detect Chinese vs English
    semantic_similarity_weight: float = 1.5  # Boost for semantic neighbours (English only)
    mental_age: Optional[float] = None  # Mental age for AoA filtering (e.g., 7.0 for a 7-year-old)
    aoa_buffer: float = 2.0  # Allow words with AoA up to mental_age + buffer
    target_language: Optional[str] = None # For filtering grammar recommendations by language


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _chunked(seq: Iterable[int], size: int) -> Iterable[List[int]]:
    """Yield chunks from *seq* with maximum length *size*."""

    chunk: List[int] = []
    for item in seq:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _normalize_kg_id(raw_id: str) -> str:
    """Normalise KG identifiers so we can match them with SPARQL results."""

    if not raw_id:
        return raw_id
    raw_id = raw_id.strip()
    if raw_id.startswith("http://") or raw_id.startswith("https://"):
        if raw_id.startswith("http://srs4autism.com/schema/"):
            return "srs-kg:" + raw_id.rsplit("/", 1)[-1]
        if raw_id.startswith("http://srs4autism.com/instance/"):
            return "srs-inst:" + raw_id.rsplit("/", 1)[-1]
        return raw_id
    if ":" in raw_id:
        return raw_id
    # Plain local name -> assume schema namespace
    return f"srs-kg:{raw_id}"


def _iri_from_id(node_id: str) -> str:
    """Return a full IRI suitable for SPARQL queries."""

    if node_id.startswith("http://") or node_id.startswith("https://"):
        return f"<{node_id}>"
    if node_id.startswith("srs-kg:"):
        local = node_id.split(":", 1)[1]
        return f"<http://srs4autism.com/schema/{local}>"
    if node_id.startswith("srs-inst:"):
        local = node_id.split(":", 1)[1]
        return f"<http://srs4autism.com/instance/{local}>"
    return f"<http://srs4autism.com/schema/{node_id}>"


# ---------------------------------------------------------------------------
# Anki mastery extraction
# ---------------------------------------------------------------------------


class AnkiMasteryExtractor:
    """Pull `_KG_Map` metadata and card states via AnkiConnect."""

    def __init__(self, config: RecommenderConfig):
        self.config = config
        self.client = AnkiConnect()

    def fetch_kg_card_states(self) -> Dict[str, List[CardState]]:
        """Return mapping of kg_id -> list of card states."""

        if not self.client.ping():
            raise RuntimeError(
                "AnkiConnect is not reachable. Please ensure Anki is running "
                "with the AnkiConnect add-on installed."
            )

        note_ids = self.client._invoke("findNotes", {"query": self.config.anki_query})
        if not note_ids:
            print("⚠️  No CUMA notes with _KG_Map field were found via Anki search.")
            return {}

        notes_info: List[Dict[str, object]] = []
        for chunk in _chunked(note_ids, 250):
            data = self.client._invoke("notesInfo", {"notes": chunk})
            if data:
                notes_info.extend(data)

        card_ids: List[int] = []
        for note in notes_info:
            card_ids.extend(note.get("cards", []))

        cards_map: Dict[int, Dict[str, object]] = {}
        for chunk in _chunked(card_ids, 250):
            data = self.client._invoke("cardsInfo", {"cards": chunk})
            if not data:
                continue
            for card in data:
                cards_map[card.get("cardId")] = card

        kg_to_card_states: Dict[str, List[CardState]] = {}

        for note in notes_info:
            fields = note.get("fields", {})
            kg_field = fields.get(self.config.kg_field_name)
            kg_map_raw = None
            if isinstance(kg_field, dict):
                kg_map_raw = kg_field.get("value")
            elif isinstance(kg_field, str):
                kg_map_raw = kg_field

            if not kg_map_raw:
                continue

            try:
                kg_map = json.loads(kg_map_raw)
            except json.JSONDecodeError:
                print(f"⚠️  Invalid JSON in _KG_Map field: {kg_map_raw[:50]}...")
                continue

            note_card_ids = note.get("cards", [])
            for card_id in note_card_ids:
                card = cards_map.get(card_id)
                if not card:
                    continue

                cloze_index = int(card.get("ord", 0)) + 1
                kg_ids = self._kg_ids_for_card(kg_map, cloze_index)
                if not kg_ids:
                    continue

                card_state = CardState(
                    card_id=card_id,
                    interval=int(card.get("interval", 0)),
                    lapses=int(card.get("lapses", 0)),
                    reps=int(card.get("reps", 0)),
                    ease_factor=int(card.get("factor")) if card.get("factor") else None,
                )

                for kg_id in kg_ids:
                    normalized_id = _normalize_kg_id(kg_id)
                    kg_to_card_states.setdefault(normalized_id, []).append(card_state)

        return kg_to_card_states

    @staticmethod
    def _kg_ids_for_card(kg_map: object, card_index: int) -> List[str]:
        """Return KG identifiers for a given card (supports legacy and new formats)."""

        if not isinstance(kg_map, list):
            return []

        for entry in kg_map:
            if not isinstance(entry, dict):
                continue

            entry_index = entry.get("card_index")
            if entry_index is None:
                entry_index = entry.get("cloze_index")

            try:
                entry_index = int(entry_index)
            except (TypeError, ValueError):
                continue

            if entry_index != card_index:
                continue

            # New structure with kg_link
            kg_link = entry.get("kg_link")
            if isinstance(kg_link, dict):
                target = kg_link.get("target")
                source = kg_link.get("source")
                if target:
                    return [str(target)]
                if source:
                    return [str(source)]

            # Legacy structure with kg_ids
            kg_ids = entry.get("kg_ids", [])
            if isinstance(kg_ids, list):
                return [str(k) for k in kg_ids if k]
            if isinstance(kg_ids, str):
                return [kg_ids]

        return []


# ---------------------------------------------------------------------------
# Mastery vector heuristic
# ---------------------------------------------------------------------------


class MasteryVectorGenerator:
    """Convert card states into a 0..1 mastery score."""

    def __init__(self, config: RecommenderConfig):
        self.config = config

    def generate(self, kg_to_card_states: Dict[str, List[CardState]]) -> Dict[str, float]:
        vector: Dict[str, float] = {}
        for kg_id, states in kg_to_card_states.items():
            vector[kg_id] = self._calculate_score(states)
        return vector

    def _calculate_score(self, states: List[CardState]) -> float:
        if not states:
            return 0.0

        min_interval = min(max(state.interval, 0) for state in states)
        normalized_interval = math.log(min_interval + 1) / math.log(
            self.config.max_interval_for_norm + 1
        )

        total_lapses = sum(max(state.lapses, 0) for state in states)
        lapse_penalty = total_lapses * self.config.lapse_penalty

        ease_values = [state.ease_factor for state in states if state.ease_factor]
        if ease_values:
            avg_ease = sum(ease_values) / len(ease_values)
            ease_term = (avg_ease / self.config.ease_factor_scale) * 0.2
        else:
            ease_term = 0.0

        score = normalized_interval + ease_term - lapse_penalty
        return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Knowledge graph client
# ---------------------------------------------------------------------------


class KnowledgeGraphService:
    """Fetch node metadata from knowledge graph via SPARQL."""

    def __init__(self, config: RecommenderConfig, kg_client=None):
        self.config = config
        if kg_client:
            self.kg_client = kg_client
        else:
            # Fallback to creating a client if none is provided
            self.kg_client = KnowledgeGraphClient(
                endpoint_url=self.config.fuseki_endpoint if self.config.fuseki_endpoint else None
            )

    def fetch_nodes(self) -> Dict[str, KnowledgeNode]:
        node_types = " ".join(self.config.node_types)
        query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX srs-inst: <http://srs4autism.com/instance/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT ?node ?label ?hsk ?cefr ?concreteness ?frequency ?freqRank ?aoa ?prereq
        WHERE {{
            VALUES ?type {{ {node_types} }}
            ?node a ?type .
            ?node rdfs:label ?label .
            OPTIONAL {{ ?node srs-kg:hskLevel ?hsk }}
            OPTIONAL {{ ?node srs-kg:cefrLevel ?cefr }}
            OPTIONAL {{ ?node srs-kg:concreteness ?concreteness }}
            OPTIONAL {{ ?node srs-kg:frequency ?frequency }}
            OPTIONAL {{ ?node srs-kg:frequencyRank ?freqRank }}
            OPTIONAL {{ ?node srs-kg:ageOfAcquisition ?aoa }}
            OPTIONAL {{ ?node srs-kg:requiresPrerequisite ?prereq }}
            FILTER (!STRSTARTS(STR(?label), "synset:"))
            FILTER (!STRSTARTS(STR(?label), "concept:"))
        """
        
        if self.config.target_language == "zh":
            # Chinese: Exclude grammar points with IDs starting with "grammar-en-" or "gp-en-"
            # and only include those with rdfs:label@zh or no language tag (assuming Chinese)
            query += '    FILTER (!STRSTARTS(STR(?node), "http://srs4autism.com/instance/grammar-en-"))\n'
            query += '    FILTER (!STRSTARTS(STR(?node), "http://srs4autism.com/instance/gp-en-"))\n'
            query += '    FILTER (lang(?label) = "zh" || lang(?label) = "")\n'
        elif self.config.target_language == "en":
            # English: Only include grammar points with IDs starting with "grammar-en-" or "gp-en-"
            # and rdfs:label@en
            query += '    FILTER (STRSTARTS(STR(?node), "http://srs4autism.com/instance/grammar-en-") || STRSTARTS(STR(?node), "http://srs4autism.com/instance/gp-en-"))\n'
            query += '    FILTER (lang(?label) = "en")\n'

        query += "}"

        print(f"\n--- DEBUG SPARQL ---\n{query}\n------------------\n")

        try:
            data = self.kg_client.query(query)
        except KnowledgeGraphError as e:
            raise RuntimeError(f"Failed to fetch nodes from knowledge graph: {e}") from e

        nodes: Dict[str, KnowledgeNode] = {}
        for row in data.get("results", {}).get("bindings", []):
            node_iri = row["node"]["value"]
            label = row["label"]["value"]
            node_id = _normalize_kg_id(node_iri)

            node = nodes.setdefault(
                node_id,
                KnowledgeNode(
                    node_id=node_id,
                    iri=node_iri,
                    label=label,
                    hsk_level=None,
                    cefr_level=None,
                    concreteness=None,
                    frequency=None,
                    frequency_rank=None,
                    age_of_acquisition=None,
                    prerequisites=[],
                ),
            )

            if "hsk" in row and row["hsk"]["value"]:
                try:
                    node.hsk_level = int(float(row["hsk"]["value"]))
                except ValueError:
                    pass

            if "cefr" in row and row["cefr"]["value"]:
                node.cefr_level = str(row["cefr"]["value"]).upper()

            if "concreteness" in row and row["concreteness"]["value"]:
                try:
                    node.concreteness = float(row["concreteness"]["value"])
                except (ValueError, TypeError):
                    pass

            if "frequency" in row and row["frequency"]["value"]:
                try:
                    node.frequency = float(row["frequency"]["value"])
                except (ValueError, TypeError):
                    pass

            if "freqRank" in row and row["freqRank"]["value"]:
                try:
                    node.frequency_rank = int(float(row["freqRank"]["value"]))
                except (ValueError, TypeError):
                    pass

            if "aoa" in row and row["aoa"]["value"]:
                try:
                    node.age_of_acquisition = float(row["aoa"]["value"])
                except (ValueError, TypeError):
                    pass

            if "prereq" in row and row["prereq"]["value"]:
                prereq_id = _normalize_kg_id(row["prereq"]["value"])
                if prereq_id not in node.prerequisites:
                    node.prerequisites.append(prereq_id)

        return nodes


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


class CuriousMarioRecommender:
    """Main façade class that orchestrates the pipeline."""

    def __init__(self, config: Optional[RecommenderConfig] = None, kg_client=None):
        self.config = config or RecommenderConfig()
        self.anki_extractor = AnkiMasteryExtractor(self.config)
        self.mastery_generator = MasteryVectorGenerator(self.config)
        self.kg_service = KnowledgeGraphService(self.config, kg_client=kg_client)

    def build_mastery_vector(self) -> Dict[str, float]:
        kg_to_card_states = self.anki_extractor.fetch_kg_card_states()
        return self.mastery_generator.generate(kg_to_card_states)

    def _detect_language(self, nodes: Dict[str, KnowledgeNode]) -> str:
        """Detect if we're working with Chinese or English words."""
        if not self.config.auto_detect_language:
            # Default to Chinese if auto-detect is off
            return "zh"
        
        # Check if we have CEFR levels (English) or HSK levels (Chinese)
        has_cefr = any(node.cefr_level for node in nodes.values())
        has_hsk = any(node.hsk_level for node in nodes.values())
        
        if has_cefr and not has_hsk:
            return "en"
        elif has_hsk and not has_cefr:
            return "zh"
        elif has_cefr and has_hsk:
            # Mixed: use majority
            cefr_count = sum(1 for node in nodes.values() if node.cefr_level)
            hsk_count = sum(1 for node in nodes.values() if node.hsk_level)
            return "en" if cefr_count > hsk_count else "zh"
        else:
            # No level data: check label language
            en_labels = sum(1 for node in nodes.values() if any(ord(c) < 128 for c in node.label[:10]))
            return "en" if en_labels > len(nodes) / 2 else "zh"
    
    def _find_learning_frontier(self, nodes: Dict[str, KnowledgeNode], mastery_vector: Dict[str, float], language: str) -> Optional[Union[int, str]]:
        """Find the learning frontier level (HSK for Chinese, CEFR for English)."""
        if language == "zh":
            # Find HSK learning frontier
            mastery_by_level: Dict[int, Dict[str, int]] = {}
            for node in nodes.values():
                if node.hsk_level is None:
                    continue
                level = node.hsk_level
                if level not in mastery_by_level:
                    mastery_by_level[level] = {"mastered": 0, "total": 0}
                mastery_by_level[level]["total"] += 1
                if mastery_vector.get(node.node_id, 0.0) >= self.config.mastery_threshold:
                    mastery_by_level[level]["mastered"] += 1
            
            for level in sorted(mastery_by_level.keys()):
                rate = mastery_by_level[level]["mastered"] / mastery_by_level[level]["total"]
                if rate < 0.8:
                    return level
            return max(mastery_by_level.keys()) if mastery_by_level else None
        else:
            # Find CEFR learning frontier
            cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
            mastery_by_level: Dict[str, Dict[str, int]] = {}
            for node in nodes.values():
                if not node.cefr_level:
                    continue
                level = node.cefr_level.upper()
                if level not in mastery_by_level:
                    mastery_by_level[level] = {"mastered": 0, "total": 0}
                mastery_by_level[level]["total"] += 1
                if mastery_vector.get(node.node_id, 0.0) >= self.config.mastery_threshold:
                    mastery_by_level[level]["mastered"] += 1
            
            for level in cefr_order:
                if level in mastery_by_level:
                    rate = mastery_by_level[level]["mastered"] / mastery_by_level[level]["total"]
                    if rate < 0.8:
                        return level
            return cefr_order[-1] if mastery_by_level else None

    def generate_recommendations(self) -> Tuple[List[Recommendation], List[Recommendation], Dict[str, float], Dict[str, KnowledgeNode], str]:
        mastery_vector = self.build_mastery_vector()
        nodes = self.kg_service.fetch_nodes()
        
        # Detect language and find learning frontier
        language = self._detect_language(nodes)
        learning_frontier = self._find_learning_frontier(nodes, mastery_vector, language)
        
        if learning_frontier is not None:
            if language == "zh":
                print(f"🎯 Learning frontier: HSK {learning_frontier}")
            else:
                print(f"🎯 Learning frontier: CEFR {learning_frontier}")

        exploratory: List[Recommendation] = []
        remedial: List[Recommendation] = []

        for node in nodes.values():
            mastery = mastery_vector.get(node.node_id, 0.0)

            prereq_scores = [mastery_vector.get(pr, 0.0) for pr in node.prerequisites]
            missing_prereqs = [pr for pr, score in zip(node.prerequisites, prereq_scores) if score < self.config.prereq_threshold]
            prereq_mastery = min(prereq_scores) if prereq_scores else 1.0

            if mastery >= self.config.mastery_threshold:
                continue
            if missing_prereqs:
                continue

            score = self._score_candidate(node, mastery, prereq_mastery, language, learning_frontier)
            exploratory.append(
                Recommendation(
                    node_id=node.node_id,
                    label=node.label,
                    hsk_level=node.hsk_level,
                    mastery=mastery,
                    prereq_mastery=prereq_mastery,
                    score=score,
                )
            )

        exploratory.sort(key=lambda rec: rec.score, reverse=True)
        exploratory = exploratory[: self.config.top_n]

        for node_id, mastery in mastery_vector.items():
            if mastery >= self.config.remedial_threshold:
                continue
            node = nodes.get(node_id)
            if not node:
                continue
            prereq_scores = [mastery_vector.get(pr, 0.0) for pr in node.prerequisites]
            missing_prereqs = [pr for pr, score in zip(node.prerequisites, prereq_scores) if score < self.config.prereq_threshold]
            remedial.append(
                Recommendation(
                    node_id=node.node_id,
                    label=node.label,
                    hsk_level=node.hsk_level,
                    mastery=mastery,
                    prereq_mastery=min(prereq_scores) if prereq_scores else 1.0,
                    score=mastery,
                    missing_prereqs=missing_prereqs,
                )
            )

        remedial.sort(key=lambda rec: rec.mastery)
        remedial = remedial[: self.config.top_n]

        return exploratory, remedial, mastery_vector, nodes, language

    def _score_candidate(self, node: KnowledgeNode, mastery: float, prereq_mastery: float, 
                         language: str = "zh", learning_frontier: Optional[Union[int, str]] = None) -> float:
        readiness = 1.0 - mastery
        base_score = (readiness * self.config.challenge_weight) + (
            prereq_mastery * self.config.prereq_weight
        )

        if language == "zh":
            # Chinese: use HSK level scoring + AoA filtering and scoring
            
            # AoA filter: Exclude words with AoA > mental_age + buffer (if mental_age is set)
            if self.config.mental_age is not None and node.age_of_acquisition is not None:
                aoa_ceiling = self.config.mental_age + self.config.aoa_buffer
                if node.age_of_acquisition > aoa_ceiling:
                    # Too advanced for mental age - return very low score to exclude
                    return 0.01
            
            # HSK level scoring
            if node.hsk_level is not None:
                if learning_frontier is not None and isinstance(learning_frontier, int):
                    target_level = learning_frontier
                else:
                    target_level = self.config.target_hsk_level or 3
                
                diff = node.hsk_level - target_level
            if diff == 0:
                    base_score += self.config.hsk_match_bonus
            elif diff == 1:
                    base_score += self.config.hsk_match_bonus * 0.5
            elif diff > 1:
                    base_score -= self.config.hsk_penalty * diff
            
            # AoA bonus/penalty for Chinese words (if AoA data available)
            # Lower AoA = easier = bonus, Higher AoA = harder = penalty
            if node.age_of_acquisition is not None:
                # Normalize AoA to 0-1 scale (lower AoA = higher score)
                # Assuming typical range: 2-15 years
                aoa_score = max(0.0, 1.0 - (node.age_of_acquisition / 15.0))
                # Add AoA as a bonus/penalty (scale: -0.2 to +0.2)
                # Words learned earlier (lower AoA) get bonus, words learned later get penalty
                aoa_bonus = (aoa_score - 0.5) * 0.4  # Maps 0-1 to -0.2 to +0.2
                base_score += aoa_bonus
        else:
            # English: "Filter then Rank" strategy
            # Step 1: HARD FILTERS (CEFR and AoA)
            # CEFR filter: Only consider words in Zone of Proximal Development (current level and +1)
            if node.cefr_level and learning_frontier and isinstance(learning_frontier, str):
                cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
                node_level = node.cefr_level.upper()
                if node_level in cefr_order:
                    target_idx = cefr_order.index(learning_frontier) if learning_frontier in cefr_order else 2
                    node_idx = cefr_order.index(node_level)
                    # Filter: only allow current level and +1 level
                    if node_idx > target_idx + 1:
                        # Too hard - return very low score to exclude
                        return 0.01
            
            # AoA filter: Exclude words with AoA > mental_age + buffer
            if self.config.mental_age is not None and node.age_of_acquisition is not None:
                aoa_ceiling = self.config.mental_age + self.config.aoa_buffer
                if node.age_of_acquisition > aoa_ceiling:
                    # Too advanced for mental age - return very low score to exclude
                    return 0.01
            
            # Step 2: Calculate component scores (0-1.0 scale)
            # Concreteness score (0-1.0 scale, higher = more concrete = easier)
            if node.concreteness:
                conc_score = (node.concreteness - 1.0) / 4.0  # 1.0→0.0, 5.0→1.0
            else:
                conc_score = 0.5  # Neutral if no data
            
            # AoA score (0-1.0 scale, lower AoA = higher score = easier)
            # Formula: V_AoA = max(0, 1 - AoA/15)
            if node.age_of_acquisition is not None:
                aoa_score = max(0.0, 1.0 - (node.age_of_acquisition / 15.0))
            else:
                aoa_score = 0.5  # Neutral if no data (default to harder)
            
            # Frequency score using Zipf scale (logarithmic normalization)
            # Formula: V_freq = 1 - ln(Rank) / ln(MaxRank)
            max_rank = 20000.0
            if node.frequency_rank:
                rank = float(min(max_rank, max(1, node.frequency_rank)))
                # Use natural log for Zipf scale
                freq_score = max(0.0, 1.0 - (math.log(rank) / math.log(max_rank)))
            elif node.frequency:
                # If we have raw frequency, use log scale
                freq_score = min(
                    1.0,
                    (math.log10(node.frequency + 1.0) / math.log10(50000.0)),
                ) if node.frequency > 0 else 0.5
            else:
                freq_score = 0.5  # Neutral if no data
            
            # Step 3: Combine Concreteness and AoA into "Ease" component
            # Ease = 0.7 * Concreteness + 0.3 * AoA (as per Gemini's recommendation)
            ease_score = (0.7 * conc_score) + (0.3 * aoa_score)
            
            # Step 4: Weighted combination (slider: Frequency vs Ease)
            # Slider S: 0.0 = Max Frequency (Utility), 1.0 = Max Ease (Concreteness + AoA)
            # Score = (1 - S) * V_freq + S * V_ease
            slider_value = self.config.concreteness_weight  # 0.0-1.0, where 1.0 = max ease
            weighted_score = ((1.0 - slider_value) * freq_score) + (slider_value * ease_score)
            
            # Convert to 0-10 scale for final score
            base_score = weighted_score * 10.0
            
            # Add small bonus for readiness (words not yet mastered get slight boost)
            readiness_bonus = (1.0 - mastery) * 0.1
            base_score += readiness_bonus
            
            # Debug: log scoring details for first few words
            if not hasattr(self, '_debug_logged_count'):
                self._debug_logged_count = 0
            if self._debug_logged_count < 3:
                print(
                    f"      DEBUG SCORING: {node.label} | "
                    f"CEFR={node.cefr_level} (filter) | "
                    f"AoA={node.age_of_acquisition}→{aoa_score:.3f} | "
                    f"CONC={node.concreteness}→{conc_score:.3f} | "
                    f"EASE={ease_score:.3f} (0.7*conc+0.3*aoa) | "
                    f"FREQ={'rank ' + str(node.frequency_rank) if node.frequency_rank else ('freq ' + str(node.frequency) if node.frequency else 'N/A')}→{freq_score:.3f} | "
                    f"slider={slider_value:.2f} (0=freq, 1=ease) | "
                    f"weighted={weighted_score:.3f} | final={base_score:.2f}"
                )
                self._debug_logged_count += 1

        return base_score


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Curious Mario recommender")
    parser.add_argument("--anki-query", default='_KG_Map:*', help="Anki search query to locate CUMA notes")
    parser.add_argument("--kg-endpoint", default="http://localhost:3030/srs4autism/query", help="Fuseki SPARQL endpoint")
    parser.add_argument("--target-hsk", type=int, default=None, help="Target HSK level for exploratory recommendations (auto-detected if not specified)")
    parser.add_argument("--top", type=int, default=20, help="Number of recommendations to display")
    parser.add_argument("--slider", type=float, default=0.5, help="Slider position for English recommendations (0.0=Frequency/Utility, 1.0=Concreteness/Ease)")
    args = parser.parse_args(argv)

    config = RecommenderConfig(
        anki_query=args.anki_query,
        fuseki_endpoint=args.kg_endpoint,
        target_hsk_level=args.target_hsk,
        top_n=args.top,
        concreteness_weight=max(0.0, min(1.0, args.slider)),  # This is now the slider position
    )

    recommender = CuriousMarioRecommender(config)

    try:
        exploratory, remedial, mastery_vector, nodes, language = recommender.generate_recommendations()
    except Exception as exc:
        print(f"❌ Failed to build recommendations: {exc}")
        return 1

    print("=" * 80)
    print("Curious Mario – Exploratory Recommendations")
    print("=" * 80)
    if not exploratory:
        print("(No exploratory recommendations – either everything is mastered or prerequisites are missing.)")
    
    for idx, rec in enumerate(exploratory, 1):
        level_str = ""
        if language == "zh":
            level_str = f"HSK: {rec.hsk_level or '-'}"
        else:
            # For English, get CEFR from node
            node = nodes.get(rec.node_id)
            if node and node.cefr_level:
                level_str = f"CEFR: {node.cefr_level}"
            else:
                level_str = "CEFR: -"
        
        print(
            f"{idx:2d}. {rec.label} [{rec.node_id}] | {level_str} | "
            f"Mastery: {rec.mastery:.2f} | Score: {rec.score:.2f}"
        )

    print("\n" + "=" * 80)
    print("Curious Mario – Remedial Alerts")
    print("=" * 80)
    if not remedial:
        print("(No remedial items detected)")
    for idx, rec in enumerate(remedial, 1):
        print(
            f"{idx:2d}. {rec.label} [{rec.node_id}] | Mastery: {rec.mastery:.2f} | "
            f"Missing prereqs: {', '.join(rec.missing_prereqs) if rec.missing_prereqs else 'None'}"
        )

    print("\nTotal mastery entries tracked:", len(mastery_vector))
    return 0


if __name__ == "__main__":
    sys.exit(main())


