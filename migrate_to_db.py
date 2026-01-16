import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# Add the project root to path
sys.path.append(os.getcwd())

# Using backend. prefix as requested
from backend.app.core.config import PROFILES_FILE, DATABASE_PATH
from backend.database.db import get_db_session, init_db
from backend.database.services import ProfileService

def create_backup():
    if DATABASE_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DATABASE_PATH.with_suffix(f".db.backup_{timestamp}")
        print(f"🛡️  Creating database backup...")
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Backup created: {backup_path.name}")
        return True
    return False

def migrate():
    print("🚀 Starting Migration: JSON -> SQLite Database")
    
    # 1. Backup existing DB if it exists
    create_backup()
    
    # 2. Initialize DB structure
    init_db()
    
    # 3. Check if JSON file exists
    if not os.path.exists(PROFILES_FILE):
        print(f"❌ Could not find old profiles file at: {PROFILES_FILE}")
        return

    # 4. Load old profiles
    with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
        old_profiles = json.load(f)
    
    print(f"📋 Found {len(old_profiles)} profiles in JSON.")

    # FIX: Using 'with' statement instead of next()
    try:
        with get_db_session() as db:
            for old_data in old_profiles:
                # Generate slug ID
                profile_name = old_data.get('name', 'unknown')
                profile_id = old_data.get('id') or profile_name.lower().replace(" ", "-")
                
                # Check if already migrated
                existing = ProfileService.get_by_id(db, profile_id)
                if existing:
                    print(f"⏩ Profile '{profile_id}' already in database. Skipping.")
                    continue

                print(f"🔄 Migrating: {profile_name}...")

                # Extract mastered words safely
                m_zh = old_data.get('mastered_words') or ""
                m_en = old_data.get('mastered_english_words') or ""
                m_gr = old_data.get('mastered_grammar') or ""

                new_profile_data = {
                    "id": profile_id,
                    "name": profile_name,
                    "dob": old_data.get('dob', ""),
                    "gender": old_data.get('gender', ""),
                    "address": old_data.get('address', ""),
                    "school": old_data.get('school', ""),
                    "neighborhood": old_data.get('neighborhood', ""),
                    "interests": old_data.get('interests', []),
                    "character_roster": old_data.get('character_roster', []),
                    "verbal_fluency": old_data.get('verbal_fluency'),
                    "passive_language_level": old_data.get('passive_language_level'),
                    "mental_age": old_data.get('mental_age'),
                    "raw_input": old_data.get('raw_input'),
                    "extracted_data": old_data.get('extracted_data', {}),
                    "mastered_words_list": [w.strip() for w in m_zh.split(',') if w.strip()] if isinstance(m_zh, str) else [],
                    "mastered_english_words_list": [w.strip() for w in m_en.split(',') if w.strip()] if isinstance(m_en, str) else [],
                    "mastered_grammar_list": [g.strip() for g in m_gr.split(',') if g.strip()] if isinstance(m_gr, str) else []
                }

                ProfileService.create(db, new_profile_data)
                print(f"✅ Successfully migrated {profile_name}")

            db.commit()
            print("\n✨ Migration Complete! You can now restart your app.")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate()
