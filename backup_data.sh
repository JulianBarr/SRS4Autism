#!/bin/bash
# Quick backup script for critical data files

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="data/backups/$TIMESTAMP"

echo "Creating backup: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Backup critical files
cp data/profiles/child_profiles.json "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ child_profiles.json"
cp data/content_db/approved_cards.json "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ approved_cards.json"
cp data/content_db/chat_history.json "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ chat_history.json"
cp data/content_db/word_kp_cache.json "$BACKUP_DIR/" 2>/dev/null && echo "  ✅ word_kp_cache.json"

# Create compressed archive
cd data/backups
tar -czf "${TIMESTAMP}.tar.gz" "$TIMESTAMP" 2>/dev/null
rm -rf "$TIMESTAMP"
cd ../..

echo "✅ Backup complete: data/backups/${TIMESTAMP}.tar.gz"
echo ""
echo "To restore:"
echo "  tar -xzf data/backups/${TIMESTAMP}.tar.gz -C data/backups/"
echo "  cp data/backups/${TIMESTAMP}/child_profiles.json data/profiles/"

