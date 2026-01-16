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
from .core.config import PROJECT_ROOT, PROFILES_FILE, CARDS_FILE, ANKI_PROFILES_FILE, CHAT_HISTORY_FILE, PROMPT_TEMPLATES_FILE, WORD_KP_CACHE_FILE, MODEL_CONFIG_FILE, ENGLISH_SIMILARITY_FILE, GRAMMAR_CORRECTIONS_FILE
from .utils.pinyin_utils import get_word_knowledge, get_word_image_map, fetch_word_knowledge_points, fix_iu_ui_tone_placement
import math
import tempfile
import zipfile
import shutil
import re
import logging

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

# Database imports
import sys
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_db, init_db, get_db_session
from database.services import ProfileService, CardService, ChatService
from sqlalchemy.orm import Session
from fastapi import Depends

from agentic import AgenticPlanner, AgentMemory, PrincipleStore, AgentTools
from agentic.tools import (
    MasteryVectorError,
    KnowledgeGraphError,
    RecommenderError,
)
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

class ChatMessage(BaseModel):
    id: str
    content: str
    role: str  # "user" or "assistant"
    timestamp: datetime
    mentions: List[str] = []
    config: Optional[Dict[str, str]] = None  # Optional model configuration: {"card_model": "...", "image_model": "..."}


class RecommendationRequest(BaseModel):
    mastered_words: List[str]
    profile_id: str
    concreteness_weight: Optional[float] = 0.5  # Weight for concreteness (0.0-1.0), default 0.5
    # 0.0 = only HSK level matters, 1.0 = only concreteness matters, 0.5 = balanced
    mental_age: Optional[float] = None  # Mental age for AoA filtering (e.g., 7.0 for a 7-year-old)

class EnglishRecommendationRequest(BaseModel):
    mastered_words: List[str]
    profile_id: str
    # Slider: 0.0 = Max Frequency (Utility), 1.0 = Max Concreteness (Ease)
    concreteness_weight: Optional[float] = 0.5  # Slider position (0.0-1.0), default 0.5 = balanced
    # Note: CEFR is now a hard filter (not a weight), only showing current level and +1
    mental_age: Optional[float] = None  # Mental age for AoA filtering (e.g., 7.0 for a 7-year-old)

class PPRRecommendationRequest(BaseModel):
    """Request for PPR-based English word recommendations."""
    profile_id: str
    mastered_words: Optional[List[str]] = None  # If None, loaded from database
    exclude_words: Optional[List[str]] = None
    # PPR configuration
    alpha: Optional[float] = 0.5  # PPR teleport probability
    beta_ppr: Optional[float] = 1.0  # Weight for log-transformed PPR
    beta_concreteness: Optional[float] = 0.8  # Weight for z-scored concreteness
    beta_frequency: Optional[float] = 0.3  # Weight for log-transformed frequency
    beta_aoa_penalty: Optional[float] = 2.0  # Weight for AoA penalty
    beta_intercept: Optional[float] = 0.0  # Intercept term
    mental_age: Optional[float] = 8.0  # Mental age for AoA filtering
    aoa_buffer: Optional[float] = 2.0  # Buffer years beyond mental age
    exclude_multiword: Optional[bool] = True  # Filter out multi-word phrases
    top_n: Optional[int] = 50  # Number of recommendations

class ChinesePPRRecommendationRequest(BaseModel):
    """Request for PPR-based Chinese word recommendations."""
    profile_id: str
    mastered_words: Optional[List[str]] = None  # If None, loaded from database
    exclude_words: Optional[List[str]] = None
    # PPR configuration (same as English)
    alpha: Optional[float] = 0.5
    beta_ppr: Optional[float] = 1.0
    beta_concreteness: Optional[float] = 0.8
    beta_frequency: Optional[float] = 0.3
    beta_aoa_penalty: Optional[float] = 2.0
    beta_intercept: Optional[float] = 0.0
    mental_age: Optional[float] = 8.0
    aoa_buffer: Optional[float] = 2.0
    exclude_multiword: Optional[bool] = True
    top_n: Optional[int] = 50
    max_hsk_level: Optional[int] = 6

class GrammarRecommendationRequest(BaseModel):
    mastered_grammar: List[str]
    profile_id: str
    language: Optional[str] = "zh"  # "zh" for Chinese, "en" for English

class IntegratedRecommendationRequest(BaseModel):
    """Request for integrated recommendations (PPR + ZPD + Campaign Manager)."""
    profile_id: str
    language: Optional[str] = "zh"  # "zh" for Chinese, "en" for English
    mastered_words: Optional[List[str]] = None  # If None, loaded from database
    # PPR configuration overrides (optional)
    alpha: Optional[float] = None
    beta_ppr: Optional[float] = None
    beta_concreteness: Optional[float] = None
    beta_frequency: Optional[float] = None
    beta_aoa_penalty: Optional[float] = None
    beta_intercept: Optional[float] = None
    mental_age: Optional[float] = None
    aoa_buffer: Optional[float] = None
    exclude_multiword: Optional[bool] = None
    top_n: Optional[int] = None
    max_hsk_level: Optional[int] = None  # For Chinese only

class WordRecommendation(BaseModel):
    word: str
    pinyin: str
    hsk: int
    score: float  # Changed to float for more precise scoring
    known_chars: int
    total_chars: int
    concreteness: Optional[float] = None  # Concreteness rating (1-5 scale)
    age_of_acquisition: Optional[float] = None  # Age of Acquisition (AoA) in years

class GrammarRecommendation(BaseModel):
    grammar_point: str
    grammar_point_zh: Optional[str]
    structure: Optional[str]
    explanation: Optional[str]
    cefr_level: Optional[str]
    example_chinese: Optional[str]
    score: int


class AgenticPlanRequest(BaseModel):
    user_id: str
    topic: Optional[str] = None  # Optional - agent can determine what to learn
    learner_level: Optional[str] = None
    topic_complexity: Optional[str] = None  # Optional - agent can infer from mastery

# File paths for data storage (relative to project root)
# Get project root: backend/app/main.py -> project root is 2 levels up

# Ensure data directories exist

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


# Initialize Agentic components (lazy instantiation ensures compatibility with existing code)
_agentic_planner: Optional[AgenticPlanner] = None


def get_agentic_planner() -> AgenticPlanner:
    global _agentic_planner
    if _agentic_planner is None:
        memory = AgentMemory()
        principles = PrincipleStore()
        tools = AgentTools()
        _agentic_planner = AgenticPlanner(memory=memory, principles=principles, tools=tools)
    return _agentic_planner

def normalize_to_slug(value: str) -> str:
    """Normalize a string to a slug-friendly format without enforcing uniqueness."""
    if not value:
        return ""
    import re
    slug = value.lower()
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', slug)
    slug = slug.strip('-')
    slug = re.sub(r'-+', '-', slug)
    return slug

def normalize_for_kp_id(value: str) -> str:
    """Normalize text for inclusion in a knowledge point identifier."""
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    for sep in [' ', '/', '\\', ':', '@', ',', '，', ';', '；', '|']:
        value = value.replace(sep, '-')
    value = re.sub(r'-+', '-', value)
    slug = normalize_to_slug(value)
    return slug or "value"

def generate_kp_id(subject: str, predicate: str, obj: str) -> str:
    """Create a composite knowledge point identifier."""
    subject_part = normalize_for_kp_id(subject) or "subject"
    predicate_part = normalize_for_kp_id(predicate) or "predicate"
    object_part = normalize_for_kp_id(obj) or "value"
    return f"kp:{subject_part}--{predicate_part}--{object_part}"

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

CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')

TAG_ANNOTATION_PREFIXES = (
    "pronunciation",
    "meaning",
    "hsk",
    "knowledge",
    "note",
    "remark",
    "example",
)


def contains_chinese_chars(value: str) -> bool:
    """Check if the string contains at least one CJK unified ideograph."""
    if not value:
        return False
    return bool(CHINESE_CHAR_PATTERN.search(value))


def _sanitize_for_sparql_literal(value: str) -> str:
    """Escape characters for safe SPARQL literal usage."""
    if value is None:
        return ""
    return value.replace("\\", "\\\\").replace('"', '\\"')

def split_tag_annotations(tags: List[Any]) -> (List[str], List[str]):
    """Separate descriptive annotations from machine-friendly tags."""
    clean_tags: List[str] = []
    annotations: List[str] = []
    
    # Handle case where tags is a string (comma-separated or single tag)
    if isinstance(tags, str):
        # Split comma-separated string into list
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    elif not isinstance(tags, (list, tuple)):
        # If it's not a string or list, convert to list
        tags = [tags] if tags else []
    
    for tag in tags or []:
        if tag is None:
            continue
        tag_str = str(tag).strip()
        if not tag_str:
            continue
        lowered = tag_str.lower()
        if ":" in tag_str or any(lowered.startswith(prefix) for prefix in TAG_ANNOTATION_PREFIXES):
            annotations.append(tag_str)
        else:
            clean_tags.append(tag_str)
    return clean_tags, annotations


@lru_cache(maxsize=256)










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
                # "读者 means reader (concept)"
                display_text = f"{subj} means {obj} (concept)"
            elif pred_lower in ['has pronunciation', 'pronunciation', 'pronounced']:
                # "读者 pronounced dú zhě"
                display_text = f"{subj} pronounced {obj}"
            elif pred_lower in ['has hsk level', 'hsk level', 'hsk']:
                # "读者 HSK level 3"
                display_text = f"{subj} HSK level {obj}"
            elif pred_lower in ['has grammar rule', 'grammar rule', 'grammar']:
                # "把 grammar rule: causative construction"
                display_text = f"{subj} grammar rule: {obj}"
            elif pred_lower in ['has part of speech', 'part of speech', 'pos']:
                # "读者 part of speech: noun"
                display_text = f"{subj} part of speech: {obj}"
            else:
                # Generic format: "subject → object (predicate)"
                display_text = f"{subj} → {obj} ({pred.replace('-', ' ')})"
        else:
            # Fallback to raw format if parsing fails
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


def find_learning_frontier(mastered_words: List[str], target_level: int = 1, top_n: int = 50, concreteness_weight: float = 0.5, mental_age: Optional[float] = None) -> List[Dict[str, Any]]:
    """
    Find the learning frontier for a child based on their mastered words.
    Uses HSK levels, character composition, and concreteness weights.
    """
    from scripts.knowledge_graph.query_fuseki import query_sparql
    import csv
    import io

    mastered_set = set(mastered_words)
    words_data = defaultdict(lambda: {'pinyin': '', 'hsk': None, 'chars': set(), 'concreteness': None, 'aoa': None})

    # Step 1: Get all words with HSK and Metadata
    sparql_words = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?word_text ?pinyin ?hsk ?concreteness ?aoa WHERE {
        ?word a srs-kg:Word ; rdfs:label ?word_text .
        OPTIONAL { ?word srs-kg:pinyin ?pinyin }
        OPTIONAL { ?word srs-kg:hskLevel ?hsk }
        OPTIONAL { ?word srs-kg:concreteness ?concreteness }
        OPTIONAL { ?word srs-kg:ageOfAcquisition ?aoa }
        FILTER (lang(?word_text) = "zh")
    }
    """

    try:
        result = query_sparql(sparql_words, "text/csv")
        reader = csv.reader(io.StringIO(result))
        next(reader)
        for row in reader:
            if len(row) >= 1:
                word_text = row[0]
                words_data[word_text]['pinyin'] = row[1] if len(row) > 1 else ""
                try:
                    words_data[word_text]['hsk'] = int(float(row[2])) if row[2] else None
                    words_data[word_text]['concreteness'] = float(row[3]) if row[3] else None
                    words_data[word_text]['aoa'] = float(row[4]) if row[4] else None
                except: pass
    except Exception as e:
        print(f"Error fetching metadata: {e}")

    # AoA Filter
    if mental_age is not None:
        aoa_ceiling = mental_age + 2.0
        words_data = {w: d for w, d in words_data.items() if d['aoa'] is None or d['aoa'] <= aoa_ceiling}

    # Step 2: Scoring
    scored_words = []
    hsk_weight = 1.0 - concreteness_weight
    for word, data in words_data.items():
        if word in mastered_set: continue
        hsk_score = 0.0
        if data['hsk'] == target_level: hsk_score = 100.0
        elif data['hsk'] == target_level + 1: hsk_score = 50.0
        elif data['hsk'] and data['hsk'] > target_level + 1: continue

        conc_score = ((data['concreteness'] - 1.0) / 4.0 * 100.0) if data['concreteness'] else 50.0
        total_score = (hsk_score * hsk_weight) + (conc_score * concreteness_weight)

        scored_words.append({
            'word': word, 'pinyin': data['pinyin'], 'hsk': data['hsk'],
            'score': total_score, 'concreteness': data['concreteness'], 'age_of_acquisition': data['aoa'],
            'known_chars': 0, 'total_chars': 1 # Simplified for recovery
        })

    scored_words.sort(key=lambda x: x['score'], reverse=True)
    return scored_words[:top_n]

def parse_context_tags(content: str, mentions: List[str]) -> List[Dict[str, Any]]:
    """
    Parse @mentions from message content into structured context tags.
    
    Supports formats:
    - @profile:Alex -> {"type": "profile", "value": "Alex"}
    - @interest:trains -> {"type": "interest", "value": "trains"}
    - @word:红色 -> {"type": "word", "value": "红色"}
    - @skill:grammar-001 -> {"type": "skill", "value": "grammar-001"}
    - @character:Pinocchio -> {"type": "character", "value": "Pinocchio"}
    - @notetype:cuma-interactive-cloze -> {"type": "notetype", "value": "CUMA - Interactive Cloze"}
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
    
    # Special handling for knowledge point mentions
    # Supports two formats:
    # 1. @kp:subject--predicate--object (explicit format)
    # 2. @subject--predicate--object (simplified format, e.g., @读者--means--reader)
    # Match everything after @ until whitespace+@ (next mention) or end of line/string
    # Pattern: @[^@\s]+--[^@\s]+--[^@\n]+?(?=\s+@|[\s,]*$|[\s,]*\n)
    
    # First, try @kp: format
    kp_explicit_pattern = r'@kp:([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
    kp_explicit_matches = re.findall(kp_explicit_pattern, content)
    for kp_value in kp_explicit_matches:
        kp_value = kp_value.strip().rstrip(',')
        if kp_value:
            context_tags.append({
                "type": "kp",
                "value": kp_value
            })
            print(f"📌 Parsed knowledge point (explicit): {kp_value}")
    
    # Then, try simplified format: @subject--predicate--object
    # This matches patterns like @读者--means--reader
    # But avoid matching if it's already a known mention type (like @profile:, @word:, etc.)
    kp_simplified_pattern = r'@([^@\s:]+)--([^@\s]+)--([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
    kp_simplified_matches = re.findall(kp_simplified_pattern, content)
    for subj, pred, obj in kp_simplified_matches:
        # Skip if this looks like a regular mention (e.g., @profile:value)
        # Only accept if it's in the format subject--predicate--object
        # Common predicates: means, has-meaning, has-pronunciation, has-hsk-level, etc.
        if pred and '--' not in subj and '--' not in pred:
            kp_value = f"{subj}--{pred}--{obj.strip()}"
            # Check if this KP was already added (from @kp: format)
            already_exists = any(
                t.get("type") == "kp" and t.get("value") == kp_value
                for t in context_tags
            )
            if not already_exists:
                context_tags.append({
                    "type": "kp",
                    "value": kp_value
                })
                print(f"📌 Parsed knowledge point (simplified): @{kp_value}")
    
    # Find all other @type:value patterns (excluding @kp: which we already handled)
    # Pattern requires word boundary before @ to avoid matching @ inside values
    # Example: @template:English_Word_Cloze should NOT match @Word as a separate mention
    # Exclude @kp: from this pattern since we already handled it
    pattern = r'(?:^|[\s,])@(?!kp:)(\w+):([^\s,@]+)'
    matches = re.findall(pattern, content)
    
    for tag_type, tag_value in matches:
        # Skip if it's roster:roster (old format)
        if tag_type == 'roster' and tag_value == 'roster':
            continue
        if tag_type == 'profile':
            value_normalized = normalize_to_slug(tag_value)
        elif tag_type == 'notetype':
            value_normalized = resolve_note_type_name(tag_value)
        else:
            value_normalized = tag_value
        context_tags.append({
            "type": tag_type,
            "value": value_normalized
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


# Configuration endpoints
@app.get("/config/models")
async def get_available_models():
    """Get available AI models for card and image generation."""
    model_config = load_json_file(MODEL_CONFIG_FILE, {
        "card_models": [],
        "image_models": []
    })
    return model_config

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

# [Keep all imports at the top unchanged]
# ... (imports remain the same)

# [Find the /chat endpoint around line 1238 and replace it with this updated version]
@app.post("/chat", response_model=ChatMessage)
async def send_message(message: ChatMessage, request: Request):  # <--- Added 'request: Request'
    try:
        import sys
        import os

        # 1. Capture Credentials from Headers
        api_key = request.headers.get("X-LLM-Key")
        if not api_key:
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ")[1]
            else:
                api_key = message.config.get("apiKey") # Fallback to body if not in headers

        # 2. Capture Base URL (The Fix)
        base_url = request.headers.get("X-LLM-Base-URL")
        provider = request.headers.get("X-LLM-Provider", "deepseek").lower()

        # Default fallback if user left URL blank
        if not base_url and provider == "deepseek":
            base_url = "https://api.siliconflow.cn/v1"
        
        # 3. Set Environment Variables
        if api_key:
            print(f"DEBUG: Key found (length={len(api_key)})")
            print(f"DEBUG X-LLM-Key: {request.headers.get('X-LLM-Key')}")
            print(f"DEBUG Authorization: {request.headers.get('Authorization')}")

            # Force set these BEFORE imports
            os.environ["DEEPSEEK_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key # Fallback for some SDKs
            if base_url:
                os.environ["DEEPSEEK_API_BASE"] = base_url # <--- Vital override
                os.environ["OPENAI_BASE_URL"] = base_url   # <--- Good practice for OpenAI SDKs
            
            # --- FIX: PREVENT FALLBACK TO GEMINI ---
            # If using DeepSeek, hide the Gemini key so ContentGenerator doesn't default to Google.
            if provider == "deepseek" or (base_url and "siliconflow" in base_url):
                if "GEMINI_API_KEY" in os.environ:
                    del os.environ["GEMINI_API_KEY"]
                
                # CRITICAL: Reload modules to purge cached env vars
                import importlib
                import agent.content_generator
                import agent.conversation_handler
                importlib.reload(agent.content_generator)
                importlib.reload(agent.conversation_handler)
                print("🔄 Modules reloaded to force DeepSeek configuration")
        else:
            print("DEBUG: No API Key found in headers or message config")

        # 4. Imports (Delayed until after env var is set)
        sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
        
        from agent.intent_detector import IntentDetector, IntentType
        from agent.conversation_handler import ConversationHandler
        from agent.content_generator import ContentGenerator

        # Save user message to history
        history = load_json_file(CHAT_HISTORY_FILE, [])
        history.append(message.dict())
        save_json_file(CHAT_HISTORY_FILE, history)

        try:

            # Initialize handlers with model configuration from message
            card_model_raw = message.config.get("card_model") if message.config else None
            image_model_raw = message.config.get("image_model") if message.config else None

            base_url = os.getenv("DEEPSEEK_API_BASE", "") # Get base_url for normalization

            card_model = _normalize_model_name(card_model_raw, base_url) if card_model_raw else None
            image_model = _normalize_model_name(image_model_raw, base_url) if image_model_raw else None

            intent_detector = IntentDetector()

            # Pass the API key explicitly if the classes support it, otherwise they use the os.environ we set above
            conversation_handler = ConversationHandler(card_model=card_model, image_model=image_model)
            generator = ContentGenerator(card_model=card_model)

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

            # [Rest of the function remains identical...]
            # Get child profile from mentions if specified
            child_profile = None
            profiles = load_json_file(PROFILES_FILE, [])
            for mention in message.mentions:
                # ... (existing profile matching logic) ...
                for profile in profiles:
                    # Match by ID (including slugs), then by name
                    # Handle both old UUIDs and new slugs
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
                        print(f"📋 Found profile: {profile.get('name')} (ID: {profile.get('id')})")
                        break
                if child_profile:
                    break

            # Handle different intents
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
                response_content = "✏️ Card update feature is coming soon! For now, you can edit cards in the Card Curation tab."

            else:
                response_content = conversation_handler.handle_conversation(
                    message=message.content,
                    context_tags=context_tags,
                    child_profile=child_profile,
                    chat_history=history[-5:]
                )

        except ImportError as e:
            print(f"Agent import error: {e}")
            response_content = f"Error: Agent modules could not be loaded. {str(e)}"

    except Exception as e:
        print(f"Chat error: {e}")
        # Return the actual error to the UI so we can debug easier
        response_content = f"System Error: {str(e)}"

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
                        
                        # Parse knowledge point mentions from template text and add to context_tags
                        import re
                        # First, try @kp: format (may contain template variables)
                        template_kp_explicit_pattern = r'@kp:([^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
                        template_kp_explicit_matches = re.findall(template_kp_explicit_pattern, prompt_template)
                        for kp_pattern in template_kp_explicit_matches:
                            kp_pattern = kp_pattern.strip().rstrip(',')
                            if not kp_pattern:
                                continue
                            # Expand template variables (e.g., {{word}}, {{concept}})
                            kp_value = expand_kp_template_variables(kp_pattern, context_tags)
                            if kp_value == kp_pattern and "{{" in kp_pattern:
                                # Variables couldn't be expanded, skip this KP
                                print(f"⚠️ Could not expand knowledge point template variables: {kp_pattern}")
                                continue
                            # Check if this KP is already in context_tags (from user message)
                            kp_already_exists = any(
                                t.get("type") == "kp" and t.get("value") == kp_value
                                for t in context_tags
                            )
                            if not kp_already_exists:
                                context_tags.append({
                                    "type": "kp",
                                    "value": kp_value
                                })
                                print(f"📌 Added knowledge point from template (explicit, expanded): {kp_value}")
                        
                        # Then, try simplified format: @subject--predicate--object (may contain template variables)
                        # Use a more flexible pattern that captures the whole KP pattern including template variables
                        template_kp_simplified_pattern = r'@([^@\n]+?--[^@\n]+?--[^@\n]+?)(?=\s+@|[\s,]*$|[\s,]*\n)'
                        template_kp_simplified_matches = re.findall(template_kp_simplified_pattern, prompt_template)
                        for kp_pattern_raw in template_kp_simplified_matches:
                            kp_pattern_raw = kp_pattern_raw.strip().rstrip(',')
                            if not kp_pattern_raw:
                                continue
                            # Check if this looks like a knowledge point (has -- separators)
                            if kp_pattern_raw.count('--') != 2:
                                continue
                            # Expand template variables (e.g., {{word}}, {{concept}})
                            kp_value = expand_kp_template_variables(f"@{kp_pattern_raw}", context_tags)
                            # Remove leading @ if it was added
                            if kp_value.startswith("@"):
                                kp_value = kp_value[1:]
                            if kp_value == kp_pattern_raw and "{{" in kp_pattern_raw:
                                # Variables couldn't be expanded, skip this KP
                                print(f"⚠️ Could not expand knowledge point template variables: @{kp_pattern_raw}")
                                continue
                            # Check if this KP is already in context_tags
                            kp_already_exists = any(
                                t.get("type") == "kp" and t.get("value") == kp_value
                                for t in context_tags
                            )
                            if not kp_already_exists:
                                context_tags.append({
                                    "type": "kp",
                                    "value": kp_value
                                })
                                print(f"📌 Added knowledge point from template (simplified, expanded): {kp_value}")
                        break
                
                if not prompt_template:
                    print(f"❌ Template not found: {template_value}")
        
        # Use the flexible agent method
        # Run the blocking LLM call in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        cards = await loop.run_in_executor(
            None,
            partial(
                generator.generate_from_prompt,
                user_prompt=message.content,
                context_tags=context_tags,
                child_profile=child_profile,
                prompt_template=prompt_template
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
        
        # Create simple response message with expandable details
        card_count = len(cards)
        response_content = f"✨ 成功为您生成了 {card_count} 张卡片！\n\n"
        
        # Add details section (will be collapsed by frontend)
        basic_count = len([c for c in cards if c['card_type'] == 'basic'])
        reverse_count = len([c for c in cards if c['card_type'] == 'basic_reverse'])
        cloze_count = len([c for c in cards if c['card_type'] == 'cloze'])
        
        details = []
        if basic_count > 0:
            details.append(f"{basic_count} 张基础卡片")
        if reverse_count > 0:
            details.append(f"{reverse_count} 张反向卡片")
        if cloze_count > 0:
            details.append(f"{cloze_count} 张完形填空卡片")
        
        if details:
            response_content += f"📝 包含：{', '.join(details)}\n\n"
        
        if context_tags:
            # For display, show profile name instead of ID
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
        from agent.content_generator import ContentGenerator
        import base64
        
        # Get model configuration from message
        card_model = message.config.get("card_model") if message.config else None
        image_model = message.config.get("image_model") if message.config else None
        
        conversation_handler = ConversationHandler(card_model=card_model, image_model=image_model)
        content_generator = ContentGenerator(card_model=card_model)
        
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
                    target_card["image_data"] = image_filename
                except Exception as e:
                    print(f"Error processing image data in chat handler: {e}")
                    # Fallback to original data URL if processing fails
                    target_card["image_data"] = image_data_url
        
        if image_result["success"]:
            # Don't automatically add to card - show in chat first
            if image_result.get("is_placeholder", False):
                return f"🖼️ **Generated Image Description:**\n\n{image_description}\n\n⚠️ **Note:** This is a placeholder image. To generate actual images, integrate with an image generation service like DALL-E 3, Midjourney, or Stable Diffusion.\n\n💡 **Instructions:** {image_result.get('instructions', '')}\n\n**To add this image to a card, please specify:**\n- Which card (by ID or 'last card')\n- Front or back\n- Before or after the text"
            else:
                # Show the image in chat with options
                if image_filename:
                    image_path = f"/static/media/{image_filename}"
                    image_markdown = f"![Generated Image]({image_path})"
                else:
                    # Fallback to data URL if filename not available
                    image_markdown = f"![Generated Image]({image_result.get('image_data', '')})"
                
                return f"🖼️ **Generated Image:**\n\n{image_markdown}\n\n**Image Description:**\n{image_description}\n\n**To add this image to a card, please specify:**\n- Which card (by ID or 'last card')\n- Front or back\n- Before or after the text\n\n**Example commands:**\n- 'Add this image to the last card, front, before text'\n- 'Insert image to card #123, back, after text'"
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
        # For CUMA - Interactive Cloze cards, use text_field instead of front
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

@app.post("/kg/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """
    Get vocabulary recommendations based on mastered words and knowledge graph.
    
    Returns top 50 words to learn next based on the Learning Frontier algorithm.
    """
    try:
        # Validate input
        if not request.mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words provided"
            }
        
        print(f"\n📚 Getting recommendations for {len(request.mastered_words)} mastered words")
        
        # Get recommendations
        # Dynamically determine target level based on mastery rates
        # Find the "learning frontier" - first level where mastery < 80%
        target_level = 3  # Default fallback
        
        print(f"🎯 Determining optimal target level...")
        
        if request.mastered_words:
            # Get mastery rate per level
            mastery_by_level = defaultdict(lambda: {'total': 0, 'mastered': 0})
            
            try:
                sparql = """
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?word ?word_text ?hsk WHERE {
                    ?word a srs-kg:Word ;
                          rdfs:label ?word_text ;
                          srs-kg:hskLevel ?hsk .
                    FILTER (lang(?word_text) = "zh")
                }
                """
                
                print(f"   🔍 Querying knowledge graph...")
                csv_result = query_sparql(sparql, "text/csv")
                reader = csv.reader(io.StringIO(csv_result))
                next(reader)  # Skip header
                
                mastered_set = set(request.mastered_words)
                
                for row in reader:
                    if len(row) >= 3:
                        word_text = row[1]  # word_text is second column
                        try:
                            hsk = int(row[2]) if len(row) > 2 and row[2] else None
                        except ValueError:
                            hsk = None
                        
                        if hsk:
                            mastery_by_level[hsk]['total'] += 1
                            if word_text in mastered_set:
                                mastery_by_level[hsk]['mastered'] += 1
                
                print(f"   📊 Mastery rates by level:")
                for level in sorted(mastery_by_level.keys()):
                    if mastery_by_level[level]['total'] > 0:
                        rate = mastery_by_level[level]['mastered'] / mastery_by_level[level]['total']
                        print(f"      HSK {level}: {mastery_by_level[level]['mastered']}/{mastery_by_level[level]['total']} ({rate*100:.1f}%)")
                
                # Find learning frontier (first level < 80% mastery)
                for level in sorted(mastery_by_level.keys()):
                    if mastery_by_level[level]['total'] > 0:
                        rate = mastery_by_level[level]['mastered'] / mastery_by_level[level]['total']
                        if rate < 0.8:  # Less than 80% mastered
                            target_level = level
                            print(f"   🎯 Learning frontier: HSK {target_level} ({rate*100:.1f}% mastered)")
                            break
            except Exception as e:
                print(f"   ⚠️  Warning: Could not determine optimal target level: {e}")
                import traceback
                traceback.print_exc()
                target_level = 1  # Conservative default
        
        print(f"   📌 Using target_level = {target_level}")
        
        # Get concreteness weight from request (default 0.5 = balanced)
        concreteness_weight = request.concreteness_weight if hasattr(request, 'concreteness_weight') else 0.5
        concreteness_weight = max(0.0, min(1.0, concreteness_weight))  # Clamp to 0-1
        print(f"   ⚖️  Concreteness weight: {concreteness_weight:.2f} (HSK weight: {1.0 - concreteness_weight:.2f})")
        
        # Get mental_age from profile if available
        mental_age = None
        if request.profile_id:
            profiles = load_json_file(PROFILES_FILE, [])
            profile = next((p for p in profiles if p.get('id') == request.profile_id or p.get('name') == request.profile_id), None)
            if profile and profile.get('mental_age'):
                try:
                    mental_age = float(profile['mental_age'])
                    print(f"   🧠 Using mental_age={mental_age:.1f} from profile for AoA filtering")
                except (ValueError, TypeError):
                    pass
        
        recommendations = find_learning_frontier(
            mastered_words=request.mastered_words,
            target_level=target_level,
            top_n=50,  # Changed from 20 to 50
            concreteness_weight=concreteness_weight,
            mental_age=mental_age
        )
        
        print(f"   ✅ Found {len(recommendations)} recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")


@app.post("/kg/english-recommendations")
async def get_english_recommendations(request: EnglishRecommendationRequest):
    """
    Get English vocabulary recommendations based on mastered words and knowledge graph.
    
    Returns top 50 English words to learn next based on the Learning Frontier algorithm.
    Uses CEFR levels and concreteness scoring.
    """
    try:
        # Validate input
        if not request.mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words provided"
            }
        
        print(f"\n📚 Getting English recommendations for {len(request.mastered_words)} mastered words")
        
        # Import curious mario recommender
        import sys
        from pathlib import Path
        import requests
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.knowledge_graph.curious_mario_recommender import (
            CuriousMarioRecommender, RecommenderConfig, KnowledgeGraphService, KnowledgeNode
        )
        
        # Build mastery vector from profile's mastered words
        # We need to map word texts to KG node IDs
        mastered_set = set(w.lower().strip() for w in request.mastered_words)
        
        # Create config for English vocabulary
        # Slider: 0.0 = Max Frequency (Utility), 1.0 = Max Concreteness (Ease)
        slider_value = max(0.0, min(1.0, request.concreteness_weight or 0.5))
        print(f"   ⚖️  Slider position: {slider_value:.2f} (0.0=Frequency/Utility, 1.0=Concreteness/Ease)")
        print(f"   📋 CEFR acts as hard filter: only showing current level and +1")
        
        config = RecommenderConfig(
            fuseki_endpoint="http://localhost:3030/srs4autism/query",
            node_types=("srs-kg:Word",),
            concreteness_weight=slider_value,  # This is now the slider position, not a weight
            top_n=50,
            auto_detect_language=True,
            mental_age=request.mental_age  # Pass mental age for AoA filtering
        )
        print(f"   ⚖️  Config slider: {config.concreteness_weight:.2f}")
        print(f"   🧠 Semantic similarity weight: {config.semantic_similarity_weight:.2f}")
        english_similarity_map = get_english_semantic_similarity()
        
        # Fetch nodes to build mastery vector
        # Override fetch_nodes to filter for English words only (those with CEFR levels)
        kg_service = KnowledgeGraphService(config)
        
        # Custom query to get only English words (those with CEFR levels)
        node_types = " ".join(config.node_types)
        query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?node ?label ?hsk ?cefr ?concreteness ?frequency ?freqRank ?aoa ?prereq WHERE {{
            VALUES ?type {{ {node_types} }}
            ?node a ?type ;
                  rdfs:label ?label .
            # Filter for English words: must have CEFR level (English words) OR English language tag
            OPTIONAL {{ ?node srs-kg:cefrLevel ?cefr }}
            OPTIONAL {{ ?node srs-kg:hskLevel ?hsk }}
            OPTIONAL {{ ?node srs-kg:concreteness ?concreteness }}
            OPTIONAL {{ ?node srs-kg:frequency ?frequency }}
            OPTIONAL {{ ?node srs-kg:frequencyRank ?freqRank }}
            OPTIONAL {{ ?node srs-kg:ageOfAcquisition ?aoa }}
            OPTIONAL {{ ?node srs-kg:requiresPrerequisite ?prereq }}
            # Only include words with CEFR level (English words)
            FILTER(BOUND(?cefr))
        }}
        """
        
        response = requests.post(
            config.fuseki_endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        
        # Parse nodes from SPARQL results
        nodes = {}
        for row in data.get("results", {}).get("bindings", []):
            node_iri = row["node"]["value"]
            label = row["label"]["value"]
            # Extract node_id from IRI
            node_id = node_iri.split("/")[-1] if "/" in node_iri else node_iri
            
            from scripts.knowledge_graph.curious_mario_recommender import KnowledgeNode
            node = KnowledgeNode(
                node_id=node_id,
                iri=node_iri,
                label=label,
                hsk_level=None,
                cefr_level=None,
                concreteness=None,
                frequency=None,
                frequency_rank=None,
                age_of_acquisition=None,
                prerequisites=[],
            )
            
            if "hsk" in row and row["hsk"]["value"]:
                try:
                    node.hsk_level = int(float(row["hsk"]["value"]))
                except ValueError:
                    pass
            
            if "cefr" in row and row["cefr"]["value"]:
                node.cefr_level = str(row["cefr"]["value"]).upper()
            
            if "concreteness" in row and row["concreteness"]["value"]:
                try:
                    node.concreteness = float(row["concreteness"]["value"])
                except (ValueError, TypeError):
                    pass

            if "frequency" in row and row["frequency"]["value"]:
                try:
                    node.frequency = float(row["frequency"]["value"])
                except (ValueError, TypeError):
                    pass

            if "freqRank" in row and row["freqRank"]["value"]:
                try:
                    node.frequency_rank = int(float(row["freqRank"]["value"]))
                except (ValueError, TypeError):
                    pass
            
            if "aoa" in row and row["aoa"]["value"]:
                try:
                    node.age_of_acquisition = float(row["aoa"]["value"])
                except (ValueError, TypeError):
                    pass
            
            if "prereq" in row and row["prereq"]["value"]:
                prereq_id = row["prereq"]["value"].split("/")[-1] if "/" in row["prereq"]["value"] else row["prereq"]["value"]
                if prereq_id not in node.prerequisites:
                    node.prerequisites.append(prereq_id)
            
            nodes[node_id] = node
        
        print(f"   📊 Fetched {len(nodes)} English words from knowledge graph")
        
        if len(nodes) == 0:
            return {
                "recommendations": [],
                "message": "No English words found in knowledge graph. Please ensure the English vocabulary has been populated.",
                "learning_frontier": None
            }
        
        # Build mastery vector: mark words as mastered if they're in the profile
        mastery_vector = {}
        mastered_count = 0
        matched_words = []
        unmatched_words = []
        
        for node_id, node in nodes.items():
            # Check if word label matches any mastered word (case-insensitive)
            word_lower = node.label.lower().strip()
            if word_lower in mastered_set:
                mastery_vector[node_id] = 1.0  # Fully mastered
                mastered_count += 1
                matched_words.append(node.label)
            else:
                mastery_vector[node_id] = 0.0  # Not mastered
        
        # Show some examples of matched/unmatched words for debugging
        if mastered_count > 0:
            print(f"   ✅ Matched {mastered_count} mastered words (examples: {matched_words[:5]})")
        else:
            # Check if any words from mastered_set exist in nodes (for debugging)
            sample_mastered = list(mastered_set)[:5]
            sample_node_labels = [node.label.lower() for node in list(nodes.values())[:10]]
            print(f"   ⚠️  No matches found. Sample mastered words: {sample_mastered}")
            print(f"   ⚠️  Sample node labels: {sample_node_labels}")
            print(f"   ⚠️  Total mastered words provided: {len(mastered_set)}")
        
        print(f"   📊 Built mastery vector: {mastered_count} mastered out of {len(mastery_vector)} words")
        
        # Create recommender and find learning frontier
        recommender = CuriousMarioRecommender(config)
        # Reset debug counter for this request
        recommender._debug_logged_count = 0
        language = recommender._detect_language(nodes)
        print(f"   🌐 Detected language: {language}")
        learning_frontier = recommender._find_learning_frontier(nodes, mastery_vector, language)
        
        if learning_frontier:
            print(f"   🎯 Learning frontier: CEFR {learning_frontier}")
        
        # Generate recommendations
        mastered_node_ids = {
            node_id for node_id, mastery in mastery_vector.items()
            if mastery >= config.mastery_threshold
        }
        semantic_weight = config.semantic_similarity_weight
        recommendations = []
        for node_id, node in nodes.items():
            mastery = mastery_vector.get(node_id, 0.0)
            
            # Skip if already mastered
            if mastery >= config.mastery_threshold:
                continue
            
            # Skip if no CEFR level (not in CEFR-J vocabulary)
            if not node.cefr_level:
                continue
            
            # Calculate score
            prereq_mastery = 1.0  # No prerequisites for now
            score = recommender._score_candidate(node, mastery, prereq_mastery, language, learning_frontier)
            semantic_boost = 0.0
            if english_similarity_map:
                similar_entries = english_similarity_map.get(node_id, [])
                for neighbour in similar_entries:
                    neighbour_id = neighbour.get("neighbor_id")
                    if not neighbour_id:
                        continue
                    if mastery_vector.get(neighbour_id, 0.0) >= config.mastery_threshold:
                        sim_value = float(neighbour.get("similarity", 0.0))
                        semantic_boost = max(semantic_boost, sim_value)
                if semantic_boost > 0:
                    score += semantic_boost * semantic_weight
            
            # Calculate component scores for debugging (0-1.0 scale, matching scoring formula)
            conc_score_val = 0.5
            aoa_score_val = 0.5
            freq_score_val = 0.5
            ease_score_val = 0.5
            
            if node.concreteness:
                conc_score_val = (node.concreteness - 1.0) / 4.0  # 1.0→0.0, 5.0→1.0
            
            # AoA score (0-1.0 scale, lower AoA = higher score = easier)
            if node.age_of_acquisition is not None:
                aoa_score_val = max(0.0, 1.0 - (node.age_of_acquisition / 15.0))
            
            # Ease score = 0.7 * concreteness + 0.3 * AoA
            ease_score_val = (0.7 * conc_score_val) + (0.3 * aoa_score_val)
            
            # Frequency score using Zipf scale (logarithmic normalization)
            max_rank = 20000.0
            if node.frequency_rank:
                rank = float(min(max_rank, max(1, node.frequency_rank)))
                freq_score_val = max(0.0, 1.0 - (math.log(rank) / math.log(max_rank)))
            elif node.frequency:
                freq_score_val = min(
                    1.0,
                    (math.log10(node.frequency + 1.0) / math.log10(50000.0)),
                ) if node.frequency > 0 else 0.5
            
            recommendations.append({
                "word": node.label,
                "cefr_level": node.cefr_level,
                "concreteness": node.concreteness,
                "age_of_acquisition": node.age_of_acquisition,
                "frequency": node.frequency,
                "frequency_rank": node.frequency_rank,
                "score": score,
                "mastery": mastery,
                "concreteness_score": conc_score_val,  # 0-1.0 scale for debugging
                "aoa_score": aoa_score_val,  # 0-1.0 scale for debugging
                "ease_score": ease_score_val,  # 0-1.0 scale for debugging (0.7*conc + 0.3*aoa)
                "frequency_score": freq_score_val,  # 0-1.0 scale for debugging
                "semantic_similarity_boost": round(semantic_boost, 4),
            })
        
        # Sort by score
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        recommendations = recommendations[:config.top_n]
        
        print(f"   ✅ Found {len(recommendations)} recommendations")
        # Log top 5 for debugging
        print(f"   📊 Top 5 recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(
                f"      {i}. {rec['word']}: score={rec['score']:.2f}, "
                f"CEFR={rec['cefr_level']}, conc={rec.get('concreteness', 'N/A')}, "
                f"freq_rank={rec.get('frequency_rank')}"
            )
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations",
            "learning_frontier": learning_frontier,
            "weights_used": {
                "slider_position": config.concreteness_weight,  # 0.0=Frequency, 1.0=Concreteness
                "cefr_filter": "active"  # CEFR acts as hard filter (current level and +1 only)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting English recommendations: {str(e)}")


@app.post("/kg/ppr-recommendations")
async def get_ppr_recommendations(request: PPRRecommendationRequest):
    """
    Get English vocabulary recommendations using Personalized PageRank (PPR) algorithm.
    
    Uses semantic similarity graph, mastered words, and probability-based scoring.
    Returns top N words to learn next based on PPR scores combined with concreteness,
    frequency, and age of acquisition.
    """
    try:
        print(f"\n📚 Getting PPR recommendations for profile '{request.profile_id}'")
        
        # Import PPR service
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from services.ppr_recommender_service import get_ppr_service
        
        # Load mastered words from database if not provided
        mastered_words = request.mastered_words
        if not mastered_words:
            db = next(get_db())
            try:
                mastered_words = ProfileService.get_mastered_words(db, request.profile_id, 'en')
                print(f"   📘 Loaded {len(mastered_words)} mastered words from database")
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
        
        # Get PPR service (lazy-loaded singleton)
        similarity_file = PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"
        kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_english.ttl"
        
        service = get_ppr_service(
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
        
        print(f"   ✅ Found {len(recommendations)} recommendations")
        
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
        raise HTTPException(status_code=500, detail=f"Error getting PPR recommendations: {str(e)}")


@app.post("/kg/chinese-ppr-recommendations")
async def get_chinese_ppr_recommendations(request: ChinesePPRRecommendationRequest):
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
        # Use merged KG which now includes SUBTLEX-CH frequency data
        kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
        
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
    request: IntegratedRecommendationRequest,
    db: Session = Depends(get_db)
):
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


@app.post("/agentic/plan")
async def agentic_plan(request: AgenticPlanRequest):
    """
    Entry point for the new Agentic Learning Agent.

    This is a "learning agent" that:
    1. Synthesizes cognitive state (mastery, KG, profile)
    2. Determines WHAT to learn (via recommender)
    3. Returns a learning plan (not just cards)

    The agent solves "what to learn" by integrating with the recommender system.
    Topic is optional - if not provided, the agent will determine the best learning
    content based on the child's cognitive state.

    Raises:
        HTTPException 503: If critical services (mastery vector, KG, recommender) fail
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
        # Critical service failure - return HTTP 503
        logger.error(f"Agentic planner failed for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Learning service temporarily unavailable. Please try again later."
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Unexpected error - return HTTP 500
        logger.error(f"Unexpected error in agentic planner for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )

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
            image_path = word_image_map.get(word.strip())
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
        result = query_sparql(query, output_format="application/sparql-results+json", timeout=30)
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
        
        # Query Fuseki
        results = query_sparql(sparql, output_format="application/sparql-results+json")
        
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
                        example_results = query_sparql(example_sparql, output_format="application/sparql-results+json")
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
                            example_results_reverse = query_sparql(example_sparql_reverse, output_format="application/sparql-results+json")
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

@app.post("/kg/grammar-recommendations")
async def get_grammar_recommendations(request: GrammarRecommendationRequest):
    """
    Get grammar point recommendations based on mastered grammar and knowledge graph.
    
    Returns top 50 grammar points to learn next based on the Learning Frontier algorithm.
    Uses CEFR levels instead of HSK levels.
    """
    try:
        # Validate input - allow empty list for first-time users
        mastered_count = len(request.mastered_grammar) if request.mastered_grammar else 0
        
        language = request.language or "zh"
        print(f"\n📖 Getting {language.upper()} grammar recommendations for {mastered_count} mastered grammar points")
        
        # Get all grammar points from knowledge graph
        # mastered_grammar should contain URIs, not names (to avoid comma issues)
        mastered_set = set(request.mastered_grammar) if request.mastered_grammar else set()
        
        # Get mastery rate per CEFR level
        mastery_by_level = defaultdict(lambda: {'total': 0, 'mastered': 0})
        
        try:
            # Filter by language: 
            # English grammar (CEFR-J): URI starts with "grammar-en-" (from populate_english_grammar.py)
            # Chinese grammar: URI does NOT start with "grammar-en-"
            if language == "en":
                # English grammar: URI must contain "grammar-en-"
                label_filter = 'FILTER(CONTAINS(STR(?gp_uri), "grammar-en-"))'
            else:
                # Chinese grammar: URI must NOT contain "grammar-en-" and must have Chinese label
                label_filter = 'FILTER(!CONTAINS(STR(?gp_uri), "grammar-en-") && BOUND(?label_zh))'
            
            sparql = f"""
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?gp_uri ?label_en ?label_zh ?cefr WHERE {{
                ?gp_uri a srs-kg:GrammarPoint .
                OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }}
                OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
                OPTIONAL {{ ?gp_uri srs-kg:cefrLevel ?cefr }}
                {label_filter}
            }}
            """
            
            print(f"   🔍 Querying knowledge graph for grammar points...")
            results = query_sparql(sparql, output_format="application/sparql-results+json")
            
            if results and 'results' in results:
                for binding in results.get('results', {}).get('bindings', []):
                    gp_uri = binding.get('gp_uri', {}).get('value', '')
                    cefr = binding.get('cefr', {}).get('value', '') or 'not specified'
                    
                    if gp_uri:
                        mastery_by_level[cefr]['total'] += 1
                        if gp_uri in mastered_set:
                            mastery_by_level[cefr]['mastered'] += 1
        except Exception as e:
            print(f"   ⚠️  Warning: Could not query grammar points: {e}")
        
        # Find learning frontier (first CEFR level < 80% mastery)
        target_cefr = 'A1'  # Default
        cefr_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'not specified']
        
        print(f"   📊 Mastery rates by CEFR level:")
        for level in cefr_order:
            if mastery_by_level[level]['total'] > 0:
                rate = mastery_by_level[level]['mastered'] / mastery_by_level[level]['total']
                print(f"      CEFR {level}: {mastery_by_level[level]['mastered']}/{mastery_by_level[level]['total']} ({rate*100:.1f}%)")
                
                if rate < 0.8:  # Less than 80% mastered
                    target_cefr = level
                    print(f"   🎯 Learning frontier: CEFR {target_cefr} ({rate*100:.1f}% mastered)")
                    break
        
        # Get all grammar points and score them
        print(f"   📌 Using target CEFR level = {target_cefr}")
        
        # Query all grammar points with their details (filtered by language)
        # English grammar: URI starts with "grammar-en-" (from CEFR-J)
        # Chinese grammar: URI does NOT start with "grammar-en-"
        if language == "en":
            label_filter_all = 'FILTER(CONTAINS(STR(?gp_uri), "grammar-en-"))'
        else:
            label_filter_all = 'FILTER(!CONTAINS(STR(?gp_uri), "grammar-en-") && BOUND(?label_zh))'
        
        sparql_all = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?gp_uri ?label_en ?label_zh ?structure ?explanation ?cefr WHERE {{
            ?gp_uri a srs-kg:GrammarPoint .
            OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }}
            OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
            OPTIONAL {{ ?gp_uri srs-kg:structure ?structure }}
            OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation }}
            OPTIONAL {{ ?gp_uri srs-kg:cefrLevel ?cefr }}
            {label_filter_all}
        }}
        """
        
        results = query_sparql(sparql_all, output_format="application/sparql-results+json")
        
        if not results or 'results' not in results:
            return {
                "recommendations": [],
                "message": "Could not query grammar points from knowledge graph"
            }
        
        scored_grammar = []
        seen_uris = set()
        
        for binding in results.get('results', {}).get('bindings', []):
            try:
                gp_uri = binding.get('gp_uri', {}).get('value', '')
                if gp_uri in seen_uris:
                    continue
                seen_uris.add(gp_uri)
                
                label_en = binding.get('label_en', {}).get('value', '')
                label_zh = binding.get('label_zh', {}).get('value', '')
                structure = binding.get('structure', {}).get('value', '')
                explanation = binding.get('explanation', {}).get('value', '')
                cefr = binding.get('cefr', {}).get('value', '') or 'not specified'
                
                # Use language-appropriate label
                if language == "en":
                    grammar_point = label_en or label_zh  # Prefer English, fallback to Chinese
                else:
                    grammar_point = label_zh or label_en  # Prefer Chinese, fallback to English
                
                if not grammar_point or gp_uri in mastered_set:
                    continue  # Skip if no label or already mastered (check by URI)
                
                # Score grammar points
                score = 0
                
                # Prioritize grammar points in target CEFR level
                if cefr == target_cefr:
                    score += 100
                
                # Bonus for having structure and explanation
                if structure:
                    score += 10
                if explanation:
                    score += 10
                
                # Get example sentence
                # Try both hasExample (forward) and demonstratesGrammar (reverse) relationships
                example_chinese = ''
                try:
                    # First try hasExample (grammar point -> sentence)
                    example_sparql = f"""
                    PREFIX srs-kg: <http://srs4autism.com/schema/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?example_chinese WHERE {{
                        <{gp_uri}> srs-kg:hasExample ?example .
                        ?example rdfs:label ?example_chinese . FILTER(LANG(?example_chinese) = "zh")
                    }}
                    LIMIT 1
                    """
                    example_results = query_sparql(example_sparql, output_format="application/sparql-results+json")
                    if example_results and 'results' in example_results:
                        bindings = example_results.get('results', {}).get('bindings', [])
                        if bindings:
                            example_chinese = bindings[0].get('example_chinese', {}).get('value', '')
                    
                    # If no result, try reverse relationship (sentence -> grammar point)
                    if not example_chinese:
                        example_sparql_reverse = f"""
                        PREFIX srs-kg: <http://srs4autism.com/schema/>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        SELECT ?example_chinese WHERE {{
                            ?example srs-kg:demonstratesGrammar <{gp_uri}> .
                            ?example rdfs:label ?example_chinese . FILTER(LANG(?example_chinese) = "zh")
                        }}
                        LIMIT 1
                        """
                        example_results_reverse = query_sparql(example_sparql_reverse, output_format="application/sparql-results+json")
                        if example_results_reverse and 'results' in example_results_reverse:
                            bindings = example_results_reverse.get('results', {}).get('bindings', [])
                            if bindings:
                                example_chinese = bindings[0].get('example_chinese', {}).get('value', '')
                except:
                    pass
                
                scored_grammar.append({
                    'gp_uri': gp_uri,  # Include URI as unique identifier
                    'grammar_point': grammar_point,
                    'grammar_point_zh': label_zh,
                    'structure': structure,
                    'explanation': explanation,
                    'cefr_level': cefr,
                    'example_chinese': example_chinese,
                    'score': score
                })
            except Exception as e:
                continue
        
        # Sort by score (descending) and take top 50
        scored_grammar.sort(key=lambda x: x['score'], reverse=True)
        recommendations = scored_grammar[:50]
        
        print(f"   ✅ Found {len(recommendations)} grammar recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations",
            "target_cefr": target_cefr
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting grammar recommendations: {str(e)}")

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
