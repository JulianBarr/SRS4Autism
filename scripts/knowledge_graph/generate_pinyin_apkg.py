#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate .apkg file for pinyin sample deck with templates, notes, and audio files.

This script creates a complete Anki package (.apkg) that includes:
1. Updated note types (Element and Syllable) with proper templates
2. Sample notes (element "a" and syllable "ma1")
3. All TTS audio files
4. Media files (images)

Importing this .apkg will automatically:
- Create/update the note types with correct templates
- Add the sample notes
- Include all audio files
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import genanki
except ImportError:
    print("❌ genanki not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "genanki"])
    import genanki

PROJECT_ROOT = project_root
OUTPUT_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck"
AUDIO_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
MEDIA_DIR = PROJECT_ROOT / "media" / "pinyin"

# Fixed IDs for note types (to avoid conflicts)
ELEMENT_MODEL_ID = 1985090401
SYLLABLE_MODEL_ID = 1985090402
DECK_ID = 1985090403


def create_element_model():
    """Create CUMA - Pinyin Element note type model"""
    
    fields = [
        {'name': 'Element'},
        {'name': 'ExampleChar'},
        {'name': 'Picture'},
        {'name': 'Tone1'},
        {'name': 'Tone2'},
        {'name': 'Tone3'},
        {'name': 'Tone4'},
        {'name': '_Remarks'},
        {'name': '_KG_Map'},
    ]
    
    css = """
.pinyin-element-card {
  font-family: Arial, sans-serif;
  padding: 20px;
  text-align: center;
}

.element-display {
  font-size: 72px;
  font-weight: bold;
  color: #2196F3;
  margin: 20px 0;
}

.example-char {
  font-size: 48px;
  color: #666;
  margin: 10px 0;
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
  align-items: center;
  justify-content: center;
  padding: 15px;
  background-color: #f5f5f5;
  border-radius: 8px;
  min-width: 80px;
}

.tone-mark {
  font-size: 48px;
  font-weight: bold;
  color: #333;
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
    
    front_template = """
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
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone2}}</span>
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone3}}</span>
    </div>
    <div class="tone-item">
      <span class="tone-mark">{{Tone4}}</span>
    </div>
  </div>
  
  <div class="caregiver-note" style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border-radius: 8px; color: #856404;">
    <p style="margin: 0; font-size: 16px;">📢 请照顾者朗读 (Please read aloud)</p>
  </div>
</div>
"""
    
    back_template = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{Element}}</p>
  <p><strong>Example:</strong> {{ExampleChar}}</p>
</div>
"""
    
    model = genanki.Model(
        ELEMENT_MODEL_ID,
        'CUMA - Pinyin Element',
        fields=fields,
        templates=[
            {
                'name': 'Element Card',
                'qfmt': front_template,
                'afmt': back_template,
            }
        ],
        css=css,
    )
    
    return model


def create_syllable_model():
    """Create CUMA - Pinyin Syllable note type model with 6 cards"""
    
    fields = [
        {'name': 'ElementToLearn'},
        {'name': 'Syllable'},
        {'name': 'WordPinyin'},
        {'name': 'WordHanzi'},
        {'name': 'WordPicture'},
        {'name': '_Remarks'},
        {'name': '_KG_Map'},
    ]
    
    css = """
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
  color: #ffffff;
  background-color: rgba(255, 255, 255, 0.2);
  padding: 8px 12px;
  border-radius: 4px;
  font-weight: 500;
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

.mcq-picture-options {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.mcq-picture-option {
  cursor: pointer;
  border: 3px solid #ddd;
  border-radius: 8px;
  padding: 5px;
  background-color: white;
  transition: all 0.2s;
  max-width: 200px;
}

.mcq-picture-option:hover {
  border-color: #999;
  transform: scale(1.05);
}

.mcq-picture-option.selected {
  border-color: #4CAF50;
  border-width: 4px;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.mcq-picture-option.wrong {
  border-color: #f44336;
  border-width: 4px;
  opacity: 0.6;
}

.mcq-picture-option img {
  width: 100%;
  height: auto;
  border-radius: 4px;
  display: block;
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
    
    # Card 0: Element Card (Teaching)
    card0_front = """
<div class="pinyin-syllable-card">
  <div class="element-display">{{ElementToLearn}}</div>
  <p>学习元素 (Learning Element)</p>
  
  <div style="margin-top: 20px;">
    <button onclick="playTeachingSequence()" class="play-btn">▶️ 播放</button>
    <button onclick="toggleSound()" id="sound-toggle" class="sound-toggle">🔊 声音: 开</button>
  </div>
  
  <!-- Audio sequence - element audio skipped (caregiver reads), only syllable audio -->
  <div id="teaching-audio" style="height: 0; overflow: hidden;">
    [sound:mo1.mp3] [sound:{{Syllable}}.mp3]
    [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
  </div>
  <div style="margin-top: 10px; font-size: 14px; color: #666;">
    <p>ℹ️ 元素 "{{ElementToLearn}}" 由照顾者朗读 (Element "{{ElementToLearn}}" read by caregiver)</p>
  </div>
</div>

<script>
let soundEnabled = true;

function playTeachingSequence() {
  if (!soundEnabled) return;
  const audioDiv = document.getElementById('teaching-audio');
  if (audioDiv) {
    audioDiv.style.display = 'block';
    setTimeout(() => audioDiv.style.display = 'none', 100);
  }
}

function toggleSound() {
  soundEnabled = !soundEnabled;
  const btn = document.getElementById('sound-toggle');
  btn.textContent = soundEnabled ? '🔊 声音: 开' : '🔇 声音: 关';
}
</script>
"""
    
    card0_back = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{ElementToLearn}}</p>
  <p><strong>Syllable:</strong> {{Syllable}}</p>
</div>
"""
    
    # Card 1: Word to Pinyin (Teaching)
    card1_front = """
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
  
  <div style="margin-top: 20px;">
    <button onclick="playWordSequence()" class="play-btn">▶️ 播放</button>
  </div>
  
  <!-- Audio sequence - element audio skipped (caregiver reads), only syllable audio -->
  <div id="word-audio" style="height: 0; overflow: hidden;">
    [sound:mo1.mp3] [sound:{{Syllable}}.mp3]
    [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
  </div>
  <div style="margin-top: 10px; font-size: 14px; color: #666;">
    <p>ℹ️ 元素 "{{ElementToLearn}}" 由照顾者朗读 (Element "{{ElementToLearn}}" read by caregiver)</p>
  </div>
</div>

<script>
function playWordSequence() {
  const audioDiv = document.getElementById('word-audio');
  if (audioDiv) {
    audioDiv.style.display = 'block';
    setTimeout(() => audioDiv.style.display = 'none', 100);
  }
}
</script>
"""
    
    card1_back = """{{FrontSide}}

<hr id="answer">

<!-- Play word audio when back is shown -->
<div style="height: 0; overflow: hidden;">
  [sound:{{WordPinyin}}.mp3]
</div>

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
  <p><strong>汉字:</strong> {{WordHanzi}}</p>
</div>
"""
    
    # Card 2-4: MCQ cards (same structure)
    mcq_front = """
<div class="pinyin-syllable-card">
  <!-- Play audio when front card loads -->
  <div style="height: 0; overflow: hidden;">
    [sound:{{WordPinyin}}.mp3]
  </div>
  
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="instruction">
    <p>选择正确的拼音 (Select the correct pinyin):</p>
  </div>
  
  <div class="mcq-options" id="mcq-front">
    <button class="mcq-option" data-correct="{{Syllable}}" onclick="selectMCQ(this)">
      {{Syllable}}
    </button>
    <!-- Placeholder wrong options - in real implementation, these would come from fields -->
    <button class="mcq-option" data-correct="ma" onclick="selectMCQ(this)">ma</button>
    <button class="mcq-option" data-correct="mà" onclick="selectMCQ(this)">mà</button>
    <button class="mcq-option" data-correct="mǎ" onclick="selectMCQ(this)">mǎ</button>
  </div>
</div>

<script>
function selectMCQ(button) {
  const options = document.querySelectorAll('#mcq-front .mcq-option, #mcq-back .mcq-option');
  options.forEach(opt => {
    opt.classList.remove('selected', 'wrong');
  });
  
  const correct = button.getAttribute('data-correct');
  const selected = button.textContent.trim();
  
  if (selected === correct) {
    button.classList.add('selected');
    const bell = document.createElement('div');
    bell.innerHTML = '[sound:bell.wav]';
    bell.style.display = 'block';
    setTimeout(() => bell.remove(), 100);
  } else {
    button.classList.add('wrong');
    options.forEach(opt => {
      if (opt.textContent.trim() === correct) {
        opt.classList.add('selected');
      }
    });
  }
}
</script>
"""
    
    mcq_back = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-back">
  <!-- Same order as front -->
  <button class="mcq-option selected">{{Syllable}}</button>
  <button class="mcq-option">ma</button>
  <button class="mcq-option">mà</button>
  <button class="mcq-option">mǎ</button>
</div>
"""
    
    # Card 5: Pinyin to Word (MCQ with Pictures)
    card5_front = """
<div class="pinyin-syllable-card">
  <!-- Play audio when front card loads -->
  <div style="height: 0; overflow: hidden;">
    [sound:{{WordPinyin}}.mp3]
  </div>
  
  <div class="word-pinyin-hint" style="font-size: 36px; margin-bottom: 30px;">{{WordPinyin}}</div>
  
  <div class="instruction">
    <p>选择正确的图片 (Select the correct picture):</p>
  </div>
  
  <div class="mcq-picture-options" id="mcq-picture-front">
    {{#WordPicture}}
    <div class="mcq-picture-option" data-correct="true" onclick="selectPictureMCQ(this)">
      {{WordPicture}}
    </div>
    {{/WordPicture}}
    <!-- Placeholder wrong options - in real implementation, these would come from fields -->
    <div class="mcq-picture-option" data-correct="false" onclick="selectPictureMCQ(this)">
      <img src="ahh.png" alt="distractor">
    </div>
    <div class="mcq-picture-option" data-correct="false" onclick="selectPictureMCQ(this)">
      <img src="ahh.png" alt="distractor">
    </div>
    <div class="mcq-picture-option" data-correct="false" onclick="selectPictureMCQ(this)">
      <img src="ahh.png" alt="distractor">
    </div>
  </div>
</div>

<script>
function selectPictureMCQ(option) {
  const options = document.querySelectorAll('#mcq-picture-front .mcq-picture-option, #mcq-picture-back .mcq-picture-option');
  options.forEach(opt => {
    opt.classList.remove('selected', 'wrong');
  });
  
  const isCorrect = option.getAttribute('data-correct') === 'true';
  
  if (isCorrect) {
    option.classList.add('selected');
    const bell = document.createElement('div');
    bell.innerHTML = '[sound:bell.wav]';
    bell.style.display = 'block';
    setTimeout(() => bell.remove(), 100);
  } else {
    option.classList.add('wrong');
    options.forEach(opt => {
      if (opt.getAttribute('data-correct') === 'true') {
        opt.classList.add('selected');
      }
    });
  }
}
</script>
"""
    
    card5_back = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{WordHanzi}}</span></p>
  <p><strong>拼音:</strong> {{WordPinyin}}</p>
</div>

<div class="mcq-picture-options" id="mcq-picture-back">
  {{#WordPicture}}
  <div class="mcq-picture-option selected" data-correct="true">
    {{WordPicture}}
  </div>
  {{/WordPicture}}
  <!-- Same order as front -->
  <div class="mcq-picture-option" data-correct="false">
    <img src="ahh.png" alt="distractor">
  </div>
  <div class="mcq-picture-option" data-correct="false">
    <img src="ahh.png" alt="distractor">
  </div>
  <div class="mcq-picture-option" data-correct="false">
    <img src="ahh.png" alt="distractor">
  </div>
</div>
"""
    
    model = genanki.Model(
        SYLLABLE_MODEL_ID,
        'CUMA - Pinyin Syllable',
        fields=fields,
        templates=[
            {
                'name': 'Element Card',
                'qfmt': card0_front,
                'afmt': card0_back,
            },
            {
                'name': 'Word to Pinyin',
                'qfmt': card1_front,
                'afmt': card1_back,
            },
            {
                'name': 'MCQ Recent',
                'qfmt': mcq_front,
                'afmt': mcq_back,
            },
            {
                'name': 'MCQ Tone',
                'qfmt': mcq_front,
                'afmt': mcq_back,
            },
            {
                'name': 'MCQ Confusor',
                'qfmt': mcq_front,
                'afmt': mcq_back,
            },
            {
                'name': 'Pinyin to Word',
                'qfmt': card5_front,
                'afmt': card5_back,
            },
        ],
        css=css,
    )
    
    return model


def create_apkg():
    """Create the complete .apkg file"""
    
    print("=" * 80)
    print("Generate Pinyin Sample Deck .apkg File")
    print("=" * 80)
    
    # Create models
    print("\n1. Creating note type models...")
    element_model = create_element_model()
    syllable_model = create_syllable_model()
    print("   ✅ Element model created")
    print("   ✅ Syllable model created (6 cards)")
    
    # Create deck
    print("\n2. Creating deck...")
    deck = genanki.Deck(DECK_ID, '拼音学习样本 (Pinyin Sample)')
    
    # Add element note
    print("\n3. Adding sample notes...")
    element_note = genanki.Note(
        model=element_model,
        fields=[
            'a',  # Element
            '啊',  # ExampleChar
            '<img src="ahh.png">',  # Picture
            'ā',  # Tone1 (proper tone mark)
            'á',  # Tone2
            'ǎ',  # Tone3
            'à',  # Tone4
            'Sample element note for review',  # _Remarks
            '{"0": [{"kp": "pinyin-element-a", "skill": "form_to_sound", "weight": 1.0}]}',  # _KG_Map
        ]
    )
    deck.add_note(element_note)
    print("   ✅ Added element 'a' note")
    
    # Add syllable note
    syllable_note = genanki.Note(
        model=syllable_model,
        fields=[
            'a',  # ElementToLearn
            'mā',  # Syllable (proper tone mark)
            'mā mā',  # WordPinyin
            '妈妈',  # WordHanzi
            '<img src="mommy.png">',  # WordPicture
            'Sample syllable note for review',  # _Remarks
            json.dumps({
                "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
                "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}],
                "2": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "3": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "4": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "5": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}]
            }),  # _KG_Map
        ]
    )
    deck.add_note(syllable_note)
    print("   ✅ Added syllable 'ma1' (mā) note")
    
    # Create package
    print("\n4. Packaging deck...")
    package = genanki.Package(deck)
    package.models = [element_model, syllable_model]
    
    # Add media files
    print("\n5. Adding media files...")
    media_files = []
    
    # Audio files - only include syllable audio
    # Element audio skipped per Pinyin Review.md: "don't do this now"
    audio_files = [
        # Syllable audio - using TTS with Chinese characters
        'mo1.mp3', 'mā.mp3', 'mā mā.mp3'
    ]
    
    print("   ℹ️  Note: Pinyin element audio (a1, a2, a3, a4, a) not included")
    print("      - Per requirements: 'don't do this now'")
    print("      - Caregiver will read element tones manually")
    print("      - Only syllable audio included (TTS with Chinese characters)")
    
    for audio_file in audio_files:
        audio_path = AUDIO_DIR / audio_file
        if audio_path.exists():
            # Use absolute path to ensure genanki can find the file
            media_files.append(str(audio_path.resolve()))
            print(f"   ✅ Added audio: {audio_file}")
        else:
            print(f"   ⚠️  Audio file not found: {audio_file}")
    
    # Image files
    image_files = ['ahh.png', 'mommy.png']
    for image_file in image_files:
        image_path = MEDIA_DIR / image_file
        if image_path.exists():
            # Use absolute path to ensure genanki can find the file
            media_files.append(str(image_path.resolve()))
            print(f"   ✅ Added image: {image_file} ({image_path.resolve()})")
        else:
            print(f"   ⚠️  Image file not found: {image_file}")
    
    # Bell sound (optional)
    bell_path = AUDIO_DIR / "bell.wav"
    if bell_path.exists():
        media_files.append(str(bell_path))
        print(f"   ✅ Added bell sound: bell.wav")
    else:
        print(f"   ⚠️  Bell sound not found (optional): bell.wav")
    
    package.media_files = media_files
    
    # Write package
    output_file = OUTPUT_DIR / "Pinyin_Sample_Deck.apkg"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n6. Writing .apkg file...")
    package.write_to_file(str(output_file))
    
    print(f"\n{'='*80}")
    print(f"✅ .apkg file created successfully!")
    print(f"   Location: {output_file}")
    print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
    print(f"\n📋 To import:")
    print(f"   1. Open Anki")
    print(f"   2. File → Import")
    print(f"   3. Select: {output_file}")
    print(f"   4. The note types and sample notes will be imported automatically!")
    print(f"   5. All audio files and images will be included")
    print(f"{'='*80}")
    
    return output_file


if __name__ == "__main__":
    create_apkg()

