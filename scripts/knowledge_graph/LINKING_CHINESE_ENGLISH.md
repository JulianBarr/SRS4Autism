# Linking Chinese Words to English Translations

There are **two approaches** to link Chinese words to English translations for AoA propagation:

## Approach 1: Through Concepts (Recommended)

**How it works:**
1. Chinese word → `srs-kg:means` → **Concept** ← `srs-kg:means` ← English word
2. Both Chinese and English words share the same Concept node
3. The `propagate_aoa_to_chinese.py` script finds English words through these shared concepts

**To create these links, use:**
```bash
python scripts/knowledge_graph/link_english_via_cedict.py
```

This script:
- Loads CC-CEDICT dictionary (English ↔ Chinese translations)
- Finds Chinese words in the KG that match CEDICT entries
- Links English words to the **same concepts** that those Chinese words use
- Creates the concept bridge needed for AoA propagation

**Advantages:**
- ✅ Uses existing Chinese concepts (which may have Wikidata Q-IDs)
- ✅ Fast (no Wikidata API calls)
- ✅ Creates semantic links (words sharing concepts = same meaning)

## Approach 2: Direct Definition Property

**How it works:**
1. Chinese word has `srs-kg:definition` property with English text
2. The `propagate_aoa_to_chinese.py` script extracts English words from definitions

**To add definitions, use:**
- CC-CEDICT data (already loaded in some scripts)
- Manual annotation
- Other dictionary sources

**Advantages:**
- ✅ Simple and direct
- ✅ Works even without concept links

**Disadvantages:**
- ⚠️ Requires parsing English text from definitions
- ⚠️ May miss words if definitions are incomplete

## Current Status

The `propagate_aoa_to_chinese.py` script uses **both approaches**:
1. First tries direct `srs-kg:definition` properties
2. Then tries concept links: `Chinese word → Concept → English word`

**Why only 1 word was found:**
- The merged graph was corrupted (only 209 triples, should be ~850K+)
- **Fixed:** Restored from backup (36M file)
- Need to re-run `link_english_via_cedict.py` to create concept links

## Recommended Workflow

1. **Restore merged graph** (if corrupted):
   ```bash
   cp knowledge_graph/world_model_merged_20251126_152809.ttl \
      knowledge_graph/world_model_merged.ttl
   ```

2. **Link English words to Chinese concepts via CEDICT:**
   ```bash
   python scripts/knowledge_graph/link_english_via_cedict.py
   ```

3. **Propagate AoA from English to Chinese:**
   ```bash
   python scripts/knowledge_graph/propagate_aoa_to_chinese.py --merge
   ```

4. **Merge and restart Fuseki:**
   ```bash
   python scripts/knowledge_graph/merge_kg_files.py
   ./restart_fuseki.sh
   ```

## Files Involved

- `link_english_via_cedict.py` - Creates concept links via CEDICT
- `propagate_aoa_to_chinese.py` - Uses concept links to propagate AoA
- `link_english_to_wikidata_concepts.py` - Alternative: links via Wikidata Q-IDs
- `fix_english_chinese_concept_links.py` - Fixes incorrect concept links


