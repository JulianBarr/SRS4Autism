import os
import re
from google.cloud import texttospeech
from dotenv import load_dotenv

# Load your .env file
load_dotenv()

# Configuration
input_file = 'SRS4Autism__Pinyin.txt' # Adjusted path based on your terminal output
output_dir = 'data'
api_key = os.getenv("GOOGLE_API_KEY")

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def generate_mp3_cloud():
    # Pass the API Key directly to the client options
    client = texttospeech.TextToSpeechClient(
        client_options={"api_key": api_key}
    )

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split('\t')
        if len(parts) > 5:
            hanzi = parts[1]
            sound_field = parts[5]
            
            match = re.search(r'\[sound:(cm_tts_zh_(.*?)\.mp3)\]', sound_field)
            
            if match:
                filename = match.group(1)
                filepath = os.path.join(output_dir, filename)
                
                if os.path.exists(filepath):
                    continue

                print(f"Synthesizing: {filename}")

                synthesis_input = texttospeech.SynthesisInput(text=hanzi)
                voice = texttospeech.VoiceSelectionParams(
                    language_code="cmn-CN",
                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )

                try:
                    response = client.synthesize_speech(
                        input=synthesis_input, voice=voice, audio_config=audio_config
                    )
                    with open(filepath, "wb") as out:
                        out.write(response.audio_content)
                except Exception as e:
                    print(f"Error at {filename}: {e}")

if __name__ == "__main__":
    generate_mp3_cloud()
