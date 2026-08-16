"""Local source registry + change detection.

data/cache/source-registry.local.json holds machine-specific details
(absolute paths, timestamps) and must never be committed.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY_SCHEMA_VERSION = 1
_LOCAL_REGISTRY_REL = Path("data/cache/source-registry.local.json")


def local_registry_path(repo_root: Path) -> Path:
    return Path(repo_root) / _LOCAL_REGISTRY_REL


def build_local_registry(scan: dict, generated_at: str) -> dict:
    sources: dict[str, dict] = {}

    wb = scan.get("worldbox") or {}
    if wb.get("root"):
        sources["worldbox"] = {
            "kind": "game",
            "root_path": wb["root"],
            "exe_found": wb.get("exe_found", False),
            "steam_buildid": wb.get("steam_buildid"),
            "game_version": wb.get("game_version"),
            "game_version_status": wb.get("game_version_status"),
            "assembly": wb.get("assembly"),
        }
        if wb.get("publicized"):
            sources["worldbox-publicized"] = {
                "kind": "assembly",
                "file": wb["publicized"],
                "alternatives": wb.get("publicized_alternatives", []),
            }

    nml = scan.get("neomodloader") or {}
    if nml.get("root") or nml.get("assemblies"):
        sources["neomodloader"] = {
            "kind": "loader",
            "root_path": nml.get("root"),
            "commit": nml.get("commit"),
            "version": nml.get("version"),
            "assemblies": nml.get("assemblies", []),
        }

    for mod in scan.get("reference_mods", []):
        sources[mod["id"]] = {"kind": "reference-mod", **mod}

    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "config_origin": scan.get("config_origin"),
        "sources": sources,
    }


def identity(source: dict) -> tuple:
    """Fields whose change means the source changed."""
    kind = source.get("kind")
    if kind == "game":
        assembly = source.get("assembly") or {}
        return ("game", assembly.get("sha256"), source.get("steam_buildid"), source.get("game_version"))
    if kind == "assembly":
        f = source.get("file") or {}
        return ("assembly", f.get("sha256"))
    if kind == "loader":
        return (
            "loader",
            source.get("commit"),
            source.get("version"),
            tuple((a.get("filename"), a.get("sha256")) for a in source.get("assemblies", [])),
        )
    fp = source.get("fingerprint") or {}
    return ("reference-mod", fp.get("file_count"), fp.get("total_size"), fp.get("latest_mtime"))


def diff_registries(old: dict | None, new: dict) -> dict[str, str]:
    old_sources = (old or {}).get("sources", {})
    new_sources = new.get("sources", {})
    out: dict[str, str] = {}
    for sid in sorted(set(old_sources) | set(new_sources)):
        if sid not in new_sources:
            out[sid] = "MISSING"
        elif sid not in old_sources:
            out[sid] = "NEW"
        elif identity(old_sources[sid]) != identity(new_sources[sid]):
            out[sid] = "CHANGED"
        else:
            out[sid] = "UNCHANGED"
    return out


def load_local_registry(repo_root: Path) -> dict | None:
    path = local_registry_path(repo_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and "sources" in data else None


def save_json_if_changed(path: Path, data: dict, volatile_keys: tuple[str, ...] = ("generated_at",)) -> bool:
    """Write only when content (ignoring volatile keys like timestamps) differs."""
    path = Path(path)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            scrub_old = {k: v for k, v in existing.items() if k not in volatile_keys}
            scrub_new = {k: v for k, v in data.items() if k not in volatile_keys}
            if scrub_old == scrub_new:
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def registry_paths_valid(registry: dict) -> bool:
    """Every recorded source still exists at its recorded location."""
    for source in registry.get("sources", {}).values():
        kind = source.get("kind")
        paths: list[str] = []
        if kind == "game":
            paths.append(source.get("root_path") or "")
            assembly = source.get("assembly") or {}
            paths.append(assembly.get("path") or "")
        elif kind == "assembly":
            f = source.get("file") or {}
            paths.append(f.get("path") or "")
        elif kind == "loader":
            paths.append(source.get("root_path") or "")
            paths.extend(a.get("path") or "" for a in source.get("assemblies", []))
        else:
            paths.append(source.get("root_path") or "")
        if any(p and not Path(p).exists() for p in paths):
            return False
    return True
