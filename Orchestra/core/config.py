"""
Orchestra of Experts - Configuration

Loads and saves settings from config.json next to this file.
All other modules should read settings through get_config().
"""

from __future__ import annotations

import json
from pathlib import Path
from copy import deepcopy
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    # Inference
    "n_ctx": 4096,
    "n_gpu_layers": -1,
    "n_threads": None,
    "max_tokens": 1024,
    "temperature": 0.7,
    "verbose_loader": False,

    # Memory Palace
    "auto_remember": False,
    "memory_recall_limit": 3,
    "default_memory_wing": "conversations",

    # Routing / multi-expert
    "enabled_experts": [],          # empty = all discovered experts allowed
    "auto_judge_when_multiple": True,
    "judge_expert_key": "Judge",

    # GUI
    "gui_theme": "dark",
    "gui_width": 1100,
    "gui_height": 720,
    "sidebar_visible": True,

    # Paths (relative to Orchestra/ or absolute)
    "orchestra_root": None,         # None = auto (parent of core/)
}

_config_cache: dict[str, Any] | None = None


def _merge_defaults(data: dict) -> dict:
    """Ensure every default key exists."""
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(data or {})
    return merged


def load_config(force_reload: bool = False) -> dict[str, Any]:
    """Load config from disk (or create defaults if missing)."""
    global _config_cache

    if _config_cache is not None and not force_reload:
        return _config_cache

    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            _config_cache = _merge_defaults(raw)
        except Exception as e:
            print(f"[Config] Failed to read config.json ({e}) — using defaults.")
            _config_cache = deepcopy(DEFAULT_CONFIG)
    else:
        _config_cache = deepcopy(DEFAULT_CONFIG)
        save_config(_config_cache)

    return _config_cache


def save_config(cfg: dict[str, Any] | None = None) -> None:
    """Write config to disk."""
    global _config_cache
    if cfg is not None:
        _config_cache = _merge_defaults(cfg)

    if _config_cache is None:
        _config_cache = deepcopy(DEFAULT_CONFIG)

    CONFIG_PATH.write_text(
        json.dumps(_config_cache, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_config() -> dict[str, Any]:
    """Return the current in-memory config (loads from disk on first call)."""
    return load_config()


def update_config(**kwargs) -> dict[str, Any]:
    """Update one or more keys and save."""
    cfg = get_config()
    cfg.update(kwargs)
    save_config(cfg)
    return cfg


def get(key: str, default: Any = None) -> Any:
    """Convenience: get a single setting."""
    return get_config().get(key, default)
