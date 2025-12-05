#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update Card 2 (MCQ Recent) with requirements:
1. Remove instruction text
2. Make buttons and text larger
3. Fix click handler to work properly
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

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

mcq_front_template = """{{#ElementToLearn}}
<!-- Play WordAudio when front card loads -->
{{WordAudio}}

<div class="pinyin-syllable-card">
  {{#WordPicture}}
  <div class="word-picture">{{WordPicture}}</div>
  {{/WordPicture}}
  
  <div class="word-display">
    <p class="word-hanzi">{{WordHanzi}}</p>
  </div>
  
  <div class="mcq-options" id="mcq-recent-front">
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="{{Syllable}}">{{Syllable}}</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="mē">mē</button>
    <button class="mcq-option" data-correct="{{Syllable}}" data-value="mō">mō</button>
  </div>
</div>

<script>
(function() {
  window.ankiPinyinMCQRecent = ['{{Syllable}}', 'mē', 'mō'];
  
  setTimeout(function() {
    const options = document.querySelectorAll('#mcq-recent-front .mcq-option');
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

mcq_back_template = """{{#ElementToLearn}}{{FrontSide}}

<hr id="answer">

<div class="answer-section">
  <p><strong>正确答案:</strong> <span class="correct-answer">{{Syllable}}</span></p>
</div>

<div class="mcq-options" id="mcq-recent-back">
  <button class="mcq-option selected">{{Syllable}}</button>
  <button class="mcq-option">mē</button>
  <button class="mcq-option">mō</button>
</div>
{{/ElementToLearn}}"""

new_mcq_css = """
.mcq-options {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 30px;
}

.mcq-option {
  padding: 30px 50px;
  font-size: 64px;
  font-weight: bold;
  border: 3px solid #ddd;
  border-radius: 12px;
  background-color: white;
  color: #333;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 200px;
  text-align: center;
  line-height: 1.2;
}

.mcq-option:hover {
  background-color: #f5f5f5;
  border-color: #999;
  transform: scale(1.05);
}

.mcq-option.selected {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
  border-width: 4px;
}

.mcq-option.wrong {
  background-color: #f44336;
  color: white;
  border-color: #f44336;
  border-width: 4px;
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
    
    # Update CSS - remove old MCQ styles and add new larger ones
    css = syllable_model.get('css', '')
    css = re.sub(r'\.mcq-options\s*\{[^}]*\}', '', css, flags=re.DOTALL)
    css = re.sub(r'\.mcq-option[^{]*\{[^}]*\}', '', css, flags=re.DOTALL)
    css = css + new_mcq_css
    syllable_model['css'] = css
    print("   ✅ Updated CSS - larger buttons and text")
    
    # Find Card 2 (MCQ Recent) template
    tmpls = syllable_model.get('tmpls', [])
    card2_found = False
    
    for tmpl in tmpls:
        tmpl_name = tmpl.get('name', '')
        tmpl_ord = tmpl.get('ord', -1)
        
        if tmpl_ord == 2 or 'MCQ Recent' in tmpl_name or (tmpl_ord == 1 and 'MCQ' in tmpl_name):
            card2_found = True
            print(f"\n📄 Found Card 2 template: {tmpl_name} (ord: {tmpl_ord})")
            
            # Update templates
            tmpl['qfmt'] = mcq_front_template
            tmpl['afmt'] = mcq_back_template
            
            print("   ✅ Updated Card 2 templates")
            print("   - Removed instruction text")
            print("   - Larger buttons (64px font)")
            print("   - Fixed click handler with addEventListener")
            break
    
    if not card2_found:
        print("❌ Card 2 template not found")
        print("Available templates:")
        for tmpl in tmpls:
            print(f"   - {tmpl.get('name')} (ord: {tmpl.get('ord')})")
    else:
        # Fix database inconsistency: remove cards with ord >= number of templates
        num_templates = len(syllable_model.get('tmpls', []))
        print(f"\n🔧 Fixing database inconsistency...")
        print(f"   Templates: {num_templates} (ordinals 0-{num_templates-1})")
        
        # Get all note IDs for this model
        cursor.execute("SELECT id FROM notes WHERE mid = ?", (syllable_model_id,))
        note_ids = [row[0] for row in cursor.fetchall()]
        
        # Delete cards with ord >= num_templates
        deleted_count = 0
        for note_id in note_ids:
            cursor.execute("DELETE FROM cards WHERE nid = ? AND ord >= ?", (note_id, num_templates))
            deleted_count += cursor.rowcount
        
        if deleted_count > 0:
            print(f"   ✅ Deleted {deleted_count} orphaned cards (ord >= {num_templates})")
        else:
            print(f"   ✅ No orphaned cards found")
        
        # Save updated models
        models[str(syllable_model_id)] = syllable_model
        cursor.execute("UPDATE col SET models = ?", (json.dumps(models),))
        conn.commit()
        print("\n✅ Models updated")
    
    conn.close()
    
    # Repackage
    print("\n📦 Repackaging .apkg...")
    with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_path in tmpdir_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(tmpdir_path)
                z.write(file_path, arcname)
    
    print("✅ .apkg updated")
