from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import json
import sys
from datetime import datetime
from pathlib import Path

# Adjust path to include backend root if needed
# This matches main.py's behavior
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from database.db import get_db
from database.services import ProfileService
from app.core.config import PROFILES_FILE, ANKI_PROFILES_FILE, PROMPT_TEMPLATES_FILE
from utils import generate_slug

router = APIRouter()

# ============================================================================
# Data Models
# ============================================================================

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

# ============================================================================
# Helper Functions
# ============================================================================

def load_json_file(file_path: Path, default: Any = None):
    """Load JSON data from file, return default if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else []

def save_json_file(file_path: Path, data: Any):
    """Save data to JSON file"""
    # Ensure directory exists
    if hasattr(file_path, 'parent'):
        os.makedirs(file_path.parent, exist_ok=True)
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================================
# Profile Routes
# ============================================================================

@router.get("/profiles", response_model=List[ChildProfile])
async def get_profiles(db: Session = Depends(get_db)):
    """Get all profiles from database"""
    profiles = ProfileService.get_all(db)
    return [ProfileService.profile_to_dict(db, p) for p in profiles]

@router.post("/profiles", response_model=ChildProfile)
async def create_profile(profile: ChildProfile, db: Session = Depends(get_db)):
    """Create new profile in database"""
    
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

@router.get("/profiles/{profile_id}", response_model=ChildProfile)
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

@router.put("/profiles/{profile_id}", response_model=ChildProfile)
async def update_profile(profile_id: str, updated_profile: ChildProfile, db: Session = Depends(get_db)):
    """Update profile in database"""
    print(f"\n📝 Updating profile: {profile_id}")
    print(f"   Received data: name={updated_profile.name}, mental_age={updated_profile.mental_age}")
    
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
        print(f"   ❌ Profile not found: {profile_id}")
        raise HTTPException(status_code=404, detail="Profile not found")
    
    print(f"   ✅ Found profile: {profile.name} (id: {profile_id})")
    
    # Prepare data for database
    profile_data = updated_profile.dict()
    
    # Remove id field - we don't update the ID, and it might be None which causes constraint errors
    profile_data.pop('id', None)
    
    # Split mastered words into lists
    mastered_words_str = profile_data.pop('mastered_words', '') or ''
    mastered_english_str = profile_data.pop('mastered_english_words', '') or ''
    mastered_grammar_str = profile_data.pop('mastered_grammar', '') or ''
    
    profile_data['mastered_words_list'] = [w.strip() for w in mastered_words_str.split(', ') if w.strip()]
    profile_data['mastered_english_words_list'] = [w.strip() for w in mastered_english_str.split(', ') if w.strip()]
    profile_data['mastered_grammar_list'] = [g.strip() for g in mastered_grammar_str.split(',') if g.strip()]
    
    updated = ProfileService.update(db, profile_id, profile_data)
    print(f"   ✅ Profile updated successfully")
    return ProfileService.profile_to_dict(db, updated)

@router.delete("/profiles/{profile_id}")
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

# ============================================================================
# Anki Profile Routes
# ============================================================================

@router.get("/anki-profiles", response_model=List[AnkiProfile])
async def get_anki_profiles():
    profiles = load_json_file(ANKI_PROFILES_FILE, [])
    return profiles

@router.post("/anki-profiles", response_model=AnkiProfile)
async def create_anki_profile(profile: AnkiProfile):
    profiles = load_json_file(ANKI_PROFILES_FILE, [])
    profiles.append(profile.dict())
    save_json_file(ANKI_PROFILES_FILE, profiles)
    return profile

# ============================================================================
# Template Routes
# ============================================================================

@router.get("/templates", response_model=List[PromptTemplate])
async def get_templates():
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    return templates

@router.post("/templates", response_model=PromptTemplate)
async def create_template(template: PromptTemplate):
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    templates.append(template.dict())
    save_json_file(PROMPT_TEMPLATES_FILE, templates)
    return template

@router.put("/templates/{template_id}", response_model=PromptTemplate)
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

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
    initial_count = len(templates)
    templates = [t for t in templates if t.get("id") != template_id]
    
    if len(templates) == initial_count:
        raise HTTPException(status_code=404, detail="Template not found")
    
    save_json_file(PROMPT_TEMPLATES_FILE, templates)
    return {"message": "Template deleted successfully"}


