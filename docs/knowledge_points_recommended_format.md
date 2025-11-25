# Recommended Format for Knowledge Points in Templates

## Problem

When specifying knowledge points in templates, you want them to be **automatically populated** with actual values based on the word being taught, rather than being interpreted literally.

## Solution: Template Variables

Use **template variables** in the format `{{variable}}` to automatically populate knowledge points.

## Recommended Format

```
@{{word}}--means--{{concept}}
```

### Why This Format?

1. **Readable**: Easy to understand what will be populated
2. **Precise**: Automatically expands to correct values
3. **Reusable**: Works for any word, not just specific examples
4. **Flexible**: Supports multiple variables

## Available Variables

| Variable | What It Does | Example Output |
|----------|-------------|----------------|
| `{{word}}` | The actual word from `@word:` mention | `读者` |
| `{{concept}}` | The meaning/concept (looked up automatically) | `reader` |
| `{{pronunciation}}` | The pinyin pronunciation | `dú zhě` |
| `{{hsk_level}}` | The HSK level | `3` |

## Complete Example

### Template Definition

```json
{
  "name": "chinese_word",
  "template_text": "Create interactive cloze cards for a Chinese word.\n\nKnowledge Points:\n@{{word}}--means--{{concept}}\n@{{word}}--has-pronunciation--{{pronunciation}}\n@{{word}}--has-hsk-level--{{hsk_level}}\n\n..."
}
```

### User Message

```
@template:chinese_word @word:读者 @quantity:5
```

### What Happens

1. System extracts word: `读者` (from `@word:读者`)
2. System looks up knowledge: concept=`reader`, pronunciation=`dú zhě`, hsk_level=`3`
3. System expands template variables:
   - `@{{word}}--means--{{concept}}` → `@读者--means--reader`
   - `@{{word}}--has-pronunciation--{{pronunciation}}` → `@读者--has-pronunciation--dú zhě`
   - `@{{word}}--has-hsk-level--{{hsk_level}}` → `@读者--has-hsk-level--3`
4. Knowledge points are added to cards

### Result in Card

- **Storage**: `["kp:读者--means--reader", "kp:读者--has-pronunciation--dú-zhě", "kp:读者--has-hsk-level--3"]`
- **Display in _Remarks**:
  ```
  Knowledge Points:
  - 读者 means reader (concept)
  - 读者 pronounced dú zhě
  - 读者 HSK level 3
  ```

## Alternative Formats (Also Supported)

### Explicit Format
```
@kp:{{word}}--means--{{concept}}
```

### Literal Values (No Variables)
```
@读者--means--reader
```
(Use this only for word-specific templates)

## Best Practices

1. ✅ **Use template variables** for reusable templates: `@{{word}}--means--{{concept}}`
2. ✅ **Use literal values** only for word-specific templates: `@读者--means--reader`
3. ✅ **Combine multiple knowledge points** to track different aspects
4. ✅ **Test with real words** to ensure variables expand correctly

## See Also

- `knowledge_points_template_variables.md` - Detailed documentation on template variables
- `knowledge_points_format.md` - Knowledge point format documentation
- `knowledge_points_examples.md` - Quick examples and use cases

