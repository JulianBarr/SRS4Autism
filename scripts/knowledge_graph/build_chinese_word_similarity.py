#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build semantic similarity data for Chinese vocabulary using word embeddings.

This script mirrors the English word similarity builder but for Chinese words.
It supports multiple embedding sources:
1. spaCy Chinese models (zh_core_web_md/lg) - easiest, good for basic words
2. Tencent AI Lab Embeddings - best quality, covers modern usage
3. fastText Chinese - good backup with sub-word support

Usage:
    # Using spaCy (easiest, install: python -m spacy download zh_core_web_lg)
    python build_chinese_word_similarity.py --model spacy --spacy-model zh_core_web_lg
    
    # Using Tencent embeddings (best quality, requires download)
    python build_chinese_word_similarity.py --model tencent --tencent-file path/to/tencent_vectors.txt
    
    # Using fastText (backup option)
    python build_chinese_word_similarity.py --model fasttext --fasttext-file path/to/cc.zh.300.bin
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_cwn.ttl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "content_db" / "chinese_word_similarity.json"

SRS_KG = Namespace("http://srs4autism.com/schema/")


def load_chinese_words(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """Return list of (node_id, label) for Chinese words with HSK levels."""
    print("📚 Loading Chinese vocabulary from KG...")
    kg = Graph()
    kg.bind("srs-kg", SRS_KG)
    kg.parse(str(KG_FILE), format="turtle")

    words: List[Tuple[str, str]] = []
    for word_uri in kg.subjects(RDF.type, SRS_KG.Word):
        node_id = str(word_uri).split("/")[-1]
        hsk_levels = list(kg.objects(word_uri, SRS_KG.hskLevel))
        if not hsk_levels:
            continue

        labels = list(kg.objects(word_uri, RDFS.label))
        if not labels:
            continue

        # Prefer Chinese labels
        label_literal = None
        for lbl in labels:
            lbl_lang = getattr(lbl, "language", None)
            # Chinese labels (zh, zh-CN, or no language tag)
            if lbl_lang in ("zh", "zh-CN", None) or not lbl_lang:
                # Check if it contains Chinese characters
                label_str = str(lbl)
                if any('\u4e00' <= char <= '\u9fff' for char in label_str):
                    label_literal = lbl
                    break
        if label_literal is None:
            label_literal = labels[0]

        label = str(label_literal).strip()
        if not label:
            continue

        words.append((node_id, label))

    words.sort(key=lambda item: item[1])
    if limit:
        words = words[:limit]

    print(f"✅ Loaded {len(words)} Chinese words with HSK levels")
    return words


def load_vectors_spacy(
    word_entries: List[Tuple[str, str]],
    model_name: str = "zh_core_web_lg"
) -> Tuple[List[np.ndarray], List[str], List[str]]:
    """Load word vectors using spaCy Chinese model."""
    try:
        import spacy
    except ImportError:
        raise ImportError("spaCy not installed. Install with: pip install spacy")
    
    print(f"🧠 Loading spaCy Chinese model '{model_name}'...")
    try:
        nlp = spacy.load(model_name)
    except OSError:
        raise OSError(
            f"spaCy model '{model_name}' not found. "
            f"Download with: python -m spacy download {model_name}"
        )

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
        raise RuntimeError(
            "No vectors available for the provided words. "
            "Ensure the spaCy model has word vectors."
        )

    print(f"✅ Retained {len(vectors)} words with vectors "
          f"(dropped {len(texts) - len(vectors)})")

    # Detect and filter hash-based vectors (spaCy fallback)
    print("🔍 Detecting hash-based vectors (spaCy fallback vectors)...")
    matrix_raw = np.vstack(vectors).astype("float32")
    
    unique_vectors = {}
    hash_based_indices = set()
    
    for idx, vec in enumerate(matrix_raw):
        vec_tuple = tuple(vec)
        if vec_tuple in unique_vectors:
            hash_based_indices.add(idx)
            hash_based_indices.add(unique_vectors[vec_tuple])
        else:
            unique_vectors[vec_tuple] = idx

    if hash_based_indices:
        print(f"⚠️  Found {len(hash_based_indices)} words with hash-based vectors")
        print(f"   These will be excluded to prevent false similarity=1.0 matches")
        real_vectors = [vectors[i] for i in range(len(vectors)) if i not in hash_based_indices]
        real_filtered_node_ids = [filtered_node_ids[i] for i in range(len(filtered_node_ids)) if i not in hash_based_indices]
        real_filtered_labels = [filtered_labels[i] for i in range(len(filtered_labels)) if i not in hash_based_indices]
        vectors = real_vectors
        filtered_node_ids = real_filtered_node_ids
        filtered_labels = real_filtered_labels
        print(f"✅ Filtered to {len(vectors)} words with unique vectors")

    return vectors, filtered_node_ids, filtered_labels


def load_vectors_tencent(
    word_entries: List[Tuple[str, str]],
    tencent_file: Path
) -> Tuple[List[np.ndarray], List[str], List[str]]:
    """Load word vectors from Tencent AI Lab Embedding file."""
    print(f"🧠 Loading Tencent AI Lab embeddings from {tencent_file}...")
    
    if not tencent_file.exists():
        raise FileNotFoundError(f"Tencent embedding file not found: {tencent_file}")
    
    # Tencent format: word vector (space-separated floats)
    # First line may contain vocab_size and dimension
    word_to_vec: Dict[str, np.ndarray] = {}
    
    with tencent_file.open('r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        # Check if first line is header (vocab_size dim)
        parts = first_line.split()
        if len(parts) == 2 and parts[0].isdigit():
            vocab_size, dim = int(parts[0]), int(parts[1])
            print(f"   Vocabulary size: {vocab_size}, Dimension: {dim}")
        else:
            # First line is a word vector, rewind
            f.seek(0)
            dim = None
        
        for line_num, line in enumerate(f, start=1):
            parts = line.strip().split()
            if not parts:
                continue
            
            word = parts[0]
            try:
                vec = np.array([float(x) for x in parts[1:]], dtype=np.float32)
                if dim is None:
                    dim = len(vec)
                elif len(vec) != dim:
                    print(f"⚠️  Skipping line {line_num}: dimension mismatch")
                    continue
                word_to_vec[word] = vec
            except (ValueError, IndexError):
                print(f"⚠️  Skipping line {line_num}: invalid format")
                continue
            
            if line_num % 100000 == 0:
                print(f"   Loaded {line_num:,} vectors...")
    
    print(f"✅ Loaded {len(word_to_vec):,} word vectors from Tencent file")
    
    # Match words to vectors
    vectors = []
    filtered_node_ids = []
    filtered_labels = []
    matched = 0
    
    for node_id, label in word_entries:
        # Try exact match first
        if label in word_to_vec:
            vectors.append(word_to_vec[label])
            filtered_node_ids.append(node_id)
            filtered_labels.append(label)
            matched += 1
        else:
            # Try variations (remove spaces, try simplified/traditional)
            label_clean = label.replace(' ', '').replace('　', '')
            if label_clean in word_to_vec:
                vectors.append(word_to_vec[label_clean])
                filtered_node_ids.append(node_id)
                filtered_labels.append(label)
                matched += 1
    
    print(f"✅ Matched {matched}/{len(word_entries)} words to Tencent vectors")
    
    if not vectors:
        raise RuntimeError("No word vectors matched. Check word format in KG vs Tencent file.")
    
    return vectors, filtered_node_ids, filtered_labels


def load_vectors_fasttext(
    word_entries: List[Tuple[str, str]],
    fasttext_file: Path
) -> Tuple[List[np.ndarray], List[str], List[str]]:
    """Load word vectors using fastText Chinese model."""
    try:
        import fasttext
    except ImportError:
        raise ImportError("fasttext not installed. Install with: pip install fasttext")
    
    print(f"🧠 Loading fastText model from {fasttext_file}...")
    if not fasttext_file.exists():
        raise FileNotFoundError(f"fastText model not found: {fasttext_file}")
    
    model = fasttext.load_model(str(fasttext_file))
    print(f"   Model dimension: {model.get_dimension()}")
    
    texts = [label for _, label in word_entries]
    node_ids = [node_id for node_id, _ in word_entries]
    
    print(f"🔎 Computing vectors for {len(texts)} words...")
    vectors = []
    filtered_node_ids = []
    filtered_labels = []
    
    for node_id, label in zip(node_ids, texts):
        # fastText can handle sub-words, so it's more robust
        vec = model.get_word_vector(label)
        if np.linalg.norm(vec) > 0:
            vectors.append(vec)
            filtered_node_ids.append(node_id)
            filtered_labels.append(label)
    
    if not vectors:
        raise RuntimeError("No vectors available from fastText model.")
    
    print(f"✅ Retained {len(vectors)} words with vectors "
          f"(dropped {len(texts) - len(vectors)})")
    
    return vectors, filtered_node_ids, filtered_labels


def build_similarity(
    vectors: List[np.ndarray],
    node_ids: List[str],
    labels: List[str],
    top_k: int,
    threshold: float,
) -> Dict[str, List[Dict[str, float]]]:
    """Compute top-k cosine similarity neighbours for each word."""
    similarity_map: Dict[str, List[Dict[str, float]]] = {}
    
    # Normalize vectors for cosine similarity
    matrix = np.vstack(vectors).astype("float32")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # Avoid division by zero
    matrix = matrix / norms

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
                "neighbor_id": node_ids[neighbour_idx],
                "neighbor_label": labels[neighbour_idx],
                "similarity": round(sim, 4),
            })

        similarity_map[node_ids[idx]] = neighbours

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
    """Save similarity data to JSON file."""
    payload = {
        "model": model,
        "threshold": threshold,
        "top_k": top_k,
        "word_count": len(similarity_map),
        "similarities": similarity_map,
    }

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"💾 Saved similarity data to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Build semantic similarity data for Chinese words using word embeddings")
    parser.add_argument(
        "--model",
        choices=["spacy", "tencent", "fasttext"],
        default="spacy",
        help="Embedding model type (default: spacy)"
    )
    parser.add_argument(
        "--spacy-model",
        default="zh_core_web_lg",
        help="spaCy model name (default: zh_core_web_lg). "
             "Download with: python -m spacy download zh_core_web_lg"
    )
    parser.add_argument(
        "--tencent-file",
        type=Path,
        help="Path to Tencent AI Lab embedding file (text format)"
    )
    parser.add_argument(
        "--fasttext-file",
        type=Path,
        help="Path to fastText model file (.bin)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.65,
        help="Minimum cosine similarity to keep an edge (default: 0.65)"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of neighbours to keep per word (default: 10)"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=None,
        help="Optional cap on number of words to process"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Output JSON path (default: data/content_db/chinese_word_similarity.json)"
    )

    args = parser.parse_args()

    # Load Chinese words from KG
    words = load_chinese_words(limit=args.max_words)
    if not words:
        print("❌ No Chinese words found in knowledge graph")
        return

    # Load vectors based on model type
    if args.model == "spacy":
        vectors, node_ids, labels = load_vectors_spacy(words, args.spacy_model)
        model_name = f"spacy_{args.spacy_model}"
    elif args.model == "tencent":
        if not args.tencent_file:
            parser.error("--tencent-file is required when using --model tencent")
        vectors, node_ids, labels = load_vectors_tencent(words, args.tencent_file)
        model_name = f"tencent_{args.tencent_file.stem}"
    elif args.model == "fasttext":
        if not args.fasttext_file:
            parser.error("--fasttext-file is required when using --model fasttext")
        vectors, node_ids, labels = load_vectors_fasttext(words, args.fasttext_file)
        model_name = f"fasttext_{args.fasttext_file.stem}"
    else:
        parser.error(f"Unknown model type: {args.model}")

    # Build similarity graph
    similarity_map = build_similarity(
        vectors,
        node_ids,
        labels,
        top_k=args.top_k,
        threshold=args.threshold,
    )

    # Save results
    save_similarity(
        similarity_map,
        model_name,
        args.threshold,
        args.top_k,
        args.output,
    )

    print(f"\n✅ Chinese word similarity graph built successfully!")
    print(f"   Words processed: {len(words)}")
    print(f"   Words with vectors: {len(vectors)}")
    print(f"   Similarity edges: {sum(len(neighbors) for neighbors in similarity_map.values())}")
    print(f"   Output file: {args.output}")


if __name__ == "__main__":
    main()


