# Knowledge Points in Templates - Guide

## Overview

Knowledge points are atomic units of knowledge that can be tracked and linked to learning cards. They help connect cards to structured knowledge in the knowledge graph and track learning progress at a granular level.

## Format

Knowledge points are specified in templates using `@kp:` mentions with the following format:

```
@kp:subject--predicate--object
```

### Components

- **subject**: The entity being learned (e.g., a Chinese word like `读者`)
- **predicate**: The type of knowledge (e.g., `has-meaning`, `has-pronunciation`, `has-hsk-level`)
- **object**: The specific value (e.g., `reader`, `dú zhě`, `3`)

## Examples

### Single Knowledge Point

```
@kp:读者--has-meaning--reader
```

This specifies that the card is teaching the meaning of the word "读者" (reader).

### Multiple Knowledge Points

You can specify multiple knowledge points in a single template:

```
@kp:读者--has-meaning--reader @kp:读者--has-pronunciation--dú zhě @kp:读者--has-hsk-level--3
```

This tracks:
1. The meaning of "读者" (reader)
2. The pronunciation (dú zhě)
3. The HSK level (3)

### Common Predicates

- `has-meaning`: The meaning/translation of a word
- `has-pronunciation`: The pinyin pronunciation
- `has-hsk-level`: The HSK level (1-7)
- `has-grammar-rule`: A grammar rule (e.g., `@kp:把--has-grammar-rule--causative-construction`)
- `has-part-of-speech`: Part of speech (e.g., `@kp:读者--has-part-of-speech--noun`)

## Usage in Templates

### Option 1: Specify in Template Text

Add knowledge point mentions directly in the template text:

```json
{
  "name": "chinese_word",
  "template_text": "Create interactive cloze cards for the word 读者.\n\nKnowledge Points:\n@kp:读者--has-meaning--reader @kp:读者--has-pronunciation--dú zhě @kp:读者--has-hsk-level--3\n\n..."
}
```

### Option 2: Specify in User Message

When using a template, you can also add knowledge points in your message:

```
@template:chinese_word @word:读者 @kp:读者--has-meaning--reader @kp:读者--has-pronunciation--dú zhě
```

### Option 3: Dynamic from Word

If you use `@word:读者` mention, the system can automatically generate knowledge points if the word is found in the knowledge graph. However, **explicit `@kp:` mentions take precedence** and are more reliable.

## How It Works

1. **Parsing**: The system parses `@kp:` mentions from the template text or user message
2. **Storage**: Knowledge points are stored in the card's `knowledge_points` array as `kp:subject--predicate--object`
3. **Display**: In the `_Remarks` field, they appear as `word:subject--has_predicate--object` (for display purposes)
4. **Tracking**: Knowledge points can be queried from the knowledge graph and linked to learning progress

## Example Template

Here's a complete example template for Chinese words with knowledge points:

```json
{
  "name": "chinese_word_with_kp",
  "template_text": "Create interactive cloze cards for a Chinese word.\n\nGenerate 10 cloze deletion cards using @notetype:cuma-interactive-cloze.\n\nKnowledge Points to Track:\nWhen generating cards for a word, include these knowledge points:\n@kp:读者--has-meaning--reader @kp:读者--has-pronunciation--dú zhě @kp:读者--has-hsk-level--3\n\nNote: Replace '读者' with the actual word being taught. The knowledge points will be automatically associated with the generated cards.\n\nFormat Requirements:\n- card_type: 'interactive_cloze'\n- note_type: 'CUMA - Interactive Cloze'\n- text_field: Chinese sentence with [[c1::word]] cloze\n- Use simplified Chinese characters\n\nRequirements:\n- Vivid and easy to visualize\n- Age-appropriate for autistic child\n- 10 cards per word\n\nReturn as JSON array with fields: card_type, note_type, text_field, extra_field (optional), tags"
}
```

### Real-World Example: Using Knowledge Points

**Template Definition:**

When you create a template, you can include knowledge points directly in the template text. For example, if you're creating cards for the word "读者" (reader), you would include:

```
@kp:读者--has-meaning--reader @kp:读者--has-pronunciation--dú zhě @kp:读者--has-hsk-level--3
```

**User Message:**

When using the template, you can reference it like this:

```
@template:chinese_word @word:读者 @quantity:5
```

The system will:
1. Load the template
2. Parse `@kp:` mentions from the template text
3. Associate those knowledge points with the generated cards
4. Store them in the card's `knowledge_points` array
5. Display them in the `_Remarks` field

**Result:**

The generated cards will have:
- `knowledge_points`: `["kp:读者--has-meaning--reader", "kp:读者--has-pronunciation--dú-zhě", "kp:读者--has-hsk-level--3"]`
- `_Remarks` field will contain:
  ```
  Knowledge Points:
  - word:读者--has_meaning--reader
  - word:读者--has_pronunciation--dú-zhě
  - word:读者--has_hsk_level--3
  ```

**Note:** If you also specify knowledge points in your user message (e.g., `@kp:读者--has-meaning--reader`), they will be merged with the template's knowledge points (duplicates are automatically removed).

## Important Notes

1. **Atomic Knowledge**: Each knowledge point should represent a single, atomic piece of knowledge
   - ✅ Good: `@kp:读者--has-meaning--reader`
   - ❌ Bad: `@kp:读者--has-meaning-and-pronunciation--reader-dú zhě`

2. **Consistent Format**: Use hyphens (`--`) to separate components, and hyphens within predicate names (e.g., `has-meaning` not `has_meaning` in the KP ID)

3. **Display Format**: The system automatically converts `kp:读者--has-meaning--reader` to `word:读者--has_meaning--reader` in the `_Remarks` field for readability

4. **Explicit is Better**: Always specify knowledge points explicitly in templates rather than relying on automatic generation

## See Also

- `AGENT_ARCHITECTURE.md` - Overview of the agent system
- `MENTION_SYSTEM.md` - How mentions work in the system
- `docs/agentic_migration.md` - Agentic RAG framework migration guide

