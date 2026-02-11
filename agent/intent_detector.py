import json
import logging
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class IntentType(Enum):
    CONVERSATION = "conversation"
    CARD_GENERATION = "card_generation"

class IntentDetector:
    """
    LLM-based Micro-Router.
    Uses the configured LLM to classify user intent and extract topics.
    """
    
    @staticmethod
    def detect_intent(message: str, api_key: Optional[str], provider: str = "google") -> Dict[str, Any]:
        """
        Classifies intent using a lightweight LLM call.
        Returns: {"intent": IntentType, "confidence": float, "topic": str | None}
        """
        # 1. Avoid circular imports by importing inside method
        from backend.app.services.agent_service import AgentService

        # 2. Fast, minimalist system prompt
        system_prompt = f"""
        You are an Intent Classifier for a Special Education App.
        
        INPUT: "{message}"
        
        TASK:
        1. Classify if the user wants to GENERATE FLASHCARDS/LEARNING MATERIALS or just CHAT.
        2. If generating, extract the TOPIC (word, concept, or subject).
        
        RULES:
        - "Teach me X", "Make cards for X", "Help me learn X", "@word:X" -> CARD_GENERATION
        - "Hi", "Who are you?", "Why is the sky blue?" -> CONVERSATION
        
        OUTPUT JSON ONLY:
        {{
            "intent": "CARD_GENERATION" or "CONVERSATION",
            "topic": "extracted string or null"
        }}
        """

        try:
            # 3. Call the "Micro-Router" (Cheap & Fast)
            # Use fastest models for routing
            model_name = "gemini-2.0-flash" if provider == "google" else "gpt-3.5-turbo"
            
            # Ensure we have an API key (AgentService._call_llm requires it)
            if not api_key:
                logger.warning("⚠️ No API key provided for intent detection. Defaulting to CONVERSATION.")
                return {"intent": IntentType.CONVERSATION, "confidence": 0.0, "extracted_topic": None}
            
            response_text = AgentService._call_llm(
                system_prompt=system_prompt,
                api_key=api_key,
                provider=provider,
                model_name=model_name
            )
            
            # 4. Parse Response
            clean = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            
            intent_str = data.get("intent", "CONVERSATION").upper()
            topic = data.get("topic")
            
            detected_intent = IntentType.CARD_GENERATION if intent_str == "CARD_GENERATION" else IntentType.CONVERSATION
            
            logger.info(f"🧠 Micro-Router: {intent_str} | Topic: {topic}")
            
            return {
                "intent": detected_intent,
                "confidence": 0.95, # LLMs are confident
                "extracted_topic": topic
            }
            
        except Exception as e:
            logger.error(f"Router Failed: {e}. Defaulting to Conversation.")
            return {"intent": IntentType.CONVERSATION, "confidence": 0.0, "extracted_topic": None}
