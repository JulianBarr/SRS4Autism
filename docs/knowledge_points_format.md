# Knowledge Points Format - Readable and Precise

## Overview

Knowledge points use a simplified format that is both **readable** and **precise**:
- **Input**: `@读者--means--reader` (simple, readable)
- **Storage**: `kp:读者--means--reader` (precise, machine-readable)
- **Display**: "读者 means reader (concept)" (human-friendly)

## Format

```
@subject--predicate--object
```

### Components

- **subject**: The entity being learned (e.g., a Chinese word like `读者`)
- **predicate**: The relationship type (e.g., `means`, `has-pronunciation`, `has-hsk-level`)
- **object**: The value (e.g., `reader` (concept), `dú zhě`, `3`)

## Examples

### Word Meaning (Concept)
```
@读者--means--reader
```
- **Input**: `@读者--means--reader`
- **Storage**: `kp:读者--means--reader`
- **Display**: "读者 means reader (concept)"

### Pronunciation
```
@读者--has-pronunciation--dú zhě
```
- **Input**: `@读者--has-pronunciation--dú zhě`
- **Storage**: `kp:读者--has-pronunciation--dú-zhě` (spaces normalized)
- **Display**: "读者 pronounced dú zhě"

### HSK Level
```
@读者--has-hsk-level--3
```
- **Input**: `@读者--has-hsk-level--3`
- **Storage**: `kp:读者--has-hsk-level--3`
- **Display**: "读者 HSK level 3"

### Grammar Rule
```
@把--has-grammar-rule--causative-construction
```
- **Input**: `@把--has-grammar-rule--causative-construction`
- **Storage**: `kp:把--has-grammar-rule--causative-construction`
- **Display**: "把 grammar rule: causative construction"

## Why This Format?

### Readable
- Easy to understand: `@读者--means--reader` is immediately clear
- No need for `@kp:` prefix (though it's still supported for backward compatibility)
- Natural language-like structure

### Precise
- Machine-readable for knowledge graph storage
- Consistent format: `subject--predicate--object`
- Can be parsed and queried programmatically

### Display-Friendly
- Automatically converted to human-readable sentences
- Different predicates get different display formats:
  - `means` → "subject means object (concept)"
  - `has-pronunciation` → "subject pronounced object"
  - `has-hsk-level` → "subject HSK level object"
  - `has-grammar-rule` → "subject grammar rule: object"
  - Generic → "subject → object (predicate)"

## Common Predicates

| Predicate | Example | Display Format |
|-----------|---------|----------------|
| `means` | `@读者--means--reader` | "读者 means reader (concept)" |
| `has-pronunciation` | `@读者--has-pronunciation--dú zhě` | "读者 pronounced dú zhě" |
| `has-hsk-level` | `@读者--has-hsk-level--3` | "读者 HSK level 3" |
| `has-grammar-rule` | `@把--has-grammar-rule--causative-construction` | "把 grammar rule: causative construction" |
| `has-part-of-speech` | `@读者--has-part-of-speech--noun` | "读者 part of speech: noun" |

## Usage

### In User Message
```
@template:chinese_word @word:读者 @quantity:5 @读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3
```

### In Template Text
```json
{
  "name": "chinese_word_读者",
  "template_text": "Create interactive cloze cards for 读者.\n\nKnowledge Points:\n@读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3\n\n..."
}
```

## Backward Compatibility

The explicit format `@kp:subject--predicate--object` is still supported for backward compatibility:
- `@kp:读者--means--reader` (explicit format)
- `@读者--means--reader` (simplified format)

Both formats are parsed and stored identically.

## See Also

- `knowledge_points_examples.md` - Quick examples and use cases
- `knowledge_points_template_guide.md` - Complete guide with detailed explanations

