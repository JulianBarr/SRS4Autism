# Exception Handling Fix: agentic/tools.py

**Date:** 2026-01-10
**Status:** ✅ COMPLETED

---

## Problem Statement

The `agentic/tools.py` file had **exception swallowing** issues where errors were caught and hidden, returning empty results or error dictionaries instead of propagating failures. This caused:

1. **Silent failures** - Callers received empty data and proceeded as if everything was fine
2. **No error visibility** - Exceptions were only printed to console, not logged properly
3. **Ambiguous error states** - Returning `{"error": "..."}` dicts that callers might not check
4. **Difficult debugging** - Root cause of failures was lost

---

## Changes Made

### 1. Added Custom Exception Hierarchy

Created specific exception types for different failure modes:

```python
class AgentToolsError(Exception):
    """Base exception for AgentTools errors"""

class MasteryVectorError(AgentToolsError):
    """Raised when mastery vector query fails"""

class MasteryVectorTimeoutError(MasteryVectorError):
    """Raised when mastery vector query times out"""

class KnowledgeGraphError(AgentToolsError):
    """Raised when knowledge graph query fails"""

class KnowledgeGraphTimeoutError(KnowledgeGraphError):
    """Raised when knowledge graph query times out"""

class RecommenderError(AgentToolsError):
    """Raised when recommender fails"""

class RecommenderTimeoutError(RecommenderError):
    """Raised when recommender times out"""
```

**Benefits:**
- Callers can catch specific exception types
- Clear distinction between timeout vs other failures
- Maintains exception chain with `from e` clause

---

### 2. Fixed `query_mastery_vector()` - Lines 89-122

**Before:**
```python
def query_mastery_vector(self, user_id: str) -> Dict[str, float]:
    try:
        # ... query logic ...
        return mastery_vector
    except FutureTimeoutError:
        print("⚠️  timed out, returning empty vector")
        return {}  # 🚨 SWALLOWED EXCEPTION
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return {}  # 🚨 SWALLOWED EXCEPTION
```

**After:**
```python
def query_mastery_vector(self, user_id: str) -> Dict[str, float]:
    """
    ...
    Raises:
        MasteryVectorTimeoutError: If query takes longer than 30 seconds
        MasteryVectorError: If query fails for any other reason
    """
    try:
        # ... query logic ...
        logger.info(f"Successfully retrieved mastery vector with {len(mastery_vector)} nodes")
        return mastery_vector
    except FutureTimeoutError as e:
        logger.error(f"Mastery vector query timed out after 30 seconds for user {user_id}")
        raise MasteryVectorTimeoutError(
            f"Mastery vector query timed out after 30 seconds for user {user_id}"
        ) from e
    except MasteryVectorTimeoutError:
        raise  # Re-raise timeout errors as-is
    except Exception as e:
        logger.error(f"Failed to query mastery vector for user {user_id}: {e}", exc_info=True)
        raise MasteryVectorError(
            f"Failed to query mastery vector for user {user_id}: {str(e)}"
        ) from e
```

**Key Improvements:**
- ✅ Exceptions propagate instead of being swallowed
- ✅ Structured logging with context (user_id, node count)
- ✅ Specific exception types for different failure modes
- ✅ Maintains exception chain for debugging

---

### 3. Fixed `query_world_model()` - Lines 124-207

**Before:**
```python
def query_world_model(...) -> Dict[str, Any]:
    try:
        # ... SPARQL query ...
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "timeout", "data": {}}  # 🚨 SWALLOWED
    except Exception as e:
        return {"error": str(e), "data": {}}     # 🚨 SWALLOWED
```

**After:**
```python
def query_world_model(...) -> Dict[str, Any]:
    """
    ...
    Raises:
        KnowledgeGraphTimeoutError: If query takes longer than 15 seconds
        KnowledgeGraphError: If query fails for any other reason
    """
    try:
        # ... SPARQL query ...
        logger.info(f"Successfully queried KG (endpoint: {self._kg_endpoint})")
        return result
    except requests.exceptions.Timeout as e:
        logger.error(f"Knowledge graph query timed out after 15 seconds")
        raise KnowledgeGraphTimeoutError(
            f"Knowledge graph query timed out after 15 seconds (endpoint: {self._kg_endpoint})"
        ) from e
    except requests.exceptions.RequestException as e:
        logger.error(f"Knowledge graph request failed: {e}", exc_info=True)
        raise KnowledgeGraphError(
            f"Knowledge graph request failed: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error querying knowledge graph: {e}", exc_info=True)
        raise KnowledgeGraphError(
            f"Unexpected error querying knowledge graph: {str(e)}"
        ) from e
```

**Key Improvements:**
- ✅ No more error dicts - raises proper exceptions
- ✅ Separate handling for timeout vs network vs unexpected errors
- ✅ Full stack traces with `exc_info=True`
- ✅ Endpoint URL included in error messages for debugging

---

### 4. Fixed `call_recommender()` - Lines 217-347

**Before:**
```python
def call_recommender(...) -> Dict[str, Any]:
    try:
        # ... generate recommendations ...
        return {
            "decision": decision,
            ...
        }
    except Exception as e:
        return {                              # 🚨 SWALLOWED
            "error": str(e),
            "decision": "ERROR",
            ...
        }
```

**After:**
```python
def call_recommender(...) -> Dict[str, Any]:
    """
    ...
    Raises:
        RecommenderTimeoutError: If recommender takes longer than 60 seconds
        RecommenderError: If recommender fails for any other reason

    Note:
        On timeout, returns a safe fallback with decision="REVIEW" to allow graceful degradation.
        Other errors will raise exceptions to signal true failures.
    """
    try:
        # ... generate recommendations ...
        except FutureTimeoutError as e:
            logger.warning(f"Recommender timed out, returning fallback")
            return {
                "decision": "REVIEW",
                "plan_title": "Unable to generate recommendations (timeout)",
                ...
                "timeout": True,  # Flag to indicate this is a timeout fallback
            }
        # ... build response ...
        logger.info(f"Successfully generated recommendations: {decision} with {len(recommendations)} items")
        return result
    except Exception as e:
        logger.error(f"Failed to generate recommendations for user {user_id}: {e}", exc_info=True)
        raise RecommenderError(
            f"Failed to generate recommendations for user {user_id}: {str(e)}"
        ) from e
```

**Key Improvements:**
- ✅ Timeout handled gracefully (returns valid response with `timeout: True` flag)
- ✅ Other exceptions raise `RecommenderError` instead of being swallowed
- ✅ Success logging includes decision type and recommendation count
- ✅ Clear documentation of fallback behavior

---

### 5. Added Structured Logging

**Changes:**
- Imported `logging` module
- Created module-level logger: `logger = logging.getLogger(__name__)`
- Replaced all `print()` statements with proper logging:
  - `logger.info()` - Successful operations
  - `logger.warning()` - Timeout fallbacks
  - `logger.error()` - Failures with full stack traces
  - `logger.debug()` - SPARQL query details

**Benefits:**
- Log levels can be configured externally
- Structured log messages with context
- Stack traces captured for debugging
- Production-ready logging

---

## Migration Guide for Callers

### Before (Old Code):
```python
# Old callers had to check for empty dicts or error keys
tools = AgentTools()
mastery = tools.query_mastery_vector(user_id)
if not mastery:
    # Was this a failure or truly empty?
    pass
```

### After (New Code):
```python
from agentic.tools import (
    AgentTools,
    MasteryVectorError,
    MasteryVectorTimeoutError,
    KnowledgeGraphError,
    RecommenderError
)

tools = AgentTools()

# Option 1: Let exceptions propagate (preferred)
try:
    mastery = tools.query_mastery_vector(user_id)
    # mastery is guaranteed valid here
except MasteryVectorTimeoutError:
    # Handle timeout specifically
    logger.warning("Mastery vector query timed out, using default")
    mastery = {}  # Explicit fallback
except MasteryVectorError as e:
    # Handle other failures
    logger.error(f"Failed to get mastery vector: {e}")
    raise  # Re-raise if can't handle

# Option 2: Catch all AgentTools errors
try:
    kg_data = tools.query_world_model(topic="chinese")
    recommendations = tools.call_recommender(user_id, cognitive_prior)
except AgentToolsError as e:
    # Handle any agent tools error
    logger.error(f"Agent tools error: {e}")
    # Return error response to user
    return {"error": "Service temporarily unavailable"}
```

---

## Testing Checklist

- [x] Syntax validation: `python -m py_compile agentic/tools.py` ✅
- [ ] Unit tests for exception handling
- [ ] Integration tests with Fuseki unavailable
- [ ] Test timeout scenarios
- [ ] Verify logging output in production
- [ ] Update caller code to handle new exceptions

---

## Backward Compatibility

**Breaking Changes:** ⚠️ YES

This is a **breaking change** for any code that:
1. Called these methods and checked for empty dicts
2. Checked for `"error"` keys in response
3. Relied on silent failures

**Migration Required:**
- All callers must add `try/except` blocks
- Or wrap these methods in compatibility shim if needed

---

## Next Steps

### Immediate (Required):
1. ✅ Fix exception swallowing in `agentic/tools.py` - **DONE**
2. [ ] Update all callers to handle new exceptions
3. [ ] Add retry logic (see Section 5 of ENGINEERING_AUDIT.md)
4. [ ] Add unit tests for error paths

### Short-term:
1. [ ] Apply same pattern to other service files
2. [ ] Fix transaction boundaries in `backend/database/services.py`
3. [ ] Add constants file for magic strings

### Long-term:
1. [ ] Implement Result/Either pattern for more functional error handling
2. [ ] Add circuit breaker pattern for external dependencies
3. [ ] Create KG abstraction layer for Oxigraph migration

---

## Related Files

- **ENGINEERING_AUDIT.md** - Full architectural audit report
- **agentic/tools.py** - Fixed file (this PR)
- **backend/services/integrated_recommender_service.py** - Caller, needs update
- **backend/services/chinese_ppr_recommender_service.py** - Indirect caller

---

**Status:** ✅ COMPLETED
**Review:** Ready for code review and testing
**Risk Level:** MEDIUM (breaking change, requires caller updates)
