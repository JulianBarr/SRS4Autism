# Knowledge Graph Schema Migration Analysis
## Phase 3: SPARQL Query Migration

**Date**: 2026-01-13
**Scope**: `backend/app/routers/literacy.py`

---

## Summary of Breaking Changes

### 1. Primary Label Property
- **OLD**: `srs-kg:text` with language filters
- **NEW**: `rdfs:label` with language tags
- **Impact**: ALL SPARQL queries that read word text

### 2. URI Pattern Changes
- **OLD**: Arbitrary patterns (e.g., `srs-kg:word-pengyou`)
- **NEW**: Strict conventions:
  - Concepts: `srs-inst:concept_{QID}` (e.g., `srs-inst:concept_Q146`)
  - Chinese words: `srs-inst:word_zh_{pinyin}` (e.g., `srs-inst:word_zh_mao`)
  - English words: `srs-inst:word_en_{word}` (e.g., `srs-inst:word_en_cat`)

### 3. Language Filtering
- **OLD**: `FILTER (lang(?text) = "en")`
- **NEW**: `FILTER (lang(?label) = "en")` on `rdfs:label`

---

## Affected Queries in literacy.py

### Query 1: Light Vocabulary Query (Lines 333-341)
**Location**: `_build_sorted_vocab_cache()` function
**Purpose**: Fetch all Logic City vocabulary items with English labels

**Current Query** (BROKEN):
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT DISTINCT ?wordUri ?englishWord (SAMPLE(?imageNode) AS ?exampleImage) WHERE {
    ?zhNode srs-kg:learningTheme "Logic City" ; srs-kg:means ?concept .
    ?wordUri a srs-kg:Word ; srs-kg:means ?concept ; srs-kg:text ?englishWord .
    FILTER (lang(?englishWord) = "en")
    OPTIONAL { ?concept srs-kg:hasVisualization ?imageNode }
} GROUP BY ?wordUri ?englishWord
```

**Issues**:
1. Uses `srs-kg:text` instead of `rdfs:label`
2. Assumes English words are separate entities with `srs-kg:text`

**Fixed Query**:
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?wordUri ?englishWord (SAMPLE(?imageNode) AS ?exampleImage) WHERE {
    ?zhNode srs-kg:learningTheme "Logic City" ; srs-kg:means ?concept .
    ?wordUri a srs-kg:Word ; srs-kg:means ?concept ; rdfs:label ?englishWord .
    FILTER (lang(?englishWord) = "en")
    OPTIONAL { ?concept srs-kg:hasVisualization ?imageNode }
} GROUP BY ?wordUri ?englishWord
```

---

### Query 2: Detail Vocabulary Query (Lines 545-563)
**Location**: `get_logic_city_vocab()` endpoint
**Purpose**: Fetch detailed information (Chinese words, images) for paginated vocabulary

**Current Query** (BROKEN):
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?wordUri ?chineseWord ?imagePath WHERE {
    VALUES ?wordUri { {uris} }
    ?wordUri srs-kg:means ?concept .

    # Fetch ONLY the Logic City tagged Chinese word
    OPTIONAL {
        ?zhNode srs-kg:text ?chineseWord ;
                srs-kg:means ?concept ;
                srs-kg:learningTheme "Logic City" .
        FILTER (lang(?chineseWord) = "zh")
    }

    OPTIONAL {
        ?concept srs-kg:hasVisualization ?v . ?v srs-kg:imageFilePath ?imagePath .
    }
}
```

**Issues**:
1. Uses `srs-kg:text` instead of `rdfs:label`
2. Queries for Chinese words separately

**Fixed Query**:
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?wordUri ?chineseWord ?imagePath WHERE {
    VALUES ?wordUri { {uris} }
    ?wordUri srs-kg:means ?concept .

    # Fetch ONLY the Logic City tagged Chinese word
    OPTIONAL {
        ?zhNode rdfs:label ?chineseWord ;
                srs-kg:means ?concept ;
                srs-kg:learningTheme "Logic City" .
        FILTER (lang(?chineseWord) = "zh")
    }

    OPTIONAL {
        ?concept srs-kg:hasVisualization ?v . ?v srs-kg:imageFilePath ?imagePath .
    }
}
```

---

### Query 3: Anki Sync Query (Lines 666-678)
**Location**: `sync_logic_city_to_anki()` endpoint
**Purpose**: Fetch data for syncing to Anki

**Current Query** (BROKEN):
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?wordUri ?english ?chinese ?imagePath WHERE {
    VALUES ?wordUri { {uri_str} }
    ?wordUri srs-kg:text ?english .
    FILTER(lang(?english)="en")
    ?wordUri srs-kg:means ?c .
    OPTIONAL {
        ?zh srs-kg:means ?c; srs-kg:text ?chinese; srs-kg:learningTheme "Logic City".
        FILTER(lang(?chinese)="zh")
    }
    OPTIONAL { ?c srs-kg:hasVisualization ?v. ?v srs-kg:imageFilePath ?imagePath. }
}
```

**Issues**:
1. Uses `srs-kg:text` for both English and Chinese
2. Assumes ?wordUri has English text directly

**Fixed Query**:
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?wordUri ?english ?chinese ?imagePath WHERE {
    VALUES ?wordUri { {uri_str} }
    ?wordUri rdfs:label ?english .
    FILTER(lang(?english)="en")
    ?wordUri srs-kg:means ?c .
    OPTIONAL {
        ?zh srs-kg:means ?c; rdfs:label ?chinese; srs-kg:learningTheme "Logic City".
        FILTER(lang(?chinese)="zh")
    }
    OPTIONAL { ?c srs-kg:hasVisualization ?v. ?v srs-kg:imageFilePath ?imagePath. }
}
```

---

## Migration Checklist

- [x] Phase 1: Finalize ontology at `knowledge_graph/ontology.ttl`
- [x] Phase 2: Create generator script `scripts/build_core_v2.py`
- [x] Phase 2: Generate `world_model_v2.ttl` with sample data
- [ ] Phase 3: Fix Query 1 in `_build_sorted_vocab_cache()`
- [ ] Phase 3: Fix Query 2 in `get_logic_city_vocab()`
- [ ] Phase 3: Fix Query 3 in `sync_logic_city_to_anki()`
- [ ] Phase 4: Test queries with `world_model_v2.ttl`
- [ ] Phase 5: Full data migration (regenerate complete graph)

---

## Notes

1. **Backward Compatibility**: The old `srs-kg:text` property is marked as deprecated in the ontology but NOT removed, allowing gradual migration.

2. **Testing Strategy**:
   - Use `world_model_v2.ttl` for initial testing
   - Once queries work, regenerate full knowledge graph
   - Update Fuseki/Oxigraph to load new graph

3. **Future Work**:
   - Add fallback queries for legacy data during transition period
   - Consider adding SPARQL UPDATE queries to migrate existing data in-place
