import sys
import os
sys.path.append(os.path.abspath('backend'))
from database.kg_client import KnowledgeGraphClient

kg_client = KnowledgeGraphClient()

query = """
PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX hhh-inst: <http://cuma.org/instance/hhh/>

SELECT ?moduleLabel ?submoduleLabel ?focusLabel ?itemLabel ?minAge ?maxAge ?targetLabel
WHERE {
    GRAPH <http://cuma.org/graph/heep-hong-language> {
        ?item a hhh-kg:CurriculumItem ;
              rdfs:label ?itemLabel .
        
        OPTIONAL { ?item hhh-kg:ageMinMonths ?minAge . }
        OPTIONAL { ?item hhh-kg:ageMaxMonths ?maxAge . }
        
        OPTIONAL {
            ?item hhh-kg:hasTarget ?target .
            ?target rdfs:label ?targetLabel .
        }
        
        # Go up the tree to find focus, submodule, module
        OPTIONAL {
            ?focus hhh-kg:hasCurriculumItem ?item ;
                   rdfs:label ?focusLabel .
            OPTIONAL {
                ?submodule hhh-kg:hasLearningFocus ?focus ;
                           rdfs:label ?submoduleLabel .
                OPTIONAL {
                    ?module hhh-kg:hasSubmodule ?submodule ;
                            rdfs:label ?moduleLabel .
                }
            }
        }
    }
}
LIMIT 20
"""

results = kg_client.query_bindings(query)
for r in results:
    print({k: v['value'] for k, v in r.items()})
