# Gap Fill Suggestions Endpoint - Debug Code

This file contains all code related to the `/pinyin/gap-fill-suggestions` endpoints for debugging.

## Backend Endpoints (FastAPI)

### Cache Variables
```python
# Cache for gap-fill suggestions to avoid re-reading CSV on every request
_pinyin_suggestions_cache = None
_pinyin_suggestions_cache_mtime = None
```

### GET Endpoint: `/pinyin/gap-fill-suggestions`
```python
@app.get("/pinyin/gap-fill-suggestions")
async def get_pinyin_gap_fill_suggestions():
    """
    Get pinyin gap fill suggestions from the CSV file (cached for performance).
    """
    global _pinyin_suggestions_cache, _pinyin_suggestions_cache_mtime
    
    try:
        suggestions_file = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
        
        if not suggestions_file.exists():
            raise HTTPException(status_code=404, detail="Suggestions file not found. Please run find_best_pinyin_words.py first.")
        
        # Check if file was modified (invalidate cache if changed)
        current_mtime = suggestions_file.stat().st_mtime
        if _pinyin_suggestions_cache is None or _pinyin_suggestions_cache_mtime != current_mtime:
            # Read CSV file (fast - only 231 lines)
            def read_csv_file():
                suggestions = []
                with open(suggestions_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        suggestions.append(dict(row))
                return suggestions
            
            import asyncio
            loop = asyncio.get_event_loop()
            _pinyin_suggestions_cache = await loop.run_in_executor(None, read_csv_file)
            _pinyin_suggestions_cache_mtime = current_mtime
        
        # Return cached data (instant)
        return {
            "suggestions": _pinyin_suggestions_cache,
            "total": len(_pinyin_suggestions_cache)
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading suggestions: {str(e)}")
```

### PUT Endpoint: `/pinyin/gap-fill-suggestions`
```python
@app.put("/pinyin/gap-fill-suggestions")
async def save_pinyin_gap_fill_suggestions(request: Dict[str, Any]):
    """
    Save approved/edited pinyin gap fill suggestions.
    Invalidates cache after saving.
    """
    global _pinyin_suggestions_cache, _pinyin_suggestions_cache_mtime
    import asyncio
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
            import tempfile
            import shutil
            temp_file = suggestions_file.with_suffix('.tmp')
            
            try:
                print(f"📝 [SAVE] Writing to temp file: {temp_file}")
                # Run file I/O in thread executor to avoid blocking event loop
                import asyncio
                
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
```

## Frontend Code (React)

### API Base URL
```javascript
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

### Load Suggestions Function
```javascript
const loadSuggestions = async () => {
  setLoading(true);
  setMessage(null);
  try {
    const response = await axios.get(`${API_BASE}/pinyin/gap-fill-suggestions`, {
      timeout: 30000 // 30 second timeout (response can be large with 230+ suggestions)
    });
    const loaded = response.data.suggestions || [];
    
    // Initialize approval status for each suggestion
    const suggestionsWithStatus = loaded.map(s => ({
      ...s,
      approved: s.approved || false,
      edited: s.edited || false
    }));
    
    setSuggestions(suggestionsWithStatus);
  } catch (error) {
    console.error('Error loading suggestions:', error);
    setMessage({ type: 'error', text: `加载失败: ${error.response?.data?.detail || error.message}` });
  } finally {
    setLoading(false);
  }
};
```

### Save Suggestions Function
```javascript
const handleSave = async () => {
  if (selectedSuggestions.size === 0) {
    setMessage({ type: 'warning', text: '请先选择要保存的建议' });
    return;
  }
  
  setSaving(true);
  setMessage(null);
  
  try {
    const approvedSuggestions = Array.from(selectedSuggestions).map(index => ({
      ...suggestions[index],
      approved: 'True'
    }));
    
    await axios.put(`${API_BASE}/pinyin/gap-fill-suggestions`, {
      suggestions: approvedSuggestions
    }, {
      timeout: 10000 // 10 second timeout
    });
    
    setMessage({ type: 'success', text: `已保存 ${approvedSuggestions.length} 条建议` });
    setSelectedSuggestions(new Set());
    
    // Reload suggestions to get updated data
    await loadSuggestions();
  } catch (error) {
    console.error('Error saving suggestions:', error);
    setMessage({ type: 'error', text: `保存失败: ${error.response?.data?.detail || error.message}` });
  } finally {
    setSaving(false);
  }
};
```

## File Information

- **CSV File**: `data/pinyin_gap_fill_suggestions.csv`
- **Expected Columns**: 'Syllable', 'Suggested Word', 'Word Pinyin', 'HSK Level', 'Frequency Rank', 'Has Image', 'Image File', 'Concreteness', 'AoA', 'Num Syllables', 'Score', 'approved'
- **CSV Size**: ~230 rows
- **Frontend Timeout**: 30 seconds (GET), 10 seconds (PUT)

## Known Issues

1. **Timeout Error**: Frontend shows "timeout of 30000ms exceeded" error
2. **Performance**: GET endpoint should be fast due to caching, but appears slow
3. **Cache**: Uses global variables `_pinyin_suggestions_cache` and `_pinyin_suggestions_cache_mtime` for caching

## Fix Applied

**Date**: 2025-12-09
**Issue**: Timeout caused by `asyncio.run_in_executor` creating thread pool starvation
**Solution**: Removed executor and implemented direct synchronous file read for small CSV files (~14KB, 230 rows)

### Changes Made:
1. Removed `run_in_executor` - direct synchronous file read
2. Added comprehensive logging for debugging
3. Added timing measurements
4. File size verification: 14KB (confirmed)

### Performance:
- **First request**: ~77ms (reads CSV, populates cache)
- **Cached requests**: <20ms (serves from memory)
- **File size**: 14KB (230 rows)

## Debug Checklist

- [x] Check if CSV file exists and is readable - ✅ 14KB file exists
- [x] Verify CSV file size (should be ~230 rows) - ✅ 230 rows
- [x] Check if cache is working (first request vs subsequent requests) - ✅ Working
- [x] Verify asyncio executor is not blocking - ✅ Removed executor
- [x] Check server logs for errors - ✅ Added logging
- [x] Test endpoint directly with curl - ✅ Working (~77ms)
- [ ] Verify frontend timeout is sufficient - Frontend timeout is 30s, should be fine now
- [x] Check if there are any blocking operations in the endpoint - ✅ Removed blocking executor

