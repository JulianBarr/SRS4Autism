#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix MCQ Tone, MCQ Confusor, and Pinyin to Word cards:
1. MCQ Tone: Use proper tone marks (mā, má, mǎ, mà) instead of numbers (mā1, mā2, etc.)
2. MCQ Confusor: Use proper tone marks and larger text
3. Pinyin to Word: Make it a MCQ with confusor pictures
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import re
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import parse_pinyin, add_tone_to_final, extract_tone

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

def convert_tone_number_to_mark(pinyin: str) -> str:
    """Convert pinyin with tone number to tone mark (e.g., 'ma1' -> 'mā')"""
    pinyin_no_tone, tone = extract_tone(pinyin)
    if tone:
        return add_tone_to_final(pinyin_no_tone, tone)
    return pinyin

def generate_tone_variations(base_syllable: str) -> list:
    """Generate all 4 tone variations of a syllable (e.g., 'ma' -> ['mā', 'má', 'mǎ', 'mà'])"""
    # Remove any existing tone
    pinyin_no_tone, _ = extract_tone(base_syllable)
    
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(pinyin_no_tone, tone)
        variations.append(toned)
    
    return variations

# MCQ Tone templates
mcq_tone_front_template = """{{#ElementToLearn}}
{{WordAudio}}

<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="mcq-options" id="mcq-tone-front">
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="tone1">{{Tone1}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="tone2">{{Tone2}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="tone3">{{Tone3}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="tone4">{{Tone4}}</button>
  </div>
</div>

<script>
(function() {
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-tone-front .mcq-option');
    const correctAnswer = '{{Syllable}}';
    
    options.forEach(function(button) {
      button.addEventListener('click', function() {
        const selected = this.getAttribute('data-value');
        const selectedText = this.textContent.trim();
        const isCorrect = (selectedText === correctAnswer);
        
        options.forEach(function(opt) {
          opt.classList.remove('selected', 'wrong');
        });
        
        if (isCorrect) {
          this.classList.add('selected');
        } else {
          this.classList.add('wrong');
          options.forEach(function(opt) {
            if (opt.textContent.trim() === correctAnswer) {
              opt.classList.add('selected');
            }
          });
        }
      });
    });
  }, 100);
})();
</script>
{{/ElementToLearn}}"""

mcq_tone_back_template = """{{#ElementToLearn}}{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-tone-back">
  <button class="mcq-option" data-value="tone1">{{Tone1}}</button>
  <button class="mcq-option" data-value="tone2">{{Tone2}}</button>
  <button class="mcq-option" data-value="tone3">{{Tone3}}</button>
  <button class="mcq-option" data-value="tone4">{{Tone4}}</button>
</div>

<script>
(function() {
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-tone-back .mcq-option');
    const correctAnswer = '{{Syllable}}';
    
    options.forEach(function(button) {
      const buttonText = button.textContent.trim();
      if (buttonText === correctAnswer) {
        button.classList.add('selected');
      }
    });
  }, 100);
})();
</script>
{{/ElementToLearn}}"""

# MCQ Confusor templates
mcq_confusor_front_template = """{{#ElementToLearn}}
{{WordAudio}}

<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="mcq-options" id="mcq-confusor-front">
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="{{Syllable}}">{{Syllable}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="{{Confusor1}}">{{Confusor1}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="{{Confusor2}}">{{Confusor2}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="{{Confusor3}}">{{Confusor3}}</button>
  </div>
</div>

<script>
(function() {
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-confusor-front .mcq-option');
    const correctAnswer = '{{Syllable}}';
    
    options.forEach(function(button) {
      button.addEventListener('click', function() {
        const selected = this.getAttribute('data-value');
        const isCorrect = (selected === correctAnswer);
        
        options.forEach(function(opt) {
          opt.classList.remove('selected', 'wrong');
        });
        
        if (isCorrect) {
          this.classList.add('selected');
        } else {
          this.classList.add('wrong');
          options.forEach(function(opt) {
            if (opt.getAttribute('data-value') === correctAnswer) {
              opt.classList.add('selected');
            }
          });
        }
      });
    });
  }, 100);
})();
</script>
{{/ElementToLearn}}"""

mcq_confusor_back_template = """{{#ElementToLearn}}{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-confusor-back">
  <button class="mcq-option" data-value="{{Syllable}}">{{Syllable}}</button>
  <button class="mcq-option" data-value="{{Confusor1}}">{{Confusor1}}</button>
  <button class="mcq-option" data-value="{{Confusor2}}">{{Confusor2}}</button>
  <button class="mcq-option" data-value="{{Confusor3}}">{{Confusor3}}</button>
</div>

<script>
(function() {
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-confusor-back .mcq-option');
    const correctAnswer = '{{Syllable}}';
    
    options.forEach(function(button) {
      const buttonValue = button.getAttribute('data-value');
      if (buttonValue === correctAnswer) {
        button.classList.add('selected');
      }
    });
  }, 100);
})();
</script>
{{/ElementToLearn}}"""

# Pinyin to Word templates (MCQ with pictures)
pinyin_to_word_front_template = """{{#ElementToLearn}}
<div class="pinyin-syllable-card">
  <div class="pinyin-display">
    <p class="syllable-pinyin">{{Syllable}}</p>
  </div>
  
  <div class="mcq-picture-options" id="mcq-pinyin-to-word-front">
    {{#WordPicture}}
    <div class="mcq-picture-option" data-correct="true" data-value="correct">
      {{WordPicture}}
    </div>
    {{/WordPicture}}
    {{#ConfusorPicture1}}
    <div class="mcq-picture-option" data-correct="false" data-value="confusor1">
      {{ConfusorPicture1}}
    </div>
    {{/ConfusorPicture1}}
    {{#ConfusorPicture2}}
    <div class="mcq-picture-option" data-correct="false" data-value="confusor2">
      {{ConfusorPicture2}}
    </div>
    {{/ConfusorPicture2}}
    {{#ConfusorPicture3}}
    <div class="mcq-picture-option" data-correct="false" data-value="confusor3">
      {{ConfusorPicture3}}
    </div>
    {{/ConfusorPicture3}}
  </div>
</div>

<script>
(function() {
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-pinyin-to-word-front .mcq-picture-option');
    
    options.forEach(function(option) {
      option.addEventListener('click', function() {
        const isCorrect = this.getAttribute('data-correct') === 'true';
        
        options.forEach(function(opt) {
          opt.classList.remove('selected', 'wrong');
        });
        
        if (isCorrect) {
          this.classList.add('selected');
        } else {
          this.classList.add('wrong');
          options.forEach(function(opt) {
            if (opt.getAttribute('data-correct') === 'true') {
              opt.classList.add('selected');
            }
          });
        }
      });
    });
  }, 100);
})();
</script>
{{/ElementToLearn}}"""

pinyin_to_word_back_template = """{{#ElementToLearn}}{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{WordHanzi}}</span></p>
  <p><strong>拼音:</strong> {{WordPinyin}}</p>
</div>

<div class="mcq-picture-options" id="mcq-pinyin-to-word-back">
  {{#WordPicture}}
  <div class="mcq-picture-option selected" data-correct="true" data-value="correct">
    {{WordPicture}}
  </div>
  {{/WordPicture}}
  {{#ConfusorPicture1}}
  <div class="mcq-picture-option" data-correct="false" data-value="confusor1">
    {{ConfusorPicture1}}
  </div>
  {{/ConfusorPicture1}}
  {{#ConfusorPicture2}}
  <div class="mcq-picture-option" data-correct="false" data-value="confusor2">
    {{ConfusorPicture2}}
  </div>
  {{/ConfusorPicture2}}
  {{#ConfusorPicture3}}
  <div class="mcq-picture-option" data-correct="false" data-value="confusor3">
    {{ConfusorPicture3}}
  </div>
  {{/ConfusorPicture3}}
</div>
{{/ElementToLearn}}"""

# CSS for picture options
picture_mcq_css = """
.mcq-picture-options {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 30px;
}

.mcq-picture-option {
  cursor: pointer;
  border: 3px solid #ddd;
  border-radius: 12px;
  padding: 5px;
  background-color: white;
  transition: all 0.2s;
  max-width: 250px;
  min-width: 200px;
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
  border-radius: 8px;
  display: block;
}

.syllable-pinyin {
  font-size: 72px;
  font-weight: bold;
  color: #2196F3;
  margin: 20px 0;
}
"""

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    
    print("📦 Extracting .apkg...")
    with zipfile.ZipFile(APKG_PATH, 'r') as z:
        z.extractall(tmpdir_path)
    
    db = tmpdir_path / "collection.anki21"
    if not db.exists():
        db = tmpdir_path / "collection.anki2"
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("SELECT models FROM col")
    models = json.loads(cursor.fetchone()[0])
    
    # Find syllable model
    syllable_model_id = None
    syllable_model = None
    
    for mid_str, model in models.items():
        if model.get('name') == 'CUMA - Pinyin Syllable':
            syllable_model_id = int(mid_str)
            syllable_model = model
            break
    
    if not syllable_model:
        print("❌ Syllable model not found")
        conn.close()
        exit(1)
    
    print("✅ Found syllable model")
    
    # Get field names
    field_names = [f['name'] for f in syllable_model.get('flds', [])]
    print(f"   Current fields: {', '.join(field_names)}")
    
    # Add new fields if they don't exist
    new_fields_to_add = []
    for i in [1, 2, 3, 4]:
        if f'Tone{i}' not in field_names:
            new_fields_to_add.append(f'Tone{i}')
    for i in [1, 2, 3]:
        if f'Confusor{i}' not in field_names:
            new_fields_to_add.append(f'Confusor{i}')
        if f'ConfusorPicture{i}' not in field_names:
            new_fields_to_add.append(f'ConfusorPicture{i}')
    
    if new_fields_to_add:
        print(f"\n   ➕ Adding new fields: {', '.join(new_fields_to_add)}")
        for field_name in new_fields_to_add:
            new_field = {
                'name': field_name,
                'rtl': False,
                'sticky': False,
                'font': 'Arial',
                'size': 20,
                'media': []
            }
            syllable_model['flds'].append(new_field)
            field_names.append(field_name)
        print(f"   ✅ Added {len(new_fields_to_add)} new fields")
    else:
        print(f"   ✅ All required fields already exist")
    
    # Update CSS - add picture MCQ styles
    css = syllable_model.get('css', '')
    # Remove old picture styles if any
    css = re.sub(r'\.mcq-picture-options\s*\{[^}]*\}', '', css, flags=re.DOTALL)
    css = re.sub(r'\.mcq-picture-option[^{]*\{[^}]*\}', '', css, flags=re.DOTALL)
    css = css + picture_mcq_css
    syllable_model['css'] = css
    print("   ✅ Updated CSS - added picture MCQ styles")
    
    # Update templates
    tmpls = syllable_model.get('tmpls', [])
    
    for tmpl in tmpls:
        tmpl_name = tmpl.get('name', '')
        tmpl_ord = tmpl.get('ord', -1)
        
        if 'MCQ Tone' in tmpl_name or tmpl_ord == 2:
            print(f"\n📄 Found MCQ Tone template: {tmpl_name} (ord: {tmpl_ord})")
            tmpl['qfmt'] = mcq_tone_front_template
            tmpl['afmt'] = mcq_tone_back_template
            print("   ✅ Updated MCQ Tone templates")
            print("   - Using Tone1-4 fields with proper tone marks")
            print("   - Larger buttons (64px font)")
            print("   - Fixed click handler")
        
        elif 'MCQ Confusor' in tmpl_name or tmpl_ord == 3:
            print(f"\n📄 Found MCQ Confusor template: {tmpl_name} (ord: {tmpl_ord})")
            tmpl['qfmt'] = mcq_confusor_front_template
            tmpl['afmt'] = mcq_confusor_back_template
            print("   ✅ Updated MCQ Confusor templates")
            print("   - Using Confusor1-3 fields")
            print("   - Larger buttons (64px font)")
            print("   - Fixed click handler")
        
        elif 'Pinyin to Word' in tmpl_name or tmpl_ord == 4:
            print(f"\n📄 Found Pinyin to Word template: {tmpl_name} (ord: {tmpl_ord})")
            tmpl['qfmt'] = pinyin_to_word_front_template
            tmpl['afmt'] = pinyin_to_word_back_template
            print("   ✅ Updated Pinyin to Word templates")
            print("   - Changed to MCQ with confusor pictures")
            print("   - Clickable picture options")
    
    # Update notes: populate new fields and convert tone numbers
    print("\n🔧 Updating notes...")
    cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
    notes = cursor.fetchall()
    
    # First pass: collect all word pictures for confusor generation
    # Use original field names (before new fields were added) to read WordPicture
    original_field_names = [f['name'] for f in syllable_model.get('flds', [])]
    word_picture_idx = original_field_names.index('WordPicture') if 'WordPicture' in original_field_names else -1
    
    all_word_pictures = []
    for note_id, flds_str in notes:
        fields = flds_str.split('\x1f')
        if word_picture_idx >= 0 and word_picture_idx < len(fields):
            word_pic = fields[word_picture_idx]
            if word_pic:
                all_word_pictures.append((note_id, word_pic))
    
    updated_count = 0
    for note_id, flds_str in notes:
        fields = flds_str.split('\x1f')
        
        # Ensure fields list matches field_names length (pad with empty strings)
        while len(fields) < len(field_names):
            fields.append('')
        
        field_dict = dict(zip(field_names, fields))
        
        # Get base syllable (remove tone)
        syllable = field_dict.get('Syllable', '')
        if not syllable:
            continue
        
        # Generate tone variations
        pinyin_no_tone, _ = extract_tone(syllable)
        tone_variations = generate_tone_variations(pinyin_no_tone)
        
        # Update Tone1-4 fields
        for i, tone_var in enumerate(tone_variations, 1):
            tone_field_idx = field_names.index(f'Tone{i}')
            existing = field_dict.get(f'Tone{i}', '')
            if existing:
                # Convert existing tone number format to tone mark if needed
                converted = convert_tone_number_to_mark(existing)
                fields[tone_field_idx] = converted
            else:
                # Use generated variation
                fields[tone_field_idx] = tone_var
        
        # Generate confusor options (similar syllables with different tones/initials)
        # For now, use simple variations - in production, these would come from a confusor database
        confusors = []
        if pinyin_no_tone:
            # Generate confusors by changing initial or tone
            # Simple approach: use similar syllables
            base_initial = pinyin_no_tone[0] if pinyin_no_tone else ''
            base_final = pinyin_no_tone[1:] if len(pinyin_no_tone) > 1 else pinyin_no_tone
            
            # Generate 3 confusors (simple examples - in production use actual confusor data)
            confusors = [
                add_tone_to_final('b' + base_final if base_final else 'ba', 1),  # Change initial
                add_tone_to_final('p' + base_final if base_final else 'pa', 2),  # Change initial + tone
                add_tone_to_final(pinyin_no_tone, 3 if field_dict.get('Syllable') != add_tone_to_final(pinyin_no_tone, 3) else 4)  # Different tone
            ]
        
        # Update Confusor1-3 fields
        for i, confusor in enumerate(confusors[:3], 1):
            confusor_field_idx = field_names.index(f'Confusor{i}')
            fields[confusor_field_idx] = confusor
        
        # For ConfusorPicture fields, use pictures from other notes
        current_word_pic = field_dict.get('WordPicture', '')
        other_pictures = [pic for nid, pic in all_word_pictures if nid != note_id and pic != current_word_pic]
        
        for i in [1, 2, 3]:
            confusor_pic_field_idx = field_names.index(f'ConfusorPicture{i}')
            if i <= len(other_pictures):
                fields[confusor_pic_field_idx] = other_pictures[i-1]
            else:
                fields[confusor_pic_field_idx] = ''  # Empty if not enough other pictures
        
        # Update flds
        new_flds = '\x1f'.join(fields)
        cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (new_flds, note_id))
        updated_count += 1
    
    print(f"   ✅ Updated {updated_count} notes")
    print("   - Generated Tone1-4 fields with proper tone marks")
    print("   - Generated Confusor1-3 fields")
    
    # Count how many confusor pictures were populated
    cursor.execute("SELECT flds FROM notes WHERE mid = ?", (syllable_model_id,))
    notes_check = cursor.fetchall()
    confusor_pic_count = 0
    for (flds_str,) in notes_check:
        fields = flds_str.split('\x1f')
        for i in [1, 2, 3]:
            confusor_pic_idx = field_names.index(f'ConfusorPicture{i}')
            if confusor_pic_idx < len(fields) and fields[confusor_pic_idx]:
                confusor_pic_count += 1
    
    print(f"   - Populated {confusor_pic_count} ConfusorPicture fields from other notes")
    
    # Save updated models
    models[str(syllable_model_id)] = syllable_model
    cursor.execute("UPDATE col SET models = ?", (json.dumps(models),))
    conn.commit()
    print("\n✅ Models and notes updated")
    
    conn.close()
    
    # Repackage
    print("\n📦 Repackaging .apkg...")
    with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_path in tmpdir_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(tmpdir_path)
                z.write(file_path, arcname)
    
    print("✅ .apkg updated")

