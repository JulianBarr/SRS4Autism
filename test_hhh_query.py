import sys
import os
sys.path.append(os.path.abspath('backend'))
from database.kg_client import KnowledgeGraphClient

kg_client = KnowledgeGraphClient()

query = """
PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?moduleLabel ?submoduleLabel ?learningFocusLabel ?itemLabel ?targetLabel
WHERE {
    GRAPH <http://cuma.org/graph/heep-hong-language> {
        ?module a hhh-kg:Module ;
                rdfs:label ?moduleLabel .
        OPTIONAL {
            ?module hhh-kg:hasSubmodule ?submodule .
            ?submodule rdfs:label ?submoduleLabel .
            OPTIONAL {
                ?submodule hhh-kg:hasLearningFocus ?learningFocus .
                ?learningFocus rdfs:label ?learningFocusLabel .
                OPTIONAL {
                    ?learningFocus hhh-kg:hasCurriculumItem ?item .
                    ?item rdfs:label ?itemLabel .
                    OPTIONAL {
                        ?item hhh-kg:hasTarget ?target .
                        ?target rdfs:label ?targetLabel .
                    }
                }
            }
        }
    }
}
LIMIT 10
"""

results = kg_client.query(query)
for r in results:
    print(r)
