"""
Migration script to convert existing UUID-based profile IDs to slug-based IDs.

This script:
1. Loads existing profiles from profiles.json
2. Generates slugs for profiles without slugs
3. Updates profiles.json with new slug-based IDs
4. Preserves existing UUIDs for profiles that already have them

Usage:
    python backend/migrations/migrate_to_slugs.py
"""
import json
import os
import sys

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

from utils.slug_generator import SlugGenerator

PROFILES_FILE = os.path.join(backend_dir, "data", "profiles", "child_profiles.json")

def migrate_profiles_to_slugs():
    """Migrate existing profiles to use slug-based IDs."""
    
    if not os.path.exists(PROFILES_FILE):
        print(f"❌ {PROFILES_FILE} not found")
        return
    
    # Load existing profiles
    with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    print(f"📋 Found {len(profiles)} profile(s) to migrate")
    
    # Create slug generator instance
    slug_gen = SlugGenerator()
    
    # Pre-load all existing IDs to avoid duplicates
    existing_ids = [p.get("id") for p in profiles if p.get("id")]
    slug_gen.used_slugs = existing_ids.copy()
    
    updated_count = 0
    for profile in profiles:
        old_id = profile.get("id", "")
        name = profile.get("name", "")
        
        if not name:
            print(f"⚠️  Skipping profile with no name: {old_id}")
            continue
        
        # Check if ID is already a UUID (has hyphens in UUID format)
        import re
        is_uuid = re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', old_id, re.IGNORECASE)
        
        if is_uuid:
            # Generate slug from name
            new_slug = slug_gen.generate_slug(name)
            print(f"🔄 {name}: {old_id} -> {new_slug}")
            profile["id"] = new_slug
            updated_count += 1
        else:
            print(f"✓ Already using slug: {name} -> {old_id}")
    
    # Save updated profiles
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Migration complete! Updated {updated_count} profile(s)")


if __name__ == "__main__":
    migrate_profiles_to_slugs()

