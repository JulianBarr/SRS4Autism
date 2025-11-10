#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract mastered Chinese words from vocab files.

Reads:
1. basic_words.csv - already has Chinese translations
2. filtered_list1.txt - tab-separated, English words
3. filtered_list2.txt - tab-separated, English words

Outputs a consolidated list of Chinese words the child knows.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add backend directory to path to load API key
BACKEND_DIR = Path(__file__).parent.parent.parent / "backend"
PROJECT_ROOT = Path("/Users/maxent/src/SRS4Autism")
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / "gemini.env")

# Paths
BASIC_WORDS = PROJECT_ROOT / "data/content_db/basic_words.csv"
FILTERED_LIST1 = PROJECT_ROOT / "data/content_db/filtered_list1.txt"
FILTERED_LIST2 = PROJECT_ROOT / "data/content_db/filtered_list2.txt"
OUTPUT_FILE = PROJECT_ROOT / "data/content_db/mastered_words_list.txt"

# Try to initialize Cloud Translation API first (preferred)
# Then fall back to Gemini if service account not available
translation_client = None
translation_model = None

# Check for Google Cloud service account credentials
CREDENTIALS_FILE = BACKEND_DIR / "google-credentials.json"
GOOGLE_PROJECT_ID = None
if CREDENTIALS_FILE.exists():
    try:
        # Read project ID from credentials file
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
            GOOGLE_PROJECT_ID = creds_data.get('project_id')
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(CREDENTIALS_FILE)
        from google.cloud import translate_v3 as translate
        
        translation_client = translate.TranslationServiceClient()
        print("✅ Google Cloud Translation API initialized (service account)")
        print(f"   Project ID: {GOOGLE_PROJECT_ID}")
        print("   Using dedicated translation API - fast and efficient!")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize Cloud Translation API: {e}")
        print("   Falling back to Gemini...")
        translation_client = None
        GOOGLE_PROJECT_ID = None

# Fallback to Gemini if Cloud Translation not available
if not translation_client:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            translation_model = genai.GenerativeModel('models/gemini-2.5-flash')
            print("✅ Gemini API initialized for translation (fallback)")
            print("   Note: For better performance, set up Cloud Translation API")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize Gemini: {e}")
            translation_model = None
    else:
        print("⚠️  Warning: No translation service available")
        print("   Set up either:")
        print("   1. Cloud Translation API: Place google-credentials.json in backend/")
        print("   2. Gemini API: Set GEMINI_API_KEY in backend/gemini.env")

def read_basic_words():
    """Read Chinese words from basic_words.csv"""
    words = set()
    
    print(f"📖 Reading {BASIC_WORDS.name}...")
    
    try:
        with open(BASIC_WORDS, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                chinese = row.get('Chinese (Simplified)', '').strip()
                if chinese:
                    words.add(chinese)
        
        print(f"   ✅ Found {len(words)} unique Chinese words")
        return words
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return words

# Persistent cache file to resume interrupted translations
CACHE_FILE = PROJECT_ROOT / "data/content_db/translation_cache.json"

def load_cache():
    """Load translation cache from disk"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load cache: {e}")
    return {}

def save_cache():
    """Save translation cache to disk"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(translation_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save cache: {e}")

# Cache for translations to avoid re-translating the same words
translation_cache = load_cache()
translation_disabled = False

# Batch translation helper (optimized for Cloud Translation API or Gemini)
def translate_batch(english_words):
    """Translate a list of English words to Chinese in batch (more efficient)"""
    global translation_disabled
    
    # Filter out already cached words
    words_to_translate = [w for w in english_words if w not in translation_cache]
    
    if not words_to_translate:
        # All words are cached
        return {w: translation_cache[w] for w in english_words}
    
    translations = {}
    
    # Try Cloud Translation API first (much faster, no rate limits)
    if translation_client:
        try:
            if not GOOGLE_PROJECT_ID:
                raise ValueError("Project ID not found in credentials file")
            parent = f"projects/{GOOGLE_PROJECT_ID}/locations/global"
            
            # Cloud Translation API can handle large batches efficiently
            # Translate up to 128 texts at a time
            batch_size = 128
            
            for i in range(0, len(words_to_translate), batch_size):
                batch = words_to_translate[i:i + batch_size]
                
                response = translation_client.translate_text(
                    contents=batch,
                    target_language_code='zh-CN',
                    parent=parent
                )
                
                for j, translation in enumerate(response.translations):
                    word = batch[j]
                    chinese = translation.translated_text
                    translations[word] = chinese
                    translation_cache[word] = chinese
            
            # Include cached words in return
            for word in english_words:
                if word in translation_cache and word not in translations:
                    translations[word] = translation_cache[word]
            
            return translations
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️  Cloud Translation batch failed: {error_msg[:100]}")
            # Fall through to Gemini
    
    # Fallback to Gemini batch translation
    if translation_model and not translation_disabled:
        try:
            # Translate up to 50 words at a time to stay within limits
            batch_size = 50
            
            for i in range(0, len(words_to_translate), batch_size):
                batch = words_to_translate[i:i + batch_size]
                
                # Create batch prompt
                words_list = '\n'.join([f"- {word}" for word in batch])
                prompt = f"""Translate the following English words to Chinese (Simplified). Provide ONLY the translations, one per line in the format "English: Chinese". If a word has multiple translations, separate them with commas (,) or Chinese comma (、).

{words_list}

Translations:"""
                
                response = translation_model.generate_content(prompt)
                result_text = response.text.strip()
                
                # Parse results (format: "English: Chinese")
                lines = result_text.split('\n')
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            word = parts[0].strip().lstrip('-').strip()
                            chinese = parts[1].strip()
                            if word in batch:
                                translations[word] = chinese
                                translation_cache[word] = chinese
                
                # Small delay between batches
                time.sleep(0.2)
            
            # Include cached words in return
            for word in english_words:
                if word in translation_cache and word not in translations:
                    translations[word] = translation_cache[word]
            
            return translations
        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                print(f"   ⚠️  Batch translation hit rate limit. Will continue individually.")
                save_cache()
                return {}  # Return empty so individual translation can continue
            else:
                print(f"   ⚠️  Batch translation failed: {error_msg[:100]}")
                return {}
    
    return {}

if translation_cache:
    print(f"✅ Loaded {len(translation_cache)} cached translations")

def translate_to_chinese(english_word):
    """Translate English word to Chinese using Cloud Translation API or Gemini with caching"""
    global translation_disabled
    
    # Check cache first
    if english_word in translation_cache:
        return translation_cache[english_word]
    
    # Try Cloud Translation API first (preferred - fast and no rate limits)
    if translation_client:
        try:
            if not GOOGLE_PROJECT_ID:
                raise ValueError("Project ID not found in credentials file")
            parent = f"projects/{GOOGLE_PROJECT_ID}/locations/global"
            
            response = translation_client.translate_text(
                contents=[english_word],
                target_language_code='zh-CN',
                parent=parent
            )
            
            chinese = response.translations[0].translated_text
            
            # Cache the result
            translation_cache[english_word] = chinese
            return chinese
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️  Cloud Translation failed for '{english_word}': {error_msg[:100]}")
            # Fall through to Gemini if Cloud Translation fails
    
    # Fallback to Gemini
    if translation_model and not translation_disabled:
        try:
            prompt = f"""Translate the following English word to Chinese (Simplified).

Word: {english_word}

Provide ONLY the Chinese translation, without any explanation or extra text.
If there are multiple translations, provide them separated by commas (,) or Chinese comma (、).

Chinese translation:"""
            
            response = translation_model.generate_content(prompt)
            chinese = response.text.strip()
            
            # Clean up the response (remove quotes if any)
            chinese = chinese.strip('"').strip("'")
            
            # Cache the result
            translation_cache[english_word] = chinese
            
            # Minimal delay (Gemini 2.0 Flash has better rate limits)
            time.sleep(0.1)
            
            return chinese
        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                print(f"   ⚠️  Quota exceeded. Stopping translation.")
                translation_disabled = True
                save_cache()  # Save progress before stopping
                return None
            else:
                print(f"   ⚠️  Translation failed for '{english_word}': {error_msg[:100]}")
    
    return None

def extract_chinese_words(text):
    """Extract Chinese words from text, handling separators like comma and 、"""
    if not text:
        return set()
    
    words = set()
    
    # First, split by common separators (comma, 、, etc.)
    # Handle both full-width comma (，) and half-width comma (,)
    parts = text.replace('、', ',').replace('，', ',').split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Extract Chinese characters (consecutive Chinese chars form a word)
        current_word = []
        for char in part:
            if '\u4e00' <= char <= '\u9fff':
                current_word.append(char)
            else:
                # When we hit non-Chinese, save the current word if any
                if current_word:
                    word = ''.join(current_word)
                    if len(word) >= 1:
                        words.add(word)
                    current_word = []
        
        # Don't forget the last word
        if current_word:
            word = ''.join(current_word)
            if len(word) >= 1:
                words.add(word)
    
    return words

def read_filtered_list(file_path):
    """Read English words from filtered_list and translate to Chinese"""
    words = set()
    translated_count = 0
    english_words_to_translate = []  # Collect words for batch translation
    
    print(f"📖 Reading {file_path.name}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments and empty lines
                if line.strip().startswith('#') or not line.strip():
                    continue
                
                # Split by tab
                parts = line.strip().split('\t')
                
                # Handle both formats: [English] or [Chinese, English]
                chinese_hint = ''
                english_word = ''
                
                if len(parts) == 1:
                    # Only one part - this is the English word (first column is empty)
                    english_word = parts[0].strip()
                elif len(parts) >= 2:
                    # Two parts - [Chinese hint, English word]
                    chinese_hint = parts[0].strip()
                    english_word = parts[1].strip()
                
                # Extract Chinese words from hint if available
                if chinese_hint and any('\u4e00' <= char <= '\u9fff' for char in chinese_hint):
                    extracted = extract_chinese_words(chinese_hint)
                    words.update(extracted)
                elif (translation_client or translation_model) and english_word:
                    # Check if word needs translation (not in cache, not Chinese)
                    if english_word not in translation_cache and not any('\u4e00' <= char <= '\u9fff' for char in english_word):
                        english_words_to_translate.append(english_word)
        
        # Translate collected words (batch if possible, otherwise individual)
        if (translation_client or translation_model) and english_words_to_translate:
            print(f"   📝 Translating {len(english_words_to_translate)} words...")
            
            # Reset disabled flag (might have been set from previous run)
            global translation_disabled
            was_disabled = translation_disabled
            translation_disabled = False
            
            # Try batch first
            batch_results = translate_batch(english_words_to_translate)
            
            # Translate remaining words individually (if batch failed or quota hit)
            remaining_words = [w for w in english_words_to_translate if w not in batch_results]
            
            if remaining_words and not translation_disabled:
                print(f"   📝 Translating {len(remaining_words)} remaining words individually...")
                for i, word in enumerate(remaining_words, 1):
                    if translation_disabled:
                        print(f"   ⚠️  Quota hit, stopping at word {i}/{len(remaining_words)}")
                        break
                    chinese_translation = translate_to_chinese(word)
                    if chinese_translation:
                        batch_results[word] = chinese_translation
                    
                    # Progress indicator
                    if i % 50 == 0:
                        print(f"   ... translated {i}/{len(remaining_words)} words")
                        save_cache()  # Save progress periodically
            
            # Process all translations
            for word, chinese_translation in batch_results.items():
                if chinese_translation:
                    extracted = extract_chinese_words(chinese_translation)
                    words.update(extracted)
                    translated_count += 1
            
            if translated_count > 0:
                print(f"   ✅ Translated {translated_count} words")
                save_cache()  # Save cache after translation
        
        print(f"   ✅ Extracted {len(words)} Chinese words")
        if translated_count > 0:
            print(f"   ✅ Translated {translated_count} words from English")
        return words
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return words

def main():
    print("=" * 80)
    print("Extracting Mastered Chinese Words")
    print("=" * 80)
    print()
    
    all_words = set()
    
    # 1. Read from basic_words.csv
    basic_words = read_basic_words()
    all_words.update(basic_words)
    
    # 2. Read from filtered_list1.txt
    filtered1_words = read_filtered_list(FILTERED_LIST1)
    all_words.update(filtered1_words)
    
    # 3. Read from filtered_list2.txt
    filtered2_words = read_filtered_list(FILTERED_LIST2)
    all_words.update(filtered2_words)
    
    # Sort words for output
    sorted_words = sorted(all_words, key=lambda x: (len(x), x))
    
    # Write to output file
    print(f"\n📝 Writing consolidated list to {OUTPUT_FILE.name}...")
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for word in sorted_words:
                f.write(f"{word}\n")
        print(f"   ✅ Successfully wrote {len(sorted_words)} unique words")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Print statistics
    print("\n📊 Statistics:")
    print(f"   Basic words: {len(basic_words)}")
    print(f"   Filtered list 1: {len(filtered1_words)}")
    print(f"   Filtered list 2: {len(filtered2_words)}")
    print(f"   Total unique words: {len(sorted_words)}")
    
    # Show sample
    print("\n📝 Sample words:")
    for word in sorted_words[:20]:
        print(f"   - {word}")
    if len(sorted_words) > 20:
        print(f"   ... and {len(sorted_words) - 20} more")
    
    # Prepare for profile
    print("\n📋 Ready for profile (first 100 words):")
    sample_list = sorted_words[:100]
    print(f"   {', '.join(sample_list)}")
    print(f"\n   Total: {len(sample_list)} words")
    
    # Final cache save
    save_cache()
    
    print("\n" + "=" * 80)
    print("✅ Done!")
    print("=" * 80)

if __name__ == "__main__":
    main()

