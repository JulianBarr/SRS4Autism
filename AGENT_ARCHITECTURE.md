# SRS4Autism Agent Architecture

## Overview

The refactored content generator transforms from a **rigid card type system** into a **flexible AI agent** that accepts natural language with context injection via @mentions.

## The Problem with the Old System

```python
# ❌ OLD: Rigid, predetermined card types
generator.generate_basic_card("colors", profile)
generator.generate_basic_reverse_card("colors", profile)
generator.generate_cloze_card("colors", profile)
```

**Issues:**
- Caregiver must adapt to the AI
- Limited to predefined card types
- No control over context injection
- Can't combine multiple requirements

## The New Agent System

```python
# ✅ NEW: Flexible, natural language with @mentions
generator.generate_from_prompt(
    user_prompt="Create a card for 红色 (red) about trains using the past tense",
    context_tags=[
        {"type": "word", "value": "红色"},
        {"type": "interest", "value": "trains"},
        {"type": "skill", "value": "past-tense"}
    ],
    child_profile=alex_profile
)
```

## How @Mentions Work

### Supported @mention Types

| Mention | Example | Purpose |
|---------|---------|---------|
| `@word:value` | `@word:红色` | Target word/concept to teach |
| `@interest:value` | `@interest:trains` | Child's interest to incorporate |
| `@skill:value` | `@skill:grammar-001` | Grammar point or skill to practice |
| `@profile:name` | `@profile:Alex` or `@Alex` | Child's profile context |
| `@character:name` | `@character:Pinocchio` | Familiar character from stories/movies |
| `@actor:role` | `@actor:Teacher` | Person/role to include |

### Example User Prompts

**Example 1: Simple vocabulary**
```
"Create flashcards about colors for @Alex"
```
- Parsed as: `@profile:Alex`
- Agent includes Alex's age, interests, language level

**Example 2: With interests**
```
"Teach @word:numbers using @interest:dinosaurs"
```
- Parsed as: `@word:numbers`, `@interest:dinosaurs`
- Agent creates number cards featuring dinosaurs

**Example 3: Grammar focus**
```
"Make a card for @word:红色 about @interest:trains using @skill:past-tense"
```
- Parsed as: `@word:红色`, `@interest:trains`, `@skill:past-tense`
- Agent creates a card: "The train was red" (红色的火车是...)

**Example 4: Using character roster**
```
"Create flashcards about @word:brave using @character:Pinocchio"
```
- Parsed as: `@word:brave`, `@character:Pinocchio`
- Agent creates: "Pinocchio was brave when he told the truth"

**Example 5: Combined context**
```
"Teach @Alex about @word:honesty with @character:Pinocchio and @interest:swimming"
```
- Parsed as: `@profile:Alex`, `@word:honesty`, `@character:Pinocchio`, `@interest:swimming`
- Agent creates contextual cards featuring characters Alex knows

## Architecture Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. USER (Frontend)                                           │
│    Caregiver types: "Create a card for @word:红色 about      │
│    @interest:trains using @skill:past-tense"                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. FRONTEND PARSING                                          │
│    Extracts @mentions and sends JSON to backend:             │
│    {                                                          │
│      "content": "Create a card for 红色...",                 │
│      "mentions": ["trains", "past-tense"],                   │
│      "context_tags": [                                        │
│        {"type": "word", "value": "红色"},                    │
│        {"type": "interest", "value": "trains"},              │
│        {"type": "skill", "value": "past-tense"}              │
│      ]                                                        │
│    }                                                          │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. AGENT (Backend)                                           │
│    ContentGenerator.generate_from_prompt()                   │
│    - Receives structured context                             │
│    - Queries Knowledge Graph for grammar rules               │
│    - Fetches child profile                                   │
│    - Builds dynamic system prompt                            │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. DYNAMIC SYSTEM PROMPT                                     │
│    You are an AI assistant...                                │
│                                                               │
│    **Child Profile:**                                         │
│    Name: Alex                                                 │
│    Age: 5 years old                                           │
│    Interests: trains, dinosaurs                               │
│    Language level: HSK 1                                      │
│                                                               │
│    **Required Context:**                                      │
│    - Target word: 红色 (red)                                 │
│    - Must incorporate interest: trains                        │
│    - Must use grammar: past tense                            │
│                                                               │
│    **User's Goal:**                                           │
│    Create a flashcard about red trains in past tense         │
│                                                               │
│    Generate JSON array of flashcards...                      │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. LLM (Gemini 2.0)                                          │
│    Returns:                                                   │
│    [{                                                         │
│      "front": "What color was the train?",                   │
│      "back": "The train was red (火车是红色的)",             │
│      "card_type": "basic",                                   │
│      "tags": ["colors", "trains", "past-tense"]              │
│    }]                                                         │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. AGENT RETURNS CARDS                                       │
│    Cards saved to database and returned to frontend          │
└──────────────────────────────────────────────────────────────┘
```

## Benefits of This Architecture

| Feature | Rigid Model | Agent Model |
|---------|-------------|-------------|
| **Control** | None - hard-coded context | Full - inject any context |
| **Precision** | Low - AI guesses intent | High - structured, clear prompts |
| **Flexibility** | Zero - fixed card types | Infinite - any combination |
| **UI Complexity** | Simple text box | Power tool (still intuitive) |
| **Scalability** | Must code new features | Just add new @mention types |

## Adding New @mention Types

To add a new context type:

1. **Backend**: Update `parse_context_tags()` in `main.py`
2. **Agent**: Update `_build_dynamic_system_prompt()` in `content_generator.py`
3. **Frontend**: Update mention suggestions in `ChatAssistant.js`

Example - adding `@difficulty:level`:

```python
# In _build_dynamic_system_prompt()
elif tag_type == "difficulty":
    prompt_parts.append(f"- Difficulty level: {tag_value}")
```

## Future Enhancements

### 1. Knowledge Graph Integration
```python
if tag_type == "skill":
    # Query knowledge graph for grammar rule details
    grammar_rule = knowledge_graph.get_rule(tag_value)
    prompt_parts.append(f"- Grammar rule: {grammar_rule.description}")
```

### 2. Media Context
```python
@media:photo.jpg  # Include image analysis in context
@audio:recording.mp3  # Include audio transcription
```

### 3. Situational Learning
```python
@situation:restaurant  # Create cards for restaurant context
@event:birthday  # Create cards about a specific event
```

## Code Structure

```
agent/
└── content_generator.py
    ├── generate_from_prompt()          # ✨ NEW flexible method
    ├── _build_dynamic_system_prompt()   # Builds LLM prompt with context
    ├── _build_profile_context()         # Formats child profile
    └── [legacy methods]                 # Backward compatibility

backend/app/
└── main.py
    ├── parse_context_tags()             # Parses @mentions
    ├── send_message()                   # Chat endpoint using new agent
    └── [other endpoints]
```

## Migration Guide

### Old Code
```python
cards = generator.generate_cards_from_prompt(
    prompt="teach colors",
    child_profile=profile,
    card_types=["basic", "cloze"]
)
```

### New Code
```python
cards = generator.generate_from_prompt(
    user_prompt="teach colors about @interest:trains",
    context_tags=[{"type": "interest", "value": "trains"}],
    child_profile=profile
)
```

The agent decides card types based on context and educational effectiveness!
