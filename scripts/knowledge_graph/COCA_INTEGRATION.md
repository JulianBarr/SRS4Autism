# COCA 20000 Integration Guide

This guide explains how to integrate COCA 20000 (Corpus of Contemporary American English) word list into the English knowledge graph to fill gaps from CEFR-J vocabulary.

## Why COCA 20000?

COCA 20000 provides a **frequency-based** list of the 20,000 most common English words based on the Corpus of Contemporary American English. This complements CEFR-J vocabulary by:

1. **Filling gaps**: Many words in your Anki cards (e.g., "theater", "restroom", "socket") are not in CEFR-J but are in COCA 20000
2. **Frequency ranking**: Provides word frequency data that can help estimate CEFR levels
3. **Comprehensive coverage**: Includes common words used in daily American English

## Getting COCA 20000 Data

### Option 1: Download from WordFrequency.info

1. Visit: https://www.wordfrequency.info/sample.asp
2. Download the full 20,000 word list (CSV format)
3. Save as: `data/content_db/coca_20000.csv`

### Option 2: Use Existing Data

If you already have COCA 20000 data, ensure it's in CSV format with columns:
- `word` or `Word` or `lemma`: The English word
- `rank` or `Rank` or `#`: Frequency rank (1-20000)
- `frequency` or `Frequency` or `freq`: Frequency count
- `pos` or `POS` or `part_of_speech`: Part of speech (optional)

### CSV Format Example

```csv
word,rank,frequency,pos
the,1,56271872,det
be,2,28636776,v
and,3,26877386,conj
of,4,26021939,prep
a,5,21306062,det
...
```

## Integration Steps

### 1. Place COCA CSV File

Place the COCA 20000 CSV file at:
```
data/content_db/coca_20000.csv
```

Or use a custom path:
```bash
python scripts/knowledge_graph/integrate_coca_20000.py --coca-file path/to/coca_20000.csv
```

### 2. Run Integration Script

**Merge with existing KG** (recommended):
```bash
cd /Users/maxent/src/SRS4Autism
source venv/bin/activate
python scripts/knowledge_graph/integrate_coca_20000.py --merge
```

**Create new KG** (if you want to start fresh):
```bash
python scripts/knowledge_graph/integrate_coca_20000.py --output knowledge_graph/world_model_english_coca.ttl
```

### 3. Review Results

The script will:
- ✅ Load COCA words
- ✅ Skip words already in KG (from CEFR-J)
- ✅ Add new words with estimated CEFR levels
- ✅ Link words to concepts
- ✅ Save updated KG

Example output:
```
✅ Loaded 20000 words from COCA
✅ Added: 12500
   Updated: 500
   Skipped (already exists): 7000
```

### 4. Re-run _KG_Map Population

After integrating COCA, re-run the bulk population script to map more cards:

```bash
python scripts/knowledge_graph/populate_english_kg_map_bulk.py
```

This should significantly reduce the number of skipped words!

## CEFR Level Estimation

The script estimates CEFR levels based on COCA rank:

| COCA Rank | Estimated CEFR Level |
|-----------|---------------------|
| 1-1,000   | A2 (most frequent)  |
| 1,001-5,000 | B1 (common)      |
| 5,001-10,000 | B2 (moderate)   |
| 10,001-20,000 | C1 (less frequent) |
| >20,000   | C2 (advanced)       |

**Note**: These are rough estimates. Words with existing CEFR-J levels will keep their original levels (CEFR-J takes precedence).

## Integration Strategy

The script uses a **merge strategy**:

1. **CEFR-J words take precedence**: If a word exists in both CEFR-J and COCA, keep the CEFR-J data (including CEFR level)
2. **COCA fills gaps**: Add words from COCA that are not in CEFR-J
3. **Estimate CEFR levels**: For COCA-only words, estimate CEFR level from frequency rank

## Expected Results

After integrating COCA 20000:

- **Before**: 778 skipped words (out of 1,856 notes)
- **After**: Expected ~200-400 skipped words (mostly multi-word phrases)

The remaining skipped words will likely be:
- Multi-word phrases/phrasal verbs (e.g., "work out", "look up")
- Domain-specific terms
- Proper nouns

## Troubleshooting

### File Not Found

If you get "COCA file not found":
1. Check the file path: `data/content_db/coca_20000.csv`
2. Or use `--coca-file` to specify custom path

### CSV Format Issues

If words aren't loading correctly:
1. Check CSV has header row
2. Ensure columns are named: `word`, `rank`, `frequency` (or variants)
3. Check encoding is UTF-8

### Merge Issues

If merge fails:
1. Backup your existing KG first: `cp knowledge_graph/world_model_english.ttl knowledge_graph/world_model_english.ttl.backup`
2. Check KG file is valid Turtle format
3. Try without `--merge` to create new file

## Next Steps

After integrating COCA 20000:

1. ✅ **Re-populate _KG_Map**: Run `populate_english_kg_map_bulk.py` again
2. ✅ **Enrich with Wikidata**: Run `enrich_english_with_wikidata.py` for semantic linking
3. ✅ **Add visual images**: Link images from Anki packages if available
4. ✅ **Review remaining gaps**: Check `english_kg_map_not_found.json` for patterns

## References

- **COCA (Corpus of Contemporary American English)**: https://www.english-corpora.org/coca/
- **WordFrequency.info**: https://www.wordfrequency.info/
- **COCA Word Lists**: https://www.wordfrequency.info/sample.asp

