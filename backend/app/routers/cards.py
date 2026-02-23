import sys
import os
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database.db import get_db
from backend.database.models import ApprovedCard
from ..core.config import CARDS_FILE
from ..utils.common import load_json_file, save_json_file, split_tag_annotations

logger = logging.getLogger(__name__)
router = APIRouter()

# --- GLOBALS ---
_genai_model = None
def _set_genai_model(model):
    global _genai_model
    _genai_model = model

# --- SCHEMAS ---
# We use a flexible Dict return type to support flattening
class UpdateCardRequest(BaseModel):
    status: str
    text_field: Optional[str] = None
    extra_field: Optional[str] = None
    front: Optional[str] = None
    back: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[Dict[str, Any]] = None

class ImageGenerationRequest(BaseModel):
    card_id: int 
    prompt: Optional[str] = None
    location: str = "after"

# --- HELPER: ROBUST PARSER & FLATTENER ---
def safe_parse_content(content_raw):
    """Parses nested JSON strings safely."""
    if not content_raw: return {}
    if isinstance(content_raw, dict): return content_raw
    if isinstance(content_raw, str):
        try:
            parsed = json.loads(content_raw)
            if isinstance(parsed, str): # Handle double-encoding
                try: return json.loads(parsed)
                except: return {"text_field": parsed}
            return parsed
        except:
            return {"text_field": content_raw}
    return {}

def format_card_flat(card):
    """
    CRITICAL FIX: Flattens the DB structure to match the old JSON format.
    Instead of { id: 1, content: { text: "Hi" } }
    It returns { id: "1", text: "Hi" }
    Also maps text_field/extra_field to front/back for basic cards.
    """
    # 1. Start with DB Columns
    base_obj = {
        "id": str(card.id),  # String ID for Frontend
        "profile_id": card.profile_id,
        "card_type": card.card_type,
        "status": card.status,
        "approved_at": card.approved_at
    }
    
    # 2. Parse Content Blob
    content_obj = safe_parse_content(card.content)
    
    # 3. Merge (Flatten) Content into Base
    # This ensures 'text_field', 'tags', etc. are at the top level
    base_obj.update(content_obj)
    
    # 4. Map field names for frontend compatibility
    # Frontend expects 'front' and 'back' for basic cards, but backend uses 'text_field' and 'extra_field'
    if card.card_type in ['basic', 'basic_reverse']:
        if 'text_field' in base_obj and 'front' not in base_obj:
            base_obj['front'] = base_obj['text_field']
        if 'extra_field' in base_obj and 'back' not in base_obj:
            base_obj['back'] = base_obj['extra_field']
        # Also keep the original fields for backward compatibility
        if 'front' in base_obj and 'text_field' not in base_obj:
            base_obj['text_field'] = base_obj['front']
        if 'back' in base_obj and 'extra_field' not in base_obj:
            base_obj['extra_field'] = base_obj['back']
    
    # 5. Ensure ID/Status didn't get overwritten by content garbage
    base_obj["id"] = str(card.id)
    base_obj["status"] = card.status
    
    return base_obj

# --- ENDPOINTS ---

@router.get("/cards", response_model=List[Dict[str, Any]])
def get_all_cards(db: Session = Depends(get_db)):
    """Get all cards from database, ordered by ID descending (newest first)."""
    try:
        cards = db.query(ApprovedCard).order_by(ApprovedCard.id.desc()).all()
        result = []
        for card in cards:
            flat_card = format_card_flat(card)
            # Normalize tags field
            tags = flat_card.get('tags', [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            elif not isinstance(tags, (list, tuple)):
                tags = [str(tags)] if tags else []
            flat_card['tags'] = tags if tags else []
            
            # Remove large binary payloads to keep response lightweight
            has_image = bool(flat_card.get("image_data"))
            flat_card["has_image_data"] = has_image
            if has_image:
                flat_card.pop('image_data', None)
            if 'generated_image' in flat_card and isinstance(flat_card['generated_image'], dict):
                flat_card['generated_image'].pop('data', None)
            
            result.append(flat_card)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

@router.get("/cards/curation/{profile_id}", response_model=List[Dict[str, Any]])
def get_cards_for_curation(profile_id: str, db: Session = Depends(get_db)):
    """Target endpoint returning FLAT objects."""
    try:
        query = db.query(ApprovedCard)
        cards = query.filter(ApprovedCard.profile_id == profile_id)\
                     .order_by(ApprovedCard.id.desc()).all()  # Order by ID descending (newest first)
        
        if not cards:
            simple_name = profile_id.split('(')[0].strip()
            if simple_name:
                cards = query.filter(ApprovedCard.profile_id.ilike(f"%{simple_name}%"))\
                             .order_by(ApprovedCard.id.desc()).all()

        return [format_card_flat(c) for c in cards]
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

@router.put("/cards/{card_id}/approve")
def approve_card(card_id: str, db: Session = Depends(get_db)):
    """Approve a card by ID from database."""
    try:
        # Try to parse as integer first (database card ID)
        try:
            card_id_int = int(card_id)
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id_int).first()
        except ValueError:
            # If not an integer, treat as string
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id).first()
        
        if not card:
            raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")
        
        card.status = "approved"
        if not card.approved_at:
            card.approved_at = datetime.utcnow()
        
        db.commit()
        db.refresh(card)
        return {"message": "Card approved", "card": format_card_flat(card)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error approving card: {str(e)}")

@router.put("/cards/{card_id}")
def update_card(card_id: str, request: UpdateCardRequest, db: Session = Depends(get_db)):
    """Update a card by ID (supports both integer and UUID string IDs)."""
    try:
        # Try to parse as integer first
        try:
            card_id_int = int(card_id)
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id_int).first()
        except ValueError:
            # If not an integer, treat as string
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id).first()
        
        if not card:
            raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")
        
        card.status = request.status
        if request.status == "approved" and not card.approved_at:
            card.approved_at = datetime.utcnow()

        # Pack flat fields from UI back into the content blob
        current_content = safe_parse_content(card.content)
        if request.text_field is not None:
            current_content["text_field"] = request.text_field
        elif request.front is not None:
            current_content["text_field"] = request.front
        if request.extra_field is not None:
            current_content["extra_field"] = request.extra_field
        elif request.back is not None:
            current_content["extra_field"] = request.back
        if request.tags is not None:
            current_content["tags"] = request.tags
        if request.content:
            # Allow full content blob override if provided
            current_content.update(request.content)
        card.content = json.dumps(current_content)

        db.commit()
        db.refresh(card)
        # Return flat structure
        return format_card_flat(card)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating card: {str(e)}")

@router.delete("/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db)):
    """Delete a card by ID (supports both integer and UUID string IDs)."""
    try:
        # Try to parse as integer first
        try:
            card_id_int = int(card_id)
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id_int).first()
        except ValueError:
            # If not an integer, treat as string
            card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id).first()
        
        if not card:
            raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")
        db.delete(card)
        db.commit()
        return {"message": "Deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting card: {str(e)}")

@router.post("/cards/{card_id}/image")
async def generate_card_image(card_id: int, request: ImageGenerationRequest, db: Session = Depends(get_db)):
    if not _genai_model:
         raise HTTPException(status_code=503, detail="Model missing")

    card = db.query(ApprovedCard).filter(ApprovedCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    try:
        content_dict = safe_parse_content(card.content)
        
        text_to_draw = content_dict.get("text_field", "") or content_dict.get("front", "")
        clean_text = re.sub(r'\[\[c\d+::(.*?)(::.*?)?\]\]', r'\1', text_to_draw)
        
        prompt = request.prompt or f"Simple illustration: {clean_text}"
        _genai_model.generate_content(prompt)
        
        image_html = f'<img src="https://via.placeholder.com/300?text=AI+Image" alt="Generated">'
        
        if request.location == "before":
            content_dict["text_field"] = f"{image_html}<br>{content_dict.get('text_field', '')}"
        else:
            content_dict["extra_field"] = f"{content_dict.get('extra_field', '')}<br>{image_html}"
            
        card.content = json.dumps(content_dict)
        db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
