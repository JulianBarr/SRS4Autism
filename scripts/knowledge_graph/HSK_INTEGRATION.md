# HSK Vocabulary Integration Guide

This document explains how to integrate HSK (Hanyu Shuiping Kaoshi) vocabulary data into the knowledge graph.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd /Users/maxent/src/SRS4Autism
   source venv/bin/activate
   pip install -r scripts/knowledge_graph/requirements.txt
   ```

2. **Download HSK vocabulary:**
   - Option A: Run the download script (may not work if sources are unavailable)
     ```bash
     python scripts/knowledge_graph/download_hsk.py
     ```
   - Option B: Manually download from:
     - https://github.com/kaisersparpick/HSK-Vocabulary-List
     - https://github.com/duguyue/hsk
     - Save as `data/content_db/hsk_vocabulary.csv`

3. **Expected CSV Format:**
   ```csv
   word,traditional,pinyin,hsk_level
   朋友,朋友,péngyou,1
   学习,學習,xuéxí,1
   老师,老師,lǎoshī,2
   ```

   Column variations supported:
   - `word` or `simplified` or `chinese` → simplified Chinese word
   - `traditional` or `traditional_chinese` → traditional Chinese word
   - `pinyin` or `hanyu_pinyin` → pinyin pronunciation
   - `hsk_level` or `hsk` or `level` → HSK level (1-6)

4. **Run the enhanced knowledge graph generator:**
   ```bash
   python scripts/knowledge_graph/populate_from_cwn.py
   ```

## Features Added

### 1. Traditional to Simplified Conversion
- Uses `chinese-converter` library
- Automatically converts Traditional Chinese from CwnGraph to Simplified Chinese
- Stores both forms when they differ

### 2. Bopomofo to Pinyin Conversion
- Uses `dragonmapper` library
- Converts Bopomofo (Zhuyin, 注音) from CwnGraph to Hanyu Pinyin
- Falls back to CwnGraph pinyin if conversion fails or if already in pinyin

### 3. HSK Level Integration
- Matches words from CwnGraph with HSK vocabulary list
- Adds `hskLevel` property to word nodes
- Enables queries like "Find all HSK Level 3 words"

### 4. Enhanced Metadata
- Each word node now includes:
  - Simplified Chinese (primary text)
  - Traditional Chinese (if different)
  - Pinyin (converted from bopomofo or from HSK)
  - HSK level (if available)

## Output

The enhanced script generates `knowledge_graph/world_model_cwn.ttl` with:
- All CwnGraph data (27,000+ words, semantic relationships)
- Simplified Chinese conversion
- Pinyin conversion
- HSK level annotations

## Query Examples

```python
from rdflib import Graph, Namespace, RDFS
from rdflib.namespace import RDF

# Load the knowledge graph
graph = Graph()
graph.parse("knowledge_graph/world_model_cwn.ttl", format="turtle")

SRS_KG = Namespace("http://srs4autism.com/schema/")

# Find all HSK Level 1 words
for word, _, level in graph.triples((None, SRS_KG.hskLevel, None)):
    if int(level) == 1:
        word_label = graph.value(word, RDFS.label)
        print(f"HSK 1: {word_label}")

# Find words with traditional forms
for word, _, traditional in graph.triples((None, SRS_KG.traditional, None)):
    simplified = graph.value(word, SRS_KG.text)
    print(f"{simplified} (Traditional: {traditional})")
```

## Troubleshooting

### Conversion Libraries Not Working
If `chinese-converter` or `dragonmapper` fail to install or work:
- The script will continue without conversion
- Words will be stored as-is from CwnGraph
- You can manually fix conversions later

### HSK Data Not Found
If HSK CSV is missing:
- The script will continue without HSK levels
- Words will still be processed from CwnGraph
- You can add HSK data later and re-run the script

### Traditional Property Not in Schema
The script tries to add `srs-kg:traditional` property. If it doesn't exist in your ontology:
- It will fallback to storing in `rdfs:comment`
- You can add the property to `srs_schema.ttl`:
  ```turtle
  srs-kg:traditional a rdf:Property ;
      rdfs:domain srs-kg:Word ;
      rdfs:range rdfs:Literal .
  ```

