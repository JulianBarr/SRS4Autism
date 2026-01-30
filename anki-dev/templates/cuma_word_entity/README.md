# CUMA-Word-Entity Note Type

A 4-stage progressive learning system for autism education, implementing "Concept-to-Sound" mapping with dynamic distractor generation.

## Overview

The CUMA-Word-Entity note type implements a **4-stage funnel** that progressively increases difficulty:

1. **Stage 1: Receptive Easy** - Audio + Picture, 1 Target + 1 Distractor (different category)
2. **Stage 2: Expressive Easy** - Picture only, 1 Target + 1 Distractor (different category), audio plays on correct click
3. **Stage 3: Receptive Hard** - Audio + Picture, 1 Target + 3 Distractors (same category, 4-grid layout)
4. **Stage 4: Expressive Hard** - Picture only, 1 Target + 5 Distractors (mixed source, 6-grid layout)

## Design Philosophy

- **No hardcoded distractors** - All distractors are generated dynamically via JavaScript
- **External data file** - Uses `_cuma_logic_city_data.js` stored in `collection.media` folder
- **Minimal fields** - Only 4 fields: Word, Media, Category, UUID
- **Touch-friendly** - Large buttons optimized for autistic motor skills

## Setup Instructions

### 1. Deploy the Note Type

Run the deployment script:

```bash
cd /Users/maxent/src/SRS4Autism/anki-dev
python3 deploy_cuma_word_entity.py
```

This will:
- Create the "CUMA-Word-Entity" note type in Anki
- Set up all 4 card templates
- Apply the CSS styling

### 2. Copy Data File to Anki Media Folder

The `_cuma_logic_city_data.js` file must be placed in Anki's `collection.media` folder:

1. Open Anki
2. Go to **Tools** → **Add-ons** → **View Files**
3. Navigate to the `collection.media` folder
4. Copy `_cuma_logic_city_data.js` into this folder

**Important:** The underscore prefix (`_`) prevents Anki's media cleaner from removing this file.

### 3. Customize the Data File

Edit `_cuma_logic_city_data.js` in the Anki media folder to add your word categories:

```javascript
window.CUMA_DATA = {
  "kitchen": ["碗", "盘", "勺", "筷子"],
  "fruit": ["苹果", "香蕉", "葡萄"],
  "animal": ["狗", "猫", "鸟"],
  // Add more categories as needed
  "all_words": [] // Auto-populated
};
```

### 4. Create Notes

When creating notes, use these fields:

- **Word**: The target Hanzi (e.g., "朋友")
- **Media**: Both image and audio tags (e.g., `<img src="friend.jpg">[sound:friend.mp3]`)
- **Category**: The semantic key (e.g., "kitchen", "fruit")
- **UUID**: Unique identifier for tracking (can be auto-generated)

## Field Details

### Word Field
The target Chinese character(s) to learn. Example: `朋友`

### Media Field
Contains both image and audio. Anki allows dragging both into one field. The templates automatically parse this to:
- Extract the image for display
- Extract the audio for playback control

Format examples:
- `<img src="friend.jpg">[sound:friend.mp3]`
- `<img src="friend.jpg"><audio src="friend.mp3"></audio>`

### Category Field
The semantic category key that matches a key in `CUMA_DATA`. This determines:
- **Stage 1/2**: Distractors come from different categories
- **Stage 3**: Distractors come from the same category (precision training)
- **Stage 4**: Mixed distractors (some same, some random)

### UUID Field
Used for deterministic random number generation, ensuring the same card always shows the same distractors.

## Card Behavior

### Stage 1: Receptive Easy
- **Trigger**: Audio auto-plays + Picture shown
- **Options**: 2 buttons (1 target + 1 distractor from different category)
- **Layout**: 2-column grid

### Stage 2: Expressive Easy
- **Trigger**: Picture only (no audio auto-play)
- **Options**: 2 buttons (1 target + 1 distractor from different category)
- **Layout**: 2-column grid
- **Feedback**: Clicking correct answer plays audio immediately

### Stage 3: Receptive Hard (Precision)
- **Trigger**: Audio auto-plays + Picture shown
- **Options**: 4 buttons (1 target + 3 distractors from same category)
- **Layout**: 2x2 grid
- **Purpose**: Tests precision by using semantically similar distractors

### Stage 4: Expressive Hard (Crowded Room)
- **Trigger**: Picture only (no audio auto-play)
- **Options**: 6 buttons (1 target + 5 distractors, mixed source)
- **Layout**: 3x2 grid
- **Purpose**: High-density visual search challenge
- **Feedback**: Clicking correct answer plays audio immediately

## Technical Details

### Data Loading
- Uses `<script src="_cuma_logic_city_data.js"></script>` to load data
- Implements retry logic (up to 2 seconds) if data hasn't loaded yet
- Falls back gracefully if data is unavailable

### Media Parsing
The templates use regex to parse the Media field:
- Extracts `<img>` tags for display
- Extracts `[sound:filename.mp3]` or `<audio>` tags for playback
- Handles both formats automatically

### Seeded Random
Uses UUID-based seeded random number generation for:
- Deterministic distractor selection
- Consistent shuffling
- Same card always shows same options

### IIFE Pattern
All JavaScript is wrapped in IIFEs to prevent "Zombie State" bugs in Anki's WebView:
```javascript
(function() {
  // All code here
})();
```

## Troubleshooting

### Data File Not Loading
- Ensure `_cuma_logic_city_data.js` is in `collection.media` folder
- Check file name matches exactly (case-sensitive)
- Verify the file contains valid JavaScript syntax

### Distractors Not Generating
- Check that `window.CUMA_DATA` is defined in the data file
- Verify the Category field matches a key in `CUMA_DATA`
- Ensure there are enough words in the categories

### Audio Not Playing
- Check that audio files are in the media folder
- Verify the `[sound:...]` tag format is correct
- On mobile, ensure autoplay is allowed in browser settings

## File Structure

```
cuma_word_entity/
├── README.md
├── _cuma_logic_city_data.js          # Data file (copy to collection.media)
├── cuma_word_entity.css               # Styling
├── stage1_receptive_easy_front.html
├── stage1_receptive_easy_back.html
├── stage2_expressive_easy_front.html
├── stage2_expressive_easy_back.html
├── stage3_receptive_hard_front.html
├── stage3_receptive_hard_back.html
├── stage4_expressive_hard_front.html
└── stage4_expressive_hard_back.html
```

## License

Part of the SRS4Autism project.






