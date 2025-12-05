#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review pinyin note templates and generate sample deck.

This script:
1. Reviews current pinyin note templates
2. Generates sample deck with element "a" and syllable "ma1"
3. Creates proper templates according to Pinyin Review.md requirements
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from anki_integration.anki_connect import AnkiConnect
from scripts.knowledge_graph.pinyin_parser import add_tone_to_final, TONE_MARKS

PROJECT_ROOT = project_root
OUTPUT_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def convert_tone_number_to_mark(element: str, tone: int) -> str:
    """Convert element with tone number to tone mark (e.g., 'a1' -> 'ā')"""
    if tone < 1 or tone > 4:
        return element
    
    # Find the vowel to mark
    vowels_priority = ['a', 'o', 'e', 'i', 'u', 'ü', 'A', 'O', 'E', 'I', 'U', 'Ü']
    for vowel in vowels_priority:
        if vowel in element:
            mark = TONE_MARKS.get(vowel, [])[tone - 1]
            if mark:
                return element.replace(vowel, mark, 1)
    
    return element


def generate_audio_sequence(element: str) -> str:
    """
    Generate audio sequence for element card: a1 a1 a2 a3 a4 a
    Returns Anki audio tags
    """
    audio_tags = []
    # a1 a1 a2 a3 a4 a
    for tone in [1, 1, 2, 3, 4]:
        toned = convert_tone_number_to_mark(element, tone)
        audio_tags.append(f'[sound:{element}{tone}.mp3]')
    # Final a (no tone)
    audio_tags.append(f'[sound:{element}.mp3]')
    return ' '.join(audio_tags)


def generate_element_template_code() -> str:
    """Generate template code for Pinyin Element note type"""
    return """# CUMA - Pinyin Element Note Type
# Teaching card for pinyin elements (initials/finals)

## Fields (current):
Element, ExampleChar, Picture, Tone1, Tone2, Tone3, Tone4, _Remarks, _KG_Map

## Card Template:

### Front Template:
<div class="pinyin-element-card">
  <div class="element-display">
    <div class="main-element">{{Element}}</div>
    {{#ExampleChar}}
    <div class="example-char">{{ExampleChar}}</div>
    {{/ExampleChar}}
  </div>
  
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
    <button onclick="playAudioSequence()" class="play-btn">▶️ 播放</button>
    <button onclick="replayAudio()" class="replay-btn">🔄 重播</button>
  </div>
  
  <div id="audio-sequence" style="display: none;">
    [sound:{{Element}}1.mp3] [sound:{{Element}}1.mp3] [sound:{{Element}}2.mp3] [sound:{{Element}}3.mp3] [sound:{{Element}}4.mp3] [sound:{{Element}}.mp3]
  </div>
</div>

<script>
let audioSequence = null;
let currentAudioIndex = 0;

function playAudioSequence() {
  const audioDiv = document.getElementById('audio-sequence');
  if (audioDiv) {
    // Trigger Anki's audio playback
    const audioTags = audioDiv.innerHTML.trim();
    // Anki will automatically play [sound:...] tags
    audioDiv.style.display = 'block';
    setTimeout(() => {
      audioDiv.style.display = 'none';
    }, 100);
  }
}

function replayAudio() {
  playAudioSequence();
}
</script>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{Element}}</p>
  <p><strong>Example:</strong> {{ExampleChar}}</p>
</div>

### Styling:
.pinyin-element-card {
  font-family: Arial, sans-serif;
  padding: 20px;
  text-align: center;
}

.element-display {
  margin-bottom: 20px;
}

.main-element {
  font-size: 72px;
  font-weight: bold;
  color: #2196F3;
  margin-bottom: 10px;
}

.example-char {
  font-size: 48px;
  color: #666;
}

.picture {
  margin: 20px 0;
}

.picture img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
}

.tones-display {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin: 30px 0;
  flex-wrap: wrap;
}

.tone-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 15px;
  background-color: #f5f5f5;
  border-radius: 8px;
  min-width: 80px;
}

.tone-mark {
  font-size: 48px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.tone-number {
  font-size: 18px;
  color: #666;
}

.audio-controls {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

.play-btn, .replay-btn {
  padding: 12px 24px;
  font-size: 16px;
  border: 2px solid #2196F3;
  border-radius: 8px;
  background-color: white;
  color: #2196F3;
  cursor: pointer;
  transition: all 0.2s;
}

.play-btn:hover, .replay-btn:hover {
  background-color: #2196F3;
  color: white;
}

.answer-section {
  margin-top: 20px;
  padding: 15px;
  background-color: #f0f8ff;
  border-radius: 8px;
}
"""


def generate_syllable_template_code() -> str:
    """Generate template code for Pinyin Syllable note type with 5 cards"""
    return """# CUMA - Pinyin Syllable Note Type
# Whole syllable with 5 cards

## Fields (current):
ElementToLearn, Syllable, WordPinyin, WordHanzi, WordPicture, _Remarks, _KG_Map

## Card 0: Element Card (Teaching Card)

### Front Template:
<div class="pinyin-syllable-card">
  <div class="element-to-learn">
    <p>学习元素 (Learning Element):</p>
    <div class="element-display">{{ElementToLearn}}</div>
  </div>
  
  <div class="teaching-sequence">
    <p>听音序列 (Audio Sequence):</p>
    <div id="teaching-audio" style="display: none;">
      [sound:mo1.mp3] [sound:{{ElementToLearn}}1.mp3] [sound:{{Syllable}}.mp3]
      <span id="pause-marker"></span>
      [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
    </div>
    <button onclick="playTeachingSequence()" class="play-btn">▶️ 播放</button>
    <button onclick="toggleSound()" class="sound-toggle">🔊 声音: 开</button>
  </div>
</div>

<script>
let soundEnabled = true;

function playTeachingSequence() {
  if (!soundEnabled) return;
  const audioDiv = document.getElementById('teaching-audio');
  if (audioDiv) {
    audioDiv.style.display = 'block';
    setTimeout(() => {
      audioDiv.style.display = 'none';
    }, 100);
  }
}

function toggleSound() {
  soundEnabled = !soundEnabled;
  const btn = document.querySelector('.sound-toggle');
  btn.textContent = soundEnabled ? '🔊 声音: 开' : '🔇 声音: 关';
}
</script>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{ElementToLearn}}</p>
  <p><strong>Syllable:</strong> {{Syllable}}</p>
</div>

## Card 1: Word to Pinyin (Teaching Card)

### Front Template:
<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
    <p class="word-pinyin-hint">{{WordPinyin}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的拼音 (Select the correct pinyin):</p>
  </div>
  
  <div class="teaching-audio-section">
    <div id="word-to-pinyin-audio" style="display: none;">
      [sound:mo1.mp3] [sound:{{ElementToLearn}}1.mp3] [sound:{{Syllable}}.mp3]
      <span id="pause-marker"></span>
      [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
    </div>
    <button onclick="playWordToPinyinSequence()" class="play-btn">▶️ 播放</button>
  </div>
</div>

<script>
function playWordToPinyinSequence() {
  const audioDiv = document.getElementById('word-to-pinyin-audio');
  if (audioDiv) {
    audioDiv.style.display = 'block';
    setTimeout(() => {
      audioDiv.style.display = 'none';
    }, 100);
  }
}
</script>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> {{Syllable}}</p>
  <p><strong>汉字:</strong> {{WordHanzi}}</p>
</div>

## Card 2: MCQ Recent

### Front Template:
<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的拼音 (Select the correct pinyin):</p>
  </div>
  
  <div class="mcq-options" id="mcq-recent-front">
    <!-- Options will be populated from fields -->
    <button class="mcq-option" data-correct="{{Syllable}}" onclick="selectMCQ(this, 'mcq-recent')">
      {{Syllable}}
    </button>
    <!-- Add more options from fields if available -->
  </div>
</div>

<script>
function selectMCQ(button, cardType) {
  const options = document.querySelectorAll(`#${cardType}-front .mcq-option, #${cardType}-back .mcq-option`);
  options.forEach(opt => {
    opt.classList.remove('selected', 'wrong');
  });
  
  const correct = button.getAttribute('data-correct');
  const selected = button.textContent.trim();
  
  if (selected === correct) {
    button.classList.add('selected');
    // Play bell sound
    const bellAudio = document.createElement('div');
    bellAudio.innerHTML = '[sound:bell.wav]';
    bellAudio.style.display = 'block';
    setTimeout(() => bellAudio.remove(), 100);
  } else {
    button.classList.add('wrong');
    // Highlight correct answer
    options.forEach(opt => {
      if (opt.textContent.trim() === correct) {
        opt.classList.add('selected');
      }
    });
  }
}
</script>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-recent-back">
  <!-- Same options as front, in same order, with correct answer highlighted -->
  <button class="mcq-option selected">{{Syllable}}</button>
  <!-- Other options -->
</div>

## Card 3: MCQ Tone (Same structure as MCQ Recent)

### Front Template:
<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的拼音声调 (Select the correct tone):</p>
  </div>
  
  <div class="mcq-options" id="mcq-tone-front">
    <button class="mcq-option" data-correct="{{Syllable}}" onclick="selectMCQ(this, 'mcq-tone')">
      {{Syllable}}
    </button>
    <!-- Tone variations -->
  </div>
</div>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-tone-back">
  <button class="mcq-option selected">{{Syllable}}</button>
  <!-- Other tone options in same order -->
</div>

## Card 4: MCQ Confusor (Same structure as MCQ Recent)

### Front Template:
<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的拼音 (Select the correct pinyin):</p>
  </div>
  
  <div class="mcq-options" id="mcq-confusor-front">
    <button class="mcq-option" data-correct="{{Syllable}}" onclick="selectMCQ(this, 'mcq-confusor')">
      {{Syllable}}
    </button>
    <!-- Confusor options -->
  </div>
</div>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-confusor-back">
  <button class="mcq-option selected">{{Syllable}}</button>
  <!-- Other confusor options in same order -->
</div>

## Card 5: Pinyin to Word (MCQ Reverse)

### Front Template:
<div class="pinyin-syllable-card">
  <div class="pinyin-display">
    <p class="syllable-pinyin">{{Syllable}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的汉字 (Select the correct character):</p>
  </div>
  
  <div class="mcq-options" id="mcq-reverse-front">
    <button class="mcq-option" data-correct="{{WordHanzi}}" onclick="selectMCQ(this, 'mcq-reverse')">
      {{WordHanzi}}
    </button>
    <!-- Other word options -->
  </div>
</div>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{WordHanzi}}</span></p>
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
</div>

<div class="mcq-options" id="mcq-reverse-back">
  <button class="mcq-option selected">{{WordHanzi}}</button>
  <!-- Other word options in same order -->
</div>

### Styling (shared for all cards):
.pinyin-syllable-card {
  font-family: Arial, sans-serif;
  padding: 20px;
  text-align: center;
}

.word-picture img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.word-display {
  margin: 20px 0;
}

.word-hanzi {
  font-size: 48px;
  font-weight: bold;
  color: #333;
  margin: 10px 0;
}

.word-pinyin-hint {
  font-size: 24px;
  color: #666;
}

.syllable-pinyin {
  font-size: 72px;
  font-weight: bold;
  color: #2196F3;
  margin: 20px 0;
}

.mcq-options {
  display: flex;
  justify-content: center;
  gap: 15px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.mcq-option {
  padding: 15px 30px;
  font-size: 24px;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: white;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 100px;
}

.mcq-option:hover {
  background-color: #f5f5f5;
  border-color: #999;
}

.mcq-option.selected {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
}

.mcq-option.wrong {
  background-color: #f44336;
  color: white;
  border-color: #f44336;
}

.correct-answer {
  font-size: 32px;
  font-weight: bold;
  color: #4CAF50;
}

.instruction {
  margin: 20px 0;
  font-size: 18px;
  color: #666;
}

.answer-section {
  margin-top: 20px;
  padding: 15px;
  background-color: #f0f8ff;
  border-radius: 8px;
}

.play-btn, .sound-toggle {
  padding: 12px 24px;
  font-size: 16px;
  border: 2px solid #2196F3;
  border-radius: 8px;
  background-color: white;
  color: #2196F3;
  cursor: pointer;
  margin: 5px;
  transition: all 0.2s;
}

.play-btn:hover, .sound-toggle:hover {
  background-color: #2196F3;
  color: white;
}
"""


def generate_sample_notes():
    """Generate sample notes for element 'a' and syllable 'ma1'"""
    
    # Element "a" note
    element_note = {
        'note_id': 'sample_element_a',
        'element': 'a',
        'element_type': 'final',
        'display_order': 0,
        'fields': {
            'Element': 'a',
            'ExampleChar': '啊',
            'Picture': '<img src="ahh.png">',
            'Tone1': 'ā',  # Proper tone mark instead of 'a1'
            'Tone2': 'á',
            'Tone3': 'ǎ',
            'Tone4': 'à',
            '_Remarks': 'Sample element note for review',
            '_KG_Map': json.dumps({
                "0": [{"kp": "pinyin-element-a", "skill": "form_to_sound", "weight": 1.0}]
            })
        }
    }
    
    # Syllable "ma1" note
    syllable_note = {
        'note_id': 'sample_syllable_ma1',
        'syllable': 'mā',
        'word': '妈',
        'concept': 'Mother',
        'display_order': 1,
        'fields': {
            'ElementToLearn': 'a',
            'Syllable': 'mā',  # Proper tone mark
            'WordPinyin': 'mā mā',
            'WordHanzi': '妈妈',
            'WordPicture': '<img src="mommy.png">',
            '_Remarks': 'Sample syllable note for review',
            '_KG_Map': json.dumps({
                "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
                "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}],
                "2": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "3": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "4": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "5": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}]
            })
        }
    }
    
    return element_note, syllable_note


def main():
    """Main function"""
    print("=" * 80)
    print("Pinyin Note Template Review and Sample Deck Generation")
    print("=" * 80)
    
    # Check Anki connection
    anki = AnkiConnect()
    if not anki.ping():
        print("❌ AnkiConnect not available. Please start Anki first.")
        return
    
    print("\n1. Reviewing current note types...")
    models = anki._invoke('modelNames', {})
    pinyin_models = [m for m in models if 'pinyin' in m.lower() or 'Pinyin' in m]
    
    for model_name in pinyin_models:
        print(f"\n   📋 {model_name}:")
        fields = anki._invoke('modelFieldNames', {'modelName': model_name})
        print(f"      Fields: {', '.join(fields)}")
        
        # Get template info
        try:
            templates = anki._invoke('modelTemplates', {'modelName': model_name})
            print(f"      Cards: {len(templates)}")
            for card_name in templates.keys():
                print(f"        - {card_name}")
        except:
            print(f"      (Could not retrieve template info)")
    
    # Generate template code files
    print("\n2. Generating template code files...")
    element_template = generate_element_template_code()
    syllable_template = generate_syllable_template_code()
    
    element_template_file = OUTPUT_DIR / "CUMA_PINYIN_ELEMENT_TEMPLATE.txt"
    syllable_template_file = OUTPUT_DIR / "CUMA_PINYIN_SYLLABLE_TEMPLATE.txt"
    
    with open(element_template_file, 'w', encoding='utf-8') as f:
        f.write(element_template)
    print(f"   ✅ Element template: {element_template_file}")
    
    with open(syllable_template_file, 'w', encoding='utf-8') as f:
        f.write(syllable_template)
    print(f"   ✅ Syllable template: {syllable_template_file}")
    
    # Generate sample notes
    print("\n3. Generating sample notes...")
    element_note, syllable_note = generate_sample_notes()
    
    sample_file = OUTPUT_DIR / "sample_notes.json"
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump({
            'element_note': element_note,
            'syllable_note': syllable_note
        }, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Sample notes: {sample_file}")
    
    # Generate summary report
    print("\n4. Generating review report...")
    report = f"""# Pinyin Note Template Review Report

## Current Status

### Element Note Type
- **Fields:** {', '.join(['Element', 'ExampleChar', 'Picture', 'Tone1', 'Tone2', 'Tone3', 'Tone4', '_Remarks', '_KG_Map'])}
- **Issues:**
  1. ✅ Tone fields should use proper tone marks (ā á ǎ à) instead of (a1 a2 a3 a4)
  2. ⚠️  Need audio playback sequence: a1 a1 a2 a3 a4 a
  3. ⚠️  Need replay button
  4. ⚠️  Teaching cards should appear less frequently (Anki scheduling)

### Syllable Note Type
- **Fields:** {', '.join(['ElementToLearn', 'Syllable', 'WordPinyin', 'WordHanzi', 'WordPicture', '_Remarks', '_KG_Map'])}
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

- {element_template_file.name}
- {syllable_template_file.name}
- {sample_file.name}
"""
    
    report_file = OUTPUT_DIR / "REVIEW_REPORT.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"   ✅ Review report: {report_file}")
    
    print("\n✅ Review complete!")
    print(f"\n📁 All files saved to: {OUTPUT_DIR}")
    print("\n📝 Next steps:")
    print("   1. Review the template files")
    print("   2. Update Anki note types if needed")
    print("   3. Generate TTS audio files (or let me know if you need help)")


if __name__ == "__main__":
    main()


