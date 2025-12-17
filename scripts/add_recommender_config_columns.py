#!/usr/bin/env python3
"""
Migration script to add recommender configuration columns to profiles table.

Adds:
- recommender_daily_capacity (INTEGER, default 20)
- recommender_vocab_ratio (FLOAT, default 0.5)
- recommender_grammar_ratio (FLOAT, default 0.5)
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db_session, create_backup, DB_PATH
from sqlalchemy import text


def migrate():
    """Add recommender configuration columns to profiles table."""
    print("=" * 80)
    print("Adding Recommender Configuration Columns to Profiles Table")
    print("=" * 80)
    
    # Create backup
    print("\n📦 Creating database backup...")
    backup_path = create_backup()
    print(f"   ✅ Backup created: {backup_path}")
    
    # Check if columns already exist
    with get_db_session() as db:
        result = db.execute(text("PRAGMA table_info(profiles)"))
        columns = [row[1] for row in result.fetchall()]
        
        if "recommender_daily_capacity" in columns:
            print("\n⚠️  Column 'recommender_daily_capacity' already exists!")
            print("   Migration may have already been run.")
            response = input("   Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Migration cancelled")
                return False
    
    # Add columns
    print("\n🔧 Adding new columns...")
    with get_db_session() as db:
        try:
            # Add recommender_daily_capacity
            print("   Adding recommender_daily_capacity...")
            db.execute(text("""
                ALTER TABLE profiles 
                ADD COLUMN recommender_daily_capacity INTEGER DEFAULT 20
            """))
            
            # Add recommender_vocab_ratio
            print("   Adding recommender_vocab_ratio...")
            db.execute(text("""
                ALTER TABLE profiles 
                ADD COLUMN recommender_vocab_ratio REAL DEFAULT 0.5
            """))
            
            # Add recommender_grammar_ratio
            print("   Adding recommender_grammar_ratio...")
            db.execute(text("""
                ALTER TABLE profiles 
                ADD COLUMN recommender_grammar_ratio REAL DEFAULT 0.5
            """))
            
            db.commit()
            print("\n✅ Migration completed successfully!")
            
            # Verify
            result = db.execute(text("PRAGMA table_info(profiles)"))
            columns = [row[1] for row in result.fetchall()]
            if all(col in columns for col in [
                "recommender_daily_capacity",
                "recommender_vocab_ratio",
                "recommender_grammar_ratio"
            ]):
                print("✅ Verification: All columns added successfully")
                
                # Show current values
                result = db.execute(text("""
                    SELECT id, name, 
                           recommender_daily_capacity,
                           recommender_vocab_ratio,
                           recommender_grammar_ratio
                    FROM profiles
                """))
                profiles = result.fetchall()
                if profiles:
                    print("\n📊 Current profile values:")
                    for profile in profiles:
                        print(f"   {profile[1]} (ID: {profile[0]}):")
                        print(f"      Daily capacity: {profile[2]}")
                        print(f"      Vocab ratio: {profile[3]}")
                        print(f"      Grammar ratio: {profile[4]}")
                
                return True
            else:
                print("❌ Verification failed: Some columns missing")
                return False
                
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)







