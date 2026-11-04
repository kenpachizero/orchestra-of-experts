"""
Orchestra of Experts - Model Setup Helper

Uses llmfit to recommend models that fit the current hardware,
then helps download suitable general-purpose models into Orchestra/General/.

llmfit is MIT licensed (Copyright (c) 2026 Alex Jones).
https://github.com/AlexsJones/llmfit
"""

from pathlib import Path
import json
import subprocess
import shutil
import sys

CURRENT_DIR = Path(__file__).parent
ORCHESTRA_ROOT = CURRENT_DIR.parent
GENERAL_DIR = ORCHESTRA_ROOT / "General"
SETUP_FLAG = GENERAL_DIR / ".models_setup_done"


def find_llmfit_binary() -> str | None:
    """
    Try to locate a usable llmfit binary.
    Order of preference:
    1. llmfit on PATH
    2. Built binary inside the cloned llmfit folder
    """
    # 1. System / PATH
    if shutil.which("llmfit"):
        return "llmfit"

    # 2. Local clone (common locations after cargo build)
    candidates = [
        CURRENT_DIR / "llmfit" / "target" / "release" / "llmfit",
        CURRENT_DIR / "llmfit" / "target" / "debug" / "llmfit",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return str(path)

    return None


def get_recommendations(limit: int = 5) -> list[dict]:
    """
    Call llmfit recommend --json and return the list of models.
    Returns empty list on failure.
    """
    binary = find_llmfit_binary()
    if not binary:
        print("[ModelSetup] llmfit binary not found.")
        print("           Install it with:  uv tool install llmfit")
        print("           or build the cloned repo:  cd Orchestra/core/llmfit && cargo build --release")
        return []

    try:
        result = subprocess.run(
            [binary, "recommend", "--json", "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print("[ModelSetup] llmfit returned an error:")
            print(result.stderr.strip() or result.stdout.strip())
            return []

        data = json.loads(result.stdout)
        # llmfit returns { "system": {...}, "models": [ ... ] }
        return data.get("models", [])
    except Exception as e:
        print(f"[ModelSetup] Failed to run llmfit: {e}")
        return []


def print_recommendations(models: list[dict]) -> None:
    if not models:
        print("[ModelSetup] No recommendations available.")
        return

    print("\nRecommended general models for your hardware:\n")
    for i, m in enumerate(models, 1):
        name = m.get("name") or m.get("model") or "unknown"
        score = m.get("score", "?")
        fit = m.get("fit_level", "?")
        quant = m.get("best_quant") or m.get("quantization") or "?"
        tps = m.get("estimated_tps", "?")
        size = m.get("disk_size_gb") or m.get("memory_required_gb") or "?"

        print(f"  {i}. {name}")
        print(f"     Score: {score}  |  Fit: {fit}  |  Quant: {quant}  |  ~{tps} tok/s  |  ~{size} GB")
    print()


def is_first_run() -> bool:
    """True if we have never successfully run model setup for General."""
    if SETUP_FLAG.exists():
        return False
    # Also treat empty General folder as first run
    if not GENERAL_DIR.exists():
        return True
    # Ignore .gitkeep and the flag itself
    contents = [p for p in GENERAL_DIR.iterdir() if p.name not in {".gitkeep", ".models_setup_done"}]
    return len(contents) == 0


def mark_setup_done() -> None:
    GENERAL_DIR.mkdir(parents=True, exist_ok=True)
    SETUP_FLAG.write_text("done\n", encoding="utf-8")


def run_model_setup(interactive: bool = True) -> None:
    """
    Main entry point.
    Shows llmfit recommendations and (optionally) guides the user
    to download models into Orchestra/General/.
    """
    print("[ModelSetup] Checking hardware and asking llmfit for recommendations...")
    print("            (llmfit by Alex Jones — https://github.com/AlexsJones/llmfit)\n")

    models = get_recommendations(limit=5)
    print_recommendations(models)

    if not models:
        return

    if not interactive:
        return

    print("These models are suitable for the General expert folder.")
    print("Downloading large GGUF files can take a lot of disk space and time.")
    print()
    print("Options:")
    print("  1. Open the official model page / download instructions (recommended)")
    print("  2. Mark setup as done and skip for now")
    print("  3. Cancel")
    print()

    choice = input("Choose [1/2/3]: ").strip()

    if choice == "1":
        top = models[0]
        name = top.get("name") or top.get("model") or ""
        print()
        print(f"Top recommendation: {name}")
        print()
        print("Suggested next steps:")
        print(f"  • Visit the model on Hugging Face and download a GGUF quant that fits your VRAM")
        print(f"  • Place the .gguf file(s) into:  {GENERAL_DIR}")
        print()
        print("Or, if you use Ollama / LM Studio, pull the model there and we can link it later.")
        mark_setup_done()
        print("\n[ModelSetup] Setup marked as done. You can re-run this anytime with the 'models' command.")

    elif choice == "2":
        mark_setup_done()
        print("[ModelSetup] Marked as done. You can re-run later with the 'models' command.")

    else:
        print("[ModelSetup] Cancelled.")


if __name__ == "__main__":
    run_model_setup(interactive=True)
