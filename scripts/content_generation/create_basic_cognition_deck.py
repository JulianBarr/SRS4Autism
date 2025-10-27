import genanki
import csv
import os
import random
import re

# --- Configuration ---
CSV_FILE = 'basic_words.csv'
IMAGE_MAPPING_FILE = 'eng_recovered.csv' # The new file mapping English words to image filenames
IMAGE_DIR = 'images'
AUDIO_DIR = 'audio'
DECK_NAME = 'Mandarin Naming Deck'
DECK_ID = random.randrange(1 << 30, 1 << 31)
MODEL_ID = random.randrange(1 << 30, 1 << 31)

# --- Anki Model Definition ---
# This defines the structure of each "note" or flashcard entry.
anki_model = genanki.Model(
    MODEL_ID,
    'Mandarin Naming Model (4-way)',
    fields=[
        {'name': 'English'},
        {'name': 'Chinese'},
        {'name': 'Pinyin'},
        {'name': 'Audio'},
        {'name': 'Image'},
        # Fields for Multiple Choice distractors
        {'name': 'DistractorText1'},
        {'name': 'DistractorText2'},
        {'name': 'DistractorImage1'},
        {'name': 'DistractorImage2'},
    ],
    templates=[
        # --- Template 1: Picture -> Type Pinyin ---
        {
            'name': '1. Pic -> Type Pinyin',
            'qfmt': '''
                <div class="card-container">
                    <div class="image-q">{{Image}}</div>
                    <div class="prompt-text">What is this in Pinyin?</div>
                    {{type:Pinyin}}
                </div>
            ''',
            'afmt': '''
                <div class="card-container">
                    <div class="image-q">{{Image}}</div>
                    <div class="answer-section">
                        <div class="chinese-answer">{{Chinese}}</div>
                        <div class="pinyin-answer">{{Pinyin}}</div>
                        <div class="english-answer">{{English}}</div>
                        {{Audio}}
                    </div>
                </div>
            ''',
        },
        # --- Template 2: Audio -> Picture ---
        {
            'name': '2. Audio -> Pic (Listening)',
            'qfmt': '''
                <div class="card-container">
                    <div class="prompt-text">What do you hear?</div>
                    <div class="audio-q">{{Audio}}</div>
                    <button class="replay-button" onclick="document.querySelector('.audio-q audio').play();">Replay Audio</button>
                </div>
            ''',
            'afmt': '''
                <div class="card-container">
                    <div class="image-a">{{Image}}</div>
                     <div class="answer-section">
                        <div class="chinese-answer">{{Chinese}}</div>
                        <div class="pinyin-answer">{{Pinyin}}</div>
                        <div class="english-answer">{{English}}</div>
                    </div>
                </div>
            ''',
        },
        # --- Template 3: MCQ (Picture -> Reading) ---
        {
            'name': '3. MCQ Pic -> Text (Reading)',
            'qfmt': '''
                <div class="card-container">
                    <div class="image-q">{{Image}}</div>
                    <div class="prompt-text">Which word matches the picture?</div>
                    <div id="choices" class="mcq-choices">
                        <div class="choice">{{Chinese}}</div>
                        <div class="choice">{{DistractorText1}}</div>
                        <div class="choice">{{DistractorText2}}</div>
                    </div>
                </div>
                <script>
                    var choices = document.getElementById("choices");
                    for (var i = choices.children.length; i >= 0; i--) {
                        choices.appendChild(choices.children[Math.random() * i | 0]);
                    }
                </script>
            ''',
            'afmt': '''
                <div class="card-container">
                    <div class="image-q">{{Image}}</div>
                    <div class="prompt-text">Correct! It's:</div>
                     <div class="answer-section">
                        <div class="chinese-answer correct-choice">{{Chinese}}</div>
                        <div class="pinyin-answer">{{Pinyin}}</div>
                        <div class="english-answer">{{English}}</div>
                        {{Audio}}
                    </div>
                </div>
            ''',
        },
        # --- Template 4: MCQ (Audio -> Picture) ---
        {
            'name': '4. MCQ Audio -> Pic (Listening)',
            'qfmt': '''
                <div class="card-container">
                    <div class="prompt-text">Which picture matches the sound?</div>
                    <div class="audio-q">{{Audio}}</div>
                    <button class="replay-button" onclick="document.querySelector('.audio-q audio').play();">Replay Audio</button>
                    <div id="choices" class="mcq-image-choices">
                        <div class="choice-img">{{Image}}</div>
                        <div class="choice-img">{{DistractorImage1}}</div>
                        <div class="choice-img">{{DistractorImage2}}</div>
                    </div>
                </div>
                 <script>
                    var choices = document.getElementById("choices");
                    for (var i = choices.children.length; i >= 0; i--) {
                        choices.appendChild(choices.children[Math.random() * i | 0]);
                    }
                </script>
            ''',
            'afmt': '''
                <div class="card-container">
                     <div class="prompt-text">Correct! It's:</div>
                    <div class="image-a correct-image">{{Image}}</div>
                     <div class="answer-section">
                        <div class="chinese-answer">{{Chinese}}</div>
                        <div class="pinyin-answer">{{Pinyin}}</div>
                        <div class="english-answer">{{English}}</div>
                    </div>
                </div>
            ''',
        },
    ],
    css='''
        .card {
            font-family: Arial, sans-serif;
            font-size: 24px;
            text-align: center;
            color: black;
            background-color: #F0F8FF; /* Alice Blue */
        }
        .card-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
        }
        .image-q img, .image-a img {
            max-width: 250px;
            max-height: 250px;
            border-radius: 15px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .prompt-text {
            margin: 20px 0;
            font-size: 20px;
            color: #555;
        }
        .answer-section {
            margin-top: 20px;
        }
        .chinese-answer {
            font-size: 48px;
            font-weight: bold;
            color: #2c3e50;
        }
        .pinyin-answer, .english-answer {
            font-size: 22px;
            color: #7f8c8d;
        }
        .replay-button {
            padding: 10px 20px;
            font-size: 18px;
            border-radius: 8px;
            border: none;
            background-color: #3498db;
            color: white;
            cursor: pointer;
            margin-top: 15px;
        }
        /* MCQ Styles */
        .mcq-choices .choice, .mcq-image-choices .choice-img {
            display: inline-block;
            margin: 10px;
            padding: 15px;
            border: 2px solid #bdc3c7;
            border-radius: 12px;
            cursor: pointer;
        }
        .mcq-choices .choice { font-size: 32px; }
        .mcq-image-choices .choice-img img { max-width: 150px; max-height: 150px; }

        /* Answer Side Highlighting */
        .cloze, .correct-choice { color: #27ae60; font-weight: bold; }
        .correct-image { border: 5px solid #27ae60; border-radius: 20px; }
    '''
)

def create_image_map(mapping_file):
    """Reads the image mapping file and returns a dictionary."""
    image_map = {}
    print(f"Reading image map from '{mapping_file}'...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '|' in line:
                img_tag, english_word = line.split('|', 1)

                # --- THIS IS THE FIX ---
                # A more precise regex to capture only valid filename characters.
                # It looks for src= and then captures a sequence of letters, numbers, underscores, hyphens, and dots.
                match = re.search(r'src=([\w\._-]+)', img_tag)
                
                if match:
                    # Strip whitespace from the captured filename and the English word key.
                    filename = match.group(1).strip()
                    word_key = english_word.strip()
                    image_map[word_key] = filename
                    
    print(f"Found {len(image_map)} image mappings.")
    return image_map

def create_anki_deck():
    """Generates the Anki deck from the CSV and media files."""
    
    # --- Pre-run Checks ---
    for f in [CSV_FILE, IMAGE_MAPPING_FILE, IMAGE_DIR, AUDIO_DIR]:
        if not os.path.exists(f):
            print(f"ERROR: Required file or directory not found: '{f}'")
            return

    # --- Read Data ---
    image_map = create_image_map(IMAGE_MAPPING_FILE)
    
    print(f"Reading words from '{CSV_FILE}'...")
    all_words = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if row:
                all_words.append(dict(zip(header, row)))

    # --- Create Deck and Notes ---
    anki_deck = genanki.Deck(DECK_ID, DECK_NAME)
    media_files = set() # Use a set to avoid duplicate media files

    print(f"Processing {len(all_words)} words and creating notes...")
    for word_data in all_words:
        english = word_data['English']
        chinese = word_data['Chinese (Simplified)']
        pinyin = word_data['Pinyin']
        
        # --- Find Media Files using the map ---
        image_name = image_map.get(english.strip()) # Also strip whitespace from the lookup key
        if image_name:
            image_path = os.path.join(IMAGE_DIR, image_name)
            if os.path.exists(image_path):
                media_files.add(image_path)
            else:
                print(f"Warning: Image file '{image_name}' not found for '{english}'")
                image_name = None # Invalidate if file doesn't exist
        else:
            print(f"Warning: No image mapping found for '{english}'")
        
        audio_filename = english.replace(' ', '_') + ".mandarin.mp3"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        if os.path.exists(audio_path):
            media_files.add(audio_path)
        
        if not image_name:
            print(f"--> Skipping note for '{english}' due to missing image.")
            continue

        # --- Get Distractors for MCQs ---
        other_words = [w for w in all_words if w['English'] != english]
        if len(other_words) < 2:
            print("Warning: Not enough other words to create distractors.")
            continue
        distractors = random.sample(other_words, 2)

        distractor_text1 = distractors[0]['Chinese (Simplified)']
        distractor_text2 = distractors[1]['Chinese (Simplified)']

        # Find images for distractors using the map
        distractor_image1_name = image_map.get(distractors[0]['English'].strip())
        distractor_image2_name = image_map.get(distractors[1]['English'].strip())
        
        # --- Create Anki Note ---
        # Only create the note if we have all necessary images for the MCQs
        if all([image_name, distractor_image1_name, distractor_image2_name]):
            anki_note = genanki.Note(
                model=anki_model,
                fields=[
                    english,
                    chinese,
                    pinyin,
                    f"[sound:{audio_filename}]",
                    f'<img src="{image_name}">',
                    distractor_text1,
                    distractor_text2,
                    f'<img src="{distractor_image1_name}">',
                    f'<img src="{distractor_image2_name}">'
                ]
            )
            anki_deck.add_note(anki_note)
        else:
            print(f"Warning: Could not find all distractor images for '{english}'. Skipping note.")

    # --- Package and Save Deck ---
    anki_package = genanki.Package(anki_deck)
    anki_package.media_files = list(media_files)
    output_filename = DECK_NAME.replace(' ', '_') + '.apkg'
    anki_package.write_to_file(output_filename)
    
    print(f"\nSuccessfully created Anki deck: '{output_filename}'")
    print(f"It contains {len(anki_deck.notes)} notes.")

if __name__ == "__main__":
    create_anki_deck()


