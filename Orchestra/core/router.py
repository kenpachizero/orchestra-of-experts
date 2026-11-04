"""
Orchestra of Experts - Router / Conductor

This is the always-resident controller.
It decides which expert to load, runs it, then unloads it.
Only one expert should be active on the GPU at a time.
"""

from pathlib import Path
from typing import Optional
import json


class Conductor:
    def __init__(self, orchestra_root: str | Path = "Orchestra"):
        self.root = Path(orchestra_root)
        self.available_experts = self._scan_experts()

    def _scan_experts(self) -> dict:
        """
        Scan the Orchestra folder structure and build a map of available experts.
        Respects the naming rules for community experts.
        """
        experts = {}

        # Top-level categories that are themselves experts
        top_level = [
            "Conductor", "Decision", "General", "Maths",
            "Reasoning", "Research", "Judge", "Critic"
        ]

        for name in top_level:
            path = self.root / name
            if path.exists():
                experts[name] = {
                    "path": path,
                    "type": "top_level",
                    "default": True
                }

        # Code sub-categories
        code_root = self.root / "Code"
        if code_root.exists():
            for lang_dir in code_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                lang = lang_dir.name
                # Look for default + valid community experts
                for expert_dir in lang_dir.iterdir():
                    if not expert_dir.is_dir():
                        continue
                    folder_name = expert_dir.name
                    # Naming rule: must be "default" or contain the language name
                    if folder_name == "default" or lang.lower() in folder_name.lower():
                        key = f"Code/{lang}/{folder_name}"
                        experts[key] = {
                            "path": expert_dir,
                            "type": "code",
                            "language": lang,
                            "default": folder_name == "default"
                        }

        # Literature sub-categories
        lit_root = self.root / "Literature"
        if lit_root.exists():
            for style_dir in lit_root.iterdir():
                if style_dir.is_dir():
                    key = f"Literature/{style_dir.name}"
                    experts[key] = {
                        "path": style_dir,
                        "type": "literature",
                        "default": True
                    }

        return experts

    def list_experts(self) -> list[str]:
        """Return a sorted list of all available expert keys."""
        return sorted(self.available_experts.keys())

    def decide(self, user_message: str, history: Optional[list] = None) -> dict:
        """
        Main decision logic.

        Returns a structured action, for example:

        {
            "action": "call_expert",
            "expert_path": "Code/Python/default",
            "instruction": "Write a clean function that...",
            "reason": "User asked for Python code"
        }

        or

        {
            "action": "final_answer",
            "answer": "..."
        }
        """
        # TODO: Replace this with real model inference (small Conductor model)
        # For now this is a simple rule-based stub so the structure is clear.

        msg = user_message.lower()

        if any(word in msg for word in ["python", "py "]):
            return {
                "action": "call_expert",
                "expert_path": "Code/Python/default",
                "instruction": user_message,
                "reason": "Detected Python-related request"
            }

        if any(word in msg for word in ["javascript", "js ", "typescript", "ts "]):
            return {
                "action": "call_expert",
                "expert_path": "Code/JavaScript/default",
                "instruction": user_message,
                "reason": "Detected JavaScript-related request"
            }

        if "php" in msg:
            return {
                "action": "call_expert",
                "expert_path": "Code/PHP/default",
                "instruction": user_message,
                "reason": "Detected PHP-related request"
            }

        if any(word in msg for word in ["math", "calculate", "equation", "algebra"]):
            return {
                "action": "call_expert",
                "expert_path": "Maths",
                "instruction": user_message,
                "reason": "Detected maths-related request"
            }

        # Fallback
        return {
            "action": "call_expert",
            "expert_path": "General",
            "instruction": user_message,
            "reason": "No specialised expert matched – using General"
        }

    def run(self, user_message: str) -> str:
        """
        High-level entry point.
        1. Decide which expert to use
        2. (Future) Load expert
        3. (Future) Run expert
        4. (Future) Unload expert
        5. Return result
        """
        decision = self.decide(user_message)

        print("[Conductor] Decision:")
        print(json.dumps(decision, indent=2))

        # Placeholder – real loading/running will go here later
        if decision["action"] == "call_expert":
            expert = decision["expert_path"]
            return f"[Stub] Would now load and run expert: {expert}\nInstruction: {decision['instruction']}"

        return decision.get("answer", "No answer generated.")


if __name__ == "__main__":
    conductor = Conductor()
    print("Available experts:")
    for e in conductor.list_experts():
        print(f"  - {e}")

    print("\n--- Test ---")
    result = conductor.run("Write a Python function that calculates factorial")
    print(result)
