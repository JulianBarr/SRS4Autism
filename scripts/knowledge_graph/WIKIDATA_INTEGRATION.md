# Wikidata Integration for Cross-Language Concept Alignment

This implementation follows the strategy outlined in `Align different languages to the single global concept.md` to use **Wikidata Q-IDs** as the central "hub" for aligning Chinese and English words to the same semantic concepts.

## Architecture

### The Hub-and-Spoke Model

```
Chinese Word (朋友) 
    ↓ srs-kg:means
Concept (Q34079) ← Wikidata Q-ID
    ↓ owl:sameAs
Wikidata Entity (http://www.wikidata.org/entity/Q34079)
    ↑ owl:sameAs
Concept (Q34079)
    ↑ srs-kg:means
English Word (friend)
```

### Key Components

1. **Concept Nodes**: Store Wikidata Q-IDs (`srs-kg:wikidataId`) and link to Wikidata entities via `owl:sameAs`
2. **CC-CEDICT Dictionary**: Provides Chinese-to-English translations for lookup
3. **Wikidata API**: Searches for matching concepts and retrieves multilingual labels

## Files

- `load_cc_cedict.py`: Loads and parses CC-CEDICT dictionary data
- `enrich_with_wikidata.py`: Main script to enrich existing concepts with Wikidata Q-IDs
- `srs_schema.ttl`: Updated ontology with `srs-kg:wikidataId` property

## Setup

### 1. Download CC-CEDICT Dictionary

Download the CC-CEDICT dictionary file:

```bash
# Option 1: Direct download
wget https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
gunzip cedict_1_0_ts_utf-8_mdbg.txt.gz
mv cedict_1_0_ts_utf-8_mdbg.txt data/cedict_ts.u8

# Option 2: From official source
# Visit: https://www.mdbg.net/chinese/dictionary?page=cc-cedict
# Download: cedict_ts.u8
# Place in: data/cedict_ts.u8
```

### 2. Run the Enrichment Script

```bash
cd /Users/maxent/src/SRS4Autism
python3 scripts/knowledge_graph/enrich_with_wikidata.py
```

This script will:
1. Load CC-CEDICT dictionary
2. Find all Chinese words in the knowledge graph
3. Get English translations from CC-CEDICT
4. Search Wikidata API for matching concepts
5. Link concepts to Wikidata Q-IDs
6. Update the knowledge graph

## How It Works

### Step 1: Find Chinese Words
The script iterates through all `srs-kg:Word` nodes in the knowledge graph.

### Step 2: Get English Translations
For each Chinese word, it looks up English translations in CC-CEDICT:
- Input: `朋友`
- Output: `['friend', 'companion', 'pal']`

### Step 3: Search Wikidata
For each English translation, it searches Wikidata API:
- Search term: `"friend"`
- Returns: `Q34079` (with label "friend" and description)

### Step 4: Link to Concept
The script adds to the concept node:
```turtle
srs-kg:concept-friend-xxx a srs-kg:Concept ;
    srs-kg:wikidataId "Q34079" ;
    owl:sameAs <http://www.wikidata.org/entity/Q34079> ;
    rdfs:label "friend"@en ;
    rdfs:label "朋友"@zh .
```

## Benefits

1. **Cross-Language Alignment**: Chinese "朋友" and English "friend" both link to Q34079
2. **Future-Proof**: Can easily add more languages (Spanish, French, etc.)
3. **Rich Metadata**: Wikidata provides descriptions, images, and relationships
4. **Extensibility**: Same system works for math, science, and other domains

## Example Query

Find all words (in any language) that mean the same concept:

```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX wd: <http://www.wikidata.org/entity/>

SELECT ?chinese_word ?english_word
WHERE {
    # Find concept with Wikidata Q-ID
    ?concept srs-kg:wikidataId "Q34079" .
    
    # Find Chinese word
    ?chinese_word_uri a srs-kg:Word .
    ?chinese_word_uri srs-kg:text ?chinese_word .
    ?chinese_word_uri srs-kg:means ?concept .
    
    # Find English word (if exists)
    OPTIONAL {
        ?english_word_uri a srs-kg:Word .
        ?english_word_uri srs-kg:text ?english_word .
        ?english_word_uri srs-kg:means ?concept .
        FILTER(LANG(?english_word) = "en")
    }
}
```

## Rate Limiting

The script includes a 500ms delay between Wikidata API requests to be respectful. For large datasets, consider:
- Running in batches
- Using Wikidata Query Service (SPARQL) for bulk lookups
- Caching results

## Troubleshooting

### CC-CEDICT Not Found
- Ensure the file is named `cedict_ts.u8` or `cc-cedict.txt`
- Place it in `data/` directory or update paths in `load_cc_cedict.py`

### Wikidata API Errors
- Check internet connection
- Verify API is accessible: https://www.wikidata.org/w/api.php
- Increase timeout if needed

### No Matches Found
- Some words may not have Wikidata entries
- Try different English translations
- Manually add Wikidata Q-IDs if needed

## Next Steps

1. **Add English Words**: Create a script to add English words that link to the same Wikidata concepts
2. **Math Integration**: Use Wikidata Q-IDs for mathematical concepts (e.g., Q11518 for "Pythagorean theorem")
3. **Visual Enrichment**: Use Wikidata to fetch images and other visualizations
4. **Relationship Mapping**: Import semantic relationships from Wikidata (synonyms, antonyms, etc.)


