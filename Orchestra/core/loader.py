"""
Orchestra of Experts - Expert Loader

Responsible for loading a single expert into memory, running it,
and then unloading it so the next expert can take its place.

Only one expert should be resident at a time.

Backend: llama-cpp-python (GGUF)
"""

from pathlib import Path
from typing import Optional, Any
import time
import gc

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None  # type: ignore


# Default system prompts by expert type / category
SYSTEM_PROMPTS = {
    "General": (
        "You are a helpful, capable general-purpose assistant. "
        "Answer clearly and accurately. If you are unsure, say so."
    ),
    "Maths": (
        "You are a precise mathematics expert. "
        "Show your reasoning step by step. Prefer exact answers when possible."
    ),
    "Code": (
        "You are an expert software engineer. "
        "Write clean, correct, well-structured code. "
        "Explain non-obvious parts briefly. Prefer modern best practices."
    ),
    "Literature": (
        "You are a skilled writer and literature expert. "
        "Write with clarity, style, and appropriate tone for the request."
    ),
    "Reasoning": (
        "You are a careful reasoning expert. "
        "Think step by step. Examine assumptions. Reach well-supported conclusions."
    ),
    "Research": (
        "You are a thorough research assistant. "
        "Be accurate, cite reasoning, and distinguish facts from speculation."
    ),
    "Judge": (
        "You are an impartial judge. "
        "Compare answers fairly, list strengths and weaknesses, and pick the best one with clear reasons."
    ),
    "default": (
        "You are a helpful expert assistant. "
        "Be clear, accurate, and concise."
    ),
}


class ExpertLoader:
    def __init__(
        self,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,      # -1 = offload as many layers as possible to GPU
        n_threads: int | None = None,
        verbose: bool = False,
    ):
        self.current_expert: Optional[str] = None
        self.current_model: Any = None
        self.current_gguf: Optional[Path] = None
        self.current_category: str = "default"
        self.load_count = 0

        # Inference defaults
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.verbose = verbose

    def _find_gguf(self, expert_path: Path) -> Optional[Path]:
        """
        Find a GGUF file inside the expert folder.

        Preference order:
        1. Exact name 'model.gguf'
        2. Any file ending in .gguf (first one found)
        """
        if not expert_path.is_dir():
            return None

        preferred = expert_path / "model.gguf"
        if preferred.exists():
            return preferred

        ggufs = sorted(expert_path.glob("*.gguf"))
        if ggufs:
            return ggufs[0]

        return None

    def _detect_category(self, expert_path: Path) -> str:
        """Infer a high-level category from the path for system prompt selection."""
        parts = [p.lower() for p in expert_path.parts]

        if "code" in parts:
            return "Code"
        if "maths" in parts or "math" in parts:
            return "Maths"
        if "literature" in parts:
            return "Literature"
        if "reasoning" in parts:
            return "Reasoning"
        if "research" in parts:
            return "Research"
        if "judge" in parts:
            return "Judge"
        if "general" in parts:
            return "General"

        return "default"

    def load(self, expert_path: str | Path) -> bool:
        """
        Load the expert located at expert_path.

        Returns True if loading succeeded (or was a no-op because already loaded).
        """
        expert_path = Path(expert_path)

        if not expert_path.exists():
            print(f"[Loader] ERROR: Path does not exist → {expert_path}")
            return False

        # Already loaded?
        if self.current_expert == str(expert_path) and self.current_model is not None:
            print(f"[Loader] Expert already loaded: {expert_path.name}")
            return True

        # Unload previous expert first
        if self.current_expert is not None:
            self.unload()

        if not LLAMA_CPP_AVAILABLE:
            print("[Loader] ERROR: llama-cpp-python is not installed.")
            print("           Install it with:")
            print("             pip install llama-cpp-python")
            print("           (For GPU support see the llama-cpp-python documentation)")
            return False

        gguf_path = self._find_gguf(expert_path)
        if gguf_path is None:
            print(f"[Loader] ERROR: No .gguf file found in {expert_path}")
            print("           Place a GGUF model in the folder (recommended name: model.gguf)")
            return False

        print(f"[Loader] Loading expert: {expert_path.name}")
        print(f"           GGUF: {gguf_path.name}")
        start = time.perf_counter()

        try:
            self.current_model = Llama(
                model_path=str(gguf_path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                verbose=self.verbose,
            )
            self.current_expert = str(expert_path)
            self.current_gguf = gguf_path
            self.current_category = self._detect_category(expert_path)
            self.load_count += 1

            elapsed = time.perf_counter() - start
            print(f"[Loader] Loaded in {elapsed:.2f}s  (total loads this session: {self.load_count})")
            return True

        except Exception as e:
            print(f"[Loader] ERROR while loading model: {e}")
            self.current_model = None
            self.current_expert = None
            self.current_gguf = None
            self.current_category = "default"
            return False

    def unload(self) -> None:
        """Unload the currently resident expert and free resources."""
        if self.current_expert is None:
            return

        print(f"[Loader] Unloading expert: {Path(self.current_expert).name}")

        self.current_model = None
        self.current_expert = None
        self.current_gguf = None
        self.current_category = "default"
        gc.collect()

        print("[Loader] Unloaded.")

    def _build_prompt(self, instruction: str) -> str:
        """Build a clean chat-style prompt using the expert's system message."""
        system = SYSTEM_PROMPTS.get(self.current_category, SYSTEM_PROMPTS["default"])

        # Simple but effective ChatML-style / Instruct format that works
        # well across many GGUF models (Llama, Qwen, Mistral, etc.)
        prompt = (
            f"System: {system}\n\n"
            f"User: {instruction}\n\n"
            f"Assistant:"
        )
        return prompt

    def run(
        self,
        instruction: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop: list[str] | None = None,
        **kwargs,
    ) -> str:
        """
        Run the currently loaded expert with the given instruction.

        Returns the expert's output as a string.
        """
        if self.current_model is None:
            return "[Loader] ERROR: No expert is currently loaded."

        print(f"[Loader] Running expert ({len(instruction)} chars)...")

        try:
            prompt = self._build_prompt(instruction)

            output = self.current_model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or ["User:", "\nUser:", "System:"],
                echo=False,
            )

            text = output["choices"][0]["text"].strip()
            return text

        except Exception as e:
            return f"[Loader] ERROR during inference: {e}"

    def status(self) -> dict:
        """Return a quick status snapshot."""
        return {
            "current_expert": self.current_expert,
            "current_gguf": str(self.current_gguf) if self.current_gguf else None,
            "current_category": self.current_category,
            "is_loaded": self.current_model is not None,
            "load_count": self.load_count,
            "llama_cpp_available": LLAMA_CPP_AVAILABLE,
        }
