import sys
import os

# Ensure the parent directory is in the python path to allow imports
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from state_service import StateService
from policy_engine import PolicyEngine

def test_brain():
    print("Initializing Brain Components...")
    state_service = StateService()
    policy_engine = PolicyEngine()

    # Scenario A: High Frustration
    print("\n--- Scenario A: High Frustration ---")
    # Reset state to clean slate
    state_service = StateService() # Re-init for clean state or use update
    state_service.update_state("personal", "frustration", 0.8)
    
    snapshot_a = state_service.get_snapshot()
    action_a, params_a = policy_engine.decide(snapshot_a)
    
    print(f"State: {snapshot_a}")
    print(f"Action: {action_a}, Params: {params_a}")
    
    assert action_a == "switch_topic", f"Expected 'switch_topic', got '{action_a}'"
    assert params_a['target'] == "interests", f"Expected target 'interests', got '{params_a.get('target')}'"

    # Scenario B: High Errors (Low Frustration)
    print("\n--- Scenario B: High Errors ---")
    # Reset relevant fields
    state_service.update_state("personal", "frustration", 0.0)
    state_service.update_state("world", "consecutive_errors", 2)
    
    snapshot_b = state_service.get_snapshot()
    action_b, params_b = policy_engine.decide(snapshot_b)
    
    print(f"State: {snapshot_b}")
    print(f"Action: {action_b}, Params: {params_b}")
    
    assert action_b == "adjust_difficulty", f"Expected 'adjust_difficulty', got '{action_b}'"
    assert params_b['mode'] == "scaffolded", f"Expected mode 'scaffolded', got '{params_b.get('mode')}'"

    # Scenario C: Flow State
    print("\n--- Scenario C: Flow State ---")
    state_service.update_state("personal", "frustration", 0.0)
    state_service.update_state("world", "consecutive_errors", 0)
    
    snapshot_c = state_service.get_snapshot()
    action_c, params_c = policy_engine.decide(snapshot_c)
    
    print(f"State: {snapshot_c}")
    print(f"Action: {action_c}, Params: {params_c}")
    
    assert action_c == "continue_curriculum", f"Expected 'continue_curriculum', got '{action_c}'"
    assert params_c['difficulty'] == "adaptive", f"Expected difficulty 'adaptive', got '{params_c.get('difficulty')}'"

    # Scenario D: Abstract Word Workflow
    print("\n--- Scenario D: Abstract Word Workflow ---")
    state_service.update_state("world", "is_abstract", True)
    state_service.update_state("world", "current_topic", "Freedom")
    
    snapshot_d = state_service.get_snapshot()
    action_d, params_d = policy_engine.decide(snapshot_d)
    
    print(f"State: {snapshot_d}")
    print(f"Action: {action_d}, Params: {params_d}")
    
    assert action_d == "run_workflow", f"Expected 'run_workflow', got '{action_d}'"
    assert params_d['type'] == "producer_critic", f"Expected type 'producer_critic', got '{params_d.get('type')}'"

    print("\n✅ BRAIN TESTS PASSED")

if __name__ == "__main__":
    try:
        test_brain()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        sys.exit(1)
