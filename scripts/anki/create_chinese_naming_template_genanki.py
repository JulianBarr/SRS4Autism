#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create "CUMA - Chinese Naming" note type in Anki using genanki.

This script creates an Anki package (.apkg) file that can be imported
to automatically create the note type with all templates.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import genanki
except ImportError:
    print("❌ genanki not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "genanki"])
    import genanki

from anki_integration.anki_connect import AnkiConnect


def create_chinese_naming_model():
    """Create the CUMA - Chinese Naming note type model"""
    
    # Define all fields
    fields = [
        {'name': 'Concept'},
        {'name': 'Image'},
        {'name': 'Audio'},
        {'name': 'Difficulty'},
        {'name': 'Syllable'},
        {'name': 'FullPinyin'},
        {'name': 'SyllableIndex'},
        {'name': 'TotalSyllables'},
        {'name': 'SyllableOption1'},
        {'name': 'SyllableOption2'},
        {'name': 'SyllableOption3'},
        {'name': 'SyllableOption4'},
        {'name': 'Initial'},
        {'name': 'InitialOption1'},
        {'name': 'InitialOption2'},
        {'name': 'Medial'},
        {'name': 'MedialOption1'},
        {'name': 'MedialOption2'},
        {'name': 'TonedFinal'},
        {'name': 'TonedFinalOption1'},
        {'name': 'TonedFinalOption2'},
        {'name': 'Pinyin'},
        {'name': 'Config'},
        {'name': '_KG_Map'},
        {'name': '_Remarks'},
    ]
    
    # CSS styling (with dark mode support)
    css = """<style>
/* Use Anki's CSS variables for theme compatibility */
.cuma-naming-card {
  font-family: Arial, sans-serif;
  padding: 20px;
  color: var(--text-fg, #000);
  background-color: var(--card-bg, #fff);
}

.concept-image {
  text-align: center;
  margin-bottom: 20px;
}

.concept-image img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.pinyin-construction {
  margin-top: 20px;
}

.component-group {
  margin-bottom: 20px;
  padding: 15px;
  border-radius: 8px;
}

/* Initial group - Blue theme */
.initial-group {
  background-color: rgba(33, 150, 243, 0.15);
  border: 2px solid #2196F3;
}

.nightMode .initial-group {
  background-color: rgba(33, 150, 243, 0.25);
  border-color: #64B5F6;
}

/* Medial group - Purple theme */
.medial-group {
  background-color: rgba(156, 39, 176, 0.15);
  border: 2px solid #9C27B0;
}

.nightMode .medial-group {
  background-color: rgba(156, 39, 176, 0.25);
  border-color: #BA68C8;
}

/* Final group - Orange theme */
.final-group {
  background-color: rgba(255, 152, 0, 0.15);
  border: 2px solid #FF9800;
}

.nightMode .final-group {
  background-color: rgba(255, 152, 0, 0.25);
  border-color: #FFB74D;
}

.component-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 16px;
  color: var(--text-fg, #000);
}

.options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.option-btn, .syllable-option-btn {
  padding: 12px 24px;
  font-size: 18px;
  border: 2px solid var(--border, #ddd);
  border-radius: 8px;
  background-color: var(--button-bg, #fff);
  color: var(--text-fg, #000);
  cursor: pointer;
  transition: all 0.2s;
  min-width: 60px;
  font-weight: 500;
}

.option-btn:hover, .syllable-option-btn:hover {
  background-color: var(--button-hover-bg, #f5f5f5);
  border-color: var(--border-hover, #999);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.nightMode .option-btn:hover, .nightMode .syllable-option-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  border-color: #888;
}

.option-btn.selected, .syllable-option-btn.selected {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
}

.nightMode .option-btn.selected, .nightMode .syllable-option-btn.selected {
  background-color: #66BB6A;
  border-color: #66BB6A;
}

.option-btn.wrong, .syllable-option-btn.wrong {
  background-color: #f44336;
  color: white;
  border-color: #f44336;
  box-shadow: 0 2px 4px rgba(244, 67, 54, 0.3);
}

.nightMode .option-btn.wrong, .nightMode .syllable-option-btn.wrong {
  background-color: #EF5350;
  border-color: #EF5350;
}

.constructed-pinyin {
  margin-top: 20px;
  padding: 15px;
  background-color: var(--faint-bg, #f9f9f9);
  border: 2px solid var(--border, #ddd);
  border-radius: 8px;
  font-size: 24px;
  text-align: center;
  min-height: 50px;
}

.nightMode .constructed-pinyin {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: #555;
}

.constructed-pinyin span {
  margin: 0 5px;
  font-weight: bold;
}

.correct-pinyin, .correct-syllable {
  font-size: 24px;
  margin: 10px 0;
  color: var(--text-fg, #000);
  font-weight: bold;
}

.initial-component {
  color: #2196F3;
  font-weight: bold;
}

.nightMode .initial-component {
  color: #64B5F6;
}

.medial-component {
  color: #9C27B0;
  font-weight: bold;
}

.nightMode .medial-component {
  color: #BA68C8;
}

.final-component {
  color: #FF9800;
  font-weight: bold;
}

.nightMode .final-component {
  color: #FFB74D;
}

.full-pinyin {
  font-size: 18px;
  color: var(--text-fg, #666);
  margin-top: 10px;
  opacity: 0.8;
}

.concept {
  font-size: 16px;
  color: var(--text-fg, #333);
  margin-top: 5px;
  font-weight: 500;
}

.syllable-indicator {
  font-size: 14px;
  color: var(--text-fg, #666);
  font-style: italic;
  opacity: 0.7;
}

.instruction {
  margin-bottom: 20px;
}

.instruction p {
  color: var(--text-fg, #000);
  font-size: 16px;
  margin: 10px 0;
}

.syllable-multiple-choice {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 20px;
}

.answer-section {
  margin-top: 20px;
  padding: 15px;
  background-color: rgba(33, 150, 243, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(33, 150, 243, 0.3);
}

.nightMode .answer-section {
  background-color: rgba(33, 150, 243, 0.2);
  border-color: rgba(100, 181, 246, 0.4);
}

.answer-section p {
  color: var(--text-fg, #000);
  margin: 8px 0;
}

.answer-section strong {
  color: var(--text-fg, #000);
}
</style>"""
    
    # Card 1: Easy - Select Syllable (Front Template)
    easy_front = """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  <div class="audio">
    {{Audio}}
  </div>
  <div class="instruction">
    <p id="instruction-text">点击选择正确的拼音音节：</p>
    {{#TotalSyllables}}
      {{#TotalSyllables}}
        <p class="syllable-indicator">音节 {{SyllableIndex}}/{{TotalSyllables}}</p>
      {{/TotalSyllables}}
    {{/TotalSyllables}}
  </div>
  
  <script>
  // Update instruction based on Config field
  (function() {
    const config = '{{Config}}';
    const instructionEl = document.getElementById('instruction-text');
    if (instructionEl) {
      if (config === 'traditional') {
        instructionEl.textContent = '點擊選擇正確的拼音音節：';
      } else {
        instructionEl.textContent = '点击选择正确的拼音音节：';
      }
    }
  })();
  </script>
  
  <div class="syllable-multiple-choice">
    <button class="syllable-option-btn" data-correct="{{Syllable}}" onclick="selectSyllable(this)">
      {{SyllableOption1}}
    </button>
    {{#SyllableOption2}}
    <button class="syllable-option-btn" data-correct="{{Syllable}}" onclick="selectSyllable(this)">
      {{SyllableOption2}}
    </button>
    {{/SyllableOption2}}
    {{#SyllableOption3}}
    <button class="syllable-option-btn" data-correct="{{Syllable}}" onclick="selectSyllable(this)">
      {{SyllableOption3}}
    </button>
    {{/SyllableOption3}}
    {{#SyllableOption4}}
    <button class="syllable-option-btn" data-correct="{{Syllable}}" onclick="selectSyllable(this)">
      {{SyllableOption4}}
    </button>
    {{/SyllableOption4}}
  </div>
</div>

<script>
function selectSyllable(button) {
  const buttons = button.parentElement.querySelectorAll('.syllable-option-btn');
  buttons.forEach(btn => btn.classList.remove('selected', 'wrong'));
  
  const correct = button.getAttribute('data-correct');
  const selected = button.textContent.trim();
  
  if (selected === correct) {
    button.classList.add('selected');
  } else {
    button.classList.add('wrong');
    buttons.forEach(btn => {
      if (btn.textContent.trim() === correct) {
        btn.classList.add('selected');
      }
    });
  }
}
</script>"""
    
    # Card 1: Easy - Select Syllable (Back Template)
    easy_back = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案 (Correct Answer):</strong></p>
  <div class="correct-syllable">
    {{Syllable}}
  </div>
  <p class="full-pinyin">完整拼音: {{FullPinyin}}</p>
  <p class="concept">概念: {{Concept}}</p>
</div>"""
    
    # Card 2: Harder - Construct Syllable (Front Template)
    harder_front = """<div class="cuma-naming-card">
  {{#Image}}
  <div class="concept-image">
    {{Image}}
  </div>
  {{/Image}}
  {{#Audio}}
  <div class="audio">
    {{Audio}}
  </div>
  {{/Audio}}
  <div class="instruction">
    <p id="instruction-text-construct">点击声母、介音、韵母来构建拼音：</p>
    {{#TotalSyllables}}
      {{#TotalSyllables}}
        <p class="syllable-indicator">音节 {{SyllableIndex}}/{{TotalSyllables}}</p>
      {{/TotalSyllables}}
    {{/TotalSyllables}}
  </div>
  
  <script>
  // Update instruction based on Config field
  (function() {
    const config = '{{Config}}';
    const instructionEl = document.getElementById('instruction-text-construct');
    if (instructionEl) {
      if (config === 'traditional') {
        instructionEl.textContent = '點擊聲母、介音、韻母來構建拼音：';
      } else {
        instructionEl.textContent = '点击声母、介音、韵母来构建拼音：';
      }
    }
  })();
  </script>
  
  <div class="pinyin-construction">
    <!-- Initial -->
    {{#Initial}}
    <div class="component-group initial-group">
      <label>声母 (Initial):</label>
      <div class="options">
        <button class="option-btn" data-correct="{{Initial}}" onclick="selectOption(this, 'initial')">
          {{InitialOption1}}
        </button>
        {{#InitialOption2}}
        <button class="option-btn" data-correct="{{Initial}}" onclick="selectOption(this, 'initial')">
          {{InitialOption2}}
        </button>
        {{/InitialOption2}}
      </div>
    </div>
    {{/Initial}}
    
    <!-- Medial (only if present) -->
    {{#Medial}}
    <div class="component-group medial-group">
      <label>介音 (Medial):</label>
      <div class="options">
        <button class="option-btn" data-correct="{{Medial}}" onclick="selectOption(this, 'medial')">
          {{MedialOption1}}
        </button>
        {{#MedialOption2}}
        <button class="option-btn" data-correct="{{Medial}}" onclick="selectOption(this, 'medial')">
          {{MedialOption2}}
        </button>
        {{/MedialOption2}}
      </div>
    </div>
    {{/Medial}}
    
    <!-- Toned Final -->
    {{#TonedFinal}}
    <div class="component-group final-group">
      <label>韵母 (Final):</label>
      <div class="options">
        <button class="option-btn" data-correct="{{TonedFinal}}" onclick="selectOption(this, 'final')">
          {{TonedFinalOption1}}
        </button>
        {{#TonedFinalOption2}}
        <button class="option-btn" data-correct="{{TonedFinal}}" onclick="selectOption(this, 'final')">
          {{TonedFinalOption2}}
        </button>
        {{/TonedFinalOption2}}
      </div>
    </div>
    {{/TonedFinal}}
    
    <!-- Constructed Pinyin Display -->
    <div class="constructed-pinyin">
      <span id="selected-initial"></span>
      <span id="selected-medial"></span>
      <span id="selected-final"></span>
    </div>
  </div>
</div>

<script>
let selectedComponents = {
  initial: null,
  medial: null,
  final: null
};

function selectOption(button, componentType) {
  const group = button.closest('.component-group');
  group.querySelectorAll('.option-btn').forEach(btn => {
    btn.classList.remove('selected', 'wrong');
  });
  
  button.classList.add('selected');
  selectedComponents[componentType] = button.textContent.trim();
  updateConstructedPinyin();
}

function updateConstructedPinyin() {
  const display = document.getElementById('selected-initial');
  if (display) {
    const initial = selectedComponents.initial || '';
    const medial = selectedComponents.medial || '';
    const final = selectedComponents.final || '';
    
    display.parentElement.innerHTML = `
      <span id="selected-initial">${initial}</span>
      <span id="selected-medial">${medial}</span>
      <span id="selected-final">${final}</span>
    `;
  }
}
</script>"""
    
    # Card 2: Harder - Construct Syllable (Back Template)
    harder_back = """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案 (Correct Answer):</strong></p>
  <div class="correct-pinyin">
    {{#Initial}}<span class="initial-component">{{Initial}}</span>{{/Initial}}
    {{#Medial}}<span class="medial-component">{{Medial}}</span>{{/Medial}}
    <span class="final-component">{{TonedFinal}}</span>
  </div>
  <p class="full-pinyin">完整拼音: {{FullPinyin}}</p>
  <p class="concept">概念: {{Concept}}</p>
</div>"""
    
    # Create the model with a unique model ID
    # Using a fixed ID so it's consistent
    model_id = 1607453189  # Fixed ID for CUMA - Chinese Naming
    
    model = genanki.Model(
        model_id,
        'CUMA - Chinese Naming',
        fields=fields,
        templates=[
            {
                'name': 'Easy - Select Syllable',
                'qfmt': easy_front,
                'afmt': easy_back,
            },
            {
                'name': 'Harder - Construct Syllable',
                'qfmt': harder_front,
                'afmt': harder_back,
            },
        ],
        css=css,
    )
    
    return model


def create_template_package():
    """Create an Anki package file with the note type and a sample note"""
    
    print("🚀 Creating CUMA - Chinese Naming note type using genanki...\n")
    
    # Create the model
    model = create_chinese_naming_model()
    
    # Create a deck
    deck_id = 1985090310  # Fixed ID for template deck
    deck = genanki.Deck(deck_id, 'CUMA Template - Chinese Naming')
    
    # Add a sample note to ensure the package can be imported
    # This is a dummy example for "shī" (first syllable of "shī zi" - lion)
    # Include a sample image reference
    sample_note_easy = genanki.Note(
        model=model,
        fields=[
            'Lion',  # Concept
            '<img src="lion.png" alt="Lion">',  # Image (sample reference)
            '',  # Audio (empty for template)
            'easy',  # Difficulty
            'shī',  # Syllable
            'shī zi',  # FullPinyin
            '1',  # SyllableIndex
            '2',  # TotalSyllables
            'shī',  # SyllableOption1 (correct)
            'shí',  # SyllableOption2 (distractor)
            'mā',  # SyllableOption3 (distractor)
            'zī',  # SyllableOption4 (distractor)
            'sh',  # Initial
            'sh',  # InitialOption1 (correct)
            'zh',  # InitialOption2 (distractor)
            '',  # Medial (empty)
            '',  # MedialOption1
            '',  # MedialOption2
            'ī',  # TonedFinal
            'ī',  # TonedFinalOption1 (correct)
            'í',  # TonedFinalOption2 (distractor)
            'shī',  # Pinyin
            'simplified',  # Config
            '{"card_type": "chinese_naming", "knowledge_points": []}',  # _KG_Map
            'Chinese Naming - 狮子 (Lion) - Syllable 1/2: shī - Easy (Template Example)'  # _Remarks
        ]
    )
    
    sample_note_harder = genanki.Note(
        model=model,
        fields=[
            'Lion',  # Concept
            '<img src="lion.png" alt="Lion">',  # Image (sample reference)
            '',  # Audio
            'harder',  # Difficulty
            'shī',  # Syllable
            'shī zi',  # FullPinyin
            '1',  # SyllableIndex
            '2',  # TotalSyllables
            'shī',  # SyllableOption1
            'shí',  # SyllableOption2
            'mā',  # SyllableOption3
            'zī',  # SyllableOption4
            'sh',  # Initial
            'sh',  # InitialOption1 (correct)
            'zh',  # InitialOption2 (distractor)
            '',  # Medial
            '',  # MedialOption1
            '',  # MedialOption2
            'ī',  # TonedFinal
            'ī',  # TonedFinalOption1 (correct)
            'í',  # TonedFinalOption2 (distractor)
            'shī',  # Pinyin
            'simplified',  # Config
            '{"card_type": "chinese_naming", "knowledge_points": []}',  # _KG_Map
            'Chinese Naming - 狮子 (Lion) - Syllable 1/2: shī - Harder (Template Example)'  # _Remarks
        ]
    )
    
    # Add notes to deck
    # Only add one sample note (Easy) to avoid confusion
    # Users can delete it after verifying the template works
    deck.add_note(sample_note_easy)
    
    # Remove the harder note - we only need one sample to verify the template
    # The harder card template will be tested when real notes are synced
    
    # Create a package
    package = genanki.Package(deck)
    package.models = [model]  # Include the model in the package
    
    # Try to find and add a lion image if it exists
    # This ensures the sample note displays correctly
    lion_image_paths = [
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "lion.png",
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "Lion.png",
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "lion.jpg",
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "Lion.jpg",
    ]
    
    lion_image_found = None
    for img_path in lion_image_paths:
        if img_path.exists():
            lion_image_found = img_path
            break
    
    if lion_image_found:
        # Add the image to the package
        package.media_files = [str(lion_image_found)]
        print(f"   📷 Found and included image: {lion_image_found.name}")
    else:
        print(f"   ⚠️  Lion image not found. Sample note will show broken image.")
        print(f"      (This is OK - real cards will have images synced from the app)")
    
    # Save the package
    output_file = PROJECT_ROOT / "data" / "content_db" / "CUMA_Chinese_Naming_Template.apkg"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    package.write_to_file(str(output_file))
    
    print(f"✅ Created Anki package: {output_file}")
    print(f"   - Note type: CUMA - Chinese Naming")
    print(f"   - Sample notes: 2 (one Easy, one Harder card for 'shī' - lion)")
    print(f"\n📋 To import the note type:")
    print(f"   1. Open Anki")
    print(f"   2. File → Import")
    print(f"   3. Select: {output_file}")
    print(f"   4. The note type 'CUMA - Chinese Naming' will be created automatically!")
    print(f"   5. You'll see 1 sample card in the deck (you can delete it after verifying)")
    print(f"\n   After import, you can use this note type to sync Chinese naming cards from the app.")
    
    return output_file


def import_via_anki_connect():
    """Try to import the package via AnkiConnect"""
    
    anki = AnkiConnect()
    
    if not anki.ping():
        print("⚠️  AnkiConnect not available. Please import manually.")
        return False
    
    print("\n📦 Attempting to import via AnkiConnect...")
    
    output_file = PROJECT_ROOT / "data" / "content_db" / "CUMA_Chinese_Naming_Template.apkg"
    
    if not output_file.exists():
        print(f"❌ Package file not found: {output_file}")
        return False
    
    try:
        # AnkiConnect doesn't have a direct importPackage action
        # But we can check if the model exists
        model_names = anki._invoke("modelNames")
        if "CUMA - Chinese Naming" in model_names:
            print("✅ Note type 'CUMA - Chinese Naming' already exists in Anki!")
            return True
        else:
            print("⚠️  Note type not found. Please import the .apkg file manually:")
            print(f"   {output_file}")
            return False
    except Exception as e:
        print(f"⚠️  Could not check Anki: {e}")
        print(f"   Please import manually: {output_file}")
        return False


if __name__ == "__main__":
    # Create the package
    package_file = create_template_package()
    
    # Try to check if it can be imported via AnkiConnect
    import_via_anki_connect()

