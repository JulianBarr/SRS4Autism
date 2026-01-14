# Knowledge Graph Generator V2 Usage Guide

## Quick Start

### Test with Sample (Recommended First)
```bash
# Generate graph with first 50 HSK words
python scripts/build_core_v2.py --sample 50
```

### Generate Full HSK Vocabulary
```bash
# All HSK levels (1-6)
python scripts/build_core_v2.py

# Specific HSK levels
python scripts/build_core_v2.py --hsk-levels 1 2 3

# HSK 1 only
python scripts/build_core_v2.py --hsk-levels 1
```

### Include English Vocabulary (Logic City)
```bash
# Add first 500 English words
python scripts/build_core_v2.py --english --english-limit 500

# Add all English words
python scripts/build_core_v2.py --english
```

### Advanced Options
```bash
# Slower rate limit (more polite to Wikidata)
python scripts/build_core_v2.py --rate-limit 1.0

# Custom output path
python scripts/build_core_v2.py --output my_graph.ttl

# Save cache more frequently
python scripts/build_core_v2.py --save-every 50
```

## How It Works

1. **Loads Vocabulary**: Reads HSK words from `data/content_db/hsk_csv/` or `data/content_db/hsk_vocabulary.csv`
2. **Fetches Q-IDs**: Queries Wikidata API for concept Q-IDs (with caching)
3. **Generates Graph**: Creates RDF triples following `knowledge_graph/ontology.ttl`
4. **Validates**: Checks URI safety, labels, and Wikidata links

## Q-ID Cache

- Cached Q-IDs saved to: `data/content_db/wikidata_qid_cache.json`
- Reused across runs to avoid repeated API calls
- Speeds up subsequent generations significantly

## Rate Limiting

- Default: 0.5s between Wikidata API calls
- Prevents rate limiting by Wikidata
- Adjust with `--rate-limit` if needed

## Expected Output

### Small Sample (50 words)
- File size: ~50 KB
- Generation time: ~1-2 minutes

### Full HSK (11,000+ words)
- File size: ~10-15 MB
- Generation time: ~2-3 hours (with API lookups)
- Subsequent runs: ~30 minutes (with cache)

### With English (500 words)
- File size: ~12-18 MB
- Additional time: ~30-45 minutes

## Troubleshooting

### "No English gloss available"
- Some HSK words may not have English translations in the CSV
- These will be skipped
- Check `data/content_db/hsk_csv/hsk*.csv` for format

### "Wikidata API error"
- Network issue or rate limiting
- Script will continue with next word
- Q-IDs are cached, so restart will skip already-fetched items

### "pypinyin not installed"
- Install with: `pip install pypinyin`
- Required for generating pinyin from Chinese text

### Incorrect Wikidata Q-IDs
- **Known Issue**: Wikidata's search API sometimes returns pop culture results instead of core concepts
  - Example: "tea" → Q15885810 (female name) instead of Q6097 (tea beverage)
  - Example: "love" → Q58624685 (Bee Gees song) instead of Q316 (love emotion)
- **Workaround**: The script caches all Q-IDs in `data/content_db/wikidata_qid_cache.json`
  - You can manually review and correct critical Q-IDs in this file
  - Re-run the generator with corrected cache for improved results
- **Why this happens**: Wikidata's simple text search prioritizes popular entities over conceptual ones
- **Future improvement**: Use SPARQL queries or entity type filtering (slower but more accurate)

## Example Output
```
======================================================================
KNOWLEDGE GRAPH GENERATOR V2 - ONTOLOGY-DRIVEN
======================================================================

Processing 1147 HSK vocabulary items...

[1/1147] Processing: 爱 (ài) [HSK1]
  ✓ Found Q-ID: Q316 ('love' - emotion or virtue)
  ✓ Created concept: http://srs4autism.com/instance/concept_Q316
  ✓ Created Chinese word: http://srs4autism.com/instance/word_zh_ai

[2/1147] Processing: 八 (bā) [HSK1]
  ✓ Found Q-ID: Q23632 ('eight' - natural number)
  ✓ Created concept: http://srs4autism.com/instance/concept_Q23632
  ✓ Created Chinese word: http://srs4autism.com/instance/word_zh_ba

...

✅ Generation complete!
   Total triples: 15234
   Concepts created: 1054
   HSK words processed: 1147/1147
   Skipped: 0
```
