"""
Orchestra of Experts - File Checker & Auto-Repair

Checks that all required core files exist.
If any are missing, downloads the latest version from GitHub.
"""

from pathlib import Path
import urllib.request
import sys

# GitHub raw content base
GITHUB_USER = "kenpachizero"
GITHUB_REPO = "orchestra-of-experts"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}"

# Files that must exist (relative to this script's directory)
REQUIRED_FILES = [
    "main.py",
    "router.py",
    "loader.py",
    "check.py",          # this file itself
]


def get_core_dir() -> Path:
    return Path(__file__).parent.resolve()


def download_file(relative_path: str, dest: Path) -> bool:
    """Download a single file from the GitHub repo."""
    url = f"{RAW_BASE}/Orchestra/core/{relative_path}"
    print(f"  Downloading {relative_path} ...")
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            content = response.read()
        dest.write_bytes(content)
        print(f"  ✓ Restored {relative_path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {relative_path}: {e}")
        return False


def check_and_repair() -> bool:
    """
    Check all required files.
    Download any that are missing.
    Returns True if everything is present (or was successfully restored).
    """
    core_dir = get_core_dir()
    print(f"Checking core files in: {core_dir}\n")

    missing = []
    for filename in REQUIRED_FILES:
        path = core_dir / filename
        if path.exists() and path.stat().st_size > 0:
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename}  (missing)")
            missing.append(filename)

    if not missing:
        print("\nAll required files are present.")
        return True

    print(f"\n{len(missing)} file(s) missing. Attempting to restore from GitHub...\n")

    success = True
    for filename in missing:
        dest = core_dir / filename
        if not download_file(filename, dest):
            success = False

    if success:
        print("\nAll missing files have been restored.")
    else:
        print("\nSome files could not be restored. Check your internet connection or the GitHub repo.")

    return success


def main():
    print("=" * 50)
    print("  Orchestra of Experts - File Check")
    print("=" * 50)
    print()

    ok = check_and_repair()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
