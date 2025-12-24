# Edge-TTS Tone Issue - Final Analysis

## Problem Confirmed

Even with SSML phoneme tags using `alphabet="pinyin"`, edge-tts is **not generating correct tones** for standalone pinyin characters (ā, á, ǎ, à).

### Evidence:
- ✅ Files are generated (different sizes: 28-30KB)
- ✅ Files have different content (different MD5 hashes)
- ❌ **But tones sound the same** (only slight pitch differences, not proper tone contours)

### Root Cause:
Edge-tts may **not support** the `alphabet="pinyin"` attribute in SSML phoneme tags, or it's being ignored. The TTS engine is likely:
1. Ignoring the phoneme tag
2. Reading the Unicode character (ā, á, ǎ, à) but not applying proper tone contours
3. Only applying slight pitch variations instead of proper Chinese tones

## Why This Happens

For standalone pinyin elements like "a" with different tones:
- There are **no separate Chinese characters** for "a" with tones 2, 3, 4
- The character 啊 (ā) is primarily tone 1
- Edge-tts doesn't have context to determine the correct tone
- SSML phoneme tags with "pinyin" alphabet may not be supported

## Solutions

### Option 1: Manual Recording (Recommended)
**Best quality and accuracy**
- Record audio files manually with a native Chinese speaker
- Ensure proper tone contours for each tone
- Files: `a1.mp3`, `a2.mp3`, `a3.mp3`, `a4.mp3`, `a.mp3`

### Option 2: Use Different TTS Engine
Try TTS engines that better support pinyin tones:
- **Baidu TTS** (if available)
- **Azure Cognitive Services** (direct API, not edge-tts)
- **Google Cloud TTS** with proper SSML (may work better than edge-tts)

### Option 3: Use Words in Context
Instead of standalone "a", use words that contain "a" with different tones:
- Tone 1: 啊 (ā) - "ah"
- Tone 2: 啊 (in some contexts) - but this is unreliable
- Tone 3: 啊 (in some contexts) - but this is unreliable  
- Tone 4: 啊 (in some contexts) - but this is unreliable

**Problem**: There aren't good standalone words for "a" tones 2, 3, 4.

### Option 4: Accept Limitation
- Use the generated files (they're different, just not perfect tones)
- Add visual/contextual cues in the Anki cards
- Supplement with manual recordings later

## Current Status

- ✅ Script generates files with SSML
- ✅ Files are different (different hashes)
- ❌ Tones are not correct (sound similar)
- ⚠️  Edge-tts limitation for standalone pinyin tones

## Recommendation

**Use manual recording** for the element "a" tones (a1, a2, a3, a4, a). This is the most reliable way to ensure correct pronunciation for teaching purposes.

For syllables (mo1, mā, mā mā), the current approach works because we use Chinese characters (摸, 妈, 妈妈) which edge-tts handles correctly.










