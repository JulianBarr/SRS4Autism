from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pathlib import Path
import csv
import time
import asyncio
import json
import re
import shutil
import traceback

from database.db import get_db_session
from database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final, parse_pinyin
from backend.app.utils.pinyin_utils import fix_iu_ui_tone_placement, get_word_knowledge, get_word_image_map
from ..core.config import PROJECT_ROOT

router = APIRouter()

# --- Pinyin Gap Fill Suggestions Admin Endpoints ---
# Cache for pinyin suggestions (global, will be invalidated on save)
_pinyin_suggestions_cache: Optional[List[Dict[str, Any]]] = None
_pinyin_suggestions_cache_mtime: Optional[float] = None

@router.get("/gap-fill-suggestions")
async def get_pinyin_gap_fill_suggestions():
    """
    Get pinyin gap fill suggestions.
    OPTIMIZED: Removed asyncio executor for simple file IO to prevent thread starvation.
    """
    global _pinyin_suggestions_cache, _pinyin_suggestions_cache_mtime
    
    t_start = time.time()
    try:
        suggestions_file = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
        print(f"🔍 [GET] Request received. Checking: {suggestions_file}")
        
        if not suggestions_file.exists():
            print(f"❌ [GET] File not found: {suggestions_file}")
            raise HTTPException(status_code=404, detail="Suggestions file not found. Please run find_best_pinyin_words.py first.")
        
        # Check file stats (blocking but fast)
        file_stats = suggestions_file.stat()
        current_mtime = file_stats.st_mtime
        file_size = file_stats.st_size
        
        print(f"📂 [GET] File found. Size: {file_size} bytes. Cache mtime: {_pinyin_suggestions_cache_mtime} vs Current: {current_mtime}")
        
        # Refresh cache if needed
        if _pinyin_suggestions_cache is None or _pinyin_suggestions_cache_mtime != current_mtime:
            print("🔄 [GET] Cache stale. Reading CSV synchronously...")
            
            # DIRECT READ (No Executor): Removes complexity and deadlock risk
            suggestions = []
            with open(suggestions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    suggestions.append(dict(row))
            
            _pinyin_suggestions_cache = suggestions
            _pinyin_suggestions_cache_mtime = current_mtime
            print(f"✅ [GET] CSV Read complete. Loaded {len(suggestions)} rows.")
        else:
            print("⚡ [GET] Serving from cache.")
        
        duration = (time.time() - t_start) * 1000
        print(f"🚀 [GET] Completed in {duration:.2f}ms")
        
        return {
            "suggestions": _pinyin_suggestions_cache,
            "total": len(_pinyin_suggestions_cache)
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading suggestions: {str(e)}")

@router.put("/gap-fill-suggestions")
async def save_pinyin_gap_fill_suggestions(request: Dict[str, Any]):
    """
    Save approved/edited pinyin gap fill suggestions.
    Invalidates cache after saving.
    """
    global _pinyin_suggestions_cache, _pinyin_suggestions_cache_mtime
    try:
        suggestions_file = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
        approved_suggestions = request.get("suggestions", [])
        
        if not approved_suggestions:
            return {"message": "No suggestions to save", "saved": 0}
        
        print(f"💾 [SAVE] Starting save of {len(approved_suggestions)} suggestions to CSV...")
        print(f"💾 [SAVE] File path: {suggestions_file}")
        
        # Load existing suggestions
        print(f"💾 [SAVE] Loading existing suggestions from CSV...")
        existing_suggestions = {}
        if suggestions_file.exists():
            try:
                with open(suggestions_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    row_count = 0
                    for row in reader:
                        syllable = row.get('Syllable')
                        if syllable:
                            existing_suggestions[syllable] = dict(row)
                            row_count += 1
                    print(f"💾 [SAVE] Loaded {row_count} existing suggestions")
            except Exception as e:
                print(f"⚠️ [SAVE] Error reading existing suggestions: {e}")
                traceback.print_exc()
                # Continue with empty dict if read fails
        
        # Normalize pinyin function
        def normalize_pinyin_for_save(pinyin: str, word: str = None) -> str:
            """
            Normalize pinyin to proper format with tone marks and space separation.
            If word is provided and pinyin is missing/incorrect, try to fetch from knowledge graph.
            """
            if not pinyin or not isinstance(pinyin, str):
                pinyin = ''
            
            pinyin = pinyin.strip()
            
            # If pinyin is empty or doesn't have proper tone marks, try to get from word
            if word and word.strip():
                word_stripped = word.strip()
                # Check if pinyin needs updating (empty or missing tone marks)
                has_tone_marks = any(mark in pinyin for mark in ['ā', 'á', 'ǎ', 'à', 'ē', 'é', 'ě', 'è', 
                                                                  'ī', 'í', 'ǐ', 'ì', 'ō', 'ó', 'ǒ', 'ò', 
                                                                  'ū', 'ú', 'ǔ', 'ù', 'ǖ', 'ǘ', 'ǚ', 'ǜ'])
                
                if not pinyin or not has_tone_marks:
                    try:
                        word_info = get_word_knowledge(word_stripped)
                        pronunciations = word_info.get("pronunciations", [])
                        if pronunciations and pronunciations[0]:
                            pinyin = pronunciations[0]
                            print(f"💾 [SAVE] Fetched pinyin for '{word_stripped}': '{pinyin}'")
                    except Exception as e:
                        print(f"⚠️ [SAVE] Could not fetch pinyin for '{word_stripped}': {e}")
            
            if not pinyin:
                return ''
            
            # Normalize: ensure space separation and proper formatting
            # Remove extra whitespace and normalize to single spaces
            pinyin = ' '.join(pinyin.split())
            
            # Apply fix_iu_ui_tone_placement to ensure correct tone placement
            try:
                pinyin = fix_iu_ui_tone_placement(pinyin)
            except Exception as e:
                print(f"⚠️ [SAVE] Could not apply tone placement fix: {e}")
            
            return pinyin
        
        # Update with approved/edited suggestions
        print(f"💾 [SAVE] Updating {len(approved_suggestions)} suggestions...")
        for suggestion in approved_suggestions:
            syllable = suggestion.get('Syllable')
            if syllable:
                # Auto-update pinyin from Chinese word
                word = suggestion.get('Suggested Word', '').strip()
                current_pinyin = suggestion.get('Word Pinyin', '').strip()
                
                # Always fetch pinyin from the Chinese word if word is provided
                if word and word != 'NONE':
                    try:
                        # Use the word-info endpoint logic which already handles normalization
                        word_stripped = word.strip()
                        word_info = get_word_knowledge(word_stripped)
                        pronunciations = word_info.get("pronunciations", [])
                        if pronunciations and pronunciations[0]:
                            fetched_pinyin = pronunciations[0]
                            
                            # Add spaces between syllables if missing
                            # Use a simple heuristic: split after tone marks when followed by initials
                            # This is a best-effort approach - for perfect results, use the frontend normalization
                            
                            if ' ' not in fetched_pinyin:
                                # First pass: handle ng endings (ang, eng, ong) - these are complete
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?ng)([bpmfdtnlgkhjqxzcsrzhchshyw][a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Second pass: handle n/r endings (but check it's not part of ng)
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?[nr])(?![g])([bpmfdtnlgkhjqxzcsrzhchshyw][a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Third pass: handle syllables ending with just tone mark (including compound finals like ao, ou, ai, ei)
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])([bpmfdtnlgkhjqxzcsrzhchshyw][a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Additional pass: handle cases where tone mark is in compound final (ao, ou, etc.)
                                # and is followed by initial + vowel with tone
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?[a-zü])([bpmfdtnlgkhjqxzcsrzhchshyw][a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Iterative pass: keep splitting until no more changes (handles multi-syllable words)
                                prev_pinyin = ''
                                while prev_pinyin != fetched_pinyin:
                                    prev_pinyin = fetched_pinyin
                                    # Split after any tone mark when followed by initial + vowel with tone
                                    fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?)([bpmfdtnlgkhjqxzcsrzhchshyw][a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Handle two-character initials (zh, ch, sh)
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?)\s*(zh|ch|sh)([a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1 \2\3', fetched_pinyin, flags=re.IGNORECASE)
                                
                                # Clean up: if we accidentally split "an" + "g" (should be "ang"), fix it
                                fetched_pinyin = re.sub(r'([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][a-zü]*?[nr])\s+([g])([a-zü]*?[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])', r'\1\2\3', fetched_pinyin, flags=re.IGNORECASE)
                            
                            # Normalize: ensure single spaces and trim
                            normalized_pinyin = ' '.join(fetched_pinyin.split()).strip()
                            
                            # Apply tone placement fix
                            try:
                                normalized_pinyin = fix_iu_ui_tone_placement(normalized_pinyin)
                            except:
                                pass
                            
                            suggestion['Word Pinyin'] = normalized_pinyin
                            print(f"💾 [SAVE] Auto-updated pinyin for '{syllable}' (word: '{word}'): '{current_pinyin}' → '{normalized_pinyin}'")
                        else:
                            print(f"⚠️ [SAVE] No pinyin found for word '{word}'")
                    except Exception as e:
                        print(f"⚠️ [SAVE] Could not fetch pinyin for word '{word}': {e}")
                        # If fetch fails, still try to normalize existing pinyin
                        if current_pinyin:
                            normalized_pinyin = normalize_pinyin_for_save(current_pinyin, None)
                            if normalized_pinyin:
                                suggestion['Word Pinyin'] = normalized_pinyin
                else:
                    # No word provided, just normalize existing pinyin
                    if current_pinyin:
                        normalized_pinyin = normalize_pinyin_for_save(current_pinyin, None)
                        if normalized_pinyin:
                            suggestion['Word Pinyin'] = normalized_pinyin
                
                # Ensure all fields are properly preserved, especially Image File
                image_file = suggestion.get('Image File', '') or ''
                if image_file and str(image_file).strip():
                    suggestion['Has Image'] = 'Yes'
                    suggestion['Image File'] = str(image_file).strip()
                else:
                    suggestion['Has Image'] = 'No'
                    suggestion['Image File'] = ''
                
                if syllable in existing_suggestions:
                    existing_suggestions[syllable].update(suggestion)
                else:
                    existing_suggestions[syllable] = suggestion
                
                print(f"💾 [SAVE] Updated syllable '{syllable}': Image File = '{suggestion.get('Image File', '')}', Has Image = '{suggestion.get('Has Image', '')}'")
        
        # Save back to CSV
        if existing_suggestions:
            fieldnames = ['Syllable', 'Suggested Word', 'Word Pinyin', 'HSK Level', 
                         'Frequency Rank', 'Has Image', 'Image File', 'Concreteness', 
                         'AoA', 'Num Syllables', 'Score', 'approved']
            
            # Write to a temporary file first, then rename (atomic operation)
            import tempfile
            import shutil
            temp_file = suggestions_file.with_suffix('.tmp')
            
            try:
                print(f"📝 [SAVE] Writing to temp file: {temp_file}")
                # Run file I/O in thread executor to avoid blocking event loop
                
                def write_csv_file():
                    with open(temp_file, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                        writer.writeheader()
                        print(f"📝 [SAVE] Writing {len(existing_suggestions)} suggestions...")
                        for suggestion in existing_suggestions.values():
                            writer.writerow(suggestion)
                    print(f"📝 [SAVE] Temp file written successfully")
                
                # Run in executor with timeout
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, write_csv_file),
                    timeout=30.0  # 30 second timeout for file write
                )
                
                print(f"📝 [SAVE] Renaming temp file to: {suggestions_file}")
                # Atomic rename - also run in executor
                await loop.run_in_executor(
                    None,
                    lambda: shutil.move(str(temp_file), str(suggestions_file))
                )
                print(f"✅ [SAVE] Successfully saved {len(existing_suggestions)} suggestions")
            except Exception as e:
                # Clean up temp file on error
                if temp_file.exists():
                    temp_file.unlink()
                raise
        
        # Invalidate cache so next GET request will reload fresh data
        _pinyin_suggestions_cache = None
        _pinyin_suggestions_cache_mtime = None
        
        return {
            "message": f"Saved {len(approved_suggestions)} suggestions",
            "saved": len(approved_suggestions)
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving suggestions: {str(e)}")

def generate_tone_variations(syllable: str) -> list:
    """
    Generate all 4 tone variations of a syllable.
    Example: 'zhen' -> ['zhēn', 'zhén', 'zhěn', 'zhèn']
    """
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone:
        return ['', '', '', '']
    
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(syllable_no_tone, tone)
        variations.append(toned)
    return variations


def generate_confusors(syllable: str) -> list:
    """
    Generate confusor syllables (similar syllables that might be confused).
    Based on pattern: change initial to b/p and vary tones.
    """
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone or len(syllable_no_tone) < 2:
        return ['', '', '']
    
    # Extract initial and final
    initial = syllable_no_tone[0]
    final = syllable_no_tone[1:] if len(syllable_no_tone) > 1 else ''
    
    # Generate confusors: b+final (tone 1), p+final (tone 2), original with different tone
    confusors = []
    if final:
        confusors.append(add_tone_to_final('b' + final, 1))
        confusors.append(add_tone_to_final('p' + final, 2))
    else:
        confusors.append(add_tone_to_final('ba', 1))
        confusors.append(add_tone_to_final('pa', 2))
    
    # Third confusor: original syllable with tone 3 or 4 (if original wasn't tone 3)
    original_toned = add_tone_to_final(syllable_no_tone, 3)
    if original_toned == syllable:
        original_toned = add_tone_to_final(syllable_no_tone, 4)
    confusors.append(original_toned)
    
    return confusors


def get_element_to_learn(syllable: str) -> str:
    """
    Determine ElementToLearn from syllable.
    For syllable cards, ElementToLearn is typically the final (韵母).
    Example: 'zhen' -> 'en' (final)
    """
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone:
        return ''
    
    parsed = parse_pinyin(syllable_no_tone)
    # ElementToLearn is the final (韵母)
    return parsed.get('final', '') or ''


def generate_word_audio(word: str) -> str:
    """
    Generate WordAudio field with plain filename: cm_tts_zh_<word>.mp3
    """
    if not word:
        return ''
    return f"cm_tts_zh_{word}.mp3"


@router.post("/apply-suggestions")
async def apply_pinyin_suggestions(request: Dict[str, Any]):
    """
    Apply approved pinyin suggestions to the pinyin deck database.
    Creates new PinyinSyllableNote entries for approved suggestions.
    """
    try:
        suggestions = request.get("suggestions", [])
        profile_id = request.get("profile_id") # Keeping for backward compatibility but not required
        
        if not suggestions:
            raise HTTPException(status_code=400, detail="No suggestions provided")
        
        created_count = 0
        updated_count = 0
        errors = []
        
        with get_db_session() as db:
            target_syllables = set()
            suggestion_data = []
            
            for suggestion in suggestions:
                syllable = suggestion.get('Syllable') or suggestion.get('syllable', '')
                word = suggestion.get('Suggested Word') or suggestion.get('word', '')
                
                if not syllable or not word or word == 'NONE':
                    continue
                
                target_syllables.add(syllable)
                suggestion_data.append({
                    'syllable': syllable,
                    'word': word,
                    'pinyin': suggestion.get('Word Pinyin') or suggestion.get('pinyin', ''),
                    'image_file': suggestion.get('Image File') or suggestion.get('image_file', ''),
                    'original': suggestion
                })
            
            existing_notes = []
            if target_syllables:
                existing_notes = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable.in_(target_syllables)
                ).all()
            
            exact_match_map = {
                (note.syllable, note.word): note 
                for note in existing_notes
            }
            
            syllable_fallback_map = {}
            for note in existing_notes:
                if note.syllable not in syllable_fallback_map:
                    syllable_fallback_map[note.syllable] = note
            
            max_order = db.query(PinyinSyllableNote.display_order).order_by(
                PinyinSyllableNote.display_order.desc()
            ).first()
            next_order = (max_order[0] if max_order else 0) + 1
            
            for suggestion_info in suggestion_data:
                try:
                    syllable = suggestion_info['syllable']
                    word = suggestion_info['word']
                    pinyin = suggestion_info['pinyin']
                    image_file = suggestion_info['image_file']
                    
                    existing = exact_match_map.get((syllable, word))
                    if not existing:
                        existing = syllable_fallback_map.get(syllable)
                    
                    concept = word
                    
                    if existing:
                        existing.word = word
                        existing.concept = concept
                        fields = json.loads(existing.fields) if existing.fields else {}
                        
                        if pinyin:
                            fields['WordPinyin'] = fix_iu_ui_tone_placement(pinyin)
                        fields['WordHanzi'] = word
                        
                        if image_file:
                            fields['WordPicture'] = f'<img src="{image_file}">'
                        
                        if not fields.get('ElementToLearn'):
                            fields['ElementToLearn'] = get_element_to_learn(syllable)
                        
                        if not fields.get('WordAudio'):
                            fields['WordAudio'] = generate_word_audio(word)
                        
                        existing.fields = json.dumps(fields, ensure_ascii=False)
                        updated_count += 1
                    else:
                        fixed_pinyin = fix_iu_ui_tone_placement(pinyin or '') if pinyin else ''
                        
                        element_to_learn = get_element_to_learn(syllable)
                        word_audio = generate_word_audio(word)
                        
                        word_picture = ''
                        if image_file:
                            word_picture = f'<img src="{image_file}">'
                        
                        fields = {
                            'ElementToLearn': element_to_learn,
                            'Syllable': syllable,
                            'WordPinyin': fixed_pinyin,
                            'WordHanzi': word,
                            'WordPicture': word_picture,
                            'WordAudio': word_audio,
                            '_Remarks': '',
                            '_KG_Map': '{}'
                        }
                        
                        new_note = PinyinSyllableNote(
                            note_id=f"syllable_{syllable}_{next_order}",
                            syllable=syllable,
                            word=word,
                            concept=concept,
                            fields=json.dumps(fields, ensure_ascii=False),
                            display_order=next_order
                        )
                        
                        db.add(new_note)
                        
                        exact_match_map[(syllable, word)] = new_note
                        if syllable not in syllable_fallback_map:
                            syllable_fallback_map[syllable] = new_note
                        
                        next_order += 1
                        created_count += 1
                
                except Exception as e:
                    syllable = suggestion_info.get('syllable', 'unknown')
                    errors.append(f"Error processing {syllable}: {str(e)}")
                    continue
        
        return {
            "message": f"Applied {len(suggestions)} suggestions ({created_count} created, {updated_count} updated)",
            "created": created_count,
            "updated": updated_count,
            "total": len(suggestions),
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error applying suggestions: {str(e)}")
