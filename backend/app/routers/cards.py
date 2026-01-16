from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import base64
import os
import json

from ..core.config import CARDS_FILE, PROJECT_ROOT
from openai import OpenAI

router = APIRouter()

# Import Gemini model - will be set at module level when main.py imports this router
_genai_model = None

def _set_genai_model(model):
    """Called by main.py to inject the Gemini model"""
    global _genai_model
    _genai_model = model

# ============================================================================
# Shared Utility Functions (imported from main.py or duplicated)
# ============================================================================

def load_json_file(file_path: str, default: Any = None):
    """Load JSON data from file, return default if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else []

def save_json_file(file_path: str, data: Any):
    """Save data to JSON file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

def split_tag_annotations(tags: List[Any]) -> tuple:
    """Separate descriptive annotations from machine-friendly tags."""
    TAG_ANNOTATION_PREFIXES = (
        "pronunciation",
        "meaning",
        "hsk",
        "knowledge",
        "note",
        "remark",
        "example",
    )

    clean_tags: List[str] = []
    annotations: List[str] = []

    # Handle case where tags is a string (comma-separated or single tag)
    if isinstance(tags, str):
        # Split comma-separated string into list
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    elif not isinstance(tags, (list, tuple)):
        # If it's not a string or list, convert to list
        tags = [tags] if tags else []

    for tag in tags:
        if not tag:
            continue
        tag_str = str(tag).strip()
        if not tag_str:
            continue

        # Check if it starts with an annotation prefix
        lower_tag = tag_str.lower()
        is_annotation = any(lower_tag.startswith(prefix + ":") for prefix in TAG_ANNOTATION_PREFIXES)

        if is_annotation:
            annotations.append(tag_str)
        else:
            clean_tags.append(tag_str)

    return clean_tags, annotations

def get_llm_client_from_request(request: Request):
    """
    Creates an LLM client (OpenAI-compatible) based on request headers.
    Headers: X-LLM-Provider, X-LLM-Key, X-LLM-Base-URL
    """
    print(f"\n🔍 DEBUG: get_llm_client_from_request")
    print(f"   Headers - Provider: {request.headers.get('X-LLM-Provider')}")
    print(f"   Headers - Base URL: {request.headers.get('X-LLM-Base-URL')}")

    provider = request.headers.get("X-LLM-Provider", "gemini").lower()
    api_key = request.headers.get("X-LLM-Key")
    base_url = request.headers.get("X-LLM-Base-URL")

    # Handle DeepSeek / OpenAI
    if provider in ["deepseek", "openai"]:
        # Fallback to env vars if header is missing
        if not api_key:
            api_key = os.getenv("DEEPSEEK_API_KEY") if provider == "deepseek" else os.getenv("OPENAI_API_KEY")

        # Default Base URLs
        if not base_url:
            base_url = "https://api.siliconflow.cn/v1" if provider == "deepseek" else None

        print(f"   Creating OpenAI client with base_url={base_url}")

        if api_key:
            return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        else:
            print(f"   ⚠️ No API key found for {provider}")
            return None

    # For Gemini or unsupported providers, return None (will use _genai_model)
    print(f"   Using Gemini fallback (_genai_model)")
    return None

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

# ============================================================================
# Pydantic Models
# ============================================================================

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

class CardImageRequest(BaseModel):
    position: Optional[str] = "front"
    location: Optional[str] = "after"
    user_request: Optional[str] = None
    config: Optional[Dict[str, str]] = None  # Optional model configuration: {"image_model": "..."}
    image_model: Optional[str] = None  # Direct image model ID (for convenience)

# ============================================================================
# Helper Functions
# ============================================================================

def extract_plain_text(value: str) -> str:
    """Strip HTML tags and normalize whitespace for prompt generation."""
    if not value:
        return ""
    import re
    from html import unescape
    text = unescape(value)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def _run_director_agent(card_front: str, card_back: str, client=None, style_guide: str = "Modern 3D Animation Style (Pixar/Disney style), vibrant lighting, high fidelity, highly detailed, 8k resolution", model_name: Optional[str] = None) -> str:
    """
    Run the director agent to generate image descriptions with an optional client.
    If client is an OpenAI instance, use client.chat.completions.create.
    If client is None or a Gemini object, use _genai_model.generate_content.

    Args:
        card_front: The front content of the flashcard
        card_back: The back content of the flashcard
        client: Optional OpenAI client or None/Gemini model
        style_guide: Art style guide for image generation (default: Modern 3D Animation Style)
        model_name: Optional model name to use for OpenAI client. If not provided, will use fallback logic.

    Returns:
        Generated image description text
    """
    # Build system instruction with style guide
    system_instruction = f"""You are an expert at creating detailed image descriptions for educational flashcards for children with autism.

**Flashcard Content:**
Front: {card_front}
Back: {card_back}

**Instructions:**
Create a detailed, vivid description of an image that would be perfect for this flashcard. The image should be:

1. **Educational**: Clearly illustrates the concept being taught
2. **Appropriate**: Age-appropriate and culturally sensitive
3. **Visual**: Rich in visual details that can be easily rendered
4. **Inclusive**: Consider the child's interests and character preferences

**STYLE GUIDE:**
- Art Style: {style_guide}.
- Lighting: Cinematic, warm, volumetric lighting.
- Detail: Rich textures (e.g., fur, fabric), expressive faces.
- Composition: Dynamic angles, depth of field.
- Mood: Cheerful, magical, encouraging.

**Image Description Guidelines:**
- Be specific about colors, shapes, and composition
- Include details about the setting, characters, and objects
- Make it vivid and easy to visualize
- Consider the child's interests if mentioned

**Output:**
Provide a detailed image description that an artist could use to create the perfect illustration for this flashcard. Be specific about visual elements, colors, composition, and style.

Generate the image description now:"""

    # Check if client is an OpenAI instance
    if client is not None and isinstance(client, OpenAI):
        try:
            # Determine model name with fallback logic
            if not model_name:
                # Check client.base_url for DeepSeek
                if hasattr(client, 'base_url') and client.base_url and "deepseek" in str(client.base_url).lower():
                    model_name = "deepseek-chat"
                else:
                    model_name = "gpt-3.5-turbo"

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": system_instruction}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI client error: {e}")
            # Fallback to Gemini if OpenAI fails
            if _genai_model:
                response = _genai_model.generate_content(system_instruction)
                return response.text
            # Fallback return if all else fails
            return f"A high-quality, {style_guide} illustration of: {card_front}. Cinematic lighting, 8k."

    # Use Gemini (default or fallback)
    if _genai_model:
        try:
            response = _genai_model.generate_content(system_instruction)
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
            return f"A high-quality, {style_guide} illustration of: {card_front}. Cinematic lighting, 8k."

    # Fallback if no model available
    return f"A high-quality, {style_guide} illustration of: {card_front}. Cinematic lighting, 8k."

# ============================================================================
# API Routes
# ============================================================================

@router.get("/cards")
async def get_cards():
    cards = load_json_file(CARDS_FILE, [])
    # Normalize tags field - convert string to list if needed
    for card in cards:
        tags = card.get('tags')
        # Ensure tags is always a list
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            # Split comma-separated string into list
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        elif not isinstance(tags, (list, tuple)):
            # Convert other types to list
            tags = [str(tags)] if tags else []
        card['tags'] = tags
        clean_tags, extracted_annotations = split_tag_annotations(card.get("tags", []))
        card['tags'] = clean_tags
        if extracted_annotations:
            existing_annotations = card.get("field__Remarks_annotations") or []
            card["field__Remarks_annotations"] = existing_annotations + extracted_annotations
        # Remove large binary payloads to keep response lightweight
        has_image = bool(card.get("image_data"))
        card["has_image_data"] = has_image
        if has_image:
            card.pop('image_data', None)
        if 'generated_image' in card and isinstance(card['generated_image'], dict):
            card['generated_image'].pop('data', None)
    return cards

@router.get("/cards/{card_id}/image-data")
async def get_card_image_data(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    for card in cards:
        if card.get("id") == card_id:
            image_data = card.get("image_data")
            if not image_data:
                raise HTTPException(status_code=404, detail="No image data found for this card")
            return {"image_data": image_data}
    raise HTTPException(status_code=404, detail="Card not found")

@router.post("/cards", response_model=Card)
async def create_card(card: Card):
    cards = load_json_file(CARDS_FILE, [])
    cards.append(card.dict())
    save_json_file(CARDS_FILE, cards)
    return card

@router.put("/cards/{card_id}/approve")
async def approve_card(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    for card in cards:
        if card["id"] == card_id:
            card["status"] = "approved"
            save_json_file(CARDS_FILE, cards)
            return {"message": "Card approved"}
    raise HTTPException(status_code=404, detail="Card not found")

@router.put("/cards/{card_id}")
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

@router.delete("/cards/{card_id}")
async def delete_card(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    initial_count = len(cards)
    cards = [card for card in cards if card["id"] != card_id]

    if len(cards) == initial_count:
        raise HTTPException(status_code=404, detail="Card not found")

    save_json_file(CARDS_FILE, cards)
    return {"message": "Card deleted successfully"}

@router.post("/cards/{card_id}/generate-image")
async def generate_card_image(card_id: str, request: CardImageRequest, req: Request):
    # 1. SETUP ENVIRONMENT (Copied from send_message)
    # ----------------------------------------------------------------
    api_key = req.headers.get("X-LLM-Key")
    if not api_key:
        auth = req.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            api_key = auth.split(" ")[1]

    base_url = req.headers.get("X-LLM-Base-URL")
    provider = req.headers.get("X-LLM-Provider", "deepseek").lower()

    # Default fallback for DeepSeek -> SiliconFlow
    if not base_url and provider == "deepseek":
        base_url = "https://api.siliconflow.cn/v1"

    if api_key:
        # Critical: Set env vars so ConversationHandler can find them
        os.environ["DEEPSEEK_API_KEY"] = api_key
        os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["DEEPSEEK_API_BASE"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url
            os.environ["OPENAI_API_BASE"] = base_url # Legacy support

        # --- FIX: PREVENT FALLBACK TO GEMINI ---
        # If using DeepSeek, hide the Gemini key so ContentGenerator doesn't default to Google.
        if provider == "deepseek" or (base_url and "siliconflow" in base_url):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            # Also unset the global fallback model if possible, or ensuring the generator prefers OpenAI
    # ----------------------------------------------------------------

    cards = load_json_file(CARDS_FILE, [])
    card_index = next((idx for idx, card in enumerate(cards) if card.get("id") == card_id), None)

    if card_index is None:
        raise HTTPException(status_code=404, detail="Card not found")

    card = cards[card_index]
    sanitized_card = {
        **card,
        "front": extract_plain_text(card.get("front", "")),
        "back": extract_plain_text(card.get("back", "")),
        "text_field": extract_plain_text(card.get("text_field", "")),
        "extra_field": extract_plain_text(card.get("extra_field", "")),
        "cloze_text": extract_plain_text(card.get("cloze_text", ""))
    }

    try:
        from agent.conversation_handler import ConversationHandler
        from agent.content_generator import ContentGenerator

        # Get LLM client for Step 1
        llm_client = get_llm_client_from_request(req)

        # Determine Card Model (Text)
        card_model_raw = None
        if request.config and request.config.get("card_model"):
            card_model_raw = request.config.get("card_model")

        # Normalize Text Model
        card_model = _normalize_model_name(card_model_raw, base_url or "") if card_model_raw else None

        # Determine Image Model
        image_model_raw = None
        if request.config and request.config.get("image_model"):
            image_model_raw = request.config.get("image_model")
        elif request.image_model:
            image_model_raw = request.image_model

        # --- FIX: Explicitly Map Hunyuan for SiliconFlow ---
        image_model = image_model_raw
        if base_url and "siliconflow" in base_url.lower():
             # If user selected generic Hunyuan or nothing, force specific ID
             if not image_model or "hunyuan" in str(image_model).lower():
                 image_model = "Tencent/Hunyuan-DiT"

        print(f"\n🎨 DEBUG: Config")
        print(f"   Text Model: {card_model}")
        print(f"   Image Model: {image_model}")
        print(f"   Base URL: {base_url}")

        # Initialize handlers
        # ConversationHandler will now find the API Key in os.environ!
        conversation_handler = ConversationHandler(image_model=image_model)
        content_generator = ContentGenerator()

        primary_text = (
            sanitized_card.get("text_field")
            or sanitized_card.get("cloze_text")
            or sanitized_card.get("front")
            or sanitized_card.get("back")
            or ""
        )
        user_request = request.user_request or f"Generate an illustration for this flashcard content: {primary_text}"

        context_str = "No specific context available"
        prompt = f"""You are a Lead Texture Artist & Lighter for a high-budget animated feature film (Pixar/Disney style).

**Context:**
{context_str}

**Scene Content:**
Subject: {sanitized_card.get('front', '')}
Action/Detail: {sanitized_card.get('back', '')}

**User Request:**
{user_request}

**YOUR TASK:**
Write a vivid, highly detailed rendering prompt for Unreal Engine 5.

**STYLE RULES (STRICT):**
1. **Art Style**: 3D CGI Render, Stylized Realism (like Zootopia, Frozen).
2. **Lighting**: Cinematic volumetric lighting, rim lighting to separate subject from background, soft shadows.
3. **Texture & Material**: High fidelity. Describe the "fluffiness" of fur, the "sheen" of fabric, the "subsurface scattering" of skin.
4. **Camera**: Use a 85mm portrait lens effect with a soft depth-of-field (blurred background).

**CRITICAL INSTRUCTIONS:**
- Do NOT mention "flashcard", "simple", "flat", or "vector".
- Treat this as a movie still frame.
- Make the characters expressive and alive.

**Output:**
Return ONLY the raw prompt string. Start with: "A stunning 3D render of..."
"""

        # --- STEP 1: Generate Description ---
        try:
            print("\n" + "="*80)
            print("🎨 STEP 1: GENERATING DESCRIPTION")
            print("-"*80)

            # Fallback logic for text model
            target_model = card_model
            if not target_model or target_model == "gpt-3.5-turbo":
                if base_url and "siliconflow" in base_url.lower():
                    target_model = "deepseek-ai/DeepSeek-V3"
                elif base_url and "deepseek" in base_url.lower():
                    target_model = "deepseek-chat"

            if llm_client is not None and isinstance(llm_client, OpenAI):
                response = llm_client.chat.completions.create(
                    model=target_model,
                    messages=[{"role": "user", "content": prompt}]
                )
                image_description = response.choices[0].message.content
            elif _genai_model:
                response = _genai_model.generate_content(prompt)
                image_description = response.text
            else:
                image_description = f"A stunning 3D render of {sanitized_card.get('front', '')}."

            print(f"✅ Description: {image_description[:100]}...")

        except Exception as e:
            print(f"❌ Text Generation Error: {e}")
            image_description = f"A stunning 3D render of {sanitized_card.get('front', '')}."

        # --- STEP 2: Generate Actual Image ---
        print("\n" + "="*80)
        print("🎨 STEP 2: GENERATING IMAGE")
        print(f"   Model: {image_model}")
        print("-"*80)

        image_result = conversation_handler.generate_actual_image(
            image_description=image_description,
            user_request=user_request
        )

        print(f"✅ Image Result: Success={image_result.get('success')}")
        if image_result.get('error'):
            print(f"❌ Image Error: {image_result.get('error')}")

        # ... (Rest of existing saving logic remains the same) ...
        # [Cursor: Copy the rest of the original saving/response logic here]

        card["image_description"] = image_description
        card["image_generated"] = image_result.get("success", False)
        card["image_error"] = image_result.get("error")
        card["is_placeholder"] = image_result.get("is_placeholder", False)
        card["image_prompt"] = image_result.get("prompt_used")
        card["image_url"] = image_result.get("image_url")

        image_html = None
        image_filename = None

        if image_result.get("success") and image_result.get("image_data"):
            # Extract base64 data from data URL
            image_data_url = image_result.get("image_data")

            # Parse data URL: data:image/jpeg;base64,<data>
            if image_data_url and image_data_url.startswith("data:"):
                try:
                    # Extract MIME type and base64 data
                    header, encoded = image_data_url.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1]  # Extract "image/jpeg" from "data:image/jpeg;base64"

                    # Decode base64 to bytes
                    image_bytes = base64.b64decode(encoded)

                    # Save using hash-based method
                    image_filename = content_generator._save_hashed_image(image_bytes, mime_type)

                    # Store filename instead of base64 data URL
                    card["image_data"] = image_filename

                    # Create HTML with file path (served from /static/media/)
                    image_path = f"/static/media/{image_filename}"
                    image_html = (
                        f'<img src="{image_path}" alt="Generated image" '
                        'style="max-width: 100%; height: auto; margin: 0 0 10px 0; border-radius: 8px; border: 1px solid #dee2e6;" />'
                    )
                except Exception as e:
                    print(f"Error processing image data: {e}")
                    # Fallback to original data URL if processing fails
                    card["image_data"] = image_data_url
                    image_html = (
                        f'<img src="{image_data_url}" alt="Generated image" '
                        'style="max-width: 100%; height: auto; margin: 0 0 10px 0; border-radius: 8px; border: 1px solid #dee2e6;" />'
                    )
            else:
                # Not a data URL, use as-is
                card["image_data"] = image_data_url
                image_html = (
                    f'<img src="{image_data_url}" alt="Generated image" '
                    'style="max-width: 100%; height: auto; margin: 0 0 10px 0; border-radius: 8px; border: 1px solid #dee2e6;" />'
                )

            position = (request.position or "front").lower()
            location = (request.location or "before").lower()

            card_type = card.get("card_type", "")
            if card_type == "interactive_cloze":
                target_field = "text_field"
            elif card_type == "cloze":
                target_field = "cloze_text"
            else:
                target_field = "front" if position != "back" else "back"

            current_content = card.get(target_field) or ""
            if location == "before":
                new_content = f"{image_html}\n{current_content}".strip()
            else:
                new_content = f"{current_content}\n{image_html}".strip()
            card[target_field] = new_content

        cards[card_index] = card
        save_json_file(CARDS_FILE, cards)

        message = "Generated image description."
        if image_result.get("success"):
            message = "Image generated and added to card."
        elif image_result.get("error"):
            message = image_result.get("error")

        return {
            "message": message,
            "card": card,
            "image": {
                "success": image_result.get("success", False),
                "is_placeholder": image_result.get("is_placeholder", False),
                "error": image_result.get("error"),
                "description": image_description
            }
        }

    except Exception as e:
        print(f"Image generation endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")
