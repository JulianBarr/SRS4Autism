from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from functools import lru_cache
from pathlib import Path
import math

# Database imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_db, init_db, get_db_session
from database.services import ProfileService, CardService, ChatService
from sqlalchemy.orm import Session
from fastapi import Depends

from agentic import AgenticPlanner, AgentMemory, PrincipleStore, AgentTools
import google.generativeai as genai
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "../gemini.env"))
except Exception:
    pass

app = FastAPI(title="Curious Mario API", version="1.0.0")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Curious Mario API...")
    print("📊 Initializing database...")
    init_db()
    print("✅ Database ready!")

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
    mental_age: Optional[float] = None  # Mental/developmental age in years (for AoA filtering)
    raw_input: Optional[str] = None
    mastered_words: Optional[str] = None  # Comma-separated list of mastered words
    mastered_english_words: Optional[str] = None  # Comma-separated list of mastered English words
    mastered_grammar: Optional[str] = None  # Comma-separated list of mastered grammar points
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

class CardImageRequest(BaseModel):
    position: Optional[str] = "front"
    location: Optional[str] = "after"
    user_request: Optional[str] = None

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

class GrammarRecommendationRequest(BaseModel):
    mastered_grammar: List[str]
    profile_id: str
    language: Optional[str] = "zh"  # "zh" for Chinese, "en" for English

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
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PROFILES_FILE = str(PROJECT_ROOT / "data" / "profiles" / "child_profiles.json")
CARDS_FILE = str(PROJECT_ROOT / "data" / "content_db" / "approved_cards.json")
ANKI_PROFILES_FILE = str(PROJECT_ROOT / "data" / "profiles" / "anki_profiles.json")
CHAT_HISTORY_FILE = str(PROJECT_ROOT / "data" / "content_db" / "chat_history.json")
PROMPT_TEMPLATES_FILE = str(PROJECT_ROOT / "data" / "profiles" / "prompt_templates.json")
WORD_KP_CACHE_FILE = str(PROJECT_ROOT / "data" / "content_db" / "word_kp_cache.json")
ENGLISH_SIMILARITY_FILE = PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"

# Ensure data directories exist
os.makedirs(PROJECT_ROOT / "data" / "profiles", exist_ok=True)
os.makedirs(PROJECT_ROOT / "data" / "content_db", exist_ok=True)

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

# Cached semantic similarity map for English words
_english_similarity_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None


def get_english_semantic_similarity() -> Dict[str, List[Dict[str, Any]]]:
    """Load precomputed semantic similarity map for English words."""
    global _english_similarity_cache
    if _english_similarity_cache is not None:
        return _english_similarity_cache

    if not ENGLISH_SIMILARITY_FILE.exists():
        print(f"⚠️  English similarity file not found at {ENGLISH_SIMILARITY_FILE}")
        _english_similarity_cache = {}
        return _english_similarity_cache

    try:
        with ENGLISH_SIMILARITY_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            _english_similarity_cache = payload.get("similarities", {})
            meta = payload.get("metadata", {})
            print(f"🧠 Loaded English semantic similarity graph "
                  f"(words={len(_english_similarity_cache)}, "
                  f"model={meta.get('model')}, "
                  f"threshold={meta.get('threshold')})")
    except Exception as exc:
        print(f"⚠️  Failed to load English similarity file: {exc}")
        _english_similarity_cache = {}

    return _english_similarity_cache

# Gemini configuration for fallback knowledge lookups
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
_genai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _genai_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    except Exception as exc:
        print(f"⚠️ Unable to configure Gemini model: {exc}")
else:
    print("⚠️ GEMINI_API_KEY not set; falling back to cache-only knowledge lookup.")

# Cache for word knowledge derived from LLM or manual sources
_word_kp_cache: Dict[str, Dict[str, Any]] = {}
try:
    _word_kp_cache = load_json_file(WORD_KP_CACHE_FILE, {})
    if not isinstance(_word_kp_cache, dict):
        _word_kp_cache = {}
except Exception as exc:
    print(f"⚠️ Could not load word knowledge cache: {exc}")
    _word_kp_cache = {}

def _save_word_kp_cache():
    try:
        save_json_file(WORD_KP_CACHE_FILE, _word_kp_cache)
    except Exception as exc:
        print(f"⚠️ Failed to save word knowledge cache: {exc}")


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

def extract_plain_text(value: str) -> str:
    """Strip HTML tags and normalize whitespace for prompt generation."""
    if not value:
        return ""
    import re
    text = unescape(value)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

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
def fetch_word_knowledge_points(word: str) -> Dict[str, Any]:
    """Fetch pronunciation/meaning knowledge points for a given Chinese word."""
    if not word:
        return {}
    sanitized_word = word.strip()
    if not sanitized_word:
        return {}
    sparql_word = _sanitize_for_sparql_literal(sanitized_word)
    sparql = f"""
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?pinyin ?definition ?conceptLabel ?hsk WHERE {{
        ?word a srs-kg:Word ;
              srs-kg:text "{sparql_word}" .
        OPTIONAL {{ ?word srs-kg:pinyin ?pinyin . }}
        OPTIONAL {{ ?word srs-kg:definition ?definition .
                    FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }}
        OPTIONAL {{
            ?word srs-kg:means ?concept .
            ?concept rdfs:label ?conceptLabel .
        }}
        OPTIONAL {{ ?word srs-kg:hskLevel ?hsk . }}
    }}
    """
    try:
        results = query_sparql(sparql, output_format="application/sparql-results+json")
    except HTTPException:
        return {}
    except Exception:
        return {}
    
    bindings = []
    if isinstance(results, dict):
        bindings = results.get("results", {}).get("bindings", [])
    
    pronunciations: List[str] = []
    meanings: List[str] = []
    hsk_level = None
    
    for row in bindings or []:
        pinyin_value = row.get("pinyin", {}).get("value")
        if pinyin_value and pinyin_value not in pronunciations:
            pronunciations.append(pinyin_value)
        definition_value = row.get("definition", {}).get("value")
        if definition_value and definition_value not in meanings:
            meanings.append(definition_value)
        concept_value = row.get("conceptLabel", {}).get("value")
        if concept_value and concept_value not in meanings:
            meanings.append(concept_value)
        hsk_value = row.get("hsk", {}).get("value")
        if hsk_value and not hsk_level:
            hsk_level = hsk_value
    
    if not pronunciations and not meanings and not hsk_level:
        return {}
    
    return {
        "pronunciations": pronunciations,
        "meanings": meanings,
        "hsk_level": hsk_level
    }


def _clean_llm_json(text: str) -> Dict[str, Any]:
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return {}


def _fetch_word_info_via_llm(word: str) -> Dict[str, Any]:
    if not _genai_model:
        return {}
    prompt = (
        "You are a bilingual lexicon assistant.\n"
        f"Provide the Hanyu Pinyin (with tone marks) and a concise English meaning for the Chinese word \"{word}\".\n"
        "Respond ONLY with JSON like: {\"pinyin\": \"dú zhě\", \"meaning\": \"reader\"}."
    )
    try:
        response = _genai_model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        data = _clean_llm_json(text)
        result: Dict[str, Any] = {}
        pinyin = data.get("pinyin")
        meaning = data.get("meaning") or data.get("meaning_en") or data.get("english")
        if pinyin:
            result["pinyin"] = pinyin.strip()
        if meaning:
            result["meaning"] = meaning.strip()
        return result
    except Exception as exc:
        print(f"⚠️ Gemini lookup failed for '{word}': {exc}")
        return {}


def get_word_knowledge(word: str) -> Dict[str, Any]:
    """Combine knowledge graph data, cache, and LLM fallback for a Chinese word."""
    info = fetch_word_knowledge_points(word) or {}
    pronunciations: List[str] = list(dict.fromkeys(info.get("pronunciations") or []))
    meanings: List[str] = list(dict.fromkeys(info.get("meanings") or []))
    hsk_level = info.get("hsk_level")

    cached = _word_kp_cache.get(word) or {}
    cache_pinyin = cached.get("pinyin")
    cache_meaning = cached.get("meaning") or cached.get("meaning_en")
    cache_pron_list = cached.get("pronunciations") or []
    cache_meaning_list = cached.get("meanings") or []
    cache_hsk = cached.get("hsk_level")

    for val in [cache_pinyin]:
        if val and val not in pronunciations:
            pronunciations.append(val)
    for val in cache_pron_list:
        if val and val not in pronunciations:
            pronunciations.append(val)
    for val in [cache_meaning]:
        if val and val not in meanings:
            meanings.append(val)
    for val in cache_meaning_list:
        if val and val not in meanings:
            meanings.append(val)
    if not hsk_level and cache_hsk:
        hsk_level = cache_hsk

    needs_llm = (not pronunciations or not meanings) and _genai_model is not None
    if needs_llm:
        llm_info = _fetch_word_info_via_llm(word)
        updated = False
        llm_pinyin = llm_info.get("pinyin")
        llm_meaning = llm_info.get("meaning")
        if llm_pinyin and llm_pinyin not in pronunciations:
            pronunciations.append(llm_pinyin)
            updated = True
        if llm_meaning and llm_meaning not in meanings:
            meanings.append(llm_meaning)
            updated = True
        if updated:
            cache_entry = _word_kp_cache.get(word, {})
            cache_entry.setdefault("pronunciations", [])
            cache_entry.setdefault("meanings", [])
            if llm_pinyin and llm_pinyin not in cache_entry["pronunciations"]:
                cache_entry["pronunciations"].append(llm_pinyin)
            if llm_meaning and llm_meaning not in cache_entry["meanings"]:
                cache_entry["meanings"].append(llm_meaning)
            _word_kp_cache[word] = cache_entry
            _save_word_kp_cache()

    return {
        "pronunciations": pronunciations,
        "meanings": meanings,
        "hsk_level": hsk_level
    }


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
# Knowledge Graph Configuration
FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"

def query_sparql(sparql_query: str, output_format: str = "text/csv"):
    """Execute a SPARQL query against Jena Fuseki."""
    try:
        params = urlencode({"query": sparql_query})
        url = f"{FUSEKI_ENDPOINT}?{params}"
        response = requests.get(url, headers={"Accept": output_format}, timeout=10)
        response.raise_for_status()
        if output_format == "application/sparql-results+json":
            return response.json()
        return response.text
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Knowledge graph server unavailable: {str(e)}")

def find_learning_frontier(mastered_words: List[str], target_level: int = 1, top_n: int = 20, concreteness_weight: float = 0.5, mental_age: Optional[float] = None):
    """
    Find words to learn next using the "Learning Frontier" algorithm with concreteness scoring and AoA filtering.
    
    Algorithm:
    1. Get all words with HSK levels, pinyin, concreteness ratings, and AoA
    2. Find words in the next level (Learning Frontier)
    3. Filter words by AoA if mental_age is provided
    4. Score words based on:
       - HSK level (learning frontier): weighted by (1 - concreteness_weight)
       - Concreteness (higher = more concrete = easier): weighted by concreteness_weight
       - AoA (lower = easier): bonus/penalty
       - Known characters (prerequisites): bonus points
       - Being too hard: penalty
    
    Args:
        mastered_words: List of mastered words
        target_level: Target HSK level to focus on
        top_n: Number of recommendations to return
        concreteness_weight: Weight for concreteness (0.0-1.0)
            - 0.0 = only HSK level matters
            - 1.0 = only concreteness matters
            - 0.5 = balanced (default)
        mental_age: Mental age for AoA filtering (e.g., 7.0 for a 7-year-old)
    """
    # Step 1: Get all words with HSK levels, pinyin, concreteness, and AoA
    sparql = f"""
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word ?word_text ?pinyin ?hsk ?concreteness ?aoa WHERE {{
        ?word a srs-kg:Word ;
              srs-kg:text ?word_text ;
              srs-kg:pinyin ?pinyin ;
              srs-kg:hskLevel ?hsk .
        OPTIONAL {{ ?word srs-kg:concreteness ?concreteness }}
        OPTIONAL {{ ?word srs-kg:ageOfAcquisition ?aoa }}
    }}
    """
    
    csv_result = query_sparql(sparql, "text/csv")
    
    # Parse results using proper CSV parser
    words_data = defaultdict(lambda: {'pinyin': '', 'hsk': None, 'concreteness': None, 'aoa': None, 'chars': set()})
    reader = csv.reader(io.StringIO(csv_result))
    header = next(reader)  # Skip header
    print(f"   📊 CSV Header: {header}")
    
    mastered_set = set(mastered_words)
    
    words_with_concreteness = 0
    words_with_aoa = 0
    total_words = 0
    
    for row in reader:
        if len(row) >= 4:
            total_words += 1
            word_text = row[1]  # word_text is the second column
            pinyin = row[2] if len(row) > 2 else ''
            try:
                hsk = int(row[3]) if len(row) > 3 and row[3] else None
            except ValueError:
                hsk = None
            
            # Parse concreteness (optional, may be empty)
            # CSV format: word, word_text, pinyin, hsk, concreteness, aoa
            concreteness = None
            if len(row) > 4 and row[4] and row[4].strip():
                try:
                    concreteness = float(row[4].strip())
                    words_with_concreteness += 1
                except (ValueError, TypeError) as e:
                    concreteness = None
            
            # Parse AoA (optional, may be empty)
            aoa = None
            if len(row) > 5 and row[5] and row[5].strip():
                try:
                    aoa = float(row[5].strip())
                    words_with_aoa += 1
                except (ValueError, TypeError) as e:
                    aoa = None
            
            words_data[word_text]['pinyin'] = pinyin
            words_data[word_text]['hsk'] = hsk
            words_data[word_text]['concreteness'] = concreteness
            words_data[word_text]['aoa'] = aoa
    
    if total_words > 0:
        print(f"   📈 Loaded {total_words} words, {words_with_concreteness} with concreteness ({words_with_concreteness/total_words*100:.1f}%), {words_with_aoa} with AoA ({words_with_aoa/total_words*100:.1f}%)")
    else:
        print(f"   ⚠️  Warning: No words loaded from SPARQL query!")
    
    # AoA filtering: exclude words with AoA > mental_age + buffer (if mental_age is set)
    aoa_buffer = 2.0
    if mental_age is not None:
        aoa_ceiling = mental_age + aoa_buffer
        filtered_count = 0
        words_to_remove = []
        for word_text, data in words_data.items():
            if data['aoa'] is not None and data['aoa'] > aoa_ceiling:
                words_to_remove.append(word_text)
                filtered_count += 1
        for word_text in words_to_remove:
            del words_data[word_text]
        if filtered_count > 0:
            print(f"   🎯 Filtered out {filtered_count} words with AoA > {aoa_ceiling:.1f} (mental_age={mental_age:.1f} + buffer={aoa_buffer})")
    
    # Step 2: Get all character composition data in one query
    sparql_all_chars = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word_label ?char_label WHERE {
        ?word a srs-kg:Word ;
              srs-kg:composedOf ?char ;
              rdfs:label ?word_label .
        ?char rdfs:label ?char_label .
    }
    """
    
    try:
        char_result = query_sparql(sparql_all_chars, "text/csv")
        char_reader = csv.reader(io.StringIO(char_result))
        next(char_reader)  # Skip header
        
        for row in char_reader:
            if len(row) >= 2:
                word_text = row[0]
                char_text = row[1]
                if word_text in words_data:
                    words_data[word_text]['chars'].add(char_text)
    except Exception as e:
        print(f"Warning: Could not load character data: {e}")
    
    # Step 3: Score words with concreteness and HSK level balance
    scored_words = []
    
    # Normalize concreteness_weight to 0-1 range
    concreteness_weight = max(0.0, min(1.0, concreteness_weight))
    hsk_weight = 1.0 - concreteness_weight
    
    print(f"   ⚖️  Scoring with concreteness_weight={concreteness_weight:.2f}, hsk_weight={hsk_weight:.2f}")
    
    for word, data in words_data.items():
        if word in mastered_set:
            continue  # Skip already mastered words
        
        hsk_score_raw = 0.0
        concreteness_score_raw = 0.0
        
        # HSK level scoring (raw values, will be normalized)
        if data['hsk'] is not None:
            if data['hsk'] == target_level:
                hsk_score_raw = 100.0  # Target level gets highest priority
            elif data['hsk'] == target_level + 1:
                hsk_score_raw = 50.0   # Next level gets medium priority
            elif data['hsk'] < target_level:
                hsk_score_raw = 25.0  # Lower levels get small bonus (review)
            elif data['hsk'] > target_level + 1:
                hsk_score_raw = -500.0  # Too hard gets penalized
        else:
            # No HSK level, give small baseline
            hsk_score_raw = 10.0
        
        # Concreteness scoring (raw values, will be normalized)
        # Higher concreteness = easier to learn = higher score
        # Concreteness is on 1-5 scale
        if data['concreteness'] is not None:
            # Raw concreteness value (1.0 to 5.0)
            concreteness_score_raw = data['concreteness']
        else:
            # No concreteness data, use neutral value (middle of range: 3.0)
            # BUT: if concreteness_weight is high, words without concreteness should be penalized
            # So we use a lower neutral value when weight is high
            concreteness_score_raw = 3.0 * (1.0 - concreteness_weight * 0.5)  # Scale down neutral when weight is high
        
        # Normalize both scores to 0-100 scale for fair comparison
        # BUT: We want to preserve the relative importance of HSK level differences
        # The issue: if we normalize -500 to 100, we lose the distinction between target level and too hard
        
        # HSK score normalization: 
        # - Target level (100) should stay at 100 (highest priority)
        # - Next level (50) should stay at 50 (medium priority)  
        # - Lower levels (25) should stay at 25 (review)
        # - Too hard (-500) should be 0 (excluded)
        # - No level (10) should stay at 10 (baseline)
        # So we keep positive scores as-is, and map negative to 0
        if hsk_score_raw <= 0:
            hsk_score = 0.0  # Too hard or negative scores get 0
        else:
            # Keep positive scores as-is (they're already in 0-100 range)
            hsk_score = hsk_score_raw
        
        # Concreteness score normalization: 1.0 (min) to 5.0 (max) -> 0 to 100
        # Formula: (raw - 1) / (5 - 1) * 100
        concreteness_score = max(0.0, min(100.0, ((concreteness_score_raw - 1.0) / 4.0) * 100.0))
        
        # AoA bonus/penalty (if AoA data available)
        # Lower AoA = easier = bonus, Higher AoA = harder = penalty
        aoa_bonus = 0.0
        if data['aoa'] is not None:
            # Normalize AoA to 0-1 scale (lower AoA = higher score)
            # Assuming typical range: 2-15 years
            aoa_score = max(0.0, 1.0 - (data['aoa'] / 15.0))
            # Add AoA as a bonus/penalty (scale: -20 to +20 points)
            # Words learned earlier (lower AoA) get bonus, words learned later get penalty
            aoa_bonus = (aoa_score - 0.5) * 40.0  # Maps 0-1 to -20 to +20
        
        # Combine scores with weights
        combined_score = (hsk_score * hsk_weight) + (concreteness_score * concreteness_weight)
        
        # Count known characters (prerequisites) - bonus points
        known_chars = sum(1 for char in data['chars'] if char in mastered_set)
        total_chars = len(data['chars']) if data['chars'] else 1
        char_bonus = 0.0
        if total_chars > 0:
            char_ratio = known_chars / total_chars
            char_bonus = 50.0 * char_ratio  # Bonus based on ratio of known chars
        
        final_score = combined_score + char_bonus + aoa_bonus
        
        if final_score > 0:  # Only include words with positive scores
            scored_words.append({
                'word': word,
                'pinyin': data['pinyin'],
                'hsk': data['hsk'],
                'score': final_score,
                'known_chars': known_chars,
                'total_chars': len(data['chars']),
                'concreteness': data['concreteness'],
                'age_of_acquisition': data['aoa']  # Add AoA to response
            })
    
    # Sort by score and return top N
    scored_words.sort(key=lambda x: x['score'], reverse=True)
    
    # Debug: Show top 5 scores with breakdown
    if scored_words:
        print(f"   🔝 Top 5 scores (target_level={target_level}):")
        for i, item in enumerate(scored_words[:5]):
            word_data = words_data.get(item['word'], {})
            hsk = item['hsk']
            conc = word_data.get('concreteness', None)
            score = item['score']
            # Calculate what the scores would have been
            hsk_raw = 0.0
            if hsk == target_level:
                hsk_raw = 100.0
            elif hsk == target_level + 1:
                hsk_raw = 50.0
            elif hsk and hsk < target_level:
                hsk_raw = 25.0
            elif hsk and hsk > target_level + 1:
                hsk_raw = -500.0
            hsk_norm = min(100.0, hsk_raw) if hsk_raw > 0 else 0.0
            conc_norm = ((conc - 1.0) / 4.0 * 100.0) if conc else 50.0
            hsk_contrib = hsk_norm * hsk_weight
            conc_contrib = conc_norm * concreteness_weight
            char_bonus = item.get('known_chars', 0) / max(item.get('total_chars', 1), 1) * 50.0
            print(f"      {i+1}. {item['word']}: final={score:.1f} (HSK={hsk}→{hsk_norm:.0f}*{hsk_weight:.2f}={hsk_contrib:.1f}, conc={conc if conc else 'N/A'}→{conc_norm:.0f}*{concreteness_weight:.2f}={conc_contrib:.1f}, chars={char_bonus:.1f})")
    
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

# Child Profile endpoints
@app.get("/profiles", response_model=List[ChildProfile])
async def get_profiles(db: Session = Depends(get_db)):
    """Get all profiles from database"""
    profiles = ProfileService.get_all(db)
    return [ProfileService.profile_to_dict(db, p) for p in profiles]

@app.post("/profiles", response_model=ChildProfile)
async def create_profile(profile: ChildProfile, db: Session = Depends(get_db)):
    """Create new profile in database"""
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    from utils import generate_slug
    
    # Generate slug-based ID from name if not provided
    if not profile.id:
        profile.id = generate_slug(profile.name)
    
    # Ensure uniqueness
    existing = ProfileService.get_by_id(db, profile.id)
    if existing:
        counter = 2
        base_id = profile.id
        while ProfileService.get_by_id(db, f"{base_id}-{counter}"):
            counter += 1
        profile.id = f"{base_id}-{counter}"
    
    # Prepare data for database
    profile_data = profile.dict()
    
    # Split mastered words into lists
    mastered_words_str = profile_data.pop('mastered_words', '') or ''
    mastered_english_str = profile_data.pop('mastered_english_words', '') or ''
    mastered_grammar_str = profile_data.pop('mastered_grammar', '') or ''
    
    profile_data['mastered_words_list'] = [w.strip() for w in mastered_words_str.split(', ') if w.strip()]
    profile_data['mastered_english_words_list'] = [w.strip() for w in mastered_english_str.split(', ') if w.strip()]
    profile_data['mastered_grammar_list'] = [g.strip() for g in mastered_grammar_str.split(',') if g.strip()]
    
    created_profile = ProfileService.create(db, profile_data)
    return ProfileService.profile_to_dict(db, created_profile)

@app.get("/profiles/{profile_id}", response_model=ChildProfile)
async def get_profile(profile_id: str, db: Session = Depends(get_db)):
    """Get specific profile from database"""
    profile = ProfileService.get_by_id(db, profile_id)
    if not profile:
        # Try to find by name for backward compatibility
        all_profiles = ProfileService.get_all(db)
        for p in all_profiles:
            if p.name == profile_id:
                return ProfileService.profile_to_dict(db, p)
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileService.profile_to_dict(db, profile)

@app.put("/profiles/{profile_id}", response_model=ChildProfile)
async def update_profile(profile_id: str, updated_profile: ChildProfile, db: Session = Depends(get_db)):
    """Update profile in database"""
    # Find profile by ID or name
    profile = ProfileService.get_by_id(db, profile_id)
    if not profile:
        all_profiles = ProfileService.get_all(db)
        for p in all_profiles:
            if p.name == profile_id:
                profile = p
                profile_id = p.id
                break
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Prepare data for database
    profile_data = updated_profile.dict()
    
    # Split mastered words into lists
    mastered_words_str = profile_data.pop('mastered_words', '') or ''
    mastered_english_str = profile_data.pop('mastered_english_words', '') or ''
    mastered_grammar_str = profile_data.pop('mastered_grammar', '') or ''
    
    profile_data['mastered_words_list'] = [w.strip() for w in mastered_words_str.split(', ') if w.strip()]
    profile_data['mastered_english_words_list'] = [w.strip() for w in mastered_english_str.split(', ') if w.strip()]
    profile_data['mastered_grammar_list'] = [g.strip() for g in mastered_grammar_str.split(',') if g.strip()]
    
    updated = ProfileService.update(db, profile_id, profile_data)
    return ProfileService.profile_to_dict(db, updated)

@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    """Delete profile from database"""
    # Find profile by ID or name
    profile = ProfileService.get_by_id(db, profile_id)
    if not profile:
        all_profiles = ProfileService.get_all(db)
        for p in all_profiles:
            if p.name == profile_id:
                profile_id = p.id
                break
    
    success = ProfileService.delete(db, profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    
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

@app.get("/cards/{card_id}/image-data")
async def get_card_image_data(card_id: str):
    cards = load_json_file(CARDS_FILE, [])
    for card in cards:
        if card.get("id") == card_id:
            image_data = card.get("image_data")
            if not image_data:
                raise HTTPException(status_code=404, detail="No image data found for this card")
            return {"image_data": image_data}
    raise HTTPException(status_code=404, detail="Card not found")

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

@app.post("/cards/{card_id}/generate-image")
async def generate_card_image(card_id: str, request: CardImageRequest):
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
        conversation_handler = ConversationHandler()
        
        primary_text = (
            sanitized_card.get("text_field")
            or sanitized_card.get("cloze_text")
            or sanitized_card.get("front")
            or sanitized_card.get("back")
            or ""
        )
        user_request = request.user_request or f"Generate an illustration for this flashcard content: {primary_text}"
        
        image_description = conversation_handler._generate_image_description(
            card_content=sanitized_card,
            user_request=user_request,
            child_profile=None
        )
        
        image_result = conversation_handler.generate_actual_image(
            image_description=image_description,
            user_request=user_request
        )
        
        card["image_description"] = image_description
        card["image_generated"] = image_result.get("success", False)
        card["image_error"] = image_result.get("error")
        card["is_placeholder"] = image_result.get("is_placeholder", False)
        card["image_prompt"] = image_result.get("prompt_used")
        card["image_url"] = image_result.get("image_url")
        card["image_data"] = image_result.get("image_data")
        
        image_html = None
        if image_result.get("success") and image_result.get("image_data"):
            image_html = (
                f'<img src="{image_result["image_data"]}" alt="Generated image" '
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
                    profile_id_raw = (profile.get("id") or "").lower()
                    profile_name_slug = normalize_to_slug(profile.get("name", ""))
                    mention_lower = mention.lower()
                    mention_slug = normalize_to_slug(mention)
                    
                    if (profile_id_raw and profile_id_raw == mention_lower or
                        profile.get("name") == mention or 
                        profile_name_slug and profile_name_slug == mention_slug or
                        (profile_id_raw and profile_id_raw.endswith(mention_lower)) or  # For partial UUID matching
                        (profile_id_raw and mention_lower.endswith(profile_id_raw)) or
                        (profile_name_slug and mention_slug.endswith(profile_name_slug))):
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
        cards = generator.generate_from_prompt(
            user_prompt=message.content,
            context_tags=context_tags,
            child_profile=child_profile,
            prompt_template=prompt_template
        )
        
        # Save generated cards
        existing_cards = load_json_file(CARDS_FILE, [])
        for card in cards:
            remarks = build_cuma_remarks(card, context_tags)
            card["field__Remarks"] = remarks or ""
            card.pop("field__Remarks_annotations", None)
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
        
        # Prepare cards (ensure remarks computed and tags normalized)
        for card in cards_to_sync:
            remarks = build_cuma_remarks(card, [])
            card["field__Remarks"] = remarks or ""
            card.pop("field__Remarks_annotations", None)
        
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
                          srs-kg:text ?word_text ;
                          srs-kg:hskLevel ?hsk .
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
    """
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

# Cache for word->image mapping (loaded from TTL file)
_word_image_cache = None
_word_image_cache_time = None

def get_word_image_map():
    """Load word->image mapping from TTL file (cached, much faster than full graph)."""
    global _word_image_cache, _word_image_cache_time
    from pathlib import Path
    import threading
    
    kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_cwn.ttl"
    
    # Reload if file is newer than cache (or cache doesn't exist)
    file_mtime = kg_file.stat().st_mtime if kg_file.exists() else 0
    if _word_image_cache is None or _word_image_cache_time is None or file_mtime > _word_image_cache_time:
        # If cache is being built, return empty dict (will be populated on next request)
        if _word_image_cache is None:
            # Start loading in background thread to avoid blocking
            def load_cache():
                global _word_image_cache, _word_image_cache_time
                from rdflib import Graph, Namespace
                from rdflib.namespace import RDF
                
                print("Loading word->image mapping from TTL file (this may take 20-30 seconds)...")
                graph = Graph()
                SRS_KG = Namespace("http://srs4autism.com/schema/")
                graph.bind("srs-kg", SRS_KG)
                
                if kg_file.exists():
                    try:
                        # Only parse the file (this is still slow but necessary)
                        graph.parse(str(kg_file), format="turtle")
                        
                        # Build a simple word->image mapping (much faster lookups)
                        word_image_map = {}
                        sparql = """
                        PREFIX srs-kg: <http://srs4autism.com/schema/>
                        SELECT DISTINCT ?word_text ?image_path
                        WHERE {
                            ?word_uri a srs-kg:Word .
                            ?word_uri srs-kg:text ?word_text .
                            ?word_uri srs-kg:means ?concept_uri .
                            ?concept_uri srs-kg:hasVisualization ?image_uri .
                            ?image_uri srs-kg:imageFilePath ?image_path .
                        }
                        """
                        
                        results = graph.query(sparql)
                        for row in results:
                            word = str(row.word_text).strip()
                            img = str(row.image_path).strip()
                            if word and img:
                                if not img.startswith('/'):
                                    img = '/' + img
                                word_image_map[word] = img
                        
                        _word_image_cache = word_image_map
                        _word_image_cache_time = file_mtime
                        print(f"✅ Loaded {len(word_image_map)} word->image mappings from {len(graph)} triples")
                    except Exception as e:
                        print(f"Error loading KG file: {e}")
                        import traceback
                        traceback.print_exc()
                        if _word_image_cache is None:
                            _word_image_cache = {}  # Empty dict as fallback
            
            # Start loading in background
            thread = threading.Thread(target=load_cache, daemon=True)
            thread.start()
            # Return empty dict while loading
            return {}
    
    return _word_image_cache or {}

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

# Get grammar points for mastered grammar management
@app.get("/vocabulary/grammar")
async def get_grammar_points(cefr_level: Optional[str] = None):
    """
    Get grammar points from the knowledge graph, optionally filtered by CEFR level (A1, A2, etc.).
    Returns grammar points with their structure, explanation, and CEFR level.
    """
    try:
        # Query the knowledge graph for grammar points
        # Use OPTIONAL for properties that might be missing, and handle language-tagged literals
        # Get both English and Chinese labels, and first example sentence (only one per grammar point)
        # First get all grammar points with their properties
        sparql = """
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?gp_uri ?label_en ?label_zh ?structure ?explanation ?cefr WHERE {
            ?gp_uri a srs-kg:GrammarPoint .
            OPTIONAL { ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }
            OPTIONAL { ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }
            OPTIONAL { ?gp_uri srs-kg:structure ?structure }
            OPTIONAL { ?gp_uri srs-kg:explanation ?explanation }
            OPTIONAL { ?gp_uri srs-kg:cefrLevel ?cefr }
            FILTER(BOUND(?label_en) || BOUND(?label_zh))  # At least one label must exist
        }
        ORDER BY ?cefr ?label_en
        """
        
        if cefr_level:
            # Filter by CEFR level
            sparql = sparql.replace(
                "ORDER BY ?cefr ?label",
                f"""
                FILTER(?cefr = "{cefr_level}")
                ORDER BY ?cefr ?label
                """
            )
        
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
                
                # Use English label as primary, fallback to Chinese if no English
                label = label_en or label_zh
                
                if label:
                    # Get first example sentence for this grammar point
                    example_chinese = ''
                    try:
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
                    except:
                        pass  # If example query fails, just continue without example
                    
                    grammar_points.append({
                        'gp_uri': gp_uri,  # Include URI for updating
                        'grammar_point': label,
                        'grammar_point_zh': label_zh,  # Chinese translation
                        'structure': structure,
                        'explanation': explanation,
                        'cefr_level': cefr,
                        'example_chinese': example_chinese  # First example sentence in Chinese
                    })
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
GRAMMAR_CORRECTIONS_FILE = str(PROJECT_ROOT / "data" / "content_db" / "grammar_corrections.json")

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
            # Filter by language: English grammar has English labels, Chinese grammar has Chinese labels
            if language == "en":
                # English grammar: must have English label
                label_filter = 'FILTER(BOUND(?label_en))'
            else:
                # Chinese grammar: must have Chinese label
                label_filter = 'FILTER(BOUND(?label_zh))'
            
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
        if language == "en":
            label_filter_all = 'FILTER(BOUND(?label_en))'
        else:
            label_filter_all = 'FILTER(BOUND(?label_zh))'
        
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
                example_chinese = ''
                try:
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

# Mount static files for serving images
# Images are stored in media/visual_images/ relative to project root
media_dir = PROJECT_ROOT / "media"
if media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
