#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinyin Parser - Decompose Pinyin into Initial, Medial, Final, and Tone

Based on Layer 0 design:
- Initial (声母): zh, b, p, etc.
- Medial (介音): u, i, ü (optional)
- Final (韵母): ang, a, ou, etc. (with tone)
- Tone (声调): 1, 2, 3, 4 (marked on final)

For "zhuang4" (壮):
- Initial: zh
- Medial: u
- Final: ang4 (toned final)
- Tone: 4
"""

import re
from typing import Dict, Optional, Tuple, List

# Pinyin initials (声母)
PINYIN_INITIALS = [
    'b', 'p', 'm', 'f',
    'd', 't', 'n', 'l',
    'g', 'k', 'h',
    'j', 'q', 'x',
    'zh', 'ch', 'sh', 'r',
    'z', 'c', 's',
    'y', 'w'
]

# Pinyin medials (介音)
PINYIN_MEDIALS = ['i', 'u', 'ü']

# Pinyin finals (韵母) - without tone
PINYIN_FINALS = [
    'a', 'o', 'e', 'i', 'u', 'ü',
    'ai', 'ei', 'ao', 'ou',
    'an', 'en', 'ang', 'eng', 'ong',
    'ia', 'iao', 'ian', 'iang', 'iong',
    'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 'un',
    'üe', 'üan', 'ün',
    'er'
]

# Tone marks mapping
TONE_MARKS = {
    'a': ['ā', 'á', 'ǎ', 'à'],
    'e': ['ē', 'é', 'ě', 'è'],
    'i': ['ī', 'í', 'ǐ', 'ì'],
    'o': ['ō', 'ó', 'ǒ', 'ò'],
    'u': ['ū', 'ú', 'ǔ', 'ù'],
    'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ'],
    'A': ['Ā', 'Á', 'Ǎ', 'À'],
    'E': ['Ē', 'É', 'Ě', 'È'],
    'I': ['Ī', 'Í', 'Ǐ', 'Ì'],
    'O': ['Ō', 'Ó', 'Ǒ', 'Ò'],
    'U': ['Ū', 'Ú', 'Ǔ', 'Ù'],
    'Ü': ['Ǖ', 'Ǘ', 'Ǚ', 'Ǜ']
}


def extract_tone(pinyin: str) -> Tuple[str, Optional[int]]:
    """
    Extract tone from pinyin and return pinyin without tone, and tone number (1-4).
    
    Examples:
        'zhuàng' -> ('zhuang', 4)
        'mā' -> ('ma', 1)
        'zhong1' -> ('zhong', 1)
    """
    # First check for numeric tone (e.g., "zhuang4")
    numeric_match = re.search(r'(\d)$', pinyin)
    if numeric_match:
        tone = int(numeric_match.group(1))
        pinyin_no_tone = pinyin[:-1]
        return pinyin_no_tone, tone
    
    # Check for tone marks
    for vowel, marks in TONE_MARKS.items():
        for tone_idx, mark in enumerate(marks, start=1):
            if mark in pinyin:
                pinyin_no_tone = pinyin.replace(mark, vowel.lower())
                return pinyin_no_tone, tone_idx
    
    # No tone found
    return pinyin, None


def add_tone_to_final(final: str, tone: Optional[int]) -> str:
    """
    Add tone mark to the final.
    
    Rules:
    1. If final has 'a', mark 'a'
    2. Else if final has 'o', mark 'o'
    3. Else if final has 'e', mark 'e'
    4. Special case: If final has both 'i' and 'u' together, mark the second one (i u 并列标在后)
       - Examples: 'iu' -> 'iú' (tone on u), 'ui' -> 'uí' (tone on i)
    5. Else if final has 'i', mark 'i'
    6. Else if final has 'u', mark 'u'
    7. Else if final has 'ü', mark 'ü'
    
    Examples:
        ('ang', 4) -> 'àng'
        ('ou', 2) -> 'óu'
        ('iu', 2) -> 'iú'  (i u together, tone on second)
        ('ui', 2) -> 'uí'  (i u together, tone on second)
        ('i', 1) -> 'ī'
    """
    if not tone or tone < 1 or tone > 4:
        return final
    
    # Special case: i and u together (i u 并列标在后)
    # Check for 'iu' or 'ui' patterns
    if 'iu' in final:
        # Tone goes on 'u' (the second one)
        mark = TONE_MARKS.get('u', [])[tone - 1]
        if mark:
            # Replace the 'u' in 'iu' with the tone mark
            final = final.replace('iu', 'i' + mark, 1)
            return final
    elif 'ui' in final:
        # Tone goes on 'i' (the second one)
        mark = TONE_MARKS.get('i', [])[tone - 1]
        if mark:
            # Replace the 'i' in 'ui' with the tone mark
            final = final.replace('ui', 'u' + mark, 1)
            return final
    
    # Regular priority order for tone placement
    vowels_priority = ['a', 'o', 'e', 'i', 'u', 'ü', 'A', 'O', 'E', 'I', 'U', 'Ü']
    
    for vowel in vowels_priority:
        if vowel in final:
            mark = TONE_MARKS.get(vowel, [])[tone - 1]
            if mark:
                # Replace first occurrence
                final = final.replace(vowel, mark, 1)
                return final
    
    return final


def parse_pinyin(pinyin: str) -> Dict[str, any]:
    """
    Parse pinyin into components: initial, medial, final, tone.
    
    Returns:
        {
            'initial': 'zh' or None,
            'medial': 'u' or None,
            'final': 'ang',
            'toned_final': 'àng' (final with tone),
            'tone': 4 or None,
            'original': 'zhuang4'
        }
    
    Examples:
        'zhuang4' -> {'initial': 'zh', 'medial': 'u', 'final': 'ang', 'toned_final': 'àng', 'tone': 4}
        'ma1' -> {'initial': 'm', 'medial': None, 'final': 'a', 'toned_final': 'ā', 'tone': 1}
        'ai2' -> {'initial': None, 'medial': None, 'final': 'ai', 'toned_final': 'ái', 'tone': 2}
    """
    original = pinyin
    pinyin_lower = pinyin.lower()
    
    # Extract tone
    pinyin_no_tone, tone = extract_tone(pinyin)
    pinyin_no_tone_lower = pinyin_no_tone.lower()
    
    # Find initial (longest match first)
    initial = None
    remaining = pinyin_no_tone_lower
    
    # Sort initials by length (longest first) to match 'zh' before 'z'
    sorted_initials = sorted(PINYIN_INITIALS, key=len, reverse=True)
    
    for init in sorted_initials:
        if pinyin_no_tone_lower.startswith(init):
            initial = init
            remaining = pinyin_no_tone_lower[len(init):]
            break
    
    # Find medial (if present)
    # A medial only exists if there's a final after it
    # For example: "xiao" -> x-i-ao (i is medial, ao is final)
    # But "shi" -> sh-i (i is the final, not a medial)
    medial = None
    if remaining and len(remaining) > 1:
        # Check if first character is a medial AND there's more after it
        first_char = remaining[0]
        if first_char in PINYIN_MEDIALS:
            # The remaining part after the potential medial must be a valid final
            potential_final = remaining[1:]
            # Check if potential_final is a known final or starts with a known final
            is_valid_final = potential_final in PINYIN_FINALS
            if not is_valid_final:
                # Check if any known final starts with potential_final (for partial matches)
                for pf in PINYIN_FINALS:
                    if pf.startswith(potential_final) or potential_final.startswith(pf):
                        is_valid_final = True
                        break
            
            if is_valid_final:
                medial = first_char
                remaining = remaining[1:]
    
    # Remaining is the final
    final = remaining if remaining else None
    
    # Add tone to final
    toned_final = add_tone_to_final(final, tone) if final else None
    
    return {
        'initial': initial,
        'medial': medial,
        'final': final,
        'toned_final': toned_final,
        'tone': tone,
        'original': original
    }


def generate_distractors(component_type: str, correct_value: str, all_components: List[str]) -> List[str]:
    """
    Generate distractor options for a component.
    
    Args:
        component_type: 'initial', 'medial', or 'final'
        correct_value: The correct component value
        all_components: List of all possible values for this component type
    
    Returns:
        List of 2 options: [correct, distractor]
    """
    if not correct_value:
        return [None, None]
    
    # Filter out the correct value
    available = [c for c in all_components if c != correct_value]
    
    if not available:
        return [correct_value, None]
    
    # Select a distractor (prefer similar ones)
    import random
    distractor = random.choice(available)
    
    return [correct_value, distractor]


def test_parser():
    """Test the parser with various examples"""
    test_cases = [
        'zhuang4',
        'ma1',
        'ai2',
        'zhong1',
        'xue2',
        'peng2',
        'er4'
    ]
    
    print("Testing Pinyin Parser:")
    print("=" * 60)
    for pinyin in test_cases:
        result = parse_pinyin(pinyin)
        print(f"\nInput: {pinyin}")
        print(f"  Initial: {result['initial']}")
        print(f"  Medial: {result['medial']}")
        print(f"  Final: {result['final']}")
        print(f"  Toned Final: {result['toned_final']}")
        print(f"  Tone: {result['tone']}")


if __name__ == "__main__":
    test_parser()

