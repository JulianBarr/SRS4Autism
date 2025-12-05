from dataclasses import dataclass
from typing import Any, Dict, Optional

from .memory import AgentMemory
from .principles import PrincipleStore
from .tools import AgentTools


@dataclass
class AgentPlan:
    """
    Learning plan returned by the agentic planner.
    
    The agent is now a "learning agent" that determines WHAT to learn,
    not just HOW to generate cards.
    """
    learner_level: str
    topic: Optional[str]  # May be None if determined by recommender
    topic_complexity: Optional[str]
    scaffold_type: Optional[str]  # Determined by recommender or principles
    rationale: str
    cognitive_prior: Dict[str, Any]  # The synthesized cognitive state
    recommendation_plan: Optional[Dict[str, Any]] = None  # Plan from recommender
    cards_payload: Optional[Dict[str, Any]] = None  # Generated cards if needed


class AgenticPlanner:
    """
    Cognitive State Synthesis Engine - A Learning Agent, not just a card generator.
    
    This agent:
    1. Queries mastery vector (from Anki review history)
    2. Queries world model (knowledge graph)
    3. Queries user profile (from memory)
    4. Synthesizes a "cognitive prior" (best estimate of child's cognitive state)
    5. Calls the recommender with this prior to determine WHAT to learn
    6. Returns a learning plan (not just cards)
    
    The agent solves "what to learn" by integrating with the recommender system.
    """

    def __init__(self, memory: Optional[AgentMemory] = None, principles: Optional[PrincipleStore] = None, tools: Optional[AgentTools] = None) -> None:
        self.memory = memory or AgentMemory()
        self.principles = principles or PrincipleStore()
        self.tools = tools or AgentTools()

    def synthesize_cognitive_prior(self, user_id: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesize the cognitive prior by querying:
        - Mastery vector (what the child has mastered)
        - World model/KG (knowledge structure and dependencies)
        - User profile (preferences and learning style)
        
        This is the "best effort prior" of the child's cognitive state.
        """
        # 1. Query mastery vector (from Anki review history)
        print("  📊 Querying mastery vector from Anki...")
        mastery_vector = self.tools.query_mastery_vector(user_id)
        print(f"  ✅ Mastery vector: {len(mastery_vector)} nodes")
        
        # 2. Query world model (knowledge graph)
        print(f"  🌐 Querying knowledge graph{' for topic: ' + topic if topic else ''}...")
        kg_context = self.tools.query_world_model(topic=topic)
        print("  ✅ Knowledge graph context retrieved")
        
        # 3. Query user profile
        print("  👤 Querying user profile...")
        profile = self.tools.query_user_profile(user_id, self.memory)
        print("  ✅ User profile retrieved")
        
        # Synthesize the prior
        cognitive_prior = {
            "mastery_vector": mastery_vector,
            "kg_context": kg_context,
            "profile": profile,
            "mastery_summary": {
                "total_nodes": len(mastery_vector),
                "mastered_nodes": sum(1 for v in mastery_vector.values() if v >= 0.85),
                "weak_nodes": sum(1 for v in mastery_vector.values() if 0.0 < v < 0.45),
                "unlearned_nodes": sum(1 for v in mastery_vector.values() if v == 0.0),
            },
        }
        
        return cognitive_prior

    def plan_learning_step(
        self,
        user_id: str,
        topic: Optional[str] = None,
        learner_level: Optional[str] = None,
        topic_complexity: Optional[str] = None,
    ) -> AgentPlan:
        """
        Plan a learning step by:
        1. Synthesizing cognitive prior
        2. Calling recommender with the prior
        3. Generating content if needed
        
        The agent determines WHAT to learn, not just generates cards for a given topic.
        """
        # Get user profile
        profile = self.memory.get_profile(user_id)
        resolved_level = learner_level or profile.get("level") or "novice"
        
        # STEP 1: Synthesize cognitive prior
        print("🔍 Step 1: Synthesizing cognitive prior...")
        cognitive_prior = self.synthesize_cognitive_prior(user_id, topic)
        print(f"✅ Cognitive prior synthesized: {len(cognitive_prior.get('mastery_vector', {}))} nodes tracked")
        
        # STEP 2: Call recommender with the prior
        print("🎯 Step 2: Calling recommender to determine next learning step...")
        recommendation_plan = self.tools.call_recommender(
            user_id=user_id,
            cognitive_prior=cognitive_prior,
        )
        print(f"✅ Recommender returned: {recommendation_plan.get('decision', 'UNKNOWN')} - {recommendation_plan.get('plan_title', 'No plan')}")
        
        # STEP 3: Generate rationale based on the synthesis
        mastery_summary = cognitive_prior.get("mastery_summary", {})
        rationale = (
            f"Analyzed cognitive state: {mastery_summary.get('mastered_nodes', 0)} mastered, "
            f"{mastery_summary.get('weak_nodes', 0)} weak areas, "
            f"{mastery_summary.get('unlearned_nodes', 0)} unlearned nodes. "
            f"Recommender decision: {recommendation_plan.get('decision', 'UNKNOWN')}. "
            f"Plan: {recommendation_plan.get('plan_title', 'No plan')}."
        )
        
        # STEP 4: Generate cards if the plan requires it
        cards_result = None
        task_details = recommendation_plan.get("task_details", {})
        scaffold_type = task_details.get("type")
        
        if scaffold_type and recommendation_plan.get("learning_task") == "scaffold":
            # Generate flashcards for the recommended learning task
            recommended_node = recommendation_plan.get("recommendations", [{}])[0] if recommendation_plan.get("recommendations") else {}
            node_label = recommended_node.get("label", topic or "learning content")
            
            prompt = f"Create {scaffold_type} practice for '{node_label}'."
            context_tags = {
                "type": scaffold_type,
                "node_id": recommended_node.get("node_id"),
                "level": resolved_level,
            }
            cards_result = self.tools.generate_flashcards(
                prompt=prompt,
                context_tags=context_tags,
                child_profile=profile or {},
            )
        
        # Determine topic from recommendation if not provided
        final_topic = topic
        if not final_topic and recommendation_plan.get("recommendations"):
            final_topic = recommendation_plan["recommendations"][0].get("label")
        
        # Determine complexity from mastery if not provided
        final_complexity = topic_complexity
        if not final_complexity:
            # Infer complexity from mastery levels
            avg_mastery = (
                sum(cognitive_prior["mastery_vector"].values()) / len(cognitive_prior["mastery_vector"])
                if cognitive_prior["mastery_vector"] else 0.5
            )
            if avg_mastery < 0.3:
                final_complexity = "high"
            elif avg_mastery < 0.6:
                final_complexity = "medium"
            else:
                final_complexity = "low"
        
        plan = AgentPlan(
            learner_level=resolved_level,
            topic=final_topic,
            topic_complexity=final_complexity,
            scaffold_type=scaffold_type,
            rationale=rationale,
            cognitive_prior=cognitive_prior,
            recommendation_plan=recommendation_plan,
            cards_payload=cards_result,
        )
        
        # Update memory with this interaction
        self.memory.append_history(
            user_id,
            {
                "topic": final_topic,
                "scaffold": scaffold_type,
                "decision": recommendation_plan.get("decision"),
                "plan_title": recommendation_plan.get("plan_title"),
                "reason": rationale,
            },
        )
        self.memory.update_profile(user_id, {"level": resolved_level})
        
        return plan

