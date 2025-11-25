# Knowledge Points in Templates - Quick Examples

## How to Specify Knowledge Points

Knowledge points are specified using the simplified format: `@subject--predicate--object`

This format is both **readable** and **precise**:
- **Readable**: Easy to understand (e.g., `@读者--means--reader`)
- **Precise**: Machine-readable for knowledge graph storage
- **Display**: Automatically formatted for human readability (e.g., "读者 means reader (concept)")

## Example 1: In User Message (Simplified Format)

When using a template, specify knowledge points in your message using the simplified format:

```
@template:chinese_word @word:读者 @quantity:5 @读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3
```

**Result:** The generated cards will have these knowledge points associated with them, and they will be displayed as:
- "读者 means reader (concept)"
- "读者 pronounced dú zhě"
- "读者 HSK level 3"

## Example 2: In Template Text (For Specific Word)

If you want to create a template specifically for a word, include knowledge points directly in the template:

```json
{
  "name": "chinese_word_读者",
  "template_text": "Create interactive cloze cards for 读者.\n\nKnowledge Points:\n@读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3\n\nGenerate 10 cloze deletion cards using @notetype:cuma-interactive-cloze..."
}
```

**Result:** When you use this template, the knowledge points will be automatically extracted and associated with the cards, and displayed in a readable format.

## Example 3: Multiple Knowledge Points

You can specify multiple knowledge points on one line or multiple lines:

```
@读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3
```

Or:

```
@读者--means--reader
@读者--has-pronunciation--dú zhě
@读者--has-hsk-level--3
```

## Example 4: Common Predicates

### Word Meaning (Concept)
```
@读者--means--reader
```
**Display:** "读者 means reader (concept)"

### Pronunciation
```
@读者--has-pronunciation--dú zhě
```
**Display:** "读者 pronounced dú zhě"  
**Note:** Spaces are allowed in pronunciation values (e.g., `dú zhě`)

### HSK Level
```
@读者--has-hsk-level--3
```
**Display:** "读者 HSK level 3"

### Grammar Rule
```
@把--has-grammar-rule--causative-construction
```
**Display:** "把 grammar rule: causative construction"

### Part of Speech
```
@读者--has-part-of-speech--noun
```
**Display:** "读者 part of speech: noun"

## How It Works

1. **Parsing**: The system parses `@kp:` mentions from:
   - Your user message
   - The template text (if a template is used)

2. **Storage**: Knowledge points are stored in the card's `knowledge_points` array with the `kp:` prefix:
   ```json
   {
     "knowledge_points": [
       "kp:读者--means--reader",
       "kp:读者--has-pronunciation--dú-zhě",
       "kp:读者--has-hsk-level--3"
     ]
   }
   ```
   **Note:** 
   - Input format: `@读者--means--reader` (simplified, readable)
   - Storage format: `kp:读者--means--reader` (precise, machine-readable)
   - Spaces in values are normalized to hyphens (e.g., `dú zhě` → `dú-zhě`)

3. **Display**: In the `_Remarks` field, they appear in a readable format:
   ```
   Knowledge Points:
   - 读者 means reader (concept)
   - 读者 pronounced dú zhě
   - 读者 HSK level 3
   ```
   **Note:** The system automatically converts knowledge points to human-readable sentences based on the predicate type.

## Complete Workflow Example

**1. Create a template** (optional - you can also specify KPs directly in your message):

```json
{
  "name": "chinese_word",
  "template_text": "Create interactive cloze cards for a Chinese word.\n\nGenerate 10 cloze deletion cards using @notetype:cuma-interactive-cloze..."
}
```

**2. Use the template with knowledge points:**

```
@template:chinese_word @word:读者 @quantity:5 @读者--means--reader @读者--has-pronunciation--dú zhě @读者--has-hsk-level--3
```

**3. Generated cards will have:**

- `knowledge_points`: `["kp:读者--means--reader", "kp:读者--has-pronunciation--dú-zhě", "kp:读者--has-hsk-level--3"]`
- `_Remarks` field will contain:
  ```
  Knowledge Points:
  - 读者 means reader (concept)
  - 读者 pronounced dú zhě
  - 读者 HSK level 3
  ```
- Knowledge points will be synced to Anki in the `_Remarks` field

## Important Notes

1. **Spaces in Values**: Spaces are allowed in knowledge point values (e.g., `dú zhě`). They will be normalized to hyphens when stored.

2. **Format**: Use `--` (double hyphen) to separate subject, predicate, and object. 
   - Simplified format: `@subject--predicate--object` (e.g., `@读者--means--reader`)
   - Explicit format: `@kp:subject--predicate--object` (also supported for backward compatibility)

3. **Display Format**: The system automatically converts knowledge points to human-readable sentences:
   - `@读者--means--reader` → "读者 means reader (concept)"
   - `@读者--has-pronunciation--dú zhě` → "读者 pronounced dú zhě"
   - `@读者--has-hsk-level--3` → "读者 HSK level 3"

4. **Duplicates**: If you specify the same knowledge point in both the template and your message, duplicates are automatically removed.

5. **Atomic Knowledge**: Each knowledge point should represent a single, atomic piece of knowledge. Don't combine multiple concepts into one KP.

## See Also

- `knowledge_points_template_guide.md` - Complete guide with detailed explanations
- `AGENT_ARCHITECTURE.md` - Overview of the agent system
- `MENTION_SYSTEM.md` - How mentions work in the system

