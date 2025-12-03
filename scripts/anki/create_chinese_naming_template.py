#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create "CUMA - Chinese Naming" note type in Anki with templates.

This script uses AnkiConnect to check if the note type exists,
and if not, provides instructions or attempts to create it using Anki's Python API.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from anki_integration.anki_connect import AnkiConnect


def create_chinese_naming_template():
    """Create CUMA - Chinese Naming note type in Anki"""
    
    anki = AnkiConnect()
    
    # Check connection
    if not anki.ping():
        print("❌ Error: Cannot connect to Anki. Make sure Anki is running with AnkiConnect add-on installed.")
        return False
    
    print("✅ Connected to AnkiConnect")
    
    # Check if note type already exists
    try:
        model_names = anki._invoke("modelNames")
        if "CUMA - Chinese Naming" in model_names:
            print("✅ Note type 'CUMA - Chinese Naming' already exists")
            response = input("Do you want to update it? (y/N): ")
            if response.lower() != 'y':
                print("Skipping update.")
                return True
    except Exception as e:
        print(f"⚠️  Warning: Could not check existing note types: {e}")
    
    # AnkiConnect doesn't support creating note types directly
    # We need to use Anki's Python API or provide manual instructions
    print("\n📝 Creating note type using Anki's Python API...")
    
    try:
        # Try to import anki library
        try:
            from anki.models import ModelManager, NotetypeDict
            from anki.collection import Collection
            from anki import hooks
            import anki
        except ImportError:
            print("❌ Anki Python library not found.")
            print("   Please install it: pip install anki")
            print("\n📋 Manual Setup Instructions:")
            print_manual_instructions()
            return False
        
        # Get Anki collection path
        import anki.collection
        import anki.storage
        
        # Try to find Anki collection
        # Anki stores collection in user's Anki folder
        import platform
        if platform.system() == "Darwin":  # macOS
            anki_path = Path.home() / "Library/Application Support/Anki2"
        elif platform.system() == "Windows":
            anki_path = Path(os.getenv("APPDATA", "")) / "Anki2"
        else:  # Linux
            anki_path = Path.home() / ".local/share/Anki2"
        
        # Find the default profile's collection
        profile_dirs = list(anki_path.glob("User *")) if anki_path.exists() else []
        if not profile_dirs:
            print(f"❌ Could not find Anki profile directory at {anki_path}")
            print("\n📋 Manual Setup Instructions:")
            print_manual_instructions()
            return False
        
        # Use the first profile (or ask user)
        profile_path = profile_dirs[0]
        collection_path = profile_path / "collection.anki2"
        
        if not collection_path.exists():
            print(f"❌ Could not find collection at {collection_path}")
            print("\n📋 Manual Setup Instructions:")
            print_manual_instructions()
            return False
        
        print(f"📂 Found Anki collection: {collection_path}")
        
        # Open collection
        try:
            col = Collection(str(collection_path))
        except Exception as e:
            # Try Anki 2.1.x style
            try:
                col = collection.Collection(str(collection_path))
            except Exception as e2:
                print(f"❌ Could not open collection: {e}, {e2}")
                print("\n📋 Manual Setup Instructions:")
                print_manual_instructions()
                return False
        
        # Create the note type
        try:
            mm = col.models
            model = mm.new("CUMA - Chinese Naming")
        except AttributeError:
            # Try Anki 2.1.x style
            mm = col.models
            model = mm.new("CUMA - Chinese Naming")
        
        # Add fields
        fields_to_add = [
            "Concept", "Image", "Audio", "Difficulty", "Syllable", "FullPinyin",
            "SyllableIndex", "TotalSyllables",
            # Easy mode fields
            "SyllableOption1", "SyllableOption2", "SyllableOption3", "SyllableOption4",
            # Harder mode fields
            "Initial", "InitialOption1", "InitialOption2",
            "Medial", "MedialOption1", "MedialOption2",
            "TonedFinal", "TonedFinalOption1", "TonedFinalOption2",
            "Pinyin", "Config", "_KG_Map", "_Remarks"
        ]
        
        for field_name in fields_to_add:
            field = mm.new_field(field_name)
            mm.add_field(model, field)
        
        # Create card templates
        # Card 1: Easy (Multiple Choice)
        card1 = mm.new_template("Easy - Select Syllable")
        card1['qfmt'] = get_easy_front_template()
        card1['afmt'] = get_easy_back_template()
        mm.add_template(model, card1)
        
        # Card 2: Harder (Construction)
        card2 = mm.new_template("Harder - Construct Syllable")
        card2['qfmt'] = get_harder_front_template()
        card2['afmt'] = get_harder_back_template()
        mm.add_template(model, card2)
        
        # Add CSS
        model['css'] = get_css()
        
        # Save
        mm.add(model)
        col.save()
        col.close()
        
        print("✅ Successfully created 'CUMA - Chinese Naming' note type!")
        print("   - Fields: " + ", ".join(fields_to_add))
        print("   - Cards: Easy (Multiple Choice), Harder (Construction)")
        return True
        
    except Exception as e:
        print(f"❌ Error creating note type: {e}")
        import traceback
        traceback.print_exc()
        print("\n📋 Manual Setup Instructions:")
        print_manual_instructions()
        return False


def get_easy_front_template():
    """Get front template for Easy (Multiple Choice) card"""
    return """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  <div class="audio">
    {{Audio}}
  </div>
  <div class="instruction">
    {{#Config}}
      {{#Config=simplified}}
        <p>点击选择正确的拼音音节：</p>
      {{/Config=simplified}}
      {{#Config=traditional}}
        <p>點擊選擇正確的拼音音節：</p>
      {{/Config=traditional}}
    {{/Config}}
    {{#TotalSyllables}}
      {{#TotalSyllables=1}}
        <!-- Single syllable word -->
      {{/TotalSyllables=1}}
      {{#TotalSyllables}}
        <p class="syllable-indicator">音节 {{SyllableIndex}}/{{TotalSyllables}}</p>
      {{/TotalSyllables}}
    {{/TotalSyllables}}
  </div>
  
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
    // Highlight correct answer
    buttons.forEach(btn => {
      if (btn.textContent.trim() === correct) {
        btn.classList.add('selected');
      }
    });
  }
}
</script>"""


def get_easy_back_template():
    """Get back template for Easy (Multiple Choice) card"""
    return """{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案 (Correct Answer):</strong></p>
  <div class="correct-syllable">
    {{Syllable}}
  </div>
  <p class="full-pinyin">完整拼音: {{FullPinyin}}</p>
  <p class="concept">概念: {{Concept}}</p>
</div>"""


def get_harder_front_template():
    """Get front template for Harder (Construction) card"""
    return """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  <div class="audio">
    {{Audio}}
  </div>
  <div class="instruction">
    {{#Config}}
      {{#Config=simplified}}
        <p>点击声母、介音、韵母来构建拼音：</p>
      {{/Config=simplified}}
      {{#Config=traditional}}
        <p>點擊聲母、介音、韻母來構建拼音：</p>
      {{/Config=traditional}}
    {{/Config}}
    {{#TotalSyllables}}
      {{#TotalSyllables=1}}
        <!-- Single syllable word -->
      {{/TotalSyllables=1}}
      {{#TotalSyllables}}
        <p class="syllable-indicator">音节 {{SyllableIndex}}/{{TotalSyllables}}</p>
      {{/TotalSyllables}}
    {{/TotalSyllables}}
  </div>
  
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


def get_harder_back_template():
    """Get back template for Harder (Construction) card"""
    return """{{FrontSide}}

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


def get_css():
    """Get CSS styling for the cards"""
    return """.cuma-naming-card {
  font-family: Arial, sans-serif;
  padding: 20px;
}

.concept-image img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.pinyin-construction {
  margin-top: 20px;
}

.component-group {
  margin-bottom: 20px;
  padding: 15px;
  border-radius: 8px;
}

.initial-group {
  background-color: #e3f2fd;
  border: 2px solid #2196F3;
}

.medial-group {
  background-color: #f3e5f5;
  border: 2px solid #9C27B0;
}

.final-group {
  background-color: #fff3e0;
  border: 2px solid #FF9800;
}

.component-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 16px;
}

.options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.option-btn, .syllable-option-btn {
  padding: 12px 24px;
  font-size: 18px;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: white;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 60px;
}

.option-btn:hover, .syllable-option-btn:hover {
  background-color: #f5f5f5;
  border-color: #999;
}

.option-btn.selected, .syllable-option-btn.selected {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
}

.option-btn.wrong, .syllable-option-btn.wrong {
  background-color: #f44336;
  color: white;
  border-color: #f44336;
}

.constructed-pinyin {
  margin-top: 20px;
  padding: 15px;
  background-color: #f9f9f9;
  border: 2px solid #ddd;
  border-radius: 8px;
  font-size: 24px;
  text-align: center;
  min-height: 50px;
}

.constructed-pinyin span {
  margin: 0 5px;
  font-weight: bold;
}

.correct-pinyin, .correct-syllable {
  font-size: 24px;
  margin: 10px 0;
}

.initial-component {
  color: #2196F3;
  font-weight: bold;
}

.medial-component {
  color: #9C27B0;
  font-weight: bold;
}

.final-component {
  color: #FF9800;
  font-weight: bold;
}

.full-pinyin {
  font-size: 18px;
  color: #666;
  margin-top: 10px;
}

.concept {
  font-size: 16px;
  color: #333;
  margin-top: 5px;
}

.syllable-indicator {
  font-size: 14px;
  color: #666;
  font-style: italic;
}

.syllable-multiple-choice {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 20px;
}

.instruction {
  margin-bottom: 20px;
}

.answer-section {
  margin-top: 20px;
  padding: 15px;
  background-color: #f0f8ff;
  border-radius: 8px;
}"""


def print_manual_instructions():
    """Print manual setup instructions"""
    print("""
📋 Manual Setup Instructions for "CUMA - Chinese Naming" Note Type:

1. Open Anki
2. Go to Tools → Manage Note Types
3. Click "Add" → "Add: Basic"
4. Name it: "CUMA - Chinese Naming"
5. Click "Fields..." and add all these fields:
   - Concept, Image, Audio, Difficulty, Syllable, FullPinyin
   - SyllableIndex, TotalSyllables
   - SyllableOption1, SyllableOption2, SyllableOption3, SyllableOption4
   - Initial, InitialOption1, InitialOption2
   - Medial, MedialOption1, MedialOption2
   - TonedFinal, TonedFinalOption1, TonedFinalOption2
   - Pinyin, Config, _KG_Map, _Remarks

6. Click "Cards..." and:
   - Add 2 cards: "Easy - Select Syllable" and "Harder - Construct Syllable"
   - Copy the templates from: docs/anki_templates/CUMA_CHINESE_NAMING.md
   - Copy the CSS from the same file

7. Save

See docs/anki_templates/CUMA_CHINESE_NAMING.md for complete templates.
""")


if __name__ == "__main__":
    print("🚀 Creating CUMA - Chinese Naming note type in Anki...\n")
    success = create_chinese_naming_template()
    if success:
        print("\n✅ Done! The note type is ready to use.")
    else:
        print("\n⚠️  Please follow the manual instructions above.")

