# Minimal Test Guide for Refactored Agentic Architecture

## Quick Test Options

### Option 1: API Test (Easiest - Recommended)

**Prerequisites:**
1. Backend server must be running
2. Anki and Knowledge Graph services are optional (agent handles gracefully)

**Steps:**

1. Start the backend server:
   ```bash
   cd backend
   python run.py
   ```

2. In another terminal, run the API test:
   ```bash
   chmod +x test_agentic_api.sh
   ./test_agentic_api.sh
   ```

   Or manually test with curl:
   ```bash
   curl -X POST "http://localhost:8000/agentic/plan" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "test_user_001",
       "topic": null
     }' | python3 -m json.tool
   ```

**Expected Response:**
```json
{
  "learner_level": "novice",
  "topic": "...",
  "topic_complexity": "...",
  "scaffold_type": "...",
  "rationale": "Analyzed cognitive state: ...",
  "cognitive_prior": {
    "mastery_summary": {
      "total_nodes": 0,
      "mastered_nodes": 0,
      "weak_nodes": 0,
      "unlearned_nodes": 0
    },
    "total_nodes": 0
  },
  "recommendation_plan": {
    "decision": "EXPLORATORY" | "REMEDIATE" | "REVIEW" | "ERROR",
    "plan_title": "...",
    "learning_task": "...",
    "recommendations": [...]
  },
  "cards": null
}
```

### Option 2: Python Test Script

**Prerequisites:**
- Python environment with dependencies installed
- May need virtual environment activated

**Steps:**

```bash
# Activate virtual environment if you have one
source venv/bin/activate  # or your venv path

# Run the test
python3 test_agentic_minimal.py
```

**Note:** This test may fail if dependencies aren't properly set up. The API test is more reliable.

### Option 3: Manual Python Test (Simplest)

Create a simple test file `quick_test.py`:

```python
import sys
sys.path.insert(0, '.')

from agentic import AgenticPlanner

# Create agent
planner = AgenticPlanner()

# Test cognitive prior synthesis
user_id = "test_001"
prior = planner.synthesize_cognitive_prior(user_id)
print("Cognitive Prior:", prior)

# Test learning plan
plan = planner.plan_learning_step(user_id=user_id, topic=None)
print("\nLearning Plan:")
print(f"  Topic: {plan.topic}")
print(f"  Rationale: {plan.rationale}")
print(f"  Decision: {plan.recommendation_plan.get('decision') if plan.recommendation_plan else 'N/A'}")
```

## What to Verify

✅ **Agent can be instantiated**
- No import errors
- Components (memory, principles, tools) are initialized

✅ **Cognitive prior synthesis works**
- Returns a dictionary with:
  - `mastery_vector`: Dict of node IDs to mastery scores
  - `kg_context`: Knowledge graph query results
  - `profile`: User profile from memory
  - `mastery_summary`: Summary statistics

✅ **Learning plan generation works**
- Returns an `AgentPlan` with:
  - `rationale`: Explanation of the decision
  - `cognitive_prior`: The synthesized state
  - `recommendation_plan`: Output from recommender
  - `cards_payload`: Generated cards (if any)

✅ **Recommender integration works**
- `recommendation_plan` contains:
  - `decision`: "EXPLORATORY", "REMEDIATE", or "REVIEW"
  - `plan_title`: Human-readable plan name
  - `recommendations`: List of recommended learning nodes

## Troubleshooting

**If Anki is not available:**
- Agent should return empty mastery vector
- Recommender may return "ERROR" decision
- This is expected and handled gracefully

**If Knowledge Graph is not available:**
- Agent should return error in `kg_context`
- This is expected and handled gracefully

**If recommender fails:**
- Agent should still return a plan with "ERROR" decision
- Check that `curious_mario_recommender.py` is accessible

## Success Criteria

The minimal test passes if:
1. ✅ Agent can be instantiated without errors
2. ✅ `synthesize_cognitive_prior()` returns a valid dictionary
3. ✅ `plan_learning_step()` returns an `AgentPlan` object
4. ✅ The plan includes `cognitive_prior` and `recommendation_plan` fields
5. ✅ The rationale explains the decision

Even if external services (Anki, KG) aren't available, the agent should handle it gracefully and still return a valid plan structure.

