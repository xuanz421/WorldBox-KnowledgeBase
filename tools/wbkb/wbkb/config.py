"""Local configuration (config/wbkb.local.json) handling.

The local config is machine-specific (absolute paths) and must never be
committed; config/wbkb.example.json documents the schema and is committed.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = "config"
LOCAL_CONFIG_NAME = "wbkb.local.json"
EXAMPLE_CONFIG_NAME = "wbkb.example.json"

REQUIRED_KEYS = (
    "worldbox_root",
    "assembly_csharp",
    "assembly_csharp_publicized",
    "neomodloader_root",
    "reference_mods_roots",
)


def example_config() -> dict:
    return {
        "worldbox_root": "",
        "assembly_csharp": "",
        "assembly_csharp_publicized": "",
        "neomodloader_root": "",
        "reference_mods_roots": [],
    }


def local_config_path(repo_root: Path) -> Path:
    return Path(repo_root) / CONFIG_DIR / LOCAL_CONFIG_NAME


def load_local_config(repo_root: Path) -> dict | None:
    path = local_config_path(repo_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if any(key not in data for key in REQUIRED_KEYS):
        return None
    roots = data.get("reference_mods_roots")
    if roots is not None and not isinstance(roots, list):
        return None
    return data


def config_is_usable(cfg: dict) -> bool:
    """Usable = the WorldBox root it points at exists on this machine."""
    root = (cfg.get("worldbox_root") or "").strip()
    return bool(root) and Path(root).is_dir()


def save_local_config_if_changed(repo_root: Path, cfg: dict) -> bool:
    path = local_config_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True
