"""
Wrapper tools that expose existing logic to the new agentic layer.

The agent uses these tools to:
1. Query mastery vector (from Anki review history)
2. Query world model (knowledge graph)
3. Query user profile (from memory)
4. Call recommender with cognitive prior
5. Generate flashcards when needed
"""

from typing import Any, Dict, List, Optional

from agent.content_generator import ContentGenerator
# Lazy imports to avoid circular dependencies
def _get_build_cuma_remarks():
    from backend.app.main import build_cuma_remarks
    return build_cuma_remarks


class AgentTools:
    """
    Tools for the agentic learning agent.

    These tools allow the agent to:
    - Query cognitive state (mastery, KG, profile)
    - Get learning recommendations
    - Generate content when needed
    """

    def __init__(self) -> None:
        self.generator = ContentGenerator()
        self._recommender = None
        self._kg_endpoint = "http://localhost:3030/srs4autism/query"

    def _get_recommender(self):
        """Lazy load the recommender to avoid import issues."""
        if self._recommender is None:
            from scripts.knowledge_graph.curious_mario_recommender import (
                CuriousMarioRecommender,
                RecommenderConfig,
            )
            config = RecommenderConfig()
            self._recommender = CuriousMarioRecommender(config)
        return self._recommender

    def query_mastery_vector(self, user_id: str) -> Dict[str, float]:
        """
        Query the mastery vector for a user based on Anki review history.
        
        Returns a dictionary mapping knowledge graph node IDs to mastery scores (0.0-1.0).
        """
        try:
            recommender = self._get_recommender()
            mastery_vector = recommender.build_mastery_vector()
            return mastery_vector
        except Exception as e:
            # If Anki is not available, return empty vector
            return {}

    def query_world_model(self, topic: Optional[str] = None, node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the knowledge graph (world model) for information about a topic or node.
        
        Args:
            topic: Optional topic to query (e.g., "math", "chinese")
            node_id: Optional specific node ID to query
            
        Returns:
            Dictionary with node information, dependencies, and structure
        """
        try:
            import requests
            from urllib.parse import urlencode
            
            if node_id:
                # Query specific node with prerequisites
                sparql = f"""
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?node ?label ?hsk ?prereq WHERE {{
                    BIND(<http://srs4autism.com/schema/{node_id}> AS ?node)
                    ?node rdfs:label ?label .
                    OPTIONAL {{ ?node srs-kg:hskLevel ?hsk }}
                    OPTIONAL {{ ?node srs-kg:requiresPrerequisite ?prereq }}
                }}
                """
            elif topic:
                # Query nodes related to topic
                sparql = f"""
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?node ?label ?hsk ?prereq WHERE {{
                    ?node a srs-kg:Word ;
                          rdfs:label ?label .
                    OPTIONAL {{ ?node srs-kg:hskLevel ?hsk }}
                    OPTIONAL {{ ?node srs-kg:requiresPrerequisite ?prereq }}
                    FILTER(CONTAINS(LCASE(?label), LCASE("{topic}")))
                }}
                LIMIT 50
                """
            else:
                # General query for structure
                sparql = """
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT (COUNT(?node) AS ?total_nodes) WHERE {
                    ?node a srs-kg:Word .
                }
                """
            
            params = urlencode({"query": sparql})
            url = f"{self._kg_endpoint}?{params}"
            response = requests.get(url, headers={"Accept": "application/sparql-results+json"}, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "data": {}}

    def query_user_profile(self, user_id: str, memory) -> Dict[str, Any]:
        """
        Query user profile from memory.
        
        This is a convenience method that wraps memory.get_profile().
        """
        return memory.get_profile(user_id)

    def call_recommender(
        self,
        user_id: str,
        cognitive_prior: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call the recommender with a synthesized cognitive prior.
        
        Note: The recommender builds its own mastery vector from Anki.
        The cognitive_prior is provided for context and future enhancements,
        but the recommender uses its own data sources.
        
        Args:
            user_id: User identifier
            cognitive_prior: Dictionary containing:
                - mastery_vector: Dict[str, float] - mastery scores by node ID (for reference)
                - kg_context: Dict[str, Any] - knowledge graph context
                - profile: Dict[str, Any] - user profile/preferences
                
        Returns:
            Dictionary with recommendation plan:
                - decision: str - "EXPLORATORY", "REMEDIAL", or "REVIEW"
                - plan_title: str - human-readable plan name
                - learning_task: str - type of task ("scaffold", "review", "rest")
                - task_details: Dict - specific task parameters
                - recommendations: List[Dict] - list of recommended nodes
        """
        try:
            recommender = self._get_recommender()
            
            # Generate recommendations (recommender builds mastery vector internally)
            exploratory, remedial, mastery_vector = recommender.generate_recommendations()
            
            # Determine decision based on recommendations
            if remedial:
                # Prioritize remedial if there are items needing review
                top_remedial = remedial[0] if remedial else None
                decision = "REMEDIATE"
                plan_title = f"Review and strengthen: {top_remedial.label if top_remedial else 'weak areas'}"
                learning_task = "scaffold"
                task_details = {
                    "type": "cloze",  # Remedial typically uses cloze
                    "node_id": top_remedial.node_id if top_remedial else None,
                    "count": 5,
                }
                recommendations = [
                    {
                        "node_id": rec.node_id,
                        "label": rec.label,
                        "mastery": rec.mastery,
                        "type": "remedial",
                    }
                    for rec in remedial[:5]
                ]
            elif exploratory:
                # Use exploratory recommendations
                top_exploratory = exploratory[0]
                decision = "EXPLORATORY"
                plan_title = f"Learn: {top_exploratory.label}"
                learning_task = "scaffold"
                task_details = {
                    "type": "mcq",  # Exploratory typically starts with MCQ
                    "node_id": top_exploratory.node_id,
                    "count": 3,
                }
                recommendations = [
                    {
                        "node_id": rec.node_id,
                        "label": rec.label,
                        "mastery": rec.mastery,
                        "score": rec.score,
                        "type": "exploratory",
                    }
                    for rec in exploratory[:10]
                ]
            else:
                # No recommendations - might be fully mastered or prerequisites missing
                decision = "REVIEW"
                plan_title = "Review mastered content"
                learning_task = "review"
                task_details = {"type": "review", "count": 10}
                recommendations = []
            
            return {
                "decision": decision,
                "plan_title": plan_title,
                "learning_task": learning_task,
                "task_details": task_details,
                "recommendations": recommendations,
                "mastery_summary": {
                    "total_tracked": len(mastery_vector),
                    "mastered_count": sum(1 for v in mastery_vector.values() if v >= 0.85),
                },
            }
        except Exception as e:
            return {
                "error": str(e),
                "decision": "ERROR",
                "plan_title": "Unable to generate recommendations",
                "learning_task": "rest",
                "task_details": {},
                "recommendations": [],
            }

    def generate_flashcards(self, prompt: str, context_tags: Dict[str, Any], child_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate flashcards using the existing ContentGenerator but return
        structured metadata that the agent can reason over.
        """
        cards = self.generator.generate_from_prompt(
            user_prompt=prompt,
            context_tags=context_tags,
            child_profile=child_profile,
            prompt_template=None,
        )
        build_cuma_remarks = _get_build_cuma_remarks()
        for card in cards:
            remarks = build_cuma_remarks(card, [])
            card["field__Remarks"] = remarks
        return {"cards": cards}

