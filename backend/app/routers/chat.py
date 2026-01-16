from fastapi import APIRouter, HTTPException, Request, Depends, status
from pydantic import BaseModel
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

# Agentic imports
from agentic import AgenticPlanner, AgentMemory, PrincipleStore, AgentTools
from agentic.tools import (
    MasteryVectorError,
    KnowledgeGraphError,
    RecommenderError,
)
from agent.intent_detector import IntentDetector, IntentType
from agent.conversation_handler import ConversationHandler
from agent.content_generator import ContentGenerator

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Models ---

class ChatMessage(BaseModel):
    id: str
    content: str
    role: str  # "user" or "assistant"
    timestamp: datetime
    mentions: List[str] = []
    config: Optional[Dict[str, str]] = None  # Optional model configuration: {"card_model": "...", "image_model": "..."}

class AgenticPlanRequest(BaseModel):
    user_id: str
    topic: Optional[str] = None  # Optional - agent can determine what to learn
    learner_level: Optional[str] = None
    topic_complexity: Optional[str] = None  # Optional - agent can infer from mastery

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
                logger.info(f"No profile specified with @roster, using first profile: {child_profile.get('name')}")
            
            if child_profile and child_profile.get("character_roster"):
                characters_str = ", ".join(child_profile["character_roster"])
                context_tags.append({
                    "type": "character_list",
                    "value": characters_str
                })
                logger.info(f"Using character roster: {characters_str}")
        
        # Get prompt template if specified
        prompt_template = None
        for tag in context_tags:
            if tag.get("type") == "template":
                template_value = tag.get("value")
                templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
                logger.debug(f"Looking for template: {template_value}")
                
                for tmpl in templates:
                    # Match by ID, name, or name with underscores/hyphens
                    template_name_normalized = tmpl.get("name", "").replace(' ', '_').lower()
                    template_value_normalized = template_value.replace('_', '_').replace('-', '_').lower()
                    
                    if (tmpl.get("id") == template_value or 
                        tmpl.get("name") == template_value or
                        template_name_normalized == template_value_normalized or
                        template_name_normalized.replace('_', '') == template_value_normalized.replace('_', '') or
                        tmpl.get("name", "").lower().replace(' ', '-') == template_value.lower().replace('_', '-')):
                        prompt_template = tmpl.get("template_text")
                        
                        # Fix for incorrect instruction in chinese_word template
                        if "English vocab exercise" in prompt_template:
                            prompt_template = prompt_template.replace("English vocab exercise", "Chinese vocab exercise")
                            logger.info("Fixed 'English vocab exercise' in template")

                        logger.info(f"Found template: {tmpl.get('name')}")
                        
                        # Parse knowledge point mentions from template text and add to context_tags
                        # First, try @kp: format
                        template_kp_explicit_pattern = r'@kp:([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
                        template_kp_explicit_matches = re.findall(template_kp_explicit_pattern, prompt_template)
                        for kp_pattern in template_kp_explicit_matches:
                            kp_pattern = kp_pattern.strip().rstrip(',')
                            if not kp_pattern:
                                continue
                            kp_value = expand_kp_template_variables(kp_pattern, context_tags)
                            if kp_value == kp_pattern and "{{" in kp_pattern:
                                logger.warning(f"Could not expand knowledge point template variables: {kp_pattern}")
                                continue
                            kp_already_exists = any(
                                t.get("type") == "kp" and t.get("value") == kp_value
                                for t in context_tags
                            )
                            if not kp_already_exists:
                                context_tags.append({
                                    "type": "kp",
                                    "value": kp_value
                                })
                                logger.debug(f"Added knowledge point from template (explicit, expanded): {kp_value}")
                        
                        # Then, try simplified format
                        template_kp_simplified_pattern = r'@([^@\n]+?--[^@\n]+?--[^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
                        template_kp_simplified_matches = re.findall(template_kp_simplified_pattern, prompt_template)
                        for kp_pattern_raw in template_kp_simplified_matches:
                            kp_pattern_raw = kp_pattern_raw.strip().rstrip(',')
                            if not kp_pattern_raw:
                                continue
                            if kp_pattern_raw.count('--') != 2:
                                continue
                            kp_value = expand_kp_template_variables(f"@{kp_pattern_raw}", context_tags)
                            if kp_value.startswith("@"):
                                kp_value = kp_value[1:]
                            if kp_value == kp_pattern_raw and "{{" in kp_pattern_raw:
                                logger.warning(f"Could not expand knowledge point template variables: @{kp_pattern_raw}")
                                continue
                            kp_already_exists = any(
                                t.get("type") == "kp" and t.get("value") == kp_value
                                for t in context_tags
                            )
                            if not kp_already_exists:
                                context_tags.append({
                                    "type": "kp",
                                    "value": kp_value
                                })
                                logger.debug(f"Added knowledge point from template (simplified, expanded): {kp_value}")
                        break
                
                if not prompt_template:
                    logger.warning(f"Template not found: {template_value}")
        
        # Extract quantity from context_tags
        quantity = None
        for tag in context_tags:
            if tag.get("type") == "quantity":
                try:
                    quantity = int(tag.get("value"))
                    logger.info(f"Extracted quantity from @quantity: {quantity}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid quantity value: {tag.get('value')}")
        
        # Use the flexible agent method
        loop = asyncio.get_event_loop()
        cards = await loop.run_in_executor(
            None,
            partial(
                generator.generate_from_prompt,
                user_prompt=message.content,
                context_tags=context_tags,
                child_profile=child_profile,
                prompt_template=prompt_template,
                quantity=quantity
            )
        )
        
        # Save generated cards
        existing_cards = load_json_file(CARDS_FILE, [])
        for card in cards:
            remarks = build_cuma_remarks(card, context_tags)
            card["field__Remarks"] = remarks or ""
            card.pop("field__Remarks_annotations", None)
            existing_cards.append(card)
        save_json_file(CARDS_FILE, existing_cards)
        
        # Create response
        card_count = len(cards)
        response_content = f"✨ 成功为您生成了 {card_count} 张卡片！\n\n"
        
        basic_count = len([c for c in cards if c['card_type'] == 'basic'])
        reverse_count = len([c for c in cards if c['card_type'] == 'basic_reverse'])
        cloze_count = len([c for c in cards if c['card_type'] == 'cloze'])
        
        details = []
        if basic_count > 0: details.append(f"{basic_count} 张基础卡片")
        if reverse_count > 0: details.append(f"{reverse_count} 张反向卡片")
        if cloze_count > 0: details.append(f"{cloze_count} 张完形填空卡片")
        
        if details:
            response_content += f"📝 包含：{', '.join(details)}\n\n"
        
        if context_tags:
            tag_strings = []
            for t in context_tags:
                if t['type'] == 'profile' and child_profile:
                    tag_strings.append(f"profile={child_profile.get('name')}")
                else:
                    tag_strings.append(f"{t['type']}={t['value']}")
            response_content += f"🎯 应用上下文：{', '.join(tag_strings)}\n\n"
        
        response_content += "👉 请在「卡片审核」标签页中查看并批准这些卡片！"
        
        return response_content
        
    except Exception as e:
        logger.error(f"Card generation error: {e}")
        return f"I encountered an error generating cards: {str(e)}. Please try again with a different request."

async def _handle_image_generation(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                 child_profile: Dict[str, Any], generator,
                                 profiles: List[Dict[str, Any]]) -> str:
    """Handle image generation requests."""
    try:
        all_cards = load_json_file(CARDS_FILE, [])
        if not all_cards:
            return "❌ No cards found to add images to. Please generate some cards first."
        
        target_card = all_cards[-1]
        card_id = target_card["id"]
        
        logger.info(f"Generating image for card: {card_id}")
        
        image_prompt = f"Create a simple, child-friendly illustration for this flashcard content: '{target_card.get('front', '')}' - '{target_card.get('back', '')}'. The image should be colorful, simple, and appropriate for a child with autism."
        
        card_model = message.config.get("card_model") if message.config else None
        image_model = message.config.get("image_model") if message.config else None
        
        conversation_handler = ConversationHandler(card_model=card_model, image_model=image_model)
        content_generator = ContentGenerator(card_model=card_model)
        
        image_description = conversation_handler._generate_image_description(
            card_content=target_card,
            user_request=message.content,
            child_profile=child_profile
        )
        
        image_result = conversation_handler.generate_actual_image(
            image_description=image_description,
            user_request=message.content
        )
        
        target_card["image_description"] = image_description
        target_card["image_prompt"] = image_prompt
        
        image_filename = None
        if image_result.get("success") and image_result.get("image_data"):
            image_data_url = image_result.get("image_data")
            if image_data_url and image_data_url.startswith("data:"):
                try:
                    header, encoded = image_data_url.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1]
                    image_bytes = base64.b64decode(encoded)
                    image_filename = content_generator._save_hashed_image(image_bytes, mime_type)
                    target_card["image_data"] = image_filename
                except Exception as e:
                    logger.error(f"Error processing image data in chat handler: {e}")
                    target_card["image_data"] = image_data_url
        
        if image_result["success"]:
            if image_result.get("is_placeholder", False):
                return f"🖼️ **Generated Image Description:**\n\n{image_description}\n\n⚠️ **Note:** This is a placeholder image."
            else:
                if image_filename:
                    image_path = f"/static/media/{image_filename}"
                    image_markdown = f"![Generated Image]({image_path})"
                else:
                    image_markdown = f"![Generated Image]({image_result.get('image_data', '')})"
                
                return f"🖼️ **Generated Image:**\n\n{image_markdown}\n\n**Image Description:**\n{image_description}\n\n**To add this image to a card, please specify:**\n- Which card (by ID or 'last card')\n- Front or back\n- Before or after the text"
        else:
            target_card["image_generated"] = False
            target_card["image_error"] = image_result["error"]
            
            for i, card in enumerate(all_cards):
                if card["id"] == card_id:
                    all_cards[i] = target_card
                    break
            save_json_file(CARDS_FILE, all_cards)
            
            return f"🖼️ Generated image description for card '{target_card.get('front', 'Card')}':\n\n{image_description}\n\n❌ **Image generation failed:** {image_result['error']}"
        
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return f"I encountered an error generating an image: {str(e)}. Please try again."

async def _handle_image_insertion(message: ChatMessage, context_tags: List[Dict[str, Any]], 
                                child_profile: Optional[Dict[str, Any]]) -> str:
    """Handle image insertion requests."""
    try:
        message_lower = message.content.lower()
        
        # Extract card reference
        card_ref = None
        if "last card" in message_lower:
            all_cards = load_json_file(CARDS_FILE)
            if all_cards:
                card_ref = all_cards[-1]
            else:
                return "❌ No cards found. Please create a card first."
        elif "card #" in message_lower or "card " in message_lower:
            card_id_match = re.search(r'card\s*#?(\w+)', message_lower)
            if card_id_match:
                card_id = card_id_match.group(1)
                all_cards = load_json_file(CARDS_FILE)
                card_ref = next((card for card in all_cards if card["id"].endswith(card_id)), None)
                if not card_ref:
                    return f"❌ Card #{card_id} not found."
        else:
            return "❌ Please specify which card to add the image to (e.g., 'last card', 'card #123')."
        
        # Extract position and location
        position = "back" if "back" in message_lower else "front"
        location = "before" if "before" in message_lower else "after"
        
        # Check chat history for recent image
        chat_history = load_json_file(CHAT_HISTORY_FILE)
        last_image = None
        
        for msg in reversed(chat_history[-10:]):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if "Generated Image:" in content:
                    img_match = re.search(r'!\[Generated Image\]\(([^)]+)\)', content)
                    if img_match:
                        last_image = img_match.group(1)
                        break
        
        if not last_image:
            return "❌ No recent image found. Please generate an image first."
        
        # Insert image
        card_type = card_ref.get("card_type", "")
        is_interactive_cloze = card_type == "interactive_cloze"
        
        if position == "front":
            target_field = "text_field" if is_interactive_cloze else "front"
            current_content = card_ref.get(target_field, "") or card_ref.get("front", "")
            img_html = f"<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-bottom: 10px;\">"
            
            if location == "before":
                card_ref[target_field] = f"{img_html}\n{current_content}"
            else:
                card_ref[target_field] = f"{current_content}\n{img_html.replace('margin-bottom', 'margin-top')}"
        else:
            target_field = "extra_field" if is_interactive_cloze else "back"
            current_content = card_ref.get(target_field, "") or card_ref.get("back", "")
            img_html = f"<img src=\"{last_image}\" alt=\"Generated image\" style=\"max-width: 100%; height: auto; margin-bottom: 10px;\">"
            
            if location == "before":
                card_ref[target_field] = f"{img_html}\n{current_content}"
            else:
                card_ref[target_field] = f"{current_content}\n{img_html.replace('margin-bottom', 'margin-top')}"
        
        # Save updated card
        all_cards = load_json_file(CARDS_FILE)
        card_updated = False
        for i, card in enumerate(all_cards):
            if card["id"] == card_ref["id"]:
                all_cards[i] = card_ref
                card_updated = True
                break
        
        if card_updated:
            save_json_file(CARDS_FILE, all_cards)
            return f"✅ Image added to {position} of card ({location} text)."
        else:
            return "❌ Failed to update card."
            
    except Exception as e:
        logger.error(f"Image insertion error: {e}")
        return f"Error inserting image: {str(e)}"

# --- Routes ---

@router.get("/chat/history", response_model=List[ChatMessage])
async def get_chat_history():
    """Get chat history."""
    history = load_json_file(CHAT_HISTORY_FILE, [])
    return history

@router.delete("/chat/history")
async def clear_chat_history():
    """Clear chat history."""
    save_json_file(CHAT_HISTORY_FILE, [])
    return {"message": "Chat history cleared"}

@router.post("/chat", response_model=ChatMessage)
async def send_message(message: ChatMessage, request: Request):
    try:
        import sys
        
        # 1. Capture Credentials
        api_key = request.headers.get("X-LLM-Key")
        if not api_key:
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ")[1]
            else:
                api_key = message.config.get("apiKey")
        
        base_url = request.headers.get("X-LLM-Base-URL")
        provider = request.headers.get("X-LLM-Provider", "deepseek").lower()
        
        if not base_url and provider == "deepseek":
            base_url = "https://api.siliconflow.cn/v1"
        
        # 2. Set Env Vars
        if api_key:
            os.environ["DEEPSEEK_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["DEEPSEEK_API_BASE"] = base_url
                os.environ["OPENAI_BASE_URL"] = base_url
            
            if provider == "deepseek" or (base_url and "siliconflow" in base_url):
                if "GEMINI_API_KEY" in os.environ:
                    del os.environ["GEMINI_API_KEY"]
                
                import importlib
                import agent.content_generator
                import agent.conversation_handler
                importlib.reload(agent.content_generator)
                importlib.reload(agent.conversation_handler)
                logger.info("Modules reloaded to force DeepSeek configuration")
        
        # 3. Imports
        # sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        
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
            
            intent_detector = IntentDetector()
            conversation_handler = ConversationHandler(card_model=card_model, image_model=image_model)
            generator = ContentGenerator(card_model=card_model)
            
            context_tags = parse_context_tags(message.content, message.mentions)
            
            intent_result = intent_detector.detect_intent(message.content, context_tags)
            intent_type = intent_result["intent"]
            confidence = intent_result["confidence"]
            
            logger.info(f"INTENT: {intent_type.value} ({confidence})")
            
            # Match profile
            child_profile = None
            profiles = load_json_file(PROFILES_FILE, [])
            for mention in message.mentions:
                for profile in profiles:
                    profile_id_raw = (profile.get("id") or "").lower()
                    profile_name_slug = normalize_to_slug(profile.get("name", ""))
                    mention_lower = mention.lower()
                    mention_slug = normalize_to_slug(mention)
                    
                    if (profile_id_raw and profile_id_raw == mention_lower or
                        profile.get("name") == mention or
                        profile_name_slug and profile_name_slug == mention_slug or
                        (profile_id_raw and profile_id_raw.endswith(mention_lower)) or
                        (profile_id_raw and mention_lower.endswith(profile_id_raw)) or
                        (profile_name_slug and mention_slug.endswith(profile_name_slug))):
                        child_profile = profile
                        break
                if child_profile:
                    break
            
            # Handle intents
            if intent_type == IntentType.CONVERSATION:
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]
                )
            elif intent_type == IntentType.CARD_GENERATION:
                response_content = await _handle_card_generation(
                    message, context_tags, child_profile, generator, profiles
                )
            elif intent_type == IntentType.IMAGE_GENERATION:
                response_content = await _handle_image_generation(
                    message, context_tags, child_profile, generator, profiles
                )
            elif intent_type == IntentType.IMAGE_INSERTION:
                response_content = await _handle_image_insertion(
                    message, context_tags, child_profile
                )
            elif intent_type == IntentType.CARD_UPDATE:
                response_content = "✏️ Card update feature is coming soon!"
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

# Agentic Planner Logic
_agentic_planner: Optional[AgenticPlanner] = None

def get_agentic_planner() -> AgenticPlanner:
    global _agentic_planner
    if _agentic_planner is None:
        memory = AgentMemory()
        principles = PrincipleStore()
        tools = AgentTools()
        _agentic_planner = AgenticPlanner(memory=memory, principles=principles, tools=tools)
    return _agentic_planner

@router.post("/agentic/plan")
async def agentic_plan(request: AgenticPlanRequest):
    """
    Entry point for the new Agentic Learning Agent.
    """
    try:
        planner = get_agentic_planner()
        plan = planner.plan_learning_step(
            user_id=request.user_id,
            topic=request.topic,
            learner_level=request.learner_level,
            topic_complexity=request.topic_complexity,
        )
        response = {
            "learner_level": plan.learner_level,
            "topic": plan.topic,
            "topic_complexity": plan.topic_complexity,
            "scaffold_type": plan.scaffold_type,
            "rationale": plan.rationale,
            "cognitive_prior": {
                "mastery_summary": plan.cognitive_prior.get("mastery_summary", {}),
                "total_nodes": len(plan.cognitive_prior.get("mastery_vector", {})),
            },
            "recommendation_plan": plan.recommendation_plan,
            "cards": plan.cards_payload.get("cards") if plan.cards_payload else None,
        }
        return response

    except (MasteryVectorError, KnowledgeGraphError, RecommenderError) as e:
        logger.error(f"Agentic planner failed for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Learning service temporarily unavailable. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in agentic planner for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )

