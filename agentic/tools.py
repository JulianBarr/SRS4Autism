"""
Wrapper tools that expose existing logic to the new agentic layer.

The agent uses these tools to:
1. Query mastery vector (from Anki review history)
2. Query world model (knowledge graph)
3. Query user profile (from memory)
4. Call recommender with cognitive prior
5. Generate flashcards when needed
"""

import logging
from typing import Any, Dict, List, Optional

from agent.content_generator import ContentGenerator

# Configure logging
logger = logging.getLogger(__name__)


# Custom exceptions for better error handling
class AgentToolsError(Exception):
    """Base exception for AgentTools errors"""
    pass


class MasteryVectorError(AgentToolsError):
    """Raised when mastery vector query fails"""
    pass


class MasteryVectorTimeoutError(MasteryVectorError):
    """Raised when mastery vector query times out"""
    pass


class KnowledgeGraphError(AgentToolsError):
    """Raised when knowledge graph query fails"""
    pass


class KnowledgeGraphTimeoutError(KnowledgeGraphError):
    """Raised when knowledge graph query times out"""
    pass


class RecommenderError(AgentToolsError):
    """Raised when recommender fails"""
    pass


class RecommenderTimeoutError(RecommenderError):
    """Raised when recommender times out"""
    pass


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

        Raises:
            MasteryVectorTimeoutError: If query takes longer than 30 seconds
            MasteryVectorError: If query fails for any other reason
        """
        try:
            recommender = self._get_recommender()
            # Add timeout protection using threading (works in FastAPI)
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(recommender.build_mastery_vector)
                try:
                    mastery_vector = future.result(timeout=30)  # 30 second timeout
                    logger.info(f"Successfully retrieved mastery vector with {len(mastery_vector)} nodes for user {user_id}")
                    return mastery_vector
                except FutureTimeoutError as e:
                    logger.error(f"Mastery vector query timed out after 30 seconds for user {user_id}")
                    raise MasteryVectorTimeoutError(
                        f"Mastery vector query timed out after 30 seconds for user {user_id}"
                    ) from e
        except MasteryVectorTimeoutError:
            # Re-raise timeout errors as-is
            raise
        except Exception as e:
            logger.error(f"Failed to query mastery vector for user {user_id}: {e}", exc_info=True)
            raise MasteryVectorError(
                f"Failed to query mastery vector for user {user_id}: {str(e)}"
            ) from e

    def query_world_model(self, topic: Optional[str] = None, node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the knowledge graph (world model) for information about a topic or node.

        Args:
            topic: Optional topic to query (e.g., "math", "chinese")
            node_id: Optional specific node ID to query

        Returns:
            Dictionary with node information, dependencies, and structure

        Raises:
            KnowledgeGraphTimeoutError: If query takes longer than 15 seconds
            KnowledgeGraphError: If query fails for any other reason
        """
        import requests
        from urllib.parse import urlencode

        try:
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
                logger.debug(f"Querying KG for specific node: {node_id}")
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
                logger.debug(f"Querying KG for topic: {topic}")
            else:
                # General query for structure
                sparql = """
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                SELECT (COUNT(?node) AS ?total_nodes) WHERE {
                    ?node a srs-kg:Word .
                }
                """
                logger.debug("Querying KG for general structure")

            params = urlencode({"query": sparql})
            url = f"{self._kg_endpoint}?{params}"
            response = requests.get(url, headers={"Accept": "application/sparql-results+json"}, timeout=15)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully queried KG (endpoint: {self._kg_endpoint})")
            return result

        except requests.exceptions.Timeout as e:
            logger.error(f"Knowledge graph query timed out after 15 seconds (endpoint: {self._kg_endpoint})")
            raise KnowledgeGraphTimeoutError(
                f"Knowledge graph query timed out after 15 seconds (endpoint: {self._kg_endpoint})"
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Knowledge graph request failed: {e}", exc_info=True)
            raise KnowledgeGraphError(
                f"Knowledge graph request failed: {str(e)}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error querying knowledge graph: {e}", exc_info=True)
            raise KnowledgeGraphError(
                f"Unexpected error querying knowledge graph: {str(e)}"
            ) from e

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

        Raises:
            RecommenderTimeoutError: If recommender takes longer than 60 seconds
            RecommenderError: If recommender fails for any other reason

        Note:
            On timeout, returns a safe fallback with decision="REVIEW" to allow graceful degradation.
            Other errors will raise exceptions to signal true failures.
        """
        try:
            recommender = self._get_recommender()

            # Generate recommendations (recommender builds mastery vector internally)
            # Add timeout protection using threading (works in FastAPI)
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(recommender.generate_recommendations)
                try:
                    exploratory, remedial, mastery_vector = future.result(timeout=60)  # 60 second timeout
                except FutureTimeoutError as e:
                    logger.warning(f"Recommender timed out after 60 seconds for user {user_id}, returning fallback")
                    # Return a safe fallback response for timeout (graceful degradation)
                    return {
                        "decision": "REVIEW",
                        "plan_title": "Unable to generate recommendations (timeout)",
                        "learning_task": "rest",
                        "task_details": {},
                        "recommendations": [],
                        "mastery_summary": {
                            "total_tracked": 0,
                            "mastered_count": 0,
                        },
                        "timeout": True,  # Flag to indicate this is a timeout fallback
                    }
            
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
            
            result = {
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
            logger.info(f"Successfully generated recommendations for user {user_id}: {decision} with {len(recommendations)} items")
            return result

        except Exception as e:
            logger.error(f"Failed to generate recommendations for user {user_id}: {e}", exc_info=True)
            raise RecommenderError(
                f"Failed to generate recommendations for user {user_id}: {str(e)}"
            ) from e

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

