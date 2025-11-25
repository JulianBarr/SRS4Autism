# English Vocabulary Recommender Experiment

This document describes the implementation of a spreading activation recommender system for English vocabulary, based on the "Integrated Approach" described in `An integrated approach for recommender system of language learning.md`.

## Overview

The experiment implements a **spreading activation algorithm** on a heterogeneous knowledge graph to recommend the next best English words to learn. It integrates:

1. **Anki data** - Mastery scores from `_KG_Map` field
2. **Knowledge Graph** - Word → Concept relationships
3. **Semantic similarity** - spaCy word embeddings for word-to-word connections
4. **Anki tags** - Topic-based clustering

## Addressing the Word Family Concern

**Question:** Do we have word family relations in our KG? If not, do we have enough information to propagate among English words?

**Answer:** We do **not** have explicit word family relationships (e.g., `run → running → runner`) in the KG. However, we can still create meaningful connections using:

### 1. Concept Hubs (Primary Method)
Words that share the same concept are connected through a concept hub node:
- `word-en-dog` → `CONCEPT:dog` ← `word-en-puppy`
- This allows activation to flow between semantically related words

### 2. Semantic Similarity (spaCy)
If spaCy is available, we create edges between words with similarity > 0.7:
- Uses pre-trained word embeddings (`en_core_web_md`)
- Automatically connects semantically similar words
- Example: "dog" and "puppy" will have high similarity

### 3. Tag-Based Clustering
Words with shared Anki tags are connected:
- Words tagged with `Biology` form a cluster
- Words tagged with `Food` form another cluster
- This creates topic-based relationships

### 4. Future: Word Family Integration
To add word family relationships, we could:
- Use a morphological analyzer (e.g., `nltk.stem.WordNetLemmatizer`)
- Extract word families from WordNet
- Add `srs-kg:hasWordFamily` property to the ontology
- Populate relationships during KG construction

## Algorithm

### Step 1: Build Graph
- **Nodes:** Word nodes, Concept hub nodes, Tag nodes
- **Edges:** 
  - Word → Concept (via `means` relationship)
  - Word ↔ Word (via semantic similarity)
  - Word → Tag (via Anki tags)

### Step 2: Calculate Resistance
For each word, calculate a "resistance" score (higher = harder to learn):
```
R = 0.4 * (1/Frequency) + 0.4 * (5 - Concreteness) + 0.2 * CEFR_Level
```

### Step 3: Initialize Activation
Set initial activation from Anki mastery scores:
- Mastery calculated from card intervals and lapses
- Normalized to 0.0-1.0 scale

### Step 4: Spreading Activation
Propagate energy through the graph:
```
For each iteration:
  For each activated node:
    Push energy to neighbors: activation * edge_weight * decay_factor
```

### Step 5: Generate Recommendations
Score each candidate word:
```
Score = Activation / (Resistance + ε)
```

## Usage

```bash
# Basic usage
python scripts/knowledge_graph/english_recommender_experiment.py

# Show top 50 recommendations
python scripts/knowledge_graph/english_recommender_experiment.py --top-n 50
```

## Requirements

```bash
pip install networkx rdflib requests

# Optional (for semantic similarity)
python -m spacy download en_core_web_md
```

## Output

The script prints:
1. **Top N recommendations** with scores, activation, resistance, and reasoning
2. **Summary statistics**:
   - Total words in graph
   - Words with mastery scores
   - Graph structure (nodes, edges, hubs)

## Example Output

```
TOP 20 RECOMMENDATIONS
================================================================================
WORD                      SCORE      ACT      RES      REASON
--------------------------------------------------------------------------------
 1. puppy                  0.3421     0.45     2.10   high activation, low resistance, shares concept with 1 word(s)
 2. cat                    0.2987     0.38     2.15   high activation, low resistance
 3. animal                 0.2456     0.32     2.30   high activation, shares concept with 2 word(s)
...
```

## Limitations & Future Work

1. **No Word Families:** As noted, we don't have explicit word family relationships. This could be added using WordNet or morphological analysis.

2. **Frequency Data:** Currently uses default frequency values if not in KG. Could integrate SUBTLEX-US or COCA frequency data.

3. **Concreteness Data:** Uses default values if not in KG. Could integrate Brysbaert Concreteness Ratings.

4. **Graph Density:** Without word families, the graph may be sparse. Semantic similarity helps, but explicit relationships would be better.

5. **Cross-Lingual:** This experiment focuses on English only. The full system should support cross-lingual propagation (English → Concept → Chinese).

## Testing

To test if the recommendations are useful:
1. Check if recommended words are semantically related to mastered words
2. Verify that low-resistance (easy) words are ranked higher
3. Confirm that words sharing concepts with mastered words appear in recommendations
4. Validate that recommendations are in the "i+1" zone (not too easy, not too hard)

