# Knowledge Points Template Variables

## Overview

Templates can use **template variables** to automatically populate knowledge points based on the word being taught. This makes templates reusable and dynamic.

## Format

Use `{{variable}}` syntax in knowledge point patterns:

```
@{{word}}--means--{{concept}}
```

When generating cards for a word (e.g., `@word:读者`), the template variables are automatically replaced with actual values.

## Available Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{word}}` | The actual word from `@word:` mention | `读者` |
| `{{concept}}` | The meaning/concept of the word (first meaning from knowledge graph) | `reader` |
| `{{pronunciation}}` | The pinyin pronunciation | `dú zhě` |
| `{{hsk_level}}` | The HSK level | `3` |

## Examples

### Basic Usage

**Template:**
```
Knowledge Points:
@{{word}}--means--{{concept}}
```

**When used with `@word:读者`:**
- `{{word}}` → `读者`
- `{{concept}}` → `reader` (looked up from knowledge graph)
- Result: `@读者--means--reader`

### Multiple Knowledge Points

**Template:**
```
Knowledge Points:
@{{word}}--means--{{concept}}
@{{word}}--has-pronunciation--{{pronunciation}}
@{{word}}--has-hsk-level--{{hsk_level}}
```

**When used with `@word:读者`:**
- `@读者--means--reader`
- `@读者--has-pronunciation--dú zhě`
- `@读者--has-hsk-level--3`

### Partial Variables

You can mix template variables with literal values:

**Template:**
```
Knowledge Points:
@{{word}}--means--{{concept}}
@{{word}}--has-pronunciation--{{pronunciation}}
```

**When used with `@word:读者`:**
- `@读者--means--reader`
- `@读者--has-pronunciation--dú zhě`

## How It Works

1. **Template Definition**: Include knowledge point patterns with template variables in your template text
2. **Variable Extraction**: When the template is used, the system extracts the word from `@word:` mentions
3. **Knowledge Lookup**: If needed, the system looks up word knowledge (concept, pronunciation, HSK level) from the knowledge graph
4. **Variable Expansion**: Template variables are replaced with actual values
5. **Knowledge Point Creation**: The expanded knowledge points are added to the card's `knowledge_points` array

## Complete Example

### Template Definition

```json
{
  "name": "chinese_word",
  "template_text": "Create interactive cloze cards for a Chinese word.\n\nKnowledge Points:\n@{{word}}--means--{{concept}}\n@{{word}}--has-pronunciation--{{pronunciation}}\n@{{word}}--has-hsk-level--{{hsk_level}}\n\nGenerate 10 cloze deletion cards using @notetype:cuma-interactive-cloze..."
}
```

### User Message

```
@template:chinese_word @word:读者 @quantity:5
```

### Result

The generated cards will have:
- `knowledge_points`: `["kp:读者--means--reader", "kp:读者--has-pronunciation--dú-zhě", "kp:读者--has-hsk-level--3"]`
- `_Remarks` field will contain:
  ```
  Knowledge Points:
  - 读者 means reader (concept)
  - 读者 pronounced dú zhě
  - 读者 HSK level 3
  ```

## Fallback Behavior

- If `{{word}}` cannot be found (no `@word:` mention), the knowledge point pattern is skipped
- If `{{concept}}` cannot be found, it falls back to the word itself
- If `{{pronunciation}}` cannot be found, it's replaced with an empty string
- If `{{hsk_level}}` cannot be found, it's replaced with an empty string

## Best Practices

1. **Always include `{{word}}`**: This is the most reliable variable since it comes directly from the `@word:` mention
2. **Use `{{concept}}` for meanings**: Automatically looks up the word's meaning from the knowledge graph
3. **Combine variables**: Use multiple knowledge points to track different aspects of a word
4. **Test with real words**: Make sure your template works with actual Chinese words

## See Also

- `knowledge_points_format.md` - Knowledge point format documentation
- `knowledge_points_examples.md` - Quick examples and use cases
- `knowledge_points_template_guide.md` - Complete guide with detailed explanations

