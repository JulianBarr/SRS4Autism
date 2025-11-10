# Chinese Knowledge Graph Generator

This directory contains scripts to generate a Chinese language knowledge graph conforming to the SRS4Autism ontology schema.

## Scripts

### 1. `populate_chinese_kg.py` (Basic Vocabulary)

Generates a knowledge graph from CSV vocabulary data (`basic_words.csv`).

## Overview

The knowledge graph serves as the "World Model" - a general, non-personalized representation of Chinese language knowledge including:

- **Characters** (汉字): Individual Chinese characters with glyphs and definitions
- **Words** (词): Multi-character words with pinyin, definitions, and character composition
- **Concepts**: Language-agnostic concept hubs based on English translations

## Structure

The generated knowledge graph contains:

- **14,688 triples** representing relationships between:
  - Words and their component characters (`composedOf`)
  - Words and their prerequisite characters (`requiresPrerequisite`)
  - Words and their semantic concepts (`means`)
  - Characters with their glyphs, pinyin, and definitions
  - Concepts based on English translations

## Files

- `populate_chinese_kg.py`: Main script to generate the knowledge graph
- `requirements.txt`: Python dependencies (rdflib)
- `../ontology/srs_schema.ttl`: The ontology schema file
- `../../knowledge_graph/world_model.ttl`: **Output file** - the generated knowledge graph

## Usage

### Prerequisites

Install dependencies:
```bash
cd scripts/knowledge_graph
pip install -r requirements.txt
```

Or from project root:
```bash
source venv/bin/activate
pip install rdflib
```

### Run the Generator

From project root:
```bash
source venv/bin/activate
python scripts/knowledge_graph/populate_chinese_kg.py
```

#### 2. `populate_from_cwn.py` (CwnGraph Integration) ⭐ **RECOMMENDED**

Generates a comprehensive knowledge graph from CwnGraph (Chinese WordNet), creating a much more complete world model with semantic relationships.

**Source:** CwnGraph pickle file (`cwn-graph-v.2022.04.22.pyobj`)

**Usage:**
```bash
cd /Users/maxent/src/SRS4Autism
source venv/bin/activate
python scripts/knowledge_graph/populate_from_cwn.py
```

**Output:** `knowledge_graph/world_model_cwn.ttl`

**Statistics (example run):**
- 5,290 characters
- 27,077 words (lemmas)
- 29,431 senses (word meanings → concepts)
- 19,912 synsets (concept groups)
- 72,754 semantic relations
- ~23.5 MB output file

**Enhanced Features (with HSK integration):**
- ✅ **Traditional to Simplified conversion** - Automatically converts Traditional Chinese from CwnGraph
- ✅ **Bopomofo to Pinyin conversion** - Converts Zhuyin (注音) to Hanyu Pinyin
- ✅ **HSK level annotation** - Adds HSK 1-6 level information for vocabulary
- ✅ **Dual character set support** - Stores both simplified and traditional forms
- ✅ **Semantic relationships** (synonym, antonym, hypernym, hyponym)
- ✅ **Multiple word senses** mapped to concepts
- ✅ **Synset groupings** for related concepts
- ✅ **Prerequisite relationships** based on hypernymy

**Dependencies:**
```bash
pip install rdflib chinese-converter dragonmapper requests
```

**HSK Vocabulary CSV Generation:**

Before running `populate_from_cwn.py`, you need to generate the HSK vocabulary CSV file. If you have the `complete-hsk-vocabulary` project available:

```bash
python scripts/knowledge_graph/generate_hsk_csv.py
```

This script:
- Reads from `/Users/maxent/src/complete-hsk-vocabulary/complete.json`
- Extracts simplified, traditional, pinyin, and HSK level (1-7)
- Generates `data/content_db/hsk_vocabulary.csv` with ~11,470 words

**Alternative:** Use `download_hsk.py` to download HSK data from online sources, or manually create the CSV.

See `HSK_INTEGRATION.md` for detailed setup instructions.

## Output (Basic Vocabulary)

The `populate_chinese_kg.py` script generates `knowledge_graph/world_model.ttl` containing:

- **732 words** from `basic_words.csv`
- **760 unique characters** extracted from the words
- **725 concepts** based on English translations
- Full ontology schema (classes and properties)
- All relationships between entities

## Example Queries

You can query the knowledge graph using rdflib in Python:

```python
from rdflib import Graph, Namespace

# Load the knowledge graph
graph = Graph()
graph.parse("knowledge_graph/world_model.ttl", format="turtle")

SRS_KG = Namespace("http://srs4autism.com/schema/")

# Find all words that mean a concept
for word, _, concept in graph.triples((None, SRS_KG.means, None)):
    word_label = graph.value(word, RDFS.label)
    concept_label = graph.value(concept, RDFS.label)
    print(f"{word_label} -> {concept_label}")

# Find characters that compose a word
word_uri = SRS_KG["word-pengyou"]
for char in graph.objects(word_uri, SRS_KG.composedOf):
    char_label = graph.value(char, RDFS.label)
    print(f"Character: {char_label}")
```

## Next Steps

This "World Model" can be used as a foundation for:

1. **Learning Frontier Algorithm**: Find concepts where prerequisites are mastered but the concept itself is not
2. **Recommendation Engine**: Suggest next words to learn based on known characters
3. **Content Generation**: Constrain LLM prompts to use only mastered vocabulary
4. **Knowledge Tracing**: Track which KPs (Knowledge Points) a child has mastered

## Data Sources

- `data/content_db/basic_words.csv`: 732 Chinese-English word pairs
- Future: Can be extended with Chinese WordNet, HSK word lists, or other linguistic corpora

