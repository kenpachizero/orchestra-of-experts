"""
Orchestra of Experts - Main entry point

Startup sequence:
1. Initialise the Conductor (router)
2. Scan available experts
3. Enter the main interaction loop
4. Let the Conductor decide which expert to call
5. (Future) Load → Run → Unload the chosen expert
"""

import sys
from pathlib import Path

# Make sure we can import router even if run from different directories
CURRENT_DIR = Path(__file__).parent
sys.path.insert(0, str(CURRENT_DIR))

from router import Conductor


def print_banner():
    print("=" * 60)
    print("  Orchestra of Experts")
    print("  Sequential Mixture-of-Experts System")
    print("=" * 60)
    print()


def startup():
    """Run all startup checks and initialise the system."""
    print_banner()

    print("[Startup] Initialising Conductor...")
    # Point at the parent Orchestra folder
    orchestra_root = CURRENT_DIR.parent
    conductor = Conductor(orchestra_root=orchestra_root)

    experts = conductor.list_experts()
    print(f"[Startup] Found {len(experts)} available experts:")
    for expert in experts:
        print(f"           • {expert}")
    print()

    print("[Startup] System ready. Type your request (or 'quit' to exit).")
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

        if user_input.lower() in {"quit", "exit", "q"}:
            print("[Shutdown] Goodbye.")
            break

        # Hand everything to the Conductor / router
        result = conductor.run(user_input)
        print(f"\nOrchestra: {result}")


def main():
    conductor = startup()
    main_loop(conductor)


if __name__ == "__main__":
    main()
