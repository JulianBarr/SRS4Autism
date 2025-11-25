# Ontology Redesign: KnowledgePoint as Super-Property

## Overview

The ontology has been redesigned based on the insight that **KnowledgePoint should model relationships (facts) rather than things (nodes)**.

**Version:** 2.0  
**Date:** 2024-11-13

## Key Changes

### Before (Version 1.0)

- `KnowledgePoint` was a **class** (rdfs:Class)
- `Character`, `Word`, `GrammarPoint` were subclasses of `KnowledgePoint`
- Relationships like `means`, `composedOf` were standalone properties
- No inverse properties for two-way knowledge

### After (Version 2.0)

- `KnowledgePoint` is now a **super-property** (owl:ObjectProperty)
- `Character`, `Word`, `GrammarPoint` are independent classes (no longer inherit from KnowledgePoint)
- All knowledge relationships are **sub-properties** of `KnowledgePoint`
- **Inverse properties** added for two-way knowledge representation

## New Structure

### Classes (The "Nouns")

All classes are now independent, no longer inheriting from KnowledgePoint:

- `Character` - Chinese characters (汉字)
- `Word` - Multi-character words (词)
- `GrammarPoint` - Grammar rules
- `Sentence` - Example sentences
- `Concept` - Language-agnostic concepts

### Properties (The "Verbs")

#### KnowledgePoint - The Super-Property

```
srs-kg:KnowledgePoint a owl:ObjectProperty
```

All knowledge relationships are sub-properties of `KnowledgePoint`:

#### Semantic Relationships (Word ↔ Concept)

- `means` - A word means/expresses a concept
- `isExpressedBy` - A concept is expressed by a word (inverse of `means`)

#### Composition Relationships (Word ↔ Character)

- `composedOf` - A word is composed of characters
- `partOf` - A character is part of a word (inverse of `composedOf`)

#### Prerequisite Relationships

- `requiresPrerequisite` - An entity requires a prerequisite
- `isPrerequisiteFor` - An entity is a prerequisite for another (inverse)

#### Grammar Relationships (Sentence ↔ GrammarPoint)

- `illustratesGrammar` - A sentence illustrates a grammar point
- `isIllustratedBy` - A grammar point is illustrated by a sentence (inverse)

#### Sentence-Word Relationships

- `containsWord` - A sentence contains a word
- `appearsIn` - A word appears in a sentence (inverse)

#### Concept Relationships (Concept ↔ Concept)

- `isSynonymOf` - A concept is a synonym of another
- `isAntonymOf` - A concept is an antonym of another

## Benefits

### 1. Correct Semantic Modeling

Knowledge points are now correctly modeled as **relationships** (facts) rather than as **things** (nodes). The fact that "朋友 means friend" is a knowledge point, not the word or concept itself.

### 2. Two-Way Knowledge

Using `owl:inverseOf`, we automatically get bidirectional knowledge:

```turtle
# When you assert:
srs-kg:word-朋友 srs-kg:means srs-kg:concept-friend .

# The ontology automatically infers:
srs-kg:concept-friend srs-kg:isExpressedBy srs-kg:word-朋友 .
```

### 3. Query Flexibility

You can now query knowledge points directly:

```sparql
# Find all knowledge points (relationships)
SELECT ?subject ?kp ?object WHERE {
    ?subject ?kp ?object .
    ?kp rdfs:subPropertyOf srs-kg:KnowledgePoint .
}

# Find all words that express a concept (using inverse)
SELECT ?word WHERE {
    srs-kg:concept-friend srs-kg:isExpressedBy ?word .
}
```

### 4. Extensibility

New knowledge relationships can be easily added as sub-properties of `KnowledgePoint`:

```turtle
srs-kg:hasPronunciation a owl:ObjectProperty ;
    rdfs:subPropertyOf srs-kg:KnowledgePoint ;
    rdfs:domain srs-kg:Word ;
    rdfs:range srs-kg:Pronunciation .
```

## Migration Notes

### Backward Compatibility

The populate scripts (`populate_from_cwn.py`, `populate_chinese_kg.py`, etc.) **do not need changes** because:

1. They create instances using `RDF.type` (e.g., `SRS_KG.Character`) - these classes still exist
2. They use properties like `composedOf`, `means` - these still work the same way
3. The only difference is semantic: these properties are now sub-properties of `KnowledgePoint`

### Legacy Property Names

For backward compatibility, some legacy property names are mapped:

- `demonstratesGrammar` → equivalent to `illustratesGrammar`
- `hasExample` → equivalent to `isIllustratedBy`

### Existing Data

Existing knowledge graph data will continue to work because:
- The property names remain the same
- The class names remain the same
- Only the ontology structure (schema) has changed

When regenerating the knowledge graph, the new ontology will be used automatically.

## Example Usage

### Creating Knowledge Points

```turtle
# Word means Concept (a knowledge point)
srs-kg:word-朋友 srs-kg:means srs-kg:concept-friend .

# Word composed of Characters (knowledge points)
srs-kg:word-朋友 srs-kg:composedOf srs-kg:char-朋, srs-kg:char-友 .

# Prerequisites (knowledge points)
srs-kg:word-朋友 srs-kg:requiresPrerequisite srs-kg:char-朋, srs-kg:char-友 .
```

### Querying Knowledge Points

```sparql
# Find all knowledge points involving a word
SELECT ?kp ?object WHERE {
    srs-kg:word-朋友 ?kp ?object .
    ?kp rdfs:subPropertyOf srs-kg:KnowledgePoint .
}

# Find all words that express concepts (using inverse)
SELECT ?word ?concept WHERE {
    ?concept srs-kg:isExpressedBy ?word .
}
```

## References

- Original design discussion: `Complete ontology.md`
- Schema file: `knowledge_graph/ontology/srs_schema.ttl`


