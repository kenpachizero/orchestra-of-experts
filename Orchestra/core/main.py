"""
Orchestra of Experts - Main entry point

Startup sequence:
1. Ensure we are running inside a project virtual environment
2. Detect GPU backend (CUDA / Metal / ROCm) and install matching llama-cpp-python
3. Ensure llmfit is present (clone if missing)
4. On first run, offer to set up General models via llmfit recommendations
5. Initialise the Conductor and enter the interaction loop

Compatible with: Linux, macOS, Windows
"""

import os
import sys
import subprocess
import importlib.util
import platform
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
VENV_DIR = CURRENT_DIR / ".venv"                 # lives inside Orchestra/core/
LLMFIT_DIR = CURRENT_DIR / "llmfit"
LLMFIT_REPO = "https://github.com/AlexsJones/llmfit.git"

# Make local imports work
sys.path.insert(0, str(CURRENT_DIR))


def print_banner():
    print("=" * 60)
    print("  Orchestra of Experts")
    print("  Sequential Mixture-of-Experts System")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Virtual environment bootstrap
# ---------------------------------------------------------------------------
def in_venv() -> bool:
    """Return True if we are already running inside a virtual environment."""
    return (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or bool(os.environ.get("VIRTUAL_ENV"))
    )


def get_venv_python() -> Path:
    """Return the path to the Python executable inside our .venv."""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> None:
    """
    Create a project virtual environment if needed and re-launch
    this script inside it.
    """
    if in_venv():
        print("[Startup] Running inside virtual environment.")
        return

    print("[Startup] No virtual environment detected.")
    print(f"          Creating one at: {VENV_DIR}")

    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("[Startup] ERROR: Failed to create virtual environment.")
        print(e)
        sys.exit(1)

    venv_python = get_venv_python()
    if not venv_python.exists():
        print("[Startup] ERROR: Virtual environment created but Python not found.")
        sys.exit(1)

    print("[Startup] Virtual environment ready. Re-launching inside it...")
    print()

    # Re-execute this script with the venv Python
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])


# ---------------------------------------------------------------------------
# GPU detection + llama-cpp-python install
# ---------------------------------------------------------------------------
def detect_gpu_backend() -> str:
    """
    Detect the best available GPU backend.

    Returns one of: "cuda", "metal", "rocm", "cpu"
    """
    system = platform.system()
    machine = platform.machine().lower()

    # Apple Silicon → Metal
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        print("[Startup] Detected Apple Silicon → Metal")
        return "metal"

    # NVIDIA CUDA
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"[Startup] Detected NVIDIA GPU → CUDA")
                print(f"           {result.stdout.strip().splitlines()[0]}")
                return "cuda"
        except Exception:
            pass

    # AMD ROCm
    if shutil.which("rocm-smi") or Path("/opt/rocm").exists():
        print("[Startup] Detected AMD ROCm")
        return "rocm"

    print("[Startup] No supported GPU acceleration detected → CPU")
    return "cpu"


def install_llama_cpp(backend: str) -> bool:
    """
    Install llama-cpp-python for the given backend.
    Falls back to plain CPU install on failure.
    """
    python = sys.executable
    base_cmd = [python, "-m", "pip", "install", "--upgrade", "llama-cpp-python"]

    env = os.environ.copy()

    if backend == "cuda":
        print("[Startup] Installing llama-cpp-python with CUDA support...")
        cmd = base_cmd + [
            "--extra-index-url",
            "https://abetlen.github.io/llama-cpp-python/whl/cu121",
        ]
        env["CMAKE_ARGS"] = "-DGGML_CUDA=on"

    elif backend == "metal":
        print("[Startup] Installing llama-cpp-python with Metal support...")
        env["CMAKE_ARGS"] = "-DGGML_METAL=on"
        cmd = base_cmd

    elif backend == "rocm":
        print("[Startup] Installing llama-cpp-python with ROCm support...")
        env["CMAKE_ARGS"] = "-DGGML_HIPBLAS=on"
        cmd = base_cmd

    else:
        print("[Startup] Installing llama-cpp-python (CPU)...")
        cmd = base_cmd

    try:
        subprocess.run(cmd, check=True, env=env)
        return True
    except subprocess.CalledProcessError:
        if backend != "cpu":
            print(f"[Startup] {backend.upper()} install failed — falling back to CPU...")
            try:
                subprocess.run(base_cmd, check=True)
                return True
            except subprocess.CalledProcessError:
                return False
        return False


def ensure_llama_cpp() -> bool:
    """Ensure llama-cpp-python is importable, installing it if necessary."""
    if importlib.util.find_spec("llama_cpp") is not None:
        print("[Startup] llama-cpp-python found.")
        return True

    print("[Startup] llama-cpp-python not found.")
    backend = detect_gpu_backend()
    print()

    success = install_llama_cpp(backend)

    if success and importlib.util.find_spec("llama_cpp") is not None:
        print("[Startup] llama-cpp-python installed successfully.")
        return True

    print("[Startup] ERROR: Could not install or import llama-cpp-python.")
    print("          Manual install options:")
    print(f"            {sys.executable} -m pip install llama-cpp-python")
    print()
    print("          GPU-specific instructions:")
    print("            https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration")
    return False


# ---------------------------------------------------------------------------
# llmfit
# ---------------------------------------------------------------------------
def ensure_llmfit() -> bool:
    """Clone llmfit if the folder is missing."""
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
        print(f"           Manually run: git clone {LLMFIT_REPO} {LLMFIT_DIR}")
        return False
    except subprocess.CalledProcessError as e:
        print("[Startup] ERROR: Failed to clone llmfit.")
        print(e.stderr)
        return False


# ---------------------------------------------------------------------------
# Memory CLI helpers
# ---------------------------------------------------------------------------
def handle_memory_command(conductor, user_input: str) -> bool:
    """
    Handle memory-related commands.
    Returns True if the input was a memory command (and was handled).
    """
    palace = conductor.palace
    parts = user_input.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # status
    if cmd in {"memory", "palace"} and not arg:
        status = palace.status()
        print("\n[Memory Palace]")
        print(f"  Root:    {status['palace_root']}")
        print(f"  Wings:   {status['wings']}  {status['wing_names']}")
        print(f"  Rooms:   {status['rooms']}")
        print(f"  Drawers: {status['drawers']}")
        return True

    # recall <query>
    if cmd == "recall":
        if not arg:
            print("Usage: recall <query>")
            return True
        hits = palace.search(arg, limit=5)
        if not hits:
            print(f"No memories found for: {arg}")
        else:
            print(f"\n[Recall] {len(hits)} result(s) for '{arg}':\n")
            for i, h in enumerate(hits, 1):
                print(f"  {i}. ({h.get('wing')}/{h.get('room')})")
                print(f"     {h.get('content', '')[:300]}")
                print()
        return True

    # remember <text>
    if cmd == "remember":
        if not arg:
            print("Usage: remember <text to store>")
            return True
        drawer = palace.remember(
            content=arg,
            wing="manual",
            room="notes",
            tags=["manual"],
        )
        print(f"[Memory] Stored in manual/notes (id: {drawer['id']})")
        return True

    # remember wing/room: <text>   (optional richer form)
    if cmd == "remember" and ":" in arg:
        # already handled above as plain text; keep simple for now
        pass

    return False


# ---------------------------------------------------------------------------
# Main startup + loop
# ---------------------------------------------------------------------------
def startup():
    print_banner()

    # 1. Virtual environment
    ensure_venv()
    print()

    # 2. llama-cpp-python (with GPU detection)
    if not ensure_llama_cpp():
        print("\n[Startup] Cannot continue without llama-cpp-python.")
        sys.exit(1)
    print()

    # 3. llmfit
    ensure_llmfit()
    print()

    # Local imports after dependency checks
    from router import Conductor
    from model_setup import is_first_run, run_model_setup

    # 4. First-run model setup
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

    # Palace status
    palace_status = conductor.palace.status()
    print(f"[Startup] Memory Palace: {palace_status['drawers']} drawers across {palace_status['wings']} wings")
    print()

    print("[Startup] System ready.")
    print("          Commands:  models | memory | recall <q> | remember <text> | quit")
    print("-" * 60)
    return conductor


def main_loop(conductor):
    from model_setup import run_model_setup

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

        if lower in {"models", "setup", "setup models", "recommend"}:
            run_model_setup(interactive=True)
            continue

        # Memory Palace commands
        if handle_memory_command(conductor, user_input):
            continue

        result = conductor.run(user_input)
        print(f"\nOrchestra: {result}")


def main():
    conductor = startup()
    main_loop(conductor)


if __name__ == "__main__":
    main()
