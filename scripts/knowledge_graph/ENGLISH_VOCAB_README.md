# English Vocabulary Knowledge Graph

This directory contains scripts to build an English vocabulary knowledge graph with CEFR (Common European Framework of Reference) levels, similar to the HSK-based Chinese vocabulary knowledge graph.

## Overview

The English vocabulary knowledge graph uses **CEFR levels** (A1, A2, B1, B2, C1, C2) instead of HSK levels to categorize vocabulary by proficiency:

- **A1-A2**: Beginner (Basic user)
- **B1-B2**: Intermediate (Independent user)  
- **C1-C2**: Advanced (Proficient user)

## Data Sources

### Primary: English Vocabulary Profile (EVP)

The **English Vocabulary Profile (EVP)** is the recommended primary data source:
- Website: https://www.englishprofile.org/wordlists
- Provides words and phrases with CEFR levels
- Includes definitions, example sentences, and usage notes

### Alternative Sources

1. **CEFRLex Project**
   - URL: https://cental.uclouvain.be/cefrlex/
   - Machine-readable lexical resources graded by CEFR

2. **Cambridge English Word Lists**
   - KET (A2), PET (B1), FCE (B2), CAE (C1), CPE (C2)
   - Available as PDFs from Cambridge

3. **Oxford 3000/5000**
   - Oxford 3000: Most important words
   - Oxford 5000: Expanded list
   - Tagged with CEFR levels

4. **Wordly Wise 3000** (for K-12 grade levels)
   - Grade 2-12 vocabulary curriculum
   - ~3,000 words total

## Setup

### 1. Prepare Data File

Create a CSV or JSON file with English vocabulary:

**CSV Format** (`data/content_db/english_vocab_evp.csv`):
```csv
word,definition,cefr_level,pos,concreteness
cat,a small domesticated carnivorous mammal,A1,noun,4.8
dog,a domesticated carnivorous mammal,A1,noun,4.9
house,a building for human habitation,A1,noun,5.0
```

**JSON Format** (`data/content_db/english_vocab_evp.json`):
```json
[
  {
    "word": "cat",
    "definition": "a small domesticated carnivorous mammal",
    "cefr_level": "A1",
    "pos": "noun",
    "concreteness": 4.8
  }
]
```

**Required columns:**
- `word`: The English word
- `definition`: Word definition (optional but recommended)
- `cefr_level`: CEFR level (A1, A2, B1, B2, C1, C2)
- `pos`: Part of speech (optional)
- `concreteness`: Concreteness rating 1-5 (optional, from Brysbaert et al. BRM)

### 2. Download Sample Data (Optional)

Run the helper script to create a sample vocabulary file:

```bash
cd /Users/maxent/src/SRS4Autism
source venv/bin/activate
python scripts/knowledge_graph/download_evp_data.py
```

This creates a small sample file with common A1-A2 words.

### 3. Generate Knowledge Graph

Run the population script:

```bash
python scripts/knowledge_graph/populate_english_vocab.py
```

The script will:
- Load vocabulary from CSV or JSON
- Create Word nodes with CEFR levels
- Create Concept nodes for semantic linking
- Link words to concepts via `srs-kg:means`
- Optionally merge with existing Chinese KG

**Output:** `knowledge_graph/world_model_english.ttl`

## Schema Updates

The ontology schema (`knowledge_graph/ontology/srs_schema.ttl`) has been updated to support CEFR levels for English words:

```turtle
srs-kg:cefrLevel a rdf:Property ;
    rdfs:range rdfs:Literal ;
    rdfs:comment "CEFR level (A1, A2, B1, B2, C1, C2) for GrammarPoint or Word proficiency level." .
```

Note: `cefrLevel` can now be used for both `Word` and `GrammarPoint` classes.

## Integration with Recommender

The English vocabulary can be used with the Curious Mario recommender by:

1. **Updating the recommender config** to query English words:
   ```python
   config = RecommenderConfig(
       node_types=("srs-kg:Word",),  # Will match both Chinese and English
       # Filter by language if needed
   )
   ```

2. **Querying by CEFR level** instead of HSK level:
   ```sparql
   SELECT ?word ?cefr WHERE {
       ?word a srs-kg:Word ;
             rdfs:label ?label ;
             srs-kg:cefrLevel ?cefr .
       FILTER(LANG(?label) = "en")
   }
   ```

## Merging with Chinese KG

To create a unified knowledge graph with both Chinese and English vocabulary:

1. Run the English vocab script and choose to merge when prompted
2. Or manually merge the Turtle files:
   ```bash
   # Load both into Fuseki
   # Or use rdflib to merge programmatically
   ```

## Next Steps

1. **Download full EVP dataset** from English Profile website
2. **Add concreteness ratings** from Brysbaert et al. BRM database
3. **Link to Wikidata** concepts (similar to Chinese vocabulary)
4. **Add visual images** from Anki packages
5. **Integrate with recommender** engine for bilingual recommendations

## References

- English Vocabulary Profile: https://www.englishprofile.org/
- CEFRLex: https://cental.uclouvain.be/cefrlex/
- CEFR Framework: https://www.coe.int/en/web/common-european-framework-reference-languages/
- Concreteness Database: Brysbaert et al. (2014) - Available in `data/content_db/Concreteness_ratings_Brysbaert_et_al_BRM.txt`

