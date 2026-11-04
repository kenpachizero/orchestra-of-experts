"""
Orchestra of Experts - Main entry point

Startup sequence:
1. Ensure llmfit is present (clone if missing)
2. On first run, offer to set up General models via llmfit recommendations
3. Initialise the Conductor (router)
4. Scan available experts
5. Enter the main interaction loop
6. Let the Conductor decide which expert to call
"""

import sys
import subprocess
from pathlib import Path

# Make sure we can import router even if run from different directories
CURRENT_DIR = Path(__file__).parent
sys.path.insert(0, str(CURRENT_DIR))

from router import Conductor
from model_setup import is_first_run, run_model_setup

LLMFIT_DIR = CURRENT_DIR / "llmfit"
LLMFIT_REPO = "https://github.com/AlexsJones/llmfit.git"


def print_banner():
    print("=" * 60)
    print("  Orchestra of Experts")
    print("  Sequential Mixture-of-Experts System")
    print("=" * 60)
    print()


def ensure_llmfit() -> bool:
    """
    Make sure the llmfit folder exists.
    If missing, clone the official repository.

    llmfit is MIT licensed (Copyright (c) 2026 Alex Jones).
    We use it as-is and keep the original LICENSE.
    """
    if LLMFIT_DIR.exists() and any(LLMFIT_DIR.iterdir()):
        print("[Startup] llmfit found.")
        return True

    print("[Startup] llmfit not found. Cloning official repository...")
    print(f"           Source: {LLMFIT_REPO}")
    print("           License: MIT (Copyright (c) 2026 Alex Jones)")
    print()

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", LLMFIT_REPO, str(LLMFIT_DIR)],
            check=True,
            capture_output=True,
            text=True,
        )
        print("[Startup] llmfit successfully downloaded.")
        print("           Please respect the MIT license and credit the original author.")
        return True
    except FileNotFoundError:
        print("[Startup] ERROR: git is not installed. Cannot download llmfit.")
        print("           Install git, or manually clone:")
        print(f"           git clone {LLMFIT_REPO} {LLMFIT_DIR}")
        return False
    except subprocess.CalledProcessError as e:
        print("[Startup] ERROR: Failed to clone llmfit.")
        print(e.stderr)
        return False


def startup():
    """Run all startup checks and initialise the system."""
    print_banner()

    # 1. Ensure llmfit is available
    ensure_llmfit()
    print()

    # 2. First-run model setup for General folder
    if is_first_run():
        print("[Startup] First run detected (General folder is empty).")
        print("          Would you like to see recommended models for your hardware?")
        answer = input("          Run model setup now? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            run_model_setup(interactive=True)
        else:
            print("[Startup] Skipped. You can run it later by typing: models")
        print()

    print("[Startup] Initialising Conductor...")
    orchestra_root = CURRENT_DIR.parent
    conductor = Conductor(orchestra_root=orchestra_root)

    experts = conductor.list_experts()
    print(f"[Startup] Found {len(experts)} available experts:")
    for expert in experts:
        print(f"           • {expert}")
    print()

    print("[Startup] System ready.")
    print("          Commands:  models  |  quit")
    print("-" * 60)
    return conductor


def main_loop(conductor: Conductor):
    """Simple interactive loop. The Conductor handles all routing."""
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n[Shutdown] Goodbye.")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in {"quit", "exit", "q"}:
            print("[Shutdown] Goodbye.")
            break

        # Built-in command: re-run model recommendations / setup
        if lower in {"models", "setup", "setup models", "recommend"}:
            run_model_setup(interactive=True)
            continue

        # Hand everything else to the Conductor / router
        result = conductor.run(user_input)
        print(f"\nOrchestra: {result}")


def main():
    conductor = startup()
    main_loop(conductor)


if __name__ == "__main__":
    main()
