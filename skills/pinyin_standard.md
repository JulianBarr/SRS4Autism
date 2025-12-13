# PINYIN HANDLING PROTOCOL (CUMA PROJECT)
# Keywords: Pinyin, Mandarin, Pronunciation, Tone, Romanization, 拼音

## 1. Core Philosophy
- **Single Source of Truth:** Do NOT write custom Pinyin conversion logic. Always use `utils.pinyin_utils`.
- **Library:** We use `pypinyin` as the backend engine.

## 2. Pinyin Rules (The "Laws")
If you must explain or generate logic manually, adhere to these strict rules:

### A. Tone Mark Placement (Priority Order)
1.  **a** and **e** always take the tone.
2.  **o** takes the tone (unless with 'a' or 'e').
3.  **i** and **u**:
    - If seen alone or with other vowels (not i/u combo): Follow standard order (a > o > e > i/u).
    - **EXCEPTION:** If `i` and `u` appear together (`iu` or `ui`), the tone mark goes on the **second** vowel.
      - `liu` -> `liú` (on u)
      - `gui` -> `guī` (on i)

### B. Input Normalization
- **'v' Handling:** The letter 'v' must always be treated as 'ü' (u with umlaut).
- **Numeric Tones:** 1-5 (5 is neutral). Example: `lve4` -> `lüè`.
- **Valid Syllables:** Only generate syllables that map to actual Simplified Chinese characters (Modern Putonghua). Avoid constructing theoretical sounds like "kei" (rare) or "bou" (non-existent) unless verifying against the valid set.

### C. Display Formatting
- **Spacing:** STRICTLY impose a space between every syllable.
  - Correct: `ni3 hao3` -> `nǐ hǎo`
  - Incorrect: `nǐhǎo`
- **Case:** Lowercase by default unless starting a sentence.

## 3. Implementation Reference
See `src/utils/pinyin_utils.py` for the canonical implementation.