# SRS4Autism POC - Setup Guide

This is the first proof-of-concept for the Agent-based SRS4Autism system.

## Features Implemented

### Frontend
- **Chat Assistant**: Interactive chat interface with mention system
- **Card Curation**: Review and approve generated flashcards
- **Profile Manager**: Create and manage child profiles
- **Context Tagging**: @mention system for profiles and actors

### Backend
- **FastAPI REST API**: Full CRUD operations for profiles and cards
- **AI Agent Integration**: Content generation using OpenAI
- **Card Management**: Support for basic, reverse, and cloze cards
- **File-based Storage**: JSON files for data persistence

### AI Agent
- **Content Generation**: Creates flashcards from natural language prompts
- **Multiple Card Types**: Basic, Basic Reverse, and Cloze deletion cards
- **Context Awareness**: Uses child profiles for personalized content

## Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=your_key_here" > .env

# Run the backend
python run.py
```

The backend will be available at `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm start
```

The frontend will be available at `http://localhost:3000`

## Usage

### 1. Create Child Profiles
- Go to the "Profiles" tab
- Click "Add New Profile"
- Fill in child information (name, age, interests, etc.)
- Save the profile

### 2. Generate Content via Chat
- Go to the "Chat Assistant" tab
- Type a request like: "Create flashcards about colors for @Alex"
- The AI will generate 3 types of cards (basic, reverse, cloze)
- Cards will appear in the "Card Curation" tab

### 3. Review and Approve Cards
- Go to the "Card Curation" tab
- Review generated cards
- Select cards to approve
- Choose Anki profile for syncing
- Sync approved cards to Anki

## Card Types

### Basic Cards
- Front: Question or prompt
- Back: Answer
- Example: "What color is the sky?" → "Blue"

### Basic Reverse Cards
- Works both ways
- Front to back and back to front
- Example: "What is 2+2?" ↔ "4"

### Cloze Cards
- Fill-in-the-blank format
- Uses Anki's cloze deletion syntax
- Example: "The sky is {{c1::blue}}"

## API Endpoints

### Profiles
- `GET /profiles` - List all profiles
- `POST /profiles` - Create new profile
- `GET /profiles/{name}` - Get specific profile

### Cards
- `GET /cards` - List all cards
- `POST /cards` - Create new card
- `PUT /cards/{id}/approve` - Approve card

### Chat
- `POST /chat` - Send message to AI agent

### Anki Profiles
- `GET /anki-profiles` - List Anki profiles
- `POST /anki-profiles` - Create Anki profile

## Data Storage

All data is stored in JSON files:
- `data/profiles/child_profiles.json` - Child profiles
- `data/content_db/approved_cards.json` - Generated cards
- `data/profiles/anki_profiles.json` - Anki profiles

## Next Steps

1. **AnkiConnect Integration**: Connect to local Anki instance
2. **Enhanced AI**: More sophisticated content generation
3. **Knowledge Graph**: Structured knowledge representation
4. **Learning Analytics**: Track learning progress
5. **Multi-modal Content**: Images and audio generation

## Troubleshooting

### Backend Issues
- Ensure OpenAI API key is set in `.env`
- Check that port 8000 is available
- Verify all dependencies are installed

### Frontend Issues
- Ensure Node.js and npm are installed
- Check that port 3000 is available
- Verify backend is running on port 8000

### AI Generation Issues
- Check OpenAI API key is valid
- Verify internet connection
- Check API rate limits

## Development

### Adding New Card Types
1. Update `ContentGenerator` class in `agent/content_generator.py`
2. Add new card type to frontend `CardCuration` component
3. Update card preview rendering

### Adding New Profile Fields
1. Update `ChildProfile` model in `backend/app/main.py`
2. Update `ProfileManager` component in frontend
3. Update profile display logic

### Enhancing AI Agent
1. Modify `ContentGenerator` class
2. Add new generation methods
3. Integrate with external APIs
4. Add context awareness features



