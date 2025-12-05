# Pinyin Note Template Review

## Current Implementation vs Requirements

### Element Note Type: "CUMA - Pinyin Element"

#### Current Fields:
- Element, ExampleChar, Picture, Tone1, Tone2, Tone3, Tone4, _Remarks, _KG_Map

#### Current Template Issues:
1. ❌ **Tone fields use numbers (a1, a2, a3, a4) instead of proper tone marks (ā, á, ǎ, à)**
   - Current: `{{Tone1}}` displays "a1"
   - Required: Should display "ā" (proper tone mark)

2. ❌ **No audio playback sequence**
   - Required: Should play "a1 a1 a2 a3 a4 a" sequence
   - Need: Play button and replay button

3. ❌ **No replay functionality**
   - Required: Replay button to repeat audio sequence

4. ⚠️  **Teaching card frequency**
   - Note: This is handled by Anki's scheduling algorithm, not the template
   - Can be configured via Anki's card settings (new card interval, ease factor)

#### Required Changes:
1. Update database to store proper tone marks in Tone1-Tone4 fields
2. Add audio playback buttons to template
3. Add audio sequence: `[sound:a1.mp3] [sound:a1.mp3] [sound:a2.mp3] [sound:a3.mp3] [sound:a4.mp3] [sound:a.mp3]`

---

### Syllable Note Type: "CUMA - Pinyin Syllable"

#### Current Fields:
- ElementToLearn, Syllable, WordPinyin, WordHanzi, WordPicture, _Remarks, _KG_Map

#### Current Cards (5 cards exist):
1. Word to Pinyin
2. MCQ Recent
3. MCQ Tone
4. MCQ Confusor
5. Pinyin to Word

#### Issues per Card:

##### Card 0: Element Card (MISSING - should be first card)
- ❌ **Not implemented**
- Required: Teaching card that plays "mo1 a1 ma1" (摸啊妈), then pause, then "ma1 ma1" (妈妈)
- Required: Sound toggle option
- Required: Display element "a" in a different card context

##### Card 1: Word to Pinyin
- ⚠️  **Needs audio sequence**
  - Required: Play "mo1 a1 ma1" then pause, then "ma1 ma1"
  - Required: Sound toggle option

##### Card 2: MCQ Recent
- ❌ **Not clickable**
  - Required: Clickable buttons
  - Required: Play bell.wav when correct answer is selected
- ❌ **Back card options don't match front**
  - Required: Same options, same order, only correct answer highlighted

##### Card 3: MCQ Tone
- ❌ **Same issues as MCQ Recent**
  - Required: Clickable, bell sound, matching back card

##### Card 4: MCQ Confusor
- ❌ **Same issues as MCQ Recent**
  - Required: Clickable, bell sound, matching back card

##### Card 5: Pinyin to Word
- ❌ **Not MCQ format**
  - Required: Should be MCQ in reverse direction (pinyin → word)
  - Required: Clickable options, bell sound

---

## Sample Deck Data

### Element "a"
```json
{
  "Element": "a",
  "ExampleChar": "啊",
  "Picture": "<img src=\"ahh.png\">",
  "Tone1": "ā",  // Changed from "a1"
  "Tone2": "á",  // Changed from "a2"
  "Tone3": "ǎ",  // Changed from "a3"
  "Tone4": "à",  // Changed from "a4"
  "_Remarks": "",
  "_KG_Map": "{\"0\": [{\"kp\": \"pinyin-element-a\", \"skill\": \"form_to_sound\", \"weight\": 1.0}]}"
}
```

### Syllable "ma1" (mā)
```json
{
  "ElementToLearn": "a",
  "Syllable": "mā",  // Changed from "ma1" - proper tone mark
  "WordPinyin": "mā mā",
  "WordHanzi": "妈妈",
  "WordPicture": "<img src=\"mommy.png\">",
  "_Remarks": "",
  "_KG_Map": "{\"0\": [{\"kp\": \"pinyin-syllable-ma1\", \"skill\": \"form_to_sound\", \"weight\": 1.0}], ...}"
}
```

---

## Required Audio Files

### Element "a":
- `a1.mp3` - Pronunciation of "ā" (tone 1)
- `a2.mp3` - Pronunciation of "á" (tone 2)
- `a3.mp3` - Pronunciation of "ǎ" (tone 3)
- `a4.mp3` - Pronunciation of "à" (tone 4)
- `a.mp3` - Pronunciation of "a" (neutral tone)

### Syllable "ma1":
- `mo1.mp3` - Pronunciation of "摸" (mo1)
- `mā.mp3` - Pronunciation of "妈" (mā)
- `mā mā.mp3` - Pronunciation of "妈妈" (mā mā)

### System:
- `bell.wav` - Success sound when MCQ answer is correct

---

## Action Items

1. ✅ **Update database fields** - Convert Tone1-Tone4 from "a1" format to "ā" format
2. ✅ **Update Element template** - Add audio playback and replay buttons
3. ✅ **Add Card 0 to Syllable** - Element teaching card
4. ✅ **Update Card 1** - Add audio sequence
5. ✅ **Update Cards 2-4** - Make clickable, add bell sound, fix back card
6. ✅ **Update Card 5** - Convert to MCQ format
7. ⚠️  **Generate TTS audio files** - Use generate_pinyin_audio.py script
8. ⚠️  **Test in Anki** - Verify all cards work correctly


