from typing import Dict, Any, Union

class StateService:
    def __init__(self):
        self.personal_state: Dict[str, Any] = {"frustration": 0.0, "mastery": {}}
        self.world_state: Dict[str, Any] = {"consecutive_errors": 0, "current_topic": "General"}

    def update_state(self, category: str, key: str, value: Any) -> None:
        """
        Update the state for a given category and key.
        
        Args:
            category (str): The category of state ("personal" or "world").
            key (str): The key to update.
            value (Any): The new value.
        """
        if category == "personal":
            self.personal_state[key] = value
        elif category == "world":
            self.world_state[key] = value
        else:
            raise ValueError(f"Unknown category: {category}. Must be 'personal' or 'world'.")

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Returns a flattened dictionary for the rule engine.
        Merges personal and world state into one dict.
        """
        # Create a snapshot by merging dictionaries
        # Using ** unpacking to merge, prioritizing world_state keys if duplicates exist (though unlikely given the design)
        # Or just merge them into a new dict.
        # The prompt implies a flat structure for access like "state.frustration" in the condition.
        # However, the condition in YAML is "state.frustration", which implies `state` is the object/dict passed to simpleeval.
        # Wait, the prompt says: `simpleeval.simple_eval(condition, names={"state": state_snapshot})`
        # This means `state_snapshot` itself should be the object that has attributes or keys accessible via dot notation or dictionary access.
        # SimpleEval supports attribute access on objects or dictionary access if names is a dict.
        # If I pass `names={"state": state_snapshot}`, then inside the expression `state.frustration` works if `state_snapshot` is an object with `frustration` attribute, OR if simpleeval is configured to access dict keys with dot notation (which it isn't by default without custom logic or if `state` is a dict and we use `state['frustration']`).
        # BUT, the prompt's YAML says `state.frustration`.
        # The prompt says `get_snapshot()` returns a "flattened dictionary".
        # If `state` is a dict `{'frustration': 0.7}`, then `state.frustration` in simpleeval expression might fail unless I wrap it in a class or use a specific simpleeval configuration.
        # However, standard python `eval` or `simpleeval` on a dict `d` doesn't allow `d.key`. It allows `d['key']`.
        # The user's prompt specifically uses `state.frustration`.
        # This implies `state_snapshot` should probably be an object (like a SimpleNamespace or a custom class) OR the user is assuming dot notation works on dicts in simpleeval (which is not standard).
        # Let's look at `simpleeval` documentation or common usage. `simpleeval` allows defining functions and names.
        # If the user insists on `state.frustration` syntax in the YAML, I should probably return a `SimpleNamespace` or similar object from `get_snapshot` or convert the dict to one before passing to `simpleeval`, OR the user might be mistaken about syntax.
        # However, the prompt says "Returns a flattened dictionary".
        # If I return a dict, `state.frustration` will raise an AttributeError in standard Python.
        # I will implement `get_snapshot` to return a dict as requested.
        # I will handle the object conversion in `PolicyEngine` or use a dict wrapper that supports dot access, or just `SimpleNamespace`.
        # "Returns a flattened dictionary" - strict instruction.
        # I will follow "Returns a flattened dictionary".
        
        snapshot = {**self.personal_state, **self.world_state}
        return snapshot
