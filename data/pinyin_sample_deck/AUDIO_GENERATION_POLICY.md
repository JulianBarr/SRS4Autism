# Pinyin Audio Generation Policy

## Current Approach

### Pinyin Element Notes
- **Audio Generation**: ❌ **SKIPPED**
- **Reason**: TTS cannot accurately generate tones for standalone pinyin elements (ā, á, ǎ, à)
- **Solution**: Caregiver will read these manually during learning sessions
- **Files**: `a1.mp3`, `a2.mp3`, `a3.mp3`, `a4.mp3`, `a.mp3` are **NOT generated**

### Pinyin Syllable Notes
- **Audio Generation**: ✅ **USING TTS**
- **Method**: Edge-tts with Chinese characters
- **Reason**: TTS handles Chinese characters correctly
- **Files Generated**:
  - `mo1.mp3` - Generated from "摸" (Chinese character)
  - `mā.mp3` - Generated from "妈" (Chinese character)
  - `mā mā.mp3` - Generated from "妈妈" (Chinese characters)

## Template Behavior

The Anki templates still include audio tags for element notes (e.g., `[sound:a1.mp3]`), but:
- These files are **not included** in the `.apkg` file
- If the files don't exist, Anki will simply skip them (no error)
- The caregiver can read the tones instead
- This is the intended behavior

## Scripts

- **`generate_pinyin_audio.py`**: Skips element audio, generates syllable audio
- **`generate_pinyin_apkg.py`**: Only includes syllable audio files in the package

## Future Considerations

If accurate element audio is needed later:
1. Manual recording by native Chinese speaker (recommended)
2. Use a different TTS engine that better supports pinyin tones
3. Use words/context that naturally have those tones










