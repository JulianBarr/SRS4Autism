import os
import json
import re
import unicodedata
import requests
import asyncio
import threading
import logging
import time
from functools import lru_cache
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..core.config import PROJECT_ROOT, ENGLISH_SIMILARITY_FILE, WORD_KP_CACHE_FILE

from fastapi import HTTPException
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

# Try to import rdflib for TTL parsing
try:
    from rdflib import Graph, Literal, Namespace
    from rdflib.namespace import RDF, RDFS
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

from scripts.knowledge_graph.pinyin_parser import TONE_MARKS, extract_tone, add_tone_to_final, parse_pinyin

logger = logging.getLogger(__name__)


# Load environment variables (for Gemini API key)
WORD_IMAGE_MAP_FILE = PROJECT_ROOT / "data" / "word_image_map.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-pro")
FUSEKI_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://localhost:3030/srs4autism/query")

# Initialize Gemini model
_genai_model: Optional[genai.GenerativeModel] = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _genai_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    except Exception as exc:
        print(f"⚠️ Unable to configure Gemini model: {exc}")
else:
    print("⚠️ GEMINI_API_KEY not set; falling back to cache-only knowledge lookup.")

# Cache files

def load_json_file(file_path: Path, default_value: Any) -> Any:
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    return default_value

def save_json_file(file_path: Path, data: Any):
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error writing JSON to {file_path}: {e}")

def _get_word_kp_cache_file() -> Path:
    from ..core.config import WORD_KP_CACHE_FILE
    return WORD_KP_CACHE_FILE
_word_kp_cache: Dict[str, Dict[str, Any]] = {}
try:
    _word_kp_cache = load_json_file(_get_word_kp_cache_file(), {})
    if not isinstance(_word_kp_cache, dict):
        _word_kp_cache = {}
except Exception as exc:
    print(f"⚠️ Could not load word knowledge cache: {exc}")
    _word_kp_cache = {}

def _save_word_kp_cache():
    try:
        save_json_file(_get_word_kp_cache_file(), _word_kp_cache)
    except Exception as exc:
        print(f"⚠️ Failed to save word knowledge cache: {exc}")

# Cache for word->image mapping
_word_image_cache: Optional[Dict[str, str]] = None
_word_image_cache_time: Optional[float] = None
_word_image_cache_lock = threading.Lock()

def query_sparql(sparql_query: str, output_format: str = "application/sparql-results+json") -> Dict[str, Any]:
    headers = {
        "Accept": output_format,
        "Content-Type": "application/sparql-query"
    }
    try:
        response = requests.post(FUSEKI_ENDPOINT, data=sparql_query.encode('utf-8'), headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error querying SPARQL: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"SPARQL query failed: {e.response.text}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error querying SPARQL: {e}")
        raise HTTPException(status_code=503, detail=f"Could not connect to knowledge graph service: {e}")
    except Exception as e:
        logger.error(f"General error querying SPARQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge graph: {e}")


def _sanitize_for_sparql_literal(value: str) -> str:
    """Escape characters for safe SPARQL literal usage."""
    if value is None:
        return ""
    return value.replace("\\", "\\\\").replace('"', '\\"')

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
              rdfs:label "{sparql_word}"@zh .
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

def fix_iu_ui_tone_placement(pinyin: str) -> str:
    """
    Fix pinyin tone marks to follow 'i u 并列标在后' rule.
    When i and u appear together:
    - 'iu' -> tone should be on 'u' (e.g., 'liú' not 'líu')
    - 'ui' -> tone should be on 'i' (e.g., 'guì' not 'gúi')
    
    Returns corrected pinyin.
    """
    if not pinyin:
        return pinyin
    
    # Split into syllables (space-separated)
    syllables = pinyin.split()
    fixed_syllables = []
    
    for syllable in syllables:
        # Extract tone from syllable
        syllable_no_tone, tone = extract_tone(syllable)
        
        if not tone:
            fixed_syllables.append(syllable)
            continue
        
        # Check for 'iu' pattern - tone should be on 'u' (the latter)
        if 'iu' in syllable_no_tone.lower():
            # Check if tone is currently on 'i' (wrong)
            i_tones = ['ī', 'í', 'ǐ', 'ì', 'Ī', 'Í', 'Ǐ', 'Ì']
            has_tone_on_i = any(i_tone in syllable for i_tone in i_tones)
            
            if has_tone_on_i:
                # Wrong: tone is on i, should be on u
                # Use add_tone_to_final which follows the i u 并列标在后 rule
                fixed = add_tone_to_final(syllable_no_tone, tone)
                fixed_syllables.append(fixed)
            else:
                # Tone is already on u or correct, keep as is
                fixed_syllables.append(syllable)
        
        # Check for 'ui' pattern - tone should be on 'i' (the latter)
        elif 'ui' in syllable_no_tone.lower():
            # Check if tone is currently on 'u' (wrong)
            u_tones = ['ū', 'ú', 'ǔ', 'ù', 'Ū', 'Ú', 'Ǔ', 'Ù']
            has_tone_on_u = any(u_tone in syllable for u_tone in u_tones)
            
            if has_tone_on_u:
                # Wrong: tone is on u, should be on i
                # Use add_tone_to_final which follows the i u 并列标在后 rule
                fixed = add_tone_to_final(syllable_no_tone, tone)
                fixed_syllables.append(fixed)
            else:
                # Tone is already on i or correct, keep as is
                fixed_syllables.append(syllable)
        else:
            # No iu/ui pattern, keep as is
            fixed_syllables.append(syllable)
    
    return ' '.join(fixed_syllables)

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

def get_word_image_map() -> Dict[str, str]:
    """Load word->image mapping from TTL file (cached, much faster than full graph)."""
    global _word_image_cache, _word_image_cache_time, _word_image_cache_lock
    
    with _word_image_cache_lock:
        ttl_file = PROJECT_ROOT / "knowledge_graph" / "world_model_cwn.ttl"
        
        # 1. Check in-memory cache
        current_time = time.time()
        file_mtime = ttl_file.stat().st_mtime if ttl_file.exists() else 0
        
        if _word_image_cache is not None and _word_image_cache_time is not None:
            if file_mtime <= _word_image_cache_time:
                return _word_image_cache

        # 2. Check JSON cache on disk
        if WORD_IMAGE_MAP_FILE.exists():
            json_mtime = WORD_IMAGE_MAP_FILE.stat().st_mtime
            if json_mtime >= file_mtime:
                cached_map = load_json_file(WORD_IMAGE_MAP_FILE, None)
                if cached_map:
                    _word_image_cache = cached_map
                    _word_image_cache_time = json_mtime
                    return _word_image_cache

        # 3. If no valid cache, load from TTL
        if not ttl_file.exists():
            return {}

        if not HAS_RDFLIB:
            logger.warning("rdflib not installed, cannot parse TTL for image mapping")
            return {}

        try:
            g = Graph()
            g.parse(str(ttl_file), format="turtle")
            
            SRS_KG = Namespace("http://srs4autism.com/schema/")
            
            word_image_map = {}
            for s, p, o in g.triples((None, RDF.type, SRS_KG.Word)):
                word_label = None
                image_file = None
                
                for p2, o2 in g.predicate_objects(s):
                    if p2 == RDFS.label and hasattr(o2, 'language') and o2.language == 'zh':
                        word_label = str(o2)
                    elif p2 == SRS_KG.imageFile:
                        image_file = str(o2)
                
                if word_label and image_file:
                    word_image_map[word_label] = image_file
            
            _word_image_cache = word_image_map
            _word_image_cache_time = time.time()
            
            # Save to JSON cache
            save_json_file(WORD_IMAGE_MAP_FILE, word_image_map)
            return _word_image_cache
        except Exception as e:
            logger.error(f"Error loading word image map from TTL: {e}")
            return {}

def strip_pinyin_tones(pinyin_str: str) -> str:
    """
    Removes tone marks (diacritics) from a pinyin string.
    Example: 'shì' -> 'shi', 'zhōng' -> 'zhong'
    """
    if not pinyin_str:
        return ""
    # Use NFKD normalization to separate base characters from diacritics
    normalized = unicodedata.normalize('NFKD', pinyin_str)
    # Filter out the combining marks (tones)
    return "".join([c for c in normalized if not unicodedata.combining(c)])

def get_pinyin_tone(pinyin_str: str) -> int:
    """
    Identifies the tone (1-4) of a pinyin syllable. Returns 0 for neutral.
    """
    tone_marks = {
        'ā': 1, 'ē': 1, 'ī': 1, 'ō': 1, 'ū': 1, 'ǖ': 1,
        'á': 2, 'é': 2, 'í': 2, 'ó': 2, 'ú': 2, 'ǘ': 2,
        'ǎ': 3, 'ě': 3, 'ǐ': 3, 'ǒ': 3, 'ǔ': 3, 'ǚ': 3,
        'à': 4, 'è': 4, 'ì': 4, 'ò': 4, 'ù': 4, 'ǜ': 4,
    }
    for char in pinyin_str:
        if char in tone_marks:
            return tone_marks[char]
    return 0

def get_standard_pinyin(pinyin_str: str) -> str:
    """
    Returns a lowercase, stripped version of the pinyin.
    """
    if not pinyin_str:
        return ""
    return pinyin_str.strip().lower()
