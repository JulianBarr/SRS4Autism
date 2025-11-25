#!/usr/bin/env python3
"""
Minimal test for the refactored agentic architecture.

This test verifies:
1. Agent can be instantiated
2. Agent can synthesize cognitive prior
3. Agent can plan a learning step
4. Agent returns a valid learning plan

Run with: python test_agentic_minimal.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agentic import AgenticPlanner, AgentMemory, PrincipleStore, AgentTools


def test_agent_instantiation():
    """Test that the agent can be instantiated."""
    print("=" * 60)
    print("Test 1: Agent Instantiation")
    print("=" * 60)
    
    try:
        planner = AgenticPlanner()
        print("✅ Agent instantiated successfully")
        print(f"   - Memory: {type(planner.memory).__name__}")
        print(f"   - Principles: {type(planner.principles).__name__}")
        print(f"   - Tools: {type(planner.tools).__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed to instantiate agent: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cognitive_prior_synthesis():
    """Test that the agent can synthesize a cognitive prior."""
    print("\n" + "=" * 60)
    print("Test 2: Cognitive Prior Synthesis")
    print("=" * 60)
    
    try:
        planner = AgenticPlanner()
        user_id = "test_user_001"
        
        # Create a test profile in memory
        planner.memory.update_profile(user_id, {
            "name": "Test Child",
            "level": "intermediate",
            "age": 8,
        })
        
        print(f"   Querying cognitive state for user: {user_id}")
        cognitive_prior = planner.synthesize_cognitive_prior(user_id)
        
        print("✅ Cognitive prior synthesized")
        print(f"   - Mastery vector entries: {len(cognitive_prior.get('mastery_vector', {}))}")
        print(f"   - KG context keys: {list(cognitive_prior.get('kg_context', {}).keys())}")
        print(f"   - Profile name: {cognitive_prior.get('profile', {}).get('name', 'N/A')}")
        
        mastery_summary = cognitive_prior.get('mastery_summary', {})
        print(f"   - Mastery summary:")
        print(f"     * Total nodes: {mastery_summary.get('total_nodes', 0)}")
        print(f"     * Mastered: {mastery_summary.get('mastered_nodes', 0)}")
        print(f"     * Weak: {mastery_summary.get('weak_nodes', 0)}")
        print(f"     * Unlearned: {mastery_summary.get('unlearned_nodes', 0)}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to synthesize cognitive prior: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_learning_plan():
    """Test that the agent can create a learning plan."""
    print("\n" + "=" * 60)
    print("Test 3: Learning Plan Generation")
    print("=" * 60)
    
    try:
        planner = AgenticPlanner()
        user_id = "test_user_001"
        
        # Ensure profile exists
        planner.memory.update_profile(user_id, {
            "name": "Test Child",
            "level": "intermediate",
        })
        
        print(f"   Planning learning step for user: {user_id}")
        print("   (Topic is optional - agent will determine what to learn)")
        
        plan = planner.plan_learning_step(
            user_id=user_id,
            topic=None,  # Let agent determine
        )
        
        print("✅ Learning plan generated")
        print(f"   - Learner level: {plan.learner_level}")
        print(f"   - Topic: {plan.topic or 'Determined by recommender'}")
        print(f"   - Complexity: {plan.topic_complexity}")
        print(f"   - Scaffold type: {plan.scaffold_type or 'N/A'}")
        print(f"   - Rationale: {plan.rationale[:100]}...")
        
        if plan.recommendation_plan:
            rec_plan = plan.recommendation_plan
            print(f"   - Recommendation decision: {rec_plan.get('decision', 'N/A')}")
            print(f"   - Plan title: {rec_plan.get('plan_title', 'N/A')}")
            print(f"   - Learning task: {rec_plan.get('learning_task', 'N/A')}")
            print(f"   - Recommendations count: {len(rec_plan.get('recommendations', []))}")
        
        if plan.cards_payload:
            cards = plan.cards_payload.get('cards', [])
            print(f"   - Cards generated: {len(cards)}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to generate learning plan: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_topic():
    """Test planning with a specific topic."""
    print("\n" + "=" * 60)
    print("Test 4: Learning Plan with Specific Topic")
    print("=" * 60)
    
    try:
        planner = AgenticPlanner()
        user_id = "test_user_002"
        
        planner.memory.update_profile(user_id, {
            "name": "Test Child 2",
            "level": "novice",
        })
        
        print(f"   Planning learning step for topic: 'colors'")
        plan = planner.plan_learning_step(
            user_id=user_id,
            topic="colors",
            learner_level="novice",
        )
        
        print("✅ Learning plan with topic generated")
        print(f"   - Topic: {plan.topic}")
        print(f"   - Decision: {plan.recommendation_plan.get('decision') if plan.recommendation_plan else 'N/A'}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to generate plan with topic: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MINIMAL TEST: Refactored Agentic Architecture")
    print("=" * 60)
    print("\nThis test verifies the core functionality of the learning agent.")
    print("Note: Some tests may show warnings if Anki/KG services aren't available.")
    print("This is expected - the agent should handle missing services gracefully.\n")
    
    results = []
    results.append(("Agent Instantiation", test_agent_instantiation()))
    results.append(("Cognitive Prior Synthesis", test_cognitive_prior_synthesis()))
    results.append(("Learning Plan Generation", test_learning_plan()))
    results.append(("Plan with Topic", test_with_topic()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The agentic architecture is working.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

