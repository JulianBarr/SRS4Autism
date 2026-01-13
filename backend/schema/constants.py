"""
Knowledge Graph Schema Constants (v2.0)
Central repository for all KG schema URIs, properties, and patterns.

Based on: knowledge_graph/ontology.ttl
Last Updated: 2026-01-13
"""

# ============================================================================
# NAMESPACE PREFIXES
# ============================================================================

# Schema namespace (for classes and properties)
SCHEMA_NS = "http://srs4autism.com/schema/"
SCHEMA_PREFIX = "srs-kg:"

# Instance namespace (for actual data)
INSTANCE_NS = "http://srs4autism.com/instance/"
INSTANCE_PREFIX = "srs-inst:"

# Wikidata namespace
WIKIDATA_NS = "http://www.wikidata.org/entity/"
WIKIDATA_PREFIX = "wd:"

# Standard namespaces
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"


# ============================================================================
# RDF CLASSES (Types)
# ============================================================================

class Classes:
    """KG entity classes"""
    CONCEPT = f"{SCHEMA_PREFIX}Concept"
    WORD = f"{SCHEMA_PREFIX}Word"
    CHARACTER = f"{SCHEMA_PREFIX}Character"
    GRAMMAR_POINT = f"{SCHEMA_PREFIX}GrammarPoint"
    SENTENCE = f"{SCHEMA_PREFIX}Sentence"
    VISUAL_IMAGE = f"{SCHEMA_PREFIX}VisualImage"


# ============================================================================
# OBJECT PROPERTIES (Relationships)
# ============================================================================

class ObjectProperties:
    """KG relationship properties"""

    # Hub-and-Spoke: Word <-> Concept
    MEANS = f"{SCHEMA_PREFIX}means"
    IS_EXPRESSED_BY = f"{SCHEMA_PREFIX}isExpressedBy"

    # Composition: Word <-> Character
    COMPOSED_OF = f"{SCHEMA_PREFIX}composedOf"
    PART_OF = f"{SCHEMA_PREFIX}partOf"

    # Visual: Concept <-> Image
    HAS_VISUALIZATION = f"{SCHEMA_PREFIX}hasVisualization"
    REPRESENTS_CONCEPT = f"{SCHEMA_PREFIX}representsConcept"

    # Grammar: Sentence <-> GrammarPoint
    ILLUSTRATES_GRAMMAR = f"{SCHEMA_PREFIX}illustratesGrammar"
    IS_ILLUSTRATED_BY = f"{SCHEMA_PREFIX}isIllustratedBy"

    # Sentence-Word
    CONTAINS_WORD = f"{SCHEMA_PREFIX}containsWord"
    APPEARS_IN = f"{SCHEMA_PREFIX}appearsIn"

    # Concept Relationships
    IS_SYNONYM_OF = f"{SCHEMA_PREFIX}isSynonymOf"
    IS_ANTONYM_OF = f"{SCHEMA_PREFIX}isAntonymOf"

    # Learning Prerequisites
    REQUIRES_PREREQUISITE = f"{SCHEMA_PREFIX}requiresPrerequisite"
    IS_PREREQUISITE_FOR = f"{SCHEMA_PREFIX}isPrerequisiteFor"


# ============================================================================
# DATA PROPERTIES
# ============================================================================

class DataProperties:
    """KG data properties for literal values"""

    # Standard Properties
    LABEL = "rdfs:label"  # PREFERRED for human-readable text
    COMMENT = "rdfs:comment"

    # DEPRECATED (use rdfs:label instead)
    TEXT = f"{SCHEMA_PREFIX}text"  # ⚠️ DEPRECATED in v2

    # Wikidata Integration
    WIKIDATA_ID = f"{SCHEMA_PREFIX}wikidataId"
    SAME_AS = "owl:sameAs"

    # Chinese-specific
    PINYIN = f"{SCHEMA_PREFIX}pinyin"
    PINYIN_NUMERIC = f"{SCHEMA_PREFIX}pinyinNumeric"
    TRADITIONAL = f"{SCHEMA_PREFIX}traditional"
    GLYPH = f"{SCHEMA_PREFIX}glyph"

    # Linguistic
    PART_OF_SPEECH = f"{SCHEMA_PREFIX}partOfSpeech"
    DEFINITION = f"{SCHEMA_PREFIX}definition"

    # Difficulty & Proficiency
    HSK_LEVEL = f"{SCHEMA_PREFIX}hskLevel"
    CEFR_LEVEL = f"{SCHEMA_PREFIX}cefrLevel"

    # Psycholinguistic
    CONCRETENESS = f"{SCHEMA_PREFIX}concreteness"
    FREQUENCY = f"{SCHEMA_PREFIX}frequency"
    FREQUENCY_RANK = f"{SCHEMA_PREFIX}frequencyRank"
    AGE_OF_ACQUISITION = f"{SCHEMA_PREFIX}ageOfAcquisition"

    # Grammar
    STRUCTURE = f"{SCHEMA_PREFIX}structure"
    EXPLANATION = f"{SCHEMA_PREFIX}explanation"

    # Image
    IMAGE_FILE_NAME = f"{SCHEMA_PREFIX}imageFileName"
    IMAGE_FILE_PATH = f"{SCHEMA_PREFIX}imageFilePath"
    ORIGINAL_FILE_NAME = f"{SCHEMA_PREFIX}originalFileName"
    SOURCE_PACKAGE = f"{SCHEMA_PREFIX}sourcePackage"
    IMAGE_MIME_TYPE = f"{SCHEMA_PREFIX}imageMimeType"

    # Application-specific
    LEARNING_THEME = f"{SCHEMA_PREFIX}learningTheme"
    TRANSLATION_EN = f"{SCHEMA_PREFIX}translationEN"


# ============================================================================
# URI PATTERNS (v2.0)
# ============================================================================

class URIPatterns:
    """Standard URI patterns for creating entity URIs"""

    # Concepts (Wikidata-based)
    CONCEPT = "{instance_ns}concept_{qid}"
    # Example: srs-inst:concept_Q146

    # Words
    WORD_CHINESE = "{instance_ns}word_zh_{pinyin}"
    # Example: srs-inst:word_zh_mao

    WORD_ENGLISH = "{instance_ns}word_en_{word}"
    # Example: srs-inst:word_en_cat

    # Characters
    CHARACTER = "{instance_ns}char_{encoded}"
    # Example: srs-inst:char_%E7%8C%AB

    # Grammar Points (language-specific pedagogical constructs)
    GRAMMAR_POINT = "{instance_ns}gp_{level}_{id}_{slug}"
    # Example: srs-inst:gp_B1_142_reduplication_of_adjectives

    # Sentences
    SENTENCE = "{instance_ns}sentence_{id}"
    # Example: srs-inst:sentence_2533

    # Images
    IMAGE = "{instance_ns}image_{slug}_{id}"
    # Example: srs-inst:image_friend_001


# ============================================================================
# LANGUAGE TAGS
# ============================================================================

class LanguageTags:
    """Standard language tags for rdfs:label"""
    CHINESE = "zh"
    ENGLISH = "en"
    PINYIN = "en-Latn"  # Romanization of Chinese


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

class LegacyPatterns:
    """
    Old URI patterns (deprecated but may exist in legacy data)
    Use for backward compatibility during migration
    """

    # Old word patterns
    OLD_WORD_SCHEMA = "srs-kg:word-{text}"  # ⚠️ DEPRECATED
    OLD_WORD_INSTANCE = "srs-inst:word-{text}"  # ⚠️ DEPRECATED

    # Old character patterns
    OLD_CHARACTER = "srs-kg:char-{encoded}"  # ⚠️ DEPRECATED (wrong namespace)

    # Old property
    OLD_TEXT_PROPERTY = "srs-kg:text"  # ⚠️ DEPRECATED (use rdfs:label)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def make_concept_uri(qid: str) -> str:
    """
    Create a concept URI from Wikidata Q-ID.

    Args:
        qid: Wikidata Q-ID (e.g., "Q146")

    Returns:
        Full concept URI (e.g., "srs-inst:concept_Q146")
    """
    return URIPatterns.CONCEPT.format(instance_ns=INSTANCE_PREFIX, qid=qid)


def make_word_uri(text: str, language: str) -> str:
    """
    Create a word URI.

    Args:
        text: Word text (Chinese) or slug (English)
        language: "zh" for Chinese, "en" for English

    Returns:
        Full word URI

    Examples:
        >>> make_word_uri("mao", "zh")
        'srs-inst:word_zh_mao'
        >>> make_word_uri("cat", "en")
        'srs-inst:word_en_cat'
    """
    if language == "zh":
        return URIPatterns.WORD_CHINESE.format(instance_ns=INSTANCE_PREFIX, pinyin=text)
    elif language == "en":
        return URIPatterns.WORD_ENGLISH.format(instance_ns=INSTANCE_PREFIX, word=text)
    else:
        raise ValueError(f"Unsupported language: {language}")


def make_character_uri(encoded_char: str) -> str:
    """
    Create a character URI from URL-encoded character.

    Args:
        encoded_char: URL-encoded character (e.g., "%E7%8C%AB" for "猫")

    Returns:
        Full character URI (e.g., "srs-inst:char_%E7%8C%AB")
    """
    return URIPatterns.CHARACTER.format(instance_ns=INSTANCE_PREFIX, encoded=encoded_char)


def make_grammar_point_uri(level: str, gp_id: int, slug: str) -> str:
    """
    Create a grammar point URI.

    Args:
        level: CEFR level (e.g., "B1", "A1")
        gp_id: Grammar point ID number
        slug: URL-safe slug (e.g., "reduplication_of_adjectives")

    Returns:
        Full grammar point URI

    Example:
        >>> make_grammar_point_uri("B1", 142, "reduplication_of_adjectives")
        'srs-inst:gp_B1_142_reduplication_of_adjectives'
    """
    return URIPatterns.GRAMMAR_POINT.format(
        instance_ns=INSTANCE_PREFIX,
        level=level,
        id=gp_id,
        slug=slug
    )


def is_legacy_uri(uri: str) -> bool:
    """
    Check if a URI uses legacy (deprecated) patterns.

    Args:
        uri: URI to check

    Returns:
        True if URI uses old patterns
    """
    return (
        "srs-kg:word-" in uri or
        "srs-kg:char-" in uri or
        "srs-inst:word-" in uri  # Old format without language prefix
    )


def normalize_uri(uri: str) -> str:
    """
    Normalize a URI to use consistent namespace prefix format.

    Args:
        uri: URI to normalize (may be full URL or prefixed)

    Returns:
        Normalized URI with namespace prefix

    Examples:
        >>> normalize_uri("http://srs4autism.com/schema/Word")
        'srs-kg:Word'
        >>> normalize_uri("http://srs4autism.com/instance/concept_Q146")
        'srs-inst:concept_Q146'
    """
    if uri.startswith(SCHEMA_NS):
        return uri.replace(SCHEMA_NS, SCHEMA_PREFIX)
    elif uri.startswith(INSTANCE_NS):
        return uri.replace(INSTANCE_NS, INSTANCE_PREFIX)
    elif uri.startswith(WIKIDATA_NS):
        return uri.replace(WIKIDATA_NS, WIKIDATA_PREFIX)
    else:
        return uri  # Already prefixed or unknown format


# ============================================================================
# SPARQL PREFIXES
# ============================================================================

STANDARD_PREFIXES = f"""
PREFIX srs-kg: <{SCHEMA_NS}>
PREFIX srs-inst: <{INSTANCE_NS}>
PREFIX wd: <{WIKIDATA_NS}>
PREFIX rdf: <{RDF_NS}>
PREFIX rdfs: <{RDFS_NS}>
PREFIX owl: <{OWL_NS}>
PREFIX xsd: <{XSD_NS}>
""".strip()


def get_sparql_query_with_prefixes(query: str) -> str:
    """
    Add standard namespace prefixes to a SPARQL query.

    Args:
        query: SPARQL query (may or may not have prefixes)

    Returns:
        Query with standard prefixes prepended
    """
    # Check if query already has PREFIX declarations
    if "PREFIX" in query:
        return query  # Don't duplicate

    return f"{STANDARD_PREFIXES}\n\n{query}"


# ============================================================================
# VALIDATION
# ============================================================================

def validate_concept_uri(uri: str) -> bool:
    """Check if URI follows v2 concept pattern"""
    return INSTANCE_PREFIX in uri and "concept_Q" in uri


def validate_word_uri(uri: str, language: str = None) -> bool:
    """Check if URI follows v2 word pattern"""
    if language == "zh":
        return INSTANCE_PREFIX in uri and "word_zh_" in uri
    elif language == "en":
        return INSTANCE_PREFIX in uri and "word_en_" in uri
    else:
        # Check for any valid word pattern
        return INSTANCE_PREFIX in uri and ("word_zh_" in uri or "word_en_" in uri)


def validate_character_uri(uri: str) -> bool:
    """Check if URI follows v2 character pattern"""
    return INSTANCE_PREFIX in uri and "char_" in uri
