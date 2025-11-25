import google.generativeai as genai
import os
import base64
from typing import Dict, List, Any, Optional
from datetime import datetime

class ConversationHandler:
    """
    Handles conversational interactions with the AI assistant.
    Provides helpful responses about the system, learning tips, and general chat.
    """
    
    def __init__(self, api_key: str = None):
        if api_key:
            genai.configure(api_key=api_key)
        else:
            # Try to get from environment
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
        
        # Initialize the model for text generation - upgraded to Gemini 2.5 Flash
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # Initialize the model for image generation - will try multiple models at generation time
        # Models are tried in order: gemini-2.5-flash-image, then gemini-2.0-flash-exp-image-generation
        # Note: For Imagen 4, we may need to use Vertex AI API instead
        self.image_model = None  # Will be created dynamically during generation
        
        # Image generation is always enabled with Gemini
        self.image_generation_enabled = True
    
    def handle_conversation(self, message: str, context_tags: List[Dict[str, Any]] = None, 
                          child_profile: Dict[str, Any] = None,
                          chat_history: List[Dict[str, Any]] = None) -> str:
        """
        Handle conversational messages with context awareness.
        
        Args:
            message: The user's message
            context_tags: Parsed @mentions for context
            child_profile: Child's profile data
            chat_history: Recent chat history for context
            
        Returns:
            Conversational response
        """
        # Build context-aware prompt
        system_prompt = self._build_conversation_prompt(message, context_tags, child_profile, chat_history)
        
        try:
            print("\n" + "="*80)
            print("💬 CONVERSATION HANDLER - SENDING TO GEMINI:")
            print("-"*80)
            print(system_prompt)
            print("="*80 + "\n")
            
            response = self.model.generate_content(system_prompt)
            content = response.text
            
            print("\n" + "="*80)
            print("💬 CONVERSATION RESPONSE:")
            print("-"*80)
            print(content)
            print("="*80 + "\n")
            
            return content
            
        except Exception as e:
            print(f"Conversation handler error: {e}")
            return self._get_fallback_response(message)
    
    def _build_conversation_prompt(self, message: str, context_tags: List[Dict[str, Any]] = None,
                                 child_profile: Dict[str, Any] = None,
                                 chat_history: List[Dict[str, Any]] = None) -> str:
        """Build a context-aware conversation prompt."""
        
        prompt_parts = [
            "You are Curious Mario (好奇马力), a helpful AI assistant specialized in supporting parents and caregivers of children with autism.",
            "Your role is to provide friendly, informative, and supportive conversation about learning, education, and the Curious Mario system.",
            "",
            "**Your Capabilities:**",
            "- Help with learning strategies for children with autism",
            "- Explain how to use the Curious Mario flashcard system",
            "- Provide tips for creating effective educational content",
            "- Answer questions about child development and learning",
            "- Offer encouragement and support",
            "",
            "**Response Guidelines:**",
            "- Be warm, friendly, and supportive",
            "- Use simple, clear language",
            "- Provide practical, actionable advice",
            "- Ask follow-up questions when appropriate",
            "- Keep responses concise but helpful",
            ""
        ]
        
        # Add child profile context if available
        if child_profile:
            profile_context = self._build_profile_context(child_profile)
            prompt_parts.append(f"**Child Profile Context:**\n{profile_context}\n")
        
        # Add recent chat history for context
        if chat_history and len(chat_history) > 0:
            prompt_parts.append("**Recent Conversation Context:**")
            # Include last 3 messages for context
            recent_messages = chat_history[-3:] if len(chat_history) > 3 else chat_history
            for msg in recent_messages:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")
        
        # Add the current message
        prompt_parts.extend([
            "**Current User Message:**",
            message,
            "",
            "**Instructions:**",
            "Respond naturally and helpfully to this message. If the user is asking about:",
            "- Card creation: Suggest they use specific @mentions like @word:apple or @interest:trains",
            "- System features: Explain how to use the different tabs and features",
            "- Learning strategies: Provide specific, practical advice",
            "- General questions: Answer helpfully and ask if they need more specific help",
            "",
            "Keep your response conversational and supportive. Don't generate flashcards unless explicitly asked."
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_profile_context(self, child_profile: Dict[str, Any]) -> str:
        """Build formatted profile context string."""
        parts = []
        if child_profile.get("name"):
            parts.append(f"Child's name: {child_profile['name']}")
        if child_profile.get("dob"):
            # Calculate age
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
    
    def _get_fallback_response(self, message: str) -> str:
        """Provide a fallback response when AI is unavailable."""
        # Simple keyword-based responses
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm here to help you with your child's learning journey. How can I assist you today?"
        
        elif any(word in message_lower for word in ["help", "what can you do"]):
            return "I can help you with learning strategies, explain how to use the flashcard system, and provide tips for creating educational content. What would you like to know more about?"
        
        elif any(word in message_lower for word in ["card", "flashcard"]):
            return "To create flashcards, you can use the chat with specific @mentions like @word:apple or @interest:trains. Or you can ask me to 'create a card for [topic]' and I'll help you generate it!"
        
        elif "?" in message:
            return "That's a great question! I'd be happy to help you with that. Could you provide a bit more detail about what you're looking for?"
        
        else:
            return "I'm here to help! You can ask me about learning strategies, how to use the flashcard system, or anything else related to your child's education. What would you like to know?"
    
    def _generate_image_description(self, card_content: Dict[str, Any], user_request: str, 
                                  child_profile: Dict[str, Any] = None) -> str:
        """Generate a detailed image description for a flashcard."""
        
        # Build context for image generation
        context_parts = []
        if child_profile:
            if child_profile.get("name"):
                context_parts.append(f"Child's name: {child_profile['name']}")
            if child_profile.get("interests"):
                context_parts.append(f"Interests: {', '.join(child_profile['interests'])}")
            if child_profile.get("character_roster"):
                context_parts.append(f"Favorite Characters: {', '.join(child_profile['character_roster'])}")
        
        context_str = "\n".join(context_parts) if context_parts else "No specific context available"
        
        # Build image generation prompt
        prompt = f"""You are an expert at creating detailed image descriptions for educational flashcards for children with autism.

**Child Context:**
{context_str}

**Flashcard Content:**
Front: {card_content.get('front', '')}
Back: {card_content.get('back', '')}
Card Type: {card_content.get('card_type', 'basic')}

**User Request:**
{user_request}

**Instructions:**
Create a detailed, vivid description of an image that would be perfect for this flashcard. The image should be:

1. **Child-friendly**: Simple, colorful, and engaging for a child with autism
2. **Educational**: Clearly illustrates the concept being taught
3. **Appropriate**: Age-appropriate and culturally sensitive
4. **Visual**: Rich in visual details that can be easily rendered
5. **Inclusive**: Consider the child's interests and character preferences

**Image Description Guidelines:**
- Be specific about colors, shapes, and composition
- Include details about the setting, characters, and objects
- Make it vivid and easy to visualize
- Keep it simple but engaging
- Consider the child's interests if mentioned

**Output:**
Provide a detailed image description that an artist could use to create the perfect illustration for this flashcard. Be specific about visual elements, colors, composition, and style.

**Example Format:**
"A simple, colorful illustration showing [main subject] in [setting]. The image features [key elements] with [color scheme]. The style should be [artistic style] with [specific details]."

Generate the image description now:"""

        try:
            print("\n" + "="*80)
            print("🎨 IMAGE GENERATION - SENDING TO GEMINI:")
            print("-"*80)
            print(prompt)
            print("="*80 + "\n")
            
            response = self.model.generate_content(prompt)
            content = response.text
            
            print("\n" + "="*80)
            print("🎨 IMAGE DESCRIPTION GENERATED:")
            print("-"*80)
            print(content)
            print("="*80 + "\n")
            
            return content
            
        except Exception as e:
            print(f"Image description generation error: {e}")
            return f"A simple, colorful illustration showing the concept from the flashcard: '{card_content.get('front', '')}' - '{card_content.get('back', '')}'. The image should be child-friendly, educational, and visually engaging with bright colors and clear, simple shapes."
    
    def generate_actual_image(self, image_description: str, user_request: str = "") -> Dict[str, Any]:
        """Generate an image using Gemini 2.5 Flash Image Generation model (Nano Banana) or Imagen 4."""
        
        # Create a more specific prompt for Gemini image generation
        gemini_prompt = f"""Create a simple, child-friendly illustration for an educational flashcard.

Description: {image_description}

Requirements:
- Style: clean, colorful, simple shapes
- Suitable for children with autism
- No text in the image
- Clear, bold outlines
- Bright, engaging colors
- Simple composition with single focus

Generate an image that matches this description exactly."""

        print(f"Prompt: {gemini_prompt}")
        
        # Try different model names in order of preference
        model_names_to_try = [
            ('models/gemini-2.5-flash-image', 'Gemini 2.5 Flash Image'),
            ('models/gemini-2.0-flash-exp-image-generation', 'Gemini 2.0 Flash Exp Image Generation'),
        ]
        
        for model_name, model_desc in model_names_to_try:
            try:
                print(f"\n🎨 GENERATING IMAGE WITH {model_desc}:")
                print(f"Description: {image_description}")
                print(f"User Request: {user_request}")
                
                # Create model instance for this attempt
                image_model = genai.GenerativeModel(model_name)
                
                # Use Gemini's image generation model with proper configuration
                response = image_model.generate_content(
                    gemini_prompt,
                    generation_config={
                        "response_modalities": ["TEXT", "IMAGE"],
                        "temperature": 0.7,
                        "max_output_tokens": 8192,
                    }
                )
            
                print(f"Response type: {type(response)}")
                print(f"Response parts: {len(response.parts) if hasattr(response, 'parts') else 'No parts'}")
                
                # Check if response contains an image
                if hasattr(response, 'parts') and response.parts:
                    for i, part in enumerate(response.parts):
                        print(f"Part {i}: {type(part)}")
                        if hasattr(part, 'inline_data') and part.inline_data:
                            print(f"Found image data in part {i}")
                            # Extract image data
                            image_data = part.inline_data.data
                            mime_type = part.inline_data.mime_type
                            
                            # Convert to base64 data URL
                            base64_data = base64.b64encode(image_data).decode('utf-8')
                            data_url = f"data:{mime_type};base64,{base64_data}"
                            
                            return {
                                "success": True,
                                "error": None,
                                "image_url": None,  # Gemini doesn't provide URLs
                                "image_data": data_url,
                                "prompt_used": gemini_prompt,
                                "is_placeholder": False
                            }
                        elif hasattr(part, 'text') and part.text:
                            print(f"Part {i} text: {part.text[:100]}...")
                
                # If no image was generated, try a different approach
                print("No image found in response, trying fallback approach...")
                fallback_prompt = f"Generate an image: {image_description}"
                fallback_response = image_model.generate_content(
                    fallback_prompt,
                    generation_config={
                        "response_modalities": ["TEXT", "IMAGE"],
                        "temperature": 0.7,
                    }
                )
                
                if hasattr(fallback_response, 'parts') and fallback_response.parts:
                    for i, part in enumerate(fallback_response.parts):
                        print(f"Fallback part {i}: {type(part)}")
                        if hasattr(part, 'inline_data') and part.inline_data:
                            print(f"Found image data in fallback part {i}")
                            image_data = part.inline_data.data
                            mime_type = part.inline_data.mime_type
                            base64_data = base64.b64encode(image_data).decode('utf-8')
                            data_url = f"data:{mime_type};base64,{base64_data}"
                            
                            return {
                                "success": True,
                                "error": None,
                                "image_url": None,
                                "image_data": data_url,
                                "prompt_used": fallback_prompt,
                                "is_placeholder": False
                            }
                
                # If still no image, try next model
                print(f"⚠️  {model_desc} did not generate an image, trying next model...")
                continue
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️  Error with {model_desc}: {error_msg}")
                # If it's a 404 (model not found), try next model
                if "404" in error_msg or "not found" in error_msg.lower():
                    print(f"   Model {model_name} not available, trying next option...")
                    continue
                else:
                    # For other errors, try next model but log the error
                    continue
        
        # If all models failed, return error
        return {
            "success": False,
            "error": f"Image generation failed: None of the available models could generate an image. Please check that you have access to Gemini image generation models or consider using Vertex AI Imagen 4.",
            "image_url": None,
            "image_data": None
        }
