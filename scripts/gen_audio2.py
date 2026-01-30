import os
import re
from gtts import gTTS

input_file = 'SRS4Autism__Pinyin.txt'
output_dir = 'data'

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def generate_mp3_gtts():
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split('\t')
        if len(parts) > 5:
            hanzi = parts[1]
            sound_field = parts[5]
            
            # Find filenames starting with cm_
            match = re.search(r'\[sound:(cm_tts_zh_(.*?)\.mp3)\]', sound_field)
            
            if match:
                filename = match.group(1)
                filepath = os.path.join(output_dir, filename)
                
                if not os.path.exists(filepath):
                    print(f"Generating: {filename} via gTTS")
                    try:
                        # 'zh-cn' is the language code for Mandarin
                        tts = gTTS(text=hanzi, lang='zh-cn')
                        tts.save(filepath)
                    except Exception as e:
                        print(f"Error at {filename}: {e}")

if __name__ == "__main__":
    generate_mp3_gtts()
