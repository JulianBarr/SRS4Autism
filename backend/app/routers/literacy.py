"""
Literacy Router V2 (Logic City Level 2)
Features:
- Interleaved Sorting (Concrete/Abstract)
- Advanced Anki Integration (Cloze, Pinyin Typing)
- Automatic Pinyin Generation
- Performance Optimizations (Caching, Startup Loading)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import sqlite3
import zipfile
import tempfile
import json
import re
from html import unescape
import sys
import base64
import hashlib
import itertools
import time
import threading
import csv

# Pinyin Library Check
try:
    from pypinyin import pinyin as get_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    print("⚠️ pypinyin not found. Pinyin generation may be inaccurate. Run: pip install pypinyin")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db import get_db
from database.services import ProfileService
from anki_integration.anki_connect import AnkiConnect

router = APIRouter(prefix="/literacy", tags=["literacy"])

# Path to the English Vocabulary Level 2 deck
ENGLISH_VOCAB_DECK = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
ANKI_ORDER_CACHE_FILE = PROJECT_ROOT / "data" / "content_db" / "anki_order_cache.json"

# Cache configuration
CACHE_TTL = 3600  # 1 hour in seconds

# In-memory cache for original order (word -> order_index)
_anki_order_cache: Optional[Dict[str, int]] = None

# Global cache for sorted vocabulary list
_sorted_vocab_cache: Optional[List[Dict[str, Any]]] = None
_cache_timestamp: Optional[float] = None
_cache_lock = threading.Lock()

# --- MODELS ---

class LogicCityVocabItem(BaseModel):
    """Vocabulary item for Logic City"""
    word_id: str
    english: str
    chinese: Optional[str] = None
    pinyin: Optional[str] = None
    image_path: Optional[str] = None
    word_type: str = "Concrete"  # 'Concrete' or 'Abstract'
    sentence: Optional[str] = None
    synonym_hint: Optional[str] = None
    anki_order: Optional[int] = None
    is_mastered: bool = False
    is_synced: bool = False

class PaginatedVocabResponse(BaseModel):
    items: List[LogicCityVocabItem]
    total: int
    page: int
    page_size: int
    total_pages: int

# --- HELPERS ---

def clean_anki_field(text: str) -> str:
    if not text: return ""
    text = unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = text.replace('\xa0', ' ')
    return text.strip().lower()

def _load_anki_order_from_apkg() -> Dict[str, int]:
    """
    Extract the original order of words from the Anki deck.
    This is the expensive operation that should only run once at startup.
    Returns a mapping of word (lowercase) -> order_index (0-based)
    """
    # Try to load from persistent cache file first
    if ANKI_ORDER_CACHE_FILE.exists():
        try:
            with open(ANKI_ORDER_CACHE_FILE, 'r', encoding='utf-8') as f:
                order_map = json.load(f)
                if isinstance(order_map, dict):
                    print(f"✅ Loaded Anki order from cache: {len(order_map)} words")
                    return order_map
                else:
                    print(f"⚠️  Cache file has invalid format, regenerating...")
        except (json.JSONDecodeError, IOError, OSError) as e:
            print(f"⚠️  Error reading cache file ({e}), regenerating...")
    
    # Cache miss or error: extract from .apkg file
    if not ENGLISH_VOCAB_DECK.exists():
        print(f"⚠️  English Vocabulary deck not found: {ENGLISH_VOCAB_DECK}")
        return {}
    
    order_map = {}
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(ENGLISH_VOCAB_DECK, 'r') as z:
                # Find database file
                db_files = ['collection.anki21', 'collection.anki2']
                db_path = None
                
                for db_file in db_files:
                    if db_file in z.namelist():
                        z.extract(db_file, tmpdir)
                        db_path = Path(tmpdir) / db_file
                        break
                
                if not db_path or not db_path.exists():
                    print(f"⚠️  No database found in {ENGLISH_VOCAB_DECK.name}")
                    return {}
                
                # Read database
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get model field names
                cursor.execute("SELECT models FROM col LIMIT 1")
                row = cursor.fetchone()
                if not row or not row[0]:
                    conn.close()
                    return {}
                
                models_json = json.loads(row[0])
                model_fields = {}
                
                for model_id_str, model_data in models_json.items():
                    fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
                    model_fields[int(model_id_str)] = fields
                
                # Get notes ordered by ID (to maintain deck order)
                cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
                rows = cursor.fetchall()
                
                order_index = 0
                for note_id, mid, flds_str in rows:
                    fields = flds_str.split('\x1f')  # Anki field separator
                    field_names = model_fields.get(mid, [])
                    
                    # Extract English word from Back field (field 1) or first field
                    english_word = None
                    
                    # Try Back field first
                    for i, field_name in enumerate(field_names):
                        if field_name.lower() == 'back' and i < len(fields):
                            field_value = fields[i].strip()
                            clean_word = clean_anki_field(field_value)
                            if clean_word and len(clean_word) < 100:
                                english_word = clean_word
                                break
                    
                    # Fallback to second field or first field
                    if not english_word:
                        if len(fields) > 1:
                            clean_word = clean_anki_field(fields[1])
                            if clean_word and len(clean_word) < 100:
                                english_word = clean_word
                        elif len(fields) > 0:
                            clean_word = clean_anki_field(fields[0])
                            if clean_word and len(clean_word) < 100:
                                english_word = clean_word
                    
                    if english_word:
                        # Only add if not already in map (first occurrence wins)
                        if english_word not in order_map:
                            order_map[english_word] = order_index
                            order_index += 1
                
                conn.close()
        
        # Save to persistent cache
        try:
            # Ensure directory exists
            ANKI_ORDER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            with open(ANKI_ORDER_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(order_map, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved Anki order to cache: {len(order_map)} words")
        except (IOError, OSError) as e:
            print(f"⚠️  Error saving cache file ({e}), continuing without cache...")
        
        print(f"✅ Loaded original Anki order for {len(order_map)} words")
        return order_map
    
    except Exception as e:
        print(f"❌ Error extracting Anki order: {e}")
        import traceback
        traceback.print_exc()
        return {}

def get_anki_original_order() -> Dict[str, int]:
    """
    Get Anki order from cache. Should be pre-loaded at startup.
    """
    global _anki_order_cache
    
    if _anki_order_cache is not None:
        return _anki_order_cache
    
    # Lazy load if not initialized (shouldn't happen if startup is called)
    _anki_order_cache = _load_anki_order_from_apkg()
    return _anki_order_cache

def query_sparql(query: str, output_format: str = "application/sparql-results+json", timeout: int = 30):
    import requests
    FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"
    try:
        headers = {"Accept": output_format, "Content-Type": "application/x-www-form-urlencoded"}
        data = {"query": query}
        response = requests.post(FUSEKI_ENDPOINT, data=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json() if output_format == "application/sparql-results+json" else response.text
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Graph Error: {str(e)}")

def find_image_file(image_path: str) -> Optional[Path]:
    if not image_path: return None
    
    # Clean the input path to get just the filename
    filename = Path(image_path).name
    
    # Define explicit search paths based on the user's project structure
    media_dirs = [
        PROJECT_ROOT / "content" / "media" / "objects",  # <--- ADD THIS

        #Legacy
        PROJECT_ROOT / "content" / "media" / "images",        # Primary match for your structure
        PROJECT_ROOT / "content" / "media" / "visual_images",
        PROJECT_ROOT / "media" / "images",
        PROJECT_ROOT / "media" / "visual_images",
        PROJECT_ROOT / "media"
    ]
    
    # Search for the file
    for d in media_dirs:
        candidate = d / filename
        if candidate.exists(): 
            return candidate
            
    print(f"⚠️ Image not found: {filename} (Checked {len(media_dirs)} dirs)")
    return None
# --- GATEKEEPER CONFIG ---
CURATION_REPORT_PATH = PROJECT_ROOT / "logs" / "vision_cleanup_report.csv"

def _load_curation_blocklist() -> Dict[str, bool]:
    """
    Loads the curation report to determine which words to BLOCK.

    Returns a set of words to hide.

    Logic:
    - If a word is NOT in this list, it is considered "Auto-Passed" by AI.
    - We only BLOCK words that you explicitly reviewed and marked for deletion.
    """
    if not CURATION_REPORT_PATH.exists():
        print(f"⚠️ Gatekeeper: Report not found at {CURATION_REPORT_PATH}. Showing ALL.")
        return set()

    blocklist = set()

    try:
        with open(CURATION_REPORT_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            # Handle Excel BOM if present
            if content.startswith('\ufeff'): content = content[1:]

            reader = csv.DictReader(content.splitlines())

            for row in reader:
                english_word = row.get('English_Word', '').strip().lower()
                if not english_word: continue

                # Check columns case-insensitively
                reviewed = row.get('Reviewed', '').strip().lower() == 'true'
                match_status = row.get('Match?', '').strip().lower() == 'true'
                new_filename = row.get('New_Filename', '').strip()

                # BLOCK CONDITION:
                # You reviewed it AND (You said it's not a match OR You explicitly wrote DELETE)
                # Note: If you provided a valid filename correction, we do NOT block it.
                is_rejected = (not match_status) or (new_filename.upper() == 'DELETE')

                if reviewed and is_rejected:
                    # If you corrected it with a valid filename, don't block.
                    # e.g. New_Filename = "correct_apple.jpg" -> Keep it.
                    # e.g. New_Filename = "DELETE" -> Block it.
                    if new_filename and new_filename.upper() != 'DELETE':
                        continue

                    blocklist.add(english_word)

        print(f"🛡️  Gatekeeper Active: Blocking {len(blocklist)} explicitly deleted words.")
        return blocklist

    except Exception as e:
        print(f"❌ Gatekeeper Error: {e}")
        return set()

def _build_sorted_vocab_cache(sort_order: str = "interleaved") -> List[Dict[str, Any]]:
    """
    Build the sorted vocabulary cache by querying the knowledge graph.
    This is expensive and should be cached.
    """
    anki_order = get_anki_original_order()

    # 1. LOAD THE BLOCKLIST
    blocklist = _load_curation_blocklist()

    # Optimized query (updated for ontology v2: uses rdfs:label)
    light_query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?wordUri ?englishWord (SAMPLE(?imageNode) AS ?exampleImage) WHERE {
        ?zhNode srs-kg:learningTheme "Logic City" ; srs-kg:means ?concept .
        ?wordUri a srs-kg:Word ; srs-kg:means ?concept ; rdfs:label ?englishWord .
        FILTER (lang(?englishWord) = "en")
        OPTIONAL { ?concept srs-kg:hasVisualization ?imageNode }
    } GROUP BY ?wordUri ?englishWord
    """

    light_result = query_sparql(light_query)
    bindings = light_result.get("results", {}).get("bindings", [])

    # Bucketing
    concrete_list = []
    abstract_list = []
    seen = set()

    for b in bindings:
        english = b['englishWord']['value'].strip()
        english_lower = english.lower()

        # 2. CHECK BLOCKLIST (Explicit Deletions)
        if english_lower in blocklist:
            continue

        # 3. CHECK HALLUCINATIONS (The "Smoke" Check)
        # If it's not in the original Anki deck list, it's a generated ghost. Block it.
        if english_lower not in anki_order:
            continue

        if english_lower in seen: continue
        seen.add(english_lower)

        word_uri = b['wordUri']['value']
        has_image = 'exampleImage' in b and b['exampleImage'].get('value')

        item = {
            'word_uri': word_uri,
            'word_id': word_uri.split('/')[-1],
            'english': english,
            'word_type': 'Concrete' if has_image else 'Abstract',
            'anki_order': anki_order.get(english_lower, 999999)
        }

        if item['word_type'] == 'Concrete':
            concrete_list.append(item)
        else:
            abstract_list.append(item)

    # Sorting Strategy
    final_list = []
    if sort_order == "interleaved":
        concrete_list.sort(key=lambda x: x['anki_order'])
        abstract_list.sort(key=lambda x: x['anki_order'])
        for c, a in itertools.zip_longest(concrete_list, abstract_list):
            if c: final_list.append(c)
            if a: final_list.append(a)
    else:
        final_list = concrete_list + abstract_list
        final_list.sort(key=lambda x: x['anki_order'])

    return final_list
def get_sorted_vocab_cache(force_refresh: bool = False, sort_order: str = "interleaved") -> List[Dict[str, Any]]:
    """
    Get the sorted vocabulary cache, rebuilding if necessary.
    Thread-safe with locking to prevent concurrent rebuilds.
    """
    global _sorted_vocab_cache, _cache_timestamp
    
    with _cache_lock:
        current_time = time.time()
        
        # Check if cache is valid
        if (_sorted_vocab_cache is not None and 
            _cache_timestamp is not None and 
            not force_refresh and
            (current_time - _cache_timestamp) < CACHE_TTL):
            return _sorted_vocab_cache
        
        # Rebuild cache
        print(f"🔄 Building sorted vocabulary cache (force_refresh={force_refresh})...")
        _sorted_vocab_cache = _build_sorted_vocab_cache(sort_order)
        _cache_timestamp = current_time
        print(f"✅ Cache built: {len(_sorted_vocab_cache)} words")
        return _sorted_vocab_cache

def initialize_literacy_cache():
    """
    Initialize the cache at startup. Call this from the main app's startup event.
    """
    print("🚀 Initializing literacy cache at startup...")
    global _anki_order_cache
    
    # Load Anki order
    _anki_order_cache = _load_anki_order_from_apkg()
    
    # Pre-populate vocab cache
    get_sorted_vocab_cache(force_refresh=False)
    
    print("✅ Literacy cache initialized")

# --- ANKI ARCHITECTURE ---

def ensure_cuma_level2_model(anki: AnkiConnect) -> None:
    """Creates the advanced Note Type with Cloze, Typing, and Conditional Layout."""
    model_name = "CUMA - Master Level 2"
    fields = [
        "Concept", "Chinese", "Pinyin_Toned", "Pinyin_Clean", 
        "Image", "Audio", "Sentence_Cloze", "Synonym_Hint", "Word_Type"
    ]
    
    css = """
    .card { font-family: Arial; font-size: 24px; text-align: center; color: #333; background-color: #f9f9f9; padding: 20px; }
    .concept { font-size: 1.2em; font-weight: bold; color: #555; margin-bottom: 15px; }
    .visual img { max-height: 300px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .sentence { font-size: 1.4em; margin: 20px 0; line-height: 1.6; }
    .cloze { font-weight: bold; color: #2196F3; }
    .hint { font-size: 0.8em; color: #e91e63; margin-top: 10px; font-style: italic; }
    .type-prompt { font-size: 0.8em; color: #888; margin-top: 20px; }
    input { font-size: 1.2em; text-align: center; padding: 5px; border: 1px solid #ddd; border-radius: 4px; }
    """
    
    # Front Template: Conditional Rendering based on Word_Type
    front = """
    <div class="concept">{{Concept}}</div>
    
    {{#Image}}
        <div class="visual">{{Image}}</div>
    {{/Image}}
    
    {{^Image}}
        {{#Sentence_Cloze}}
            <div class="sentence">{{cloze:Sentence_Cloze}}</div>
            {{#Synonym_Hint}}<div class="hint">Hint: Not {{Synonym_Hint}}</div>{{/Synonym_Hint}}
        {{/Sentence_Cloze}}
    {{/Image}}
    
    <div class="type-prompt">Type Pinyin (no tones):</div>
    {{type:Pinyin_Clean}}
    """
    
    back = """
    <div class="concept">{{Concept}}</div>
    
    {{#Image}}<div class="visual">{{Image}}</div>{{/Image}}
    
    <div class="sentence">{{Chinese}}</div>
    <div style="font-size: 1.2em; color: #666;">{{Pinyin_Toned}}</div>
    
    <hr>
    <div>{{type:Pinyin_Clean}}</div>
    {{Audio}}
    """
    
    existing_models = anki._invoke("modelNames", {})
    if model_name not in existing_models:
        print(f"📝 Creating Advanced Note Model: {model_name}")
        anki._invoke("createModel", {
            "modelName": model_name,
            "inOrderFields": fields,
            "css": css,
            "cardTemplates": [{"Name": "Master Card", "Front": front, "Back": back}]
        })
    else:
        # Ensure fields exist if updating
        curr_fields = anki._invoke("modelFieldNames", {"modelName": model_name})
        for f in fields:
            if f not in curr_fields:
                anki._invoke("modelFieldAdd", {"modelName": model_name, "fieldName": f})

# --- ENDPOINTS ---

@router.get("/logic-city/vocab", response_model=PaginatedVocabResponse)
async def get_logic_city_vocab(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    profile_id: Optional[str] = None,
    sort_order: str = "interleaved",
    force_refresh: bool = Query(False, description="Force cache refresh")
):
    """
    Get Logic City vocabulary items with optimized caching.
    
    Performance optimizations:
    - Uses cached sorted vocabulary list (rebuilds only if expired or force_refresh=True)
    - Only processes details for the current page (50 items max)
    - Anki order loaded at startup, not on every request
    """
    try:
        # Get cached sorted list (or rebuild if needed)
        final_list = get_sorted_vocab_cache(force_refresh=force_refresh, sort_order=sort_order)
        
        # OPTIMIZATION: Paginate FIRST, then only process details for the current page
        total = len(final_list)
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        paged_items = final_list[start : start + page_size]
        
        # Early return if no items
        if not paged_items:
            return PaginatedVocabResponse(
                items=[],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        
        # STEP 2: Detail Fetch - ONLY for the current page (50 items max)
        uris = " ".join([f"<{x['word_uri']}>" for x in paged_items])
        
        detail_query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?wordUri ?chineseWord ?imagePath WHERE {{
            VALUES ?wordUri {{ {uris} }}
            ?wordUri srs-kg:means ?concept .

            # Fetch ONLY the Logic City tagged Chinese word (updated for ontology v2: uses rdfs:label)
            OPTIONAL {{
                ?zhNode rdfs:label ?chineseWord ;
                        srs-kg:means ?concept ;
                        srs-kg:learningTheme "Logic City" .
                FILTER (lang(?chineseWord) = "zh")
            }}

            OPTIONAL {{
                ?concept srs-kg:hasVisualization ?v . ?v srs-kg:imageFilePath ?imagePath .
            }}
        }}
        """
        
        detail_res = query_sparql(detail_query)
        details_map = {}
        for b in detail_res.get("results", {}).get("bindings", []):
            uri = b['wordUri']['value']
            if uri not in details_map: details_map[uri] = {}
            if 'chineseWord' in b: details_map[uri]['chinese'] = b['chineseWord']['value']
            if 'imagePath' in b: details_map[uri]['image_path'] = b['imagePath']['value']
        
        # Build Final Response - only for the current page
        vocab = []
        for item in paged_items:
            det = details_map.get(item['word_uri'], {})
            chinese = det.get('chinese', '')
            
            # --- START FIX: Image Path Resolution ---
            raw_img_path = det.get('image_path')
            final_image_path = None
            
            if raw_img_path:
                # 1. Use existing helper to find the physical file on disk
                found_path = find_image_file(raw_img_path)
                
                if found_path:
                    # 2. If found, construct a valid URL path
                    # Check if file is in content/media/ or just media/
                    try:
                        rel_path = found_path.relative_to(PROJECT_ROOT)
                        path_parts = rel_path.parts
                        
                        # If in content/media/, use /content/media/... URL
                        if len(path_parts) >= 3 and path_parts[0] == "content" and path_parts[1] == "media":
                            # content/media/images/filename.jpg -> /content/media/images/filename.jpg
                            final_image_path = "/" + "/".join(path_parts)
                        else:
                            # media/images/filename.jpg -> /media/images/filename.jpg
                            # Or just filename.jpg -> /media/filename.jpg
                            filename = found_path.name
                            parent_dir = found_path.parent.name
                            
                            if parent_dir in ['visual_images', 'images', 'pinyin']:
                                final_image_path = f"/media/{parent_dir}/{filename}"
                            else:
                                final_image_path = f"/media/{filename}"
                    except ValueError:
                        # Fallback if relative path calculation fails
                        filename = found_path.name
                        parent_dir = found_path.parent.name
                        if parent_dir in ['visual_images', 'images', 'pinyin']:
                            final_image_path = f"/media/{parent_dir}/{filename}"
                        else:
                            final_image_path = f"/media/{filename}"
                else:
                    # 3. Fallback: Clean the raw path if file not found on disk
                    clean_path = raw_img_path.replace("content/media/", "").replace("/media/", "")
                    if clean_path.startswith("/"): clean_path = clean_path[1:]
                    final_image_path = f"/media/{clean_path}"
            # --- END FIX ---

            # Generate Pinyin
            pinyin_str = ""
            if chinese and HAS_PYPINYIN:
                pinyin_str = " ".join([x[0] for x in get_pinyin(chinese, style=Style.TONE)])
            
            vocab.append(LogicCityVocabItem(
                word_id=item['word_id'],
                english=item['english'],
                chinese=chinese,
                pinyin=pinyin_str,
                image_path=final_image_path,  # <--- Using resolved path
                word_type=item['word_type'],
                anki_order=item['anki_order']
            ))
        
        return PaginatedVocabResponse(
            items=vocab,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logic-city/sync")
async def sync_logic_city_to_anki(request: Dict[str, Any]):
    """Syncs cards using the new Master Level 2 Note Type"""
    try:
        word_ids = request.get("word_ids", [])
        deck_name = request.get("deck_name", "English Vocabulary Level 2")
        anki = AnkiConnect()
        if not anki.ping(): raise HTTPException(503, "Anki unreachable")
        
        anki.create_deck(deck_name)
        ensure_cuma_level2_model(anki)
        
        # Fetch Data
        uris = [f"http://srs4autism.com/schema/{wid}" for wid in word_ids]
        uri_str = " ".join([f"<{u}>" for u in uris])
        
        q = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?wordUri ?english ?chinese ?imagePath WHERE {{
            VALUES ?wordUri {{ {uri_str} }}
            ?wordUri rdfs:label ?english .
            FILTER(lang(?english)="en")
            ?wordUri srs-kg:means ?c .
            OPTIONAL {{
                ?zh srs-kg:means ?c; rdfs:label ?chinese; srs-kg:learningTheme "Logic City".
                FILTER(lang(?chinese)="zh")
            }}
            OPTIONAL {{ ?c srs-kg:hasVisualization ?v. ?v srs-kg:imageFilePath ?imagePath. }}
        }}
        """
        res = query_sparql(q)
        
        processed = 0
        added = 0
        updated = 0
        
        for b in res.get("results", {}).get("bindings", []):
            english = b['english']['value']
            chinese = b.get('chinese', {}).get('value', '')
            img_raw = b.get('imagePath', {}).get('value', '')
            
            # Pinyin Generation
            pinyin_toned = ""
            pinyin_clean = ""
            if chinese and HAS_PYPINYIN:
                pinyin_toned = " ".join([x[0] for x in get_pinyin(chinese, style=Style.TONE)])
                pinyin_clean = "".join([x[0] for x in get_pinyin(chinese, style=Style.NORMAL)])
            
            # Determine Type
            word_type = "Concrete" if img_raw else "Abstract"
            
            # Image Upload
            image_html = ""
            if img_raw:
                img_path = find_image_file(img_raw)
                if img_path:
                    with open(img_path, "rb") as f:
                        data = f.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        fname = f"{hashlib.md5(data).hexdigest()[:12]}{img_path.suffix}"
                        anki_fname = anki.store_media_file(fname, b64)
                        image_html = f'<img src="/static/media/{anki_fname}">'
            
            # Sentence Placeholder (since we don't have sentences yet)
            sentence_cloze = ""
            if word_type == "Abstract":
                sentence_cloze = f"This is a placeholder sentence for {{c1::{chinese}}}."
            
            fields = {
                "Concept": english,
                "Chinese": chinese,
                "Pinyin_Toned": pinyin_toned,
                "Pinyin_Clean": pinyin_clean,
                "Image": image_html,
                "Word_Type": word_type,
                "Sentence_Cloze": sentence_cloze,
                "Synonym_Hint": "", 
                "Audio": ""
            }
            
            # Escape double quotes safely outside the f-string
            safe_english = english.replace('"', '\\"')
            query = f'deck:"{deck_name}" Concept:"{safe_english}"'
            notes = anki._invoke("findNotes", {"query": query})
            
            if notes:
                anki._invoke("updateNoteFields", {"note": {"id": notes[0], "fields": fields}})
                updated += 1
            else:
                anki.add_note(deck_name, "CUMA - Master Level 2", fields, tags=["CUMA", "Level2"])
                added += 1
            processed += 1
            
        return {"message": f"Synced {processed} cards", "added": added, "updated": updated}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))
