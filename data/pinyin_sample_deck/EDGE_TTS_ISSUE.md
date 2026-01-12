# Edge-TTS Issue and Workaround

## Problem

Edge-tts is failing with "No audio was received" error, even though:
- ✅ edge-tts is installed (version 7.2.3)
- ✅ API endpoint is reachable
- ✅ Voices can be listed
- ❌ Audio synthesis fails for all voices

## Error Details

```
edge_tts.exceptions.NoAudioReceived: No audio was received. Please verify that your parameters are correct.
```

This occurs even with:
- Simple test: `edge-tts --voice zh-CN-XiaoxiaoNeural --text "你好"`
- All Chinese voices tested
- Both Python API and CLI

## Possible Causes

1. **Network/Proxy Issue**: Edge-tts API may be blocked or require proxy configuration
2. **API Endpoint Change**: Microsoft may have changed the API endpoint
3. **Rate Limiting**: Too many requests may be blocked
4. **Authentication Issue**: Some edge-tts versions may require authentication
5. **Regional Blocking**: API may not be accessible from this region

## Solutions

### Option 1: Check Network/Proxy

```bash
# Test if you can reach the API
curl -I "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4"

# If behind a proxy, set environment variables:
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

### Option 2: Use Alternative TTS Service

Since edge-tts isn't working, you can:

1. **Use Google Cloud TTS with Chinese characters** (current workaround)
   - Script: `generate_pinyin_audio_google.py`
   - Uses Chinese characters for tones (may need manual verification)

2. **Use Baidu TTS** (if available)
   - Better support for Chinese/Pinyin

3. **Manual Recording**
   - Record the audio files manually
   - Use a native Chinese speaker

### Option 3: Try Different edge-tts Version

```bash
pip install edge-tts==6.1.9  # Try older version
# or
pip install --upgrade edge-tts  # Try latest
```

### Option 4: Use Online TTS Tools

1. Use online TTS services (e.g., Google Translate TTS, Baidu TTS)
2. Download the audio files
3. Place them in `media/audio/pinyin/`

## Current Status

- ✅ Script updated to use edge-tts with Unicode Pinyin (ā, á, ǎ, à)
- ✅ Proper error handling and diagnostics
- ❌ edge-tts API not responding (system/network issue)
- ⚠️  Using Google Cloud TTS as fallback (may not have correct tones)

## Next Steps

1. **Check your network/proxy settings**
2. **Try running edge-tts from a different network**
3. **Contact edge-tts maintainers** if issue persists
4. **Use manual recording** if TTS continues to fail

## Test Command

To test if edge-tts works on your system:

```bash
python -m edge_tts --voice zh-CN-XiaoxiaoNeural --text "你好" --write-media test.mp3
```

If this fails, edge-tts has a system-level issue that needs to be resolved first.











