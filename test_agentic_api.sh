#!/bin/bash
# Minimal API test for the agentic architecture
# Make sure the backend server is running first!

echo "=" 
echo "MINIMAL API TEST: Agentic Learning Agent"
echo "="
echo ""
echo "This test calls the /agentic/plan endpoint."
echo "Make sure the backend is running: cd backend && python run.py"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Testing POST /agentic/plan (without topic - agent determines what to learn)..."
echo ""

curl -X POST "${BASE_URL}/agentic/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_001",
    "topic": null,
    "learner_level": null,
    "topic_complexity": null
  }' \
  | python3 -m json.tool

echo ""
echo ""
echo "Testing POST /agentic/plan (with topic 'colors')..."
echo ""

curl -X POST "${BASE_URL}/agentic/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_002",
    "topic": "colors",
    "learner_level": "novice",
    "topic_complexity": "medium"
  }' \
  | python3 -m json.tool

echo ""
echo "✅ Test complete!"
echo ""
echo "Expected response includes:"
echo "  - learner_level"
echo "  - topic (may be determined by recommender)"
echo "  - rationale"
echo "  - cognitive_prior (with mastery_summary)"
echo "  - recommendation_plan (with decision, plan_title, recommendations)"
echo "  - cards (if generated)"

