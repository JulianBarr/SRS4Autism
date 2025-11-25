# IRI Migration Instructions

## Overview
The knowledge graph has been migrated from percent-encoded IRIs to readable UTF-8 IRIs.

**Before:** `srs-kg:word-%E4%B8%BB%E8%A6%81` (unreadable)  
**After:** `srs-kg:word-主要` (readable)

## Migration Steps

### 1. Backup (Already Done)
- ✅ Old file backed up as: `knowledge_graph/world_model_cwn.ttl.backup`
- ✅ New file generated: `knowledge_graph/world_model_cwn.ttl` (20MB, 464,887 triples)

### 2. Restart Fuseki

Since Fuseki is running in read-only mode (file-based dataset), you need to restart it:

**Option A: If running Fuseki manually**
```bash
# Stop current Fuseki instance (Ctrl+C or kill process)
# Then restart:
cd /path/to/fuseki
./fuseki-server --file=/Users/maxent/src/SRS4Autism/knowledge_graph/world_model_cwn.ttl /srs4autism
```

**Option B: If using a persistent dataset**
1. Access Fuseki web UI: http://localhost:3030
2. Select the `srs4autism` dataset
3. Go to "Upload" or "Add data"
4. Delete existing data (if needed)
5. Upload the new `world_model_cwn.ttl` file

### 3. Verify Migration

Run the verification script:
```bash
cd /Users/maxent/src/SRS4Autism
python3 scripts/knowledge_graph/verify_migration.py
```

This will check:
- ✅ IRIs are readable (not percent-encoded)
- ✅ SPARQL queries still work
- ✅ Word lookups function correctly

## What Changed

### Files Modified
- `scripts/knowledge_graph/populate_from_cwn.py` - Updated `generate_slug()` function
- `scripts/knowledge_graph/populate_chinese_kg.py` - Updated `generate_slug()` function  
- `scripts/knowledge_graph/populate_grammar.py` - Updated `generate_slug()` function

### Impact Assessment

**✅ Low Risk Areas (Should Continue Working)**
- SPARQL queries using `srs-kg:text` property (not IRIs directly)
- Knowledge point IDs (`kp:` format) - separate from IRI format
- Word lookups by text content

**⚠️ Potential Issues**
- Any hardcoded percent-encoded IRI references (none found in codebase)
- Cached data with old IRIs (none found - word_kp_cache.json uses text, not IRIs)

## Rollback Plan

If issues occur, you can rollback:
```bash
# Restore old file
cp knowledge_graph/world_model_cwn.ttl.backup knowledge_graph/world_model_cwn.ttl

# Restart Fuseki with old file
./fuseki-server --file=knowledge_graph/world_model_cwn.ttl /srs4autism
```

## Testing

After migration, test these endpoints:
- `/api/words/{word}` - Word knowledge lookup
- `/api/learning-frontier` - Learning frontier algorithm
- Any SPARQL queries in the backend

All should continue working since they query by text properties, not IRIs.


