from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Set
import json
import os
import re
import asyncio
import logging
from datetime import datetime
from functools import partial, lru_cache
import base64
import collections
import unicodedata
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Adjust path to include backend root if needed
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from backend.database.db import get_db
from backend.database.services import ChatSessionService

# Database models (optional, for topic history endpoint)
try:
    from backend.database.models import Profile
except ImportError:
    Profile = None

# Internal imports
from ..core.config import (
    PROJECT_ROOT,
    CHAT_HISTORY_FILE,
    PROFILES_FILE,
    CARDS_FILE,
    PROMPT_TEMPLATES_FILE,
    MODEL_CONFIG_FILE
)
from ..utils.common import (
    load_json_file,
    save_json_file,
    normalize_to_slug,
    split_tag_annotations,
    contains_chinese_chars
)
from ..utils.pinyin_utils import get_word_knowledge, get_word_image_map

router = APIRouter()
logger = logging.getLogger(__name__)

# Agentic imports
try:
    from agentic import AgenticPlanner, AgentMemory, PrincipleStore, AgentTools
    from agentic.tools import (
        MasteryVectorError,
        KnowledgeGraphError,
        RecommenderError,
    )
    from agent.intent_detector import IntentDetector, IntentType
    from agent.conversation_handler import ConversationHandler
    from agent.content_generator import ContentGenerator
except ImportError as e:
    logger.warning(f"Agent imports failed: {e}")
    IntentDetector = None
    IntentType = None
    ConversationHandler = None
    ContentGenerator = None

# --- Models ---

class ChatMessage(BaseModel):
    id: str
    content: str
    role: str  # "user" or "assistant"
    timestamp: datetime
    mentions: List[str] = []
    config: Optional[Dict[str, str]] = None  # Optional model configuration: {"card_model": "...", "image_model": "..."}

# --- Helper Functions ---

def _normalize_model_name(model_name: str, base_url: str) -> str:
    """Normalizes model names based on the base_url, especially for SiliconFlow."""
    if "siliconflow" in base_url.lower():
        if model_name == "deepseek-chat":
            return "deepseek-ai/DeepSeek-V3"
        elif model_name == "deepseek-reasoner":
            return "deepseek-ai/DeepSeek-R1"
        elif model_name == "gpt-4o-mini":  # Fallback
            return "deepseek-ai/DeepSeek-V3"
        elif model_name == "gpt-3.5-turbo":  # Fallback
            return "deepseek-ai/DeepSeek-V3"
    return model_name

def expand_kp_template_variables(kp_pattern: str, context_tags: List[Dict[str, Any]]) -> str:
    """
    Expand template variables in knowledge point patterns.
    
    Supports variables:
    - {{word}} - the actual word (from @word: mention)
    - {{concept}} - the meaning/concept of the word (looked up from knowledge graph)
    - {{pronunciation}} - the pinyin pronunciation
    - {{hsk_level}} - the HSK level
    
    Example:
    - Input: "@{{word}}--means--{{concept}}"
    - If word is "读者" and concept is "reader", output: "@读者--means--reader"
    """
    if not kp_pattern or "{{" not in kp_pattern:
        return kp_pattern
    
    # Extract word from context_tags
    word_value = None
    for tag in context_tags:
        if tag.get("type") == "word":
            word_value = tag.get("value")
            break
    
    if not word_value:
        # No word found, return pattern as-is (variables won't be replaced)
        return kp_pattern
    
    # Look up word knowledge if we need concept, pronunciation, or hsk_level
    word_knowledge = {}
    if "{{concept}}" in kp_pattern or "{{pronunciation}}" in kp_pattern or "{{hsk_level}}" in kp_pattern:
        word_knowledge = get_word_knowledge(word_value)
    
    # Replace variables
    result = kp_pattern
    result = result.replace("{{word}}", word_value)
    
    if "{{concept}}" in result:
        # Use first meaning as concept
        meanings = word_knowledge.get("meanings", [])
        concept = meanings[0] if meanings else word_value  # Fallback to word itself
        result = result.replace("{{concept}}", concept)
    
    if "{{pronunciation}}" in result:
        pronunciations = word_knowledge.get("pronunciations", [])
        pronunciation = pronunciations[0] if pronunciations else ""
        result = result.replace("{{pronunciation}}", pronunciation)
    
    if "{{hsk_level}}" in result:
        hsk_level = word_knowledge.get("hsk_level", "")
        result = result.replace("{{hsk_level}}", str(hsk_level) if hsk_level else "")
    
    return result

def build_cuma_remarks(card: Dict[str, Any], context_tags: List[Dict[str, Any]]) -> str:
    """Construct the _Remarks field combining tags and knowledge point info."""
    lines: List[str] = []
    original_tags = card.get("tags", []) or []
    clean_tags, extracted_annotations = split_tag_annotations(original_tags)
    card["tags"] = clean_tags
    annotations = (card.get("field__Remarks_annotations") or []) + extracted_annotations
    kp_ids_set: Set[str] = set(card.get("knowledge_points") or [])
    knowledge_entries: List[str] = []
    knowledge_entries_seen: Set[str] = set()

    def add_entry(text: str):
        if not text:
            return
        formatted = text.strip()
        if not formatted:
            return
        if formatted not in knowledge_entries_seen:
            knowledge_entries.append(formatted)
            knowledge_entries_seen.add(formatted)

    def add_kp_entry(raw_kp: str):
        kp_value = (raw_kp or "").strip()
        if not kp_value:
            return
        # Ensure it has kp: prefix for storage
        if not kp_value.startswith("kp:"):
            stored_kp = f"kp:{kp_value}"
        else:
            stored_kp = kp_value
        kp_ids_set.add(stored_kp)
        
        # Parse the KP for readable display
        display_parts = kp_value.split("--", 2) if not kp_value.startswith("kp:") else kp_value[3:].split("--", 2)
        if len(display_parts) == 3:
            subj, pred, obj = display_parts
            # Create readable display format based on predicate
            pred_lower = pred.lower().replace('-', ' ')
            if pred_lower in ['means', 'has meaning', 'meaning']:
                display_text = f"{subj} means {obj} (concept)"
            elif pred_lower in ['has pronunciation', 'pronunciation', 'pronounced']:
                display_text = f"{subj} pronounced {obj}"
            elif pred_lower in ['has hsk level', 'hsk level', 'hsk']:
                display_text = f"{subj} HSK level {obj}"
            elif pred_lower in ['has grammar rule', 'grammar rule', 'grammar']:
                display_text = f"{subj} grammar rule: {obj}"
            elif pred_lower in ['has part of speech', 'part of speech', 'pos']:
                display_text = f"{subj} part of speech: {obj}"
            else:
                display_text = f"{subj} → {obj} ({pred.replace('-', ' ')})"
        else:
            display_text = kp_value.replace("kp:", "").replace("--", " → ")
        add_entry(display_text)

    # Seed knowledge points from card metadata
    for kp in sorted(kp_ids_set):
        add_kp_entry(kp)

    # Allow explicit @kp:... mentions to append
    for tag in context_tags or []:
        if tag.get("type") == "kp":
            value = (tag.get("value") or "").strip()
            if value:
                if not value.startswith("kp:"):
                    value = f"kp:{value}"
                add_kp_entry(value)
    
    for annotation in annotations:
        annotation_text = str(annotation).strip()
        if not annotation_text:
            continue
        if annotation_text.startswith("kp:"):
            add_kp_entry(annotation_text)
        else:
            add_entry(annotation_text)
    
    if knowledge_entries:
        lines.append("Knowledge Points:")
        for entry in knowledge_entries:
            lines.append(f"- {entry}")
    
    if clean_tags:
        lines.append("CUMA Tags: " + ", ".join(clean_tags))

    if kp_ids_set:
        card["knowledge_points"] = sorted(kp_ids_set)
    else:
        card.pop("knowledge_points", None)
    
    return "\n".join(lines).strip()

def parse_context_tags(content: str, mentions: List[str]) -> List[Dict[str, Any]]:
    """
    Parse @mentions from message content into structured context tags.

    NOW ENHANCED WITH DIRECT REGEX PARSING:
    - Scans content string directly using regex pattern: r"@(\w+):([^\s@,]+)"
    - Extracts ALL @key:value tags from text (quantity, template, word, etc.)
    - No longer fully dependent on frontend mentions array

    Supports formats:
    - @profile:Alex -> {"type": "profile", "value": "Alex"}
    - @interest:trains -> {"type": "interest", "value": "trains"}
    - @word:红色 -> {"type": "word", "value": "红色"}
    - @skill:grammar-001 -> {"type": "skill", "value": "grammar-001"}
    - @character:Pinocchio -> {"type": "character", "value": "Pinocchio"}
    - @notetype:cuma-interactive-cloze -> {"type": "notetype", "value": "CUMA - Interactive Cloze"}
    - @template:my_template -> {"type": "template", "value": "my_template"}
    - @quantity:10 -> {"type": "quantity", "value": "10"}
    - @Alex (plain mention) -> {"type": "profile", "value": "Alex"}
    """

    context_tags = []
    seen_tags = set()  # Deduplicate tags

    # Map tag types
    valid_types = {
        "profile": "profile",
        "child": "profile",
        "interest": "interest",
        "word": "word",
        "vocabulary": "word",
        "skill": "skill",
        "character": "character",
        "notetype": "notetype",
        "note-type": "notetype",
        "template": "template",
        "prompt": "template",
        "quantity": "quantity"
    }

    # === PRIMARY PARSING: Direct Regex Scan of Content ===
    # This regex captures @key:value patterns
    # Pattern: @(\w+):([^\s@,]+)
    # - \w+ captures the key (alphanumeric + underscore)
    # - [^\s@,]+ captures the value (anything except space, @, or comma)
    generic_tag_pattern = r'@(\w+):([^\s@,]+)'
    generic_matches = re.findall(generic_tag_pattern, content)

    logger.info(f"🔍 Direct Regex Scan found {len(generic_matches)} @key:value tags in content")

    for raw_key, raw_value in generic_matches:
        tag_type = raw_key.lower().strip()
        tag_value = raw_value.strip()

        # Map to canonical type
        mapped_type = valid_types.get(tag_type, tag_type)  # Use raw type if not in map

        # Create unique key for deduplication
        tag_key = f"{mapped_type}:{tag_value}"

        if tag_key not in seen_tags:
            seen_tags.add(tag_key)
            context_tags.append({
                "type": mapped_type,
                "value": tag_value
            })
            logger.info(f"✅ Parsed from content: @{tag_type}:{tag_value} -> type={mapped_type}")

    # Find special standalone @roster mention (no colon)
    # Match @roster as a whole word (not part of another word)
    if re.search(r'(?:^|[\s,])@roster(?:[\s,]|$)', content):
        roster_key = "roster:roster"
        if roster_key not in seen_tags:
            seen_tags.add(roster_key)
            context_tags.append({
                "type": "roster",
                "value": "roster"
            })
            logger.info("Detected @roster mention")

    # Special handling for knowledge point mentions
    # Supports two formats:
    # 1. @kp:subject--predicate--object (explicit format)
    # 2. @subject--predicate--object (simplified format, e.g., @读者--means--reader)

    # First, try @kp: format
    kp_explicit_pattern = r'@kp:([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
    kp_explicit_matches = re.findall(kp_explicit_pattern, content)
    for kp_value in kp_explicit_matches:
        kp_value = kp_value.strip().rstrip(',')
        if kp_value:
            kp_key = f"kp:{kp_value}"
            if kp_key not in seen_tags:
                seen_tags.add(kp_key)
                context_tags.append({
                    "type": "kp",
                    "value": kp_value
                })
                logger.debug(f"Parsed knowledge point (explicit): {kp_value}")

    # Then, try simplified format: @subject--predicate--object
    kp_simplified_pattern = r'@([^@\s:]+)--([^@\s]+)--([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
    kp_simplified_matches = re.findall(kp_simplified_pattern, content)
    for subj, pred, obj in kp_simplified_matches:
        if pred and '--' not in subj and '--' not in pred:
            kp_value = f"{subj}--{pred}--{obj.strip()}"
            kp_key = f"kp:{kp_value}"
            if kp_key not in seen_tags:
                seen_tags.add(kp_key)
                context_tags.append({
                    "type": "kp",
                    "value": kp_value
                })

    # === FALLBACK: Process Frontend Mentions (for backward compatibility) ===
    # Only add if not already captured by regex scan
    for mention in mentions:
        # Handle @type:value format
        if ":" in mention:
            # Split only on first colon
            parts = mention.split(":", 1)
            tag_type = parts[0].lower().strip()
            tag_value = parts[1].strip()

            mapped_type = valid_types.get(tag_type, tag_type)
            tag_key = f"{mapped_type}:{tag_value}"

            if tag_key not in seen_tags:
                seen_tags.add(tag_key)
                context_tags.append({
                    "type": mapped_type,
                    "value": tag_value
                })
        else:
            # Handle plain mentions (assume profile)
            # Check if it's already handled by @roster or others
            if mention.lower() == "roster":
                continue

            tag_key = f"profile:{mention}"
            if tag_key not in seen_tags:
                seen_tags.add(tag_key)
                context_tags.append({
                    "type": "profile",
                    "value": mention
                })

    logger.info(f"📋 Final context_tags count: {len(context_tags)}")
    return context_tags

@router.get("/chat/topic/history")
async def get_topic_chat_history(
    topic_id: Optional[str] = None,
    roster_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Topic-specific chat history endpoint (matches frontend expectations).
    Returns {messages: [...]} format.
    """
    try:
        if not roster_id:
             if Profile:
                 p = db.query(Profile).first()
                 if p: roster_id = str(p.id)
        
        if not roster_id or not topic_id:
            return {"messages": []}

        history = []
        if ChatSessionService:
            history = ChatSessionService.get_history(db, topic_id, roster_id)
            if limit and len(history) > limit:
                history = history[-limit:]

        safe_history = []
        for msg in history:
            # Initialize with ALL required arrays that frontend expects
            item = {
                "cards": [],
                "suggestions": [],
                "sources": [],
                "mentions": []  # CRITICAL: Frontend formatMessage expects this
            }
            
            if isinstance(msg, dict):
                for key, value in msg.items():
                    if key in ["cards", "suggestions", "sources", "mentions"]:
                        # Only set if it's already a valid list
                        if isinstance(value, list):
                            item[key] = value
                        # Otherwise keep the empty list we initialized
                    else:
                        item[key] = value
            else:
                item["role"] = getattr(msg, "role", "assistant")
                item["content"] = getattr(msg, "content", "")
                timestamp = getattr(msg, "timestamp", None)
                if timestamp:
                    item["timestamp"] = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
                else:
                    item["timestamp"] = None

            # Final safety check - ensure ALL arrays are present and are lists
            if "cards" not in item or not isinstance(item["cards"], list):
                item["cards"] = []
            if "suggestions" not in item or not isinstance(item["suggestions"], list):
                item["suggestions"] = []
            if "sources" not in item or not isinstance(item["sources"], list):
                item["sources"] = []
            if "mentions" not in item or not isinstance(item["mentions"], list):
                item["mentions"] = []
                
            safe_history.append(item)

        return {"messages": safe_history}
    except Exception as e:
        logger.error(f"Topic History Error: {e}")
        return {"messages": []}

@router.get("/chat/history", response_model=List[ChatMessage])
async def get_chat_history():
    """Get chat history."""
    history = load_json_file(CHAT_HISTORY_FILE, [])
    # Ensure all messages have mentions array
    for msg in history:
        if "mentions" not in msg or not isinstance(msg.get("mentions"), list):
            msg["mentions"] = []
        if "cards" not in msg:
            msg["cards"] = []
        if "suggestions" not in msg:
            msg["suggestions"] = []
        if "sources" not in msg:
            msg["sources"] = []
    return history

async def _handle_card_generation(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                child_profile: Dict[str, Any], profiles: List[Dict[str, Any]],
                                api_key: Optional[str], provider: str, model: Optional[str], 
                                base_url: Optional[str], ai_extracted_topic: Optional[str] = None) -> str:
    """Handle card generation requests via AgentService (replaces Legacy ContentGenerator)."""
    try:
        from backend.app.services.agent_service import AgentService
        from backend.database.db import SessionLocal
        from backend.database.services import ProfileService
        from backend.database.models import Profile
        
        # 1. Extract parameters
        # --- TOPIC EXTRACTION LOGIC ---
        extracted_topic = None
        user_message = message.content
        
        # 1. Check for @word: syntax (Legacy/UI)
        word_match = re.search(r"@word:([\w\-\s]+)", user_message)
        if word_match:
            extracted_topic = word_match.group(1).strip()
        
        # 2. Check for Quotes (Chat "Teach 'X'")
        if not extracted_topic:
            quote_match = re.search(r"['\"](.*?)['\"]", user_message)
            if quote_match:
                extracted_topic = quote_match.group(1).strip()
                
        # 3. Fallback (Clean cleanup)
        if not extracted_topic:
            clean_msg = re.sub(r"(teach|explain|create cards for)\s+(the word|the concept of)?\s*", "", user_message, flags=re.IGNORECASE)
            extracted_topic = clean_msg.strip()
        
        # 4. Use AI-extracted topic as final fallback
        if not extracted_topic and ai_extracted_topic:
            extracted_topic = ai_extracted_topic
            logger.info(f"🎯 Using AI-extracted topic as fallback: '{extracted_topic}'")
            
        logger.info(f"🎯 Extracted Topic: '{extracted_topic}'")
        topic_id = extracted_topic

        # 1. Try to get profile from DB if not passed in
        if not child_profile:
            db = SessionLocal()
            try:
                db_profile = db.query(Profile).first()
                if db_profile:
                    child_profile = ProfileService.profile_to_dict(db, db_profile)
                    logger.info(f"👤 Loaded Profile from DB: {child_profile.get('name')}")
            except Exception as e:
                logger.error(f"DB Profile Fetch Error: {e}")
            finally:
                db.close()

        # Roster/Profile
        roster_id = "Unknown_Student"
        if child_profile:
            roster_id = str(child_profile.get("id") or child_profile.get("name"))
        
        # Template
        template_id = None
        for tag in context_tags:
            if tag.get("type") == "template":
                template_id = tag.get("value")
                break
        
        # Quantity
        quantity = 3  # Default
        for tag in context_tags:
            if tag.get("type") == "quantity":
                try:
                    quantity = int(tag.get("value"))
                except (ValueError, TypeError):
                    pass
        
        logger.info(f"🤖 Delegate to AgentService: Topic='{topic_id}', Template='{template_id}', Provider='{provider}'")

        # 2. Call AgentService
        db = SessionLocal()
        try:
            cards = AgentService.generate_cards(
                topic_id=topic_id,
                roster_id=roster_id,
                template_id=template_id,
                user_instruction=message.content,
                quantity=quantity,
                db=db,
                api_key=api_key,
                provider=provider,
                model_name=model,
                base_url=base_url
            )
            
            # 3. Create response
            card_count = len(cards)
            if card_count > 0:
                template_info = f" using template '{template_id}'" if template_id else ""
                response_content = f"✅ Generated {card_count} cards for '{topic_id}'{template_info}.\n👉 Check 'Card Review' tab."
            else:
                response_content = f"⚠️ Agent could not generate cards for '{topic_id}'. Please try being more specific."
        except Exception as e:
            logger.error(f"Agent Error: {e}", exc_info=True)
            response_content = f"Error generating cards: {str(e)}"
        finally:
            db.close()

        return response_content

    except Exception as e:
        logger.error(f"Card generation error: {e}", exc_info=True)
        return f"I encountered an error generating cards: {str(e)}. Please try again."

@router.post("/chat", response_model=ChatMessage)
async def send_message(message: ChatMessage, request: Request):
    try:
        import sys
        
        # 1. Capture Credentials & Config from Headers
        api_key = request.headers.get("X-LLM-Key")
        if not api_key:
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ")[1]
            else:
                api_key = message.config.get("apiKey") if message.config else None
        
        base_url = request.headers.get("X-LLM-Base-URL")
        provider = request.headers.get("X-LLM-Provider", "google").lower()  # Changed default to google
        model = request.headers.get("X-LLM-Model")
        
        # Normalize provider names: "gemini" -> "google"
        if provider == "gemini":
            provider = "google"
        
        # Save user message
        history = load_json_file(CHAT_HISTORY_FILE, [])
        history.append(message.dict())
        save_json_file(CHAT_HISTORY_FILE, history)
        
        try:
            # Initialize handlers
            card_model_raw = message.config.get("card_model") if message.config else None
            image_model_raw = message.config.get("image_model") if message.config else None
            
            base_url = os.getenv("DEEPSEEK_API_BASE", "")
            
            card_model = _normalize_model_name(card_model_raw, base_url) if card_model_raw else None
            image_model = _normalize_model_name(image_model_raw, base_url) if image_model_raw else None
            
            if not IntentDetector or not ConversationHandler or not ContentGenerator:
                raise ImportError("Agent modules not available")
            
            conversation_handler = ConversationHandler(card_model=card_model, image_model=image_model)
            
            context_tags = parse_context_tags(message.content, message.mentions)
            
            # 1. Detect Intent (Pass credentials to the router)
            # We use the explicit static method now, passing the key/provider we extracted earlier
            intent_result = IntentDetector.detect_intent(
                message=message.content, 
                api_key=api_key, 
                provider=provider
            )
            
            intent_type = intent_result["intent"]
            confidence = intent_result["confidence"]
            # If the LLM extracted a topic, we can use it as a fallback override if needed
            ai_extracted_topic = intent_result.get("extracted_topic")
            
            logger.info(f"INTENT: {intent_type.value} ({confidence}) | AI Topic: {ai_extracted_topic}")
            
            # Match profile
            child_profile = None
            
            # LOAD FROM DB INSTEAD OF JSON
            from backend.database.db import SessionLocal
            from backend.database.services import ProfileService
            from backend.database.models import Profile

            db = SessionLocal()
            profiles = [] # Legacy compatibility
            try:
                # 1. Try to match specific mention
                all_profiles = db.query(Profile).all()
                for mention in message.mentions:
                    for p in all_profiles:
                        if p.name.lower() in mention.lower() or mention.lower() in p.name.lower():
                            child_profile = ProfileService.profile_to_dict(db, p)
                            break
                    if child_profile: break
                
                # 2. Fallback: If @roster is used but no name matched, use the first profile
                if not child_profile and "@roster" in message.content:
                    first = db.query(Profile).first()
                    if first:
                        child_profile = ProfileService.profile_to_dict(db, first)
            finally:
                db.close()
            
            # Handle intents
            if intent_type == IntentType.CONVERSATION:
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]
                )
            elif intent_type == IntentType.CARD_GENERATION:
                # UNIFIED ROUTE: All card generation goes through AgentService
                # AgentService dynamically handles templates vs. constitution-based generation
                logger.info("🔀 Unified Route: Routing to AgentService")
                
                # PASS CONFIG TO HANDLER
                response_content = await _handle_card_generation(
                    message, context_tags, child_profile, profiles,
                    api_key, provider, model, base_url,  # Pass config from headers
                    ai_extracted_topic=ai_extracted_topic  # Pass AI-extracted topic as fallback
                )
            else:
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]
                )
                
        except ImportError as e:
            logger.error(f"Agent import error: {e}")
            response_content = f"Error: Agent modules could not be loaded. {str(e)}"

    except Exception as e:
        logger.error(f"Chat error: {e}")
        response_content = f"System Error: {str(e)}"
        
    response = ChatMessage(
        id=f"resp_{datetime.now().timestamp()}",
        content=response_content,
        role="assistant",
        timestamp=datetime.now(),
        mentions=message.mentions
    )
    
    history = load_json_file(CHAT_HISTORY_FILE, [])
    history.append(response.dict())
    save_json_file(CHAT_HISTORY_FILE, history)
    
    return response

# --- Agent Generate Endpoint ---

class AgentGenerateRequest(BaseModel):
    topic_id: str
    roster_id: str
    template_id: Optional[str] = None  # Allow null for Automatic mode
    chat_instruction: str


@router.post("/agent/generate")
async def agent_generate(request: AgentGenerateRequest, req: Request, db: Session = Depends(get_db)):
    """
    Generate cards with DYNAMIC PROVIDER support.
    Used by TopicChat component for grammar card generation.
    """
    try:
        from backend.app.services.agent_service import AgentService
        
        # 1. Extract Headers (Support both X-Llm-* and X-LLM-* for compatibility)
        api_key = req.headers.get("X-Llm-Key") or req.headers.get("X-LLM-Key")
        raw_provider = (req.headers.get("X-Llm-Provider") or req.headers.get("X-LLM-Provider") or "google").lower()
        # Normalize provider names: "gemini" -> "google"
        provider = "google" if raw_provider == "gemini" else raw_provider
        model = req.headers.get("X-Llm-Model") or req.headers.get("X-LLM-Model")
        base_url = req.headers.get("X-Llm-Base-Url") or req.headers.get("X-LLM-Base-URL")
        
        # Fallback for Bearer Token
        if not api_key:
            auth = req.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ")[1]

        logger.info(f"🛸 Agent Request: {request.topic_id} | Template: {request.template_id or 'AUTO'}")

        # 2. Parse quantity from @quantity:N in chat_instruction (same as chat flow)
        quantity = 5  # Default
        context_tags = parse_context_tags(request.chat_instruction, [])
        for tag in context_tags:
            if tag.get("type") == "quantity":
                try:
                    quantity = int(tag.get("value"))
                    quantity = max(1, min(20, quantity))  # Clamp 1–20
                    break
                except (ValueError, TypeError):
                    pass

        # 3. Call Service with Explicit Config
        generated_cards = AgentService.generate_cards(
            topic_id=request.topic_id,
            roster_id=request.roster_id,
            template_id=request.template_id,
            user_instruction=request.chat_instruction,
            quantity=quantity,
            db=db,
            # Pass config explicitly
            api_key=api_key,
            provider=provider,
            model_name=model,
            base_url=base_url
        )
        
        # 4. Create Response & Save History
        card_count = len(generated_cards)
        if card_count > 0:
            response_content = f"✅ Generated {card_count} cards for {request.topic_id}."
        else:
            response_content = "⚠️ No cards were generated. Check backend logs."
        # Save User Request to History
        ChatSessionService.add_message(
            db, request.topic_id, request.roster_id, "user", request.chat_instruction
        )
        # Save Assistant Response to History
        ChatSessionService.add_message(
            db, request.topic_id, request.roster_id, "assistant", response_content
        )
        return {
            "content": response_content,
            "cards_generated": card_count,
            "cards": generated_cards if isinstance(generated_cards, list) else [],
            "role": "assistant",
            "mentions": [],
            "suggestions": [],
            "sources": []
        }
    except Exception as e:
        logger.error(f"❌ Agent Generate Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
