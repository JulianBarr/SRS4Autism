import google.generativeai as genai
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import os

class ContentGenerator:
    """
    AI Agent for flexible flashcard generation using @mention context injection.
    
    Instead of rigid card types, this agent accepts natural language prompts
    with @mentions to inject context (child profile, interests, grammar points, etc.)
    """
    
    def __init__(self, api_key: str = None):
        if api_key:
            genai.configure(api_key=api_key)
        else:
            # Try to get from environment
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
    
    def generate_from_prompt(self, user_prompt: str, context_tags: List[Dict[str, Any]] = None, 
                           child_profile: Dict[str, Any] = None, 
                           prompt_template: str = None) -> List[Dict[str, Any]]:
        """
        Flexible flashcard generation from natural language with @mention context.
        
        Args:
            user_prompt: The caregiver's natural language request
            context_tags: Parsed @mentions with type and value
                Example: [{"type": "word", "value": "红色"}, 
                         {"type": "interest", "value": "trains"}]
            child_profile: Child's profile data
            
        Returns:
            List of generated flashcards
        """
        # Build dynamic system prompt with injected context
        system_prompt = self._build_dynamic_system_prompt(user_prompt, context_tags, child_profile, prompt_template)
        
        try:
            print("\n" + "="*80)
            print("🤖 SENDING TO GEMINI:")
            print("-"*80)
            print(system_prompt)
            print("="*80 + "\n")
            
            response = self.model.generate_content(system_prompt)
            content = response.text
            
            print("\n" + "="*80)
            print("✨ GEMINI RESPONSE:")
            print("-"*80)
            print(content)
            print("="*80 + "\n")
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            
            # Parse the response - expect array of cards
            cards_data = json.loads(content.strip())
            
            # Ensure it's a list
            if not isinstance(cards_data, list):
                cards_data = [cards_data]
            
            # Add metadata to each card
            cards = []
            for card_data in cards_data:
                card_type = card_data.get("card_type", "basic")
                
                card = {
                    "id": str(uuid.uuid4()),
                    "card_type": card_type,
                    "front": card_data.get("front", ""),
                    "back": card_data.get("back", ""),
                    "tags": card_data.get("tags", []),
                    "created_at": datetime.now().isoformat(),
                    "status": "pending"
                }
                
                # Handle different card types
                if card_type == "interactive_cloze":
                    card["text_field"] = card_data.get("text_field", "")
                    card["extra_field"] = card_data.get("extra_field", "")
                    card["note_type"] = card_data.get("note_type", "Interactive Cloze")
                    card["cloze_text"] = None  # Not used for interactive cloze
                elif card_type == "cloze":
                    card["cloze_text"] = card_data.get("cloze_text")
                
                cards.append(card)
            
            return cards
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fallback: create a simple card from the prompt
            return [{
                "id": str(uuid.uuid4()),
                "front": f"Learn: {user_prompt}",
                "back": f"Generated from: {user_prompt}",
                "card_type": "basic",
                "tags": ["auto-generated"],
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }]
    
    def _build_dynamic_system_prompt(self, user_prompt: str, context_tags: List[Dict[str, Any]] = None,
                                    child_profile: Dict[str, Any] = None, 
                                    prompt_template: str = None) -> str:
        """Build a dynamic system prompt by injecting @mention context."""
        
        # If user provided a custom template, use it as the base
        if prompt_template:
            prompt_parts = [
                "You are an AI assistant specialized in creating educational flashcards for children with autism.",
                "",
                "**Custom Template Instructions:**",
                prompt_template,
                ""
            ]
        else:
            # Base system prompt
            prompt_parts = [
                "You are an AI assistant specialized in creating educational flashcards for children with autism.",
                ""
            ]
        
        # Add child profile context if available
        if child_profile:
            profile_context = self._build_profile_context(child_profile)
            prompt_parts.append(f"**Child Profile:**\n{profile_context}\n")
        
        # Add context from @mentions
        if context_tags:
            prompt_parts.append("**Required Context:**")
            for tag in context_tags:
                tag_type = tag.get("type", "")
                tag_value = tag.get("value", "")
                
                if tag_type == "word":
                    prompt_parts.append(f"- Target word/concept: {tag_value}")
                elif tag_type == "interest":
                    prompt_parts.append(f"- Must incorporate child's interest: {tag_value}")
                elif tag_type == "skill":
                    prompt_parts.append(f"- Must practice skill/grammar point: {tag_value}")
                elif tag_type == "profile":
                    prompt_parts.append(f"- Context from profile: {tag_value}")
                elif tag_type == "character":
                    # Handle slug-based character values (e.g., "peppa-pig" -> "Peppa Pig")
                    # Try to find original character name from child's roster
                    import re
                    character_name = tag_value
                    if child_profile and child_profile.get("character_roster"):
                        # Reverse lookup slug to original name
                        for original_char in child_profile["character_roster"]:
                            # Generate slug (Python version)
                            slug = original_char.lower()
                            slug = re.sub(r'\s+', '-', slug)
                            slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', slug)
                            slug = re.sub(r'-+', '-', slug)
                            if slug == tag_value or tag_value.replace('-', '').replace('_', '') in original_char.lower():
                                character_name = original_char
                                break
                    prompt_parts.append(f"- Feature this character: {character_name} (from child's favorite stories/movies)")
                elif tag_type == "character_list":
                    prompt_parts.append(f"- Choose from these characters: {tag_value}")
                    prompt_parts.append(f"  (Select the most appropriate character for this card)")
                elif tag_type == "roster":
                    prompt_parts.append(f"- Use characters from the child's character roster")
                elif tag_type == "notetype":
                    # Handle both slug-based (e.g., "basic-and-reversed-card") and original (e.g., "Basic (and reversed card)")
                    # Replace hyphens with spaces, then normalize
                    note_type_display = tag_value.replace('-', ' ').replace('_', ' ').strip()
                    prompt_parts.append(f"- REQUIRED: Use Anki note type '{note_type_display}'")
                    prompt_parts.append(f"  Set note_type field to '{note_type_display}'")
                elif tag_type == "actor":
                    prompt_parts.append(f"- Include this person/role: {tag_value}")
                else:
                    prompt_parts.append(f"- {tag_type}: {tag_value}")
            prompt_parts.append("")
        
        # Add user's goal
        prompt_parts.append(f"**User's Goal:**\n{user_prompt}\n")
        
        # Check if specific note type was requested
        requested_notetype = None
        if context_tags:
            for tag in context_tags:
                if tag.get("type") == "notetype":
                    requested_notetype = tag.get("value", "").replace('_', ' ')
        
        # ONLY add output format if NO custom template was provided
        # Custom templates should define their own output format
        if prompt_template:
            # Template defines its own format - just add JSON reminder
            print(f"✅ USING CUSTOM TEMPLATE - NO DEFAULT FORMAT APPENDED")
            prompt_parts.append("**Important:** Return ONLY valid JSON array, no extra text.")
        elif requested_notetype:
            prompt_parts.extend([
                "**Output Format:**",
                f"Generate 1-3 flashcards using the '{requested_notetype}' note type.",
                "",
                f"If '{requested_notetype}' is 'Interactive Cloze':",
                "- card_type: 'interactive_cloze'",
                f"- note_type: '{requested_notetype}'",
                "- text_field: Text with [[c1::answer]] [[c2::answer]] for blanks",
                "- extra_field: (optional) Additional context or hints",
                "- tags: Array of relevant tags",
                "",
                f"If '{requested_notetype}' is 'Basic':",
                "- card_type: 'basic'",
                "- front: The question or prompt",
                "- back: The answer",
                "- tags: Array of relevant tags",
                "",
                "Important:",
                "- Use [[c1::word]] syntax for interactive cloze (NOT {{c1::word}})",
                f"- MUST set note_type to '{requested_notetype}'",
                "- Make the cards simple and age-appropriate",
                "",
                "Return ONLY valid JSON array, no extra text."
            ])
        else:
            prompt_parts.extend([
                "**Output Format:**",
                "Generate 1-3 flashcards as a JSON array.",
                "",
                "Choose the best card type based on content:",
                "",
                "For Interactive Cloze cards (BEST for sentences with multiple blanks):",
                "- card_type: 'interactive_cloze'",
                "- note_type: 'Interactive Cloze'",
                "- text_field: Text with [[c1::answer]] [[c2::answer]] for blanks",
                "- extra_field: (optional) Additional context or hints",
                "- tags: Array of relevant tags",
                "",
                "For Basic cards (simple Q&A):",
                "- card_type: 'basic' or 'basic_reverse'",
                "- front: The question or prompt",
                "- back: The answer",
                "- tags: Array of relevant tags",
                "",
                "Important:",
                "- Use [[c1::word]] syntax for interactive cloze (NOT {{c1::word}})",
                "- Interactive cloze is best for sentences with multiple blanks",
                "- Basic cards for simple definitions",
                "- Make the cards simple and age-appropriate",
                "",
                "Return ONLY valid JSON array, no extra text."
            ])
        
        return "\n".join(prompt_parts)
    
    def _build_profile_context(self, child_profile: Dict[str, Any]) -> str:
        """Build formatted profile context string."""
        parts = []
        if child_profile.get("name"):
            parts.append(f"Name: {child_profile['name']}")
        if child_profile.get("dob"):
            # Calculate age
            from datetime import datetime
            try:
                dob = datetime.fromisoformat(child_profile['dob'].replace('Z', '+00:00'))
                age = (datetime.now() - dob).days // 365
                parts.append(f"Age: {age} years old")
            except:
                pass
        if child_profile.get("interests"):
            parts.append(f"Interests: {', '.join(child_profile['interests'])}")
        if child_profile.get("character_roster"):
            parts.append(f"Favorite Characters: {', '.join(child_profile['character_roster'])}")
        if child_profile.get("verbal_fluency"):
            parts.append(f"Verbal fluency: {child_profile['verbal_fluency']}")
        if child_profile.get("passive_language_level"):
            parts.append(f"Language level: {child_profile['passive_language_level']}")
        
        return "\n".join(parts) if parts else "No profile available"
    
    # Legacy methods for backward compatibility
    def generate_basic_card(self, topic: str, child_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a basic flashcard"""
        context = self._build_context(child_profile)
        
        prompt = f"""
        Create a basic flashcard for a child learning about: {topic}
        
        Child context: {context}
        
        Generate a simple, clear front and back for the card.
        The front should be a question or prompt.
        The back should be a clear, simple answer.
        
        Format as JSON:
        {{
            "front": "question or prompt",
            "back": "answer",
            "tags": ["tag1", "tag2"]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            content = response.text
            
            # Clean up the response to extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            
            card_data = json.loads(content.strip())
            
            return {
                "id": str(uuid.uuid4()),
                "front": card_data["front"],
                "back": card_data["back"],
                "card_type": "basic",
                "tags": card_data.get("tags", []),
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fallback to simple card if API fails
            return {
                "id": str(uuid.uuid4()),
                "front": f"What is {topic}?",
                "back": f"This is {topic}",
                "card_type": "basic",
                "tags": [topic.lower()],
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
    
    def generate_basic_reverse_card(self, topic: str, child_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a basic reverse flashcard"""
        context = self._build_context(child_profile)
        
        prompt = f"""
        Create a basic reverse flashcard for a child learning about: {topic}
        
        Child context: {context}
        
        Generate a card that works both ways:
        - Front to back: question to answer
        - Back to front: answer to question
        
        Format as JSON:
        {{
            "front": "question or prompt",
            "back": "answer",
            "tags": ["tag1", "tag2"]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            content = response.text
            
            # Clean up the response to extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            
            card_data = json.loads(content.strip())
            
            return {
                "id": str(uuid.uuid4()),
                "front": card_data["front"],
                "back": card_data["back"],
                "card_type": "basic_reverse",
                "tags": card_data.get("tags", []),
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fallback to simple card if API fails
            return {
                "id": str(uuid.uuid4()),
                "front": f"What is {topic}?",
                "back": f"This is {topic}",
                "card_type": "basic_reverse",
                "tags": [topic.lower()],
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
    
    def generate_cloze_card(self, topic: str, child_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a cloze deletion card"""
        context = self._build_context(child_profile)
        
        prompt = f"""
        Create a cloze deletion card for a child learning about: {topic}
        
        Child context: {context}
        
        Generate a sentence with a key word missing (marked with {{c1::word}}).
        The sentence should be simple and appropriate for the child's level.
        
        Format as JSON:
        {{
            "cloze_text": "sentence with {{c1::missing_word}}",
            "tags": ["tag1", "tag2"]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            content = response.text
            
            # Clean up the response to extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            
            card_data = json.loads(content.strip())
            
            return {
                "id": str(uuid.uuid4()),
                "front": card_data["cloze_text"],
                "back": card_data["cloze_text"],
                "card_type": "cloze",
                "cloze_text": card_data["cloze_text"],
                "tags": card_data.get("tags", []),
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fallback to simple cloze if API fails
            return {
                "id": str(uuid.uuid4()),
                "front": f"The {{c1::{topic}}} is important.",
                "back": f"The {{c1::{topic}}} is important.",
                "card_type": "cloze",
                "cloze_text": f"The {{c1::{topic}}} is important.",
                "tags": [topic.lower()],
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
    
    def _build_context(self, child_profile: Dict[str, Any] = None) -> str:
        """Build context string from child profile"""
        if not child_profile:
            return "No specific child profile available"
        
        context_parts = []
        if child_profile.get("name"):
            context_parts.append(f"Child's name: {child_profile['name']}")
        if child_profile.get("interests"):
            context_parts.append(f"Interests: {', '.join(child_profile['interests'])}")
        if child_profile.get("verbal_fluency"):
            context_parts.append(f"Verbal fluency: {child_profile['verbal_fluency']}")
        if child_profile.get("passive_language_level"):
            context_parts.append(f"Language level: {child_profile['passive_language_level']}")
        
        return "; ".join(context_parts) if context_parts else "No specific context available"
    
    def generate_cards_from_prompt(self, prompt: str, child_profile: Dict[str, Any] = None, 
                                 card_types: List[str] = None) -> List[Dict[str, Any]]:
        """Generate multiple cards from a natural language prompt"""
        if not card_types:
            card_types = ["basic", "basic_reverse", "cloze"]
        
        cards = []
        
        # Extract topic from prompt
        topic = self._extract_topic(prompt)
        
        for card_type in card_types:
            if card_type == "basic":
                cards.append(self.generate_basic_card(topic, child_profile))
            elif card_type == "basic_reverse":
                cards.append(self.generate_basic_reverse_card(topic, child_profile))
            elif card_type == "cloze":
                cards.append(self.generate_cloze_card(topic, child_profile))
        
        return cards
    
    def _extract_topic(self, prompt: str) -> str:
        """Extract main topic from prompt"""
        # Simple topic extraction - in the future this could be more sophisticated
        prompt_lower = prompt.lower()
        
        # Common topic indicators
        topic_indicators = [
            "about", "teach", "learn", "study", "practice"
        ]
        
        for indicator in topic_indicators:
            if indicator in prompt_lower:
                # Extract text after the indicator
                parts = prompt_lower.split(indicator, 1)
                if len(parts) > 1:
                    topic = parts[1].strip()
                    # Clean up the topic
                    topic = topic.split('.')[0].split('?')[0].split('!')[0].strip()
                    return topic
        
        # Fallback: return first few words
        words = prompt.split()[:3]
        return " ".join(words)

