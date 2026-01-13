"""
Knowledge Graph Schema Module
Provides constants, utilities, and helpers for working with the KG schema v2.0
"""

from .constants import (
    # Namespaces
    SCHEMA_NS,
    SCHEMA_PREFIX,
    INSTANCE_NS,
    INSTANCE_PREFIX,
    WIKIDATA_NS,
    WIKIDATA_PREFIX,

    # Classes
    Classes,

    # Properties
    ObjectProperties,
    DataProperties,

    # URI Patterns
    URIPatterns,
    LanguageTags,
    LegacyPatterns,

    # Helper Functions
    make_concept_uri,
    make_word_uri,
    make_character_uri,
    make_grammar_point_uri,
    is_legacy_uri,
    normalize_uri,

    # SPARQL Utilities
    STANDARD_PREFIXES,
    get_sparql_query_with_prefixes,

    # Validation
    validate_concept_uri,
    validate_word_uri,
    validate_character_uri,
)

__all__ = [
    # Namespaces
    "SCHEMA_NS",
    "SCHEMA_PREFIX",
    "INSTANCE_NS",
    "INSTANCE_PREFIX",
    "WIKIDATA_NS",
    "WIKIDATA_PREFIX",

    # Classes
    "Classes",

    # Properties
    "ObjectProperties",
    "DataProperties",

    # URI Patterns
    "URIPatterns",
    "LanguageTags",
    "LegacyPatterns",

    # Helper Functions
    "make_concept_uri",
    "make_word_uri",
    "make_character_uri",
    "make_grammar_point_uri",
    "is_legacy_uri",
    "normalize_uri",

    # SPARQL Utilities
    "STANDARD_PREFIXES",
    "get_sparql_query_with_prefixes",

    # Validation
    "validate_concept_uri",
    "validate_word_uri",
    "validate_character_uri",
]
