# SPARQL Query Samples for Curious Mario Knowledge Graph

The knowledge graph is available at: `http://localhost:3030/srs4autism/query`

## Basic Queries

### 1. Find HSK Level 1 Words (Beginner Vocabulary)
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?word ?pinyin WHERE {
  ?word a srs-kg:Word ;
        rdfs:label ?word_text ;
        srs-kg:pinyin ?pinyin ;
        srs-kg:hskLevel 1 .
}
LIMIT 10
```

**Result:** Returns beginner words like 一些 (yī xiē), 介绍 (jiè shào), 考试 (kǎo shì)

### 2. Count Words by HSK Level
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>

SELECT ?hsk (COUNT(DISTINCT ?word) as ?count) WHERE {
  ?word a srs-kg:Word ;
        srs-kg:hskLevel ?hsk .
}
GROUP BY ?hsk
ORDER BY ?hsk
```

**Result:**
- HSK 1: 485 words
- HSK 2: 691 words
- HSK 3: 920 words
- HSK 4: 883 words
- HSK 5: 965 words
- HSK 6: 923 words
- HSK 7: 3,846 words

### 3. Find Words Composed of Specific Characters
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?word ?pinyin ?hsk WHERE {
  ?word a srs-kg:Word ;
        srs-kg:composedOf ?char ;
        rdfs:label ?word_text ;
        srs-kg:pinyin ?pinyin ;
        srs-kg:hskLevel ?hsk .
  ?char rdfs:label "人" .
}
LIMIT 10
```

**Result:** Returns words containing 人 (like 人类, 人员, 人民币)

### 4. Find Learning Frontier (HSK 3 Words with Known Characters)
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?word ?pinyin WHERE {
  ?word a srs-kg:Word ;
        srs-kg:composedOf ?char ;
        rdfs:label ?word_text ;
        srs-kg:pinyin ?pinyin ;
        srs-kg:hskLevel 3 .
  ?char rdfs:label ?char_text .
  FILTER(?char_text IN ("苹", "果", "朋", "友"))
}
LIMIT 10
```

**Result:** Returns HSK 3 words like 人民, 朋友, 公司 that use known characters

### 5. Find Related Concepts (Synonyms)
```sparql
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?word1 ?word2 WHERE {
  ?concept srs-kg:isSynonymOf ?concept2 .
  ?word1 a srs-kg:Word ;
         srs-kg:means ?concept ;
         rdfs:label ?word1_text .
  ?word2 a srs-kg:Word ;
         srs-kg:means ?concept2 ;
         rdfs:label ?word2_text .
  FILTER(?word1 != ?word2)
}
LIMIT 10
```

**Result:** Returns word pairs that share meanings

## Advanced Queries for Recommendations

### Learning Frontier Algorithm (Python)

See `scripts/knowledge_graph/demo_recommendation.py` for the full algorithm.

**Logic:**
1. Get mastered words from profile
2. Find words in target HSK level (e.g., Level 3)
3. Score words based on:
   - Being in Learning Frontier: +100 points
   - Known characters: +50 points per char
   - Too hard (HSK > target+1): -500 points
4. Return top 20 recommendations

## Testing Queries via Command Line

```bash
curl -s "http://localhost:3030/srs4autism/query?query=YOUR_QUERY" \
  -H "Accept: text/csv"
```

Or use JSON format for programmatic access:
```bash
curl -s "http://localhost:3030/srs4autism/query?query=YOUR_QUERY" \
  -H "Accept: application/sparql-results+json"
```

## Integration Examples

### Python (using `requests` + `rdflib`)
```python
import requests
from urllib.parse import urlencode

def query_sparql(sparql_query):
    url = "http://localhost:3030/srs4autism/query"
    params = urlencode({"query": sparql_query})
    response = requests.get(f"{url}?{params}", 
                           headers={"Accept": "text/csv"})
    return response.text

# Execute query
result = query_sparql("""
PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?word WHERE { ?word a srs-kg:Word } LIMIT 10
""")
```

### JavaScript/TypeScript
```typescript
async function querySPARQL(query: string) {
  const url = "http://localhost:3030/srs4autism/query";
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/sparql-results+json" },
    body: new URLSearchParams({ query })
  });
  return response.json();
}
```

## Knowledge Graph Statistics

- **Total Words:** 8,712 words with HSK levels
- **Total Characters:** ~15,000+ Chinese characters
- **Total Concepts:** 29,431 concepts (synsets)
- **Relationships:** 
  - `composedOf` - word composition
  - `means` - word-to-concept mapping
  - `isSynonymOf` - concept relationships
  - `requiresPrerequisite` - learning dependencies

## Next Steps

1. Integrate with Curious Mario backend API
2. Build recommendation endpoints
3. Implement Knowledge Tracing
4. Create "看图说话" (picture-based exercises)

