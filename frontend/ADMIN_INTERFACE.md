# Pinyin Gap Fill Admin Interface

## Overview

The Pinyin Gap Fill Admin Interface is a **separate data preparation tool** for managing pinyin syllable gap fill suggestions. It is **not part of the main CUMA learning interface** to avoid interference with the learning workflow.

## Access

### Development
Navigate to: `http://localhost:3000/admin/pinyin-gap-fill`

### Production
After building, the admin interface will be accessible at: `/admin/pinyin-gap-fill`

## Features

- Review and edit pinyin gap fill suggestions
- Approve/reject suggestions
- Edit word, pinyin, and image associations
- Save changes to CSV
- Apply approved suggestions to the pinyin deck database

## Backend Endpoints

The admin interface uses separate backend endpoints that don't interfere with CUMA operations:

- `GET /pinyin/gap-fill-suggestions` - Load suggestions from CSV
- `PUT /pinyin/gap-fill-suggestions` - Save edited suggestions to CSV
- `POST /pinyin/apply-suggestions` - Apply approved suggestions to database
- `GET /pinyin/word-info?word=<chinese_word>` - Get word information from knowledge graph

## Data Flow

1. Run `scripts/find_best_pinyin_words.py` to generate suggestions CSV
2. Access admin interface at `/admin/pinyin-gap-fill`
3. Review, edit, and approve suggestions
4. Save changes (updates CSV)
5. Apply approved suggestions (updates database)

## Separation from CUMA

- **Frontend**: Separate route (`/admin/pinyin-gap-fill`) that doesn't interfere with main CUMA interface
- **Backend**: Separate endpoints (`/pinyin/gap-fill-*`) that only interact with CSV and database, not with active learning sessions
- **Data**: Uses separate CSV file (`data/pinyin_gap_fill_suggestions.csv`) for suggestions management

