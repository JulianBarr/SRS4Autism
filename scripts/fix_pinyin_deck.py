import csv
import os
import re

# --- Configuration ---
DATA_DIR = '../data/'
INPUT_PINYIN = DATA_DIR + 'pinyi_1206.txt'
OUTPUT_FILE = DATA_DIR + 'pinyin_curriculum_final.tsv'

# --- Stage Definitions ---
# Standardized on proper Pinyin (ü)
STAGE_ORDER = {
    'a': 1, 'o': 1, 'e': 1, 'i': 1, 'u': 1, 'ü': 1, 'b': 1, 'p': 1, 'm': 1, 'f': 1, # Lips
    'ai': 2, 'ei': 2, 'ui': 2, 'ao': 2, 'ou': 2, 'iu': 2, 'd': 2, 't': 2, 'n': 2, 'l': 2, # Tip
    'an': 3, 'en': 3, 'in': 3, 'un': 3, 'ün': 3, 'g': 3, 'k': 3, 'h': 3, # Root
    'ang': 4, 'eng': 4, 'ing': 4, 'ong': 4, 'z': 4, 'c': 4, 's': 4, 'zh': 4, 'ch': 4, 'sh': 4, 'r': 4, # Teeth/Curl
    'y': 5, 'w': 5, 'j': 5, 'q': 5, 'x': 5, # Magic
    # Complex finals
    'ia': 5, 'ie': 5, 'iao': 5, 'ian': 5, 'iang': 5, 'iong': 5,
    'ua': 5, 'uo': 5, 'uai': 5, 'uan': 5, 'uang': 5,
    'ue': 5, 'üe': 5, 'üan': 5 # 've' -> 'üe', 'van' -> 'üan'
}

# Finals list for gap detection (Standardizing on 'v' for ü)
# We will use this to generate the "missing" rows.
STANDARD_FINALS = [
    'a', 'o', 'e', 'i', 'u', 'ü',
    'ai', 'ei', 'ui', 'ao', 'ou', 'iu', 'ie', 'üe', 'er',
    'an', 'en', 'in', 'un', 'ün',
    'ang', 'eng', 'ing', 'ong',
    'ia', 'ua', 'uo', 'uai', 'uan', 'uang', 'ue', 'iang', 'iong', 'iao', 'ian', 'üan'
]

def normalize_pinyin(text):
    """
    Converts input hacks (v) to proper Pinyin (ü).
    e.g. 'lv' -> 'lü', 'nv' -> 'nü', 've' -> 'üe'
    """
    if not text: return text
    return text.replace('v', 'ü')

def parse_pinyin_file():
    """Reads the current pinyin file."""
    headers = []
    data_rows = []
    
    if not os.path.exists(INPUT_PINYIN):
        print(f"Error: Input file {INPUT_PINYIN} not found.")
        return [], []

    with open(INPUT_PINYIN, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if not row: continue
            if row[0].startswith('#'):
                headers.append(row)
                continue
            
            group = normalize_pinyin(row[0])
            
            is_header = False
            for col in row:
                if "Teaching card" in str(col):
                    is_header = True
                    break
            
            if len(row) > 2 and normalize_pinyin(row[1]) == group and "<img" in row[2]:
                is_header = True

            data_rows.append({
                'group': group,
                'is_header_row': is_header,
                'content': row
            })
    return headers, data_rows

def fill_missing_combinations(grouped_data):
    """
    Iterates through all valid Pinyin combinations.
    If a combination is missing from the grouped_data, adds a placeholder row.
    """
    initials = [k for k, v in STAGE_ORDER.items() if len(k) <= 2 and k not in STANDARD_FINALS]
    initials += ['a', 'o', 'e'] 

    for init in initials:
        if init not in grouped_data: continue

        for fin in STANDARD_FINALS:
            # --- Validity Rules (Simplified) ---
            if init in ['j', 'q', 'x'] and not (fin.startswith('i') or fin.startswith('ü')):
                continue
            
            if init in ['a', 'o', 'e']:
                 syllable = init 
                 if fin != init: continue 
            else:
                syllable = init + fin

            exists = False
            for row in grouped_data[init]['examples']:
                # Basic check stripping tones
                existing_syllable = row[1].replace('ā','a').replace('á','a').replace('ǎ','a').replace('à','a') \
                                          .replace('ō','o').replace('ó','o').replace('ǒ','o').replace('ò','o') \
                                          .replace('ē','e').replace('é','e').replace('ě','e').replace('è','e') \
                                          .replace('ī','i').replace('í','i').replace('ǐ','i').replace('ì','i') \
                                          .replace('ū','u').replace('ú','u').replace('ǔ','u').replace('ù','u') \
                                          .replace('ǖ','ü').replace('ǘ','ü').replace('ǚ','ü').replace('ǜ','ü')
                if existing_syllable == syllable:
                    exists = True
                    break
            
            if not exists:
                new_row = [''] * 20
                new_row[0] = init
                new_row[1] = syllable
                new_row[2] = "[MISSING]"
                new_row[7] = "Auto-generated Missing Combo"
                grouped_data[init]['examples'].append(new_row)
    
    return grouped_data

def fix_and_merge(data_rows):
    grouped_data = {k: {'header': None, 'examples': []} for k in STAGE_ORDER.keys()}
    
    for item in data_rows:
        group = item['group']
        if group not in grouped_data:
            grouped_data[group] = {'header': None, 'examples': []}
            
        raw_row = item['content']
        normalized_row = list(raw_row) 
        if len(normalized_row) > 0: normalized_row[0] = normalize_pinyin(normalized_row[0])
        if len(normalized_row) > 1: normalized_row[1] = normalize_pinyin(normalized_row[1])
        
        if item['is_header_row']:
            if not grouped_data[group]['header']:
                grouped_data[group]['header'] = normalized_row
        else:
            pinyin = normalized_row[1]
            exists = any(x[1] == pinyin for x in grouped_data[group]['examples'])
            if not exists:
                grouped_data[group]['examples'].append(normalized_row)

    for group in STAGE_ORDER.keys():
        if not grouped_data[group]['header'] and not grouped_data[group]['examples']:
            new_header = [''] * 20
            new_header[0] = group
            new_header[1] = group 
            new_header[2] = f"[{group.upper()}]" 
            new_header[3] = "-"
            new_header[7] = f"MISSING HEADER for {group}" 
            grouped_data[group]['header'] = new_header

    grouped_data = fill_missing_combinations(grouped_data)

    return grouped_data

def write_output(headers, grouped_data):
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for h in headers:
            writer.writerow(h)
        sorted_keys = sorted(grouped_data.keys(), key=lambda k: (STAGE_ORDER.get(k, 99), k))
        for group in sorted_keys:
            data = grouped_data[group]
            if data['header']:
                writer.writerow(data['header'])
            for ex in data['examples']:
                writer.writerow(ex)

if __name__ == "__main__":
    headers, rows = parse_pinyin_file()
    cleaned_data = fix_and_merge(rows)
    write_output(headers, cleaned_data)
    print(f"Cleaned and sorted file written to: {OUTPUT_FILE}")