# Data Preparation Tool

Separate application for data preparation tasks, independent from the main Curious Mario application.

## Structure

- `backend/` - FastAPI backend (port 8001)
- `frontend/` - React frontend (port 3001)
- `scripts/` - Batch processing scripts

## Features

1. **Pinyin Gap Fill Suggestions Management**
   - Review and edit suggestions
   - Approve/reject suggestions
   - Save to CSV

2. **Image Extraction**
   - Batch extract images from English Vocabulary .apkg files
   - Automatic renaming: `word.ext`, `word_1.ext` for multiple, `phrase_word.ext` for phrases

## Setup

### Backend

```bash
cd data_prep/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd data_prep/frontend
npm install
npm start
```

Frontend will run on `http://localhost:3001`

## Batch Image Extraction

Extract images from English Vocabulary .apkg files:

```bash
python3 scripts/extract_english_vocab_images.py
```

This will:
- Extract images from `English__Vocabulary__1. Basic.apkg`
- Extract images from `English__Vocabulary__2. Level 2.apkg`
- Rename images according to rules:
  - Single: `word.ext`
  - Multiple: `word_1.ext`, `word_2.ext`, etc.
  - Phrases: `phrase_word.ext` (joined with `_`)
- Save to `media/pinyin/`

