# Cognition (认知) Module - Code Placement

**Parallel to:** Language (语言) module  
**Purpose:** ECTA Quest platform for autism early intervention – cognition/teaching tasks.

## Current Language Module Structure

| Layer | Location | Example |
|-------|----------|---------|
| **UI Component** | `frontend/src/components/` | `LanguageContentManager.js` |
| **Backend Router** | `backend/app/routers/` | `kg.py` (grammar, PPR recommendations) |
| **Backend Services** | `backend/services/` | `ppr_recommender_service.py`, `chinese_ppr_recommender_service.py` |
| **Content** | `content/` | `01-chinese/`, `02-english/` |
| **KG Schema** | `backend/schema/` | `constants.py` (srs-kg) |
| **Ontology** | `knowledge_graph/ontology/` | `srs_schema.ttl`, `SCHEMA_VISUALIZATION.md` |

## Cognition Module – Idiomatic Placement

| Layer | Location | Naming |
|-------|----------|--------|
| **UI Component** | `frontend/src/components/` | `CognitionContentManager.js` or `CognitionQuestManager.js` |
| **Frontend Services** | `frontend/src/services/cognition/` | `cognitionQuestService.ts` (mock) |
| **Frontend Types** | `frontend/src/types/cognition/` | `graphConstants.ts`, `questPayload.ts` |
| **Backend Router** | `backend/app/routers/` | `cognition.py` |
| **Backend Services** | `backend/services/` | `cognition_quest_service.py` |
| **Content** | `content/` | `05-cognition/` (new; follows 01–04 numbering) |
| **KG Schema** | `frontend/src/types/cognition/` | `graphConstants.ts` (ecta-kg) |
| **Ontology** | `knowledge_graph/ontology/` | `quest.ttl` |

## Naming Convention

- **Component:** `CognitionContentManager` (parallel to `LanguageContentManager`)
- **Service:** `CognitionQuestService` (domain-specific: quests)
- **Types:** `ecta-kg` prefix for graph constants; `QuestPayload` for Document DB
