#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate comprehensive report on pinyin deck:
- Current organization by 5-stage curriculum
- Missing elements
- Coverage analysis
- Recommendations
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
from pathlib import Path
from collections import defaultdict, Counter

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import parse_pinyin, extract_tone

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
REPORT_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "pinyin_deck_report.md"

# 5-Stage Curriculum
STAGES = {
    1: {
        'name': 'Lips & Simple Vowels',
        'initials': ['b', 'p', 'm', 'f'],
        'finals': ['a', 'o', 'e', 'i', 'u'],
        'order': 1
    },
    2: {
        'name': 'Tip of Tongue',
        'initials': ['d', 't', 'n', 'l'],
        'finals': ['ai', 'ei', 'ao', 'ou'],
        'order': 2
    },
    3: {
        'name': 'Root of Tongue',
        'initials': ['g', 'k', 'h'],
        'finals': ['an', 'en', 'in', 'un'],
        'order': 3
    },
    4: {
        'name': 'Teeth & Curl',
        'initials': ['z', 'c', 's', 'zh', 'ch', 'sh', 'r'],
        'finals': ['ang', 'eng', 'ing', 'ong', 'er'],
        'order': 4
    },
    5: {
        'name': 'Magic Palatals',
        'initials': ['j', 'q', 'x', 'y', 'w'],
        'finals': ['i', 'u', 'ü', 'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 
                   'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 'ue', 'üe', 'üan', 'ün'],
        'order': 5
    }
}

def get_stage_for_syllable(syllable: str) -> int:
    """Determine which stage a syllable belongs to"""
    parsed = parse_pinyin(syllable)
    initial = parsed.get('initial', '')
    final = parsed.get('final', '')
    
    if not initial and not final:
        return 99
    
    for stage_num, stage_config in STAGES.items():
        if initial in stage_config['initials']:
            if final in stage_config['finals']:
                return stage_num
        if not initial and final in stage_config['finals']:
            return stage_num
    
    if initial in ['j', 'q', 'x'] and final == 'u':
        return 5
    
    return 99

def analyze_deck():
    """Analyze the pinyin deck comprehensively"""
    print("=" * 80)
    print("Generating Pinyin Deck Report")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        print("\n📦 Extracting .apkg...")
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
            return
        
        field_names = [f['name'] for f in syllable_model.get('flds', [])]
        num_templates = len(syllable_model.get('tmpls', []))
        
        # Get all notes
        print("📋 Analyzing notes...")
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        all_notes = cursor.fetchall()
        
        # Organize data
        notes_by_stage = defaultdict(list)
        syllables_by_stage = defaultdict(set)
        initials_by_stage = defaultdict(set)
        finals_by_stage = defaultdict(set)
        elements_by_stage = defaultdict(set)
        words_by_stage = defaultdict(list)
        audio_coverage = {'with_audio': 0, 'without_audio': 0}
        
        all_syllables = set()
        all_initials = set()
        all_finals = set()
        all_elements = set()
        
        for note_id, flds_str in all_notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            syllable = field_dict.get('Syllable', '').strip()
            element = field_dict.get('ElementToLearn', '').strip()
            word_hanzi = field_dict.get('WordHanzi', '').strip()
            word_audio = field_dict.get('WordAudio', '').strip()
            
            if syllable:
                parsed = parse_pinyin(syllable)
                initial = parsed.get('initial', '')
                final = parsed.get('final', '')
                
                # Normalize syllable (remove tone)
                pinyin_no_tone, _ = extract_tone(syllable)
                
                stage = get_stage_for_syllable(syllable)
                notes_by_stage[stage].append({
                    'syllable': syllable,
                    'element': element,
                    'word_hanzi': word_hanzi,
                    'initial': initial,
                    'final': final,
                    'has_audio': bool(word_audio)
                })
                
                syllables_by_stage[stage].add(pinyin_no_tone)
                if initial:
                    initials_by_stage[stage].add(initial)
                if final:
                    finals_by_stage[stage].add(final)
                if element:
                    elements_by_stage[stage].add(element)
                
                all_syllables.add(pinyin_no_tone)
                if initial:
                    all_initials.add(initial)
                if final:
                    all_finals.add(final)
                if element:
                    all_elements.add(element)
                
                words_by_stage[stage].append(word_hanzi)
                
                if word_audio:
                    audio_coverage['with_audio'] += 1
                else:
                    audio_coverage['without_audio'] += 1
        
        conn.close()
        
        # Generate report
        print("\n📝 Generating report...")
        generate_markdown_report(
            notes_by_stage,
            syllables_by_stage,
            initials_by_stage,
            finals_by_stage,
            elements_by_stage,
            words_by_stage,
            audio_coverage,
            all_syllables,
            all_initials,
            all_finals,
            all_elements,
            num_templates,
            len(all_notes)
        )
        
        print(f"✅ Report generated: {REPORT_PATH}")

def generate_markdown_report(notes_by_stage, syllables_by_stage, initials_by_stage, 
                            finals_by_stage, elements_by_stage, words_by_stage,
                            audio_coverage, all_syllables, all_initials, all_finals,
                            all_elements, num_templates, total_notes):
    """Generate markdown report"""
    
    report = []
    report.append("# Pinyin Deck Analysis Report\n")
    report.append(f"Generated: {Path(__file__).stat().st_mtime}\n")
    report.append("---\n\n")
    
    # Executive Summary
    report.append("## Executive Summary\n\n")
    report.append(f"- **Total Notes**: {total_notes}\n")
    report.append(f"- **Total Cards**: {total_notes * num_templates}\n")
    report.append(f"- **Unique Syllables**: {len(all_syllables)}\n")
    report.append(f"- **Unique Initials**: {len(all_initials)}\n")
    report.append(f"- **Unique Finals**: {len(all_finals)}\n")
    report.append(f"- **Unique Elements**: {len(all_elements)}\n")
    report.append(f"- **Audio Coverage**: {audio_coverage['with_audio']} with audio, {audio_coverage['without_audio']} without\n\n")
    
    # Stage-by-Stage Analysis
    report.append("## Stage-by-Stage Analysis\n\n")
    
    for stage_num in [1, 2, 3, 4, 5, 99]:
        stage_name = STAGES.get(stage_num, {}).get('name', 'Unknown/Advanced') if stage_num != 99 else 'Unknown/Advanced'
        notes = notes_by_stage[stage_num]
        
        if not notes:
            continue
        
        report.append(f"### Stage {stage_num}: {stage_name}\n\n")
        report.append(f"- **Notes**: {len(notes)}\n")
        report.append(f"- **Unique Syllables**: {len(syllables_by_stage[stage_num])}\n")
        report.append(f"- **Initials Covered**: {sorted(initials_by_stage[stage_num])}\n")
        report.append(f"- **Finals Covered**: {sorted(finals_by_stage[stage_num])}\n")
        report.append(f"- **Elements Covered**: {sorted(elements_by_stage[stage_num])}\n\n")
        
        # Expected vs Actual
        if stage_num in STAGES:
            expected_initials = set(STAGES[stage_num]['initials'])
            expected_finals = set(STAGES[stage_num]['finals'])
            actual_initials = initials_by_stage[stage_num]
            actual_finals = finals_by_stage[stage_num]
            
            missing_initials = expected_initials - actual_initials
            missing_finals = expected_finals - actual_finals
            
            if missing_initials or missing_finals:
                report.append("**Missing Elements:**\n")
                if missing_initials:
                    report.append(f"- Missing Initials: {sorted(missing_initials)}\n")
                if missing_finals:
                    report.append(f"- Missing Finals: {sorted(missing_finals)}\n")
                report.append("\n")
        
        # Sample words
        unique_words = list(set(words_by_stage[stage_num]))[:10]
        if unique_words:
            report.append(f"**Sample Words**: {', '.join(unique_words)}\n\n")
        
        report.append("---\n\n")
    
    # Missing Combinations Analysis
    report.append("## Missing Basic Combinations\n\n")
    report.append("Based on 5-stage curriculum, the following basic combinations are missing:\n\n")
    
    for stage_num in [1, 2, 3, 4, 5]:
        stage_config = STAGES[stage_num]
        expected_initials = set(stage_config['initials'])
        expected_finals = set(stage_config['finals'])
        actual_syllables = syllables_by_stage[stage_num]
        
        missing_combinations = []
        for initial in expected_initials:
            for final in expected_finals:
                combo = initial + final
                if combo not in actual_syllables:
                    missing_combinations.append(combo)
        
        # Also check standalone finals
        for final in expected_finals:
            if final not in actual_syllables:
                missing_combinations.append(final)
        
        if missing_combinations:
            report.append(f"### Stage {stage_num}: {stage_config['name']}\n\n")
            report.append(f"Missing: {', '.join(sorted(missing_combinations)[:20])}\n\n")
    
    # Recommendations
    report.append("## Recommendations\n\n")
    report.append("1. **Complete Basic Curriculum**: Add missing basic combinations from each stage\n")
    report.append("2. **Audio Coverage**: Generate TTS audio for notes without audio\n")
    report.append("3. **Element Coverage**: Ensure all pinyin elements (initials/finals) have teaching cards\n")
    report.append("4. **Word Selection**: For missing combinations, select high-frequency, imageable words\n")
    report.append("5. **Progressive Difficulty**: Maintain the 5-stage order for optimal learning progression\n\n")
    
    # Statistics
    report.append("## Detailed Statistics\n\n")
    report.append("### Initials Distribution\n\n")
    initial_counts = Counter()
    for stage_num in [1, 2, 3, 4, 5, 99]:
        for initial in initials_by_stage[stage_num]:
            initial_counts[initial] += 1
    
    for initial, count in sorted(initial_counts.items()):
        report.append(f"- **{initial}**: {count} syllables\n")
    
    report.append("\n### Finals Distribution\n\n")
    final_counts = Counter()
    for stage_num in [1, 2, 3, 4, 5, 99]:
        for final in finals_by_stage[stage_num]:
            final_counts[final] += 1
    
    for final, count in sorted(final_counts.items()):
        report.append(f"- **{final}**: {count} syllables\n")
    
    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(''.join(report))
    
    print(f"\n📄 Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    analyze_deck()


