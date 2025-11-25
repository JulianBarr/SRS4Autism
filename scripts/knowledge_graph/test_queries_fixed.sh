#!/bin/bash
# Fixed SPARQL queries with all required prefixes
# Usage: ./test_queries_fixed.sh

FUSEKI_ENDPOINT="http://localhost:3030/srs4autism/query"

echo "=========================================="
echo "Test 1: Find word '朋友' (friend)"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?word ?pinyin ?hsk WHERE {
    ?word a srs-kg:Word ;
          srs-kg:text "朋友"@zh .
    OPTIONAL { ?word srs-kg:pinyin ?pinyin . }
    OPTIONAL { ?word srs-kg:hskLevel ?hsk . }
}' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 2: Find all knowledge points for word '朋友'"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?kp ?object ?objectLabel WHERE {
    srs-kg:word-朋友 ?kp ?object .
    ?kp rdfs:subPropertyOf srs-kg:KnowledgePoint .
    OPTIONAL { ?object rdfs:label ?objectLabel . }
} ORDER BY ?kp' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 3: Find characters that compose word '朋友'"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?char ?charLabel WHERE {
    srs-kg:word-朋友 srs-kg:composedOf ?char .
    ?char rdfs:label ?charLabel .
}' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 4: Verify KnowledgePoint is a property (not a class)"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?type WHERE {
    srs-kg:KnowledgePoint a ?type .
}' | python3 -m json.tool


