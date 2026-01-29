#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import urllib.request
import os
import uuid
import base64
import math
import struct

# Unset proxy environment variables
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    if key in os.environ:
        del os.environ[key]

ANKI_CONNECT_URL = "http://localhost:8765"

# --- 1. Generate Real Media Assets ---

def generate_beep_base64(duration_sec=0.5, freq=440.0, sample_rate=44100):
    """Generates a valid WAV sine wave beep and returns base64 string."""
    num_samples = int(duration_sec * sample_rate)
    audio_data = []
    
    # Generate sine wave samples
    for i in range(num_samples):
        sample = 32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate)
        audio_data.append(int(sample))
    
    # Pack data (Little Endian, Short)
    packed_data = struct.pack('<' + 'h' * len(audio_data), *audio_data)
    
    # WAV Header
    header = struct.pack('<4sI4s', b'RIFF', 36 + len(packed_data), b'WAVE')
    fmt = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_header = struct.pack('<4sI', b'data', len(packed_data))
    
    wav_bytes = header + fmt + data_header + packed_data
    return base64.b64encode(wav_bytes).decode('utf-8')

# Generate the beep (0.5s A440)
TEST_AUDIO_B64 = generate_beep_base64()

# 1x1 Red Pixel JPEG (Standard Base64)
TEST_IMAGE_B64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

# --- 2. AnkiConnect Logic ---

def invoke(action, **params):
    requestJson = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    req = urllib.request.Request(ANKI_CONNECT_URL, requestJson)
    with urllib.request.urlopen(req) as response:
        result = json.load(response)
        if result.get('error'):
            raise Exception(result['error'])
        return result['result']

def store_media(filename, b64_data):
    try:
        invoke('storeMediaFile', filename=filename, data=b64_data)
        print(f"✅ Uploaded media: {filename}")
    except Exception as e:
        print(f"❌ Failed to upload {filename}: {e}")

def main():
    print("="*50)
    print("Creating Test CUMA-Word-Entity-v2 Card (Audible Audio)")
    print("="*50)

    deck_name = "CUMA - Test Deck"
    model_name = "CUMA-Word-Entity-v2"
    
    # Create deck
    try:
        invoke('createDeck', deck=deck_name)
        print(f"✅ Deck '{deck_name}' ready")
    except:
        pass

    # Check model
    try:
        models = invoke('modelNames')
        if model_name not in models:
            print(f"❌ Model '{model_name}' missing! Run deploy script first.")
            return
        print(f"✅ Model '{model_name}' found")
    except Exception as e:
        print(f"❌ AnkiConnect Error: {e}")
        return

    # Upload Media
    print("\n📦 Uploading test media files...")
    store_media("cuma_test_image.jpg", TEST_IMAGE_B64)
    store_media("cuma_test_audio.wav", TEST_AUDIO_B64) # Using .wav for generated beep

    # Create Note
    # NOTE: Use split fields WordAudio and WordPicture (v2 schema)
    note = {
        "deckName": deck_name,
        "modelName": model_name,
        "fields": {
            "Word": "苹果",
            "WordAudio": "cuma_test_audio.wav",
            "WordPicture": '<img src="cuma_test_image.jpg">', 
            "Category": "fruit",
            "UUID": str(uuid.uuid4())
        },
        "tags": ["cuma_test"],
        "options": {
            "allowDuplicate": True,
            "duplicateScope": "deck"
        }
    }
    
    try:
        note_id = invoke('addNote', note=note)
        print(f"\n✅ Successfully created test note! ID: {note_id}")
        print("\nTo view the card:")
        print("1. Open Anki")
        print(f"2. Go to deck '{deck_name}'")
        print("3. Click 'Study Now'")
        print("   - You should see a small red square image.")
        print("   - You should hear a clear BEEP sound.")
        print("\nNote: Ensure _cuma_logic_city_data.js is in your collection.media folder for distractors to appear.")
    except Exception as e:
        print(f"❌ Failed to create note: {e}")

if __name__ == "__main__":
    main()
