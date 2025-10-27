# @Mention System - Predictive Autocomplete

## Overview

The chat assistant features a powerful predictive autocomplete system for @mentions, similar to modern IDEs and chat applications.

## Current Mention Dictionary

### **Dynamic Mentions** (Auto-populated from profiles)

1. **`@profile:name`** 
   - **Source**: Child profiles
   - **Examples**: `@profile:Zhou_Yiming`, `@profile:Alex`
   - **Auto-complete**: Type `@zhou`, `@yiming`, or `@一` to find "Zhou Yiming (周一鸣)"

2. **`@character:name`**
   - **Source**: Character roster from all profiles
   - **Examples**: `@character:Pinocchio`, `@character:Luca`
   - **Auto-complete**: Type `@pin` to find "Pinocchio", `@elsa` to find "Elsa"

### **Typed Mentions** (User specifies value)

3. **`@word:value`**
   - **Purpose**: Target vocabulary/concept
   - **Examples**: `@word:红色`, `@word:honesty`, `@word:colors`
   - **No autocomplete**: Just type the value directly

4. **`@interest:value`**
   - **Purpose**: Incorporate specific interests
   - **Examples**: `@interest:trains`, `@interest:dinosaurs`
   - **No autocomplete**: Just type the value directly

5. **`@skill:value`**
   - **Purpose**: Grammar point or skill ID
   - **Examples**: `@skill:past-tense`, `@skill:grammar-001`
   - **No autocomplete**: Just type the value directly

## How Autocomplete Works

### **Trigger**
Type `@` in the chat input → Dropdown appears with all available mentions

### **Fuzzy Search**
Type partial name → Filters results instantly

**Examples:**

| You Type | Matches |
|----------|---------|
| `@zhou` | Zhou Yiming (周一鸣) |
| `@yiming` | Zhou Yiming (周一鸣) |
| `@一` | Zhou Yiming (周一鸣) |
| `@pin` | Pinocchio |
| `@elsa` | Elsa |
| `@alex` | Alex |

### **Navigation**
- **Arrow Up/Down** - Navigate through suggestions
- **Enter** - Select highlighted suggestion
- **Escape** - Close dropdown
- **Click** - Select with mouse

### **Auto-insert**
When you select a suggestion:
```
Before: "Create cards for @yim"
After:  "Create cards for @profile:Zhou_Yiming "
```

The system automatically:
1. Replaces partial text with full mention
2. Adds proper `@type:value` format
3. Adds a space after
4. Positions cursor for continued typing

## Visual Design

### Dropdown Appearance
```
┌─────────────────────────────────┐
│ [profile]  Zhou Yiming (周一鸣) │  ← Active (highlighted)
│ [character] Pinocchio            │
│ [character] Luca                 │
│ [profile]  Alex                  │
└─────────────────────────────────┘
```

- **Type badges** - Color-coded by mention type
- **Hover highlight** - Shows which item you're selecting
- **Keyboard highlight** - Follows arrow key navigation

## Usage Examples

### Example 1: Find Profile by Partial Name
```
User types: "Create cards for @yi"
Dropdown shows: Zhou Yiming (周一鸣)
User presses Enter
Result: "Create cards for @profile:Zhou_Yiming "
```

### Example 2: Find Character
```
User types: "Use @pin"
Dropdown shows: Pinocchio
User clicks it
Result: "Use @character:Pinocchio "
```

### Example 3: Chinese Characters
```
User types: "教 @一"
Dropdown shows: Zhou Yiming (周一鸣)
User presses Enter
Result: "教 @profile:Zhou_Yiming "
```

### Example 4: Mixed Mentions
```
"Teach @alex about @word:colors using @character:elsa"
                ↑ autocomplete  ↑ type directly  ↑ autocomplete
```

## Technical Implementation

### Search Algorithm
```javascript
// Searches in lowercase for case-insensitive matching
item.searchTerms.some(term => 
  term.includes(query.toLowerCase())
)
```

### Future Enhancements

1. **Pinyin Support**
   ```javascript
   searchTerms: [
     'zhou yiming (周一鸣)',
     'zhou yi ming',
     'yiming',
     '周一鸣',
     '一鸣'
   ]
   ```

2. **Fuzzy Matching**
   - "yming" → Zhou Yiming
   - "pino" → Pinocchio

3. **Recent Mentions**
   - Show recently used mentions first
   - Prioritize frequently mentioned profiles

4. **Context-Aware Suggestions**
   - If discussing colors, suggest color-related skills
   - If discussing characters, prioritize character mentions

5. **Rich Previews**
   ```
   ┌─────────────────────────────────┐
   │ [profile] Zhou Yiming (周一鸣)   │
   │   Age: 5 | Interests: trains    │
   │   Characters: Pinocchio, Luca   │
   └─────────────────────────────────┘
   ```

## Mention Processing Flow

```
User types "@yi"
    ↓
Frontend filters mentionables by "yi"
    ↓
Shows: Zhou Yiming (周一鸣)
    ↓
User selects (Enter or Click)
    ↓
Replaces with: @profile:Zhou_Yiming
    ↓
User continues typing or sends message
    ↓
Backend parses: {type: "profile", value: "Zhou_Yiming"}
    ↓
Agent retrieves full profile context
    ↓
Gemini receives rich prompt with profile data
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `@` | Show all mentions |
| `↑` `↓` | Navigate suggestions |
| `Enter` | Select suggestion |
| `Esc` | Close dropdown |
| `Tab` | Accept first suggestion (future) |

## Benefits

1. **Speed** - Type partial names, get full context
2. **Accuracy** - No typos in profile/character names
3. **Discovery** - See all available mentions
4. **UX** - Modern, familiar autocomplete experience
5. **Multilingual** - Works with Chinese, English, any language

This creates a powerful, IDE-like experience for caregivers! 🚀

