#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create "CUMA - Chinese Naming" note type in Anki using genanki - Version 2.

This version supports:
1. Complete word input (e.g., select "shī" then "zi" then press Space/Enter)
2. Improved dark mode compatibility
3. Progressive syllable construction for multi-syllable words
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
    
    # Define all fields - now we need fields for ALL syllables
    # For simplicity, support up to 3 syllables (most Chinese words are 1-3 syllables)
    fields = [
        {'name': 'Concept'},
        {'name': 'Image'},
        {'name': 'Audio'},
        {'name': 'FullPinyin'},
        {'name': 'TotalSyllables'},
        {'name': 'Config'},
        
        # Syllable 1
        {'name': 'Syllable1'},
        {'name': 'Syllable1Option1'},
        {'name': 'Syllable1Option2'},
        {'name': 'Syllable1Option3'},
        {'name': 'Syllable1Option4'},
        {'name': 'Initial1'},
        {'name': 'Initial1Option1'},
        {'name': 'Initial1Option2'},
        {'name': 'Medial1'},
        {'name': 'Medial1Option1'},
        {'name': 'Medial1Option2'},
        {'name': 'TonedFinal1'},
        {'name': 'TonedFinal1Option1'},
        {'name': 'TonedFinal1Option2'},
        
        # Syllable 2
        {'name': 'Syllable2'},
        {'name': 'Syllable2Option1'},
        {'name': 'Syllable2Option2'},
        {'name': 'Syllable2Option3'},
        {'name': 'Syllable2Option4'},
        {'name': 'Initial2'},
        {'name': 'Initial2Option1'},
        {'name': 'Initial2Option2'},
        {'name': 'Medial2'},
        {'name': 'Medial2Option1'},
        {'name': 'Medial2Option2'},
        {'name': 'TonedFinal2'},
        {'name': 'TonedFinal2Option1'},
        {'name': 'TonedFinal2Option2'},
        
        # Syllable 3
        {'name': 'Syllable3'},
        {'name': 'Syllable3Option1'},
        {'name': 'Syllable3Option2'},
        {'name': 'Syllable3Option3'},
        {'name': 'Syllable3Option4'},
        {'name': 'Initial3'},
        {'name': 'Initial3Option1'},
        {'name': 'Initial3Option2'},
        {'name': 'Medial3'},
        {'name': 'Medial3Option1'},
        {'name': 'Medial3Option2'},
        {'name': 'TonedFinal3'},
        {'name': 'TonedFinal3Option1'},
        {'name': 'TonedFinal3Option2'},
        
        {'name': '_KG_Map'},
        {'name': '_Remarks'},
    ]
    
    # CSS styling (improved dark mode support)
    css = """<style>
/* Base card styling with dark mode support */
.cuma-naming-card {
  font-family: Arial, sans-serif;
  padding: 20px;
  color: #333;
  background-color: #fff;
  text-align: center;
}

.nightMode .cuma-naming-card,
.night_mode .cuma-naming-card {
  color: #e0e0e0;
  background-color: #1e1e1e;
}

/* Image styling */
.concept-image {
  margin-bottom: 20px;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
}

.concept-image img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  background-color: white;
  display: block;
  margin: 0 auto;
}

.nightMode .concept-image img,
.night_mode .concept-image img {
  box-shadow: 0 2px 8px rgba(255,255,255,0.1);
}

/* Audio */
.audio {
  margin-bottom: 20px;
}

/* Instruction text */
.instruction {
  margin-bottom: 20px;
  font-size: 1.2em;
  font-weight: bold;
  color: #333;
}

.nightMode .instruction,
.night_mode .instruction {
  color: #e0e0e0;
}

/* Progress indicator */
.progress-indicator {
  font-size: 0.9em;
  color: #666;
  margin-bottom: 15px;
}

.nightMode .progress-indicator,
.night_mode .progress-indicator {
  color: #999;
}

/* Constructed word display */
.constructed-word {
  margin: 20px 0;
  padding: 15px;
  background-color: #f5f5f5;
  border: 2px solid #ddd;
  border-radius: 8px;
  font-size: 1.8em;
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #333;
}

.nightMode .constructed-word,
.night_mode .constructed-word {
  background-color: #2a2a2a;
  border-color: #555;
  color: #e0e0e0;
}

.constructed-word .syllable {
  padding: 5px 10px;
  border-radius: 4px;
  background-color: #e3f2fd;
  color: #1976d2;
  font-weight: bold;
}

.nightMode .constructed-word .syllable,
.night_mode .constructed-word .syllable {
  background-color: rgba(33, 150, 243, 0.2);
  color: #64b5f6;
}

.constructed-word .cursor {
  display: inline-block;
  width: 3px;
  height: 1.2em;
  background-color: #333;
  animation: blink 1s infinite;
}

.nightMode .constructed-word .cursor,
.night_mode .constructed-word .cursor {
  background-color: #e0e0e0;
}

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

/* Syllable options */
.syllable-options {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  justify-content: center;
  margin: 20px 0;
}

.syllable-btn {
  padding: 20px 40px;
  font-size: 48px;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: #fff;
  color: #333;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 120px;
  font-weight: 600;
}

.nightMode .syllable-btn,
.night_mode .syllable-btn {
  background-color: #3a3a3a;
  border-color: #555;
  color: #e0e0e0;
}

.syllable-btn:hover {
  background-color: #f0f0f0;
  border-color: #999;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.nightMode .syllable-btn:hover,
.night_mode .syllable-btn:hover {
  background-color: #4a4a4a;
  border-color: #777;
}

.syllable-btn.selected {
  background-color: #4caf50;
  color: white;
  border-color: #4caf50;
}

.nightMode .syllable-btn.selected,
.night_mode .syllable-btn.selected {
  background-color: #66bb6a;
  border-color: #66bb6a;
}

.syllable-btn.wrong {
  background-color: #f44336;
  color: white;
  border-color: #f44336;
}

.nightMode .syllable-btn.wrong,
.night_mode .syllable-btn.wrong {
  background-color: #ef5350;
  border-color: #ef5350;
}

/* Hint text */
.hint-text {
  font-size: 0.9em;
  color: #666;
  margin-top: 10px;
  font-style: italic;
}

.nightMode .hint-text,
.night_mode .hint-text {
  color: #999;
}

/* Answer section */
.answer-section {
  margin-top: 30px;
  padding: 20px;
  background-color: #e8f5e9;
  border-radius: 8px;
  border: 2px solid #4caf50;
}

.nightMode .answer-section,
.night_mode .answer-section {
  background-color: rgba(76, 175, 80, 0.15);
  border-color: #66bb6a;
}

.answer-section p {
  color: #333;
  margin: 10px 0;
  font-size: 1.1em;
}

.nightMode .answer-section p,
.night_mode .answer-section p {
  color: #e0e0e0;
}

.correct-answer {
  font-size: 1.5em;
  font-weight: bold;
  color: #2e7d32;
  margin: 15px 0;
}

.nightMode .correct-answer,
.night_mode .correct-answer {
  color: #81c784;
}

/* Component construction (harder mode) */
.component-group {
  margin: 20px 0;
  padding: 15px;
  border-radius: 8px;
  border: 2px solid #ddd;
  background-color: #f9f9f9;
}

.nightMode .component-group,
.night_mode .component-group {
  border-color: #444;
  background-color: #2a2a2a;
}

.component-group.initial-group {
  border-color: #2196f3;
  background-color: rgba(33, 150, 243, 0.1);
}

.nightMode .component-group.initial-group,
.night_mode .component-group.initial-group {
  border-color: #64b5f6;
  background-color: rgba(100, 181, 246, 0.15);
}

.component-group.medial-group {
  border-color: #9c27b0;
  background-color: rgba(156, 39, 176, 0.1);
}

.nightMode .component-group.medial-group,
.night_mode .component-group.medial-group {
  border-color: #ba68c8;
  background-color: rgba(186, 104, 200, 0.15);
}

.component-group.final-group {
  border-color: #ff9800;
  background-color: rgba(255, 152, 0, 0.1);
}

.nightMode .component-group.final-group,
.night_mode .component-group.final-group {
  border-color: #ffb74d;
  background-color: rgba(255, 183, 77, 0.15);
}

.component-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 1.1em;
  color: #333;
}

.nightMode .component-group label,
.night_mode .component-group label {
  color: #e0e0e0;
}

.component-options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

.component-btn {
  padding: 15px 30px;
  font-size: 36px;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: #fff;
  color: #333;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 90px;
  font-weight: 600;
}

.nightMode .component-btn,
.night_mode .component-btn {
  background-color: #3a3a3a;
  border-color: #555;
  color: #e0e0e0;
}

.component-btn:hover {
  background-color: #f0f0f0;
  border-color: #999;
}

.nightMode .component-btn:hover,
.night_mode .component-btn:hover {
  background-color: #4a4a4a;
  border-color: #777;
}

.component-btn.selected {
  background-color: #4caf50;
  color: white;
  border-color: #4caf50;
}

.nightMode .component-btn.selected,
.night_mode .component-btn.selected {
  background-color: #66bb6a;
  border-color: #66bb6a;
}
</style>"""
    
    # Card 1: Easy - Progressive Syllable Selection (Front Template)
    easy_front = """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  
  <div class="progress-indicator">
    <span id="progress-text">1/{{TotalSyllables}}</span>
  </div>
  
  <div class="constructed-word" id="constructed-word">
    <span class="cursor"></span>
  </div>
  
  <div class="syllable-options" id="syllable-options">
    <!-- Options will be dynamically populated by JavaScript -->
  </div>
  
  <div class="hint-text">
    按空格或回车确认 (Press Space or Enter to confirm)
  </div>
</div>

<script>
(function() {
  // Parse syllable data
  const syllables = [
    {
      correct: '{{Syllable1}}',
      options: ['{{Syllable1Option1}}', '{{Syllable1Option2}}', '{{Syllable1Option3}}', '{{Syllable1Option4}}'].filter(o => o)
    },
    {
      correct: '{{Syllable2}}',
      options: ['{{Syllable2Option1}}', '{{Syllable2Option2}}', '{{Syllable2Option3}}', '{{Syllable2Option4}}'].filter(o => o)
    },
    {
      correct: '{{Syllable3}}',
      options: ['{{Syllable3Option1}}', '{{Syllable3Option2}}', '{{Syllable3Option3}}', '{{Syllable3Option4}}'].filter(o => o)
    }
  ].filter(s => s.correct);
  
  const totalSyllables = parseInt('{{TotalSyllables}}') || syllables.length;
  let currentSyllableIndex = 0;
  let constructedSyllables = [];
  let currentSelection = null;
  
  // Render current syllable options
  function renderOptions() {
    const optionsContainer = document.getElementById('syllable-options');
    if (!optionsContainer) return;
    
    if (currentSyllableIndex >= syllables.length) {
      optionsContainer.innerHTML = '<p style="color: #4caf50; font-weight: bold;">完成！(Complete!)</p>';
      return;
    }
    
    const currentSyllable = syllables[currentSyllableIndex];
    optionsContainer.innerHTML = '';
    
    currentSyllable.options.forEach(option => {
      const btn = document.createElement('button');
      btn.className = 'syllable-btn';
      btn.textContent = option;
      btn.onclick = () => selectSyllable(option, currentSyllable.correct);
      optionsContainer.appendChild(btn);
    });
  }
  
  // Update constructed word display
  function updateConstructedWord() {
    const wordContainer = document.getElementById('constructed-word');
    if (!wordContainer) return;
    
    wordContainer.innerHTML = '';
    constructedSyllables.forEach(syl => {
      const span = document.createElement('span');
      span.className = 'syllable';
      span.textContent = syl;
      wordContainer.appendChild(span);
    });
    
    if (currentSyllableIndex < syllables.length) {
      const cursor = document.createElement('span');
      cursor.className = 'cursor';
      wordContainer.appendChild(cursor);
    }
  }
  
  // Update progress indicator
  function updateProgress() {
    const progressEl = document.getElementById('progress-text');
    if (progressEl) {
      progressEl.textContent = `${currentSyllableIndex + 1}/${totalSyllables}`;
    }
  }
  
  // Select a syllable
  function selectSyllable(selected, correct) {
    currentSelection = selected;
    
    // Highlight selected button
    const buttons = document.querySelectorAll('.syllable-btn');
    buttons.forEach(btn => {
      btn.classList.remove('selected', 'wrong');
      if (btn.textContent === selected) {
        if (selected === correct) {
          btn.classList.add('selected');
        } else {
          btn.classList.add('wrong');
        }
      }
    });
    
    // Auto-confirm if correct (no need to press Space/Enter)
    if (selected === correct) {
      setTimeout(() => {
        confirmSelection();
      }, 300); // Small delay for visual feedback
    }
  }
  
  // Confirm selection (Space or Enter)
  function confirmSelection() {
    if (!currentSelection) {
      console.log('No selection to confirm');
      return;
    }
    
    const currentSyllable = syllables[currentSyllableIndex];
    console.log('Confirming:', currentSelection, 'Expected:', currentSyllable.correct);
    
    if (currentSelection === currentSyllable.correct) {
      // Add to constructed syllables
      constructedSyllables.push(currentSelection);
      currentSyllableIndex++;
      currentSelection = null;
      
      console.log('Syllable confirmed. Progress:', currentSyllableIndex, '/', syllables.length);
      console.log('Constructed so far:', constructedSyllables);
      
      // Update display
      updateConstructedWord();
      updateProgress();
      renderOptions();
    } else {
      console.log('Selection incorrect, not confirming');
    }
  }
  
  // Keyboard event listener
  document.addEventListener('keydown', function(e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      confirmSelection();
    }
  });
  
  // Initialize
  console.log('Initializing Chinese Naming card');
  console.log('Total syllables:', totalSyllables);
  console.log('Syllables data:', syllables);
  renderOptions();
  updateConstructedWord();
  updateProgress();
})();
</script>"""
    
    # Card 1: Easy - Back Template
    easy_back = """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  
  <div class="progress-indicator">
    <span id="progress-text">{{TotalSyllables}}/{{TotalSyllables}}</span>
  </div>
  
  <div style="margin: 40px 0; font-size: 2em; font-weight: bold; color: #4caf50;">
    ✓ 正确
  </div>
  
  <!-- Hide the Audio field so Anki doesn't auto-play it -->
  <div id="hidden_audio_src" style="display: none;">{{Audio}}</div>
</div>

<script>
(function() {
  // 1. Get the audio element
  var rawAudioContent = document.getElementById('hidden_audio_src');
  
  if (!rawAudioContent) {
    return;
  }
  
  var rawAudioText = rawAudioContent.innerText || rawAudioContent.textContent || '';
  
  // 2. Extract the filename from Anki's [sound:filename.mp3] format
  var audioFilename = null;
  var match = rawAudioText.match(/\[sound:(.*?)\]/);
  
  if (match && match[1]) {
    audioFilename = match[1];
  }
  
  // 3. Create Audio Player (only mp3, no bell.wav)
  var wordAudio = null;
  
  if (audioFilename) {
    wordAudio = new Audio(audioFilename);
    wordAudio.preload = 'auto';
    
    // 4. Play after 2 seconds
    setTimeout(function() {
      if (wordAudio) {
        wordAudio.currentTime = 0;
        wordAudio.play().catch(function(e) { 
          console.error("Audio error: ", e);
        });
      }
    }, 2000);
  }
})();
</script>

<style>
.nightMode .cuma-naming-card,
.night_mode .cuma-naming-card {
  color: #66bb6a;
}

</style>"""
    
    # Card 2: Harder - Component Construction
    harder_front = """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  
  <div class="progress-indicator">
    <span id="progress-text">1/{{TotalSyllables}}</span>
  </div>
  
  <div class="constructed-word" id="constructed-word">
    <span class="cursor"></span>
  </div>
  
  <div class="component-group initial-group">
    <div class="component-options" id="initial-options">
      <!-- Will be populated by JS -->
    </div>
  </div>
  
  <div class="component-group medial-group" id="medial-group" style="display: none;">
    <div class="component-options" id="medial-options">
      <!-- Will be populated by JS -->
    </div>
  </div>
  
  <div class="component-group final-group">
    <div class="component-options" id="final-options">
      <!-- Will be populated by JS -->
    </div>
  </div>
</div>

<script>
(function() {
  // Parse syllable data for all syllables
  const syllables = [
    {
      initial: '{{Initial1}}',
      initialOptions: ['{{Initial1Option1}}', '{{Initial1Option2}}'].filter(o => o),
      medial: '{{Medial1}}',
      medialOptions: ['{{Medial1Option1}}', '{{Medial1Option2}}'].filter(o => o),
      final: '{{TonedFinal1}}',
      finalOptions: ['{{TonedFinal1Option1}}', '{{TonedFinal1Option2}}'].filter(o => o),
      correct: '{{Syllable1}}'
    },
    {
      initial: '{{Initial2}}',
      initialOptions: ['{{Initial2Option1}}', '{{Initial2Option2}}'].filter(o => o),
      medial: '{{Medial2}}',
      medialOptions: ['{{Medial2Option1}}', '{{Medial2Option2}}'].filter(o => o),
      final: '{{TonedFinal2}}',
      finalOptions: ['{{TonedFinal2Option1}}', '{{TonedFinal2Option2}}'].filter(o => o),
      correct: '{{Syllable2}}'
    },
    {
      initial: '{{Initial3}}',
      initialOptions: ['{{Initial3Option1}}', '{{Initial3Option2}}'].filter(o => o),
      medial: '{{Medial3}}',
      medialOptions: ['{{Medial3Option1}}', '{{Medial3Option2}}'].filter(o => o),
      final: '{{TonedFinal3}}',
      finalOptions: ['{{TonedFinal3Option1}}', '{{TonedFinal3Option2}}'].filter(o => o),
      correct: '{{Syllable3}}'
    }
  ].filter(s => s.correct);
  
  const totalSyllables = parseInt('{{TotalSyllables}}') || syllables.length;
  let currentSyllableIndex = 0;
  let constructedSyllables = [];
  let currentComponents = {
    initial: '',
    medial: '',
    final: ''
  };
  
  function renderCurrentSyllable() {
    if (currentSyllableIndex >= syllables.length) {
      return;
    }
    
    const syllable = syllables[currentSyllableIndex];
    
    // Render initial options (remove duplicates)
    const initialContainer = document.getElementById('initial-options');
    initialContainer.innerHTML = '';
    const initialOpts = [...new Set([syllable.initial, ...syllable.initialOptions].filter(o => o))];
    initialOpts.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'component-btn';
      btn.textContent = opt;
      btn.onclick = () => selectComponent('initial', opt, syllable.initial);
      initialContainer.appendChild(btn);
    });
    
    // Render medial options (if exists, remove duplicates)
    const medialGroup = document.getElementById('medial-group');
    if (syllable.medial) {
      medialGroup.style.display = 'block';
      const medialContainer = document.getElementById('medial-options');
      medialContainer.innerHTML = '';
      const medialOpts = [...new Set([syllable.medial, ...syllable.medialOptions].filter(o => o))];
      medialOpts.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'component-btn';
        btn.textContent = opt;
        btn.onclick = () => selectComponent('medial', opt, syllable.medial);
        medialContainer.appendChild(btn);
      });
    } else {
      medialGroup.style.display = 'none';
      currentComponents.medial = '';
    }
    
    // Render final options (remove duplicates)
    const finalContainer = document.getElementById('final-options');
    finalContainer.innerHTML = '';
    const finalOpts = [...new Set([syllable.final, ...syllable.finalOptions].filter(o => o))];
    finalOpts.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'component-btn';
      btn.textContent = opt;
      btn.onclick = () => selectComponent('final', opt, syllable.final);
      finalContainer.appendChild(btn);
    });
  }
  
  function selectComponent(type, value, correct) {
    currentComponents[type] = value;
    
    // Highlight selected button
    const containers = {
      'initial': document.getElementById('initial-options'),
      'medial': document.getElementById('medial-options'),
      'final': document.getElementById('final-options')
    };
    
    const container = containers[type];
    if (container) {
      container.querySelectorAll('.component-btn').forEach(btn => {
        btn.classList.remove('selected', 'wrong');
        if (btn.textContent === value) {
          if (value === correct) {
            btn.classList.add('selected');
          } else {
            btn.classList.add('wrong');
          }
        }
      });
    }
    
    updateConstructedWord();
    checkCompletion();
  }
  
  function updateConstructedWord() {
    const wordContainer = document.getElementById('constructed-word');
    wordContainer.innerHTML = '';
    
    // Show completed syllables
    constructedSyllables.forEach(syl => {
      const span = document.createElement('span');
      span.className = 'syllable';
      span.textContent = syl;
      wordContainer.appendChild(span);
    });
    
    // Show current syllable being constructed
    if (currentSyllableIndex < syllables.length) {
      const currentSyl = currentComponents.initial + currentComponents.medial + currentComponents.final;
      if (currentSyl) {
        const span = document.createElement('span');
        span.style.color = '#64b5f6';
        span.style.marginLeft = '5px';
        span.textContent = currentSyl;
        wordContainer.appendChild(span);
      }
      
      const cursor = document.createElement('span');
      cursor.className = 'cursor';
      wordContainer.appendChild(cursor);
    }
  }
  
  function updateProgress() {
    const progressEl = document.getElementById('progress-text');
    if (progressEl) {
      progressEl.textContent = `${currentSyllableIndex + 1}/${totalSyllables}`;
    }
  }
  
  function checkCompletion() {
    const syllable = syllables[currentSyllableIndex];
    const constructed = currentComponents.initial + currentComponents.medial + currentComponents.final;
    
    if (constructed === syllable.correct) {
      // Correct! Move to next syllable after delay
      setTimeout(() => {
        constructedSyllables.push(constructed);
        currentSyllableIndex++;
        currentComponents = { initial: '', medial: '', final: '' };
        
        updateConstructedWord();
        updateProgress();
        renderCurrentSyllable();
      }, 300);
    }
  }
  
  // Initialize
  renderCurrentSyllable();
  updateConstructedWord();
  updateProgress();
})();
</script>"""
    
    # Card 2: Harder - Back Template
    harder_back = """<div class="cuma-naming-card">
  <div class="concept-image">
    {{Image}}
  </div>
  
  <div class="progress-indicator">
    <span id="progress-text">{{TotalSyllables}}/{{TotalSyllables}}</span>
  </div>
  
  <div style="margin: 40px 0; font-size: 2em; font-weight: bold; color: #4caf50;">
    ✓ 正确
  </div>
  
  <!-- Hide the Audio field so Anki doesn't auto-play it -->
  <div id="hidden_audio_src" style="display: none;">{{Audio}}</div>
</div>

<script>
(function() {
  // 1. Get the audio element
  var rawAudioContent = document.getElementById('hidden_audio_src');
  
  if (!rawAudioContent) {
    return;
  }
  
  var rawAudioText = rawAudioContent.innerText || rawAudioContent.textContent || '';
  
  // 2. Extract the filename from Anki's [sound:filename.mp3] format
  var audioFilename = null;
  var match = rawAudioText.match(/\[sound:(.*?)\]/);
  
  if (match && match[1]) {
    audioFilename = match[1];
  }
  
  // 3. Create Audio Player (only mp3, no bell.wav)
  var wordAudio = null;
  
  if (audioFilename) {
    wordAudio = new Audio(audioFilename);
    wordAudio.preload = 'auto';
    
    // 4. Play after 2 seconds
    setTimeout(function() {
      if (wordAudio) {
        wordAudio.currentTime = 0;
        wordAudio.play().catch(function(e) { 
          console.error("Audio error: ", e);
        });
      }
    }, 2000);
  }
})();
</script>

<style>
.nightMode .cuma-naming-card,
.night_mode .cuma-naming-card {
  color: #66bb6a;
}

</style>"""
    
    # Create the model
    model = genanki.Model(
        1607392320,  # Unique model ID
        'CUMA - Chinese Naming v2',
        fields=fields,
        templates=[
            {
                'name': 'Easy - Progressive Syllable Selection',
                'qfmt': easy_front,
                'afmt': easy_back,
            },
            {
                'name': 'Harder - Component Construction',
                'qfmt': harder_front,
                'afmt': harder_back,
            },
        ],
        css=css,
    )
    
    return model


def create_template_package():
    """Create an Anki package file with the note type and a sample note"""
    
    print("🚀 Creating CUMA - Chinese Naming v2 note type using genanki...\n")
    
    # Create the model
    model = create_chinese_naming_model()
    
    # Create a deck
    deck_id = 1985090311  # New ID for v2
    deck = genanki.Deck(deck_id, 'CUMA Template - Chinese Naming v2')
    
    # Add a sample note for "狮子" (shī zi - lion)
    sample_note = genanki.Note(
        model=model,
        fields=[
            'Lion',  # Concept
            '<img src="lion.png" alt="Lion">',  # Image
            '[sound:Lion.mandarin.mp3]',  # Audio
            'shī zi',  # FullPinyin
            '2',  # TotalSyllables
            'simplified',  # Config
            
            # Syllable 1
            'shī',  # Syllable1
            'shī',  # Syllable1Option1 (correct)
            'shí',  # Syllable1Option2
            'mā',  # Syllable1Option3
            'zī',  # Syllable1Option4
            'sh',  # Initial1
            'sh',  # Initial1Option1 (correct)
            'zh',  # Initial1Option2
            '',  # Medial1
            '',  # Medial1Option1
            '',  # Medial1Option2
            'ī',  # TonedFinal1
            'ī',  # TonedFinal1Option1 (correct)
            'í',  # TonedFinal1Option2
            
            # Syllable 2
            'zi',  # Syllable2
            'zi',  # Syllable2Option1 (correct)
            'zī',  # Syllable2Option2
            'ci',  # Syllable2Option3
            'si',  # Syllable2Option4
            'z',  # Initial2
            'z',  # Initial2Option1 (correct)
            'c',  # Initial2Option2
            '',  # Medial2
            '',  # Medial2Option1
            '',  # Medial2Option2
            'i',  # TonedFinal2
            'i',  # TonedFinal2Option1 (correct)
            'ī',  # TonedFinal2Option2
            
            # Syllable 3 (empty for 2-syllable word)
            '',  # Syllable3
            '',  # Syllable3Option1
            '',  # Syllable3Option2
            '',  # Syllable3Option3
            '',  # Syllable3Option4
            '',  # Initial3
            '',  # Initial3Option1
            '',  # Initial3Option2
            '',  # Medial3
            '',  # Medial3Option1
            '',  # Medial3Option2
            '',  # TonedFinal3
            '',  # TonedFinal3Option1
            '',  # TonedFinal3Option2
            
            '{"card_type": "chinese_naming", "knowledge_points": []}',  # _KG_Map
            'Chinese Naming v2 - 狮子 (Lion) - Template Example'  # _Remarks
        ]
    )
    
    # Add note to deck
    deck.add_note(sample_note)
    
    # Create a package
    package = genanki.Package(deck)
    package.models = [model]
    
    # Try to find and add lion image and audio
    media_files = []
    
    lion_image_paths = [
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "lion.png",
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "Lion.png",
    ]
    
    for img_path in lion_image_paths:
        if img_path.exists():
            media_files.append(str(img_path))
            print(f"   📷 Found and included image: {img_path.name}")
            break
    
    # Add lion audio
    lion_audio_path = PROJECT_ROOT / "media" / "chinese_word_recognition" / "Lion.mandarin.mp3"
    if lion_audio_path.exists():
        media_files.append(str(lion_audio_path))
        print(f"   🔊 Found and included audio: {lion_audio_path.name}")
    else:
        print(f"   ⚠️  Lion audio not found at: {lion_audio_path}")
    
    # Try to find bell.wav (standard Anki sound, but include it if found)
    bell_paths = [
        PROJECT_ROOT / "media" / "chinese_word_recognition" / "bell.wav",
        PROJECT_ROOT / "media" / "bell.wav",
    ]
    for bell_path in bell_paths:
        if bell_path.exists():
            media_files.append(str(bell_path))
            print(f"   🔔 Found and included bell.wav: {bell_path.name}")
            break
    else:
        print(f"   ℹ️  bell.wav not found in media directory. Using Anki's default bell.wav (should be in collection.media)")
    
    if media_files:
        package.media_files = media_files
    else:
        print(f"   ⚠️  No media files found.")
    
    # Write the package
    output_path = PROJECT_ROOT / "data" / "content_db" / "CUMA_Chinese_Naming_v2_Template.apkg"
    package.write_to_file(str(output_path))
    
    print(f"✅ Created Anki package: {output_path}")
    print(f"   - Note type: CUMA - Chinese Naming v2")
    print(f"   - Sample note: 1 (Progressive syllable selection for '狮子' - lion)")
    print(f"\n📋 To import the note type:")
    print(f"   1. Open Anki")
    print(f"   2. File → Import")
    print(f"   3. Select: {output_path}")
    print(f"   4. The note type 'CUMA - Chinese Naming v2' will be created automatically!")
    print(f"   5. Test the card: select 'shī' then press Space/Enter, then select 'zi' and press Space/Enter")
    print(f"\n   After import, you can use this note type to sync Chinese naming cards from the app.")
    
    # Try to check if note type exists via AnkiConnect
    print(f"\n📦 Attempting to check AnkiConnect...")
    try:
        anki = AnkiConnect()
        if anki.ping():
            model_names = anki._invoke("modelNames")
            if 'CUMA - Chinese Naming v2' in model_names:
                print(f"✅ Note type 'CUMA - Chinese Naming v2' already exists in Anki!")
            else:
                print(f"ℹ️  Note type 'CUMA - Chinese Naming v2' not found in Anki. Please import the .apkg file.")
        else:
            print(f"ℹ️  AnkiConnect not available. Please import the .apkg file manually.")
    except Exception as e:
        print(f"ℹ️  Could not check AnkiConnect: {e}")


if __name__ == "__main__":
    create_template_package()

