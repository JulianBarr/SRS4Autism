#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Personalized PageRank (PPR) recommender built on top of the
spaCy-derived semantic similarity graph.

This script follows the plan outlined in
`Recommendation improved by using PPR with Spacy similarity and mastered words
and anki review history.md`.  It builds an undirected, weighted graph from the
pre-computed similarity JSON file, applies Personalized PageRank using the
child's mastered words (optionally weighted by Anki review history), and prints
the top candidate words that are close to the learner's current frontier.

Usage examples:

  # Uniform weights (each mastered word treated equally)
  python ppr_recommender.py --mastered word-en-cat word-en-dog --top-n 15

  # Weighted seeds using "word:weight" pairs (e.g. Anki ease factors)
  python ppr_recommender.py --mastered-weighted word-en-cat:2.5 word-en-dog:1.2

  # Load mastered data from JSON (list or {word: weight} mapping)
  python ppr_recommender.py --mastered-json data/mastered_words.json
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Tuple

import networkx as nx

try:
    import inflect

    _INFLECT = inflect.engine()
except Exception:  # pragma: no cover - optional dependency
    _INFLECT = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMILARITY_FILE = (
    PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"
)
DEFAULT_KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_english.ttl"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
DEFAULT_ANKI_COLLECTION = (
    PROJECT_ROOT
    / "temp_anki_extract"
    / "English__Vocabulary__2. Level 2"
    / "collection.anki21"
)


@dataclass
class WordMetadata:
    node_id: str
    label: str
    cefr: str | None = None
    concreteness: float | None = None
    frequency_rank: int | None = None
    age_of_acquisition: float | None = None


# Comprehensive spelling variants (British -> American, prefer American as canonical)
_SPELLING_VARIANTS = {
    # -our/-or endings
    "colour": "color",
    "favour": "favor",
    "honour": "honor",
    "behaviour": "behavior",
    "neighbour": "neighbor",
    "labour": "labor",
    "humour": "humor",
    "rumour": "rumor",
    "vapour": "vapor",
    "odour": "odor",
    "tumour": "tumor",
    "vigour": "vigor",
    "armour": "armor",
    "ardour": "ardor",
    "clamour": "clamor",
    "endeavour": "endeavor",
    "fervour": "fervor",
    "flavour": "flavor",
    "glamour": "glamor",
    "harbour": "harbor",
    "parlour": "parlor",
    "rancour": "rancor",
    "rigour": "rigor",
    "saviour": "savior",
    "savour": "savor",
    "splendour": "splendor",
    "valour": "valor",
    # -ise/-ize endings
    "realise": "realize",
    "organise": "organize",
    "recognise": "recognize",
    "analyse": "analyze",
    "paralyse": "paralyze",
    "catalyse": "catalyze",
    "apologise": "apologize",
    "criticise": "criticize",
    "memorise": "memorize",
    "prioritise": "prioritize",
    "specialise": "specialize",
    "summarise": "summarize",
    "theorise": "theorize",
    "visualise": "visualize",
    # -re/-er endings
    "centre": "center",
    "theatre": "theater",
    "metre": "meter",
    "litre": "liter",
    "fibre": "fiber",
    "calibre": "caliber",
    "sabre": "saber",
    "sombre": "somber",
    "spectre": "specter",
    "lustre": "luster",
    # -ence/-ense endings
    "defence": "defense",
    "offence": "offense",
    "licence": "license",
    "pretence": "pretense",
    # -ogue/-og endings
    "dialogue": "dialog",
    "catalogue": "catalog",
    "analogue": "analog",
    "prologue": "prolog",
    "monologue": "monolog",
    "epilogue": "epilog",
    # -ll/-l (doubled consonants in past tense)
    "travelled": "traveled",
    "cancelled": "canceled",
    "labelled": "labeled",
    "modelled": "modeled",
    "fuelled": "fueled",
    "jewelled": "jeweled",
    "marvelled": "marveled",
    "panelled": "paneled",
    "quarrelled": "quarreled",
    "signalled": "signaled",
    "totalled": "totaled",
    "tunnelled": "tunneled",
    "unravelled": "unraveled",
    # -l/-ll (verb forms)
    "enrol": "enroll",
    "fulfil": "fulfill",
    "instil": "instill",
    "distil": "distill",
    # Other common variants
    "mould": "mold",
    "moult": "molt",
    "smoulder": "smolder",
    "moustache": "mustache",
    "pyjamas": "pajamas",
    "plough": "plow",
    "sceptre": "scepter",
    "sceptic": "skeptic",
    "sulphur": "sulfur",
    "tyre": "tire",
    "whisky": "whiskey",
    "yoghurt": "yogurt",
    "practise": "practice",  # verb form (noun "practice" is same in both)
    "counsellor": "counselor",
    "traveller": "traveler",
    "grey": "gray",  # color spelling variant
}


def _normalize_spelling(word: str) -> str:
    """
    Normalize spelling variants to canonical form (prefer American English).
    This ensures 'colour' and 'color' map to the same word.
    """
    word_lower = word.lower()
    # Check if it's a known variant
    if word_lower in _SPELLING_VARIANTS:
        return _SPELLING_VARIANTS[word_lower]
    # For compound words, normalize each part
    if "-" in word_lower:
        parts = word_lower.split("-")
        normalized_parts = [_SPELLING_VARIANTS.get(p, p) for p in parts]
        return "-".join(normalized_parts)
    return word_lower


def _normalize_phrase(text: str) -> str:
    """Normalize free-form text so it can be matched to KG labels."""

    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("_", " ")
    text = (
        text.replace("'", "'")
        .replace(""", '"')
        .replace(""", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace("（", "(")
        .replace("）", ")")
    )
    text = text.lower()
    text = re.sub(r"'s\b", "", text)
    text = re.sub(r"[^\w\s'/-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _generate_candidate_keys(phrase: str) -> List[str]:
    """Yield potential normalized keys (base + simple singular forms)."""

    keys = []
    base = _normalize_phrase(phrase)
    if base:
        # Normalize spelling variants
        base_normalized = _normalize_spelling(base)
        keys.append(base_normalized)
        # Also keep original if different (for backward compatibility)
        if base_normalized != base:
            keys.append(base)

    if _INFLECT and base:
        tokens = base.split()
        singular_tokens = []
        changed = False
        for tok in tokens:
            singular = _INFLECT.singular_noun(tok)
            if singular:
                singular_tokens.append(singular)
                changed = True
            else:
                singular_tokens.append(tok)
        if changed:
            singular_key = " ".join(singular_tokens).strip()
            # Normalize spelling of singular form
            singular_normalized = _normalize_spelling(singular_key)
            if singular_normalized and singular_normalized not in keys:
                keys.append(singular_normalized)
            if singular_key != singular_normalized and singular_key not in keys:
                keys.append(singular_key)

    # Also try collapsing spaces into hyphens for compound words
    if base and " " in base:
        hyphen_key = base.replace(" ", "-")
        hyphen_normalized = _normalize_spelling(hyphen_key)
        if hyphen_normalized not in keys:
            keys.append(hyphen_normalized)
        if hyphen_key != hyphen_normalized and hyphen_key not in keys:
            keys.append(hyphen_key)

    return keys


def load_word_metadata(kg_file: Path) -> Dict[str, WordMetadata]:
    """Parse the KG file and collect metadata for each English word."""

    if not kg_file.exists():
        raise FileNotFoundError(f"KG file not found: {kg_file}")

    metadata: Dict[str, WordMetadata] = {}
    current_id: str | None = None
    buffer: Dict[str, object] = {}

    def finalize() -> None:
        nonlocal current_id, buffer
        if current_id and "label" in buffer:
            metadata[current_id] = WordMetadata(
                node_id=current_id,
                label=str(buffer.get("label", current_id)),
                cefr=str(buffer.get("cefr")) if buffer.get("cefr") else None,
                concreteness=float(buffer["concreteness"])
                if "concreteness" in buffer
                else None,
                frequency_rank=int(buffer["frequency_rank"])
                if "frequency_rank" in buffer
                else None,
                age_of_acquisition=float(buffer["aoa"]) if "aoa" in buffer else None,
            )
        current_id = None
        buffer = {}

    with kg_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                finalize()
                continue

            if line.startswith("srs-kg:word-en-") and "a srs-kg:Word" in line:
                finalize()
                current_id = line.split()[0].replace("srs-kg:", "")
                buffer = {}
                continue

            if not current_id:
                continue

            if line.startswith("rdfs:label"):
                match = re.search(r"\"(.+?)\"@en", line)
                if match:
                    buffer["label"] = match.group(1)
                continue

            if line.startswith("srs-kg:cefrLevel"):
                match = re.search(r"\"(.+?)\"", line)
                if match:
                    buffer["cefr"] = match.group(1)
                continue

            if line.startswith("srs-kg:concreteness"):
                match = re.search(r"([\d\.]+)", line)
                if match:
                    buffer["concreteness"] = match.group(1)
                continue

            if line.startswith("srs-kg:frequencyRank"):
                match = re.search(r"(\d+)", line)
                if match:
                    buffer["frequency_rank"] = match.group(1)
                continue

            if line.startswith("srs-kg:ageOfAcquisition"):
                match = re.search(r"([\d\.]+)", line)
                if match:
                    buffer["aoa"] = match.group(1)
                continue

            if line.endswith("."):
                finalize()

    finalize()
    return metadata


def build_label_index(metadata: Mapping[str, WordMetadata]) -> Dict[str, str]:
    """Create lookup for normalized label -> node id."""

    index: Dict[str, str] = {}
    for meta in metadata.values():
        for key in _generate_candidate_keys(meta.label):
            if key and key not in index:
                index[key] = meta.node_id
    return index


def _map_word_to_node_id(
    phrase: str, label_index: Mapping[str, str]
) -> str | None:
    """Best-effort mapping from raw text to a KG word identifier.
    Returns normalized node ID to match canonical forms in the graph.
    """

    for key in _generate_candidate_keys(phrase):
        if key in label_index:
            node_id = label_index[key]
            # Normalize node ID to match canonical form in graph
            return _normalize_node_id(node_id) if node_id.startswith("word-en-") else node_id
    return None


def _normalize_node_id(node_id: str) -> str:
    """
    Normalize node ID by extracting word and normalizing spelling.
    'word-en-colour' -> 'word-en-color'
    Also handles combined forms like 'word-en-behaviorbehaviour' -> 'word-en-behavior'
    """
    if not node_id.startswith("word-en-"):
        return node_id
    
    word_part = node_id[8:]
    
    # Handle combined forms like "behaviorbehaviour" or "metermetre"
    # Check if word contains both British and American variants concatenated
    for brit, amer in _SPELLING_VARIANTS.items():
        if brit in word_part and amer in word_part:
            # Both variants present - use just the American (canonical) form
            word_part = amer
            break
    
    # Split on hyphens, normalize each word, rejoin
    parts = word_part.split("-")
    normalized_parts = [_normalize_spelling(p) for p in parts]
    normalized_word = "-".join(normalized_parts)
    return f"word-en-{normalized_word}"


def load_similarity_graph(
    similarity_file: Path,
    min_similarity: float,
) -> Tuple[nx.Graph, Dict[str, str]]:
    """
    Build an undirected weighted graph from the similarity JSON file.
    Merges spelling variants (e.g., 'word-en-colour' and 'word-en-color')
    into canonical nodes.

    Returns the graph plus an (optional) id->label mapping that can be used when
    printing recommendations.  When a human-readable label is unavailable the
    node id will be reused.
    """
    if not similarity_file.exists():
        raise FileNotFoundError(f"Similarity file not found: {similarity_file}")

    with similarity_file.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    similarities: Mapping[str, List[Mapping[str, float]]] = payload.get(
        "similarities", {}
    )

    graph = nx.Graph()
    labels: Dict[str, str] = {}
    # Map variant node IDs to canonical IDs
    variant_to_canonical: Dict[str, str] = {}

    for source_id, neighbours in similarities.items():
        if not neighbours:
            continue

        # Normalize source ID
        canonical_source = _normalize_node_id(source_id)
        variant_to_canonical[source_id] = canonical_source

        for neighbour in neighbours:
            target_id = neighbour.get("neighbor_id")
            weight = float(neighbour.get("similarity", 0.0))
            target_label = neighbour.get("neighbor_label")

            if not target_id or target_id == source_id:
                continue

            if weight < min_similarity:
                continue

            # Normalize target ID
            canonical_target = _normalize_node_id(target_id)
            variant_to_canonical[target_id] = canonical_target

            # Use canonical IDs for graph
            if target_label and canonical_target not in labels:
                labels[canonical_target] = target_label

            if canonical_source not in graph:
                graph.add_node(canonical_source)
            if canonical_target not in graph:
                graph.add_node(canonical_target)

            # Skip self-loops after normalization
            if canonical_source == canonical_target:
                continue

            if graph.has_edge(canonical_source, canonical_target):
                # Preserve the strongest edge if duplicates exist
                existing = graph.edges[canonical_source, canonical_target]["weight"]
                if weight > existing:
                    graph.edges[canonical_source, canonical_target]["weight"] = weight
            else:
                graph.add_edge(canonical_source, canonical_target, weight=weight)

    # Report merged variants (only cases where both forms exist in similarity file)
    variant_groups: Dict[str, List[str]] = {}
    for variant, canonical in variant_to_canonical.items():
        if variant != canonical:
            if canonical not in variant_groups:
                variant_groups[canonical] = []
            variant_groups[canonical].append(variant)
    
    if variant_groups:
        total_merged = sum(len(variants) for variants in variant_groups.values())
        print(f"🔄 Merged {total_merged} spelling variant nodes into {len(variant_groups)} canonical forms")
        # Show a few examples
        for canonical, variants in list(variant_groups.items())[:5]:
            print(f"   {canonical} <- {', '.join(variants[:3])}")
    
    # Note: All spelling variants are normalized (100+ British->American mappings)
    # including: metre->meter, neighbour->neighbor, theatre->theater, centre->center,
    # colour->color, honour->honor, mould->mold, and many more. This ensures
    # British variants in mastered words/KG correctly map to American forms in the graph.

    return graph, labels


def parse_mastered_inputs(
    mastered_words: Iterable[str],
    mastered_weighted: Iterable[str],
    mastered_json: Path | None,
) -> Dict[str, float]:
    """
    Combine mastered word IDs and optional weights into a single dictionary.

    Priority order:
      1. Entries from --mastered-json
      2. Weighted CLI entries (word:weight)
      3. Plain CLI entries (--mastered)
    """
    seeds: Dict[str, float] = {}

    if mastered_json:
        if not mastered_json.exists():
            raise FileNotFoundError(f"Mastered JSON file not found: {mastered_json}")
        with mastered_json.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, Mapping):
            for word_id, weight in data.items():
                try:
                    # Normalize node ID if it's a word-en-* ID
                    normalized_id = _normalize_node_id(str(word_id)) if str(word_id).startswith("word-en-") else str(word_id)
                    seeds[normalized_id] = seeds.get(normalized_id, 0.0) + float(weight)
                except (TypeError, ValueError):
                    continue
        elif isinstance(data, list):
            for word_id in data:
                # Normalize node ID if it's a word-en-* ID
                normalized_id = _normalize_node_id(str(word_id)) if str(word_id).startswith("word-en-") else str(word_id)
                seeds[normalized_id] = seeds.get(normalized_id, 0.0) + 1.0
        else:
            raise ValueError(
                "Mastered JSON must be either a list of word IDs or "
                "a mapping of {word_id: weight}."
            )

    for entry in mastered_weighted:
        if ":" not in entry:
            raise ValueError(
                f"Invalid weighted mastered entry '{entry}'. Expected format word-id:weight"
            )
        word_id, raw_weight = entry.split(":", 1)
        # Normalize node ID if it's a word-en-* ID
        normalized_id = _normalize_node_id(word_id) if word_id.startswith("word-en-") else word_id
        try:
            seeds[normalized_id] = seeds.get(normalized_id, 0.0) + float(raw_weight)
        except ValueError:
            raise ValueError(f"Invalid weight for '{entry}'.") from None

    for word_id in mastered_words:
        # Normalize node ID if it's a word-en-* ID
        normalized_id = _normalize_node_id(word_id) if word_id.startswith("word-en-") else word_id
        seeds[normalized_id] = seeds.get(normalized_id, 0.0) + 1.0

    return seeds


def load_mastered_word_ids_from_db(
    db_path: Path,
    profile_id: str,
    label_index: Mapping[str, str],
) -> Tuple[List[str], List[str]]:
    """Fetch mastered English words for a profile and map them to KG IDs."""

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT word FROM mastered_words WHERE profile_id = ? AND language = 'en'",
            (profile_id,),
        ).fetchall()
    finally:
        conn.close()

    matched: List[str] = []
    unmatched: List[str] = []
    for (word,) in rows:
        if not word:
            continue
        node_id = _map_word_to_node_id(word, label_index)
        if node_id:
            matched.append(node_id)
        else:
            unmatched.append(word)

    return matched, unmatched


def _extract_front_field(flds: str) -> str:
    """Return the first field (Front) from an Anki note."""

    if not flds:
        return ""
    parts = flds.split("\x1f")
    return parts[0] if parts else ""


def load_anki_seed_weights(
    collection_path: Path,
    label_index: Mapping[str, str],
) -> Tuple[Dict[str, float], List[str]]:
    """Derive seed weights from an exported Anki collection."""

    if not collection_path.exists():
        raise FileNotFoundError(f"Anki collection not found: {collection_path}")

    conn = sqlite3.connect(collection_path)
    conn.row_factory = sqlite3.Row
    try:
        note_word: Dict[int, str] = {}
        for row in conn.execute("SELECT id, flds FROM notes"):
            front = _extract_front_field(row["flds"])
            normalized = _normalize_phrase(front)
            if normalized:
                note_word[row["id"]] = normalized

        card_word: Dict[int, str] = {}
        for row in conn.execute("SELECT id, nid FROM cards"):
            word = note_word.get(row["nid"])
            if word:
                card_word[row["id"]] = word

        word_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"max_ivl": 0.0, "count": 0.0, "ease_total": 0.0}
        )
        for row in conn.execute("SELECT cid, ivl, ease FROM revlog"):
            word = card_word.get(row["cid"])
            if not word:
                continue
            stats = word_stats[word]
            ivl = max(0.0, float(row["ivl"]))
            stats["max_ivl"] = max(stats["max_ivl"], ivl)
            stats["count"] += 1.0
            stats["ease_total"] += float(row["ease"])
    finally:
        conn.close()

    weights: Dict[str, float] = {}
    unmatched: List[str] = []

    def _interval_score(max_ivl: float) -> float:
        # Normalize using a 180-day horizon (roughly 6 months)
        return min(1.0, math.log(max_ivl + 1.0) / math.log(180.0 + 1.0))

    def _review_score(count: float) -> float:
        return min(1.0, math.log(count + 1.0) / math.log(60.0 + 1.0))

    for word, stats in word_stats.items():
        node_id = _map_word_to_node_id(word, label_index)
        if not node_id:
            unmatched.append(word)
            continue

        count = stats["count"]
        if count <= 0:
            continue
        avg_ease = stats["ease_total"] / count
        interval_component = _interval_score(stats["max_ivl"])
        review_component = _review_score(count)
        ease_component = max(0.0, min(1.0, (avg_ease - 1.0) / 3.0))
        weight = max(
            0.0,
            min(1.0, 0.5 * interval_component + 0.3 * review_component + 0.2 * ease_component),
        )
        if weight <= 0:
            continue

        weights[node_id] = max(weights.get(node_id, 0.0), weight)

    return weights, unmatched


def build_personalization_vector(
    graph: nx.Graph, seed_weights: Mapping[str, float]
) -> Dict[str, float]:
    """
    Create the personalization vector (probability distribution) used by PPR.
    """
    personalization: Dict[str, float] = {}
    total_weight = 0.0

    for node_id, weight in seed_weights.items():
        if node_id not in graph or weight <= 0:
            continue
        personalization[node_id] = personalization.get(node_id, 0.0) + float(weight)
        total_weight += float(weight)

    if not personalization:
        raise ValueError(
            "None of the provided mastered words exist in the similarity graph."
        )

    if total_weight <= 0:
        uniform = 1.0 / len(personalization)
        personalization = {node_id: uniform for node_id in personalization}
    else:
        personalization = {
            node_id: weight / total_weight for node_id, weight in personalization.items()
        }

    return personalization


def run_ppr(
    graph: nx.Graph,
    personalization: Mapping[str, float],
    alpha: float,
) -> Dict[str, float]:
    """
    Execute Personalized PageRank with the given restart distribution.
    """
    scores = nx.pagerank(graph, alpha=alpha, personalization=personalization, weight="weight")
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate recommendations via Personalized PageRank over the "
        "spaCy similarity graph."
    )
    parser.add_argument(
        "--similarity-file",
        type=Path,
        default=DEFAULT_SIMILARITY_FILE,
        help="Path to english_word_similarity.json (default: %(default)s)",
    )
    parser.add_argument(
        "--kg-file",
        type=Path,
        default=DEFAULT_KG_FILE,
        help="Knowledge graph .ttl file used for label matching (default: %(default)s)",
    )
    parser.add_argument(
        "--mastered",
        nargs="*",
        default=[],
        help="List of mastered word IDs (uniform weights).",
    )
    parser.add_argument(
        "--mastered-weighted",
        nargs="*",
        default=[],
        help="Weighted mastered entries of the form word-id:weight (e.g. Anki ease factor).",
    )
    parser.add_argument(
        "--mastered-json",
        type=Path,
        default=None,
        help="Optional JSON file containing either a list of mastered IDs or "
        "a {word_id: weight} mapping.",
    )
    parser.add_argument(
        "--profile-id",
        type=str,
        default=None,
        help="Profile identifier from data/srs4autism.db for loading mastered words.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to srs4autism SQLite database (default: %(default)s)",
    )
    parser.add_argument(
        "--mastered-weight",
        type=float,
        default=1.0,
        help="Weight contribution for each mastered word pulled from the DB (default: %(default)s)",
    )
    parser.add_argument(
        "--anki-collection",
        type=Path,
        default=None,
        help="Path to collection.anki21 export for deriving review-based weights.",
    )
    parser.add_argument(
        "--mental-age",
        type=float,
        default=8.0,
        help="Learner mental age used for AoA filtering/scoring (default: %(default)s years).",
    )
    parser.add_argument(
        "--aoa-buffer",
        type=float,
        default=2.0,
        help="Extra allowance above mental age when filtering by AoA (default: %(default)s years).",
    )
    parser.add_argument(
        "--beta-ppr",
        type=float,
        default=1.0,
        help="Beta coefficient for log-transformed PPR score (default: %(default)s)",
    )
    parser.add_argument(
        "--beta-concreteness",
        type=float,
        default=0.8,
        help="Beta coefficient for z-scored concreteness (default: %(default)s)",
    )
    parser.add_argument(
        "--beta-frequency",
        type=float,
        default=0.3,
        help="Beta coefficient for log-transformed frequency (default: %(default)s)",
    )
    parser.add_argument(
        "--beta-aoa-penalty",
        type=float,
        default=2.0,
        help="Beta coefficient for AoA penalty (applied only if AoA > MentalAge) "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--beta-intercept",
        type=float,
        default=0.0,
        help="Intercept term (beta_0) in logit formula (default: %(default)s)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Teleport probability (lower = stay closer to known words). Default: 0.5",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.0,
        help="Ignore edges below this weight when building the graph. Default: 0.0 "
        "(the similarity file is already thresholded at generation time).",
    )
    parser.add_argument("--top-n", type=int, default=20, help="Number of results to show.")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="List of words (labels or node IDs) to exclude from recommendations.",
    )
    parser.add_argument(
        "--exclude-multiword",
        action="store_true",
        help="Exclude all multi-word phrases (words containing spaces or hyphens).",
    )

    args = parser.parse_args()

    word_metadata = load_word_metadata(args.kg_file)
    label_index_full = build_label_index(word_metadata)

    if (
        not args.mastered
        and not args.mastered_weighted
        and args.mastered_json is None
        and not args.profile_id
        and args.anki_collection is None
    ):
        parser.error(
            "Provide at least one seed source: CLI mastered words, mastered JSON, "
            "--profile-id, or --anki-collection."
        )

    try:
        manual_seeds = parse_mastered_inputs(
            args.mastered, args.mastered_weighted, args.mastered_json
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    seed_weights: Dict[str, float] = dict(manual_seeds)
    unmatched_mastered: List[str] = []
    unmatched_anki: List[str] = []

    if args.profile_id:
        matched_ids, unmatched = load_mastered_word_ids_from_db(
            args.db_path, args.profile_id, label_index_full
        )
        unmatched_mastered = unmatched
        for node_id in matched_ids:
            seed_weights[node_id] = seed_weights.get(node_id, 0.0) + args.mastered_weight
        print(
            f"📘 Loaded {len(matched_ids)} mastered words from profile '{args.profile_id}' "
            f"(unmatched {len(unmatched)})."
        )
    if args.anki_collection:
        anki_weights, unmatched = load_anki_seed_weights(
            args.anki_collection, label_index_full
        )
        unmatched_anki = unmatched
        for node_id, weight in anki_weights.items():
            seed_weights[node_id] = seed_weights.get(node_id, 0.0) + weight
        print(
            f"🧠 Loaded review-derived weights for {len(anki_weights)} Anki words "
            f"(unmatched {len(unmatched)})."
        )

    if not seed_weights:
        parser.error("No valid seeds available after processing all sources.")

    if unmatched_mastered:
        sample = ", ".join(unmatched_mastered[:10])
        print(
            f"⚠️  {len(unmatched_mastered)} mastered words could not be mapped to the KG "
            f"(e.g., {sample})"
        )
    if unmatched_anki:
        sample = ", ".join(unmatched_anki[:10])
        print(
            f"⚠️  {len(unmatched_anki)} Anki entries could not be mapped to the KG "
            f"(e.g., {sample})"
        )

    print(f"🌱 Using {len(seed_weights)} total seed nodes for PPR.")

    graph, labels = load_similarity_graph(args.similarity_file, args.min_similarity)

    if graph.number_of_nodes() == 0:
        parser.error(
            f"No nodes were added to the graph. Check the similarity file at {args.similarity_file}."
        )

    try:
        personalization = build_personalization_vector(graph, seed_weights)
    except ValueError as exc:
        parser.error(str(exc))

    scores = run_ppr(graph, personalization, alpha=args.alpha)

    # Calculate statistics for transformations
    all_ppr_scores = [s for s in scores.values() if s > 0]
    all_concreteness = [
        meta.concreteness
        for meta in word_metadata.values()
        if meta.concreteness is not None
    ]
    conc_mean = sum(all_concreteness) / len(all_concreteness) if all_concreteness else 3.0
    conc_std = (
        math.sqrt(
            sum((c - conc_mean) ** 2 for c in all_concreteness) / len(all_concreteness)
        )
        if len(all_concreteness) > 1
        else 1.5
    )

    def transform_ppr(raw_ppr: float) -> float:
        """
        Log-transform PPR score to handle power law distribution.
        PPR scores decay exponentially; log captures relative magnitude.
        """
        # Avoid log(0) by adding small epsilon
        return math.log10(raw_ppr + 1e-10)

    def transform_concreteness(value: float | None) -> float:
        """
        Z-score standardization of concreteness.
        Centers around mean: >mean adds to score, <mean subtracts.
        """
        if value is None:
            return 0.0  # Neutral if unknown
        return (value - conc_mean) / conc_std

    def transform_frequency(rank: int | None) -> float:
        """
        Log-transform frequency rank (negated so lower rank = higher score).
        Higher frequency (lower rank) = higher score.
        """
        if not rank or rank <= 0:
            return 0.0  # Neutral if unknown
        # Negate log so lower rank (higher frequency) gives positive score
        # Use log10, with +1 to handle rank=1
        return -math.log10(rank + 1)

    def calculate_aoa_penalty(aoa: float | None, mental_age: float | None) -> float:
        """
        One-sided penalty: only penalize if AoA > MentalAge.
        Uses ReLU-style penalty (no penalty if AoA <= MentalAge).
        """
        if aoa is None or mental_age is None:
            return 0.0
        excess = max(0.0, aoa - mental_age)
        return excess

    # Map excluded words to node IDs
    excluded_node_ids: set[str] = set()
    if args.exclude:
        for exclude_word in args.exclude:
            # First check if it's already a node ID
            if exclude_word.startswith("word-en-"):
                excluded_node_ids.add(exclude_word)
                print(f"🚫 Excluding node ID: {exclude_word}")
            else:
                # Try to map it to a node ID
                node_id = _map_word_to_node_id(exclude_word, label_index_full)
                if node_id:
                    excluded_node_ids.add(node_id)
                    print(f"🚫 Excluding: {exclude_word} -> {node_id}")
                else:
                    print(f"⚠️  Could not map excluded word to KG: {exclude_word}")

    if args.exclude_multiword:
        print("🚫 Filtering out all multi-word phrases (words with spaces or hyphens).")

    candidates: List[Tuple[str, float, float, float, float, str]] = []
    for node_id, raw_score in scores.items():
        if node_id in seed_weights:
            continue
        if node_id in excluded_node_ids:
            continue
        meta = word_metadata.get(node_id)
        if not meta:
            continue
        # Filter out multi-word phrases if requested
        if args.exclude_multiword:
            label = meta.label or labels.get(node_id, node_id)
            if " " in label or "-" in label:
                continue
        if (
            args.mental_age is not None
            and meta.age_of_acquisition is not None
            and meta.age_of_acquisition > args.mental_age + args.aoa_buffer
        ):
            continue

        # Transform features using probability-based approach
        ppr_transformed = transform_ppr(raw_score)
        conc_transformed = transform_concreteness(meta.concreteness)
        freq_transformed = transform_frequency(meta.frequency_rank)
        aoa_penalty = calculate_aoa_penalty(meta.age_of_acquisition, args.mental_age)

        # Calculate logit z-score
        z = (
            args.beta_intercept
            + args.beta_ppr * ppr_transformed
            + args.beta_concreteness * conc_transformed
            + args.beta_frequency * freq_transformed
            - args.beta_aoa_penalty * aoa_penalty
        )

        # Convert logit to probability using sigmoid
        final_score = 1.0 / (1.0 + math.exp(-z))

        label = meta.label or labels.get(node_id, node_id)
        candidates.append(
            (
                node_id,
                final_score,
                ppr_transformed,
                conc_transformed,
                freq_transformed,
                aoa_penalty,
                label,
            )
        )

    candidates.sort(key=lambda item: item[1], reverse=True)
    recommendations = candidates[: args.top_n]

    print("\n=== Personalized PageRank Recommendations ===")
    print(f"Total nodes in graph: {graph.number_of_nodes():,}")
    print(f"Total edges in graph: {graph.number_of_edges():,}")
    print(f"Seeds used: {len(personalization)} (alpha={args.alpha})\n")

    if not recommendations:
        print("No recommendations available (all candidates already mastered).")
        return

    for rank, (
        node_id,
        score,
        ppr_transformed,
        conc_transformed,
        freq_transformed,
        aoa_penalty,
        label,
    ) in enumerate(recommendations, start=1):
        print(
            f"{rank:>2}. {label} ({node_id}) — P(Recommend)={score:.6f} "
            f"[log(PPR)={ppr_transformed:.3f}, Z(Conc)={conc_transformed:.3f}, "
            f"log(Freq)={freq_transformed:.3f}, AoA_penalty={aoa_penalty:.2f}]"
        )


if __name__ == "__main__":
    main()

