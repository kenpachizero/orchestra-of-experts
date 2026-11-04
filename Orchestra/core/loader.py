"""
Orchestra of Experts - Expert Loader

Responsible for loading a single expert into memory, running it,
and then unloading it so the next expert can take its place.

Only one expert should be resident at a time.
"""

from pathlib import Path
from typing import Optional, Any
import time


class ExpertLoader:
    def __init__(self):
        self.current_expert: Optional[str] = None
        self.current_model: Any = None          # Will hold the real model object later
        self.load_count = 0

    def load(self, expert_path: str | Path) -> bool:
        """
        Load the expert located at expert_path.

        Returns True if loading succeeded (or was a no-op because already loaded).
        """
        expert_path = Path(expert_path)

        if not expert_path.exists():
            print(f"[Loader] ERROR: Path does not exist → {expert_path}")
            return False

        # If the same expert is already loaded, do nothing
        if self.current_expert == str(expert_path):
            print(f"[Loader] Expert already loaded: {expert_path.name}")
            return True

        # Unload whatever is currently resident
        if self.current_expert is not None:
            self.unload()

        print(f"[Loader] Loading expert: {expert_path}")
        start = time.perf_counter()

        # ---------------------------------------------------------------
        # TODO: Real loading logic goes here later
        #
        # Examples of what this will become:
        #   - Load a GGUF with llama-cpp-python / llama.cpp
        #   - Load a full model with transformers / vLLM / Ollama API
        #   - Load a LoRA adapter on top of a shared base
        #
        # For now we just simulate the load.
        # ---------------------------------------------------------------
        time.sleep(0.3)          # pretend it takes a moment
        self.current_model = {"stub": True, "path": str(expert_path)}
        self.current_expert = str(expert_path)
        self.load_count += 1

        elapsed = time.perf_counter() - start
        print(f"[Loader] Loaded in {elapsed:.2f}s  (total loads this session: {self.load_count})")
        return True

    def unload(self) -> None:
        """Unload the currently resident expert and free resources."""
        if self.current_expert is None:
            return

        print(f"[Loader] Unloading expert: {Path(self.current_expert).name}")

        # ---------------------------------------------------------------
        # TODO: Real unload / cleanup logic goes here
        #   - Delete model object
        #   - Clear CUDA cache if using GPU
        #   - Close any file handles / llama.cpp contexts
        # ---------------------------------------------------------------

        self.current_model = None
        self.current_expert = None
        print("[Loader] Unloaded.")

    def run(self, instruction: str, **kwargs) -> str:
        """
        Run the currently loaded expert with the given instruction.

        Returns the expert's output as a string.
        """
        if self.current_model is None:
            return "[Loader] ERROR: No expert is currently loaded."

        print(f"[Loader] Running expert with instruction ({len(instruction)} chars)...")

        # ---------------------------------------------------------------
        # TODO: Real inference call goes here
        #
        # e.g.
        #   output = self.current_model.create_completion(instruction, ...)
        #   or
        #   output = self.current_model.generate(...)
        # ---------------------------------------------------------------

        # Stub response for now
        expert_name = Path(self.current_expert).name if self.current_expert else "unknown"
        return (
            f"[Stub response from expert '{expert_name}']\n"
            f"I received this instruction:\n\n{instruction}\n\n"
            f"(Real model output will appear here once the loader is connected to an inference backend.)"
        )

    def status(self) -> dict:
        """Return a quick status snapshot."""
        return {
            "current_expert": self.current_expert,
            "is_loaded": self.current_model is not None,
            "load_count": self.load_count,
        }
