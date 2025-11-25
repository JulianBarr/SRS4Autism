#!/bin/bash
# Sample SPARQL queries to test the redesigned knowledge graph
# Usage: ./test_queries.sh

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
SELECT ?char ?charLabel WHERE {
    srs-kg:word-朋友 srs-kg:composedOf ?char .
    ?char rdfs:label ?charLabel .
}' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 4: Find concepts expressed by word '朋友' (using means)"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?concept ?conceptLabel WHERE {
    srs-kg:word-朋友 srs-kg:means ?concept .
    OPTIONAL { ?concept rdfs:label ?conceptLabel . }
} LIMIT 5' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 5: Find words that express a concept (using inverse property)"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?word ?wordLabel WHERE {
    ?concept srs-kg:isExpressedBy ?word .
    ?word srs-kg:text ?wordLabel .
    FILTER(CONTAINS(STR(?concept), "friend"))
} LIMIT 5' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 6: Count all knowledge point relationships"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
SELECT ?kp (COUNT(*) as ?count) WHERE {
    ?subject ?kp ?object .
    ?kp rdfs:subPropertyOf srs-kg:KnowledgePoint .
} GROUP BY ?kp ORDER BY DESC(?count)' | python3 -m json.tool

echo -e "\n=========================================="
echo "Test 7: Verify KnowledgePoint is a property, not a class"
echo "=========================================="
curl -s -X POST "$FUSEKI_ENDPOINT" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary 'PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?type WHERE {
    srs-kg:KnowledgePoint a ?type .
}' | python3 -m json.tool


