"""
Literacy router for Logic City vocabulary management
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

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to import pypinyin for correct pinyin generation
try:
    from pypinyin import pinyin as get_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    print("⚠️ pypinyin not found. Pinyin generation may be inaccurate. Install with: pip install pypinyin")

from database.db import get_db
from database.services import ProfileService
from anki_integration.anki_connect import AnkiConnect

router = APIRouter(prefix="/literacy", tags=["literacy"])

# Path to the English Vocabulary Level 2 deck
ENGLISH_VOCAB_DECK = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"

# Cache file path for Anki order
ANKI_ORDER_CACHE_FILE = PROJECT_ROOT / "data" / "content_db" / "anki_order_cache.json"

# In-memory cache for original order (word -> order_index)
_anki_order_cache: Optional[Dict[str, int]] = None


class LogicCityVocabItem(BaseModel):
    """Vocabulary item for Logic City"""
    word_id: str  # Knowledge graph word ID (e.g., "word-en-virtue")
    english: str
    chinese: Optional[str] = None
    pinyin: Optional[str] = None
    image_path: Optional[str] = None
    custom_image_path: Optional[str] = None
    notes: Optional[str] = None
    anki_order: Optional[int] = None  # Original order from Anki deck
    is_mastered: bool = False
    is_synced: bool = False


class VocabUpdateRequest(BaseModel):
    """Request model for updating vocabulary item"""
    custom_image_path: Optional[str] = None
    chinese: Optional[str] = None
    pinyin: Optional[str] = None
    notes: Optional[str] = None


class PaginatedVocabResponse(BaseModel):
    """Paginated response for vocabulary items"""
    items: List[LogicCityVocabItem]
    total: int
    page: int
    page_size: int
    total_pages: int


def clean_anki_field(text: str) -> str:
    """Clean Anki HTML field to get raw word"""
    if not text:
        return ""
    text = unescape(text)  # &nbsp; -> space
    text = re.sub(r'<[^>]+>', '', text)  # Remove tags
    text = re.sub(r'\[.*?\]', '', text)  # Remove sound/image refs
    text = text.replace('\xa0', ' ')
    return text.strip().lower()


def get_anki_original_order() -> Dict[str, int]:
    """
    Extract the original order of words from the Anki deck.
    Uses persistent JSON cache to avoid re-extracting on every request.
    Returns a mapping of word (lowercase) -> order_index (0-based)
    """
    global _anki_order_cache
    
    # Return in-memory cache if available
    if _anki_order_cache is not None:
        return _anki_order_cache
    
    # Try to load from persistent cache file
    if ANKI_ORDER_CACHE_FILE.exists():
        try:
            with open(ANKI_ORDER_CACHE_FILE, 'r', encoding='utf-8') as f:
                order_map = json.load(f)
                if isinstance(order_map, dict):
                    _anki_order_cache = order_map
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
        
        _anki_order_cache = order_map
        print(f"✅ Loaded original Anki order for {len(order_map)} words")
        return order_map
    
    except Exception as e:
        print(f"❌ Error extracting Anki order: {e}")
        import traceback
        traceback.print_exc()
        return {}


def query_sparql(query: str, output_format: str = "application/sparql-results+json", timeout: int = 30):
    """Query Fuseki SPARQL endpoint"""
    import requests
    
    FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"
    
    try:
        # Use POST for large queries (more reliable than GET with long URLs)
        headers = {"Accept": output_format, "Content-Type": "application/x-www-form-urlencoded"}
        data = {"query": query}
        response = requests.post(FUSEKI_ENDPOINT, data=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        if output_format == "application/sparql-results+json":
            return response.json()
        return response.text
    except requests.exceptions.ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Knowledge graph server (Jena Fuseki) is not running. Please start it with: bash restart_fuseki.sh (Error: {str(e)})"
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Knowledge graph server unavailable: {str(e)}")


@router.get("/logic-city/vocab", response_model=PaginatedVocabResponse)
async def get_logic_city_vocab(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    profile_id: Optional[str] = Query(None, description="Profile ID for mastered words filtering"),
    filter_mastered: bool = Query(False, description="Filter out mastered words"),
    sort_order: str = Query("anki_default", description="Sort order: 'anki_default' preserves original Anki order")
):
    """
    Get Logic City vocabulary items with original Anki deck order preserved.
    Uses two-step pagination to avoid timeouts: light scan first, then detail fetch.
    
    Args:
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (default: 50, max: 100)
        profile_id: Profile ID (required if filter_mastered=True)
        filter_mastered: If True, exclude words in mastered_words table
        sort_order: "anki_default" (default) preserves original Anki order
    
    Returns:
        Paginated response with vocabulary items ordered by original Anki deck sequence
    """
    try:
        # Get mastered words if filtering
        mastered_words = set()
        if filter_mastered:
            if not profile_id:
                raise HTTPException(status_code=400, detail="profile_id is required when filter_mastered=True")
            db = next(get_db())
            try:
                mastered_words = set(ProfileService.get_mastered_words(db, profile_id, 'en'))
            finally:
                db.close()
        
        # Get original Anki order
        anki_order = get_anki_original_order()
        
#        # ============================================================
#        # STEP 1: Light Scan - Get only English words and URIs
#        # ============================================================
#        light_query = """
#        PREFIX srs-kg: <http://srs4autism.com/schema/>
#        
#        SELECT DISTINCT ?wordUri ?englishWord WHERE {
#            ?wordUri a srs-kg:Word ;
#                   srs-kg:learningTheme "Logic City" ;
#                   srs-kg:text ?englishWord .
#            FILTER (lang(?englishWord) = "en")
#        }
#        """
        # ============================================================
        # STEP 1: Light Scan - Get English words via TAGGED Chinese words
        # ============================================================
        light_query = """
        PREFIX srs-kg: <http://srs4autism.com/schema/>

        SELECT DISTINCT ?wordUri ?englishWord WHERE {
            # 1. Find the TAGGED Chinese Node (The Anchor)
            ?zhNode srs-kg:learningTheme "Logic City" .

            # 2. Go up to the Concept
            ?zhNode srs-kg:means ?concept .

            # 3. Find the English Word connected to that same concept
            ?wordUri a srs-kg:Word ;
                     srs-kg:means ?concept ;
                     srs-kg:text ?englishWord .

            FILTER (lang(?englishWord) = "en")
        }
        """
        
        print(f"📊 Step 1: Light scan for Logic City words...")
        light_result = query_sparql(light_query, timeout=30)
        if not light_result or "results" not in light_result:
            return PaginatedVocabResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )
        
        light_bindings = light_result.get("results", {}).get("bindings", [])
        
        # Build list of word items with basic info
        word_items = []
        seen_english = set()
        
        for binding in light_bindings:
            word_uri = binding.get("wordUri", {}).get("value", "")
            english = binding.get("englishWord", {}).get("value", "").strip()
            
            if not english or english.lower() in seen_english:
                continue
            
            seen_english.add(english.lower())
            
            # Extract word_id from URI
            word_id = word_uri.split("/")[-1] if "/" in word_uri else word_uri.replace("http://srs4autism.com/schema/", "")
            
            # Check if mastered
            is_mastered = english.lower() in mastered_words
            
            # Filter if requested
            if filter_mastered and is_mastered:
                continue
            
            # Get Anki order
            anki_order_index = anki_order.get(english.lower())
            
            word_items.append({
                'word_uri': word_uri,
                'word_id': word_id,
                'english': english,
                'anki_order': anki_order_index,
                'is_mastered': is_mastered
            })
        
        # Sort by Anki order (None values go to end)
        if sort_order == "anki_default":
            word_items.sort(key=lambda x: (x['anki_order'] is None, x['anki_order'] or 999999))
        
        # Calculate pagination
        total_count = len(word_items)
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Slice for current page
        paged_items = word_items[start_idx:end_idx]
        
        print(f"✅ Step 1 complete: {total_count} total words, page {page}/{total_pages} ({len(paged_items)} items)")
        
        # ============================================================
        # STEP 2: Detail Fetch - Get Chinese, Pinyin, Images for page
        # ============================================================
        if not paged_items:
            return PaginatedVocabResponse(
                items=[],
                total=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        
        # Build VALUES clause for specific URIs
        uri_values = " ".join([f"<{item['word_uri']}>" for item in paged_items])
        
        detail_query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        
        SELECT ?wordUri ?chineseWord ?imagePath WHERE {{
            VALUES ?wordUri {{ {uri_values} }}
            
            ?wordUri a srs-kg:Word .
            
            # Get concept
            OPTIONAL {{
                ?wordUri srs-kg:means ?concept .
                
                # FIXED: Find Chinese word SPECIFIC to this theme to avoid polysemy collisions
                OPTIONAL {{
                    ?chineseWordNode a srs-kg:Word ;
                                    srs-kg:text ?chineseWord ;
                                    srs-kg:means ?concept ;
                                    srs-kg:learningTheme "Logic City" .
                    FILTER (lang(?chineseWord) = "zh")
                }}
                
                # Get image visualization from concept
                OPTIONAL {{
                    ?concept srs-kg:hasVisualization ?imageNode .
                    ?imageNode srs-kg:imageFilePath ?imagePath .
                }}
            }}
        }}
        """
        
        print(f"📊 Step 2: Fetching details for {len(paged_items)} words...")
        detail_result = query_sparql(detail_query, timeout=60)
        
        # Build detail map: word_uri -> {chinese, pinyin, image_path}
        detail_map = {}
        if detail_result and "results" in detail_result:
            detail_bindings = detail_result.get("results", {}).get("bindings", [])
            for binding in detail_bindings:
                word_uri = binding.get("wordUri", {}).get("value", "")
                if not word_uri:
                    continue
                
                if word_uri not in detail_map:
                    detail_map[word_uri] = {}
                
                # Chinese
                if "chineseWord" in binding:
                    chinese = binding["chineseWord"].get("value", "").strip()
                    if chinese:
                        detail_map[word_uri]['chinese'] = chinese
                
                        # FIXED: Generate Pinyin in Python to guarantee correct order
                        if HAS_PYPINYIN:
                            # Generate pinyin: [['niú'], ['zǎi'], ['kù']] -> "niú zǎi kù"
                            py_list = get_pinyin(chinese, style=Style.TONE)
                            flat_py = " ".join([item[0] for item in py_list])
                            detail_map[word_uri]['pinyin'] = flat_py
                        else:
                            detail_map[word_uri]['pinyin'] = ""  # Fallback
                
                # Image path - resolve with fallback directories
                if "imagePath" in binding:
                    img_path = binding["imagePath"].get("value", "").strip()
                    if img_path:
                        # Convert to URL path
                        if img_path.startswith("content/media/"):
                            image_path = f"/media/{img_path.replace('content/media/', '')}"
                        elif img_path.startswith("/content/media/"):
                            image_path = f"/media/{img_path.replace('/content/media/', '')}"
                        elif not img_path.startswith('/'):
                            image_path = f"/media/{img_path}"
                        else:
                            image_path = img_path
                        
                        # Try to resolve actual file location by searching multiple directories
                        filename = Path(image_path).name
                        media_dirs = [
                            PROJECT_ROOT / "content" / "media" / "images",
                            PROJECT_ROOT / "media" / "images",
                            PROJECT_ROOT / "media" / "visual_images",
                            PROJECT_ROOT / "media" / "pinyin",
                            PROJECT_ROOT / "media"
                        ]
                        
                        found = False
                        for media_dir in media_dirs:
                            if not media_dir.exists():
                                continue
                            potential_path = media_dir / filename
                            if potential_path.exists() and potential_path.is_file():
                                rel_path = potential_path.relative_to(PROJECT_ROOT)
                                image_path = f"/{rel_path.as_posix()}"
                                found = True
                                break
                        
                        # Always set image_path, but ensure it's in correct format
                        # Frontend ImageWithFallback will handle fallback if file doesn't exist
                        if found:
                            detail_map[word_uri]['image_path'] = image_path
                        else:
                            # File not found in expected locations, but still return the path
                            # Frontend will try multiple fallback directories
                            # Ensure path starts with /media/ for proper routing
                            if not image_path.startswith('/media/'):
                                # If it's just a filename, prepend /media/
                                if '/' not in image_path:
                                    detail_map[word_uri]['image_path'] = f"/media/{image_path}"
                                else:
                                    detail_map[word_uri]['image_path'] = image_path
                            else:
                                detail_map[word_uri]['image_path'] = image_path
        
        print(f"✅ Step 2 complete: Fetched details for {len(detail_map)} words")
        
        # ============================================================
        # STEP 3: Merge and Build Response
        # ============================================================
        vocabulary = []
        for item in paged_items:
            word_uri = item['word_uri']
            details = detail_map.get(word_uri, {})
            
            vocabulary.append(LogicCityVocabItem(
                word_id=item['word_id'],
                english=item['english'],
                chinese=details.get('chinese'),
                pinyin=details.get('pinyin'),
                image_path=details.get('image_path'),
                anki_order=item['anki_order'],
                is_mastered=item['is_mastered'],
                is_synced=False  # TODO: Check sync status from Anki
            ))
        
        return PaginatedVocabResponse(
            items=vocabulary,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching Logic City vocabulary: {str(e)}")


@router.put("/logic-city/vocab/{word_id}")
async def update_logic_city_vocab(
    word_id: str,
    update: VocabUpdateRequest
):
    """
    Update a Logic City vocabulary item.
    
    Args:
        word_id: Knowledge graph word ID (e.g., "word-en-virtue")
        update: Update request with custom_image_path, chinese, pinyin, and/or notes
    
    Returns:
        Updated vocabulary item
    """
    try:
        # TODO: Store updates in database or knowledge graph
        # For now, return success message
        # In a full implementation, you would:
        # 1. Store custom_image_path, chinese, pinyin, notes in a database table
        # 2. Or update the knowledge graph directly
        
        updated_fields = update.dict(exclude_unset=True)
        
        return {
            "message": "Update successful",
            "word_id": word_id,
            "updated_fields": updated_fields
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating vocabulary item: {str(e)}")


def ensure_cuma_basic_model(anki: AnkiConnect) -> None:
    """
    Ensure the "CUMA - Chinese Vocabulary" note model exists in Anki.
    Creates it if it doesn't exist.
    
    Args:
        anki: AnkiConnect client instance
    """
    model_name = "CUMA - Chinese Vocabulary"
    fields = ["Concept", "Chinese", "Pinyin", "Image", "Audio"]
    
    # Check if model exists
    model_names = anki._invoke("modelNames", {})
    
    if model_name not in model_names:
        print(f"📝 Creating note model: {model_name}")
        
        # Basic CSS for the model
        css = """
.card {
    font-family: Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #333;
    background-color: #fff;
}
"""
        
        # Simple card template: Front shows Concept, Back shows Chinese, Pinyin, Image
        card_templates = [
            {
                "Name": "Card 1",
                "Front": "{{Concept}}",
                "Back": "{{Chinese}}<br>{{Pinyin}}<br>{{Image}}<br>{{Audio}}"
            }
        ]
        
        # Create the model
        anki._invoke("createModel", {
            "modelName": model_name,
            "inOrderFields": fields,
            "css": css,
            "cardTemplates": card_templates
        })
        print(f"✅ Created note model: {model_name}")
    else:
        print(f"✅ Note model already exists: {model_name}")
        
        # Ensure all required fields exist
        existing_fields = anki._invoke("modelFieldNames", {"modelName": model_name})
        for field in fields:
            if field not in existing_fields:
                print(f"  Adding missing field: {field}")
                anki._invoke("modelFieldAdd", {
                    "modelName": model_name,
                    "fieldName": field
                })


def find_image_file(image_path: str) -> Optional[Path]:
    """
    Find the actual image file on disk given a path from the knowledge graph.
    
    Args:
        image_path: Path from knowledge graph (e.g., "/media/images/virtue.jpg")
    
    Returns:
        Path to the actual file if found, None otherwise
    """
    if not image_path:
        return None
    
    # Normalize the path
    if image_path.startswith("/media/"):
        image_path = image_path[7:]  # Remove leading /media/
    elif image_path.startswith("content/media/"):
        image_path = image_path.replace("content/media/", "")
    
    # Try multiple possible locations
    media_dirs = [
        PROJECT_ROOT / "content" / "media" / "images",
        PROJECT_ROOT / "media" / "images",
        PROJECT_ROOT / "media" / "visual_images",
        PROJECT_ROOT / "media" / "pinyin",
        PROJECT_ROOT / "media"
    ]
    
    filename = Path(image_path).name
    
    for media_dir in media_dirs:
        if not media_dir.exists():
            continue
        potential_path = media_dir / filename
        if potential_path.exists() and potential_path.is_file():
            return potential_path
    
    # Try with the full path if it's a relative path
    if not Path(image_path).is_absolute():
        for media_dir in media_dirs:
            potential_path = media_dir / image_path
            if potential_path.exists() and potential_path.is_file():
                return potential_path
    
    return None


@router.post("/logic-city/sync")
async def sync_logic_city_to_anki(
    request: Dict[str, Any]
):
    """
    Sync modified Logic City cards to Anki via AnkiConnect.
    
    Request body:
        {
            "word_ids": ["word-en-virtue", ...],
            "deck_name": "English Vocabulary Level 2"
        }
    
    Returns:
        Sync results with counts of added and updated cards
    """
    try:
        word_ids = request.get("word_ids", [])
        deck_name = request.get("deck_name", "English Vocabulary Level 2")
        
        if not word_ids:
            raise HTTPException(status_code=400, detail="word_ids is required")
        
        # Initialize AnkiConnect
        anki = AnkiConnect()
        
        if not anki.ping():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed."
            )
        
        # Ensure deck exists
        try:
            anki.create_deck(deck_name)
        except:
            pass  # Deck might already exist
        
        # Ensure "CUMA - Chinese Vocabulary" model exists
        ensure_cuma_basic_model(anki)
        
        # Use the exact model name
        MODEL_NAME = "CUMA - Chinese Vocabulary"
        
        # Use the exact model name
        MODEL_NAME = "CUMA - Chinese Vocabulary"
        
        # ============================================================
        # STEP 1: Fetch vocabulary data for word_ids
        # ============================================================
        print(f"📊 Fetching data for {len(word_ids)} words...")
        
        # Build URIs from word_ids
        word_uris = [f"http://srs4autism.com/schema/{word_id}" for word_id in word_ids]
        uri_values = " ".join([f"<{uri}>" for uri in word_uris])
        
        # Query to get English word, Chinese, and Image
        detail_query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        
        SELECT ?wordUri ?englishWord ?chineseWord ?imagePath WHERE {{
            VALUES ?wordUri {{ {uri_values} }}
            
            ?wordUri a srs-kg:Word ;
                     srs-kg:text ?englishWord .
            FILTER (lang(?englishWord) = "en")
            
            # Get concept
            OPTIONAL {{
                ?wordUri srs-kg:means ?concept .
                
                # FIXED: Find Chinese word SPECIFIC to this theme to avoid polysemy collisions
                OPTIONAL {{
                    ?chineseWordNode a srs-kg:Word ;
                                    srs-kg:text ?chineseWord ;
                                    srs-kg:means ?concept ;
                                    srs-kg:learningTheme "Logic City" .
                    FILTER (lang(?chineseWord) = "zh")
                }}
                
                # Get image visualization from concept
                OPTIONAL {{
                    ?concept srs-kg:hasVisualization ?imageNode .
                    ?imageNode srs-kg:imageFilePath ?imagePath .
                }}
            }}
        }}
        """
        
        detail_result = query_sparql(detail_query, timeout=60)
        
        if not detail_result or "results" not in detail_result:
            raise HTTPException(status_code=500, detail="Failed to fetch vocabulary data from knowledge graph")
        
        # Build word data map
        word_data_map = {}
        detail_bindings = detail_result.get("results", {}).get("bindings", [])
        
        for binding in detail_bindings:
            word_uri = binding.get("wordUri", {}).get("value", "")
            if not word_uri:
                continue
            
            english = binding.get("englishWord", {}).get("value", "").strip()
            if not english:
                continue
            
            if word_uri not in word_data_map:
                word_data_map[word_uri] = {
                    "english": english,
                    "chinese": None,
                    "pinyin": None,
                    "image_path": None
                }
            
            # Chinese
            if "chineseWord" in binding:
                chinese = binding["chineseWord"].get("value", "").strip()
                if chinese:
                    word_data_map[word_uri]["chinese"] = chinese
                    
                    # FIXED: Generate Pinyin in Python to guarantee correct order
                    if HAS_PYPINYIN:
                        # Generate pinyin: [['niú'], ['zǎi'], ['kù']] -> "niú zǎi kù"
                        py_list = get_pinyin(chinese, style=Style.TONE)
                        flat_py = " ".join([item[0] for item in py_list])
                        word_data_map[word_uri]["pinyin"] = flat_py
                    else:
                        word_data_map[word_uri]["pinyin"] = ""  # Fallback
            
            # Image path
            if "imagePath" in binding:
                img_path = binding["imagePath"].get("value", "").strip()
                if img_path:
                    # Convert to URL path format
                    if img_path.startswith("content/media/"):
                        image_path = f"/media/{img_path.replace('content/media/', '')}"
                    elif img_path.startswith("/content/media/"):
                        image_path = f"/media/{img_path.replace('/content/media/', '')}"
                    elif not img_path.startswith('/'):
                        image_path = f"/media/{img_path}"
                    else:
                        image_path = img_path
                    
                    word_data_map[word_uri]["image_path"] = image_path
        
        print(f"✅ Fetched data for {len(word_data_map)} words")
        
        # ============================================================
        # STEP 2: Process images and sync to Anki
        # ============================================================
        added_count = 0
        updated_count = 0
        errors = []
        
        # Track uploaded images to avoid duplicates
        uploaded_hashes = {}  # Maps content_hash -> anki_filename
        anki_media_map = {}  # Maps original path -> anki_filename
        
        for word_uri, data in word_data_map.items():
            try:
                english = data["english"]
                chinese = data.get("chinese") or ""
                pinyin = data.get("pinyin") or ""
                image_path = data.get("image_path")
                
                # Process image if available
                image_html = ""
                if image_path:
                    # Find the actual file on disk
                    image_file = find_image_file(image_path)
                    
                    if image_file and image_file.exists():
                        try:
                            # Read file
                            with open(image_file, 'rb') as f:
                                file_data = f.read()
                            
                            # Calculate content hash
                            content_hash = hashlib.md5(file_data).hexdigest()
                            
                            # Check if we've already uploaded this file
                            if content_hash in uploaded_hashes:
                                anki_filename = uploaded_hashes[content_hash]
                            else:
                                # Generate Anki filename: cm_logic_[sanitized_name]_[hash].[ext]
                                file_ext = image_file.suffix
                                file_stem = image_file.stem
                                sanitized_stem = re.sub(r'[^a-zA-Z0-9_-]', '_', file_stem)
                                if len(sanitized_stem) > 50:
                                    sanitized_stem = sanitized_stem[:50]
                                
                                short_hash = content_hash[:8]
                                anki_filename = f"cm_logic_{sanitized_stem}_{short_hash}{file_ext}"
                                
                                # Base64 encode
                                base64_data = base64.b64encode(file_data).decode('utf-8')
                                
                                # Upload to Anki
                                stored_filename = anki.store_media_file(anki_filename, base64_data)
                                uploaded_hashes[content_hash] = stored_filename
                                anki_filename = stored_filename
                            
                            anki_media_map[image_path] = anki_filename
                            image_html = f'<img src="{anki_filename}">'
                            
                        except Exception as e:
                            print(f"⚠️  Warning: Failed to process image {image_path}: {e}")
                            # Continue without image
                    else:
                        print(f"⚠️  Warning: Image file not found: {image_path}")
                
                # Build Anki note fields - map 'english' variable to 'Concept' field
                fields = {
                    "Concept": english,  # Use "Concept" instead of "English"
                    "Chinese": chinese,
                    "Pinyin": pinyin,
                    "Image": image_html,
                    "Audio": ""  # Audio field is empty for now
                }
                
                # Check if note already exists - query using "Concept" field
                # Escape double quotes in English word for Anki query
                escaped_english = english.replace('"', '\\"')
                query = f'deck:"{deck_name}" Concept:"{escaped_english}"'
                existing_note_ids = anki._invoke("findNotes", {"query": query})
                
                if existing_note_ids:
                    # Update existing note
                    note_id = existing_note_ids[0]  # Use first match
                    anki._invoke("updateNoteFields", {
                        "note": {
                            "id": note_id,
                            "fields": fields
                        }
                    })
                    updated_count += 1
                    print(f"  ✅ Updated: {english}")
                else:
                    # Add new note - use exact model name
                    note_id = anki.add_note(
                        deck_name=deck_name,
                        model_name=MODEL_NAME,
                        fields=fields,
                        tags=["CUMA", "LogicCity"],
                        allow_duplicate=False
                    )
                    if note_id:
                        added_count += 1
                        print(f"  ✅ Added: {english}")
                    else:
                        errors.append(f"Failed to add note for {english}")
            
            except Exception as e:
                error_msg = f"Error processing {data.get('english', 'unknown')}: {str(e)}"
                print(f"  ❌ {error_msg}")
                errors.append(error_msg)
        
        return {
            "message": f"Sync completed for {len(word_ids)} words",
            "added": added_count,
            "updated": updated_count,
            "errors": errors,
            "total_processed": added_count + updated_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing to Anki: {str(e)}")

