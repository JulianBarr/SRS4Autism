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

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
        
        # ============================================================
        # STEP 1: Light Scan - Get only English words and URIs
        # ============================================================
        light_query = """
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        
        SELECT DISTINCT ?wordUri ?englishWord WHERE {
            ?wordUri a srs-kg:Word ;
                   srs-kg:learningTheme "Logic City" ;
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
        
        SELECT ?wordUri ?chineseWord ?pinyin ?imagePath WHERE {{
            VALUES ?wordUri {{ {uri_values} }}
            
            ?wordUri a srs-kg:Word .
            
            # Get concept
            OPTIONAL {{
                ?wordUri srs-kg:means ?concept .
                
                # Find Chinese words linked to the same concept
                OPTIONAL {{
                    ?chineseWordNode a srs-kg:Word ;
                                    srs-kg:text ?chineseWord ;
                                    srs-kg:means ?concept .
                    FILTER (lang(?chineseWord) = "zh")
                    
                    # Get pinyin if available
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
                
                # Pinyin
                if "pinyin" in binding:
                    pinyin = binding["pinyin"].get("value", "").strip()
                    if pinyin:
                        detail_map[word_uri]['pinyin'] = pinyin
                
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
        Sync results
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
        
        # TODO: Implement actual sync logic
        # 1. Fetch vocabulary items for word_ids
        # 2. Create/update Anki notes with custom_image_path, pinyin, notes
        # 3. Use AnkiConnect to sync
        
        return {
            "message": f"Sync initiated for {len(word_ids)} words",
            "word_ids": word_ids,
            "deck_name": deck_name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing to Anki: {str(e)}")

