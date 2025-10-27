# -*- coding: utf-8 -*-
import os
import csv
from google.cloud import texttospeech

def generate_audio_files(word_file='basic_words.csv'):
    """
    Reads a CSV file of words and generates high-quality Mandarin audio files
    using Google Cloud's Text-to-Speech API.
    """
    # --- Configuration ---
    OUTPUT_DIR = "audio"
    
    # --- Pre-run Checks ---
    # Check for credentials environment variable
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("ERROR: The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("Please set it to the path of your JSON key file before running.")
        return

    # Check if the word list file exists
    if not os.path.exists(word_file):
        print(f"ERROR: The word list file '{word_file}' was not found.")
        print("Please make sure it's in the same directory as this script.")
        return

    # Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    # --- Main Script ---
    try:
        # Instantiates a client
        client = texttospeech.TextToSpeechClient()

        # Read the word list file using the csv module
        with open(word_file, 'r', encoding='utf-8') as f:
            # Use csv.reader to handle the CSV format
            reader = csv.reader(f)
            # Skip the header row (English,Chinese (Simplified),Pinyin)
            header = next(reader)
            print(f"Reading from CSV with header: {header}")
            
            # Convert reader to a list to get the total count
            rows = list(reader)
            print(f"Found {len(rows)} words to process.")

        for row in rows:
            # Skip empty rows
            if not row:
                continue

            # Unpack the columns
            try:
                english_word, chinese_word, pinyin = row
            except ValueError:
                print(f"Skipping malformed row: {row}")
                continue
            
            # Format the filename as requested: english.mandarin.mp3
            # Replaces spaces with underscores. Casing is preserved.
            filename = english_word.replace(' ', '_') + ".mandarin.mp3"
            output_path = os.path.join(OUTPUT_DIR, filename)

            # Skip if the file already exists to save time and API calls
            if os.path.exists(output_path):
                print(f"Skipping '{chinese_word}', file already exists.")
                continue

            print(f"Generating audio for: {english_word} ({chinese_word}) -> {filename}")

            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=chinese_word)

            # Build the voice request, selecting a high-quality WaveNet voice.
            # WaveNet voices are more natural and fall under the generous free tier.
            voice = texttospeech.VoiceSelectionParams(
                language_code="cmn-CN",
                name="cmn-CN-Wavenet-A"  # A clear, high-quality female voice
            )

            # Select the type of audio file you want
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            # Perform the text-to-speech request
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # The response's audio_content is binary.
            with open(output_path, "wb") as out:
                out.write(response.audio_content)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Please ensure your credentials are correct and you have enabled the Text-to-Speech API.")

    print(f"\nAudio generation process complete. Files are in the '{OUTPUT_DIR}' folder.")

# --- Run the main function ---
if __name__ == "__main__":
    generate_audio_files()
