# Database Migration Plan

## Current Problems with JSON Files

1. **No ACID transactions** - Can't rollback on errors
2. **No data validation** - Easy to corrupt data
3. **No concurrent access control** - Risk of data loss with multiple writes
4. **No audit trail** - Can't track who changed what and when
5. **Manual backups** - Prone to human error

## Proposed Solution: SQLite → PostgreSQL Migration Path

### Phase 1: SQLite (Immediate)
- Easy to set up, single file database
- Built-in Python support
- ACID compliant
- Good for development and single-user scenarios
- Zero configuration, no server needed

### Phase 2: PostgreSQL (Future)
- Production-grade database
- Better concurrency
- Advanced features (full-text search, JSON columns, etc.)
- Easy migration from SQLite using SQLAlchemy

## Database Schema Design

### Tables

#### `profiles`
```sql
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dob TEXT,
    gender TEXT,
    address TEXT,
    school TEXT,
    neighborhood TEXT,
    interests TEXT,  -- JSON array
    character_roster TEXT,  -- JSON array
    verbal_fluency TEXT,
    passive_language_level TEXT,
    mental_age REAL,
    raw_input TEXT,
    extracted_data TEXT,  -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `mastered_words`
```sql
CREATE TABLE mastered_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    word TEXT NOT NULL,
    language TEXT NOT NULL,  -- 'zh' or 'en'
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    UNIQUE(profile_id, word, language)
);

CREATE INDEX idx_mastered_words_profile ON mastered_words(profile_id);
CREATE INDEX idx_mastered_words_language ON mastered_words(language);
```

#### `mastered_grammar`
```sql
CREATE TABLE mastered_grammar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    grammar_uri TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    UNIQUE(profile_id, grammar_uri)
);

CREATE INDEX idx_mastered_grammar_profile ON mastered_grammar(profile_id);
```

#### `approved_cards`
```sql
CREATE TABLE approved_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    card_type TEXT NOT NULL,
    content TEXT NOT NULL,  -- JSON object
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX idx_approved_cards_profile ON approved_cards(profile_id);
```

#### `chat_history`
```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_messages_profile ON chat_messages(profile_id);
CREATE INDEX idx_chat_messages_timestamp ON chat_messages(timestamp);
```

#### `audit_log` (NEW - Track all changes)
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
    old_value TEXT,  -- JSON
    new_value TEXT,  -- JSON
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT  -- 'system', 'user', 'migration', etc.
);

CREATE INDEX idx_audit_log_table ON audit_log(table_name);
CREATE INDEX idx_audit_log_timestamp ON audit_log(changed_at);
```

## Migration Strategy

### Step 1: Create Database Schema
```python
# backend/database/schema.py
```

### Step 2: Data Migration Script
```python
# scripts/migrate_json_to_db.py
- Read existing JSON files
- Validate data
- Insert into SQLite database
- Create backup of JSON files
- Verify migration success
```

### Step 3: Update Backend API
```python
# backend/database/models.py - SQLAlchemy models
# backend/database/db.py - Database connection
# backend/app/main.py - Update endpoints to use database
```

### Step 4: Backward Compatibility
- Keep JSON files as fallback during transition
- Add flag to switch between JSON and DB modes
- Monitor for issues before full cutover

### Step 5: Testing
- Unit tests for all database operations
- Integration tests for API endpoints
- Load testing for concurrent access
- Backup/restore testing

## Advantages of This Approach

### Data Integrity
- ✅ Transactions ensure all-or-nothing operations
- ✅ Foreign key constraints prevent orphaned data
- ✅ Unique constraints prevent duplicates
- ✅ Type validation at database level

### Safety
- ✅ Automatic backups (SQLite file + audit log)
- ✅ Point-in-time recovery possible
- ✅ Audit trail for all changes
- ✅ Easy to rollback transactions

### Performance
- ✅ Indexed queries for fast lookups
- ✅ Efficient updates (no need to rewrite entire file)
- ✅ Better memory usage for large datasets

### Developer Experience
- ✅ ORM (SQLAlchemy) for type-safe queries
- ✅ Migrations with Alembic
- ✅ Easy to test with in-memory databases
- ✅ Clear schema documentation

## Timeline

### Immediate (Day 1-2)
- [x] Create database schema
- [ ] Create SQLAlchemy models
- [ ] Write migration script (JSON → SQLite)
- [ ] Test migration with backup data

### Short-term (Day 3-5)
- [ ] Update backend API to use database
- [ ] Add audit logging
- [ ] Create automated backup system
- [ ] Write unit tests

### Medium-term (Week 2)
- [ ] Full integration testing
- [ ] Performance optimization
- [ ] Documentation update
- [ ] Deploy to production

### Long-term (Future)
- [ ] Consider PostgreSQL migration if needed
- [ ] Add database monitoring
- [ ] Implement sharding if scaling needed

## Rollback Plan

If database migration fails:
1. Restore JSON files from backup
2. Switch backend to JSON mode
3. Investigate and fix issues
4. Retry migration with fixes

## Success Metrics

- ✅ Zero data loss during migration
- ✅ All existing features work with database
- ✅ Faster query performance
- ✅ Audit log captures all changes
- ✅ Backup/restore works reliably

