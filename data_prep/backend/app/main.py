"""
Data Preparation Backend - Separate from Curious Mario main application.

Handles:
- Pinyin gap fill suggestions management
- English vocabulary suggestions
- Image extraction and management
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any
import csv
import json
import time
from pathlib import Path

# Project root (SRS4Autism directory, parent of data_prep)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

app = FastAPI(title="Data Preparation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],  # Different port for data prep frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for pinyin gap fill suggestions
_pinyin_suggestions_cache = None
_pinyin_suggestions_cache_mtime = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Data Preparation API is running"}


@app.get("/pinyin/gap-fill-suggestions")
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
        import traceback
        print(f"🔥 [GET] Critical Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading suggestions: {str(e)}")


@app.put("/pinyin/gap-fill-suggestions")
async def save_pinyin_gap_fill_suggestions(request: Dict[str, Any]):
    """
    Save approved/edited pinyin gap fill suggestions.
    Invalidates cache after saving.
    """
    global _pinyin_suggestions_cache, _pinyin_suggestions_cache_mtime
    import asyncio
    import shutil
    import tempfile
    
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
                import traceback
                traceback.print_exc()
                # Continue with empty dict if read fails
        
        # Update with approved/edited suggestions
        print(f"💾 [SAVE] Updating {len(approved_suggestions)} suggestions...")
        for suggestion in approved_suggestions:
            syllable = suggestion.get('Syllable')
            if syllable:
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
            temp_file = suggestions_file.with_suffix('.tmp')
            
            try:
                print(f"📝 [SAVE] Writing to temp file: {temp_file}")
                
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving suggestions: {str(e)}")


@app.get("/pinyin/english-vocab-suggestions")
async def get_english_vocab_suggestions_for_pending():
    """
    Get English vocabulary-based suggestions for pending pinyin syllables.
    Loads pre-computed matches from JSON file (generated by match_pending_syllables_english_vocab.py).
    Returns up to 3 suggestions per syllable with radio button options.
    """
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


# Mount static files for serving images
# Images are stored in media/ relative to project root
media_dir = PROJECT_ROOT / "media"
if media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Different port from main app

