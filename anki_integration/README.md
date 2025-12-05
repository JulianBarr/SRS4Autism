# Anki Integration

This module integrates SRS4Autism with Anki via the AnkiConnect add-on.

## Setup Instructions

### 1. Install AnkiConnect Add-on

1. Open Anki
2. Go to **Tools** → **Add-ons** → **Get Add-ons...**
3. Enter code: `2055492159`
4. Click **OK** and restart Anki

### 2. Configure AnkiConnect (Optional)

AnkiConnect listens on `http://localhost:8765` by default. No configuration needed.

If you need to change settings:
1. Go to **Tools** → **Add-ons**
2. Select **AnkiConnect**
3. Click **Config**

### 3. Test Connection

Run the test script:

```bash
cd anki_integration
python anki_connect.py
```

You should see:
```
✅ Connected to AnkiConnect successfully!
Available decks: ['Default', 'My Deck', ...]
```

## Usage in SRS4Autism

### From the Web Interface

1. **Create Anki Profile** (optional)
   - Go to Settings
   - Add Anki profile with deck name
   - Or use deck name directly

2. **Sync Cards**
   - Go to **Card Curation** tab
   - Approve cards you want to sync
   - Select approved cards
   - Choose Anki profile/deck
   - Click **Sync to Anki**

### Programmatically

```python
from anki_integration import AnkiConnect

# Initialize client
anki = AnkiConnect()

# Check connection
if anki.ping():
    print("Connected!")

# Add a basic card
note_id = anki.add_basic_card(
    deck_name="SRS4Autism::Chinese",
    front="What is 红色?",
    back="Red (hóngsè)",
    tags=["colors", "hsk1"]
)

# Sync multiple cards
results = anki.sync_cards(
    deck_name="SRS4Autism::Chinese",
    cards=[
        {
            "id": "123",
            "card_type": "basic",
            "front": "Question",
            "back": "Answer",
            "tags": ["tag1"]
        }
    ]
)
```

## Supported Card Types

### 1. Basic Cards
- Front/back format
- Uses Anki's "Basic" note type

### 2. Basic Reverse Cards
- Creates 2 cards (front→back and back→front)
- Uses Anki's "Basic (and reversed card)" note type

### 3. Cloze Deletion Cards
- Fill-in-the-blank format
- Uses Anki's "Cloze" note type
- Example: `"The {{c1::answer}} is here"`

## Troubleshooting

### "Cannot connect to Anki"

**Causes:**
1. Anki is not running
2. AnkiConnect add-on is not installed
3. Firewall blocking localhost:8765

**Solutions:**
1. Start Anki
2. Install AnkiConnect (see setup instructions)
3. Check firewall settings

### "Note type not found"

**Cause:** Required note type doesn't exist in Anki

**Solution:** Anki comes with Basic and Cloze note types by default. If using custom templates, create them in Anki first.

### Cards not appearing in Anki

**Cause:** Deck doesn't exist

**Solution:** The integration automatically creates decks if they don't exist. If issues persist, manually create the deck in Anki first.

## API Reference

See `anki_connect.py` for full API documentation.

### Key Methods

- `ping()` - Test connection
- `get_deck_names()` - List all decks
- `create_deck(name)` - Create new deck
- `add_basic_card(deck, front, back, tags)` - Add basic card
- `add_cloze_card(deck, text, extra, tags)` - Add cloze card
- `sync_cards(deck, cards)` - Sync multiple cards

## Security Note

AnkiConnect only accepts connections from localhost by default. If you need remote access, configure it in the add-on settings (not recommended for security reasons).

## Links

- [AnkiConnect GitHub](https://github.com/FooSoft/anki-connect)
- [AnkiConnect Add-on Page](https://ankiweb.net/shared/info/2055492159)
- [Anki Manual](https://docs.ankiweb.net/)


