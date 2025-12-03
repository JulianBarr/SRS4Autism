#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate template code for "CUMA - Chinese Naming" note type.

This script generates a complete template file that can be used
to manually create the note type in Anki, or imported programmatically.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "docs" / "anki_templates" / "CUMA_CHINESE_NAMING_TEMPLATE_CODE.txt"


def generate_template_code():
    """Generate complete template code for Anki"""
    
    template_code = """# CUMA - Chinese Naming Note Type - Complete Template Code
# Copy and paste this into Anki's note type editor

## Fields to Add (in order):
Concept
Image
Audio
Difficulty
Syllable
FullPinyin
SyllableIndex
TotalSyllables
SyllableOption1
SyllableOption2
SyllableOption3
SyllableOption4
Initial
InitialOption1
InitialOption2
Medial
MedialOption1
MedialOption2
TonedFinal
TonedFinalOption1
TonedFinalOption2
Pinyin
Config
_KG_Map
_Remarks

## Card 1: Easy - Select Syllable

### Front Template:
<div class="cuma-naming-card">
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
    buttons.forEach(btn => {
      if (btn.textContent.trim() === correct) {
        btn.classList.add('selected');
      }
    });
  }
}
</script>

### Back Template:
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案 (Correct Answer):</strong></p>
  <div class="correct-syllable">
    {{Syllable}}
  </div>
  <p class="full-pinyin">完整拼音: {{FullPinyin}}</p>
  <p class="concept">概念: {{Concept}}</p>
</div>

## Card 2: Harder - Construct Syllable

### Front Template:
<div class="cuma-naming-card">
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
</script>

### Back Template:
{{FrontSide}}

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
</div>

## CSS Styling (paste into "Styling" section):

.cuma-naming-card {
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
}

## Setup Instructions:

1. Open Anki
2. Go to Tools → Manage Note Types
3. Click "Add" → "Add: Basic"
4. Name it: "CUMA - Chinese Naming"
5. Click "Fields..." and add all the fields listed above (in order)
6. Click "Cards..." and:
   - Add Card 1: Name it "Easy - Select Syllable", paste Front and Back templates
   - Add Card 2: Name it "Harder - Construct Syllable", paste Front and Back templates
   - Paste the CSS into the "Styling" section (shared for both cards)
7. Save

Done! The note type is ready to use.
"""
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(template_code, encoding='utf-8')
    
    print(f"✅ Generated template code file: {OUTPUT_FILE}")
    print(f"   You can now:")
    print(f"   1. Open this file and copy the templates")
    print(f"   2. Or run the create script which will use this code")
    return OUTPUT_FILE


if __name__ == "__main__":
    print("🚀 Generating CUMA - Chinese Naming template code...\n")
    output_file = generate_template_code()
    print(f"\n✅ Template code saved to: {output_file}")
    print("\n📋 Next steps:")
    print("   1. Open Anki")
    print("   2. Tools → Manage Note Types → Add → Basic")
    print("   3. Name it: 'CUMA - Chinese Naming'")
    print("   4. Follow the instructions in the generated file")

