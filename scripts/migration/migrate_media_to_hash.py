#!/usr/bin/env python3
"""
Migrate media files to hash-based naming system.

This script:
1. Scans content/media/images and media/character_recognition
2. Calculates SHA256 hash (first 12 chars) for each file
3. Copies files to content/media/objects/{hash}.{canonical_ext}
4. Updates approved_cards table to replace old filenames
5. Updates knowledge graph TTL file to update srs-kg:imageFileName
6. Creates a recovery log for rollback
"""

import sys
import json
import hashlib
import shutil
import re
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.database.db import get_db_session
from backend.database.models import ApprovedCard

try:
    from rdflib import Graph, Namespace, Literal, RDF
    from rdflib.namespace import RDFS
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_IMAGES_DIR = PROJECT_ROOT / "content" / "media" / "images"
MEDIA_CHAR_RECOG_DIR = PROJECT_ROOT / "media" / "character_recognition"
MEDIA_OBJECTS_DIR = PROJECT_ROOT / "content" / "media" / "objects"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"

# RDF Namespace
SRS_KG = Namespace("http://srs4autism.com/schema/")


def get_canonical_ext(filename: str) -> str:
    """
    Map file extensions to canonical lowercase forms.
    
    Maps .jpeg/.JPG to .jpg, keeps .png, .webp, .gif, .svg as lowercase.
    
    Args:
        filename: Original filename
        
    Returns:
        Canonical extension (e.g., '.jpg', '.png')
    """
    ext = Path(filename).suffix.lower()
    
    # Map .jpeg to .jpg
    if ext == '.jpeg':
        return '.jpg'
    
    # Keep valid extensions as lowercase
    if ext in ['.jpg', '.png', '.webp', '.gif', '.svg']:
        return ext
    
    # For unknown extensions, return as-is (lowercase)
    return ext


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of file and return first 12 characters.
    
    Args:
        file_path: Path to file
        
    Returns:
        First 12 characters of SHA256 hash (hex)
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()[:12]


def scan_and_migrate_files() -> Dict[str, str]:
    """
    Scan source directories and migrate files to hash-based names.
    
    Returns:
        Dictionary mapping old_full_path -> new_hash_filename
    """
    migration_map = {}
    
    # Ensure target directory exists
    MEDIA_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Directories to scan
    scan_dirs = []
    if MEDIA_IMAGES_DIR.exists():
        scan_dirs.append(MEDIA_IMAGES_DIR)
    if MEDIA_CHAR_RECOG_DIR.exists():
        scan_dirs.append(MEDIA_CHAR_RECOG_DIR)
    
    if not scan_dirs:
        print("⚠️  No source directories found to scan")
        return migration_map
    
    print(f"🔍 Scanning {len(scan_dirs)} directory(ies) for image files...")
    
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', 
                        '.JPG', '.JPEG', '.PNG', '.WEBP', '.GIF', '.SVG'}
    
    files_processed = 0
    files_copied = 0
    files_skipped = 0
    
    for scan_dir in scan_dirs:
        print(f"\n📁 Scanning {scan_dir}...")
        
        # Find all image files
        for file_path in scan_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix
            if ext not in image_extensions:
                continue
            
            files_processed += 1
            
            # Calculate hash
            try:
                file_hash = calculate_file_hash(file_path)
            except Exception as e:
                print(f"  ❌ Error calculating hash for {file_path.name}: {e}")
                files_skipped += 1
                continue
            
            # Get canonical extension
            canonical_ext = get_canonical_ext(file_path.name)
            
            # Create new filename
            new_filename = f"{file_hash}{canonical_ext}"
            new_path = MEDIA_OBJECTS_DIR / new_filename
            
            # Handle collisions (if hash already exists, check if same file)
            if new_path.exists():
                # Check if files are identical
                existing_hash = calculate_file_hash(new_path)
                current_hash = calculate_file_hash(file_path)
                
                if existing_hash == current_hash:
                    # Same file, skip
                    old_filename = file_path.name
                    old_full_path = str(file_path.relative_to(PROJECT_ROOT))
                    migration_map[old_full_path] = new_filename
                    print(f"  ⏭️  Skipped (duplicate): {file_path.name} -> {new_filename}")
                    files_skipped += 1
                    continue
                else:
                    # Different file with same hash prefix (very unlikely)
                    print(f"  ⚠️  Hash collision detected for {file_path.name}, using full hash")
                    full_hash = hashlib.sha256()
                    with open(file_path, "rb") as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            full_hash.update(byte_block)
                    file_hash = full_hash.hexdigest()[:16]  # Use 16 chars to avoid collision
                    new_filename = f"{file_hash}{canonical_ext}"
                    new_path = MEDIA_OBJECTS_DIR / new_filename
            
            # Copy file
            try:
                shutil.copy2(file_path, new_path)
                
                old_filename = file_path.name
                old_full_path = str(file_path.relative_to(PROJECT_ROOT))
                migration_map[old_full_path] = new_filename
                
                print(f"  ✅ {file_path.name} -> {new_filename}")
                files_copied += 1
            except Exception as e:
                print(f"  ❌ Error copying {file_path.name}: {e}")
                files_skipped += 1
    
    print(f"\n📊 Summary:")
    print(f"  Files processed: {files_processed}")
    print(f"  Files copied: {files_copied}")
    print(f"  Files skipped: {files_skipped}")
    
    return migration_map


def update_database(migration_map: Dict[str, str]):
    """
    Update approved_cards table to replace old filenames with new hash filenames.
    
    Args:
        migration_map: Dictionary mapping old_full_path -> new_hash_filename
    """
    if not DB_PATH.exists():
        print(f"⚠️  Database not found at {DB_PATH}, skipping database update")
        return
    
    print("\n💾 Updating database...")
    
    # Build reverse lookup: old_filename -> new_filename
    filename_to_new = {}
    for old_path, new_filename in migration_map.items():
        old_filename = Path(old_path).name
        filename_to_new[old_filename] = new_filename
    
    if not filename_to_new:
        print("  ℹ️  No files to update in database")
        return
    
    updated_count = 0
    
    with get_db_session() as db:
        cards = db.query(ApprovedCard).all()
        print(f"  Found {len(cards)} approved cards to check")
        
        for card in cards:
            try:
                # Parse JSON content
                content = json.loads(card.content)
                updated = False
                
                # Update front field
                if 'front' in content and content['front']:
                    old_front = content['front']
                    new_front = replace_image_refs(old_front, filename_to_new)
                    if old_front != new_front:
                        content['front'] = new_front
                        updated = True
                
                # Update back field
                if 'back' in content and content['back']:
                    old_back = content['back']
                    new_back = replace_image_refs(old_back, filename_to_new)
                    if old_back != new_back:
                        content['back'] = new_back
                        updated = True
                
                # Save if updated
                if updated:
                    card.content = json.dumps(content, ensure_ascii=False)
                    updated_count += 1
                    
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Error parsing card {card.id} content: {e}")
            except Exception as e:
                print(f"  ❌ Error updating card {card.id}: {e}")
        
        db.commit()
    
    print(f"  ✅ Updated {updated_count} cards")


def replace_image_refs(text: str, filename_map: Dict[str, str]) -> str:
    """
    Replace image filename references in text with new hash filenames.
    
    Handles:
    - <img src="filename.ext">
    - Direct filename references in paths
    - Relative paths with filenames
    
    Args:
        text: Text containing image references
        filename_map: Dictionary mapping old_filename -> new_filename
        
    Returns:
        Text with replaced filenames
    """
    if not text:
        return text
    
    result = text
    
    # Pattern 1: <img src="...filename...">
    # Match img tags with src attributes
    img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
    
    def replace_img_src(match):
        src_value = match.group(1)
        # Extract filename from path
        path_parts = src_value.replace('\\', '/').split('/')
        old_filename = path_parts[-1] if path_parts else src_value
        
        # Check if we have a mapping for this filename
        if old_filename in filename_map:
            new_filename = filename_map[old_filename]
            # Replace just the filename part
            new_src = '/'.join(path_parts[:-1] + [new_filename]) if len(path_parts) > 1 else new_filename
            # Preserve the original path structure if it had one
            if src_value.startswith('/') or src_value.startswith('http'):
                # Keep absolute path structure
                pass
            return match.group(0).replace(src_value, new_src)
        return match.group(0)
    
    result = re.sub(img_pattern, replace_img_src, result)
    
    # Pattern 2: Direct filename references (not in img tags)
    # This handles cases where filenames appear directly in text
    for old_filename, new_filename in filename_map.items():
        # Replace standalone filename (with word boundaries to avoid partial matches)
        # But allow for path separators
        pattern = r'\b' + re.escape(old_filename) + r'\b'
        result = re.sub(pattern, new_filename, result)
    
    return result


def update_knowledge_graph(migration_map: Dict[str, str]):
    """
    Update knowledge graph TTL file to update srs-kg:imageFileName values.
    
    Args:
        migration_map: Dictionary mapping old_full_path -> new_hash_filename
    """
    if not KG_FILE.exists():
        print(f"⚠️  Knowledge graph file not found at {KG_FILE}, skipping KG update")
        return
    
    print("\n🔗 Updating knowledge graph...")
    
    # Build filename mapping (just filename, not full path)
    filename_to_new = {}
    for old_path, new_filename in migration_map.items():
        old_filename = Path(old_path).name
        filename_to_new[old_filename] = new_filename
    
    if not filename_to_new:
        print("  ℹ️  No files to update in knowledge graph")
        return
    
    try:
        # Load graph
        print(f"  Loading graph from {KG_FILE} (this may take a while)...")
        graph = Graph()
        graph.parse(str(KG_FILE), format="turtle")
        graph.bind("srs-kg", SRS_KG)
        
        print(f"  Loaded {len(graph)} triples")
        
        # Find all imageFileName properties and update them
        updated_count = 0
        added_original_count = 0
        
        # Build index: old_filename -> image_uri
        filename_to_uri = {}
        for s, p, o in graph.triples((None, SRS_KG.imageFileName, None)):
            old_filename = str(o)
            filename_to_uri[old_filename] = s
        
        print(f"  Found {len(filename_to_uri)} images in knowledge graph")
        
        # Update each image
        for old_filename, new_filename in filename_to_new.items():
            if old_filename in filename_to_uri:
                image_uri = filename_to_uri[old_filename]
                
                # Update imageFileName
                graph.set((image_uri, SRS_KG.imageFileName, Literal(new_filename)))
                updated_count += 1
                
                # Add originalName property if it doesn't exist
                # Note: Using originalName as per user specification (codebase also has originalFileName)
                existing_original = graph.value(image_uri, SRS_KG.originalName)
                if existing_original is None:
                    graph.add((image_uri, SRS_KG.originalName, Literal(old_filename)))
                    added_original_count += 1
                else:
                    # Update if it exists (shouldn't happen, but handle it)
                    graph.set((image_uri, SRS_KG.originalName, Literal(old_filename)))
        
        # Save updated graph
        print(f"  Updated {updated_count} imageFileName values")
        print(f"  Added {added_original_count} originalName properties")
        print(f"  Saving to {KG_FILE}...")
        
        graph.serialize(destination=str(KG_FILE), format="turtle")
        
        print(f"  ✅ Knowledge graph updated successfully")
        
    except Exception as e:
        print(f"  ❌ Error updating knowledge graph: {e}")
        import traceback
        traceback.print_exc()


def save_migration_log(migration_map: Dict[str, str]):
    """
    Save migration log for recovery purposes.
    
    Args:
        migration_map: Dictionary mapping old_full_path -> new_hash_filename
    """
    log_data = {
        'old_full_path': {old: new for old, new in migration_map.items()},
        'timestamp': str(Path(__file__).stat().st_mtime)
    }
    
    with open(MIGRATION_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 Migration log saved to {MIGRATION_LOG}")


def main():
    """Main migration function."""
    print("=" * 80)
    print("Media Migration to Hash-Based Naming")
    print("=" * 80)
    
    # Step 1: Scan and migrate files
    migration_map = scan_and_migrate_files()
    
    if not migration_map:
        print("\n⚠️  No files were migrated. Exiting.")
        return
    
    # Step 2: Save migration log
    save_migration_log(migration_map)
    
    # Step 3: Update database
    update_database(migration_map)
    
    # Step 4: Update knowledge graph
    update_knowledge_graph(migration_map)
    
    print("\n" + "=" * 80)
    print("✅ Migration completed successfully!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"  Files migrated: {len(migration_map)}")
    print(f"  Migration log: {MIGRATION_LOG}")
    print(f"\n⚠️  Remember to backup your database and KG file before running this script!")
    print(f"   The original files in source directories are preserved.")


if __name__ == "__main__":
    main()

