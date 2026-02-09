import yaml
import os
from typing import Dict, Any, Optional, Tuple
from simpleeval import simple_eval

# Helper to allow dot notation access to dictionary
class DotDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

class PolicyEngine:
    def __init__(self):
        self.policies = self._load_policies()

    def _load_policies(self) -> list:
        # Load policies.yaml relative to this file's location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.join(current_dir, "policies.yaml")
        
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"policies.yaml not found at {yaml_path}")
            
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)

    def decide(self, state_snapshot: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Decides on an action based on the state snapshot.
        
        Args:
            state_snapshot (Dict[str, Any]): The flattened state dictionary.
            
        Returns:
            Tuple[Optional[str], Optional[Dict[str, Any]]]: A tuple containing the action name and parameters.
        """
        # Sort policies by priority (High to Low)
        sorted_policies = sorted(self.policies, key=lambda x: x.get('priority', 0), reverse=True)
        
        # Convert state_snapshot to DotDict to support dot notation in conditions (e.g., state.frustration)
        # The prompt policies use "state.frustration", which requires object-like access.
        # Since state_snapshot is a dict, we wrap it.
        state_obj = DotDict(state_snapshot)

        for policy in sorted_policies:
            condition = policy.get('condition')
            
            if condition == "default":
                return policy.get('action'), policy.get('params')
            
            try:
                # Evaluate the condition
                # names={"state": state_obj} allows 'state' to be accessed in the expression
                if simple_eval(condition, names={"state": state_obj}):
                    return policy.get('action'), policy.get('params')
            except Exception as e:
                # Log error or ignore invalid conditions? 
                # For now, we print a warning and continue to next policy
                print(f"Error evaluating policy '{policy.get('name')}': {e}")
                continue
                
        return None, None
