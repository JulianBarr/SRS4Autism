import re
from typing import Dict, List, Any, Optional
from enum import Enum

class IntentType(Enum):
    CONVERSATION = "conversation"
    CARD_GENERATION = "card_generation"
    IMAGE_GENERATION = "image_generation"
    IMAGE_INSERTION = "image_insertion"
    CARD_UPDATE = "card_update"

class IntentDetector:
    """
    Detects user intent from chat messages to determine appropriate response type.
    
    Intents:
    - CONVERSATION: General chat, questions, greetings
    - CARD_GENERATION: Requests to create flashcards
    - IMAGE_GENERATION: Requests to generate images for cards
    - CARD_UPDATE: Requests to modify existing cards
    """
    
    def __init__(self):
        # Card generation keywords
        self.card_keywords = [
            "create", "generate", "make", "build", "card", "flashcard",
            "learn", "study", "practice", "quiz", "question", "answer",
            "cloze", "fill", "blank", "sentence", "word", "vocabulary",
            "grammar", "lesson", "exercise", "drill", "teach"
        ]
        
        # Image generation keywords
        self.image_keywords = [
            "image", "picture", "photo", "draw", "illustrate", "visual",
            "show", "display", "graphic", "art", "sketch", "diagram"
        ]
        
        # Image insertion keywords
        self.image_insertion_keywords = [
            "add", "insert", "put", "place", "attach", "include"
        ]
        
        # Card update keywords
        self.update_keywords = [
            "update", "modify", "change", "edit", "fix", "correct",
            "improve", "add", "remove", "delete", "replace"
        ]
        
        # Conversation keywords (greetings, questions, etc.)
        self.conversation_keywords = [
            "hello", "hi", "hey", "how", "what", "when", "where", "why",
            "help", "explain", "tell", "describe", "show", "can you",
            "thank", "thanks", "please", "sorry", "ok", "okay", "yes", "no"
        ]
    
    def detect_intent(self, message: str, context_tags: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detect the intent of a user message.
        
        Args:
            message: The user's message
            context_tags: Parsed @mentions for additional context
            
        Returns:
            Dict with intent type, confidence, and extracted entities
        """
        message_lower = message.lower().strip()
        
        # Check for explicit @mentions that indicate card generation
        if context_tags:
            for tag in context_tags:
                if tag.get("type") in ["word", "skill", "interest", "character", "template", "notetype"]:
                    return {
                        "intent": IntentType.CARD_GENERATION,
                        "confidence": 0.9,
                        "reason": f"Explicit @mention detected: {tag.get('type')}",
                        "entities": self._extract_entities(message, context_tags)
                    }
        
        # Check for image insertion intent (higher priority than generation)
        if self._has_image_insertion_intent(message_lower):
            return {
                "intent": IntentType.IMAGE_INSERTION,
                "confidence": 0.9,
                "reason": "Image insertion keywords detected",
                "entities": self._extract_entities(message, context_tags)
            }
        
        # Check for image generation intent
        if self._has_image_intent(message_lower):
            return {
                "intent": IntentType.IMAGE_GENERATION,
                "confidence": 0.8,
                "reason": "Image generation keywords detected",
                "entities": self._extract_entities(message, context_tags)
            }
        
        # Check for card update intent
        if self._has_update_intent(message_lower):
            return {
                "intent": IntentType.CARD_UPDATE,
                "confidence": 0.7,
                "reason": "Card update keywords detected",
                "entities": self._extract_entities(message, context_tags)
            }
        
        # Check for card generation intent
        if self._has_card_intent(message_lower):
            return {
                "intent": IntentType.CARD_GENERATION,
                "confidence": 0.8,
                "reason": "Card generation keywords detected",
                "entities": self._extract_entities(message, context_tags)
            }
        
        # Check for conversation intent
        if self._has_conversation_intent(message_lower):
            return {
                "intent": IntentType.CONVERSATION,
                "confidence": 0.7,
                "reason": "Conversation keywords detected",
                "entities": self._extract_entities(message, context_tags)
            }
        
        # Default to conversation for unclear messages
        return {
            "intent": IntentType.CONVERSATION,
            "confidence": 0.5,
            "reason": "No clear intent detected, defaulting to conversation",
            "entities": self._extract_entities(message, context_tags)
        }
    
    def _has_card_intent(self, message: str) -> bool:
        """Check if message indicates card generation intent."""
        # Look for card-related keywords
        for keyword in self.card_keywords:
            if keyword in message:
                return True
        
        # Look for patterns like "create a card for X"
        card_patterns = [
            r"create.*card",
            r"generate.*card",
            r"make.*card",
            r"card.*for",
            r"flashcard.*for",
            r"learn.*about",
            r"study.*about",
            r"practice.*with"
        ]
        
        for pattern in card_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _has_image_insertion_intent(self, message: str) -> bool:
        """Check if message indicates image insertion intent."""
        # Look for patterns like "add this image to card", "insert image to front"
        insertion_patterns = [
            r"add.*this.*image",
            r"insert.*image",
            r"put.*image",
            r"place.*image",
            r"attach.*image",
            r"include.*image",
            r"add.*to.*card",
            r"insert.*to.*card",
            r"put.*to.*card",
            r"place.*to.*card",
            r"insert.*picture",
            r"add.*picture",
            r"insert.*it.*card",
            r"add.*it.*card",
            r"insert.*the.*picture",
            r"add.*the.*picture"
        ]
        
        for pattern in insertion_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _has_image_intent(self, message: str) -> bool:
        """Check if message indicates image generation intent."""
        for keyword in self.image_keywords:
            if keyword in message:
                return True
        
        # Look for patterns like "generate image", "create picture", "draw"
        image_patterns = [
            r"generate.*image",
            r"create.*image",
            r"draw.*",
            r"illustrate.*",
            r"visual.*",
            r"picture.*of",
            r"image.*of"
        ]
        
        for pattern in image_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _has_update_intent(self, message: str) -> bool:
        """Check if message indicates card update intent."""
        for keyword in self.update_keywords:
            if keyword in message:
                return True
        
        # Look for patterns like "update card", "modify the last card"
        update_patterns = [
            r"update.*card",
            r"modify.*card",
            r"change.*card",
            r"edit.*card",
            r"fix.*card",
            r"improve.*card"
        ]
        
        for pattern in update_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _has_conversation_intent(self, message: str) -> bool:
        """Check if message indicates conversation intent."""
        # Check for greeting patterns
        greeting_patterns = [
            r"^(hello|hi|hey|good morning|good afternoon|good evening)",
            r"how are you",
            r"what can you do",
            r"help me",
            r"explain",
            r"tell me about"
        ]
        
        for pattern in greeting_patterns:
            if re.search(pattern, message):
                return True
        
        # Check for question patterns
        if message.endswith('?') or message.startswith(('what', 'how', 'when', 'where', 'why', 'can you', 'could you')):
            return True
        
        # Check for conversation keywords
        for keyword in self.conversation_keywords:
            if keyword in message:
                return True
        
        return False
    
    def _extract_entities(self, message: str, context_tags: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract relevant entities from the message."""
        entities = {
            "target_words": [],
            "card_references": [],
            "image_requests": [],
            "update_requests": []
        }
        
        # Extract target words (words after "for", "about", "with")
        target_patterns = [
            r"for\s+([a-zA-Z\u4e00-\u9fff]+)",
            r"about\s+([a-zA-Z\u4e00-\u9fff]+)",
            r"with\s+([a-zA-Z\u4e00-\u9fff]+)",
            r"the\s+word\s+([a-zA-Z\u4e00-\u9fff]+)",
            r"concept\s+([a-zA-Z\u4e00-\u9fff]+)",
            r"teach\s+([a-zA-Z\u4e00-\u9fff]+)"
        ]
        
        for pattern in target_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities["target_words"].extend(matches)
        
        # Extract card references
        card_ref_patterns = [
            r"card\s+(\d+)",
            r"last\s+card",
            r"that\s+card",
            r"the\s+card"
        ]
        
        for pattern in card_ref_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities["card_references"].extend(matches)
        
        # Extract image requests
        image_patterns = [
            r"image\s+of\s+([a-zA-Z\u4e00-\u9fff\s]+)",
            r"picture\s+of\s+([a-zA-Z\u4e00-\u9fff\s]+)",
            r"draw\s+([a-zA-Z\u4e00-\u9fff\s]+)"
        ]
        
        for pattern in image_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities["image_requests"].extend(matches)
        
        return entities
