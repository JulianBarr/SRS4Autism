# Agentic RAG Migration Plan

This document tracks the gradual migration from the legacy template-driven
AI workflow to the new Agentic RAG architecture inspired by
"审视这个Agent.md".

## Architecture Overview

The agentic architecture has been refactored to be a **Learning Agent**, not just a card generator.
It solves "what to learn" by:

1. **Synthesizing Cognitive Prior**: Queries mastery vector (Anki), world model (KG), and user profile
2. **Calling Recommender**: Uses the cognitive prior to determine optimal learning content
3. **Generating Learning Plan**: Returns a plan (not just cards) with recommendations

## Phase 1 – Encapsulate (COMPLETE)

- [x] Wrapped existing generation utilities (`ContentGenerator`) in agentic
  tools (`agentic/tools.py`).
- [x] Added a lightweight memory store (`agentic/memory.py`).
- [x] Added a principle store backed by YAML (`agentic/principles.py`).
- [x] Created an agentic planner (`agentic/agent.py`) that consults memory,
  principles, and existing tools before generating content.
- [x] Exposed a new API entry point `/agentic/plan` in FastAPI.

## Phase 1.5 – Learning Agent Refactoring (COMPLETE)

- [x] Refactored `AgenticPlanner` to be a "Cognitive State Synthesis Engine"
- [x] Added `synthesize_cognitive_prior()` method that queries:
  - Mastery vector (from Anki review history via `CuriousMarioRecommender`)
  - World model (knowledge graph via SPARQL)
  - User profile (from memory)
- [x] Integrated recommender system (`CuriousMarioRecommender`) as a tool
- [x] Updated `AgentPlan` to include `cognitive_prior` and `recommendation_plan`
- [x] Made topic optional - agent can determine what to learn
- [x] Updated API to return cognitive state and recommendation plan

## Phase 2 – Introduce Principles

- LlamaIndex will replace the YAML store once the principle corpus
  is indexed. (TODO)

## Phase 3 – Persistent Memory

- The JSON memory backend will be upgraded to a vector database
  (e.g. Chroma/Weaviate) once the interaction volume grows. (TODO)

## Phase 4 – Strangle and Replace

- Existing template utilities will be rewritten as native agentic logic
  once the planning loop is stable. (TODO)

This staged approach keeps the current system running while letting the
agentic architecture grow “around” it.

