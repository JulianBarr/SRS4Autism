# Wikidata Q-ID Status

## Current Situation

**Problem:** Concepts are created **without** Wikidata Q-IDs during initial population.

- **Total concepts:** 67,320
- **Concepts with Q-ID:** 1 (0.001%)
- **Concepts without Q-ID:** 67,319 (99.999%)

## Why This Happened

1. **Initial Population** (`populate_from_cwn.py`):
   - Creates Concept nodes from CwnGraph senses
   - Does **NOT** add Wikidata Q-IDs
   - Concepts are just placeholders

2. **Enrichment Step** (`enrich_with_wikidata.py`):
   - This script is supposed to add Q-IDs
   - **Has NOT been run** (or only partially)
   - This is why only 1 concept has a Q-ID

## How Concepts Are Created

### From CwnGraph (`populate_from_cwn.py`):
```python
# Creates concept from sense
concept_uri = SRS_KG[f"concept-{concept_slug}"]
graph.add((concept_uri, RDF.type, SRS_KG.Concept))
graph.add((concept_uri, RDFS.label, Literal(f"concept:{label}", lang="zh")))
# NO wikidataId added here!
```

### Enrichment (`enrich_with_wikidata.py`):
```python
# Adds Q-ID later
graph.add((concept_uri, SRS_KG.wikidataId, Literal(qid)))
graph.add((concept_uri, OWL.sameAs, wikidata_uri))
```

## Solution

Run the enrichment script to add Q-IDs:

```bash
python scripts/knowledge_graph/enrich_with_wikidata.py
```

**Note:** This is a **long-running process**:
- 9,405 Chinese words to process
- Wikidata API rate limits (500ms delay between requests)
- Estimated time: Several hours

**Options:**
1. Run full enrichment (recommended, but slow)
2. Run with `--sample N` to test on a subset first
3. Use checkpoint system (script supports resuming)

## Impact on AoA Propagation

The `link_english_via_cedict.py` script requires concepts to have Q-IDs:
- It only links English words to concepts **with Q-IDs**
- Without Q-IDs, English-Chinese linking fails
- This is why AoA propagation found only 1 word

## After Enrichment

Once Q-IDs are added:
1. Run `link_english_via_cedict.py` to link English words
2. Run `propagate_aoa_to_chinese.py` to propagate AoA
3. Both scripts will work properly


