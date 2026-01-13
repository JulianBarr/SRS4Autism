#!/usr/bin/env python3
"""
Database URI Migration Utility
Validates and migrates URIs in the database from old format to v2.0 format.

Usage:
    python scripts/migrate_database_uris.py --audit       # Check for legacy URIs
    python scripts/migrate_database_uris.py --migrate     # Migrate legacy URIs
    python scripts/migrate_database_uris.py --validate    # Validate all URIs
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db
from backend.database.models import MasteredWord, MasteredGrammar
from backend.schema import (
    is_legacy_uri,
    validate_word_uri,
    validate_character_uri,
    make_word_uri,
    make_character_uri,
    normalize_uri
)
from sqlalchemy.orm import Session


def audit_database_uris(db: Session) -> Dict[str, any]:
    """
    Audit all URIs in the database and report statistics.

    Returns:
        Dictionary with audit results
    """
    print("=" * 70)
    print("DATABASE URI AUDIT")
    print("=" * 70 + "\n")

    results = {
        "mastered_words": {
            "total": 0,
            "legacy": 0,
            "v2": 0,
            "invalid": 0,
            "legacy_uris": []
        },
        "mastered_grammar": {
            "total": 0,
            "legacy": 0,
            "v2": 0,
            "invalid": 0,
            "legacy_uris": []
        }
    }

    # Audit MasteredWord table
    print("📝 Auditing MasteredWord table...")
    words = db.query(MasteredWord).all()
    results["mastered_words"]["total"] = len(words)

    for word in words:
        word_id = word.word or ""

        if is_legacy_uri(word_id):
            results["mastered_words"]["legacy"] += 1
            results["mastered_words"]["legacy_uris"].append({
                "id": word.id,
                "word": word_id,
                "language": word.language,
                "profile_id": word.profile_id
            })
        elif validate_word_uri(word_id):
            results["mastered_words"]["v2"] += 1
        else:
            results["mastered_words"]["invalid"] += 1
            print(f"   ⚠️  Invalid word URI: {word_id} (record ID: {word.id})")

    print(f"   Total: {results['mastered_words']['total']}")
    print(f"   ✅ v2 format: {results['mastered_words']['v2']}")
    print(f"   ⚠️  Legacy format: {results['mastered_words']['legacy']}")
    print(f"   ❌ Invalid: {results['mastered_words']['invalid']}\n")

    # Audit MasteredGrammar table
    print("📝 Auditing MasteredGrammar table...")
    try:
        grammars = db.query(MasteredGrammar).all()
        results["mastered_grammar"]["total"] = len(grammars)

        for grammar in grammars:
            grammar_id = grammar.grammar_uri or ""

            # Grammar points use srs-inst:gp_ format, which is v2-compliant
            if is_legacy_uri(grammar_id):
                results["mastered_grammar"]["legacy"] += 1
                results["mastered_grammar"]["legacy_uris"].append({
                    "id": grammar.id,
                    "grammar_uri": grammar_id,
                    "profile_id": grammar.profile_id
                })
            elif "srs-inst:gp_" in grammar_id or "srs-inst:gp-" in grammar_id:
                results["mastered_grammar"]["v2"] += 1
            else:
                results["mastered_grammar"]["invalid"] += 1
                print(f"   ⚠️  Unexpected grammar point URI: {grammar_id} (record ID: {grammar.id})")

        print(f"   Total: {results['mastered_grammar']['total']}")
        print(f"   ✅ v2 format: {results['mastered_grammar']['v2']}")
        print(f"   ⚠️  Legacy format: {results['mastered_grammar']['legacy']}")
        print(f"   ❌ Invalid: {results['mastered_grammar']['invalid']}\n")

    except Exception as e:
        print(f"   ℹ️  MasteredGrammar table error: {e}\n")

    return results


def migrate_word_uri(old_uri: str, language: str) -> str:
    """
    Migrate a word URI from old format to v2 format.

    Args:
        old_uri: Old format URI (e.g., "srs-kg:word-猫")
        language: Language code ("zh" or "en")

    Returns:
        New v2 format URI
    """
    # Strip namespace prefix
    base_id = old_uri.replace("srs-kg:", "").replace("srs-inst:", "")

    # Remove old "word-" prefix if present
    if base_id.startswith("word-"):
        base_id = base_id[5:]  # Remove "word-"

    # For Chinese words, we need to convert to pinyin
    # For now, use the text as-is (manual pinyin mapping may be needed)
    if language == "zh":
        # TODO: Add pypinyin conversion if needed
        # For now, use URL-encoded text as fallback
        word_slug = quote(base_id, safe='')
        return f"srs-inst:word_zh_{word_slug}"
    elif language == "en":
        word_slug = base_id.lower().replace(" ", "_")
        return f"srs-inst:word_en_{word_slug}"
    else:
        raise ValueError(f"Unsupported language: {language}")


def migrate_character_uri(old_uri: str) -> str:
    """
    Migrate a character URI from old format to v2 format.

    Args:
        old_uri: Old format URI (e.g., "srs-kg:char-%E7%8C%AB")

    Returns:
        New v2 format URI (e.g., "srs-inst:char_%E7%8C%AB")
    """
    # Strip old prefix
    base_id = old_uri.replace("srs-kg:char-", "").replace("srs-inst:char-", "")

    # Create v2 URI
    return f"srs-inst:char_{base_id}"


def migrate_database(db: Session, dry_run: bool = True) -> Dict[str, int]:
    """
    Migrate legacy URIs in the database to v2 format.

    Args:
        db: Database session
        dry_run: If True, only simulate migration without committing

    Returns:
        Dictionary with migration statistics
    """
    print("=" * 70)
    print(f"DATABASE URI MIGRATION {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print("=" * 70 + "\n")

    stats = {
        "words_migrated": 0,
        "words_failed": 0,
        "grammar_migrated": 0,
        "grammar_failed": 0
    }

    # Migrate words
    print("📝 Migrating MasteredWord table...")
    words = db.query(MasteredWord).filter(MasteredWord.word.isnot(None)).all()

    for word in words:
        if is_legacy_uri(word.word):
            try:
                old_uri = word.word
                new_uri = migrate_word_uri(old_uri, word.language)

                print(f"   {old_uri} → {new_uri}")

                if not dry_run:
                    word.word = new_uri

                stats["words_migrated"] += 1

            except Exception as e:
                print(f"   ❌ Failed to migrate word URI: {word.word} - {e}")
                stats["words_failed"] += 1

    print(f"\n   ✅ Words migrated: {stats['words_migrated']}")
    print(f"   ❌ Words failed: {stats['words_failed']}\n")

    # Note: Grammar points already use v2-compliant URIs (srs-inst:gp_xxx)
    # No migration needed for MasteredGrammar table
    print("📝 Checking MasteredGrammar table...")
    try:
        grammars = db.query(MasteredGrammar).filter(MasteredGrammar.grammar_uri.isnot(None)).all()
        legacy_count = 0

        for grammar in grammars:
            if is_legacy_uri(grammar.grammar_uri):
                legacy_count += 1
                print(f"   ⚠️  Legacy grammar point URI: {grammar.grammar_uri}")

        if legacy_count > 0:
            print(f"\n   ⚠️  Found {legacy_count} legacy grammar URIs")
            print(f"   ℹ️  Grammar point migration not implemented (contact support)\n")
        else:
            print(f"   ✅ All {len(grammars)} grammar point URIs are v2-compliant\n")

    except Exception as e:
        print(f"   ℹ️  MasteredGrammar table error: {e}\n")

    # Commit changes if not dry run
    if not dry_run:
        try:
            db.commit()
            print("✅ Changes committed to database\n")
        except Exception as e:
            db.rollback()
            print(f"❌ Failed to commit changes: {e}\n")
            raise
    else:
        print("ℹ️  Dry run mode - no changes committed\n")

    return stats


def validate_database(db: Session) -> bool:
    """
    Validate all URIs in the database against v2 format.

    Returns:
        True if all URIs are valid
    """
    print("=" * 70)
    print("DATABASE URI VALIDATION")
    print("=" * 70 + "\n")

    all_valid = True

    # Validate words
    print("📝 Validating MasteredWord table...")
    words = db.query(MasteredWord).all()
    invalid_words = []

    for word in words:
        if not validate_word_uri(word.word, word.language):
            invalid_words.append(word)
            all_valid = False

    if invalid_words:
        print(f"   ❌ Found {len(invalid_words)} invalid word URIs:")
        for word in invalid_words[:10]:  # Show first 10
            print(f"      - {word.word} (ID: {word.id}, Language: {word.language})")
        if len(invalid_words) > 10:
            print(f"      ... and {len(invalid_words) - 10} more")
    else:
        print(f"   ✅ All {len(words)} word URIs are valid")

    print()

    # Validate grammar points
    try:
        print("📝 Validating MasteredGrammar table...")
        grammars = db.query(MasteredGrammar).all()
        invalid_grammars = []

        for grammar in grammars:
            grammar_id = grammar.grammar_uri or ""
            # Grammar points should use srs-inst:gp_ or srs-inst:gp- format
            if not ("srs-inst:gp_" in grammar_id or "srs-inst:gp-" in grammar_id):
                invalid_grammars.append(grammar)
                all_valid = False

        if invalid_grammars:
            print(f"   ❌ Found {len(invalid_grammars)} invalid grammar point URIs:")
            for grammar in invalid_grammars[:10]:  # Show first 10
                print(f"      - {grammar.grammar_uri} (ID: {grammar.id})")
            if len(invalid_grammars) > 10:
                print(f"      ... and {len(invalid_grammars) - 10} more")
        else:
            print(f"   ✅ All {len(grammars)} grammar point URIs are valid")

    except Exception as e:
        print(f"   ℹ️  MasteredGrammar table error: {e}")

    print()

    if all_valid:
        print("✅ All URIs in database are valid v2 format\n")
    else:
        print("❌ Some URIs in database are invalid. Run migration to fix.\n")

    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Database URI Migration Utility")
    parser.add_argument("--audit", action="store_true", help="Audit database URIs")
    parser.add_argument("--migrate", action="store_true", help="Migrate legacy URIs")
    parser.add_argument("--validate", action="store_true", help="Validate all URIs")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Simulate migration without committing (default: True)")
    parser.add_argument("--live", action="store_true",
                       help="Actually commit changes (overrides --dry-run)")

    args = parser.parse_args()

    # Get database session
    db = next(get_db())

    try:
        if args.audit:
            results = audit_database_uris(db)

            # Print summary
            print("=" * 70)
            print("AUDIT SUMMARY")
            print("=" * 70)
            print(f"Total words: {results['mastered_words']['total']}")
            print(f"  - v2 format: {results['mastered_words']['v2']}")
            print(f"  - Legacy format: {results['mastered_words']['legacy']}")
            print(f"Total grammar points: {results['mastered_grammar']['total']}")
            print(f"  - v2 format: {results['mastered_grammar']['v2']}")
            print(f"  - Legacy format: {results['mastered_grammar']['legacy']}")
            print()

            if results['mastered_words']['legacy'] > 0 or results['mastered_grammar']['legacy'] > 0:
                print("⚠️  Legacy URIs found. Run with --migrate to update them.")
            else:
                print("✅ No legacy URIs found. Database is up to date!")

        elif args.migrate:
            dry_run = not args.live
            stats = migrate_database(db, dry_run=dry_run)

            print("=" * 70)
            print("MIGRATION SUMMARY")
            print("=" * 70)
            print(f"Words migrated: {stats['words_migrated']}")
            print(f"Words failed: {stats['words_failed']}")
            print(f"Grammar points checked: {stats['grammar_migrated']}")
            print(f"Grammar points with issues: {stats['grammar_failed']}")

            if dry_run:
                print("\n⚠️  This was a DRY RUN. Use --live to commit changes.")

        elif args.validate:
            valid = validate_database(db)
            sys.exit(0 if valid else 1)

        else:
            parser.print_help()

    finally:
        db.close()


if __name__ == "__main__":
    main()
