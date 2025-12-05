#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate sample pinyin deck in Anki with element "a" and syllable "ma1".

This script:
1. Creates/updates note types with proper templates
2. Generates sample notes with proper tone marks
3. Creates the deck in Anki
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
DECK_NAME = "拼音学习样本 (Pinyin Sample)"


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


def ensure_note_type_exists(anki: AnkiConnect, model_name: str, fields: list, is_element: bool = True):
    """Ensure note type exists, create if not"""
    models = anki._invoke('modelNames', {})
    
    if model_name not in models:
        print(f"   Creating note type: {model_name}")
        # Create new model
        anki._invoke('createModel', {
            'modelName': model_name,
            'inOrderFields': fields,
            'css': get_css(),
            'cardTemplates': get_card_templates(is_element)
        })
    else:
        print(f"   Note type exists: {model_name}")
        # Update fields if needed
        current_fields = anki._invoke('modelFieldNames', {'modelName': model_name})
        for field in fields:
            if field not in current_fields:
                print(f"     Adding field: {field}")
                anki._invoke('modelFieldAdd', {
                    'modelName': model_name,
                    'fieldName': field
                })


def get_css() -> str:
    """Get CSS styling for pinyin cards"""
    return """
.pinyin-card {
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

.answer-section {
  margin-top: 20px;
  padding: 15px;
  background-color: #f0f8ff;
  border-radius: 8px;
}
"""


def get_card_templates(is_element: bool) -> list:
    """Get card templates for element or syllable"""
    if is_element:
        return [{
            'Name': 'Element Card',
            'Front': get_element_front_template(),
            'Back': get_element_back_template()
        }]
    else:
        return [
            {
                'Name': 'Element Card',
                'Front': get_syllable_card0_front(),
                'Back': get_syllable_card0_back()
            },
            {
                'Name': 'Word to Pinyin',
                'Front': get_syllable_card1_front(),
                'Back': get_syllable_card1_back()
            },
            {
                'Name': 'MCQ Recent',
                'Front': get_syllable_mcq_front('recent'),
                'Back': get_syllable_mcq_back('recent')
            },
            {
                'Name': 'MCQ Tone',
                'Front': get_syllable_mcq_front('tone'),
                'Back': get_syllable_mcq_back('tone')
            },
            {
                'Name': 'MCQ Confusor',
                'Front': get_syllable_mcq_front('confusor'),
                'Back': get_syllable_mcq_back('confusor')
            },
            {
                'Name': 'Pinyin to Word',
                'Front': get_syllable_card5_front(),
                'Back': get_syllable_card5_back()
            }
        ]


def get_element_front_template() -> str:
    """Element card front template"""
    return """
<div class="pinyin-card">
  <div class="element-display">{{Element}}</div>
  {{#ExampleChar}}
  <div class="example-char">{{ExampleChar}}</div>
  {{/ExampleChar}}
  
  {{#Picture}}
  <div>{{Picture}}</div>
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
  
  <div style="margin-top: 20px;">
    <button onclick="playAudio()" style="padding: 12px 24px; font-size: 16px; border: 2px solid #2196F3; border-radius: 8px; background-color: white; color: #2196F3; cursor: pointer;">
      ▶️ 播放
    </button>
    <button onclick="playAudio()" style="padding: 12px 24px; font-size: 16px; border: 2px solid #2196F3; border-radius: 8px; background-color: white; color: #2196F3; cursor: pointer; margin-left: 10px;">
      🔄 重播
    </button>
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
"""


def get_element_back_template() -> str:
    """Element card back template"""
    return """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{Element}}</p>
  <p><strong>Example:</strong> {{ExampleChar}}</p>
</div>
"""


def get_syllable_card0_front() -> str:
    """Syllable Card 0: Element Card (Teaching)"""
    return """
<div class="pinyin-card">
  <div class="element-display">{{ElementToLearn}}</div>
  <p>学习元素 (Learning Element)</p>
  
  <div style="margin-top: 20px;">
    <button onclick="playTeachingSequence()" style="padding: 12px 24px; font-size: 16px; border: 2px solid #2196F3; border-radius: 8px; background-color: white; color: #2196F3; cursor: pointer;">
      ▶️ 播放
    </button>
    <button onclick="toggleSound()" id="sound-toggle" style="padding: 12px 24px; font-size: 16px; border: 2px solid #2196F3; border-radius: 8px; background-color: white; color: #2196F3; cursor: pointer; margin-left: 10px;">
      🔊 声音: 开
    </button>
  </div>
  
  <div style="display: none;" id="teaching-audio">
    [sound:mo1.mp3] [sound:{{ElementToLearn}}1.mp3] [sound:{{Syllable}}.mp3]
    <span id="pause"></span>
    [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
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


def get_syllable_card0_back() -> str:
    """Syllable Card 0 back"""
    return """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>Element:</strong> {{ElementToLearn}}</p>
  <p><strong>Syllable:</strong> {{Syllable}}</p>
</div>
"""


def get_syllable_card1_front() -> str:
    """Syllable Card 1: Word to Pinyin (Teaching)"""
    return """
<div class="pinyin-card">
  {{#WordPicture}}
  <div>{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div style="font-size: 48px; font-weight: bold; margin: 20px 0;">{{WordHanzi}}</div>
  <div style="font-size: 24px; color: #666; margin-bottom: 20px;">{{WordPinyin}}</div>
  
  <p>选择正确的拼音 (Select the correct pinyin):</p>
  
  <div style="margin-top: 20px;">
    <button onclick="playWordSequence()" style="padding: 12px 24px; font-size: 16px; border: 2px solid #2196F3; border-radius: 8px; background-color: white; color: #2196F3; cursor: pointer;">
      ▶️ 播放
    </button>
  </div>
  
  <div style="display: none;" id="word-audio">
    [sound:mo1.mp3] [sound:{{ElementToLearn}}1.mp3] [sound:{{Syllable}}.mp3]
    <span id="pause"></span>
    [sound:{{Syllable}}.mp3] [sound:{{Syllable}}.mp3]
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


def get_syllable_card1_back() -> str:
    """Syllable Card 1 back"""
    return """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span style="font-size: 32px; font-weight: bold; color: #4CAF50;">{{Syllable}}</span></p>
  <p><strong>汉字:</strong> {{WordHanzi}}</p>
</div>
"""


def get_syllable_mcq_front(card_type: str) -> str:
    """MCQ card front (Recent, Tone, Confusor)"""
    instruction = {
        'recent': '选择正确的拼音 (Select the correct pinyin)',
        'tone': '选择正确的拼音声调 (Select the correct tone)',
        'confusor': '选择正确的拼音 (Select the correct pinyin)'
    }.get(card_type, '选择正确的拼音')
    
    return f"""
<div class="pinyin-card">
  {{#WordPicture}}
  <div>{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div style="font-size: 48px; font-weight: bold; margin: 20px 0;">{{WordHanzi}}</div>
  
  <p>{instruction}:</p>
  
  <div class="mcq-options" id="mcq-{card_type}-front">
    <button class="mcq-option" data-correct="{{Syllable}}" onclick="selectMCQ(this, '{card_type}')">
      {{Syllable}}
    </button>
  </div>
</div>

<script>
function selectMCQ(button, cardType) {{
  const options = document.querySelectorAll(`#mcq-${{cardType}}-front .mcq-option, #mcq-${{cardType}}-back .mcq-option`);
  options.forEach(opt => {{
    opt.classList.remove('selected', 'wrong');
  }});
  
  const correct = button.getAttribute('data-correct');
  const selected = button.textContent.trim();
  
  if (selected === correct) {{
    button.classList.add('selected');
    // Play bell sound
    const bell = document.createElement('div');
    bell.innerHTML = '[sound:bell.wav]';
    bell.style.display = 'block';
    setTimeout(() => bell.remove(), 100);
  }} else {{
    button.classList.add('wrong');
    options.forEach(opt => {{
      if (opt.textContent.trim() === correct) {{
        opt.classList.add('selected');
      }}
    }});
  }}
}}
</script>
"""


def get_syllable_mcq_back(card_type: str) -> str:
    """MCQ card back (same options, correct highlighted)"""
    return f"""{{{{FrontSide}}}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span style="font-size: 32px; font-weight: bold; color: #4CAF50;">{{{{Syllable}}}}</span></p>
</div>

<div class="mcq-options" id="mcq-{card_type}-back">
  <button class="mcq-option selected">{{{{Syllable}}}}</button>
</div>
"""


def get_syllable_card5_front() -> str:
    """Syllable Card 5: Pinyin to Word (MCQ Reverse)"""
    return """
<div class="pinyin-card">
  <div class="element-display">{{Syllable}}</div>
  
  <p>选择正确的汉字 (Select the correct character):</p>
  
  <div class="mcq-options" id="mcq-reverse-front">
    <button class="mcq-option" data-correct="{{WordHanzi}}" onclick="selectMCQ(this, 'reverse')">
      {{WordHanzi}}
    </button>
  </div>
</div>

<script>
function selectMCQ(button, cardType) {
  const options = document.querySelectorAll(`#mcq-${cardType}-front .mcq-option, #mcq-${cardType}-back .mcq-option`);
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


def get_syllable_card5_back() -> str:
    """Syllable Card 5 back"""
    return """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span style="font-size: 32px; font-weight: bold; color: #4CAF50;">{{WordHanzi}}</span></p>
  {{#WordPicture}}
  <div>{{WordPicture}}</div>
  {{/WordPicture}}
</div>

<div class="mcq-options" id="mcq-reverse-back">
  <button class="mcq-option selected">{{WordHanzi}}</button>
</div>
"""


def main():
    """Main function"""
    print("=" * 80)
    print("Generate Pinyin Sample Deck")
    print("=" * 80)
    
    anki = AnkiConnect()
    if not anki.ping():
        print("❌ AnkiConnect not available. Please start Anki first.")
        return
    
    # Ensure deck exists
    print("\n1. Creating deck...")
    try:
        anki.create_deck(DECK_NAME)
        print(f"   ✅ Deck created: {DECK_NAME}")
    except:
        print(f"   ℹ️  Deck may already exist: {DECK_NAME}")
    
    # Ensure note types exist
    print("\n2. Ensuring note types exist...")
    
    element_fields = ['Element', 'ExampleChar', 'Picture', 'Tone1', 'Tone2', 'Tone3', 'Tone4', '_Remarks', '_KG_Map']
    ensure_note_type_exists(anki, 'CUMA - Pinyin Element', element_fields, is_element=True)
    
    syllable_fields = ['ElementToLearn', 'Syllable', 'WordPinyin', 'WordHanzi', 'WordPicture', '_Remarks', '_KG_Map']
    ensure_note_type_exists(anki, 'CUMA - Pinyin Syllable', syllable_fields, is_element=False)
    
    # Generate sample notes
    print("\n3. Creating sample notes...")
    
    # Element "a" note
    element_fields_dict = {
        'Element': 'a',
        'ExampleChar': '啊',
        'Picture': '<img src="ahh.png">',
        'Tone1': 'ā',  # Proper tone marks
        'Tone2': 'á',
        'Tone3': 'ǎ',
        'Tone4': 'à',
        '_Remarks': 'Sample element note - Review template',
        '_KG_Map': json.dumps({
            "0": [{"kp": "pinyin-element-a", "skill": "form_to_sound", "weight": 1.0}]
        })
    }
    
    try:
        element_note_id = anki.add_note(
            DECK_NAME,
            'CUMA - Pinyin Element',
            element_fields_dict
        )
        print(f"   ✅ Created element note: {element_note_id}")
    except Exception as e:
        print(f"   ⚠️  Error creating element note: {e}")
    
    # Syllable "ma1" note
    syllable_fields_dict = {
        'ElementToLearn': 'a',
        'Syllable': 'mā',  # Proper tone mark
        'WordPinyin': 'mā mā',
        'WordHanzi': '妈妈',
        'WordPicture': '<img src="mommy.png">',
        '_Remarks': 'Sample syllable note - Review template',
        '_KG_Map': json.dumps({
            "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
            "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}],
            "2": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
            "3": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
            "4": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
            "5": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}]
        })
    }
    
    try:
        syllable_note_id = anki.add_note(
            DECK_NAME,
            'CUMA - Pinyin Syllable',
            syllable_fields_dict
        )
        print(f"   ✅ Created syllable note: {syllable_note_id}")
    except Exception as e:
        print(f"   ⚠️  Error creating syllable note: {e}")
    
    print("\n✅ Sample deck generation complete!")
    print(f"\n📚 Deck: {DECK_NAME}")
    print("   - Element 'a' note created")
    print("   - Syllable 'ma1' (mā) note created")
    print("\n📝 Note: Audio files need to be generated separately:")
    print("   - Element: a1.mp3, a2.mp3, a3.mp3, a4.mp3, a.mp3")
    print("   - Syllable: mo1.mp3, mā.mp3, mā mā.mp3")
    print("   - Bell: bell.wav")


if __name__ == "__main__":
    main()


