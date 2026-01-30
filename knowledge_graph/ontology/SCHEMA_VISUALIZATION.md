# Knowledge Graph Schema Visualization (v2.0)

**Status:** Reverse Engineered from `world_model_rescued.ttl`
**Date:** 2026-01-29

This diagram represents the *actual* structure of the data currently in the Knowledge Graph.

## The Core Model

```mermaid
classDiagram
    direction LR

    %% --- CLASSES ---
    class Word {
        +string text
        +string rdfs:label
        +string pinyin
        +float frequency
        +int frequencyRank
        +float ageOfAcquisition
        +float concreteness
        +int hskLevel
        +string cefrLevel
        +string partOfSpeech
        +string learningTheme
        +string learningLanguage
    }

    class Concept {
        +string rdfs:label
        +string rdfs:comment
        +string wikidataId
    }

    class Character {
        +string glyph
        +string rdfs:label
    }

    class VisualImage {
        +string imageFileName
        +string imageFilePath
        +string imageMimeType
        +string sourcePackage
    }

    class GrammarPoint {
        +string rdfs:label
        +string structure
        +string explanation
        +string cefrLevel
        +string category
        +string sentenceType
    }

    class Sentence {
        +string text
        +string translationEN
        +string pinyin
    }

    class PinyinNode {
        %% Inferred from 'hasPinyin' linking to URIs
        +string displayText
    }

    %% --- RELATIONSHIPS ---

    %% Core Semantic Backbone
    Word "1" --> "1..*" Concept : means
    Concept "1" --> "1..*" Word : isExpressedBy

    %% Literacy / Composition
    Word "1" --> "1..*" Character : composedOf
    Word "1" --> "1..*" Character : requiresPrerequisite

    %% Visuals
    Concept "1" --> "0..*" VisualImage : hasVisualization
    VisualImage "1" --> "1" Concept : representsConcept

    %% Grammar
    GrammarPoint "1" --> "0..*" Sentence : hasExample
    Sentence "1" --> "1..*" GrammarPoint : demonstratesGrammar
    Sentence "1" --> "1..*" Word : containsWord

    %% Pinyin Structure
    Word "1" --> "1" PinyinNode : hasPinyin

    %% Semantic Network
    Concept --> Concept : isSynonymOf
    Concept --> Concept : requiresPrerequisite
```

## Schema Health Analysis (Technical Debt)

Based on the audit of the current data, the following inconsistencies must be resolved:

### 1. Property Redundancy
| Class | Issue | Recommendation |
|---|---|---|
| **Word** | Has both `text` and `rdfs:label`. | **Standardize on `rdfs:label`** for display text. |
| **Sentence** | Has `demonstratesGrammar` and `illustratesGrammar`. | **Pick `illustratesGrammar`** as standard. |
| **Concept** | Has `requiresPrerequisite` pointing to other Concepts. | Keep distinct from Word prerequisites. |

### 2. The Pinyin Situation
*   **Current State:** `hasPinyin` links to URIs, not literals.
*   **Action:** Explicitly define `srs-kg:PinyinSyllable` in the ontology.

### 3. Sentence Data Scarcity
*   **Issue:** Audit shows very low counts for Sentence properties.
*   **Action:** Verify Sentence deck population scripts.
