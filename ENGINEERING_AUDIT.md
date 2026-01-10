# ENGINEERING AUDIT: CUMA (SRS4Autism)
## Prepared for MVP Release - Architecture Deep Dive

**Date:** 2026-01-10
**Auditor:** Senior Principal Engineer
**Scope:** Data Save Flow, Fuseki/Jena Integration, Architectural Integrity

---

## Executive Summary

This codebase operates a **DUAL-DATABASE ARCHITECTURE** with significant architectural debt. Fuseki/Jena is deeply entangled with the application logic, presenting **HIGH MIGRATION RISK**. Multiple layers violate separation of concerns, and error handling is inconsistent with several "swallow-and-continue" patterns that mask failures.

**Migration Complexity:** HIGH (3-4 weeks of refactoring + testing)
**Production Readiness:** MEDIUM (functional but brittle)
**Technical Debt:** HIGH (requires immediate attention before scaling)

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Technology Stack Discovery

| Component | Technology | Location | Status |
|-----------|-----------|----------|--------|
| **Backend Entry** | FastAPI (Python) | `backend/run.py` → `backend/app/main.py` | ✅ Active |
| **Relational DB** | SQLite + SQLAlchemy ORM | `data/srs4autism.db` | ✅ Active |
| **Knowledge Graph** | Apache Jena Fuseki (SPARQL) | `apache-jena-fuseki-4.9.0/` + `knowledge_graph/*.ttl` | ✅ Active |
| **Frontend** | React (axios for HTTP) | `frontend/src/` | ✅ Active |
| **Media Storage** | Filesystem (hash-based naming) | `media/` | ✅ Active |
| **Backup Storage** | JSON flat files | `backend/data/content_db/` | ⚠️ Legacy |

### 1.2 Database Responsibilities

#### SQLite (`data/srs4autism.db`)
Handles **user-centric transactional data**:
- User profiles (name, DOB, mental age, interests)
- Mastered words/grammar (per-user progress tracking)
- Approved cards (user-generated content)
- Chat history (conversational state)
- Audit logs (change tracking)
- Literacy course progress (character/word/pinyin notes)

**Connection Pattern:**
```python
backend/database/db.py:24
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
```

#### Fuseki/Jena (`http://localhost:3030/srs4autism/query`)
Handles **semantic knowledge and recommendations**:
- Word nodes (Chinese/English vocabulary with metadata)
- Grammar points (prerequisite chains, CEFR/HSK levels)
- Concept relationships (similarity graphs, translations)
- Pedagogical metadata (AoA, frequency, concreteness)
- Prerequisite dependencies (learning paths)

**Connection Pattern:**
```python
agentic/tools.py:34
self._kg_endpoint = "http://localhost:3030/srs4autism/query"
# Direct HTTP SPARQL queries via requests library
```

---

## 2. DATA SAVE FLOW ANALYSIS

### 2.1 Trace: "Save Profile" Operation

**Frontend → Backend → Database:**

```
frontend/src/components/CardCuration.js:35
    ↓ [axios.post/put]
backend/app/main.py:1490  @app.post("/profiles")
    ↓ [FastAPI dependency injection]
backend/database/db.py:54  get_db() → Session
    ↓ [SQLAlchemy ORM]
backend/database/services.py:27  ProfileService.create()
    ↓ [Manual JSON serialization]
backend/database/models.py:14  Profile (SQLAlchemy model)
    ↓ [db.commit()]
data/srs4autism.db  [SQLite file write]
    ↓ [Audit trail]
backend/database/models.py:140  AuditLog (INSERT record)
```

**Critical Observations:**
1. **No validation layer** - Pydantic models at API boundary, then raw dicts
2. **JSON stored as TEXT** - `interests`, `character_roster`, `extracted_data` fields are stringified JSON
3. **Split into child tables** - `mastered_words` split by comma, written to `MasteredWord` table
4. **Audit trail** - Manual logging after each operation (not atomic with main transaction)
5. **No rollback handling** - If audit log fails, profile is already committed

### 2.2 Trace: "Get Recommendations" Operation

**Frontend → Backend → SPARQL → Fuseki:**

```
frontend/src/components/*.js
    ↓ [axios.post]
backend/app/main.py:3367  @app.post("/recommendations/integrated")
    ↓ [Service instantiation]
backend/services/integrated_recommender_service.py:64  IntegratedRecommenderService.__init__()
    ↓ [Mastery vector from Anki]
backend/services/integrated_recommender_service.py:226  build_mastery_vector()
    ↓ [SPARQL query construction]
agentic/tools.py:88  query_world_model()
    ↓ [HTTP POST with SPARQL]
requests.get(kg_endpoint + "?query=" + sparql)
    ↓ [Fuseki SPARQL engine]
http://localhost:3030/srs4autism/query
    ↓ [Parse JSON response]
backend/services/chinese_ppr_recommender_service.py:269  get_recommendations()
```

**Critical Observations:**
1. **Hardcoded endpoint** - Fuseki URL appears in 7+ files
2. **No connection pooling** - Each query creates new HTTP connection
3. **Timeout inconsistency** - Some queries timeout at 15s, others 30s, some never
4. **Error swallowing** - `agentic/tools.py:132` returns `{"error": str(e)}` but caller treats as success
5. **TTL fallback** - Some services parse `.ttl` files directly when Fuseki unavailable
6. **No retry logic** - Transient network failures fail immediately

---

## 3. MIGRATION RISK: Fuseki → Oxigraph

### 3.1 Entanglement Level: **HIGH**

Fuseki is **not abstracted** - it's hardcoded throughout the stack:

| File | Lines | Coupling Type | Migration Impact |
|------|-------|---------------|-----------------|
| `agentic/tools.py` | 34, 126 | Hardcoded URL, SPARQL queries | REWRITE |
| `backend/services/integrated_recommender_service.py` | 113, 293, 378 | Fuseki endpoint in config | MODIFY |
| `backend/services/chinese_ppr_recommender_service.py` | 202, 236 | TTL file parsing (fallback) | KEEP FALLBACK |
| `backend/services/ppr_recommender_service.py` | (Similar patterns) | TTL file parsing (fallback) | KEEP FALLBACK |
| `scripts/knowledge_graph/*.py` | 60+ files | SPARQL INSERT/UPDATE operations | TEST COMPATIBILITY |
| `restart_fuseki.sh` | 1 | Server startup script | DELETE |
| `apache-jena-fuseki-4.9.0/` | Directory | Entire Fuseki installation | DELETE |

**Total Files Affected:** ~70 files

### 3.2 Files to Modify for Oxigraph Migration

#### DELETE (no longer needed):
```
apache-jena-fuseki-4.9.0/          # Entire Fuseki server
restart_fuseki.sh                   # Startup script
```

#### CRITICAL REWRITES (direct Fuseki coupling):
```
agentic/tools.py                    # Hardcoded endpoint URL
backend/services/integrated_recommender_service.py  # Config + endpoint
backend/app/main.py                 # Direct SPARQL queries (if any)
```

#### MODIFY (configuration changes):
```
backend/services/chinese_ppr_recommender_service.py  # Update endpoint config
backend/services/ppr_recommender_service.py          # Update endpoint config
scripts/knowledge_graph/*_recommender.py             # Update KG service config
```

#### TEST EXTENSIVELY (SPARQL dialect differences):
```
scripts/knowledge_graph/*.py        # All KG ingestion/query scripts
```

### 3.3 Migration Steps (Recommended)

1. **Create abstraction layer** (1-2 days):
   ```python
   # NEW: backend/services/kg_adapter.py
   class KnowledgeGraphAdapter(ABC):
       @abstractmethod
       def query(self, sparql: str) -> Dict[str, Any]: ...

   class FusekiAdapter(KnowledgeGraphAdapter): ...
   class OxigraphAdapter(KnowledgeGraphAdapter): ...
   ```

2. **Replace hardcoded URLs with config** (1 day):
   ```python
   # backend/config.py
   KG_ENDPOINT = os.getenv("KG_SPARQL_ENDPOINT", "http://localhost:3030/srs4autism/query")
   KG_ADAPTER = os.getenv("KG_ADAPTER", "fuseki")  # or "oxigraph"
   ```

3. **Dual-run testing** (3-5 days):
   - Run Fuseki and Oxigraph in parallel
   - Query both, compare results
   - Validate SPARQL compatibility

4. **Cutover and cleanup** (1 day):
   - Switch config to Oxigraph
   - Delete Fuseki directory
   - Update deployment docs

**Total Estimated Time:** 1-2 weeks (development) + 1-2 weeks (testing/validation)

---

## 4. DIRTY SECRETS: Logic Gaps & Happy Path Assumptions

### 4.1 Exception Swallowing

**Location:** `agentic/tools.py:66-69`
```python
def query_mastery_vector(self, user_id: str) -> Dict[str, float]:
    try:
        # ... timeout logic ...
        return mastery_vector
    except Exception as e:
        print(f"⚠️  Error querying mastery vector: {e}")
        return {}  # 🚨 DIRTY SECRET: Swallows error, returns empty dict
```

**Impact:** Caller receives `{}` (empty mastery) and proceeds as if user has no progress. No error propagation. Silently degrades to "beginner mode".

**Fix:** Raise a custom exception or return `Result[Dict, Error]` type.

---

**Location:** `agentic/tools.py:130-133`
```python
def query_world_model(...) -> Dict[str, Any]:
    try:
        response = requests.get(url, timeout=15)
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "timeout", "data": {}}  # 🚨 DIRTY SECRET
    except Exception as e:
        return {"error": str(e), "data": {}}      # 🚨 DIRTY SECRET
```

**Impact:** Caller must check for `"error"` key. Many callers don't. Silently treats KG as empty.

**Fix:** Use proper exception hierarchy or explicit error types.

---

### 4.2 Missing Transaction Boundaries

**Location:** `backend/database/services.py:60-72`
```python
def create(db: Session, profile_data: Dict[str, Any]) -> Profile:
    profile = Profile(**profile_data)
    db.add(profile)
    db.flush()  # Get profile ID

    # Add mastered words
    for word in mastered_words_zh:
        db.add(MasteredWord(profile_id=profile.id, word=word))

    db.commit()  # 🚨 DIRTY SECRET: What if commit fails here?

    # Create audit log
    db.add(AuditLog(...))  # 🚨 DIRTY SECRET: Separate transaction!
    db.commit()
```

**Impact:**
- If second `commit()` fails, audit log is lost but profile is saved
- If first `commit()` fails after `flush()`, partial state may exist
- No rollback wrapper for multi-step operations

**Fix:** Use context manager or wrap entire operation in single transaction:
```python
with db.begin():
    profile = Profile(**profile_data)
    db.add(profile)
    db.flush()
    for word in mastered_words_zh:
        db.add(MasteredWord(...))
    db.add(AuditLog(...))
    # Auto-commit or rollback on exception
```

---

### 4.3 JSON Serialization Errors Not Handled

**Location:** `backend/database/services.py:36-40`
```python
if 'interests' in profile_data and isinstance(profile_data['interests'], list):
    profile_data['interests'] = json.dumps(profile_data['interests'])
# 🚨 DIRTY SECRET: What if interests contains un-serializable objects?
# 🚨 DIRTY SECRET: What if it's already a string? (idempotency issue)
```

**Impact:**
- Can store double-encoded JSON: `"[\"value\"]"` instead of `["value"]`
- TypeError not caught if list contains complex objects

**Fix:** Add validation and handle serialization errors:
```python
try:
    if isinstance(profile_data['interests'], (list, dict)):
        profile_data['interests'] = json.dumps(profile_data['interests'])
    elif not isinstance(profile_data['interests'], str):
        raise ValueError(f"Invalid type for interests: {type(profile_data['interests'])}")
except (TypeError, ValueError) as e:
    # Log and either reject or sanitize
    raise HTTPException(status_code=400, detail=f"Invalid interests format: {e}")
```

---

### 4.4 No Validation of SPARQL Responses

**Location:** `backend/services/chinese_ppr_recommender_service.py:269-492`
```python
def get_recommendations(...) -> List[Dict[str, Any]]:
    scores = run_ppr(self.graph, personalization, alpha=config["alpha"])

    for node_id, raw_ppr_score in scores.items():
        meta = self.word_metadata.get(node_id)
        if not meta:
            continue  # 🚨 DIRTY SECRET: Silently skips missing metadata

        # Assumes meta.concreteness, meta.hsk_level are valid types
        conc_transformed = transform_concreteness(meta.concreteness)
        # 🚨 DIRTY SECRET: What if concreteness is "N/A" string instead of float?
```

**Impact:**
- Type errors can occur if KG data is malformed
- Silent skipping means recommendations may be incomplete
- No logging of how many nodes were skipped

**Fix:** Add schema validation or strict type checking:
```python
if not meta:
    logger.warning(f"Missing metadata for node {node_id}, skipping")
    skipped_count += 1
    continue

if not isinstance(meta.concreteness, (int, float, type(None))):
    logger.error(f"Invalid concreteness type for {node_id}: {type(meta.concreteness)}")
    continue
```

---

### 4.5 No Retry Logic for Transient Failures

**Location:** `agentic/tools.py:127`
```python
response = requests.get(url, headers={"Accept": "application/sparql-results+json"}, timeout=15)
response.raise_for_status()
# 🚨 DIRTY SECRET: Network blip = immediate failure, no retry
```

**Impact:**
- Transient network issues fail entire recommendation flow
- 503 errors from overloaded Fuseki are not retried
- User sees "recommendations unavailable" for temporary issues

**Fix:** Add exponential backoff retry:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _query_sparql_with_retry(url: str) -> requests.Response:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response
```

---

### 4.6 Magic Strings Everywhere

**Examples:**
- `"http://localhost:3030/srs4autism/query"` - Hardcoded in 7+ files
- `"word-zh-"`, `"word-en-"`, `"grammar-"` - Node ID prefixes scattered throughout
- `"srs-kg:"` - Namespace prefix repeated manually
- `0.85` - Mastery threshold magic number
- `0.75` - Prerequisite threshold magic number

**Impact:**
- Impossible to change without global search-replace
- No single source of truth
- Typos cause silent failures

**Fix:** Create constants file:
```python
# backend/constants.py
KG_ENDPOINT = "http://localhost:3030/srs4autism/query"
KG_NAMESPACE = "http://srs4autism.com/schema/"
NODE_PREFIX_WORD_ZH = "word-zh-"
NODE_PREFIX_WORD_EN = "word-en-"
MASTERY_THRESHOLD = 0.85
PREREQ_THRESHOLD = 0.75
```

---

## 5. REFACTORING PLAN (Pre-Migration)

**Priority: Address before migrating to Oxigraph**

### Phase 1: Error Handling (1-2 days)
1. Replace exception swallowing with proper error types
2. Add Result/Either pattern for fallible operations
3. Ensure all SPARQL queries validate response structure
4. Add retry logic with exponential backoff

### Phase 2: Transaction Safety (1 day)
1. Wrap multi-step DB operations in single transaction
2. Add rollback testing (simulate failures)
3. Ensure audit logs are atomic with main operation

### Phase 3: Type Safety (2 days)
1. Add Pydantic models for KG responses (not just API)
2. Validate JSON serialization/deserialization
3. Add runtime type checks for metadata fields
4. Replace magic numbers with typed constants

### Phase 4: Abstraction Layer (2-3 days)
1. Create `KnowledgeGraphAdapter` interface
2. Extract all SPARQL queries into query builder class
3. Centralize KG endpoint configuration
4. Add adapter factory pattern

### Phase 5: Testing (3-5 days)
1. Add integration tests for dual-DB operations
2. Test transaction rollback scenarios
3. Test SPARQL query compatibility (Fuseki vs Oxigraph)
4. Load testing with concurrent requests

**Total Pre-Migration Time:** 2-3 weeks

---

## 6. PRODUCTION READINESS CHECKLIST

| Category | Status | Notes |
|----------|--------|-------|
| **Error Handling** | 🟡 PARTIAL | Many swallowed exceptions, needs audit |
| **Transaction Safety** | 🔴 UNSAFE | Split transactions, no rollback testing |
| **Type Safety** | 🟡 PARTIAL | API layer typed, internal logic loose |
| **Monitoring** | 🔴 MISSING | No metrics on query performance, errors |
| **Logging** | 🟡 BASIC | Print statements, no structured logging |
| **Connection Pooling** | 🔴 MISSING | New HTTP connection per SPARQL query |
| **Retry Logic** | 🔴 MISSING | No retries for transient failures |
| **Configuration** | 🟡 PARTIAL | Some env vars, many hardcoded values |
| **Documentation** | 🟡 BASIC | Inline comments, no API docs |
| **Testing** | 🔴 SPARSE | No integration tests for dual-DB ops |

**Overall Grade: C+ (Functional but Brittle)**

---

## 7. RECOMMENDATIONS

### Immediate (Pre-MVP):
1. Add proper error handling (no more swallowing exceptions)
2. Fix transaction boundaries for data integrity
3. Add health checks for Fuseki availability
4. Document the dual-database architecture

### Short-term (Post-MVP, Pre-Scale):
1. Implement KG abstraction layer
2. Add retry logic for all external calls
3. Replace magic strings with constants
4. Add structured logging and metrics

### Long-term (Scale Prep):
1. Migrate to Oxigraph (follow plan in Section 3.3)
2. Add connection pooling for KG queries
3. Implement caching layer for frequent SPARQL queries
4. Move audit logs to separate service/table

---

## 8. CONCLUSION

This is a **classic dual-database monolith** with **tight coupling** to Fuseki. The code works but is **brittle**. Migrating to Oxigraph is **feasible but requires 3-4 weeks** of careful refactoring.

**Key Risks:**
- Exception swallowing masks failures
- No transaction safety for multi-step operations
- Fuseki hardcoded in 70+ files
- No abstraction layer for KG access

**Key Strengths:**
- SQLAlchemy ORM is well-structured
- Audit trail exists (even if not atomic)
- TTL fallback provides resilience
- Service layer separation (partially implemented)

**Final Verdict:** Proceed with MVP, but schedule 1-month technical debt sprint immediately after. Do NOT scale without refactoring the KG layer.

---

**Signed:** Senior Principal Engineer
**Date:** 2026-01-10
