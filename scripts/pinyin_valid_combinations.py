#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valid Pinyin Combinations based on Standard Chinese Pinyin Table
Reference: https://en.wikipedia.org/wiki/Pinyin_table

This module contains the complete set of valid initial-final combinations
in Standard Chinese, excluding dialectal/nonstandard (italicized) entries.

Structure: {initial: set(final_parts)} where final_parts are just the final portion
"""

# Valid initial-final combinations based on Wikipedia Pinyin table
# Format: {initial: set(finals)} where finals are just the final parts
# Extracted from the table: each row is a final, columns are initials

VALID_PINYIN_COMBINATIONS = {
    # Group a finals
    # Note: bo = b+uo, po = p+uo, mo = m+uo, fo = f+uo (special spellings)
    'b': {'a', 'ai', 'ei', 'ao', 'an', 'en', 'ang', 'eng', 'i', 'ie', 'iao', 'ian', 'in', 'ing', 'u', 'uo'},
    'p': {'ai', 'ei', 'ao', 'an', 'en', 'ang', 'eng', 'i', 'ie', 'iao', 'ian', 'in', 'ing', 'u', 'uo'},
    'm': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'i', 'ie', 'iao', 'iu', 'ian', 'in', 'ing', 'u', 'uo'},
    'f': {'a', 'ei', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'uo'},
    'd': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'ang', 'i', 'ie', 'iao', 'iu', 'ian', 'ing', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},
    't': {'a', 'ai', 'ao', 'ou', 'an', 'eng', 'ang', 'i', 'ie', 'iao', 'ian', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},
    'n': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'i', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'u', 'uo', 'uan', 'ong', 'ü', 'üe'},
    'l': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'eng', 'ang', 'i', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'u', 'uo', 'uan', 'un', 'ong', 'ü', 'üe', 'o'},  # lo
    'g': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ong'},
    'k': {'a', 'ai', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ong'},
    'h': {'a', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ong'},
    # Note: j/q/x + ü are written as u (ju=jü, qu=qü, xu=xü, etc.)
    'j': {'i', 'ia', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'iong', 'u', 'ue', 'uan', 'un'},  # u=ü after j/q/x
    'q': {'i', 'ia', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'iong', 'u', 'ue', 'uan', 'un'},  # u=ü after j/q/x
    'x': {'i', 'ia', 'ie', 'iao', 'iu', 'ian', 'in', 'iang', 'ing', 'iong', 'u', 'ue', 'uan', 'un'},  # u=ü after j/q/x
    'zh': {'i', 'a', 'e', 'ai', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ong'},  # zhi uses special -i
    'ch': {'i', 'a', 'e', 'ai', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'ong'},  # chi uses special -i
    'sh': {'i', 'a', 'e', 'ai', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang'},  # shi uses special -i
    'r': {'i', 'e', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},  # ri uses special -i
    'z': {'i', 'a', 'e', 'ei', 'ao', 'ou', 'an', 'eng', 'ang', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},  # zi uses special -i
    'c': {'i', 'a', 'e', 'ao', 'ou', 'an', 'eng', 'ang', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},  # ci uses special -i
    's': {'i', 'a', 'e', 'ai', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'u', 'uo', 'ui', 'uan', 'un', 'ong'},  # si uses special -i
}

# Standalone finals (no initial, written as yi, ya, wu, wa, etc. when no initial)
# Note: yu = y+ü, yue = y+üe, yuan = y+üan, yun = y+ün, yong = y+iong (where iong = üeng)
STANDALONE_FINALS = {
    'zhi', 'chi', 'shi', 'ri', 'zi', 'ci', 'si',  # Special -i finals
    'a', 'o', 'e', 'ê', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'er',  # Group a
    'yi', 'ya', 'yo', 'ye', 'yao', 'you', 'yan', 'yin', 'yang', 'ying',  # Group i (i->yi)
    'wu', 'wa', 'wo', 'wai', 'wei', 'wan', 'wen', 'wang', 'weng',  # Group u (u->wu)
    'yu', 'yue', 'yuan', 'yun', 'yong',  # Group ü (ü->yu, written as yu not yü)
}

# Build complete set of all valid syllables
ALL_VALID_SYLLABLES = set()

# Add standalone finals
ALL_VALID_SYLLABLES.update(STANDALONE_FINALS)

# Add initial + final combinations
for initial, finals in VALID_PINYIN_COMBINATIONS.items():
    for final in finals:
        # Special cases: bo=buo, po=puo, mo=muo, fo=fuo
        # These are written as bo, po, mo, fo (not buo, puo, muo, fuo)
        if initial in ['b', 'p', 'm', 'f'] and final == 'uo':
            special_spelling = initial + 'o'  # bo, po, mo, fo
            ALL_VALID_SYLLABLES.add(special_spelling)
            # Don't add buo, puo, muo, fuo - those are not the standard spellings
            continue
        
        # Special cases: j/q/x + ü finals are written with u instead of ü
        # ju=jü, jue=jüe, juan=jüan, jun=jün
        # qu=qü, que=qüe, quan=qüan, qun=qün
        # xu=xü, xue=xüe, xuan=xüan, xun=xün
        # In the table, j/q/x combine with u (which represents ü)
        if initial in ['j', 'q', 'x'] and final in ['u', 'ue', 'uan', 'un']:
            # Map: u->ju, ue->jue, uan->juan, un->jun (written forms)
            syllable = initial + final  # ju, jue, juan, jun
            ALL_VALID_SYLLABLES.add(syllable)
            # Also accept canonical ü forms for validation (jü, jüe, etc.)
            ü_mapping = {'u': 'ü', 'ue': 'üe', 'uan': 'üan', 'un': 'ün'}
            canonical = initial + ü_mapping[final]
            ALL_VALID_SYLLABLES.add(canonical)
            continue
        
        # Regular case: just add initial + final
        syllable = initial + final
        ALL_VALID_SYLLABLES.add(syllable)

def is_valid_pinyin_syllable(syllable: str) -> bool:
    """
    Check if a syllable (without tone marks) is valid in Standard Chinese.
    
    Args:
        syllable: Pinyin syllable without tone marks (e.g., 'ma', 'zhang', 'ban', 'bo', 'ju')
    
    Returns:
        True if the syllable is valid according to the standard pinyin table
    """
    # Remove any tone marks first
    syllable_clean = syllable.lower()
    tone_replacements = {
        'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
        'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
        'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
        'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
        'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
        'ǖ': 'ü', 'ǘ': 'ü', 'ǚ': 'ü', 'ǜ': 'ü'
    }
    for tone, base in tone_replacements.items():
        syllable_clean = syllable_clean.replace(tone, base)
    
    # Check direct lookup first
    if syllable_clean in ALL_VALID_SYLLABLES:
        return True
    
    # Handle special spellings: bo=buo, po=puo, mo=muo, fo=fuo
    if syllable_clean in ['bo', 'po', 'mo', 'fo']:
        # These are valid but written differently (bo instead of buo)
        return True
    
    # Handle j/q/x + ü cases: ju, jue, juan, jun are valid (written as u instead of ü)
    # These should already be in ALL_VALID_SYLLABLES, but check canonical forms too
    if len(syllable_clean) >= 2 and syllable_clean[0] in ['j', 'q', 'x']:
        # Check if it could be a ü final written as u
        if syllable_clean in ['ju', 'jue', 'juan', 'jun', 'qu', 'que', 'quan', 'qun', 'xu', 'xue', 'xuan', 'xun']:
            return True
    
    return False
