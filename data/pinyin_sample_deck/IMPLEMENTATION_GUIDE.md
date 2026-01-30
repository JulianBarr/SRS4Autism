# Pinyin Template Implementation Guide

## Summary

This guide provides step-by-step instructions to implement the required changes to pinyin note templates based on `Pinyin Review.md`.

## Current Status

✅ **Database Updated**: Tone marks converted from "a1" format to "ā" format
✅ **Sample Notes Generated**: Element "a" and syllable "ma1" ready
⚠️  **Templates Need Update**: Anki templates need to be manually updated
⚠️  **Audio Files Needed**: TTS generation required

---

## Step 1: Update Database (DONE)

The script `update_pinyin_tone_marks.py` has been run to convert:
- Element notes: Tone1-Tone4 from "a1" to "ā" format
- Syllable notes: Syllable from "ma1" to "mā" format

---

## Step 2: Generate Audio Files

### Option A: Use Google Cloud TTS (Recommended)

```bash
python3 scripts/knowledge_graph/generate_pinyin_audio.py
```

**Required audio files:**
- Element "a": `a1.mp3`, `a2.mp3`, `a3.mp3`, `a4.mp3`, `a.mp3`
- Syllable "ma1": `mo1.mp3`, `mā.mp3`, `mā mā.mp3`
- System: `bell.wav`

### Option B: Manual TTS Generation

If you prefer to generate TTS yourself, you'll need:
1. Chinese TTS service (Google Cloud, Baidu, etc.)
2. Generate audio for each text above
3. Save files to Anki's media folder

**Texts to generate:**
- 啊 (for a1.mp3 - tone 1)
- 啊 (for a2.mp3 - tone 2) 
- 啊 (for a3.mp3 - tone 3)
- 啊 (for a4.mp3 - tone 4)
- 啊 (for a.mp3 - neutral)
- 摸 (for mo1.mp3)
- 妈 (for mā.mp3)
- 妈妈 (for mā mā.mp3)

---

## Step 3: Update Anki Templates

### Element Note Template Updates

1. **Open Anki** → Tools → Manage Note Types
2. **Select "CUMA - Pinyin Element"**
3. **Update Front Template:**

```html
<div class="pinyin-element-card">
  <div class="element-display">{{Element}}</div>
  {{#ExampleChar}}
  <div class="example-char">{{ExampleChar}}</div>
  {{/ExampleChar}}
  
  {{#Picture}}
  <div class="picture">{{Picture}}</div>
  {{/Picture}}
  
  <div class="tones-display">
    <div class="tone-item">
      <span class="tone-mark">{{Tone1}}</span>
      <span class="tone-number">1</span>
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone2}}</span>
      <span class="tone-number">2</span>
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone3}}</span>
      <span class="tone-number">3</span>
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone4}}</span>
      <span class="tone-number">4</span>
    </div>
  </div>
  
  <div class="audio-controls">
    <button onclick="playAudio()" class="play-btn">▶️ 播放</button>
    <button onclick="playAudio()" class="replay-btn">🔄 重播</button>
  </div>
  
  <div style="display: none;" id="audio-seq">
    [sound:{{Element}}1.mp3] [sound:{{Element}}1.mp3] [sound:{{Element}}2.mp3] [sound:{{Element}}3.mp3] [sound:{{Element}}4.mp3] [sound:{{Element}}.mp3]
  </div>
</div>

<script>
function playAudio() {
  const audioDiv = document.getElementById('audio-seq');
  if (audioDiv) {
    audioDiv.style.display = 'block';
    setTimeout(() => audioDiv.style.display = 'none', 100);
  }
}
</script>
```

4. **Update CSS** (see full CSS in template files)

### Syllable Note Template Updates

1. **Select "CUMA - Pinyin Syllable"**
2. **Add Card 0: Element Card** (currently missing)
3. **Update Cards 1-5** with clickable MCQ and bell sound

See `CUMA_PINYIN_SYLLABLE_TEMPLATE.txt` for complete templates.

---

## Step 4: Create Sample Deck

The sample deck has been created in Anki:
- **Deck Name**: "拼音学习样本 (Pinyin Sample)"
- **Element Note**: "a" with proper tone marks
- **Syllable Note**: "ma1" (mā) with all 5 cards

---

## Files Generated

All files are in `/data/pinyin_sample_deck/`:

1. **CUMA_PINYIN_ELEMENT_TEMPLATE.txt** - Complete element template code
2. **CUMA_PINYIN_SYLLABLE_TEMPLATE.txt** - Complete syllable template code
3. **sample_notes.json** - Sample note data
4. **REVIEW_REPORT.md** - Detailed review report
5. **TEMPLATE_REVIEW.md** - Template comparison
6. **IMPLEMENTATION_GUIDE.md** - This file

---

## Next Steps

1. ✅ Database updated with tone marks
2. ⚠️  Generate TTS audio files (or let me know if you need help)
3. ⚠️  Update Anki templates manually (copy from template files)
4. ⚠️  Test all cards in Anki
5. ⚠️  Configure teaching card frequency in Anki settings

---

## TTS Generation Help

If you need help with TTS generation, I can:
- Help set up Google Cloud TTS credentials
- Create a script using a different TTS service
- Provide instructions for manual TTS generation

Let me know which option you prefer!

















