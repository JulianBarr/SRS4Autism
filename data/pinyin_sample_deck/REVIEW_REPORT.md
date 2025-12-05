# Pinyin Note Template Review Report

## Current Status

### Element Note Type
- **Fields:** Element, ExampleChar, Picture, Tone1, Tone2, Tone3, Tone4, _Remarks, _KG_Map
- **Issues:**
  1. ✅ Tone fields should use proper tone marks (ā á ǎ à) instead of (a1 a2 a3 a4)
  2. ⚠️  Need audio playback sequence: a1 a1 a2 a3 a4 a
  3. ⚠️  Need replay button
  4. ⚠️  Teaching cards should appear less frequently (Anki scheduling)

### Syllable Note Type
- **Fields:** ElementToLearn, Syllable, WordPinyin, WordHanzi, WordPicture, _Remarks, _KG_Map
- **Cards:** Should have 5 cards
  1. ⚠️  Card 0 (Element Card): Teaching card with mo1 a1 ma1 sequence
  2. ⚠️  Card 1 (Word to Pinyin): Teaching card with audio sequence
  3. ⚠️  Card 2 (MCQ Recent): Clickable, plays bell.wav on correct
  4. ⚠️  Card 3 (MCQ Tone): Same as MCQ Recent
  5. ⚠️  Card 4 (MCQ Confusor): Same as MCQ Recent
  6. ⚠️  Card 5 (Pinyin to Word): MCQ in reverse direction

## Sample Deck

### Element: "a"
- Element: a
- ExampleChar: 啊
- Picture: ahh.png
- Tone1: ā (proper tone mark)
- Tone2: á
- Tone3: ǎ
- Tone4: à

### Syllable: "ma1" (mā)
- ElementToLearn: a
- Syllable: mā (proper tone mark)
- WordHanzi: 妈妈
- WordPinyin: mā mā
- WordPicture: mommy.png

## Next Steps

1. Review the generated template files
2. Update Anki note types with new templates
3. Generate TTS audio files for:
   - Element "a": a1.mp3, a2.mp3, a3.mp3, a4.mp3, a.mp3
   - Syllable "ma1": mo1.mp3, mā.mp3
   - Word: mā mā.mp3
   - Bell sound: bell.wav
4. Import sample notes to Anki
5. Test all card types

## Audio Files Needed

### For Element "a":
- a1.mp3 (ā)
- a2.mp3 (á)
- a3.mp3 (ǎ)
- a4.mp3 (à)
- a.mp3 (neutral tone)

### For Syllable "ma1":
- mo1.mp3 (摸)
- mā.mp3 (妈)
- mā mā.mp3 (妈妈)
- bell.wav (success sound)

## Template Files Generated

- CUMA_PINYIN_ELEMENT_TEMPLATE.txt
- CUMA_PINYIN_SYLLABLE_TEMPLATE.txt
- sample_notes.json
