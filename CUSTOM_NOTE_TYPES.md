# Custom Note Types - Interactive Cloze

## Overview

The system now supports custom Anki note types, specifically the "Interactive Cloze" card with `[[c1::answer]]` syntax and click-to-reveal functionality.

## Architecture

### **Data Flow:**

```
User: "Create sentence cards about colors"
    ↓
Gemini generates Interactive Cloze card:
{
  "card_type": "interactive_cloze",
  "note_type": "Interactive Cloze",
  "text_field": "The [[c1::sky]] is [[c2::blue]]",
  "extra_field": "Colors in nature",
  "tags": ["colors", "nature"]
}
    ↓
Frontend displays preview with [[c1::...]] visible
    ↓
User approves and syncs
    ↓
AnkiConnect adds to "Interactive Cloze" note type
    ↓
Card appears in Anki with clickable blanks!
```

## Card Type Support

### **1. Interactive Cloze** (New!)
```json
{
  "card_type": "interactive_cloze",
  "note_type": "Interactive Cloze",
  "text_field": "The [[c1::sky]] is [[c2::blue]] and grass is [[c3::green]]",
  "extra_field": "Optional hint or context",
  "tags": ["colors"]
}
```

**Anki Note Type:** "Interactive Cloze"  
**Fields:** Text, Extra  
**Syntax:** `[[c1::answer]]` (NOT `{{c1::answer}}`)

### **2. Basic Cards**
```json
{
  "card_type": "basic",
  "front": "What color is the sky?",
  "back": "Blue",
  "tags": ["colors"]
}
```

**Anki Note Type:** "Basic"  
**Fields:** Front, Back

### **3. Basic Reverse Cards**
```json
{
  "card_type": "basic_reverse",
  "front": "Red",
  "back": "红色 (hóngsè)",
  "tags": ["colors"]
}
```

**Anki Note Type:** "Basic (and reversed card)"  
**Fields:** Front, Back

## Setting Up in Anki

### **Step 1: Create Note Type**

1. **Tools** → **Manage Note Types** → **Add**
2. **Clone from:** "Basic"
3. **Name:** "Interactive Cloze"
4. **Click "Fields..."**
   - Rename "Front" to "Text"
   - Rename "Back" to "Extra"
5. **Click "Cards..."**
6. **Copy templates from the previous message**
7. **Save**

### **Step 2: Use in SRS4Autism**

The system will automatically:
- Generate cards with `card_type: "interactive_cloze"`
- Set `note_type: "Interactive Cloze"`
- Use `text_field` for the Text field
- Use `extra_field` for the Extra field
- Sync to the correct note type in Anki

## AI Generation Examples

### **Example 1: Colors**
**Prompt:** "Create sentence cards about @word:colors"

**Gemini generates:**
```json
{
  "card_type": "interactive_cloze",
  "note_type": "Interactive Cloze",
  "text_field": "The [[c1::sky]] is [[c2::blue]] and the [[c3::grass]] is [[c4::green]].",
  "extra_field": "Common colors in nature",
  "tags": ["colors", "nature", "sentences"]
}
```

### **Example 2: With Character**
**Prompt:** "Create cards about @word:brave with @character:Pinocchio"

**Gemini generates:**
```json
{
  "card_type": "interactive_cloze",
  "note_type": "Interactive Cloze",
  "text_field": "[[c1::Pinocchio]] was [[c2::brave]] when he told the [[c3::truth]].",
  "extra_field": "From the story of Pinocchio",
  "tags": ["character", "brave", "pinocchio"]
}
```

### **Example 3: Grammar Focus**
**Prompt:** "Teach @word:红色 with @skill:past-tense"

**Gemini generates:**
```json
{
  "card_type": "interactive_cloze",
  "note_type": "Interactive Cloze",
  "text_field": "The train [[c1::was]] [[c2::red]]. 火车[[c3::是]][[c4::红色的]]。",
  "extra_field": "Past tense practice with colors",
  "tags": ["colors", "past-tense", "bilingual"]
}
```

## Frontend Preview

The card preview will show:
```
┌─────────────────────────────────────┐
│ Interactive Cloze Card              │
│                                     │
│ The [[c1::sky]] is [[c2::blue]]    │
│                                     │
│ Extra: Colors in nature             │
│                                     │
│ ℹ Click blanks to reveal           │
│  (uses [[c1::answer]] syntax)       │
└─────────────────────────────────────┘
```

## Backend Changes

### **Card Model** (Updated)
```python
class Card(BaseModel):
    id: str
    front: str
    back: str
    card_type: str  # Now includes "interactive_cloze"
    cloze_text: Optional[str] = None
    text_field: Optional[str] = None      # NEW
    extra_field: Optional[str] = None     # NEW
    note_type: Optional[str] = None       # NEW
    tags: List[str] = []
    created_at: datetime
    status: str = "pending"
```

### **AnkiConnect Integration**
```python
# In sync_cards()
if note_type:
    fields = {}
    if text_field:
        fields["Text"] = text_field
    if extra_field:
        fields["Extra"] = extra_field
    
    note_id = anki.add_custom_note(deck_name, note_type, fields, tags)
```

## Benefits

### **Why Interactive Cloze?**

1. **Multiple blanks** - One card can have many cloze deletions
2. **Progressive reveal** - Click to reveal one at a time
3. **Flexible** - Works with any custom bracket syntax
4. **Engaging** - More interactive than standard cloze
5. **Custom styling** - Full control over appearance

### **When to Use Each Type:**

| Card Type | Best For | Example |
|-----------|----------|---------|
| **Interactive Cloze** | Sentences with multiple blanks | "The [[c1::sky]] is [[c2::blue]]" |
| **Basic** | Simple Q&A | "What color is the sky?" → "Blue" |
| **Basic Reverse** | Vocabulary pairs | "Red" ↔ "红色" |

## How Gemini Chooses Card Type

The AI agent now prefers Interactive Cloze for:
- Sentences with multiple words to learn
- Grammar practice
- Contextual vocabulary
- Story-based learning

It will use Basic cards for:
- Simple definitions
- Single-word vocabulary
- Yes/no questions

## Testing

### **1. Create the Note Type in Anki**
- Use templates from your message
- Name it "Interactive Cloze"

### **2. Generate a Card**
```
Chat: "Create a sentence card about colors"
```

### **3. Check Preview**
Should show: `text_field` with `[[c1::...]]` syntax

### **4. Sync to Anki**
- Approve card
- Select deck
- Click "Sync to Anki"

### **5. Verify in Anki**
- Open Anki
- Find the card
- Front: Blanks are clickable
- Back: All answers revealed

The system now fully supports your custom Interactive Cloze note type! 🎉

