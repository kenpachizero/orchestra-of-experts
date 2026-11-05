"""
Orchestra of Experts - Router / Conductor

This is the always-resident controller.
It decides which expert to load, runs it, then unloads it.
Only one expert should be active on the GPU at a time.

Also integrates the Memory Palace for long-term recall.
"""

from pathlib import Path
from typing import Optional
import json

from loader import ExpertLoader
from memory import MemoryPalace


class Conductor:
    def __init__(self, orchestra_root: str | Path = "Orchestra"):
        self.root = Path(orchestra_root)
        self.available_experts = self._scan_experts()
        self.loader = ExpertLoader()
        self.palace = MemoryPalace()

    def _scan_experts(self) -> dict:
        """
        Scan the Orchestra folder structure and build a map of available experts.
        Respects the naming rules for community experts.
        """
        experts = {}

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

        code_root = self.root / "Code"
        if code_root.exists():
            for lang_dir in code_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                lang = lang_dir.name
                for expert_dir in lang_dir.iterdir():
                    if not expert_dir.is_dir():
                        continue
                    folder_name = expert_dir.name
                    if folder_name == "default" or lang.lower() in folder_name.lower():
                        key = f"Code/{lang}/{folder_name}"
                        experts[key] = {
                            "path": expert_dir,
                            "type": "code",
                            "language": lang,
                            "default": folder_name == "default"
                        }

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
        return sorted(self.available_experts.keys())

    def decide(self, user_message: str, history: Optional[list] = None) -> dict:
        """
        Main decision logic (rule-based for now).
        """
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

        return {
            "action": "call_expert",
            "expert_path": "General",
            "instruction": user_message,
            "reason": "No specialised expert matched – using General"
        }

    def run(self, user_message: str, auto_remember: bool = False) -> str:
        """
        High-level entry point.
        1. Recall relevant memories from the Palace
        2. Decide which expert to use
        3. Load the expert
        4. Run the expert (with memory context injected)
        5. Optionally store the exchange
        6. Return result
        """
        # --- Memory recall ---
        memory_block = self.palace.recall_for_prompt(user_message, limit=3)
        if memory_block:
            print("[Conductor] Recalled relevant memories from the Palace.")
            enriched_instruction = (
                f"{memory_block}\n\n"
                f"---\n\n"
                f"Current user request:\n{user_message}"
            )
        else:
            enriched_instruction = user_message

        decision = self.decide(user_message)

        # Use the memory-enriched instruction for the expert
        if decision["action"] == "call_expert":
            decision["instruction"] = enriched_instruction

        print("[Conductor] Decision:")
        print(json.dumps({k: v for k, v in decision.items() if k != "instruction"}, indent=2))
        if memory_block:
            print("[Conductor] (Memory context injected into instruction)")

        if decision["action"] == "final_answer":
            return decision.get("answer", "No answer generated.")

        if decision["action"] == "call_expert":
            expert_key = decision["expert_path"]

            if expert_key not in self.available_experts:
                return f"[Conductor] ERROR: Expert '{expert_key}' not found in available experts."

            expert_info = self.available_experts[expert_key]
            expert_path = expert_info["path"]

            success = self.loader.load(expert_path)
            if not success:
                return f"[Conductor] Failed to load expert: {expert_key}"

            output = self.loader.run(decision["instruction"])

            # Optional auto-remember of the exchange
            if auto_remember and output and not output.startswith("[Loader] ERROR"):
                summary = (
                    f"User: {user_message}\n"
                    f"Expert ({expert_key}): {output[:500]}"
                )
                self.palace.remember(
                    content=summary,
                    wing="conversations",
                    room=expert_key.replace("/", "_"),
                    tags=["auto", expert_key],
                )

            return output

        return "[Conductor] Unknown action."


if __name__ == "__main__":
    conductor = Conductor()
    print("Available experts:")
    for e in conductor.list_experts():
        print(f"  - {e}")

    print("\n--- Test ---")
    result = conductor.run("Write a Python function that calculates factorial")
    print(result)
