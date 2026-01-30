# Edge-TTS Troubleshooting Guide

## Current Issue

Edge-tts is failing with "No audio was received" error on this system. The script is correctly configured to use Unicode Pinyin (ā, á, ǎ, à), but the API is not responding.

## Script Status

✅ **Script is ready**: `generate_pinyin_audio.py` is properly configured:
- Uses Unicode Pinyin (ā, á, ǎ, à) directly
- No SSML tags
- No numbers (a1, a2)
- Chinese voice (zh-CN-*)
- Proper error handling

❌ **API Issue**: Edge-tts API is not responding (404 or network error)

## To Fix Edge-TTS

### Step 1: Test Basic Connectivity

```bash
# Test if edge-tts CLI works
python -m edge_tts --list-voices | grep zh-CN

# Test simple synthesis
python -m edge_tts --voice zh-CN-XiaoxiaoNeural --text "你好" --write-media test.mp3
```

### Step 2: If CLI Works But Script Doesn't

The script should work if CLI works. If CLI fails, it's a system issue.

### Step 3: Check Network/Proxy

```bash
# Check proxy settings
env | grep -i proxy

# If behind proxy, set:
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

# Then try again
python scripts/knowledge_graph/generate_pinyin_audio.py
```

### Step 4: Try Different Network

- Try from a different network (home vs office)
- Try without VPN
- Try with mobile hotspot

### Step 5: Alternative Solutions

If edge-tts continues to fail:

1. **Use Google Cloud TTS** (current fallback)
   - Script: `generate_pinyin_audio_google.py`
   - May need manual tone verification

2. **Manual Recording**
   - Record audio files with correct tones
   - Use a native Chinese speaker

3. **Online TTS Tools**
   - Use Google Translate, Baidu TTS, etc.
   - Download and save files

## Once Edge-TTS Works

The script will automatically:
1. Find a working Chinese voice
2. Generate audio with Unicode Pinyin (ā, á, ǎ, à)
3. Create all 8 audio files
4. You can then regenerate the .apkg file

## Verification

After generating, verify tones are correct:
- `a1.mp3` should sound like tone 1 (ā - high flat)
- `a2.mp3` should sound like tone 2 (á - rising)
- `a3.mp3` should sound like tone 3 (ǎ - dipping)
- `a4.mp3` should sound like tone 4 (à - falling)

If tones are wrong, the TTS engine didn't interpret Unicode Pinyin correctly.

















