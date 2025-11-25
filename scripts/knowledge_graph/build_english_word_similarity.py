#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build semantic similarity data for English vocabulary using spaCy vectors.

This script follows the approach outlined in
`Propagation based recommendation.md` to add semantic edges between English
words. It loads English words (those with CEFR levels) from the English
knowledge graph, computes spaCy vector similarity, and stores the top
neighbours per word in a JSON file for use by the recommender.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import spacy
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_english.ttl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"

SRS_KG = Namespace("http://srs4autism.com/schema/")


def load_english_words(limit: int | None = None) -> List[Tuple[str, str]]:
    """Return list of (node_id, label) for English words with CEFR levels."""
    print("📚 Loading English vocabulary from KG...")
    kg = Graph()
    kg.bind("srs-kg", SRS_KG)
    kg.parse(str(KG_FILE), format="turtle")

    words: List[Tuple[str, str]] = []
    for word_uri in kg.subjects(RDF.type, SRS_KG.Word):
        node_id = str(word_uri).split("/")[-1]
        cefr_levels = list(kg.objects(word_uri, SRS_KG.cefrLevel))
        if not cefr_levels:
            continue

        labels = list(kg.objects(word_uri, RDFS.label))
        if not labels:
            continue

        # Prefer English labels
        label_literal = None
        for lbl in labels:
            if getattr(lbl, "language", None) == "en":
                label_literal = lbl
                break
        if label_literal is None:
            label_literal = labels[0]

        label = str(label_literal).strip()
        if not label:
            continue

        words.append((node_id, label))

    words.sort(key=lambda item: item[1].lower())
    if limit:
        words = words[:limit]

    print(f"✅ Loaded {len(words)} English words with CEFR levels")
    return words


def build_similarity(
    word_entries: List[Tuple[str, str]],
    model: str,
    top_k: int,
    threshold: float,
) -> Dict[str, List[Dict[str, float]]]:
    """Compute top-k cosine similarity neighbours for each word."""
    print(f"🧠 Loading spaCy model '{model}'...")
    nlp = spacy.load(model)

    texts = [label for _, label in word_entries]
    node_ids = [node_id for node_id, _ in word_entries]

    print(f"🔎 Computing vectors for {len(texts)} words...")
    docs = list(nlp.pipe(texts, batch_size=128))
    vectors = []
    filtered_node_ids = []
    filtered_labels = []

    for node_id, label, doc in zip(node_ids, texts, docs):
        if not doc.vector_norm or math.isclose(doc.vector_norm, 0.0):
            continue
        vectors.append(doc.vector)
        filtered_node_ids.append(node_id)
        filtered_labels.append(label)

    if not vectors:
        raise RuntimeError("No vectors available for the provided words. "
                           "Ensure the spaCy model has word vectors.")

    print(f"✅ Retained {len(vectors)} words with vectors "
          f"(dropped {len(texts) - len(vectors)})")

    matrix = np.vstack(vectors).astype("float32")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / (norms + 1e-8)

    similarity_map: Dict[str, List[Dict[str, float]]] = {}

    print("🕸️  Computing pairwise similarities...")
    for idx in range(matrix.shape[0]):
        sims = matrix @ matrix[idx]
        sims[idx] = -1.0  # Exclude self

        # Get top-k neighbours
        if top_k < len(sims):
            top_indices = np.argpartition(sims, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]
        else:
            top_indices = np.argsort(sims)[::-1]

        neighbours = []
        for neighbour_idx in top_indices:
            sim = float(sims[neighbour_idx])
            if sim < threshold:
                continue
            neighbours.append({
                "neighbor_id": filtered_node_ids[neighbour_idx],
                "neighbor_label": filtered_labels[neighbour_idx],
                "similarity": round(sim, 4),
            })

        similarity_map[filtered_node_ids[idx]] = neighbours

        if (idx + 1) % 500 == 0:
            print(f"   Processed {idx + 1}/{matrix.shape[0]} words...")

    print("✅ Similarity computation complete")
    return similarity_map


def save_similarity(
    similarity_map: Dict[str, List[Dict[str, float]]],
    model: str,
    threshold: float,
    top_k: int,
    output_path: Path,
) -> None:
    """Persist similarity map to JSON with metadata."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "generated_at": int(time.time()),
            "model": model,
            "threshold": threshold,
            "top_k": top_k,
            "word_count": len(similarity_map),
        },
        "similarities": similarity_map,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved similarity data to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Build spaCy-based semantic similarity data for English words")
    parser.add_argument("--model", default="en_core_web_md",
                        help="spaCy model name (default: en_core_web_md)")
    parser.add_argument("--threshold", type=float, default=0.65,
                        help="Minimum cosine similarity to keep an edge")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of neighbours to keep per word")
    parser.add_argument("--max-words", type=int, default=None,
                        help="Optional cap on number of words to process")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE,
                        help="Output JSON path")

    args = parser.parse_args()

    words = load_english_words(limit=args.max_words)
    similarity_map = build_similarity(
        words,
        model=args.model,
        top_k=args.top_k,
        threshold=args.threshold,
    )
    save_similarity(similarity_map, args.model, args.threshold,
                    args.top_k, args.output)


if __name__ == "__main__":
    main()

