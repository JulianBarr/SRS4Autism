from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Set
import json
import os
from datetime import datetime
import requests
from urllib.parse import urlencode
from collections import defaultdict
from html import unescape
import csv
import io
import re
import unicodedata
from functools import lru_cache, partial
import asyncio
from pathlib import Path
from .core.config import PROJECT_ROOT, PROFILES_FILE, CARDS_FILE, ANKI_PROFILES_FILE, CHAT_HISTORY_FILE, PROMPT_TEMPLATES_FILE, WORD_KP_CACHE_FILE, MODEL_CONFIG_FILE, ENGLISH_SIMILARITY_FILE, GRAMMAR_CORRECTIONS_FILE, MASTER_KG_FILE
from .utils.pinyin_utils import get_word_knowledge, get_word_image_map, fetch_word_knowledge_points, fix_iu_ui_tone_placement
from .utils.common import (
    load_json_file,
    save_json_file,
    normalize_to_slug,
    normalize_for_kp_id,
    generate_kp_id,
    contains_chinese_chars,
    split_tag_annotations,
    TAG_ANNOTATION_PREFIXES,
    CHINESE_CHAR_PATTERN
)
from database.kg_client import KnowledgeGraphClient, normalize_for_kg
import math
import tempfile
import zipfile
import shutil
import re
import logging


# Database imports
import sys
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_db, init_db, get_db_session
from database.services import ProfileService, CardService, ChatService
from sqlalchemy.orm import Session
from fastapi import Depends

import google.generativeai as genai

# Configure logging
logger = logging.getLogger(__name__)

print(f"PROJECT_ROOT: {PROJECT_ROOT}")

from openai import OpenAI
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "../gemini.env"))
except Exception:
    pass

app = FastAPI(title="Curious Mario API", version="1.0.0")

# Include routers
try:
    from .routers import literacy
    app.include_router(literacy.router)
except ImportError:
    # Fallback for absolute import
    import sys
    from pathlib import Path
    routers_path = Path(__file__).parent / "routers"
    if routers_path.exists():
        sys.path.insert(0, str(Path(__file__).parent))
        from routers import literacy
        app.include_router(literacy.router)

from .routers import pinyin_admin
app.include_router(pinyin_admin.router, prefix="/pinyin", tags=["pinyin-admin"])

from .routers import recommendations
app.include_router(recommendations.router, tags=["recommendations"])
app.include_router(recommendations.router_integrated, tags=["recommendations"])


from .routers import profiles
app.include_router(profiles.router, tags=["profiles"])

from .routers import cards
# Inject the Gemini model into cards router (will be set after Gemini initialization below)

from .routers import chat
app.include_router(chat.router, tags=["chat"])
# cards._set_genai_model will be called after _genai_model is initialized
app.include_router(cards.router, tags=["cards"])


# ============================================================================
# KG_Map Helper Functions (Following Strict Schema from Knowledge Tracking Spec)
# ============================================================================

def build_kg_map_strict(card_mappings: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Build _KG_Map JSON following the strict schema from Knowledge Tracking Specification.
    
    Schema:
    {
      "0": [
        { "kp": "word-en-apple", "skill": "sound_to_concept", "weight": 1.0 }
      ],
      "1": [
        { "kp": "word-en-apple", "skill": "concept_to_sound", "weight": 1.0 }
      ]
    }
    
    Args:
        card_mappings: Dict mapping card index (as string "0", "1", etc.) to list of KnowledgeTrace dicts.
                      Each KnowledgeTrace must have: kp (str), skill (str), weight (float, optional), context (str, optional)
    
    Returns:
        JSON string for _KG_Map field
    
    Valid Skill IDs (from Section 3):
    - Cognitive Layer: concept_to_sound, sound_to_concept
    - Literacy Layer: form_to_sound, sound_to_form, phonics_decoding, pinyin_assembly
    - Comprehension Layer: form_to_concept, concept_to_form
    """
    # Validate skill IDs
    VALID_SKILLS = {
        # Cognitive Layer
        "concept_to_sound", "sound_to_concept",
        # Literacy Layer
        "form_to_sound", "sound_to_form", "phonics_decoding", "pinyin_assembly",
        # Comprehension Layer
        "form_to_concept", "concept_to_form"
    }
    
    validated_map = {}
    for card_index, traces in card_mappings.items():
        validated_traces = []
        for trace in traces:
            if "kp" not in trace or "skill" not in trace:
                raise ValueError(f"KnowledgeTrace must have 'kp' and 'skill' fields: {trace}")
            
            skill = trace["skill"]
            if skill not in VALID_SKILLS:
                raise ValueError(f"Invalid skill ID '{skill}'. Must be one of: {sorted(VALID_SKILLS)}")
            
            validated_trace = {
                "kp": trace["kp"],
                "skill": skill,
                "weight": trace.get("weight", 1.0),
            }
            if "context" in trace:
                validated_trace["context"] = trace["context"]
            
            validated_traces.append(validated_trace)
        
        validated_map[str(card_index)] = validated_traces
    
    return json.dumps(validated_map, ensure_ascii=False)

# ============================================================================
# Pure Hash Media File Naming Strategy
# ============================================================================

def get_pure_hash_filename(original_filename: str, file_data: bytes) -> str:
    """
    Pure Hash strategy for media files: use 12-char hash filenames without prefixes.
    
    Logic:
    1. If the source filename matches hash regex (^[a-fA-F0-9]{12}\.\w+$), use it AS IS
    2. If it's a legacy name, generate a clean 12-char hash identifier from content
    
    Args:
        original_filename: The original filename (may be hash or legacy name)
        file_data: The file content bytes (used to generate hash for legacy names)
    
    Returns:
        Pure hash filename in format: {12-char-hex-hash}.{ext}
        Example: "5f29a2dff705.jpg"
    """
    import hashlib
    
    # Check if filename already matches pure hash pattern: 12 hex chars + extension
    hash_pattern = re.compile(r'^[a-fA-F0-9]{12}\.\w+$', re.IGNORECASE)
    
    if hash_pattern.match(original_filename):
        # Already a pure hash filename, use as-is
        return original_filename
    
    # Legacy filename: generate 12-char hash from content
    # Use MD5 (consistent with existing code) and take first 12 chars
    content_hash = hashlib.md5(file_data).hexdigest()[:12]
    
    # Get extension from original filename
    file_ext = Path(original_filename).suffix.lower()
    
    # Normalize .jpeg to .jpg
    if file_ext == ".jpeg":
        file_ext = ".jpg"
    
    # Ensure extension starts with dot
    if not file_ext.startswith('.'):
        file_ext = f".{file_ext}"
    
    # If no extension, default to empty string (will result in just the hash)
    if not file_ext:
        file_ext = ""
    
    # Return pure hash filename
    return f"{content_hash}{file_ext}"

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Curious Mario API...")
    print("📊 Initializing database...")
    init_db()
    from backend.database.db import DB_PATH
    print(f"🚀 ACTIVE DATABASE PATH: {DB_PATH}")
    print("✅ Database ready!")
    
    # Initialize literacy cache (Anki order + sorted vocab list)
    try:
        from .routers.literacy import initialize_literacy_cache
        initialize_literacy_cache()
    except ImportError:
        # Fallback for absolute import
        from routers.literacy import initialize_literacy_cache
        initialize_literacy_cache()
    except Exception as e:
        print(f"⚠️  Warning: Failed to initialize literacy cache: {e}")
        # Continue startup even if cache init fails


# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models




# File paths for data storage (relative to project root)
# Get project root: backend/app/main.py -> project root is 2 levels up

# Ensure data directories exist


# Gemini configuration for fallback knowledge lookups
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
_genai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _genai_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        # Inject Gemini model into cards router
        cards._set_genai_model(_genai_model)
    except Exception as exc:
        print(f"⚠️ Unable to configure Gemini model: {exc}")
else:
    print("⚠️ GEMINI_API_KEY not set; falling back to cache-only knowledge lookup.")

    _word_kp_cache = {}

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
        
        if api_key:
            print(f"   🚀 Initializing Client -> URL: {base_url} | Key: {api_key[:6]}...***")
            try:
                return OpenAI(api_key=api_key, base_url=base_url)
            except Exception as e:
                print(f"Client init failed: {e}")
        return None
    return _genai_model  # Default fallback



# Note type normalization (CUMA-prefixed models)
NOTE_TYPE_SLUG_MAP = {
    "cuma-interactive-cloze": "CUMA - Interactive Cloze",
    "interactive-cloze": "CUMA - Interactive Cloze",
    "interactive_cloze": "CUMA - Interactive Cloze",
    "cuma-basic": "CUMA - Basic",
    "basic": "CUMA - Basic",
    "cuma-basic-and-reversed-card": "CUMA - Basic (and reversed card)",
    "basic-and-reversed-card": "CUMA - Basic (and reversed card)",
    "basicand-reversed-card": "CUMA - Basic (and reversed card)",
    "cuma-cloze": "CUMA - Cloze",
    "cloze": "CUMA - Cloze",
}


def resolve_note_type_name(value: str) -> str:
    """Resolve note type slugs/aliases to canonical CUMA-prefixed names."""
    if not value:
        return value
    candidate = value.strip()
    if not candidate:
        return candidate
    slug = normalize_to_slug(candidate.replace('_', '-'))
    canonical = NOTE_TYPE_SLUG_MAP.get(slug)
    if canonical:
        return canonical
    if candidate.lower().startswith("cuma -"):
        return candidate
    return candidate


@lru_cache(maxsize=256)













# API Routes

@app.get("/")
async def root():
    return {"message": "Curious Mario API is running"}


# Configuration endpoints
@app.get("/config/models")
async def get_available_models():
    """Get available AI models for card and image generation."""
    model_config = load_json_file(MODEL_CONFIG_FILE, {
        "card_models": [],
        "image_models": []
    })
    return model_config


# [Keep all imports at the top unchanged]
# ... (imports remain the same)




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
    Handles media processing: uploads local images to Anki and rewrites HTML src paths.
    """
    try:
        import sys
        import os
        import re
        import base64
        import shutil
        from pathlib import Path
        
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
        cards_to_sync = [dict(card) for card in all_cards if card["id"] in card_ids]  # Make a copy to modify
        
        if not cards_to_sync:
            raise HTTPException(status_code=404, detail="No cards found to sync")
        
        # Initialize AnkiConnect client
        anki = AnkiConnect()
        
        if not anki.ping():
            raise HTTPException(
                status_code=503, 
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed."
            )
        
        # --- MEDIA PROCESSING LOGIC ---
        # Directory where CUMA stores generated images
        MEDIA_DIR = PROJECT_ROOT / "content" / "media" / "objects"
        
        # Cache for uploaded files to avoid re-uploading duplicates
        uploaded_media_cache = {}

        def process_html_content(html_content: str) -> str:
            """
            Scans HTML for local images, uploads them to Anki, and rewrites the src attribute.
            /static/media/foo.png -> foo.png
            """
            if not html_content:
                return html_content

            # Regex to find <img src="..."> tags
            img_pattern = r'(<img[^>]+src=["\'])([^"\']+)(["\'][^>]*>)'
            
            def replace_image_src(match):
                prefix, src, suffix = match.groups()
                
                # Skip external URLs (http/https) or data URIs
                if src.startswith(('http:', 'https:', 'data:')):
                    return match.group(0)
                
                # Extract filename from path (e.g., /static/media/abc.png -> abc.png)
                filename = Path(src).name
                
                # Check if we've already processed this file in this batch
                if filename in uploaded_media_cache:
                    return f'{prefix}{filename}{suffix}'
                
                # Look for the file in CUMA's media directories
                # 1. Try the hash-based object storage (primary)
                source_file = MEDIA_DIR / filename
                
                # 2. Fallback to legacy paths if not found
                if not source_file.exists():
                    legacy_paths = [
                        PROJECT_ROOT / "media" / filename,
                        PROJECT_ROOT / "media" / "visual_images" / filename,
                        PROJECT_ROOT / "media" / "images" / filename,
                    ]
                    for path in legacy_paths:
                        if path.exists():
                            source_file = path
                            break
                
                if source_file and source_file.exists():
                    try:
                        # Read and upload to Anki
                        with open(source_file, 'rb') as f:
                            file_data = f.read()
                            base64_data = base64.b64encode(file_data).decode('utf-8')
                            
                        # Upload using AnkiConnect (returns the filename used by Anki)
                        stored_filename = anki.store_media_file(filename, base64_data)
                        
                        print(f"  ✅ Uploaded media to Anki: {filename} -> {stored_filename}")
                        uploaded_media_cache[filename] = stored_filename
                        
                        # Return the tag with the simple filename (no path)
                        return f'{prefix}{stored_filename}{suffix}'
                    except Exception as e:
                        print(f"  ⚠️ Failed to upload media {filename}: {e}")
                        return match.group(0) # Return original on failure
                else:
                    print(f"  ⚠️ Local media file not found: {filename}")
                    return match.group(0)

            # Perform the substitution
            return re.sub(img_pattern, replace_image_src, html_content)

        # Process all cards before syncing
        print(f"🔄 Preparing {len(cards_to_sync)} cards for sync (checking media)...")
        
        for card in cards_to_sync:
            # 1. Process media in all rich-text fields
            # CUMA cards use these fields
            fields_to_process = ['front', 'back', 'text_field', 'extra_field', 'cloze_text']
            
            for field in fields_to_process:
                if field in card and card[field]:
                    card[field] = process_html_content(card[field])
            
            # 2. Build Remarks (same as before)
            from .routers.chat import build_cuma_remarks
            remarks = build_cuma_remarks(card, [])
            card["field__Remarks"] = remarks or ""
            card.pop("field__Remarks_annotations", None)
        
        # Sync cards
        print(f"🚀 Sending cards to AnkiConnect...")
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))







@app.post("/kg/chinese-ppr-recommendations")
async def get_chinese_ppr_recommendations(request):
    from .routers.recommendations import ChinesePPRRecommendationRequest
    request = ChinesePPRRecommendationRequest(**request) if isinstance(request, dict) else request
    """
    Get Chinese vocabulary recommendations using Personalized PageRank (PPR) algorithm.
    
    Uses semantic similarity graph, mastered words, and probability-based scoring.
    Returns top N words to learn next based on PPR scores combined with concreteness,
    frequency, and age of acquisition.
    """
    try:
        print(f"\n📚 Getting Chinese PPR recommendations for profile '{request.profile_id}'")
        
        # Import Chinese PPR service
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from services.chinese_ppr_recommender_service import get_chinese_ppr_service
        
        # Load mastered words from database if not provided
        mastered_words = request.mastered_words
        if not mastered_words:
            db = next(get_db())
            try:
                mastered_words = ProfileService.get_mastered_words(db, request.profile_id, 'zh')
                print(f"   📘 Loaded {len(mastered_words)} mastered Chinese words from database")
            finally:
                db.close()
        
        if not mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words found. Add some words to get recommendations."
            }
        
        # Build configuration from request
        config = {}
        if request.alpha is not None:
            config["alpha"] = request.alpha
        if request.beta_ppr is not None:
            config["beta_ppr"] = request.beta_ppr
        if request.beta_concreteness is not None:
            config["beta_concreteness"] = request.beta_concreteness
        if request.beta_frequency is not None:
            config["beta_frequency"] = request.beta_frequency
        if request.beta_aoa_penalty is not None:
            config["beta_aoa_penalty"] = request.beta_aoa_penalty
        if request.beta_intercept is not None:
            config["beta_intercept"] = request.beta_intercept
        if request.mental_age is not None:
            config["mental_age"] = request.mental_age
        if request.aoa_buffer is not None:
            config["aoa_buffer"] = request.aoa_buffer
        if request.exclude_multiword is not None:
            config["exclude_multiword"] = request.exclude_multiword
        if request.top_n is not None:
            config["top_n"] = request.top_n
        
        # Get Chinese PPR service (lazy-loaded singleton)
        similarity_file = PROJECT_ROOT / "data" / "content_db" / "chinese_word_similarity.json"
        # Use rescued KG with 27K Chinese words, 18K English words, characters, and concepts
        kg_file = MASTER_KG_FILE
        
        service = get_chinese_ppr_service(
            similarity_file=similarity_file,
            kg_file=kg_file,
            config=config
        )
        
        # Get recommendations
        recommendations = service.get_recommendations(
            mastered_words=mastered_words,
            profile_id=request.profile_id,
            exclude_words=request.exclude_words,
            **config
        )
        
        print(f"   ✅ Found {len(recommendations)} Chinese recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations",
            "config_used": config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting Chinese PPR recommendations: {str(e)}")


@app.post("/recommendations/integrated")
async def get_integrated_recommendations(
    request,
    db: Session = Depends(get_db)
):
    from .routers.recommendations import IntegratedRecommendationRequest
    if not isinstance(request, IntegratedRecommendationRequest):
        request = IntegratedRecommendationRequest(**request)
    """
    Get integrated recommendations using three-stage funnel:
    1. Candidate Generation: PPR + ZPD Filter
    2. Campaign Manager: Inventory Logic (allocates slots based on profile ratios)
    3. Synergy Matcher: (skipped for now)
    
    Returns recommendations allocated according to profile's daily capacity and target ratios.
    """
    try:
        print(f"\n🎯 Getting integrated recommendations for profile '{request.profile_id}'")
        
        # Get profile
        profile = ProfileService.get_by_id(db, request.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{request.profile_id}' not found")
        
        # Import integrated recommender service
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from services.integrated_recommender_service import IntegratedRecommenderService
        
        # Initialize integrated recommender
        recommender = IntegratedRecommenderService(profile, db)
        
        # Build PPR config overrides
        ppr_config = {}
        if request.alpha is not None:
            ppr_config["alpha"] = request.alpha
        if request.beta_ppr is not None:
            ppr_config["beta_ppr"] = request.beta_ppr
        if request.beta_concreteness is not None:
            ppr_config["beta_concreteness"] = request.beta_concreteness
        if request.beta_frequency is not None:
            ppr_config["beta_frequency"] = request.beta_frequency
        if request.beta_aoa_penalty is not None:
            ppr_config["beta_aoa_penalty"] = request.beta_aoa_penalty
        if request.beta_intercept is not None:
            ppr_config["beta_intercept"] = request.beta_intercept
        if request.mental_age is not None:
            ppr_config["mental_age"] = request.mental_age
        if request.aoa_buffer is not None:
            ppr_config["aoa_buffer"] = request.aoa_buffer
        if request.exclude_multiword is not None:
            ppr_config["exclude_multiword"] = request.exclude_multiword
        if request.top_n is not None:
            ppr_config["top_n"] = request.top_n
        if request.max_hsk_level is not None and request.language == "zh":
            ppr_config["max_hsk_level"] = request.max_hsk_level
        
        # Get recommendations
        recommendations = recommender.get_recommendations(
            language=request.language,
            mastered_words=request.mastered_words,
            **ppr_config
        )
        
        # Convert to dict format for JSON response
        recommendations_dict = [
            {
                "node_id": rec.node_id,
                "label": rec.label,
                "content_type": rec.content_type,
                "language": rec.language,
                "score": rec.score,
                "ppr_score": rec.ppr_score,
                "zpd_score": rec.zpd_score,
                "mastery": rec.mastery,
                "hsk_level": rec.hsk_level,
                "cefr_level": rec.cefr_level,
                "prerequisites": rec.prerequisites or [],
                "missing_prereqs": rec.missing_prereqs or []
            }
            for rec in recommendations
        ]
        
        print(f"   ✅ Found {len(recommendations)} integrated recommendations")
        print(f"   📊 Allocation: {recommender.vocab_slots} vocab, {recommender.grammar_slots} grammar")
        print(f"   📊 Ratios: {recommender.vocab_ratio:.1%} vocab, {recommender.grammar_ratio:.1%} grammar")
        
        return {
            "recommendations": recommendations_dict,
            "allocation": {
                "daily_capacity": recommender.daily_capacity,
                "vocab_slots": recommender.vocab_slots,
                "grammar_slots": recommender.grammar_slots,
                "vocab_ratio": recommender.vocab_ratio,
                "grammar_ratio": recommender.grammar_ratio
            },
            "message": f"Found {len(recommendations)} recommendations"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting integrated recommendations: {str(e)}")



# Get HSK vocabulary for mastered words management
@app.get("/vocabulary/hsk")
async def get_hsk_vocabulary(hsk_level: Optional[int] = None):
    """
    Get HSK vocabulary words, optionally filtered by HSK level.
    Returns words with their pinyin, HSK level, and simplified/traditional forms.
    """
    try:
        import csv
        from pathlib import Path
        
        # Path to HSK vocabulary CSV
        vocab_file = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"
        
        if not vocab_file.exists():
            raise HTTPException(status_code=404, detail="HSK vocabulary file not found")
        
        words = []
        with open(vocab_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    word_hsk = int(row.get('hsk_level', 0))
                    if hsk_level is None or word_hsk == hsk_level:
                        words.append({
                            'word': row.get('word', '').strip(),
                            'pinyin': row.get('pinyin', '').strip(),
                            'hsk_level': word_hsk,
                            'traditional': row.get('traditional', '').strip() if 'traditional' in row else None
                        })
                except (ValueError, KeyError):
                    continue
        
        return {
            "words": words,
            "total": len(words),
            "filtered_by": hsk_level
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading vocabulary: {str(e)}")

# Get CEFR English vocabulary for mastered words management
@app.get("/vocabulary/cefr")
async def get_cefr_vocabulary(cefr_level: Optional[str] = None):
    """
    Get English vocabulary words with CEFR levels, optionally filtered by CEFR level.
    Returns words with their definitions, CEFR level, and part of speech.
    """
    try:
        import csv
        from pathlib import Path
        
        # Path to CEFR-J vocabulary CSV files
        cefrj_dir = PROJECT_ROOT.parent / "olp-en-cefrj"
        cefrj_file = cefrj_dir / "cefrj-vocabulary-profile-1.5.csv"
        octanove_file = cefrj_dir / "octanove-vocabulary-profile-c1c2-1.0.csv"
        
        words = []
        word_set = set()  # Track unique words to avoid duplicates
        
        # Load CEFR-J main vocabulary
        if cefrj_file.exists():
            with open(cefrj_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    headword = row.get('headword', '').strip()
                    cefr = row.get('CEFR', '').strip()
                    pos = row.get('pos', '').strip()
                    
                    if headword and cefr:
                        # Handle variants like "catalog/catalogue"
                        variants = [v.strip() for v in headword.split('/')]
                        for variant in variants:
                            if variant.lower() not in word_set:
                                if cefr_level is None or cefr == cefr_level:
                                    words.append({
                                        'word': variant,
                                        'cefr_level': cefr,
                                        'pos': pos,
                                        'definition': ''  # CEFR-J doesn't include definitions
                                    })
                                    word_set.add(variant.lower())
        
        # Load Octanove C1/C2 supplement
        if octanove_file.exists():
            with open(octanove_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    headword = row.get('headword', '').strip()
                    cefr = row.get('CEFR', '').strip()
                    pos = row.get('pos', '').strip()
                    
                    if headword and cefr:
                        variants = [v.strip() for v in headword.split('/')]
                        for variant in variants:
                            if variant.lower() not in word_set:
                                if cefr_level is None or cefr == cefr_level:
                                    words.append({
                                        'word': variant,
                                        'cefr_level': cefr,
                                        'pos': pos,
                                        'definition': ''
                                    })
                                    word_set.add(variant.lower())
        
        # Sort by CEFR level, then by word
        cefr_order = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}
        words.sort(key=lambda w: (cefr_order.get(w['cefr_level'], 99), w['word'].lower()))
        
        return {
            "words": words,
            "total": len(words),
            "filtered_by": cefr_level
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading CEFR vocabulary: {str(e)}")


# Cache for pinyin gap fill suggestions


# Get images for words (batch query)
@app.post("/vocabulary/images")
async def get_word_images(request: Dict[str, Any]):
    """
    Get image paths for a list of Chinese words.
    Returns a mapping of word -> image path (if available).
    
    Query the TTL file directly since images aren't in Fuseki yet.
    
    Request body: { "words": ["苹果", "朋友", ...] }
    Response: { "苹果": "/media/visual_images/apple.png", "朋友": null, ... }
    """
    try:
        words = request.get("words", [])
        if not words or not isinstance(words, list):
            return {}
        
        # Get word->image mapping from cache (pre-built from TTL file)
        word_image_map = get_word_image_map()
        if not word_image_map:
            return {word: None for word in words}
        
        # Simple dictionary lookup (O(1) per word, very fast!)
        result = {}
        found_count = 0
        for word in words:
            image_path = word_image_map.get(normalize_for_kg(word.strip()))
            result[word] = image_path
            if image_path:
                found_count += 1
        
        print(f"Found {found_count} images for {len(words)} words (from cache)")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting word images: {e}")
        import traceback
        traceback.print_exc()
        # Return empty dict on error (graceful degradation)
        return {word: None for word in request.get("words", [])}

# Logic City Vocabulary endpoint
class LogicCityWord(BaseModel):
    english: str
    chinese: Optional[str] = None
    pinyin: Optional[str] = None
    image_path: Optional[str] = None

def fetch_logic_city_vocabulary(page: int = 1, page_size: int = 50) -> List[LogicCityWord]:
    """
    Query Fuseki SPARQL endpoint for words tagged with learningTheme="Logic City".
    Uses optimized pagination to prevent timeouts.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (default 50)
    
    Returns:
        List of vocabulary items with English, Chinese, pinyin, and image paths.
    """
    offset = (page - 1) * page_size
    
    # Optimized query: First select word nodes, then fetch details
    # This prevents combinatorial explosion from multiple OPTIONAL joins
    query = f"""
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?englishWord ?chineseWord ?pinyin ?imagePath WHERE {{
        {{
            # Sub-query: Select English word nodes first (with pagination)
            SELECT ?w WHERE {{
                ?w a srs-kg:Word ;
                   srs-kg:learningTheme "Logic City" ;
                   rdfs:label ?text .
                FILTER (lang(?text) = "en" || REGEX(STR(?w), "word-en-"))
            }}
            ORDER BY ?text
            LIMIT {page_size}
            OFFSET {offset}
        }}

        # Get English word text
        ?w rdfs:label ?englishWord .
        FILTER (lang(?englishWord) = "en" || REGEX(STR(?w), "word-en-"))

        # Get concept
        ?w srs-kg:means ?concept .

        # Find Chinese words linked to the same concept
        OPTIONAL {{
            ?chineseWordNode a srs-kg:Word ;
                            rdfs:label ?chineseWord ;
                            srs-kg:means ?concept .
            FILTER (lang(?chineseWord) = "zh" || REGEX(STR(?chineseWordNode), "word-zh-"))

            # Get pinyin if available (try direct property first)
            OPTIONAL {{
                ?chineseWordNode srs-kg:pinyin ?pinyin .
            }}
        }}

        # Get image visualization from concept
        OPTIONAL {{
            ?concept srs-kg:hasVisualization ?imageNode .
            ?imageNode srs-kg:imageFilePath ?imagePath .
        }}
    }}
    ORDER BY ?englishWord
    """
    
    try:
        kg_client = KnowledgeGraphClient()
        result = kg_client.query(query)
        if not result:
            print("⚠️  Logic City query returned no result")
            return []
        
        if "results" not in result:
            print(f"⚠️  Logic City query result missing 'results' key: {result.keys() if isinstance(result, dict) else type(result)}")
            return []
        
        bindings = result.get("results", {}).get("bindings", [])
        
        vocabulary = []
        seen_english = set()  # Deduplicate by English word
        
        for binding in bindings:
            english = binding.get("englishWord", {}).get("value", "").strip()
            if not english or english.lower() in seen_english:
                continue
            
            seen_english.add(english.lower())
            
            chinese = None
            if "chineseWord" in binding:
                chinese = binding["chineseWord"].get("value", "").strip()
            
            pinyin = None
            if "pinyin" in binding:
                pinyin = binding["pinyin"].get("value", "").strip()
            
            image_path = None
            if "imagePath" in binding:
                img_path = binding["imagePath"].get("value", "").strip()
                # Convert to URL path (hash-based storage: files in content/media/objects/)
                if img_path:
                    # Handle paths like "content/media/objects/..." or "content/media/images/..." -> "/static/media/..."
                    if img_path.startswith("content/media/objects/"):
                        # Hash-based storage: extract filename and serve from /static/media/
                        filename = Path(img_path).name
                        image_path = f"/static/media/{filename}"
                    elif img_path.startswith("/content/media/objects/"):
                        filename = Path(img_path).name
                        image_path = f"/static/media/{filename}"
                    elif img_path.startswith("content/media/"):
                        # Legacy path: extract filename and serve from /static/media/
                        filename = Path(img_path).name
                        image_path = f"/static/media/{filename}"
                    elif img_path.startswith("/content/media/"):
                        filename = Path(img_path).name
                        image_path = f"/static/media/{filename}"
                    elif not img_path.startswith('/'):
                        # Just a filename: serve from /static/media/
                        image_path = f"/static/media/{img_path}"
                    else:
                        image_path = img_path
                    
                    # Try to resolve actual file location by searching multiple directories
                    # Extract filename and base name for matching
                    filename_with_ext = Path(image_path).name
                    filename_base = Path(filename_with_ext).stem.lower()  # Base name, lowercase for matching
                    
                    # Extract first word from filename (e.g., "april_flowers_butterflies" -> "april")
                    # This helps match "april_flowers_butterflies.jpg" to "april.png"
                    first_word = filename_base.split('_')[0] if '_' in filename_base else filename_base
                    
                    # Search in hash-based storage first, then legacy directories (for backward compatibility)
                    media_dirs = [
                        PROJECT_ROOT / "content" / "media" / "objects",  # Hash-based storage (primary)
                        PROJECT_ROOT / "media" / "images",  # Legacy
                        PROJECT_ROOT / "media" / "visual_images",  # Legacy
                        PROJECT_ROOT / "media" / "pinyin",  # Legacy
                        PROJECT_ROOT / "media"  # Legacy
                    ]
                    
                    found = False
                    # First try exact filename match
                    for media_dir in media_dirs:
                        if not media_dir.exists():
                            continue
                        potential_path = media_dir / filename_with_ext
                        if potential_path.exists() and potential_path.is_file():
                            # If found in hash-based storage, use /static/media/ path
                            if media_dir == PROJECT_ROOT / "content" / "media" / "objects":
                                image_path = f"/static/media/{filename_with_ext}"
                            else:
                                # Legacy paths: use relative path
                                rel_path = potential_path.relative_to(PROJECT_ROOT)
                                image_path = f"/{rel_path.as_posix()}"
                            found = True
                            break
                    
                    # If not found, try matching by first word (e.g., "april" matches "april.png")
                    if not found:
                        for media_dir in media_dirs:
                            if not media_dir.exists():
                                continue
                            try:
                                # Search for files matching the first word (case-insensitive)
                                for file in media_dir.iterdir():
                                    if file.is_file():
                                        file_base = file.stem.lower()
                                        file_first_word = file_base.split('_')[0] if '_' in file_base else file_base
                                        
                                        # Match if first word matches and it's an image file
                                        if file_first_word == first_word and file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                            # If found in hash-based storage, use /static/media/ path
                                            if media_dir == PROJECT_ROOT / "content" / "media" / "objects":
                                                image_path = f"/static/media/{file.name}"
                                            else:
                                                # Legacy paths: use relative path
                                                rel_path = file.relative_to(PROJECT_ROOT)
                                                image_path = f"/{rel_path.as_posix()}"
                                            found = True
                                            break
                                if found:
                                    break
                            except (PermissionError, OSError):
                                continue
                    
                    # If still not found, keep original path (will show fallback in UI)
            
            vocabulary.append(LogicCityWord(
                english=english,
                chinese=chinese,
                pinyin=pinyin,
                image_path=image_path
            ))
        
        return vocabulary
    
    except HTTPException:
        # Re-raise HTTP exceptions (like 503)
        raise
    except Exception as e:
        print(f"❌ Error querying Logic City vocabulary: {e}")
        import traceback
        traceback.print_exc()
        # Return empty list on error (graceful degradation)
        return []

@app.get("/literacy/logic-city", response_model=List[LogicCityWord])
async def get_logic_city_vocabulary(page: int = 1, page_size: int = 50):
    """
    Get vocabulary items tagged with learningTheme="Logic City" with pagination.
    
    Args:
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (default: 50, max: 100)
    
    Returns:
        List of vocabulary items with English, Chinese, pinyin, and associated images.
    """
    # Limit page_size to prevent abuse
    page_size = min(max(1, page_size), 100)
    page = max(1, page)
    
    return fetch_logic_city_vocabulary(page=page, page_size=page_size)

# Get grammar points for mastered grammar management
@app.get("/vocabulary/grammar")
async def get_grammar_points(cefr_level: Optional[str] = None, language: Optional[str] = "zh"):
    """
    Get grammar points from the knowledge graph, optionally filtered by CEFR level (A1, A2, etc.) and language.
    Returns grammar points with their structure, explanation, and CEFR level.
    
    Args:
        cefr_level: Optional CEFR level filter (A1, A2, B1, B2, etc.)
        language: Language filter - "zh" for Chinese, "en" for English (default: "zh")
    """
    try:
        # Filter by language: 
        # English grammar (CEFR-J): URI starts with "grammar-en-"
        # Chinese grammar: URI does NOT start with "grammar-en-"
        if language == "en":
            language_filter = 'FILTER(CONTAINS(STR(?gp_uri), "grammar-en-"))'
        else:
            language_filter = 'FILTER(!CONTAINS(STR(?gp_uri), "grammar-en-") && BOUND(?label_zh))'
        
        # Query the knowledge graph for grammar points
        # Use OPTIONAL for properties that might be missing, and handle language-tagged literals
        # Get both English and Chinese labels, and first example sentence (only one per grammar point)
        # First get all grammar points with their properties
        # Build CEFR level filter if specified
        cefr_filter = f'FILTER(?cefr = "{cefr_level}")' if cefr_level else ''
        
        sparql = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?gp_uri ?label_en ?label_zh ?structure ?explanation ?cefr WHERE {{
            ?gp_uri a srs-kg:GrammarPoint .
            OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }}
            OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
            OPTIONAL {{ ?gp_uri srs-kg:structure ?structure }}
            OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation }}
            OPTIONAL {{ ?gp_uri srs-kg:cefrLevel ?cefr }}
            {language_filter}
            {cefr_filter}
        }}
        ORDER BY ?cefr ?label_en
        """
        
        # Clean up query string (remove extra whitespace)
        sparql = ' '.join(sparql.split())
        
        # Query Knowledge Graph (Oxigraph)
        kg_client = KnowledgeGraphClient()
        results = kg_client.query(sparql)
        
        if not results or 'results' not in results:
            return {
                "grammar_points": [],
                "total": 0,
                "filtered_by": cefr_level
            }
        
        grammar_points = []
        seen_uris = set()  # Track seen grammar points to avoid duplicates
        
        for binding in results.get('results', {}).get('bindings', []):
            try:
                gp_uri = binding.get('gp_uri', {}).get('value', '')
                
                # Skip if we've already seen this grammar point (avoid duplicates)
                if gp_uri in seen_uris:
                    continue
                seen_uris.add(gp_uri)
                
                label_en = binding.get('label_en', {}).get('value', '')
                label_zh = binding.get('label_zh', {}).get('value', '')
                structure = binding.get('structure', {}).get('value', '')
                explanation = binding.get('explanation', {}).get('value', '')
                cefr = binding.get('cefr', {}).get('value', '')
                
                # For English grammar, use English label; for Chinese, prefer Chinese label
                if language == "en":
                    label = label_en or label_zh  # English grammar: prefer English label
                else:
                    label = label_zh or label_en  # Chinese grammar: prefer Chinese label
                
                if label:
                    # Get first example sentence for this grammar point
                    # For English grammar, look for English examples; for Chinese, look for Chinese examples
                    example_text = ''
                    example_lang = 'en' if language == 'en' else 'zh'
                    try:
                        # First try hasExample (grammar point -> sentence)
                        example_sparql = f"""
                        PREFIX srs-kg: <http://srs4autism.com/schema/>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        SELECT ?example_text WHERE {{
                            <{gp_uri}> srs-kg:hasExample ?example .
                            ?example rdfs:label ?example_text . FILTER(LANG(?example_text) = "{example_lang}")
                        }}
                        LIMIT 1
                        """
                        kg_client = KnowledgeGraphClient()
                        example_results = kg_client.query(example_sparql)
                        if example_results and 'results' in example_results:
                            bindings = example_results.get('results', {}).get('bindings', [])
                            if bindings:
                                example_text = bindings[0].get('example_text', {}).get('value', '')
                        
                        # If no result, try reverse relationship (sentence -> grammar point)
                        if not example_text:
                            example_sparql_reverse = f"""
                            PREFIX srs-kg: <http://srs4autism.com/schema/>
                            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                            SELECT ?example_text WHERE {{
                                ?example srs-kg:demonstratesGrammar <{gp_uri}> .
                                ?example rdfs:label ?example_text . FILTER(LANG(?example_text) = "{example_lang}")
                            }}
                            LIMIT 1
                            """
                            kg_client = KnowledgeGraphClient()
                            example_results_reverse = kg_client.query(example_sparql_reverse)
                            if example_results_reverse and 'results' in example_results_reverse:
                                bindings = example_results_reverse.get('results', {}).get('bindings', [])
                                if bindings:
                                    example_text = bindings[0].get('example_text', {}).get('value', '')
                    except:
                        pass  # If example query fails, just continue without example
                    
                    # For English grammar, don't include Chinese translation; for Chinese, include it
                    grammar_point_data = {
                        'gp_uri': gp_uri,  # Include URI for updating
                        'grammar_point': label,
                        'structure': structure,
                        'explanation': explanation,
                        'cefr_level': cefr,
                    }
                    
                    if language == "en":
                        # English grammar: use example_text for English examples
                        grammar_point_data['example'] = example_text
                        # Only include Chinese translation if it exists (for bilingual display)
                        if label_zh:
                            grammar_point_data['grammar_point_zh'] = label_zh
                    else:
                        # Chinese grammar: use example_chinese for Chinese examples
                        grammar_point_data['example_chinese'] = example_text
                        grammar_point_data['grammar_point_zh'] = label_zh  # Chinese translation
                    
                    grammar_points.append(grammar_point_data)
            except Exception as e:
                continue
        
        return {
            "grammar_points": grammar_points,
            "total": len(grammar_points),
            "filtered_by": cefr_level
        }
    except Exception as e:
        # If Fuseki is not available, return empty list
        print(f"Warning: Could not query grammar points from KG: {e}")
        return {
            "grammar_points": [],
            "total": 0,
            "filtered_by": cefr_level,
            "error": "Knowledge graph server may not be available"
        }

# Save grammar point corrections/edits

@app.put("/vocabulary/grammar/{gp_uri:path}")
async def update_grammar_point(gp_uri: str, grammar_data: dict):
    """
    Update a grammar point with user corrections.
    Stores corrections in a JSON file that can be applied when repopulating the knowledge graph.
    Uses :path to allow URLs with slashes in the URI.
    """
    try:
        # Load existing corrections
        corrections = load_json_file(GRAMMAR_CORRECTIONS_FILE, {})
        
        # URL decode the URI
        from urllib.parse import unquote
        decoded_uri = unquote(gp_uri)
        
        # Store the correction
        corrections[decoded_uri] = {
            'grammar_point': grammar_data.get('grammar_point', ''),
            'grammar_point_zh': grammar_data.get('grammar_point_zh', ''),
            'structure': grammar_data.get('structure', ''),
            'explanation': grammar_data.get('explanation', ''),
            'cefr_level': grammar_data.get('cefr_level', ''),
            'example_chinese': grammar_data.get('example_chinese', ''),
            'updated_at': datetime.now().isoformat()
        }
        
        # Save corrections
        save_json_file(GRAMMAR_CORRECTIONS_FILE, corrections)
        
        return {
            "message": "Grammar point updated successfully",
            "gp_uri": decoded_uri,
            "corrections": corrections[decoded_uri]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving grammar correction: {str(e)}")

@app.get("/vocabulary/grammar/corrections")
async def get_grammar_corrections():
    """Get all grammar point corrections."""
    try:
        corrections = load_json_file(GRAMMAR_CORRECTIONS_FILE, {})
        return {"corrections": corrections, "total": len(corrections)}
    except Exception as e:
        return {"corrections": {}, "total": 0, "error": str(e)}


# Character Recognition endpoints
@app.get("/character-recognition/notes")
async def get_character_recognition_notes(profile_id: str):
    """
    Get character recognition notes from database.
    Filters out mastered characters.
    Maintains the original order from the apkg file.
    """
    try:
        from database.models import CharacterRecognitionNote
        
        # Get mastered characters (separate list with language='character')
        db = next(get_db())
        try:
            # Get mastered characters from separate list
            mastered_chars = set(ProfileService.get_mastered_words(db, profile_id, 'character'))
            
            # Get all notes from database, ordered by display_order
            db_notes = db.query(CharacterRecognitionNote).order_by(CharacterRecognitionNote.display_order).all()
            
            # Convert to API format and filter mastered
            notes = []
            for db_note in db_notes:
                # Filter out mastered characters
                if db_note.character in mastered_chars:
                    continue
                
                # Parse fields JSON
                note_fields = json.loads(db_note.fields) if db_note.fields else {}
                
                note_data = {
                    'note_id': db_note.note_id,
                    'character': db_note.character,
                    'fields': note_fields
                }
                notes.append(note_data)
        finally:
            db.close()
        
        print(f"📚 Loaded {len(notes)} character recognition notes from database (filtered {len(mastered_chars)} mastered)")
        
        return {
            "notes": notes,
            "total": len(notes),
            "mastered_filtered": len(mastered_chars)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading character recognition notes: {str(e)}")

@app.post("/character-recognition/sync")
async def sync_character_recognition_notes(request: Dict[str, Any]):
    """
    Sync character recognition notes to Anki.
    Creates 7 cards per note:
    1. Concept (picture) => Character
    2. Character => Concept (picture) (reverse)
    3. MCQ (Pick Char) - Concept => Character
    4. MCQ (Pick Pic) - Character => Concept
    5-7. Word1, Word2, Word3 - MCQ cloze completion
    
    Also extracts media files from apkg and copies them to media directory.
    """
    try:
        import sys
        import os
        import shutil
        import re
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        
        profile_id = request.get("profile_id")
        note_ids = request.get("note_ids", [])
        deck_name = request.get("deck_name", "识字")
        
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id is required")
        
        if not note_ids:
            raise HTTPException(status_code=400, detail="note_ids is required")
        
        apkg_path = PROJECT_ROOT / "data" / "content_db" / "语言语文__识字__全部.apkg"
        
        # Extract media files from apkg
        # Hash-based storage: Files are in content/media/objects/
        # Note: We don't create this directory here as it should already exist from migration
        media_dir = PROJECT_ROOT / "content" / "media" / "objects"
        
        media_map = {}  # Map original filename to new path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Extract .apkg (it's a zip file)
            with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir_path)
            
            # Copy media files to media directory
            # Note: In some apkg files, media might be stored differently
            media_source = tmpdir_path / "media"
            if media_source.exists() and media_source.is_dir():
                try:
                    print(f"📁 Extracting media files from apkg...")
                    for media_file in media_source.iterdir():
                        if media_file.is_file():
                            # Copy to media directory
                            dest_file = media_dir / media_file.name
                            if not dest_file.exists():  # Don't overwrite existing files
                                shutil.copy2(media_file, dest_file)
                                print(f"  ✅ Copied {media_file.name}")
                            else:
                                print(f"  ℹ️  {media_file.name} already exists, skipping")
                            # Map original filename to URL path (hash-based storage)
                            # Files are in content/media/objects/, served at /static/media/
                            media_map[media_file.name] = f"/static/media/{media_file.name}"
                except Exception as e:
                    print(f"⚠️  Warning: Could not extract media files: {e}")
            else:
                # Try to find media files in the zip directly
                try:
                    with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                        media_files = [f for f in zip_ref.namelist() if f.startswith('media/') and not f.endswith('/')]
                        if media_files:
                            print(f"📁 Extracting {len(media_files)} media files from apkg...")
                            for media_path in media_files:
                                filename = Path(media_path).name
                                if filename:  # Skip directories
                                    dest_file = media_dir / filename
                                    if not dest_file.exists():
                                        with zip_ref.open(media_path) as source_file:
                                            with open(dest_file, 'wb') as dest:
                                                shutil.copyfileobj(source_file, dest)
                                        print(f"  ✅ Extracted {filename}")
                                    # Map original filename to URL path (hash-based storage)
                                    # Files are in content/media/objects/, served at /static/media/
                                    media_map[filename] = f"/static/media/{filename}"
                except Exception as e:
                    print(f"⚠️  Warning: Could not extract media files from zip: {e}")
            
        # Get the notes from the database
        from database.models import CharacterRecognitionNote
        
        db = next(get_db())
        try:
            # Get notes from database
            db_notes = db.query(CharacterRecognitionNote).filter(
                CharacterRecognitionNote.note_id.in_(note_ids)
            ).order_by(CharacterRecognitionNote.display_order).all()
            
            notes_to_sync = []
            for db_note in db_notes:
                note_fields = json.loads(db_note.fields) if db_note.fields else {}
                notes_to_sync.append({
                    'note_id': db_note.note_id,
                    'character': db_note.character,
                    'fields': note_fields
                })
        finally:
            db.close()
        
        if not notes_to_sync:
            raise HTTPException(status_code=404, detail="No notes found to sync")
        
        # Initialize AnkiConnect client
        anki = AnkiConnect()
        
        # Check connection
        if not anki.ping():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed."
            )
        
        # Create deck if it doesn't exist
        try:
            anki.create_deck(deck_name)
        except:
            pass  # Deck might already exist
        
        # Step 1: Collect all image files referenced in the notes and upload them to Anki
        # Pure Hash strategy: Use 12-char hash filenames without prefixes
        # Hash-based storage: Files are in content/media/objects/
        anki_media_map = {}  # Maps original filename to Anki media filename
        media_dir = PROJECT_ROOT / "content" / "media" / "objects"  # Updated to hash-based storage
        
        def extract_image_filenames_from_html(html_content: str) -> set:
            """Extract all image filenames from HTML content (extract filename from any path)"""
            if not html_content:
                return set()
            
            filenames = set()
            # Pattern to match <img src="..."> or <img src='...'>
            pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
            
            for match in re.finditer(pattern, html_content):
                src_value = match.group(1)
                # Skip URLs
                if src_value.startswith('http'):
                    continue
                
                # Extract just the filename (remove any path, including /media/character_recognition/)
                # Handle both absolute paths (/media/...) and relative paths
                filename = src_value.strip()
                if '/' in filename:
                    # Get the last component (filename)
                    filename = Path(filename).name
                filename = filename.strip()
                
                if filename:  # Only add non-empty filenames
                    filenames.add(filename)
            
            return filenames
        
        # Collect all unique image filenames from all notes
        all_image_filenames = set()
        for note in notes_to_sync:
            fields = note['fields']
            for field_value in fields.values():
                if field_value and isinstance(field_value, str):
                    all_image_filenames.update(extract_image_filenames_from_html(field_value))
        
        # Upload each image file to Anki with Pure Hash naming
        import base64
        import hashlib
        
        # Track file hashes to avoid uploading duplicates
        uploaded_hashes = {}  # Maps content_hash -> anki_filename (for duplicate detection)
        
        for original_filename in all_image_filenames:
            source_file = media_dir / original_filename
            if not source_file.exists():
                print(f"⚠️  Warning: Media file not found: {original_filename}")
                continue
            
            try:
                # Read file
                with open(source_file, 'rb') as f:
                    file_data = f.read()
                
                # Calculate content hash to detect duplicates
                content_hash = hashlib.md5(file_data).hexdigest()
                
                # Check if we've already uploaded this exact file
                if content_hash in uploaded_hashes:
                    # Reuse the existing Anki filename
                    anki_media_map[original_filename] = uploaded_hashes[content_hash]
                    print(f"  ℹ️  Reusing {original_filename} → {uploaded_hashes[content_hash]} (duplicate)")
                    continue
                
                # Generate Pure Hash filename (no prefixes)
                # If filename matches hash pattern, use as-is; otherwise generate from content
                anki_filename = get_pure_hash_filename(original_filename, file_data)
                
                # Encode to base64 for AnkiConnect
                base64_data = base64.b64encode(file_data).decode('utf-8')
                
                # Upload to Anki
                stored_filename = anki.store_media_file(anki_filename, base64_data)
                anki_media_map[original_filename] = stored_filename
                uploaded_hashes[content_hash] = stored_filename
                print(f"  ✅ Uploaded {original_filename} → {stored_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to upload {original_filename}: {e}")
                # Fallback: use original filename (might cause conflicts, but better than nothing)
                anki_media_map[original_filename] = original_filename
        
        # Step 2: Update HTML to reference Anki media filenames (just filename, no path)
        # Anki does NOT support subdirectories - all files must be in collection.media root
        def update_image_references_to_anki(html_content: str, character: str) -> str:
            """Update image references to use Anki media filenames (no paths, just filename)
            
            Replaces paths like /media/character_recognition/I2.png with pure hash filenames (e.g., 5f29a2dff705.png)
            """
            if not html_content:
                return html_content
            
            # Pattern to match <img src="..."> or <img src='...'>
            pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
            
            def replace_img(match):
                img_tag = match.group(0)
                src_value = match.group(1)
                
                # Skip URLs
                if src_value.startswith('http'):
                    return img_tag
                
                # Extract just the filename (remove any path, including /media/character_recognition/)
                # Handle both absolute paths (/media/...) and relative paths
                filename = src_value.strip()
                if '/' in filename:
                    # Get the last component (filename) - this handles /media/character_recognition/I2.png
                    filename = Path(filename).name
                filename = filename.strip()
                
                # Look up in anki_media_map (maps original filename like "I2.png" to Anki filename)
                if filename in anki_media_map:
                    anki_filename = anki_media_map[filename]
                    # Replace the entire src value with just the Anki filename (no path, no subdirectory)
                    # This ensures Anki can find the file in collection.media root
                    # Example: /media/character_recognition/I2.png -> 5f29a2dff705.png (pure hash)
                    new_img_tag = re.sub(
                        r'src=["\']([^"\']+)["\']',
                        f'src="{anki_filename}"',
                        img_tag,
                        count=1
                    )
                    print(f"  🔄 Replaced image: {src_value} -> {anki_filename}")
                    return new_img_tag
                else:
                    # If not in map, try to extract and warn
                    print(f"  ⚠️  Warning: Image filename '{filename}' (from '{src_value}') not found in uploaded media map")
                    print(f"     Available keys: {list(anki_media_map.keys())[:5]}...")
                
                return img_tag
            
            return re.sub(pattern, replace_img, html_content)
        
        # Create cards for each note
        cards_created = 0
        errors = []
        
        for note in notes_to_sync:
            try:
                fields = note['fields']
                character = note['character']
                
                # Update all fields to use Anki media filenames
                processed_fields = {}
                for field_name, field_value in fields.items():
                    if field_value and isinstance(field_value, str):
                        processed_fields[field_name] = update_image_references_to_anki(field_value, character)
                    else:
                        processed_fields[field_name] = field_value or ""
                
                # Build _KG_Map following strict schema (Section 4 of Knowledge Tracking Spec)
                # Character recognition creates 7 cards (indices 0-6):
                # Card 0: Concept (picture) => Character (form_to_concept)
                # Card 1: Character => Concept (concept_to_form)
                # Card 2: MCQ Pick Char - Concept => Character (form_to_concept)
                # Card 3: MCQ Pick Pic - Character => Concept (concept_to_form)
                # Cards 4-6: Word examples with character cloze (form_to_concept)
                
                # For now, map all cards to the character knowledge point
                # TODO: Map individual cards to specific skills based on card type
                char_kp = f"char-zh-{character}"  # Knowledge point URI for the character
                
                card_mappings = {
                    "0": [{"kp": char_kp, "skill": "form_to_concept", "weight": 1.0}],  # Picture => Character
                    "1": [{"kp": char_kp, "skill": "concept_to_form", "weight": 1.0}],  # Character => Picture
                    "2": [{"kp": char_kp, "skill": "form_to_concept", "weight": 0.8}],  # MCQ Pick Char (hint available)
                    "3": [{"kp": char_kp, "skill": "concept_to_form", "weight": 0.8}],  # MCQ Pick Pic (hint available)
                    "4": [{"kp": char_kp, "skill": "form_to_concept", "weight": 0.6}],  # Word example 1 (context)
                    "5": [{"kp": char_kp, "skill": "form_to_concept", "weight": 0.6}],  # Word example 2 (context)
                    "6": [{"kp": char_kp, "skill": "form_to_concept", "weight": 0.6}],  # Word example 3 (context)
                }
                kg_map_json = build_kg_map_strict(card_mappings)
                
                # Add _KG_Map and _Remarks to the fields
                processed_fields["_KG_Map"] = kg_map_json
                if "_Remarks" not in processed_fields:
                    processed_fields["_Remarks"] = f"Character Recognition - {character}"
                
                # Create ONE note - the note type template will create 7 cards
                note_type = "CUMA - Chinese Recognition"
                note_id = anki.add_note(deck_name, note_type, processed_fields)
                cards_created += 7  # The note type creates 7 cards
                
            except Exception as e:
                errors.append({
                    "note_id": note.get('note_id', 'unknown'),
                    "character": note.get('character', 'unknown'),
                    "error": str(e)
                })
        
        notes_synced_successfully = len(notes_to_sync) - len(errors)
        print(f"✅ Synced {notes_synced_successfully} notes (creating {cards_created} cards) from {len(notes_to_sync)} notes to deck '{deck_name}'")
        if errors:
            print(f"⚠️  {len(errors)} errors occurred")
        
        return {
            "message": f"Synced {notes_synced_successfully} notes successfully",
            "cards_created": cards_created,
            "notes_synced": notes_synced_successfully,
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing character recognition notes: {str(e)}")

@app.post("/character-recognition/master")
async def mark_character_mastered(request: Dict[str, Any]):
    """
    Mark a character as mastered (adds to separate mastered characters list).
    """
    try:
        profile_id = request.get("profile_id")
        characters = request.get("characters", [])
        
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id is required")
        
        if not characters:
            raise HTTPException(status_code=400, detail="characters list is required")
        
        db = next(get_db())
        try:
            from database.models import MasteredWord
            
            added_count = 0
            for char in characters:
                if not char or not char.strip():
                    continue
                
                char_clean = char.strip()
                
                # Check if already mastered
                existing = db.query(MasteredWord).filter_by(
                    profile_id=profile_id,
                    word=char_clean,
                    language='character'
                ).first()
                
                if not existing:
                    mastered_char = MasteredWord(
                        profile_id=profile_id,
                        word=char_clean,
                        language='character'
                    )
                    db.add(mastered_char)
                    added_count += 1
            
            db.commit()
            
            return {
                "message": f"Marked {added_count} character(s) as mastered",
                "added": added_count,
                "total": len(characters)
            }
        finally:
            db.close()
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error marking characters as mastered: {str(e)}")


@app.get("/word-recognition/notes")
async def get_chinese_word_recognition_notes(profile_id: str):
    """
    Get Chinese word recognition notes from database.
    Filters out mastered words.
    Maintains the original order from the apkg file.
    """
    try:
        from database.models import ChineseWordRecognitionNote
        
        # Get mastered words (Chinese)
        db = next(get_db())
        try:
            # Get mastered Chinese words
            mastered_words = set(ProfileService.get_mastered_words(db, profile_id, 'zh'))
            
            # Get all notes from database, ordered by display_order
            db_notes = db.query(ChineseWordRecognitionNote).order_by(ChineseWordRecognitionNote.display_order).all()
            
            # Convert to API format and filter mastered
            notes = []
            for db_note in db_notes:
                # Filter out mastered words
                if db_note.word in mastered_words:
                    continue
                
                # Parse fields JSON
                note_fields = json.loads(db_note.fields) if db_note.fields else {}
                
                note_data = {
                    'note_id': db_note.note_id,
                    'word': db_note.word,
                    'concept': db_note.concept,
                    'fields': note_fields
                }
                notes.append(note_data)
        finally:
            db.close()
        
        print(f"📚 Loaded {len(notes)} Chinese word recognition notes from database (filtered {len(mastered_words)} mastered)")
        
        return {
            "notes": notes,
            "total": len(notes),
            "mastered_filtered": len(mastered_words)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading Chinese word recognition notes: {str(e)}")


@app.post("/word-recognition/add-custom")
async def add_custom_word_recognition(
    word: str = Form(...),
    concept: str = Form(...),
    pinyin: str = Form(""),
    bopomofo: str = Form(""),
    image: UploadFile = File(None)
):
    """
    Add a custom word to the Chinese word recognition database.
    
    Args:
        word: Chinese word
        concept: English concept
        pinyin: Pinyin pronunciation (optional)
        bopomofo: Bopomofo/Zhuyin pronunciation (optional)
        image: Image file (optional)
    """
    try:
        import uuid
        import shutil
        from database.models import ChineseWordRecognitionNote
        from database.db import get_db
        
        # Generate unique note ID
        note_id = f"custom_{uuid.uuid4().hex[:12]}"
        
        # Prepare fields
        fields = {
            'Word': word,
            'Concept': concept,
            'Pinyin': pinyin,
            'Bopomofo': bopomofo,
            'Image': '',
            'Audio': ''
        }
        
        # Handle image upload if provided
        if image and image.filename:
            # Hash-based storage: Save to content/media/objects/
            media_dir = PROJECT_ROOT / "content" / "media" / "objects"
            media_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate safe filename
            file_ext = Path(image.filename).suffix
            safe_filename = f"custom_{word}_{uuid.uuid4().hex[:8]}{file_ext}"
            image_path = media_dir / safe_filename
            
            # Save file
            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            # Update fields with image reference
            fields['Image'] = f'<img src="/media/chinese_word_recognition/{safe_filename}" alt="{concept}">'
            print(f"   📷 Saved custom image: {safe_filename}")
        
        # Get the highest display_order and add 1
        db = next(get_db())
        try:
            max_order = db.query(ChineseWordRecognitionNote).count()
            display_order = max_order + 1
            
            # Create database entry
            new_note = ChineseWordRecognitionNote(
                note_id=note_id,
                word=word,
                concept=concept,
                display_order=display_order,
                fields=json.dumps(fields, ensure_ascii=False)
            )
            
            db.add(new_note)
            db.commit()
            
            print(f"✅ Added custom word: {word} ({concept})")
            
            return {
                "message": "Custom word added successfully",
                "note_id": note_id,
                "word": word,
                "concept": concept
            }
        finally:
            db.close()
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error adding custom word: {str(e)}")


@app.post("/chinese-naming/sync")
async def sync_chinese_naming_notes(request: Dict[str, Any]):
    """
    Sync Chinese naming notes to Anki using "CUMA - Chinese Naming v2" note type.
    
    Based on Layer 0 design:
    - Uses Initial (声母), Medial (介音), Toned Final (韵母+声调) components
    - Click-based interface (not drag-and-drop)
    - No Chinese characters displayed (reduces cognitive load)
    - Each component has a distractor
    - Components are color-coded
    
    Creates cards for verbal training focusing on:
    - Concept (picture) => Pinyin construction (Initial + Medial + Final)
    - Audio => Pinyin construction
    """
    try:
        import sys
        import os
        import re
        import base64
        import hashlib
        import random
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        from database.models import ChineseWordRecognitionNote, MasteredWord
        from database.db import get_db
        from scripts.knowledge_graph.pinyin_parser import parse_pinyin, PINYIN_INITIALS, PINYIN_MEDIALS, PINYIN_FINALS
        
        profile_id = request.get("profile_id")
        note_ids = request.get("note_ids", [])
        deck_name = request.get("deck_name", "中文命名")
        config = request.get("config", "simplified")  # "simplified" or "traditional"
        
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id is required")
        
        if not note_ids:
            raise HTTPException(status_code=400, detail="note_ids is required")
        
        # Get the notes from the database
        db = next(get_db())
        try:
            db_notes = db.query(ChineseWordRecognitionNote).filter(
                ChineseWordRecognitionNote.note_id.in_(note_ids)
            ).order_by(ChineseWordRecognitionNote.display_order).all()
            
            notes_to_sync = []
            for db_note in db_notes:
                note_fields = json.loads(db_note.fields) if db_note.fields else {}
                notes_to_sync.append({
                    'note_id': db_note.note_id,
                    'word': db_note.word,
                    'concept': db_note.concept,
                    'fields': note_fields
                })
        finally:
            db.close()
        
        if not notes_to_sync:
            raise HTTPException(status_code=404, detail="No notes found to sync")
        
        # Initialize AnkiConnect client
        anki = AnkiConnect()
        
        # Check connection
        if not anki.ping():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed."
            )
        
        # Create deck if it doesn't exist
        try:
            anki.create_deck(deck_name)
        except:
            pass  # Deck might already exist
        
        # Handle media files (images and audio)
        # Pure Hash strategy: Use 12-char hash filenames without prefixes
        # Hash-based storage: Files are in content/media/objects/
        MEDIA_DIR = PROJECT_ROOT / "content" / "media" / "objects"
        anki_media_map = {}
        uploaded_hashes = {}
        
        # Collect all media filenames (images and audio)
        all_image_filenames = set()
        all_audio_filenames = set()
        
        for note in notes_to_sync:
            fields = note['fields']
            for field_value in fields.values():
                if field_value and isinstance(field_value, str):
                    # Extract image filenames
                    img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
                    for match in re.finditer(img_pattern, field_value):
                        src_value = match.group(1)
                        if not src_value.startswith('http'):
                            all_image_filenames.add(Path(src_value).name)
                    
                    # Extract audio filenames from [sound:...] tags
                    audio_pattern = r'\[sound:([^\]]+)\]'
                    for match in re.finditer(audio_pattern, field_value):
                        audio_filename = match.group(1)
                        all_audio_filenames.add(audio_filename)
        
        # Upload images
        for original_filename in all_image_filenames:
            source_file = MEDIA_DIR / original_filename
            if not source_file.exists():
                print(f"⚠️  Warning: Image file not found: {original_filename}")
                continue
            
            try:
                with open(source_file, 'rb') as f:
                    file_data = f.read()
                
                content_hash = hashlib.md5(file_data).hexdigest()
                
                if content_hash in uploaded_hashes:
                    anki_media_map[original_filename] = uploaded_hashes[content_hash]
                    print(f"  ℹ️  Reusing {original_filename} → {uploaded_hashes[content_hash]} (duplicate)")
                    continue
                
                # Generate Pure Hash filename (no prefixes)
                anki_filename = get_pure_hash_filename(original_filename, file_data)
                
                base64_data = base64.b64encode(file_data).decode('utf-8')
                stored_filename = anki.store_media_file(anki_filename, base64_data)
                anki_media_map[original_filename] = stored_filename
                uploaded_hashes[content_hash] = stored_filename
                print(f"  ✅ Uploaded image: {original_filename} → {stored_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to upload {original_filename}: {e}")
                anki_media_map[original_filename] = original_filename
        
        # Upload audio files
        for original_filename in all_audio_filenames:
            source_file = MEDIA_DIR / original_filename
            if not source_file.exists():
                print(f"⚠️  Warning: Audio file not found: {original_filename}")
                continue
            
            try:
                with open(source_file, 'rb') as f:
                    file_data = f.read()
                
                content_hash = hashlib.md5(file_data).hexdigest()
                
                if content_hash in uploaded_hashes:
                    anki_media_map[original_filename] = uploaded_hashes[content_hash]
                    print(f"  ℹ️  Reusing {original_filename} → {uploaded_hashes[content_hash]} (duplicate)")
                    continue
                
                # Generate Pure Hash filename (no prefixes)
                anki_filename = get_pure_hash_filename(original_filename, file_data)
                
                base64_data = base64.b64encode(file_data).decode('utf-8')
                stored_filename = anki.store_media_file(anki_filename, base64_data)
                anki_media_map[original_filename] = stored_filename
                uploaded_hashes[content_hash] = stored_filename
                print(f"  ✅ Uploaded audio: {original_filename} → {stored_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to upload {original_filename}: {e}")
                anki_media_map[original_filename] = original_filename
        
        # Update media references (images and audio)
        def update_media_references(content: str) -> str:
            if not content:
                return content
            
            # Update image references
            img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
            def replace_img(match):
                img_tag = match.group(0)
                src_value = match.group(1)
                if src_value.startswith('http'):
                    return img_tag
                filename = Path(src_value).name
                if filename in anki_media_map:
                    anki_filename = anki_media_map[filename]
                    return re.sub(r'src=["\']([^"\']+)["\']', f'src="{anki_filename}"', img_tag, count=1)
                return img_tag
            
            # Update audio references [sound:...]
            audio_pattern = r'\[sound:([^\]]+)\]'
            def replace_audio(match):
                original_filename = match.group(1)
                if original_filename in anki_media_map:
                    anki_filename = anki_media_map[original_filename]
                    return f"[sound:{anki_filename}]"
                return match.group(0)
            
            content = re.sub(img_pattern, replace_img, content)
            content = re.sub(audio_pattern, replace_audio, content)
            return content
        
        # Generate notes with pinyin decomposition
        cards_created = 0
        errors = []
        
        for note in notes_to_sync:
            try:
                fields = note['fields']
                word = note['word']
                concept = note['concept']
                
                # Get pinyin from fields
                pinyin_raw = fields.get('Pinyin', '').strip()
                if not pinyin_raw:
                    # Try to extract from other fields or skip
                    print(f"⚠️  Warning: No pinyin found for word '{word}', skipping")
                    continue
                
                # Parse pinyin (handle multiple syllables - keep word as whole unit)
                syllable_pinyins = pinyin_raw.split()
                if not syllable_pinyins:
                    syllable_pinyins = [pinyin_raw]
                
                # Limit to 3 syllables (as per template design)
                if len(syllable_pinyins) > 3:
                    print(f"⚠️  Warning: Word '{word}' has {len(syllable_pinyins)} syllables, truncating to 3")
                    syllable_pinyins = syllable_pinyins[:3]
                
                # Get image and audio (shared across all cards)
                image_html = fields.get('Image', '') or fields.get('image', '')
                image_html = update_media_references(image_html)
                audio_html = fields.get('Audio', '') or fields.get('audio', '')
                audio_html = update_media_references(audio_html)
                
                # For CUMA - Chinese Naming v2: Create ONE note per word with ALL syllables
                # The note will generate 2 cards (Easy and Harder) that progressively go through all syllables
                
                # Prepare fields for all syllables (up to 3)
                anki_note_fields = {
                    'Concept': concept,
                    'Image': image_html,
                    'Audio': audio_html,
                    'FullPinyin': pinyin_raw,
                    'TotalSyllables': str(len(syllable_pinyins)),
                    'Config': config,
                }
                
                # Generate syllable options and component options for each syllable
                for syllable_idx, syllable_pinyin in enumerate(syllable_pinyins):
                    # Parse pinyin into components
                    pinyin_components = parse_pinyin(syllable_pinyin)
                    
                    # Generate syllable distractors for Easy mode
                    syllable_options = [syllable_pinyin]
                    available_syllables = [
                        'mā', 'má', 'mǎ', 'mà',
                        'shī', 'shí', 'shǐ', 'shì',
                        'zī', 'zí', 'zǐ', 'zì', 'zi',
                        'lóng', 'lǒng', 'lòng',
                        'xióng', 'xiǒng', 'xiòng'
                    ]
                    available_syllables = [s for s in available_syllables if s != syllable_pinyin]
                    if available_syllables:
                        syllable_options.extend(random.sample(available_syllables, min(3, len(available_syllables))))
                    random.shuffle(syllable_options)
                    
                    # Generate component distractors for Harder mode
                    initial_options = [pinyin_components['initial']] if pinyin_components['initial'] else []
                    medial_options = [pinyin_components['medial']] if pinyin_components['medial'] else []
                    final_options = [pinyin_components['toned_final']] if pinyin_components['toned_final'] else []
                    
                    if pinyin_components['initial']:
                        available_initials = [i for i in PINYIN_INITIALS if i != pinyin_components['initial']]
                        if available_initials:
                            initial_options.append(random.choice(available_initials))
                    
                    if pinyin_components['medial']:
                        available_medials = [m for m in PINYIN_MEDIALS if m != pinyin_components['medial']]
                        if available_medials:
                            medial_options.append(random.choice(available_medials))
                    
                    if pinyin_components['toned_final']:
                        available_finals = [f for f in PINYIN_FINALS if f != pinyin_components['final']]
                        if available_finals:
                            distractor_final = random.choice(available_finals)
                            from scripts.knowledge_graph.pinyin_parser import add_tone_to_final
                            distractor_toned = add_tone_to_final(distractor_final, pinyin_components['tone'])
                            final_options.append(distractor_toned)
                    
                    random.shuffle(initial_options)
                    random.shuffle(medial_options)
                    random.shuffle(final_options)
                    
                    # Add fields for this syllable (Syllable1, Syllable2, or Syllable3)
                    syl_num = syllable_idx + 1
                    anki_note_fields[f'Syllable{syl_num}'] = syllable_pinyin
                    anki_note_fields[f'Syllable{syl_num}Option1'] = syllable_options[0] if len(syllable_options) > 0 else ''
                    anki_note_fields[f'Syllable{syl_num}Option2'] = syllable_options[1] if len(syllable_options) > 1 else ''
                    anki_note_fields[f'Syllable{syl_num}Option3'] = syllable_options[2] if len(syllable_options) > 2 else ''
                    anki_note_fields[f'Syllable{syl_num}Option4'] = syllable_options[3] if len(syllable_options) > 3 else ''
                    
                    anki_note_fields[f'Initial{syl_num}'] = pinyin_components['initial'] or ''
                    anki_note_fields[f'Initial{syl_num}Option1'] = initial_options[0] if len(initial_options) > 0 else ''
                    anki_note_fields[f'Initial{syl_num}Option2'] = initial_options[1] if len(initial_options) > 1 else ''
                    
                    anki_note_fields[f'Medial{syl_num}'] = pinyin_components['medial'] or ''
                    anki_note_fields[f'Medial{syl_num}Option1'] = medial_options[0] if len(medial_options) > 0 else ''
                    anki_note_fields[f'Medial{syl_num}Option2'] = medial_options[1] if len(medial_options) > 1 else ''
                    
                    anki_note_fields[f'TonedFinal{syl_num}'] = pinyin_components['toned_final'] or ''
                    anki_note_fields[f'TonedFinal{syl_num}Option1'] = final_options[0] if len(final_options) > 0 else ''
                    anki_note_fields[f'TonedFinal{syl_num}Option2'] = final_options[1] if len(final_options) > 1 else ''
                
                # Fill empty fields for unused syllables (if word has < 3 syllables)
                for syl_num in range(len(syllable_pinyins) + 1, 4):
                    anki_note_fields[f'Syllable{syl_num}'] = ''
                    anki_note_fields[f'Syllable{syl_num}Option1'] = ''
                    anki_note_fields[f'Syllable{syl_num}Option2'] = ''
                    anki_note_fields[f'Syllable{syl_num}Option3'] = ''
                    anki_note_fields[f'Syllable{syl_num}Option4'] = ''
                    anki_note_fields[f'Initial{syl_num}'] = ''
                    anki_note_fields[f'Initial{syl_num}Option1'] = ''
                    anki_note_fields[f'Initial{syl_num}Option2'] = ''
                    anki_note_fields[f'Medial{syl_num}'] = ''
                    anki_note_fields[f'Medial{syl_num}Option1'] = ''
                    anki_note_fields[f'Medial{syl_num}Option2'] = ''
                    anki_note_fields[f'TonedFinal{syl_num}'] = ''
                    anki_note_fields[f'TonedFinal{syl_num}Option1'] = ''
                    anki_note_fields[f'TonedFinal{syl_num}Option2'] = ''
                
                # Build _KG_Map following strict schema (Section 4 of Knowledge Tracking Spec)
                # Chinese Naming v2 creates 2 cards:
                # Card 0 (Easy): Concept (picture) => Pinyin syllable selection (concept_to_sound)
                # Card 1 (Harder): Audio => Pinyin component construction (pinyin_assembly)
                
                word_kp = f"word-zh-{word}"  # Knowledge point URI for the word
                
                card_mappings = {
                    "0": [{"kp": word_kp, "skill": "concept_to_sound", "weight": 1.0}],  # Easy: Picture => Pinyin selection
                    "1": [{"kp": word_kp, "skill": "pinyin_assembly", "weight": 1.0}],   # Harder: Audio => Component construction
                }
                anki_note_fields["_KG_Map"] = build_kg_map_strict(card_mappings)
                anki_note_fields["_Remarks"] = f"Chinese Naming v2 - {word} ({concept})"
                
                # Create ONE note (which will generate 2 cards: Easy and Harder)
                note_type = "CUMA - Chinese Naming v2"
                anki.add_note(deck_name, note_type, anki_note_fields)
                cards_created += 2  # The note type creates 2 cards
                
                # Note: Do NOT auto-mark as mastered
                # Caregiver will manually manage the mastered list using "标记为已掌握" button
                
            except Exception as e:
                errors.append({
                    "note_id": note.get('note_id', 'unknown'),
                    "word": note.get('word', 'unknown'),
                    "error": str(e)
                })
                import traceback
                traceback.print_exc()
        
        notes_synced_successfully = len(notes_to_sync) - len(errors)
        print(f"✅ Synced {notes_synced_successfully} notes (creating {cards_created} cards) to deck '{deck_name}'")
        if errors:
            print(f"⚠️  {len(errors)} errors occurred")
        
        return {
            "message": f"Synced {notes_synced_successfully} notes successfully",
            "cards_created": cards_created,
            "notes_synced": notes_synced_successfully,
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing Chinese naming notes: {str(e)}")


# ============================================================================
# Pinyin Learning endpoints
# ============================================================================

@app.get("/pinyin/elements")
async def get_pinyin_elements(profile_id: str, db: Session = Depends(get_db)):
    """
    Get Pinyin element notes (initial/final teaching cards) from database.
    """
    try:
        from database.models import PinyinElementNote
        
        # Get all element notes, ordered by display_order
        db_notes = db.query(PinyinElementNote).order_by(PinyinElementNote.display_order).all()
        
        # Convert to API format
        notes = []
        for db_note in db_notes:
            # Parse fields JSON
            note_fields = json.loads(db_note.fields) if db_note.fields else {}
            
            note_data = {
                'note_id': db_note.note_id,
                'element': db_note.element,
                'element_type': db_note.element_type,
                'fields': note_fields
            }
            notes.append(note_data)
        
        return {
            "notes": notes,
            "total": len(notes)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading pinyin element notes: {str(e)}")


@app.get("/pinyin/syllables")
async def get_pinyin_syllables(profile_id: str, db: Session = Depends(get_db)):
    """
    Get Pinyin syllable notes from database.
    """
    try:
        from database.models import PinyinSyllableNote
        
        # Get all syllable notes, ordered by display_order
        db_notes = db.query(PinyinSyllableNote).order_by(PinyinSyllableNote.display_order).all()
        
        # Convert to API format
        notes = []
        for db_note in db_notes:
            # Parse fields JSON
            note_fields = json.loads(db_note.fields) if db_note.fields else {}
            
            note_data = {
                'note_id': db_note.note_id,
                'syllable': db_note.syllable,
                'word': db_note.word,
                'concept': db_note.concept,
                'fields': note_fields
            }
            notes.append(note_data)
        
        print(f"📚 Loaded {len(notes)} pinyin syllable notes from database")
        
        return {
            "notes": notes,
            "total": len(notes)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading pinyin syllable notes: {str(e)}")


@app.get("/api/typing-course/lesson/{lesson_id}")
async def get_typing_course_lesson(lesson_id: str):
    """
    Get typing course lesson data from data/cloze_typing_course.json.
    Returns the array of items for the specified lesson ID.
    """
    try:
        course_file = PROJECT_ROOT / "data" / "cloze_typing_course.json"
        if not course_file.exists():
            raise HTTPException(
                status_code=404, 
                detail="Typing course file not found. Please ensure data/cloze_typing_course.json exists."
            )
        
        with open(course_file, 'r', encoding='utf-8') as f:
            course_data = json.load(f)
        
        lesson_items = course_data.get(lesson_id, [])
        
        if not lesson_items:
            raise HTTPException(
                status_code=404,
                detail=f"Lesson {lesson_id} not found in course data"
            )
        
        return lesson_items
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error loading typing course lesson: {str(e)}"
        )


@app.get("/api/typing-course")
async def get_typing_course():
    """
    Get all typing course data (all lessons).
    """
    try:
        course_file = PROJECT_ROOT / "data" / "cloze_typing_course.json"
        if not course_file.exists():
            raise HTTPException(
                status_code=404, 
                detail="Typing course file not found. Please ensure data/cloze_typing_course.json exists."
            )
        
        with open(course_file, 'r', encoding='utf-8') as f:
            course_data = json.load(f)
        
        return course_data
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error loading typing course: {str(e)}"
        )


@app.post("/api/typing-course/sync")
async def sync_typing_course_to_anki(request: Dict[str, Any] = None):
    """
    Sync typing course to Anki via Anki-Connect.
    First ensures Anki environment is set up, then syncs all notes.
    """
    try:
        import subprocess
        from pathlib import Path
        
        course_file = PROJECT_ROOT / "data" / "cloze_typing_course.json"
        if not course_file.exists():
            raise HTTPException(
                status_code=404,
                detail="Typing course file not found. Please ensure data/cloze_typing_course.json exists."
            )
        
        # Step 1: Setup Anki environment (deck and note type)
        setup_script = PROJECT_ROOT / "scripts" / "setup_anki_env.py"
        if not setup_script.exists():
            raise HTTPException(
                status_code=500,
                detail="Setup script not found: scripts/setup_anki_env.py"
            )
        
        print("Running Anki environment setup...")
        setup_result = subprocess.run(
            [sys.executable, str(setup_script)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        if setup_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Anki environment setup failed: {setup_result.stderr or setup_result.stdout}"
            )
        
        # Step 2: Sync notes to Anki
        sync_script = PROJECT_ROOT / "scripts" / "sync_typing_to_anki.py"
        if not sync_script.exists():
            raise HTTPException(
                status_code=500,
                detail="Sync script not found: scripts/sync_typing_to_anki.py"
            )
        
        print("Syncing notes to Anki...")
        sync_result = subprocess.run(
            [sys.executable, str(sync_script)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        if sync_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Sync failed: {sync_result.stderr or sync_result.stdout}"
            )
        
        return {
            "message": "Successfully synced typing course to Anki via Anki-Connect",
            "details": {
                "setup_output": setup_result.stdout,
                "sync_output": sync_result.stdout,
                "setup_stderr": setup_result.stderr if setup_result.stderr else None,
                "sync_stderr": sync_result.stderr if sync_result.stderr else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing typing course to Anki: {str(e)}"
        )


@app.delete("/pinyin/syllables/{note_id}")
async def delete_pinyin_syllable(note_id: str, db: Session = Depends(get_db)):
    """
    Delete a pinyin syllable note by note_id.
    """
    try:
        from database.models import PinyinSyllableNote
        
        # Find the note
        note = db.query(PinyinSyllableNote).filter(
            PinyinSyllableNote.note_id == note_id
        ).first()
        
        if not note:
            raise HTTPException(status_code=404, detail=f"Pinyin syllable note not found: {note_id}")
        
        # Delete the note
        db.delete(note)
        db.commit()
        
        print(f"🗑️  Deleted pinyin syllable note: {note_id} (syllable: {note.syllable}, word: {note.word})")
        
        return {
            "message": f"Successfully deleted pinyin syllable note: {note_id}",
            "deleted_note": {
                "note_id": note_id,
                "syllable": note.syllable,
                "word": note.word
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting pinyin syllable note: {str(e)}")


@app.delete("/pinyin/syllables")
async def delete_pinyin_syllables_batch(request: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Delete multiple pinyin syllable notes by note_ids.
    """
    try:
        from database.models import PinyinSyllableNote
        
        note_ids = request.get("note_ids", [])
        if not note_ids:
            raise HTTPException(status_code=400, detail="note_ids array is required")
        
        # Find all notes
        notes = db.query(PinyinSyllableNote).filter(
            PinyinSyllableNote.note_id.in_(note_ids)
        ).all()
        
        if not notes:
            return {
                "message": "No notes found to delete",
                "deleted_count": 0
            }
        
        deleted_info = []
        for note in notes:
            deleted_info.append({
                "note_id": note.note_id,
                "syllable": note.syllable,
                "word": note.word
            })
            db.delete(note)
        
        db.commit()
        
        print(f"🗑️  Deleted {len(notes)} pinyin syllable notes")
        
        return {
            "message": f"Successfully deleted {len(notes)} pinyin syllable notes",
            "deleted_count": len(notes),
            "deleted_notes": deleted_info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting pinyin syllable notes: {str(e)}")


def get_pinyin_curriculum_stage(element_or_syllable: str, note_type: str, element_type: str = None) -> tuple:
    """
    Determine curriculum stage for pinyin element or syllable based on 5-stage curriculum.
    Returns (stage, sub_order) tuple for sorting:
    - stage: 1-5 (curriculum stage)
    - sub_order: 0 for initials, 1 for finals, 2 for syllables within same stage
    
    Curriculum stages:
    1. Lips & Simple Vowels: b, p, m, f + a, o, e, i, u
    2. Tip of Tongue: d, t, n, l + ai, ei, ao, ou
    3. Root of Tongue: g, k, h + an, en, in, un
    4. Teeth & Curl: z, c, s, zh, ch, sh, r + ang, eng, ing, ong, er
    5. Magic Palatals: j, q, x, y, w + compound finals
    """
    # Stage mappings
    STAGE_1_INITIALS = {'b', 'p', 'm', 'f'}
    STAGE_1_FINALS = {'a', 'o', 'e', 'i', 'u'}
    
    STAGE_2_INITIALS = {'d', 't', 'n', 'l'}
    STAGE_2_FINALS = {'ai', 'ei', 'ao', 'ou'}
    
    STAGE_3_INITIALS = {'g', 'k', 'h'}
    STAGE_3_FINALS = {'an', 'en', 'in', 'un'}
    
    STAGE_4_INITIALS = {'z', 'c', 's', 'zh', 'ch', 'sh', 'r'}
    STAGE_4_FINALS = {'ang', 'eng', 'ing', 'ong', 'er'}
    
    STAGE_5_INITIALS = {'j', 'q', 'x', 'y', 'w'}
    STAGE_5_FINALS = {'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 'ua', 'uo', 'uai', 'ui', 
                      'uan', 'uang', 'ue', 'üe', 'üan', 'ün', 'ü'}  # ü variants
    
    if note_type == 'element':
        if element_type == 'initial':
            if element_or_syllable in STAGE_1_INITIALS:
                return (1, 0)  # stage, initial comes first
            elif element_or_syllable in STAGE_2_INITIALS:
                return (2, 0)
            elif element_or_syllable in STAGE_3_INITIALS:
                return (3, 0)
            elif element_or_syllable in STAGE_4_INITIALS:
                return (4, 0)
            elif element_or_syllable in STAGE_5_INITIALS:
                return (5, 0)
        elif element_type == 'final':
            element_lower = element_or_syllable.lower()
            if element_lower in STAGE_1_FINALS:
                return (1, 1)  # stage, final comes after initial
            elif element_lower in STAGE_2_FINALS:
                return (2, 1)
            elif element_lower in STAGE_3_FINALS:
                return (3, 1)
            elif element_lower in STAGE_4_FINALS:
                return (4, 1)
            elif element_lower in STAGE_5_FINALS or any(f in element_lower for f in STAGE_5_FINALS):
                return (5, 1)
        # Default: put unknown elements at end
        return (99, 0)
    
    elif note_type == 'syllable':
        # Parse syllable to extract initial and final
        try:
            from scripts.knowledge_graph.pinyin_parser import parse_pinyin, extract_tone
            
            # Remove tone from syllable
            syllable_no_tone, _ = extract_tone(element_or_syllable)
            parsed = parse_pinyin(syllable_no_tone)
            
            initial = parsed.get('initial') or ''
            # Build final: combine medial + final (e.g., juan = j + uan = j + u + an)
            medial = parsed.get('medial') or ''
            final_part = parsed.get('final') or ''
            final = medial + final_part if final_part else medial
            
            # Handle special case: if no final was parsed but we have remaining, use it
            if not final and syllable_no_tone:
                # Simple fallback: remove initial from syllable
                if initial and syllable_no_tone.startswith(initial):
                    final = syllable_no_tone[len(initial):]
                else:
                    final = syllable_no_tone
        except Exception:
            # Fallback: simple extraction if parser fails
            initial = ''
            final = element_or_syllable
        
        # Determine stage based on initial and final (use the higher stage)
        initial_stage = 99
        final_stage = 99
        
        if initial:
            if initial in STAGE_1_INITIALS:
                initial_stage = 1
            elif initial in STAGE_2_INITIALS:
                initial_stage = 2
            elif initial in STAGE_3_INITIALS:
                initial_stage = 3
            elif initial in STAGE_4_INITIALS:
                initial_stage = 4
            elif initial in STAGE_5_INITIALS:
                initial_stage = 5
        
        if final:
            final_lower = final.lower()
            # Check Stage 5 first (longer compound finals like 'uan', 'iang')
            # Sort by length descending to match longer finals first
            stage5_matched = False
            for stage5_final in sorted(STAGE_5_FINALS, key=len, reverse=True):
                if final_lower == stage5_final or final_lower.endswith(stage5_final) or stage5_final in final_lower:
                    final_stage = 5
                    stage5_matched = True
                    break
            
            if not stage5_matched:
                if final_lower in STAGE_1_FINALS:
                    final_stage = 1
                elif final_lower in STAGE_2_FINALS:
                    final_stage = 2
                elif final_lower in STAGE_3_FINALS:
                    final_stage = 3
                elif final_lower in STAGE_4_FINALS:
                    final_stage = 4
        
        # Use the maximum stage (syllables appear after both initial and final are taught)
        stage = max(initial_stage, final_stage)
        if stage == 99:
            stage = 6  # Unknown syllables go to end
        
        return (stage, 2)  # syllables come after elements (initial=0, final=1, syllable=2)
    
    return (99, 0)

# --- NEW PINYIN SORTING LOGIC ---
# Strict Teaching Order: Simple Finals -> Initials -> Compound Finals
CURRICULUM_SEQUENCE = [
    # STAGE 1: The Basics (Simple Finals then Lips)
    'a', 'o', 'e', 'i', 'u', 'ü', 
    'b', 'p', 'm', 'f',
    
    # STAGE 2: Tip of Tongue
    'd', 't', 'n', 'l',
    'ai', 'ei', 'ao', 'ou',
    
    # STAGE 3: Root of Tongue
    'g', 'k', 'h',
    'an', 'en', 'in', 'un',
    
    # STAGE 4: Teeth & Curl
    'z', 'c', 's', 
    'zh', 'ch', 'sh', 'r',
    'ang', 'eng', 'ing', 'ong', 'er',
    
    # STAGE 5: Magic Palatals & Compounds
    'j', 'q', 'x', 'y', 'w',
    'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 
    'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 
    'ue', 'üe', 'üan', 'ün'
]

# Lookup map for O(1) speed
CURRICULUM_MAP = {val: i for i, val in enumerate(CURRICULUM_SEQUENCE)}

def get_pinyin_sort_key(note_dict):
    """
    Returns sort key: (Curriculum_Index, Is_Syllable, Display_Order)
    1. Curriculum_Index: Ensures 'a' comes before 'b'
    2. Is_Syllable: Ensures 'a' element card (0) comes before 'ma' syllable card (1)
    3. Display_Order: Tie-breaker for manual ordering
    """
    note_type = note_dict.get('type')
    fields = note_dict.get('fields', {})
    display_order = note_dict.get('display_order', 999999)

    # Determine the "Anchor" (the pinyin element this card belongs to)
    anchor = ''
    if note_type == 'element':
        anchor = note_dict.get('element', '').lower()
        is_syllable = 0
    else:
        # Syllable cards anchor to 'ElementToLearn' (e.g., 'ma' anchors to 'a')
        anchor = fields.get('ElementToLearn', '').lower()
        # Fallback: if ElementToLearn is missing, guess from the syllable
        if not anchor:
            syllable = note_dict.get('syllable', '').strip()
            if syllable:
                # Simple heuristic: last char is often the simple final
                anchor = syllable[-1]
        is_syllable = 1
        
    curriculum_index = CURRICULUM_MAP.get(anchor, 999)
    return (curriculum_index, is_syllable, display_order)

print("🔥🔥🔥 LOADING PINYIN ROUTE 🔥🔥🔥")
@app.post("/pinyin/sync")
async def sync_pinyin_notes(request: Dict[str, Any]):
    """
    Sync pinyin notes (elements and/or syllables) to Anki.
    Combines both types in a single deck, ordered by 5-stage curriculum, then by display_order.
    
    Curriculum order:
    1. Stage 1 elements (initials, then finals) → Stage 1 syllables
    2. Stage 2 elements (initials, then finals) → Stage 2 syllables
    3. ... and so on
    """
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        from anki_integration.anki_connect import AnkiConnect
        from database.models import PinyinElementNote, PinyinSyllableNote
        from database.db import get_db
        
        profile_id = request.get("profile_id")
        element_note_ids = request.get("element_note_ids", [])
        syllable_note_ids = request.get("syllable_note_ids", [])
        deck_name = request.get("deck_name", "拼音")
        
        # Support legacy API format
        if not element_note_ids and not syllable_note_ids:
            note_ids = request.get("note_ids", [])
            note_type = request.get("note_type")
            if note_type == "element":
                element_note_ids = note_ids
            elif note_type == "syllable":
                syllable_note_ids = note_ids
        
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id is required")
        
        if not element_note_ids and not syllable_note_ids:
            raise HTTPException(status_code=400, detail="At least one note_id is required")
        
        # Get notes from database
        db = next(get_db())
        try:
            all_notes = []
            
            # Get element notes
            if element_note_ids:
                element_notes = db.query(PinyinElementNote).filter(
                    PinyinElementNote.note_id.in_(element_note_ids)
                ).all()
                for db_note in element_notes:
                    note_fields = json.loads(db_note.fields) if db_note.fields else {}
                    # Get curriculum stage for this element
                    stage, sub_order = get_pinyin_curriculum_stage(
                        db_note.element, 
                        'element', 
                        db_note.element_type
                    )
                    all_notes.append({
                        'note_id': db_note.note_id,
                        'type': 'element',
                        'display_order': db_note.display_order,
                        'fields': note_fields,
                        'element': db_note.element,
                        'element_type': db_note.element_type,
                        'curriculum_stage': stage,
                        'curriculum_sub_order': sub_order
                    })
            
            # Get syllable notes
            if syllable_note_ids:
                syllable_notes = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.note_id.in_(syllable_note_ids)
                ).all()
                for db_note in syllable_notes:
                    note_fields = json.loads(db_note.fields) if db_note.fields else {}
                    # Get curriculum stage for this syllable
                    stage, sub_order = get_pinyin_curriculum_stage(
                        db_note.syllable,
                        'syllable'
                    )
                    all_notes.append({
                        'note_id': db_note.note_id,
                        'type': 'syllable',
                        'display_order': db_note.display_order,
                        'fields': note_fields,
                        'syllable': db_note.syllable,
                        'curriculum_stage': stage,
                        'curriculum_sub_order': sub_order
                    })
            
            # Sort using strict Pinyin curriculum order
            # Ensures correct order: 'a' element before 'b' element, element cards before syllable cards
            all_notes.sort(key=get_pinyin_sort_key)
        finally:
            db.close()
        
        if not all_notes:
            return {
                "message": "No notes found to sync",
                "cards_created": 0,
                "notes_synced": 0
            }
        
        # Connect to Anki
        anki = AnkiConnect()
        if not anki.ping():
            raise HTTPException(status_code=500, detail="AnkiConnect not available")
        
        # Handle media files (images and audio)
        import base64
        import hashlib
        import re
        
        # Pure Hash strategy: Use 12-char hash filenames without prefixes
        # Hash-based storage: Files are in content/media/objects/
        MEDIA_DIR = PROJECT_ROOT / "content" / "media" / "objects"
        anki_media_map = {}  # Maps original filename to Anki media filename
        uploaded_hashes = {}  # Maps content_hash -> anki_filename (for duplicate detection)
        
        # Collect all media filenames (images and audio) from all notes
        all_image_filenames = set()
        all_audio_filenames = set()
        
        def extract_media_from_fields(fields: dict):
            """Extract image and audio filenames from note fields."""
            for field_name, field_value in fields.items():
                if not field_value or not isinstance(field_value, str):
                    continue
                
                # Extract image filenames from <img src="..."> tags
                img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
                for match in re.finditer(img_pattern, field_value):
                    src_value = match.group(1)
                    if not src_value.startswith('http') and not src_value.startswith('data:'):
                        # Extract filename (remove path)
                        filename = Path(src_value).name
                        if filename:
                            all_image_filenames.add(filename)
                
                # Extract image filenames from plain filename fields (Picture, WordPicture, etc.)
                if field_name in ['Picture', 'WordPicture', 'ConfusorPicture1', 'ConfusorPicture2', 'ConfusorPicture3']:
                    if field_value and not field_value.startswith('<img') and not field_value.startswith('http') and not field_value.startswith('data:'):
                        filename = Path(field_value).name
                        if filename:
                            all_image_filenames.add(filename)
                
                # Extract audio filenames from [sound:...] tags
                audio_pattern = r'\[sound:([^\]]+)\]'
                for match in re.finditer(audio_pattern, field_value):
                    audio_filename = match.group(1)
                    all_audio_filenames.add(audio_filename)
                
                # Extract audio filenames from plain filename fields (WordAudio, etc.)
                if field_name in ['WordAudio', 'Audio']:
                    if field_value and not field_value.startswith('[sound:') and not field_value.startswith('http'):
                        filename = Path(field_value).name
                        if filename:
                            all_audio_filenames.add(filename)
        
        # Collect media files from all notes
        for note in all_notes:
            extract_media_from_fields(note['fields'])
        
        # Upload image files
        for original_filename in all_image_filenames:
            # Try multiple possible locations
            possible_paths = [
                MEDIA_DIR / original_filename,
                PROJECT_ROOT / "media" / original_filename,
                PROJECT_ROOT / "media" / "pinyin" / original_filename,
            ]
            
            source_file = None
            for path in possible_paths:
                if path.exists():
                    source_file = path
                    break
            
            if not source_file:
                print(f"⚠️  Warning: Image file not found: {original_filename}")
                continue
            
            try:
                with open(source_file, 'rb') as f:
                    file_data = f.read()
                
                content_hash = hashlib.md5(file_data).hexdigest()
                
                # Check if we've already uploaded this file (by content hash)
                if content_hash in uploaded_hashes:
                    anki_media_map[original_filename] = uploaded_hashes[content_hash]
                    print(f"  ℹ️  Reusing {original_filename} → {uploaded_hashes[content_hash]} (duplicate)")
                    continue
                
                # Generate Pure Hash filename (no prefixes)
                anki_filename = get_pure_hash_filename(original_filename, file_data)
                
                # Upload to Anki
                base64_data = base64.b64encode(file_data).decode('utf-8')
                stored_filename = anki.store_media_file(anki_filename, base64_data)
                anki_media_map[original_filename] = stored_filename
                uploaded_hashes[content_hash] = stored_filename
                print(f"  ✅ Uploaded image: {original_filename} → {stored_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to upload {original_filename}: {e}")
                anki_media_map[original_filename] = original_filename
        
        # Upload audio files
        for original_filename in all_audio_filenames:
            # Try multiple possible locations
            possible_paths = [
                MEDIA_DIR / original_filename,
                PROJECT_ROOT / "media" / original_filename,
                PROJECT_ROOT / "media" / "pinyin" / original_filename,
            ]
            
            source_file = None
            for path in possible_paths:
                if path.exists():
                    source_file = path
                    break
            
            if not source_file:
                print(f"⚠️  Warning: Audio file not found: {original_filename}")
                continue
            
            try:
                with open(source_file, 'rb') as f:
                    file_data = f.read()
                
                content_hash = hashlib.md5(file_data).hexdigest()
                
                # Check if we've already uploaded this file
                if content_hash in uploaded_hashes:
                    anki_media_map[original_filename] = uploaded_hashes[content_hash]
                    print(f"  ℹ️  Reusing {original_filename} → {uploaded_hashes[content_hash]} (duplicate)")
                    continue
                
                # Generate Pure Hash filename (no prefixes)
                anki_filename = get_pure_hash_filename(original_filename, file_data)
                
                # Upload to Anki
                base64_data = base64.b64encode(file_data).decode('utf-8')
                stored_filename = anki.store_media_file(anki_filename, base64_data)
                anki_media_map[original_filename] = stored_filename
                uploaded_hashes[content_hash] = stored_filename
                print(f"  ✅ Uploaded audio: {original_filename} → {stored_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to upload {original_filename}: {e}")
                anki_media_map[original_filename] = original_filename
        
        # Function to normalize and update media references in fields
        def normalize_and_update_media(field_name: str, field_value: str) -> str:
            """Normalize image fields to <img src=...> format and update media references."""
            if not field_value:
                return ""
            
            # Handle image fields
            if field_name in ['Picture', 'WordPicture', 'ConfusorPicture1', 'ConfusorPicture2', 'ConfusorPicture3']:
                # If it's already an img tag, update the src
                if '<img' in field_value:
                    img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
                    def replace_img(match):
                        img_tag = match.group(0)
                        src_value = match.group(1)
                        if src_value.startswith('http') or src_value.startswith('data:'):
                            return img_tag
                        filename = Path(src_value).name
                        if filename in anki_media_map:
                            anki_filename = anki_media_map[filename]
                            return re.sub(r'src=["\']([^"\']+)["\']', f'src="{anki_filename}"', img_tag, count=1)
                        return img_tag
                    return re.sub(img_pattern, replace_img, field_value)
                else:
                    # Convert plain filename to <img src=...> format
                    filename = Path(field_value).name
                    if filename in anki_media_map:
                        anki_filename = anki_media_map[filename]
                        return f'<img src="{anki_filename}">'
                    elif filename:
                        return f'<img src="{filename}">'
                    return ""
            
            # Handle audio fields
            if field_name in ['WordAudio', 'Audio']:
                # Extract filename from [sound:...] tag if present, or use plain filename
                if '[sound:' in field_value:
                    audio_pattern = r'\[sound:([^\]]+)\]'
                    match = re.search(audio_pattern, field_value)
                    if match:
                        original_filename = match.group(1)
                        # Return plain filename (mapped if available)
                        if original_filename in anki_media_map:
                            return anki_media_map[original_filename]
                        return original_filename
                    return ""
                else:
                    # Already a plain filename, just update mapping if needed
                    filename = Path(field_value).name
                    if filename in anki_media_map:
                        return anki_media_map[filename]
                    elif filename:
                        return filename
                    return ""
            
            # For other fields, update any embedded media references
            # Update image references in HTML
            img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
            def replace_img(match):
                img_tag = match.group(0)
                src_value = match.group(1)
                if src_value.startswith('http') or src_value.startswith('data:'):
                    return img_tag
                filename = Path(src_value).name
                if filename in anki_media_map:
                    anki_filename = anki_media_map[filename]
                    return re.sub(r'src=["\']([^"\']+)["\']', f'src="{anki_filename}"', img_tag, count=1)
                return img_tag
            
            # Update audio references
            audio_pattern = r'\[sound:([^\]]+)\]'
            def replace_audio(match):
                original_filename = match.group(1)
                if original_filename in anki_media_map:
                    anki_filename = anki_media_map[original_filename]
                    return f"[sound:{anki_filename}]"
                return match.group(0)
            
            result = re.sub(img_pattern, replace_img, field_value)
            result = re.sub(audio_pattern, replace_audio, result)
            return result
        
        # Sync to Anki in order
        cards_created = 0
        notes_synced = 0
        errors = []
        
        for note in all_notes:
            try:
                fields = note['fields']
                note_type = note['type']
                
                # Build Anki note fields with normalized media references
                anki_note_fields = {}
                for field_name, field_value in fields.items():
                    if field_value:
                        # Normalize and update media references
                        normalized_value = normalize_and_update_media(field_name, field_value)
                        anki_note_fields[field_name] = normalized_value
                    else:
                        anki_note_fields[field_name] = ""
                
                # Build _KG_Map following strict schema
                if note_type == "element":
                    element = fields.get('Element', '') or note.get('element', '')
                    element_kp = f"pinyin-element-{element}"
                    # Element cards are teaching cards - map to appropriate skill
                    card_mappings = {
                        "0": [{"kp": element_kp, "skill": "form_to_sound", "weight": 1.0}],  # Element => Sound
                    }
                    anki_note_type = "CUMA - Pinyin Element"
                    cards_per_note = 1
                else:  # syllable
                    syllable = fields.get('Syllable', '') or note.get('syllable', '')
                    syllable_kp = f"pinyin-syllable-{syllable}"
                    # Syllable has 6 cards (indices 0-5):
                    # Card 0: Element Card
                    # Card 1: Word to Pinyin (sound_to_form)
                    # Card 2: MCQ Recent (sound_to_form with hint)
                    # Card 3: MCQ Tone (sound_to_form with hint)
                    # Card 4: MCQ Confusor (sound_to_form with hint)
                    # Card 5: Pinyin to Word (form_to_sound)
                    card_mappings = {
                        "0": [{"kp": syllable_kp, "skill": "form_to_sound", "weight": 1.0}],  # Element Card
                        "1": [{"kp": syllable_kp, "skill": "sound_to_form", "weight": 1.0}],  # Word to Pinyin
                        "2": [{"kp": syllable_kp, "skill": "sound_to_form", "weight": 0.8}],  # MCQ Recent
                        "3": [{"kp": syllable_kp, "skill": "sound_to_form", "weight": 0.8}],  # MCQ Tone
                        "4": [{"kp": syllable_kp, "skill": "sound_to_form", "weight": 0.8}],  # MCQ Confusor
                        "5": [{"kp": syllable_kp, "skill": "form_to_sound", "weight": 1.0}],  # Pinyin to Word
                    }
                    anki_note_type = "CUMA - Pinyin Syllable"
                    cards_per_note = 6
                
                anki_note_fields["_KG_Map"] = build_kg_map_strict(card_mappings)
                
                # Create note in Anki
                anki.add_note(deck_name, anki_note_type, anki_note_fields)
                
                cards_created += cards_per_note
                notes_synced += 1
                
            except Exception as e:
                errors.append({
                    "note_id": note.get('note_id', 'unknown'),
                    "error": str(e)
                })
                import traceback
                traceback.print_exc()
        
        notes_synced_successfully = len(all_notes) - len(errors)
        print(f"✅ Synced {notes_synced_successfully} pinyin notes (creating {cards_created} cards) to deck '{deck_name}'")
        if errors:
            print(f"⚠️  {len(errors)} errors occurred")
        
        return {
            "message": f"Synced {notes_synced_successfully} notes successfully",
            "cards_created": cards_created,
            "notes_synced": notes_synced_successfully,
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing pinyin notes: {str(e)}")


@app.get("/pinyin/word-info")
async def get_pinyin_for_word(word: str):
    """
    Get pinyin and other info for a Chinese word from the knowledge graph.
    Ensures pinyin follows 'i u 并列标在后' rule.
    
    Uses get_word_knowledge which includes KG lookup, cache, and LLM fallback if needed.
    Runs in executor with timeout to prevent hanging.
    """
    import asyncio
    try:
        if not word or not word.strip():
            raise HTTPException(status_code=400, detail="word parameter is required")
        
        word_stripped = word.strip()
        
        # Use get_word_knowledge but run it in executor with timeout to prevent hanging
        # This includes KG lookup, cache, and LLM fallback if needed
        loop = asyncio.get_event_loop()
        try:
            word_info = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: get_word_knowledge(word_stripped)),
                timeout=8.0  # 8 second timeout for LLM call if needed
            )
        except asyncio.TimeoutError:
            # If timeout, fall back to KG + cache only (no LLM)
            print(f"⚠️ [word-info] Timeout for '{word_stripped}', using KG+cache only")
            info = fetch_word_knowledge_points(word_stripped) or {}
            pronunciations: List[str] = list(dict.fromkeys(info.get("pronunciations") or []))
            meanings: List[str] = list(dict.fromkeys(info.get("meanings") or []))
            hsk_level = info.get("hsk_level")
            
            # Check cache
            cached = _word_kp_cache.get(word_stripped) or {}
            cache_pinyin = cached.get("pinyin")
            cache_meaning = cached.get("meaning") or cached.get("meaning_en")
            cache_pron_list = cached.get("pronunciations") or []
            cache_meaning_list = cached.get("meanings") or []
            cache_hsk = cached.get("hsk_level")
            
            # Merge cache data
            for val in [cache_pinyin] + cache_pron_list:
                if val and val not in pronunciations:
                    pronunciations.append(val)
            for val in [cache_meaning] + cache_meaning_list:
                if val and val not in meanings:
                    meanings.append(val)
            if not hsk_level and cache_hsk:
                hsk_level = cache_hsk
            
            word_info = {
                "pronunciations": pronunciations,
                "meanings": meanings,
                "hsk_level": hsk_level
            }
        
        # Extract pinyin (use first pronunciation if available)
        pinyin = None
        if word_info.get("pronunciations"):
            pinyin = word_info["pronunciations"][0]
            # Fix tone placement for iu/ui patterns
            pinyin = fix_iu_ui_tone_placement(pinyin)
        
        # Also fix pronunciations list
        fixed_pronunciations = [fix_iu_ui_tone_placement(p) for p in word_info.get("pronunciations", [])]
        
        return {
            "word": word.strip(),
            "pinyin": pinyin,
            "pronunciations": fixed_pronunciations,
            "meanings": word_info.get("meanings", []),
            "hsk_level": word_info.get("hsk_level")
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting word info: {str(e)}")






@app.get("/pinyin/english-vocab-suggestions")
async def get_english_vocab_suggestions_for_pending():
    """
    Get English vocabulary-based suggestions for pending pinyin syllables.
    Loads pre-computed matches from JSON file (generated by match_pending_syllables_english_vocab.py).
    Returns up to 3 suggestions per syllable with radio button options.
    """
    import json
    
    try:
        # Load pre-computed matches from JSON file
        matches_file = PROJECT_ROOT / "data" / "pending_syllable_english_matches.json"
        
        if not matches_file.exists():
            return {"matches": {}, "message": "No matches file found. Run match_pending_syllables_english_vocab.py first."}
        
        with open(matches_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            "matches": data.get("matches", {}),
            "total_pending": data.get("total_pending", 0),
            "matched": data.get("matched", 0),
            "generated_at": data.get("generated_at", "")
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"matches": {}, "error": str(e)}


@app.post("/pinyin/find-and-rename-image")
async def find_and_rename_image(request: Dict[str, Any]):
    """
    Find the image for a Chinese word and rename it to the English word.
    Returns the new image filename.
    """
    import shutil
    from pathlib import Path
    
    chinese_word = request.get("chinese_word", "").strip()
    english_word = request.get("english_word", "").strip().lower().replace(" ", "_")
    
    if not chinese_word or not english_word:
        raise HTTPException(status_code=400, detail="chinese_word and english_word are required")
    
    try:
        # Find image using word-image cache (fast, no LLM calls)
        word_image_map = get_word_image_map()
        image_path = word_image_map.get(chinese_word)
        
        if not image_path:
            return {"error": f"No image found for Chinese word: {chinese_word}", "image_file": ""}
        
        # image_path might be relative or absolute
        # Check common media directories
        media_dirs = [
            PROJECT_ROOT / "media" / "visual_images",
            PROJECT_ROOT / "media" / "images",
            PROJECT_ROOT / "media" / "pinyin",
            PROJECT_ROOT / "media",
        ]
        
        source_file = None
        original_ext = None
        
        # Try to find the source file
        for media_dir in media_dirs:
            # image_path might be just filename or relative path
            potential_paths = [
                media_dir / image_path,
                media_dir / Path(image_path).name,
                PROJECT_ROOT / image_path.lstrip("/"),
            ]
            
            for path in potential_paths:
                if path.exists() and path.is_file():
                    source_file = path
                    original_ext = source_file.suffix
                    break
            
            if source_file:
                break
        
        if not source_file:
            return {"error": f"Image file not found: {image_path}", "image_file": ""}
        
        # Create new filename: {english_word}.{ext}
        new_filename = f"{english_word}{original_ext}"
        target_dir = PROJECT_ROOT / "media" / "pinyin"  # Use pinyin directory for these images
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / new_filename
        
        # Copy (don't move, in case original is used elsewhere)
        shutil.copy2(source_file, target_file)
        
        return {
            "image_file": new_filename,
            "original_path": str(source_file.relative_to(PROJECT_ROOT)),
            "new_path": str(target_file.relative_to(PROJECT_ROOT))
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "image_file": ""}












# --- 修正后的挂载逻辑 ---

# 1. 挂载媒体文件目录 (Hash-based objects)
media_objects_dir = PROJECT_ROOT / "content" / "media" / "objects"
if media_objects_dir.exists():
    app.mount("/static/media", StaticFiles(directory=str(media_objects_dir)), name="static_media")
    # 兼容旧路径 /media/images/
    app.mount("/media/images", StaticFiles(directory=str(media_objects_dir)), name="media_images")
    print(f"📂 Media mounted at: /static/media & /media/images -> {media_objects_dir}")

# 2. 挂载旧的媒体目录 (Backward compatibility)
media_dir = PROJECT_ROOT / "media"
if media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

# 3. 挂载 content 目录
content_dir = PROJECT_ROOT / "content"
if content_dir.exists():
    app.mount("/content", StaticFiles(directory=str(content_dir)), name="content")

# 4. 根目录图片重定向中间件 (处理 /xxxx.png)
class RootImageRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 匹配 12 位哈希格式的图片文件名
        if re.fullmatch(r"/(?P<filename>[0-9a-fA-F]{12}\.(png|jpg))", path):
            filename = path.lstrip("/")
            new_path = f"/static/media/{filename}"
            request.scope["path"] = new_path
            request.scope["raw_path"] = new_path.encode("ascii")
            print(f"🔄 Rewriting root image request: {path} -> {new_path}")
        
        response = await call_next(request)
        return response

app.add_middleware(RootImageRedirectMiddleware)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
