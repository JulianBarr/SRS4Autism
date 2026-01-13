# Backward Compatibility Guide - KG Schema v2.0

**Date**: 2026-01-13
**Schema Version**: 2.0
**Maintainers**: See knowledge_graph/ontology.ttl

---

## Overview

This guide documents backward compatibility strategies for migrating from the old knowledge graph schema to v2.0. The migration is designed to be **non-breaking** with gradual adoption paths.

---

## Table of Contents

1. [Schema Changes Summary](#schema-changes-summary)
2. [Migration Phases](#migration-phases)
3. [Compatibility Matrix](#compatibility-matrix)
4. [Code Examples](#code-examples)
5. [Troubleshooting](#troubleshooting)

---

## Schema Changes Summary

### 1. Label Property Migration

**OLD (Deprecated)**:
```sparql
?word srs-kg:text "猫" .
```

**NEW (v2.0)**:
```sparql
?word rdfs:label "猫"@zh .
```

**Rationale**: `rdfs:label` is the standard RDF property for human-readable labels.Use language tags (`@zh`, `@en`, `@en-Latn`) to differentiate languages.

**Backward Compatibility**:
- Old `srs-kg:text` property marked as deprecated (not removed)
- Both properties can coexist during transition
- Queries should prefer `rdfs:label` but can fall back to `srs-kg:text`

---

### 2. URI Namespace Changes

| Entity Type | OLD Pattern | NEW Pattern | Example (NEW) |
|-------------|-------------|-------------|---------------|
| Concepts | N/A (didn't exist) | `srs-inst:concept_{QID}` | `srs-inst:concept_Q146` |
| Chinese Words | `srs-kg:word-{text}` | `srs-inst:word_zh_{pinyin}` | `srs-inst:word_zh_mao` |
| English Words | `srs-kg:word-{text}` | `srs-inst:word_en_{word}` | `srs-inst:word_en_cat` |
| Characters | `srs-kg:char-{encoded}` | `srs-inst:char_{encoded}` | `srs-inst:char_%E7%8C%AB` |
| Grammar Points | `srs-inst:gp-{level}-{id}-{name}` | `srs-inst:gp_{level}_{id}_{slug}` | `srs-inst:gp_B1_142_reduplication` |

**Rationale**:
- **Instances** (actual data) use `srs-inst:` namespace
- **Schema** (classes/properties) use `srs-kg:` namespace
- URL-safe characters only (underscores instead of hyphens where appropriate)
- Language-specific prefixes (`_zh_`, `_en_`) for words

**Backward Compatibility**:
- Parsers accept both old and new URI formats
- URI normalization functions handle both patterns
- Validation checks for either format during transition

---

### 3. Wikidata Integration

**NEW Feature in v2.0**:
```turtle
srs-inst:concept_Q146 a srs-kg:Concept ;
    rdfs:label "concept:cat"@en ;
    srs-kg:wikidataId "Q146" ;
    owl:sameAs wd:Q146 .
```

**Benefits**:
- Language-agnostic concept hubs
- Cross-language word alignment
- External knowledge integration

**Backward Compatibility**:
- Old data without concepts continues to work
- Concepts are optional (words can exist independently)
- Migration can be gradual (add concepts incrementally)

---

## Migration Phases

### Phase 1: Dual Format Support (COMPLETE ✅)
**Status**: Implemented in Waves 1 & 2
**Duration**: Indefinite (until Phase 3)

**Features**:
- All SPARQL queries updated to use `rdfs:label`
- Parsers accept both old and new URI formats
- Character URI construction uses new namespace
- Metadata validation handles both formats

**Action Required**: None - system automatically supports both

---

### Phase 2: New Graph Generation (IN PROGRESS ⏳)
**Status**: Sample v2 graph created
**Next Steps**: Generate complete knowledge graph

**Features**:
- Generator script (`scripts/build_core_v2.py`) creates v2-compliant graph
- Strict URI conventions enforced
- Wikidata Q-IDs integrated
- Validation checks built-in

**Action Required**:
1. Expand vocabulary in generator script
2. Run: `python scripts/build_core_v2.py`
3. Load new graph into triplestore
4. Test all endpoints

---

### Phase 3: Deprecation (FUTURE 📅)
**Status**: Not started
**Prerequisites**: All systems confirmed using v2 format

**Features**:
- Remove old `srs-kg:text` property from ontology
- Remove backward compatibility code
- Enforce strict v2 validation
- Update all documentation

**Action Required** (when ready):
1. Monitor logs for old format usage
2. Confirm zero occurrences for 30 days
3. Remove compatibility layer
4. Update ontology to remove deprecated properties

---

## Compatibility Matrix

### SPARQL Queries

| Query Type | OLD Format | NEW Format | Status |
|------------|-----------|-------------|--------|
| Word Text Lookup | `?word srs-kg:text ?text` | `?word rdfs:label ?text` | ✅ Migrated (Wave 1) |
| Language Filtering | `FILTER(lang(?text) = "zh")` | `FILTER(lang(?label) = "zh")` | ✅ Migrated (Wave 1) |
| Concept Linking | N/A | `?word srs-kg:means ?concept` | ✅ New in v2 |
| Character Lookup | `?word srs-kg:composedOf ?char` | Same (no change) | ✅ Compatible |
| Grammar Points | `?gp a srs-kg:GrammarPoint` | Same (no change) | ✅ Compatible |

### Python Code

| Component | OLD Pattern | NEW Pattern | Status |
|-----------|-------------|-------------|--------|
| Character URI | `srs-kg:char-{x}` | `srs-inst:char_{x}` | ✅ Migrated (Wave 2) |
| Word URI Parsing | `startswith("srs-kg:word-")` | Both formats supported | ✅ Migrated (Wave 2) |
| Metadata Validation | Single namespace | Multi-namespace fallback | ✅ Migrated (Wave 2) |
| Schema Constants | Hardcoded strings | `backend.schema.constants` | ✅ New in Wave 3 |

### Knowledge Graph Files

| File | Format | Compatibility | Notes |
|------|--------|---------------|-------|
| `world_model_complete.ttl` | OLD | ✅ Supported | Legacy format |
| `world_model_v2.ttl` | NEW | ✅ Supported | v2 format (sample) |
| `ontology.ttl` | v2.0 | ✅ Current | Source of truth |

---

## Code Examples

### Example 1: Using Schema Constants

**OLD (Hardcoded strings)**:
```python
# ❌ Bad: Hardcoded, error-prone
query = """
PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?word WHERE {
    ?word a srs-kg:Word ;
          srs-kg:text ?text .
}
"""
```

**NEW (Using constants)**:
```python
# ✅ Good: Type-safe, maintainable
from backend.schema import Classes, DataProperties, STANDARD_PREFIXES

query = f"""
{STANDARD_PREFIXES}
SELECT ?word WHERE {{
    ?word a {Classes.WORD} ;
          {DataProperties.LABEL} ?text .
}}
"""
```

---

### Example 2: Creating Word URIs

**OLD (Manual string concatenation)**:
```python
# ❌ Bad: Inconsistent, fragile
word_uri = f"srs-kg:word-{chinese_text}"  # Wrong namespace!
```

**NEW (Using helpers)**:
```python
# ✅ Good: Consistent, validated
from backend.schema import make_word_uri

word_uri = make_word_uri("mao", "zh")  # Returns: "srs-inst:word_zh_mao"
```

---

### Example 3: Handling Both Formats

**Recommended Pattern**:
```python
from backend.schema import is_legacy_uri, normalize_uri

def process_word_uri(uri: str) -> dict:
    # Normalize URI format
    normalized = normalize_uri(uri)

    # Check if legacy format
    if is_legacy_uri(normalized):
        print(f"⚠️  Legacy URI detected: {normalized}")
        # Handle conversion or log for migration

    # Continue processing...
    return {"uri": normalized, "is_legacy": is_legacy_uri(normalized)}
```

---

### Example 4: SPARQL with Fallback

**Backward-Compatible Query**:
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?word ?text WHERE {
    ?word a srs-kg:Word .

    # Try new format first, fallback to old
    OPTIONAL { ?word rdfs:label ?label_new . }
    OPTIONAL { ?word srs-kg:text ?label_old . }

    BIND(COALESCE(?label_new, ?label_old) AS ?text)

    FILTER(BOUND(?text))
}
```

---

## Troubleshooting

### Issue 1: "No results from SPARQL query"

**Symptoms**:
- Query returns empty results
- Worked before migration

**Diagnosis**:
```sparql
# Check which label property is used in your graph
SELECT ?prop WHERE {
    ?word a srs-kg:Word .
    ?word ?prop ?value .
    FILTER(?prop = rdfs:label || ?prop = srs-kg:text)
}
LIMIT 10
```

**Solution**:
- If graph uses `srs-kg:text`, update graph or use fallback query (Example 4)
- If graph uses `rdfs:label`, ensure queries use correct property

---

### Issue 2: "URI format mismatch"

**Symptoms**:
- Character/word lookup fails
- URI not found in graph

**Diagnosis**:
```python
from backend.schema import is_legacy_uri, normalize_uri

uri = "srs-kg:word-猫"
print(f"Is legacy: {is_legacy_uri(uri)}")
print(f"Normalized: {normalize_uri(uri)}")
```

**Solution**:
- Use `normalize_uri()` before lookups
- Check parser configuration supports both formats (Wave 2)
- Verify graph uses expected URI pattern

---

### Issue 3: "Character mastery not tracking"

**Symptoms**:
- Character mastery updates don't persist
- Recommendations ignore mastered characters

**Diagnosis**:
```python
# Check URI format in database
from backend.database.services import ProfileService

chars = ProfileService.get_mastered_characters(db, profile_id)
print(f"Mastered chars URIs: {chars}")
# Should show: srs-inst:char_xxx (v2) not srs-kg:char-xxx (old)
```

**Solution**:
- Wave 2 fixed character URI construction
- If database has old URIs, run migration script (see below)
- Verify `integrated_recommender_service.py` uses v2 format

---

### Issue 4: "Grammar points not loading"

**Symptoms**:
- Grammar point list empty
- SPARQL query returns no results

**Diagnosis**:
```sparql
# Check grammar point URIs in graph
SELECT ?gp WHERE {
    ?gp a srs-kg:GrammarPoint .
}
LIMIT 5
```

**Solution**:
- Grammar points are compatible (no URI change required)
- Ensure graph has `rdfs:label` properties (not just `srs-kg:text`)
- Check CEFR/language filters in query

---

## Migration Utilities

### Check Schema Version

```python
from backend.schema import validate_concept_uri, validate_word_uri

# Test URI against v2 patterns
uri = "srs-inst:word_zh_mao"
print(f"Valid v2 word URI: {validate_word_uri(uri, 'zh')}")

# Expected: True
```

### Bulk URI Validation

```python
from backend.schema import is_legacy_uri

# Scan URIs in database
def audit_uris(db_session):
    from backend.database.models import MasteredWord

    legacy_count = 0
    total = 0

    for record in db_session.query(MasteredWord).all():
        total += 1
        if is_legacy_uri(record.word_id):
            legacy_count += 1
            print(f"⚠️  Legacy: {record.word_id}")

    print(f"\nAudit complete: {legacy_count}/{total} legacy URIs found")
```

---

## Best Practices

### 1. Always Use Schema Constants

```python
# ✅ DO THIS
from backend.schema import Classes, DataProperties

query = f"?word a {Classes.WORD} ; {DataProperties.LABEL} ?text ."

# ❌ DON'T DO THIS
query = "?word a srs-kg:Word ; srs-kg:text ?text ."
```

### 2. Use Helper Functions for URI Construction

```python
# ✅ DO THIS
from backend.schema import make_word_uri, make_character_uri

word_uri = make_word_uri("mao", "zh")
char_uri = make_character_uri("%E7%8C%AB")

# ❌ DON'T DO THIS
word_uri = f"srs-inst:word_zh_mao"  # Typos likely
```

### 3. Validate URIs Before Database Operations

```python
# ✅ DO THIS
from backend.schema import validate_word_uri

def save_word(word_uri: str, language: str):
    if not validate_word_uri(word_uri, language):
        raise ValueError(f"Invalid word URI format: {word_uri}")

    # Proceed with save...
```

### 4. Add Fallbacks for Transition Period

```python
# ✅ DO THIS (during migration)
def get_word_label(word_node):
    # Try v2 first
    label = word_node.get(DataProperties.LABEL)
    if not label:
        # Fallback to old property
        label = word_node.get(LegacyPatterns.OLD_TEXT_PROPERTY)
    return label
```

---

## Support & Resources

### Documentation
- **Ontology**: `knowledge_graph/ontology.ttl` (source of truth)
- **Migration Reports**: `WAVE1_COMPLETE.md`, `WAVE2_COMPLETE.md`, `WAVE3_COMPLETE.md`
- **Generator**: `scripts/build_core_v2.py` (reference implementation)

### Code References
- **Schema Constants**: `backend/schema/constants.py`
- **URI Helpers**: `backend/schema/__init__.py`
- **Fixed Queries**: `backend/app/main.py` (Wave 1)
- **Fixed Parsers**: `backend/services/` (Wave 2)

### Testing
```bash
# Test with v2 graph
python scripts/build_core_v2.py  # Generate sample
# Load into triplestore
# Test endpoints

# Validate URIs
python -c "from backend.schema import *; print(validate_word_uri('srs-inst:word_zh_mao', 'zh'))"
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-01-13 | Initial v2.0 release with Wikidata integration |
| | | - Migrated to rdfs:label (Wave 1) |
| | | - Updated URI construction (Wave 2) |
| | | - Added schema constants module (Wave 3) |

---

**End of Backward Compatibility Guide**
