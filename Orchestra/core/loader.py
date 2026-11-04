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
            self.load_count += 1

            elapsed = time.perf_counter() - start
            print(f"[Loader] Loaded in {elapsed:.2f}s  (total loads this session: {self.load_count})")
            return True

        except Exception as e:
            print(f"[Loader] ERROR while loading model: {e}")
            self.current_model = None
            self.current_expert = None
            self.current_gguf = None
            return False

    def unload(self) -> None:
        """Unload the currently resident expert and free resources."""
        if self.current_expert is None:
            return

        print(f"[Loader] Unloading expert: {Path(self.current_expert).name}")

        # Drop the reference and force garbage collection
        self.current_model = None
        self.current_expert = None
        self.current_gguf = None
        gc.collect()

        print("[Loader] Unloaded.")

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
            # Simple chat-style prompt. Can be improved later with proper chat templates.
            prompt = (
                "You are a helpful expert assistant.\n\n"
                f"User: {instruction}\n\n"
                "Assistant:"
            )

            output = self.current_model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or ["User:", "\nUser:"],
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
            "is_loaded": self.current_model is not None,
            "load_count": self.load_count,
            "llama_cpp_available": LLAMA_CPP_AVAILABLE,
        }
