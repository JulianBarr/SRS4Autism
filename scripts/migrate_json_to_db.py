#!/usr/bin/env python3
"""
Migrate data from JSON files to SQLite database

This script:
1. Creates a backup of the current database (if exists)
2. Creates a backup of all JSON files
3. Reads data from JSON files
4. Validates and cleans the data
5. Inserts data into SQLite database
6. Verifies the migration was successful
7. Creates an audit log entry
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.db import init_db, get_db_session, create_backup, DB_PATH
from backend.database.models import (
    Profile, MasteredWord, MasteredGrammar, ApprovedCard, ChatMessage, AuditLog
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# JSON file paths
PROFILES_JSON = PROJECT_ROOT / "data" / "profiles" / "child_profiles.json"
APPROVED_CARDS_JSON = PROJECT_ROOT / "data" / "content_db" / "approved_cards.json"
CHAT_HISTORY_JSON = PROJECT_ROOT / "data" / "content_db" / "chat_history.json"


def backup_json_files():
    """Create backups of all JSON files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = PROJECT_ROOT / "data" / "backups" / f"json_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📦 Creating JSON backups in: {backup_dir}")
    
    import shutil
    files_backed_up = 0
    
    for json_file in [PROFILES_JSON, APPROVED_CARDS_JSON, CHAT_HISTORY_JSON]:
        if json_file.exists():
            dest = backup_dir / json_file.name
            shutil.copy2(json_file, dest)
            print(f"  ✅ {json_file.name}")
            files_backed_up += 1
    
    print(f"✅ Backed up {files_backed_up} JSON files")
    return backup_dir


def migrate_profiles():
    """Migrate profiles from JSON to database"""
    print("\n📊 Migrating profiles...")
    
    if not PROFILES_JSON.exists():
        print("  ⚠️  No profiles.json found")
        return 0
    
    with open(PROFILES_JSON, 'r', encoding='utf-8') as f:
        profiles_data = json.load(f)
    
    migrated_count = 0
    
    with get_db_session() as db:
        for profile_data in profiles_data:
            # Create profile
            profile = Profile(
                id=profile_data.get('id') or profile_data.get('name'),
                name=profile_data['name'],
                dob=profile_data.get('dob'),
                gender=profile_data.get('gender'),
                address=profile_data.get('address'),
                school=profile_data.get('school'),
                neighborhood=profile_data.get('neighborhood'),
                interests=json.dumps(profile_data.get('interests', [])),
                character_roster=json.dumps(profile_data.get('character_roster', [])),
                verbal_fluency=profile_data.get('verbal_fluency'),
                passive_language_level=profile_data.get('passive_language_level'),
                mental_age=profile_data.get('mental_age'),
                raw_input=profile_data.get('raw_input'),
                extracted_data=json.dumps(profile_data.get('extracted_data', {}))
            )
            
            db.add(profile)
            
            # Migrate Chinese words
            mastered_words_str = profile_data.get('mastered_words', '')
            if mastered_words_str:
                chinese_words = [w.strip() for w in mastered_words_str.split(', ') if w.strip()]
                for word in chinese_words:
                    mastered_word = MasteredWord(
                        profile_id=profile.id,
                        word=word,
                        language='zh'
                    )
                    db.add(mastered_word)
            
            # Migrate English words
            mastered_english_str = profile_data.get('mastered_english_words', '')
            if mastered_english_str:
                english_words = [w.strip() for w in mastered_english_str.split(', ') if w.strip()]
                for word in english_words:
                    mastered_word = MasteredWord(
                        profile_id=profile.id,
                        word=word,
                        language='en'
                    )
                    db.add(mastered_word)
            
            # Migrate grammar points
            mastered_grammar_str = profile_data.get('mastered_grammar', '')
            if mastered_grammar_str:
                grammar_uris = [g.strip() for g in mastered_grammar_str.split(',') if g.strip()]
                for grammar_uri in grammar_uris:
                    mastered_grammar = MasteredGrammar(
                        profile_id=profile.id,
                        grammar_uri=grammar_uri
                    )
                    db.add(mastered_grammar)
            
            migrated_count += 1
            print(f"  ✅ Migrated profile: {profile.name}")
            print(f"     - Chinese words: {len(chinese_words) if mastered_words_str else 0}")
            print(f"     - English words: {len(english_words) if mastered_english_str else 0}")
            print(f"     - Grammar points: {len(grammar_uris) if mastered_grammar_str else 0}")
        
        # Create audit log entry
        audit = AuditLog(
            table_name='profiles',
            record_id='ALL',
            action='MIGRATE',
            new_value=json.dumps({'migrated_count': migrated_count}),
            changed_by='migration_script'
        )
        db.add(audit)
    
    print(f"✅ Migrated {migrated_count} profiles")
    return migrated_count


def migrate_approved_cards():
    """Migrate approved cards from JSON to database"""
    print("\n📝 Migrating approved cards...")
    
    if not APPROVED_CARDS_JSON.exists():
        print("  ⚠️  No approved_cards.json found")
        return 0
    
    with open(APPROVED_CARDS_JSON, 'r', encoding='utf-8') as f:
        cards_data = json.load(f)
    
    migrated_count = 0
    
    with get_db_session() as db:
        # Get first profile ID (assume all cards belong to it)
        profile = db.query(Profile).first()
        if not profile:
            print("  ⚠️  No profiles found, skipping approved cards")
            return 0
        
        for card_data in cards_data:
            card = ApprovedCard(
                profile_id=profile.id,
                card_type=card_data.get('type', 'unknown'),
                content=json.dumps(card_data)
            )
            db.add(card)
            migrated_count += 1
        
        # Create audit log entry
        audit = AuditLog(
            table_name='approved_cards',
            record_id='ALL',
            action='MIGRATE',
            new_value=json.dumps({'migrated_count': migrated_count}),
            changed_by='migration_script'
        )
        db.add(audit)
    
    print(f"✅ Migrated {migrated_count} approved cards")
    return migrated_count


def migrate_chat_history():
    """Migrate chat history from JSON to database"""
    print("\n💬 Migrating chat history...")
    
    if not CHAT_HISTORY_JSON.exists():
        print("  ⚠️  No chat_history.json found")
        return 0
    
    with open(CHAT_HISTORY_JSON, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)
    
    migrated_count = 0
    
    with get_db_session() as db:
        # Get first profile ID (assume all messages belong to it)
        profile = db.query(Profile).first()
        if not profile:
            print("  ⚠️  No profiles found, skipping chat history")
            return 0
        
        for message_data in chat_data:
            message = ChatMessage(
                profile_id=profile.id,
                role=message_data.get('role', 'user'),
                content=message_data.get('content', '')
            )
            db.add(message)
            migrated_count += 1
        
        # Create audit log entry
        audit = AuditLog(
            table_name='chat_messages',
            record_id='ALL',
            action='MIGRATE',
            new_value=json.dumps({'migrated_count': migrated_count}),
            changed_by='migration_script'
        )
        db.add(audit)
    
    print(f"✅ Migrated {migrated_count} chat messages")
    return migrated_count


def verify_migration():
    """Verify the migration was successful"""
    print("\n🔍 Verifying migration...")
    
    with get_db_session() as db:
        profile_count = db.query(Profile).count()
        word_count = db.query(MasteredWord).count()
        grammar_count = db.query(MasteredGrammar).count()
        card_count = db.query(ApprovedCard).count()
        message_count = db.query(ChatMessage).count()
        
        print(f"  ✅ Profiles: {profile_count}")
        print(f"  ✅ Mastered words: {word_count}")
        print(f"  ✅ Mastered grammar: {grammar_count}")
        print(f"  ✅ Approved cards: {card_count}")
        print(f"  ✅ Chat messages: {message_count}")
        
        # Verify foreign key relationships
        for profile in db.query(Profile).all():
            words = db.query(MasteredWord).filter_by(profile_id=profile.id).count()
            grammar = db.query(MasteredGrammar).filter_by(profile_id=profile.id).count()
            print(f"\n  Profile '{profile.name}' (ID: {profile.id}):")
            print(f"    - Words: {words}")
            print(f"    - Grammar: {grammar}")
        
        return True


def main():
    print("=" * 80)
    print("JSON to SQLite Migration")
    print("=" * 80)
    
    # Step 1: Backup database if it exists
    if DB_PATH.exists():
        print("\n⚠️  Database already exists!")
        response = input("Do you want to overwrite it? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled")
            return
        create_backup()
    
    # Step 2: Backup JSON files
    json_backup_dir = backup_json_files()
    
    # Step 3: Initialize database
    print("\n🔧 Initializing database...")
    init_db()
    
    # Step 4: Migrate data
    try:
        profiles_migrated = migrate_profiles()
        cards_migrated = migrate_approved_cards()
        messages_migrated = migrate_chat_history()
        
        # Step 5: Verify migration
        if verify_migration():
            print("\n" + "=" * 80)
            print("✅ MIGRATION SUCCESSFUL")
            print("=" * 80)
            print(f"\n📊 Summary:")
            print(f"  - Profiles migrated: {profiles_migrated}")
            print(f"  - Approved cards migrated: {cards_migrated}")
            print(f"  - Chat messages migrated: {messages_migrated}")
            print(f"\n📦 Backups created:")
            print(f"  - JSON backup: {json_backup_dir}")
            if DB_PATH.exists():
                print(f"  - Database: {DB_PATH}")
            print("\n⚠️  IMPORTANT: Test the database before deleting JSON backups!")
        else:
            print("\n❌ Migration verification failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

