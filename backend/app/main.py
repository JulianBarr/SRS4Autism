from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime

app = FastAPI(title="Curious Mario API", version="1.0.0")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ChildProfile(BaseModel):
    id: Optional[str] = None  # Add ID field for unique identification
    name: str
    dob: str
    gender: str
    address: str
    school: str
    neighborhood: str
    interests: List[str]
    character_roster: Optional[List[str]] = []
    verbal_fluency: Optional[str] = None
    passive_language_level: Optional[str] = None
    raw_input: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None

class Card(BaseModel):
    id: str
    front: str
    back: str
    card_type: str  # "basic", "basic_reverse", "cloze", "interactive_cloze"
    cloze_text: Optional[str] = None
    text_field: Optional[str] = None  # For interactive cloze
    extra_field: Optional[str] = None  # Additional context
    note_type: Optional[str] = None  # Anki note type name
    tags: List[str] = []
    created_at: datetime
    status: str = "pending"  # "pending", "approved", "synced"
    image_description: Optional[str] = None  # AI-generated image description
    image_prompt: Optional[str] = None  # Prompt used for image generation
    image_url: Optional[str] = None  # URL of generated image
    image_data: Optional[str] = None  # Base64 encoded image data
    image_generated: Optional[bool] = None  # Whether image was successfully generated
    image_error: Optional[str] = None  # Error message if image generation failed
    is_placeholder: Optional[bool] = None  # Whether the image is a placeholder

class ChatMessage(BaseModel):
    id: str
    content: str
    role: str  # "user" or "assistant"
    timestamp: datetime
    mentions: List[str] = []

class AnkiProfile(BaseModel):
    name: str
    deck_name: str
    is_active: bool = True

class PromptTemplate(BaseModel):
    id: str
    name: str
    description: str
    template_text: str  # Free-form text with examples
    created_at: datetime
    updated_at: Optional[datetime] = None

# File paths for data storage
PROFILES_FILE = "data/profiles/child_profiles.json"
CARDS_FILE = "data/content_db/approved_cards.json"
ANKI_PROFILES_FILE = "data/profiles/anki_profiles.json"
CHAT_HISTORY_FILE = "data/content_db/chat_history.json"
PROMPT_TEMPLATES_FILE = "data/profiles/prompt_templates.json"

# Ensure data directories exist
os.makedirs("data/profiles", exist_ok=True)
os.makedirs("data/content_db", exist_ok=True)

def load_json_file(file_path: str, default: Any = None):
    """Load JSON data from file, return default if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default if default is not None else []

def save_json_file(file_path: str, data: Any):
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def parse_context_tags(content: str, mentions: List[str]) -> List[Dict[str, Any]]:
    """
    Parse @mentions from message content into structured context tags.
    
    Supports formats:
    - @profile:Alex -> {"type": "profile", "value": "Alex"}
    - @interest:trains -> {"type": "interest", "value": "trains"}
    - @word:红色 -> {"type": "word", "value": "红色"}
    - @skill:grammar-001 -> {"type": "skill", "value": "grammar-001"}
    - @character:Pinocchio -> {"type": "character", "value": "Pinocchio"}
    - @notetype:Interactive_Cloze -> {"type": "notetype", "value": "Interactive Cloze"}
    - @template:my_template -> {"type": "template", "value": "my_template"}
    - @Alex (plain mention) -> {"type": "profile", "value": "Alex"}
    """
    import re
    
    context_tags = []
    
    # Find special standalone @roster mention (no colon)
    # Match @roster as a whole word (not part of another word)
    if re.search(r'(?:^|[\s,])@roster(?:[\s,]|$)', content):
        context_tags.append({
            "type": "roster",
            "value": "roster"
        })
        print("✅ Detected @roster mention")
    
    # Find all @type:value patterns (including Unicode characters and underscores in values)
    # Pattern requires word boundary before @ to avoid matching @ inside values
    # Example: @template:English_Word_Cloze should NOT match @Word as a separate mention
    pattern = r'(?:^|[\s,])@(\w+):([^\s,@]+)'
    matches = re.findall(pattern, content)
    
    for tag_type, tag_value in matches:
        # Skip if it's roster:roster (old format)
        if tag_type == 'roster' and tag_value == 'roster':
            continue
        context_tags.append({
            "type": tag_type,
            "value": tag_value
        })
    
    # Add plain mentions as profile references
    for mention in mentions:
        # Check if this mention is already in context_tags
        already_added = any(t['value'] == mention for t in context_tags)
        if not already_added and mention != 'roster':
            context_tags.append({
                "type": "profile",
                "value": mention
            })
    
    return context_tags

# API Routes

@app.get("/")
async def root():
    return {"message": "Curious Mario API is running"}

# Child Profile endpoints
@app.get("/profiles", response_model=List[ChildProfile])
async def get_profiles():
    profiles = load_json_file(PROFILES_FILE, [])
    return profiles

@app.post("/profiles", response_model=ChildProfile)
async def create_profile(profile: ChildProfile):
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    from utils import generate_slug
    
    profiles = load_json_file(PROFILES_FILE, [])
    
    # Generate slug-based ID from name if not provided
    if not profile.id:
        profile.id = generate_slug(profile.name)
    
    # Ensure uniqueness
    existing_ids = [p.get("id") for p in profiles]
    if profile.id in existing_ids:
        # If ID already exists, append number
        counter = 2
        base_id = profile.id
        while f"{base_id}-{counter}" in existing_ids:
            counter += 1
        profile.id = f"{base_id}-{counter}"
    
    profiles.append(profile.dict())
    save_json_file(PROFILES_FILE, profiles)
    return profile

@app.get("/profiles/{profile_id}", response_model=ChildProfile)
async def get_profile(profile_id: str):
    profiles = load_json_file(PROFILES_FILE, [])
    for profile in profiles:
        if profile.get("name") == profile_id:
            return profile
    raise HTTPException(status_code=404, detail="Profile not found")

@app.put("/profiles/{profile_id}", response_model=ChildProfile)
async def update_profile(profile_id: str, updated_profile: ChildProfile):
    profiles = load_json_file(PROFILES_FILE, [])
    profile_found = False
    
    for i, profile in enumerate(profiles):
        if profile.get("name") == profile_id:
            profiles[i] = updated_profile.dict()
            profile_found = True
            break
    
    if not profile_found:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    save_json_file(PROFILES_FILE, profiles)
    return updated_profile

@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    profiles = load_json_file(PROFILES_FILE, [])
    initial_count = len(profiles)
    profiles = [profile for profile in profiles if profile.get("name") != profile_id]
    
    if len(profiles) == initial_count:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    save_json_file(PROFILES_FILE, profiles)
    return {"message": "Profile deleted successfully"}

# Card management endpoints
@app.get("/cards")
async def get_cards():
    cards = load_json_file(CARDS_FILE, [])
    # Normalize tags field - convert string to list if needed
    for card in cards:
        if isinstance(card.get('tags'), str):
            # Split comma-separated string into list
            card['tags'] = [t.strip() for t in card['tags'].split(',') if t.strip()]
    return cards

@app.post("/cards", response_model=Card)
async def create_card(card: Card):
    cards = load_json_file(CARDS_FILE, [])
    cards.append(card.dict())
    save_json_file(CARDS_FILE, cards)
    return card

@app.put("/cards/{card_id}/approve")
async def approve_card(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    for card in cards:
        if card["id"] == card_id:
            card["status"] = "approved"
            save_json_file(CARDS_FILE, cards)
            return {"message": "Card approved"}
    raise HTTPException(status_code=404, detail="Card not found")

@app.put("/cards/{card_id}")
async def update_card(card_id: str, updated_card: Card):
    cards = load_json_file(CARDS_FILE, [])
    card_found = False
    
    for i, card in enumerate(cards):
        if card["id"] == card_id:
            # Preserve the original ID
            card_data = updated_card.dict()
            card_data["id"] = card_id
            cards[i] = card_data
            card_found = True
            break
    
    if not card_found:
        raise HTTPException(status_code=404, detail="Card not found")
    
    save_json_file(CARDS_FILE, cards)
    return updated_card

@app.delete("/cards/{card_id}")
async def delete_card(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    initial_count = len(cards)
    cards = [card for card in cards if card["id"] != card_id]
    
    if len(cards) == initial_count:
        raise HTTPException(status_code=404, detail="Card not found")
    
    save_json_file(CARDS_FILE, cards)
    return {"message": "Card deleted successfully"}

# Chat endpoints
@app.get("/chat/history", response_model=List[ChatMessage])
async def get_chat_history():
    """Get chat history."""
    history = load_json_file(CHAT_HISTORY_FILE, [])
    return history

@app.delete("/chat/history")
async def clear_chat_history():
    """Clear chat history."""
    save_json_file(CHAT_HISTORY_FILE, [])
    return {"message": "Chat history cleared"}

@app.post("/chat", response_model=ChatMessage)
async def send_message(message: ChatMessage):
    try:
        # Save user message to history
        history = load_json_file(CHAT_HISTORY_FILE, [])
        history.append(message.dict())
        save_json_file(CHAT_HISTORY_FILE, history)
        
        # Import intent detection and conversation handler
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        
        try:
            from agent.intent_detector import IntentDetector, IntentType
            from agent.conversation_handler import ConversationHandler
            from agent.content_generator import ContentGenerator
            
            # Initialize handlers
            intent_detector = IntentDetector()
            conversation_handler = ConversationHandler()
            generator = ContentGenerator()
            
            # Parse @mentions from the message
            context_tags = parse_context_tags(message.content, message.mentions)
            
            # Detect user intent
            intent_result = intent_detector.detect_intent(message.content, context_tags)
            intent_type = intent_result["intent"]
            confidence = intent_result["confidence"]
            reason = intent_result["reason"]
            
            print(f"\n🎯 INTENT DETECTION:")
            print(f"   Intent: {intent_type.value}")
            print(f"   Confidence: {confidence}")
            print(f"   Reason: {reason}")
            print(f"   Entities: {intent_result.get('entities', {})}")
            
            # Get child profile from mentions if specified
            child_profile = None
            profiles = load_json_file(PROFILES_FILE, [])
            for mention in message.mentions:
                for profile in profiles:
                    # Match by ID (including slugs), then by name
                    # Handle both old UUIDs and new slugs
                    profile_id = profile.get("id", "").lower()
                    profile_name_slug = profile.get("name", "").lower().replace(" ", "-").replace("_", "-")
                    mention_normalized = mention.lower().replace("_", "-")
                    
                    if (profile_id == mention_normalized or 
                        profile.get("name") == mention or 
                        profile_name_slug == mention_normalized or
                        profile_id.endswith(mention_normalized) or  # For partial UUID matching
                        mention_normalized.endswith(profile_id)):
                        child_profile = profile
                        print(f"📋 Found profile: {profile.get('name')} (ID: {profile.get('id')})")
                        break
                if child_profile:
                    break
            
            # Handle different intents
            if intent_type == IntentType.CONVERSATION:
                # Handle conversational messages
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]  # Last 5 messages for context
                )
                
            elif intent_type == IntentType.CARD_GENERATION:
                # Handle card generation requests
                response_content = await _handle_card_generation(
                    message, context_tags, child_profile, generator, profiles
                )
                
            elif intent_type == IntentType.IMAGE_GENERATION:
                # Handle image generation requests
                response_content = await _handle_image_generation(
                    message, context_tags, child_profile, generator, profiles
                )
                
            elif intent_type == IntentType.IMAGE_INSERTION:
                # Handle image insertion requests
                response_content = await _handle_image_insertion(
                    message, context_tags, child_profile
                )
                
            elif intent_type == IntentType.CARD_UPDATE:
                # Handle card update requests (placeholder for now)
                response_content = "✏️ Card update feature is coming soon! For now, you can edit cards in the Card Curation tab."
                
            else:
                # Fallback to conversation
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]
                )
            
        except ImportError as e:
            print(f"Agent import error: {e}")
            # Fallback response when agent is not available
            response_content = f"I received your message: '{message.content}'. "
            response_content += "The AI agent is currently not available, but I can help you create flashcards manually. "
            response_content += "Please use the Card Curation tab to add cards."
            
    except Exception as e:
        print(f"Chat error: {e}")
        response_content = f"I encountered an error processing your message: '{message.content}'. Please try again."
    
    response = ChatMessage(
        id=f"resp_{datetime.now().timestamp()}",
        content=response_content,
        role="assistant",
        timestamp=datetime.now(),
        mentions=message.mentions
    )
    
    # Save assistant response to history
    history = load_json_file(CHAT_HISTORY_FILE, [])
    history.append(response.dict())
    save_json_file(CHAT_HISTORY_FILE, history)
    
    return response

async def _handle_card_generation(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                child_profile: Dict[str, Any], generator,
                                profiles: List[Dict[str, Any]]) -> str:
    """Handle card generation requests."""
    try:
        # Check for @roster mention - use entire character roster from profile
        has_roster_mention = any(tag.get("type") == "roster" for tag in context_tags)
        
        if has_roster_mention:
            # If no specific profile mentioned, use the first available profile
            if not child_profile and profiles:
                child_profile = profiles[0]
                print(f"📋 No profile specified with @roster, using first profile: {child_profile.get('name')}")
            
            if child_profile and child_profile.get("character_roster"):
                characters_str = ", ".join(child_profile["character_roster"])
                context_tags.append({
                    "type": "character_list",
                    "value": characters_str
                })
                print(f"🎭 Using character roster: {characters_str}")
        
        # Get prompt template if specified
        prompt_template = None
        for tag in context_tags:
            if tag.get("type") == "template":
                template_value = tag.get("value")
                templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
                print(f"Looking for template: {template_value}")
                print(f"Available templates: {[t.get('name') for t in templates]}")
                
                for tmpl in templates:
                    # Match by ID, name, or name with underscores/hyphens
                    # Normalize spaces, underscores, and hyphens for matching
                    template_name_normalized = tmpl.get("name", "").replace(' ', '_').lower()
                    template_value_normalized = template_value.replace('_', '_').replace('-', '_').lower()
                    
                    if (tmpl.get("id") == template_value or 
                        tmpl.get("name") == template_value or
                        template_name_normalized == template_value_normalized or
                        template_name_normalized.replace('_', '') == template_value_normalized.replace('_', '') or
                        tmpl.get("name", "").lower().replace(' ', '-') == template_value.lower().replace('_', '-')):
                        prompt_template = tmpl.get("template_text")
                        print(f"✅ Found template: {tmpl.get('name')}")
                        break
                
                if not prompt_template:
                    print(f"❌ Template not found: {template_value}")
        
        # Use the flexible agent method
        cards = generator.generate_from_prompt(
            user_prompt=message.content,
            context_tags=context_tags,
            child_profile=child_profile,
            prompt_template=prompt_template
        )
        
        # Save generated cards
        existing_cards = load_json_file(CARDS_FILE, [])
        for card in cards:
            existing_cards.append(card)
        save_json_file(CARDS_FILE, existing_cards)
        
        # Create response message
        response_content = f"✨ Generated {len(cards)} flashcard(s) from your request!\n\n"
        response_content += f"📝 Created {len([c for c in cards if c['card_type'] == 'basic'])} basic, "
        response_content += f"{len([c for c in cards if c['card_type'] == 'basic_reverse'])} reverse, "
        response_content += f"and {len([c for c in cards if c['card_type'] == 'cloze'])} cloze cards.\n\n"
        
        if context_tags:
            # For display, show profile name instead of ID
            tag_strings = []
            for t in context_tags:
                if t['type'] == 'profile' and child_profile:
                    tag_strings.append(f"profile={child_profile.get('name')}")
                else:
                    tag_strings.append(f"{t['type']}={t['value']}")
            response_content += f"🎯 Applied context: {', '.join(tag_strings)}\n\n"
        
        response_content += "👉 Review and approve them in the Card Curation tab!"
        
        return response_content
        
    except Exception as e:
        print(f"Card generation error: {e}")
        return f"I encountered an error generating cards: {str(e)}. Please try again with a different request."

async def _handle_image_generation(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                 child_profile: Dict[str, Any], generator,
                                 profiles: List[Dict[str, Any]]) -> str:
    """Handle image generation requests."""
    try:
        # Get recent cards to find the target card
        all_cards = load_json_file(CARDS_FILE, [])
        
        # Find the most recent card (last generated)
        if not all_cards:
            return "❌ No cards found to add images to. Please generate some cards first."
        
        # Get the last card (most recent)
        target_card = all_cards[-1]
        card_id = target_card["id"]
        
        print(f"🎨 Generating image for card: {card_id}")
        print(f"Card content: {target_card.get('front', '')} / {target_card.get('back', '')}")
        
        # Generate image using the LLM
        image_prompt = f"Create a simple, child-friendly illustration for this flashcard content: '{target_card.get('front', '')}' - '{target_card.get('back', '')}'. The image should be colorful, simple, and appropriate for a child with autism."
        
        # Use the conversation handler to generate image description
        from agent.conversation_handler import ConversationHandler
        conversation_handler = ConversationHandler()
        
        # Generate image description first
        image_description = conversation_handler._generate_image_description(
            card_content=target_card,
            user_request=message.content,
            child_profile=child_profile
        )
        
        # Generate actual image using DALL-E
        image_result = conversation_handler.generate_actual_image(
            image_description=image_description,
            user_request=message.content
        )
        
        # Update the card with image data
        target_card["image_description"] = image_description
        target_card["image_prompt"] = image_prompt
        
        if image_result["success"]:
            # Don't automatically add to card - show in chat first
            if image_result.get("is_placeholder", False):
                return f"🖼️ **Generated Image Description:**\n\n{image_description}\n\n⚠️ **Note:** This is a placeholder image. To generate actual images, integrate with an image generation service like DALL-E 3, Midjourney, or Stable Diffusion.\n\n💡 **Instructions:** {image_result.get('instructions', '')}\n\n**To add this image to a card, please specify:**\n- Which card (by ID or 'last card')\n- Front or back\n- Before or after the text"
            else:
                # Show the image in chat with options
                return f"🖼️ **Generated Image:**\n\n![Generated Image]({image_result['image_data']})\n\n**Image Description:**\n{image_description}\n\n**To add this image to a card, please specify:**\n- Which card (by ID or 'last card')\n- Front or back\n- Before or after the text\n\n**Example commands:**\n- 'Add this image to the last card, front, before text'\n- 'Insert image to card #123, back, after text'"
        else:
            # Fallback to description only
            target_card["image_generated"] = False
            target_card["image_error"] = image_result["error"]
            
            # Save updated card
            for i, card in enumerate(all_cards):
                if card["id"] == card_id:
                    all_cards[i] = target_card
                    break
            
            save_json_file(CARDS_FILE, all_cards)
            
            return f"🖼️ Generated image description for card '{target_card.get('front', 'Card')}':\n\n{image_description}\n\n❌ **Image generation failed:** {image_result['error']}\n\n💡 The description above can be used by an artist or image generation service."
        
    except Exception as e:
        print(f"Image generation error: {e}")
        return f"I encountered an error generating an image: {str(e)}. Please try again."

async def _handle_image_insertion(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                child_profile: Optional[Dict[str, Any]]) -> str:
    """Handle image insertion requests."""
    try:
        # Parse the insertion command to extract:
        # - Card reference (last card, card ID, etc.)
        # - Position (front/back)
        # - Location (before/after text)
        
        message_lower = message.content.lower()
        
        # Extract card reference
        card_ref = None
        if "last card" in message_lower:
            # Get the most recent card
            all_cards = load_json_file(CARDS_FILE)
            if all_cards:
                card_ref = all_cards[-1]
            else:
                return "❌ No cards found. Please create a card first."
        elif "card #" in message_lower or "card " in message_lower:
            # Extract card ID from message
            import re
            card_id_match = re.search(r'card\s*#?(\w+)', message_lower)
            if card_id_match:
                card_id = card_id_match.group(1)
                print(f"🔍 Looking for card ending with: {card_id}")
                all_cards = load_json_file(CARDS_FILE)
                print(f"🔍 Total cards: {len(all_cards)}")
                card_ref = next((card for card in all_cards if card["id"].endswith(card_id)), None)
                if not card_ref:
                    print(f"❌ Card #{card_id} not found in {len(all_cards)} cards")
                    return f"❌ Card #{card_id} not found."
                else:
                    print(f"✅ Found card: {card_ref['id']} (type: {card_ref.get('card_type', 'unknown')})")
        else:
            return "❌ Please specify which card to add the image to (e.g., 'last card', 'card #123')."
        
        # Extract position (front/back)
        position = "front"  # default
        if "back" in message_lower:
            position = "back"
        elif "front" in message_lower:
            position = "front"
        
        # Extract location (before/after text)
        location = "after"  # default
        if "before" in message_lower:
            location = "before"
        elif "after" in message_lower:
            location = "after"
        
        # Get the last generated image from chat history
        # For now, we'll need to store the last generated image somewhere
        # This is a simplified approach - in a real system, you'd store this in session state
        
        # Check if there's a recent image in the chat history
        chat_history = load_json_file(CHAT_HISTORY_FILE)
        last_image = None
        
        print(f"🔍 Searching for image in last {len(chat_history[-10:])} messages...")
        
        # Look for the most recent image generation in chat history
        for msg in reversed(chat_history[-10:]):  # Check last 10 messages
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                print(f"  Checking message: {content[:100]}...")
                
                if "Generated Image:" in content:
                    print(f"  ✅ Found 'Generated Image:' in message")
                    # Extract image data from the message
                    import re
                    img_match = re.search(r'!\[Generated Image\]\(([^)]+)\)', content)
                    if img_match:
                        last_image = img_match.group(1)
                        print(f"  ✅ Extracted image: {last_image[:50]}...")
                        break
                    else:
                        print(f"  ❌ No image pattern found in message")
        
        if not last_image:
            return "❌ No recent image found. Please generate an image first using commands like 'generate an image of [something]'."
        
        # Insert the image into the card
        # For Interactive Cloze cards, use text_field instead of front
        card_type = card_ref.get("card_type", "")
        is_interactive_cloze = card_type == "interactive_cloze"
        
        if position == "front":
            target_field = "text_field" if is_interactive_cloze else "front"
            current_content = card_ref.get(target_field, "") or card_ref.get("front", "")
            
            if location == "before":
                card_ref[target_field] = f"<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-bottom: 10px;\">\n{current_content}"
            else:  # after
                card_ref[target_field] = f"{current_content}\n<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-top: 10px;\">"
        else:  # back
            target_field = "extra_field" if is_interactive_cloze else "back"
            current_content = card_ref.get(target_field, "") or card_ref.get("back", "")
            
            if location == "before":
                card_ref[target_field] = f"<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-bottom: 10px;\">\n{current_content}"
            else:  # after
                card_ref[target_field] = f"{current_content}\n<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-top: 10px;\">"
        
        print(f"✅ Updated {target_field} for card {card_ref['id'][-6:]}")
        
        # Save the updated card
        all_cards = load_json_file(CARDS_FILE)
        card_updated = False
        for i, card in enumerate(all_cards):
            if card["id"] == card_ref["id"]:
                all_cards[i] = card_ref
                card_updated = True
                print(f"✅ Card updated in memory at index {i}")
                break
        
        if not card_updated:
            print(f"❌ Warning: Card {card_ref['id']} not found in cards list when trying to save!")
        else:
            save_json_file(CARDS_FILE, all_cards)
            print(f"✅ Card saved to file")
        
        return f"✅ Image successfully added to card #{card_ref['id'][-6:]}!\n\n**Position:** {position}\n**Location:** {location} text\n\nYou can view the updated card in the Card Curation tab."
        
    except Exception as e:
        print(f"Image insertion error: {e}")
        return f"I encountered an error inserting the image: {str(e)}. Please try again."

# Anki profile endpoints
@app.get("/anki-profiles", response_model=List[AnkiProfile])
async def get_anki_profiles():
    profiles = load_json_file(ANKI_PROFILES_FILE, [])
    return profiles

@app.post("/anki-profiles", response_model=AnkiProfile)
async def create_anki_profile(profile: AnkiProfile):
    profiles = load_json_file(ANKI_PROFILES_FILE, [])
    profiles.append(profile.dict())
    save_json_file(ANKI_PROFILES_FILE, profiles)
    return profile

# Prompt Template endpoints
@app.get("/templates", response_model=List[PromptTemplate])
async def get_templates():
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    return templates

@app.post("/templates", response_model=PromptTemplate)
async def create_template(template: PromptTemplate):
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    templates.append(template.dict())
    save_json_file(PROMPT_TEMPLATES_FILE, templates)
    return template

@app.put("/templates/{template_id}", response_model=PromptTemplate)
async def update_template(template_id: str, updated_template: PromptTemplate):
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    template_found = False
    
    for i, template in enumerate(templates):
        if template.get("id") == template_id:
            templates[i] = updated_template.dict()
            template_found = True
            break
    
    if not template_found:
        raise HTTPException(status_code=404, detail="Template not found")
    
    save_json_file(PROMPT_TEMPLATES_FILE, templates)
    return updated_template

@app.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    initial_count = len(templates)
    templates = [t for t in templates if t.get("id") != template_id]
    
    if len(templates) == initial_count:
        raise HTTPException(status_code=404, detail="Template not found")
    
    save_json_file(PROMPT_TEMPLATES_FILE, templates)
    return {"message": "Template deleted successfully"}

# AnkiConnect test endpoint
@app.get("/anki/test")
async def test_anki_connection():
    """Test connection to AnkiConnect."""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        
        anki = AnkiConnect()
        
        if anki.ping():
            decks = anki.get_deck_names()
            return {
                "status": "connected",
                "message": "AnkiConnect is running",
                "decks": decks
            }
        else:
            return {
                "status": "disconnected",
                "message": "Cannot connect to AnkiConnect"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# Get available Anki decks
@app.get("/anki/decks")
async def get_anki_decks():
    """Get list of all available Anki decks."""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        
        anki = AnkiConnect()
        
        if not anki.ping():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on."
            )
        
        decks = anki.get_deck_names()
        return {"decks": decks}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get available Anki note types
@app.get("/anki/note-types")
async def get_anki_note_types():
    """Get list of all available Anki note types."""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        
        anki = AnkiConnect()
        
        if not anki.ping():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on."
            )
        
        # Get model names (note types)
        note_types = anki._invoke("modelNames")
        return {"note_types": note_types}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Anki sync endpoint
@app.post("/anki/sync")
async def sync_to_anki(request: Dict[str, Any]):
    """
    Sync cards to Anki via AnkiConnect.
    
    Request body:
        {
            "deck_name": "My Deck",
            "card_ids": ["id1", "id2", ...]
        }
    """
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        
        deck_name = request.get("deck_name")
        card_ids = request.get("card_ids", [])
        
        if not deck_name:
            raise HTTPException(status_code=400, detail="deck_name is required")
        
        if not card_ids:
            raise HTTPException(status_code=400, detail="card_ids is required")
        
        # Get cards from database
        all_cards = load_json_file(CARDS_FILE, [])
        cards_to_sync = [card for card in all_cards if card["id"] in card_ids]
        
        if not cards_to_sync:
            raise HTTPException(status_code=404, detail="No cards found to sync")
        
        # Initialize AnkiConnect client
        anki = AnkiConnect()
        
        # Check connection
        if not anki.ping():
            raise HTTPException(
                status_code=503, 
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed."
            )
        
        # Sync cards
        print(f"🔄 Syncing {len(cards_to_sync)} cards to deck '{deck_name}'...")
        for card in cards_to_sync:
            print(f"  - Card {card['id']}: {card.get('card_type')} (status: {card.get('status')})")
        
        results = anki.sync_cards(deck_name, cards_to_sync)
        
        print(f"✅ Sync results: {results['total']} total, {len(results['success'])} success, {len(results['failed'])} failed")
        
        if results['failed']:
            for failure in results['failed']:
                print(f"  ❌ Failed: {failure['card_id']} - {failure['error']}")
        
        # Update card status to synced
        for card in all_cards:
            if card["id"] in [s["card_id"] for s in results["success"]]:
                card["status"] = "synced"
        
        save_json_file(CARDS_FILE, all_cards)
        
        return {
            "message": f"Synced {len(results['success'])} cards successfully",
            "results": results
        }
    
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"AnkiConnect module not found: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
