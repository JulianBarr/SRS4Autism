# CUMA - Chinese Naming Note Type

## Overview

This note type is designed for **Layer 0 Cognition** training, focusing on **Concept ⇔ Pinyin** mapping through **construction** rather than dictation.

Based on the design principles in `Layer 0.md`:
- Uses **Initial (声母)**, **Medial (介音)**, and **Toned Final (韵母+声调)** components
- **Click-based** interface (not drag-and-drop) - easier for autistic children
- **No Chinese characters** displayed (reduces cognitive load)
- Each component has a **distractor** option
- Components are **color-coded** for visual distinction
- Supports **Simplified (Hanyu Pinyin)** or **Traditional (Bopomofo)** configuration

## Fields

| Field Name | Description | Example |
|------------|-------------|---------|
| `Concept` | English concept/word | "Lion" |
| `Image` | Picture of the concept | `<img src="lion.jpg">` |
| `Audio` | Audio pronunciation | `[sound:lion.mp3]` |
| `Difficulty` | Card difficulty: "easy" or "harder" | "easy" |
| `Syllable` | Current syllable being practiced | "shī" |
| `FullPinyin` | Full word pinyin | "shī zi" |
| `SyllableIndex` | Which syllable (1, 2, 3...) | "1" |
| `TotalSyllables` | Total syllables in word | "2" |
| **Easy Mode Fields (Multiple Choice):** | | |
| `SyllableOption1` | First syllable option | "shī" |
| `SyllableOption2` | Second syllable option (distractor) | "shí" |
| `SyllableOption3` | Third syllable option (distractor) | "mā" |
| `SyllableOption4` | Fourth syllable option (distractor) | "zī" |
| **Harder Mode Fields (Construction):** | | |
| `Initial` | Correct initial (声母) | "sh" |
| `InitialOption1` | First initial option | "sh" |
| `InitialOption2` | Second initial option (distractor) | "zh" |
| `Medial` | Correct medial (介音), if any | "" (empty if none) |
| `MedialOption1` | First medial option | "" |
| `MedialOption2` | Second medial option (distractor) | "" |
| `TonedFinal` | Correct toned final (韵母+声调) | "ī" |
| `TonedFinalOption1` | First final option | "ī" |
| `TonedFinalOption2` | Second final option (distractor) | "í" |
| `Pinyin` | Current syllable pinyin | "shī" |
| `Config` | Configuration: "simplified" or "traditional" | "simplified" |
| `_KG_Map` | Knowledge graph mapping (JSON) | `{"knowledge_points": [...]}` |
| `_Remarks` | Notes/remarks | "Chinese Naming - 狮子 (Lion) - Syllable 1/2: shī - Easy" |

## Card Templates

### Card 1: Picture → Select Syllable (Easy - Multiple Choice)

**Front Template:**
```html
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
```

**Back Template:**
```html
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
```

### Card 2: Picture → Construct Pinyin (Harder - Component Building)

**Front Template:**
```html
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
  </div>
  
  <div class="pinyin-construction">
    <!-- Initial -->
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
    
    <!-- Constructed Pinyin Display -->
    <div class="constructed-pinyin">
      <span id="selected-initial"></span>
      <span id="selected-medial"></span>
      <span id="selected-final"></span>
    </div>
  </div>
</div>
```

**Back Template:**
```html
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案 (Correct Answer):</strong></p>
  <div class="correct-pinyin">
    <span class="initial-component">{{Initial}}</span>
    {{#Medial}}<span class="medial-component">{{Medial}}</span>{{/Medial}}
    <span class="final-component">{{TonedFinal}}</span>
  </div>
  <p class="full-pinyin">完整拼音: {{Pinyin}}</p>
  <p class="concept">概念: {{Concept}}</p>
</div>
```

### Card 2: Audio → Construct Pinyin

**Front Template:**
```html
<div class="cuma-naming-card">
  <div class="audio-only">
    {{Audio}}
    <p>听音频，构建拼音：</p>
  </div>
  
  <!-- Same construction interface as Card 1 -->
  <!-- (Copy the pinyin-construction div from Card 1) -->
</div>
```

**Back Template:**
```html
{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <!-- Same answer section as Card 1 -->
</div>
```

## Styling (CSS)

```css
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
  background-color: #e3f2fd; /* Light blue */
  border: 2px solid #2196F3;
}

.medial-group {
  background-color: #f3e5f5; /* Light purple */
  border: 2px solid #9C27B0;
}

.final-group {
  background-color: #fff3e0; /* Light orange */
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

.option-btn {
  padding: 12px 24px;
  font-size: 18px;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: white;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 60px;
}

.option-btn:hover {
  background-color: #f5f5f5;
  border-color: #999;
}

.option-btn.selected {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
}

.option-btn.wrong {
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

.correct-pinyin {
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
```

## JavaScript (for Interactive Selection)

Add this to the card template's JavaScript section:

```javascript
let selectedComponents = {
  initial: null,
  medial: null,
  final: null
};

function selectOption(button, componentType) {
  // Remove previous selection in this group
  const group = button.closest('.component-group');
  group.querySelectorAll('.option-btn').forEach(btn => {
    btn.classList.remove('selected');
  });
  
  // Mark this button as selected
  button.classList.add('selected');
  selectedComponents[componentType] = button.textContent.trim();
  
  // Update constructed pinyin display
  updateConstructedPinyin();
  
  // Check if all components are selected (for auto-reveal, if desired)
  // checkCompletion();
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
```

## Setup Instructions

1. **Create Note Type in Anki:**
   - Tools → Manage Note Types → Add
   - Clone from: "Basic"
   - Name: "CUMA - Chinese Naming"

2. **Add Fields:**
   - Concept (Text)
   - Image (Text)
   - Audio (Text)
   - Initial (Text)
   - InitialOption1 (Text)
   - InitialOption2 (Text)
   - Medial (Text)
   - MedialOption1 (Text)
   - MedialOption2 (Text)
   - TonedFinal (Text)
   - TonedFinalOption1 (Text)
   - TonedFinalOption2 (Text)
   - Pinyin (Text)
   - Config (Text)
   - _KG_Map (Text)
   - _Remarks (Text)

3. **Add Card Templates:**
   - Add 2 cards (Picture→Pinyin, Audio→Pinyin)
   - Copy the templates above
   - Add the CSS styling
   - Add the JavaScript for interactivity

4. **Test:**
   - Create a test note manually
   - Verify the construction interface works
   - Check that colors and styling are correct

## Usage

The system will automatically:
- Parse pinyin into components
- Generate distractors
- Create notes with all required fields
- Sync to Anki using this note type

Users can then:
- Click components to construct pinyin
- See visual feedback (colors, selection)
- Learn through construction rather than dictation
- Focus on concept-to-sound mapping without character reading

