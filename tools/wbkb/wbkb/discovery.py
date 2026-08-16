"""Automatic discovery of external sources.

External sources are strictly read-only. WBKB is project-agnostic: it never
inspects consumer mod projects. Discovery order (Z1.1):
1. explicit override (CLI / caller-provided worldbox root)
2. existing local config (if WorldBox root still valid)
3. WBKB_WORLDBOX_ROOT environment variable
4. Steam library folders (libraryfolders.vdf)
5. user input as last resort (interactive prompt, handled by the CLI)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import config, util

WORLDBOX_STEAM_APPID = "1206560"
WORLDBOX_ROOT_ENV = "WBKB_WORLDBOX_ROOT"
_VDF_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf")

_VERSIONS_JSON_MAX_DEPTH = 3
_PUBLICIZED_GLOB_MAX_DEPTH = 6
_PUBLICIZED_ALTERNATIVE_CAP = 3

_WORLDBOX_EXE_CANDIDATES = ("worldbox.exe", "WorldBox.exe")
_PUBLICIZED_CANDIDATES = (
    ("worldbox_Data", "StreamingAssets", "mods", "NML", "Assembly-CSharp-Publicized.dll"),
    ("worldbox_Data", "Managed", "publicized_assemblies", "Assembly-CSharp_publicized.dll"),
)
_NML_ASSEMBLY_NAMES = ("NeoModLoader.dll", "NeoModLoader.AutoUpdate_memload.dll")
_COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")
_GAME_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")


def _iter_files_bounded(root: Path, pattern: str, max_depth: int):
    root = Path(root)
    base_depth = len(root.parts)
    for base, dirs, files in os.walk(root):
        depth = len(Path(base).parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if Path(fn).match(pattern):
                yield Path(base) / fn


# --- Stage 3: find the WorldBox root via standard Steam installation -------


def _steam_libraries() -> list[Path]:
    if not _VDF_PATH.is_file():
        return []
    try:
        text = _VDF_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [Path(raw.replace("\\\\", "\\")) for raw in re.findall(r'"path"\s+"([^"]+)"', text)]


def _find_worldbox_root_in_steam_libraries() -> str | None:
    for lib in _steam_libraries():
        common = lib / "steamapps" / "common"
        if not common.is_dir():
            continue
        try:
            entries = list(common.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir() and entry.name.lower() == "worldbox":
                return str(entry)
    return None


# --- Game version ------------------------------------------------------------


def _steam_buildid(worldbox_root: Path) -> str | None:
    acf = worldbox_root.parent.parent / f"appmanifest_{WORLDBOX_STEAM_APPID}.acf"
    if not acf.is_file():
        return None
    try:
        text = acf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'"buildid"\s+"(\d+)"', text)
    return m.group(1) if m else None


def _find_version_for_path(node, target: str) -> str | None:
    """Recursively find a dict carrying both a game-version field and a path
    field that matches the WorldBox install; returns the version."""
    if isinstance(node, dict):
        version = None
        for key in ("GameVersion", "game_version", "version"):
            v = node.get(key)
            if isinstance(v, str) and _GAME_VERSION_RE.fullmatch(v):
                version = v
                break
        if version is not None:
            for key, val in node.items():
                if isinstance(val, str) and "path" in key.lower():
                    norm = val.replace("/", "\\").lower().rstrip("\\")
                    if norm == target:
                        return version
        for child in node.values():
            found = _find_version_for_path(child, target)
            if found:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_version_for_path(child, target)
            if found:
                return found
    return None


def _game_version_from_local_metadata(repo_root: Path, worldbox_root: Path) -> tuple[str | None, str]:
    target = str(worldbox_root).replace("/", "\\").lower().rstrip("\\")
    for vj in sorted(_iter_files_bounded(repo_root.parent, "versions.json", _VERSIONS_JSON_MAX_DEPTH), key=str):
        try:
            data = json.loads(vj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version = _find_version_for_path(data, target)
        if version:
            return version, "verified:local-metadata"
    return None, "unknown"


# --- Config assembly ---------------------------------------------------------


def _find_publicized(worldbox_root: Path) -> Path | None:
    for rel in _PUBLICIZED_CANDIDATES:
        cand = worldbox_root.joinpath(*rel)
        if cand.is_file():
            return cand
    for hit in sorted(_iter_files_bounded(worldbox_root, "*ublicized*.dll", _PUBLICIZED_GLOB_MAX_DEPTH), key=str):
        return hit
    return None


def _looks_like_reference_mods(mods_dir: Path) -> bool:
    try:
        children = list(mods_dir.iterdir())
    except OSError:
        return False
    return any(c.is_dir() and (c / "mod.json").is_file() for c in children)


def config_from_worldbox_root(root: Path) -> dict:
    """Derive a full source config from a WorldBox installation root."""
    cfg = config.example_config()
    rootp = Path(root).resolve()
    cfg["worldbox_root"] = str(rootp)

    assembly = rootp / "worldbox_Data" / "Managed" / "Assembly-CSharp.dll"
    if assembly.is_file():
        cfg["assembly_csharp"] = str(assembly)

    publicized = _find_publicized(rootp)
    if publicized:
        cfg["assembly_csharp_publicized"] = str(publicized.resolve())

    nml = rootp / "worldbox_Data" / "StreamingAssets" / "mods" / "NML"
    if nml.is_dir():
        cfg["neomodloader_root"] = str(nml)

    mods = rootp / "Mods"
    if mods.is_dir() and _looks_like_reference_mods(mods):
        cfg["reference_mods_roots"] = [str(mods)]

    return cfg


def auto_discover_config(_repo_root: Path) -> tuple[dict, str]:
    env_root = os.environ.get(WORLDBOX_ROOT_ENV, "").strip()
    if env_root and Path(env_root).is_dir():
        return config_from_worldbox_root(Path(env_root)), "environment"
    steam_root = _find_worldbox_root_in_steam_libraries()
    if steam_root:
        return config_from_worldbox_root(Path(steam_root)), "steam"
    return config.example_config(), "none"


# --- Source scans ------------------------------------------------------------


def _scan_worldbox(cfg: dict, repo_root: Path) -> dict:
    out = {
        "root": None,
        "exe_found": False,
        "steam_buildid": None,
        "game_version": None,
        "game_version_status": "unknown",
        "assembly": None,
        "publicized": None,
        "publicized_alternatives": [],
    }
    root = (cfg.get("worldbox_root") or "").strip()
    if not root or not Path(root).is_dir():
        return out
    rootp = Path(root)
    out["root"] = str(rootp.resolve())
    out["exe_found"] = any((rootp / name).is_file() for name in _WORLDBOX_EXE_CANDIDATES)
    out["steam_buildid"] = _steam_buildid(rootp)
    out["game_version"], out["game_version_status"] = _game_version_from_local_metadata(repo_root, rootp)

    assembly = (cfg.get("assembly_csharp") or "").strip()
    if assembly and Path(assembly).is_file():
        out["assembly"] = util.file_record(assembly)
    else:
        cand = rootp / "worldbox_Data" / "Managed" / "Assembly-CSharp.dll"
        if cand.is_file():
            out["assembly"] = util.file_record(cand)

    publicized = (cfg.get("assembly_csharp_publicized") or "").strip()
    primary = Path(publicized) if publicized else None
    if primary and primary.is_file():
        out["publicized"] = util.file_record(primary)

    primary_resolved = str(primary.resolve()) if primary else None
    seen = set()
    for rel in _PUBLICIZED_CANDIDATES:
        cand = rootp.joinpath(*rel)
        if not cand.is_file():
            continue
        resolved = str(cand.resolve())
        if resolved == primary_resolved or resolved in seen:
            continue
        seen.add(resolved)
        out["publicized_alternatives"].append(util.file_record(cand))
        if len(out["publicized_alternatives"]) >= _PUBLICIZED_ALTERNATIVE_CAP:
            break
    return out


def _scan_neomodloader(cfg: dict) -> dict:
    out = {"root": None, "commit": None, "version": None, "assemblies": []}
    nml_root = (cfg.get("neomodloader_root") or "").strip()
    mods_dir = None
    if nml_root and Path(nml_root).is_dir():
        rootp = Path(nml_root)
        out["root"] = str(rootp.resolve())
        mods_dir = rootp.parent
        commit_file = rootp / "commit"
        if commit_file.is_file():
            try:
                text = commit_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                text = ""
            if text and _COMMIT_RE.fullmatch(text):
                out["commit"] = text
        version_file = rootp / "version"
        if version_file.is_file():
            try:
                text = version_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                text = ""
            if text and len(text) <= 32:
                out["version"] = text
    elif nml_root:
        # root configured but missing — fall back to nothing
        mods_dir = None
    if mods_dir and mods_dir.is_dir():
        for name in _NML_ASSEMBLY_NAMES:
            p = mods_dir / name
            if p.is_file():
                out["assemblies"].append(util.file_record(p))
    if not out["root"] and not out["assemblies"]:
        # last resort: NeoModLoader.dll without NML dir configured
        wb_root = (cfg.get("worldbox_root") or "").strip()
        if wb_root:
            p = Path(wb_root) / "worldbox_Data" / "StreamingAssets" / "mods" / "NeoModLoader.dll"
            if p.is_file():
                out["assemblies"].append(util.file_record(p))
    return out


def _read_mod_json(root: Path) -> dict | None:
    path = root / "mod.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_git_info(root: Path) -> tuple[str | None, str | None]:
    git_dir = root / ".git"
    if not git_dir.exists():
        return None, None
    repository = None
    config_file = git_dir / "config"
    if config_file.is_file():
        try:
            lines = config_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        in_origin = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("["):
                in_origin = 'remote "origin"' in stripped
            elif in_origin and stripped.startswith("url"):
                parts = stripped.split("=", 1)
                if len(parts) == 2 and parts[1].strip():
                    repository = parts[1].strip()
                    break
    commit = None
    head = git_dir / "HEAD"
    if head.is_file():
        try:
            text = head.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            text = ""
        if text.startswith("ref:"):
            refname = text[4:].strip()
            ref_file = git_dir / refname
            if ref_file.is_file():
                try:
                    commit = ref_file.read_text(encoding="utf-8", errors="replace").strip() or None
                except OSError:
                    commit = None
            else:
                packed = git_dir / "packed-refs"
                if packed.is_file():
                    try:
                        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                            if line.endswith(" " + refname) and line.split():
                                commit = line.split()[0]
                                break
                    except OSError:
                        pass
        elif text:
            commit = text
    return repository, commit


def _scan_reference_mod(root: Path) -> dict:
    stats = util.dir_stats(root)
    mod_json = _read_mod_json(root)
    repository, commit = _read_git_info(root)

    name = root.name
    loader = None
    loader_status = None
    if mod_json is not None:
        json_name = mod_json.get("name")
        if isinstance(json_name, str) and json_name.strip():
            name = json_name.strip()
        for key in ("ModLoader", "mod_loader", "loader"):
            value = mod_json.get(key)
            if isinstance(value, str) and value.strip():
                loader = value.strip()
                loader_status = "verified:mod.json"
                break
        if loader is None:
            loader = "NeoModLoader"
            loader_status = "inferred:mod.json"

    return {
        "id": util.ref_source_id(root.name),
        "name": name,
        "dir_name": root.name,
        "root_path": str(root.resolve()),
        "git_repository": repository,
        "git_commit": commit,
        "file_count": stats["file_count"],
        "csharp_file_count": stats["csharp_file_count"],
        "project_files": stats["project_files"],
        "assembly_files": stats["assembly_files"],
        "detected_mod_loader": loader,
        "detected_mod_loader_status": loader_status,
        "fingerprint": {
            "file_count": stats["file_count"],
            "total_size": stats["total_size"],
            "latest_mtime": stats["latest_mtime"],
        },
    }


def _scan_reference_mods(cfg: dict) -> tuple[list[dict], list[str]]:
    mods: list[dict] = []
    problems: list[str] = []
    for raw in cfg.get("reference_mods_roots") or []:
        rootp = Path(str(raw))
        if not rootp.is_dir():
            problems.append(f"reference mods root not found: {raw}")
            continue
        try:
            children = sorted(rootp.iterdir(), key=str)
        except OSError:
            problems.append(f"reference mods root not readable: {raw}")
            continue
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            mods.append(_scan_reference_mod(child))
    mods.sort(key=lambda m: m["id"])
    return mods, problems


# --- Entry point -------------------------------------------------------------


def discover_sources(repo_root: Path, worldbox_root_override: str | None = None) -> dict:
    override = (worldbox_root_override or "").strip()
    if override and Path(override).is_dir():
        cfg = config_from_worldbox_root(Path(override))
        origin = "explicit"
    else:
        cfg = config.load_local_config(repo_root)
        if cfg is not None and config.config_is_usable(cfg):
            origin = "local-config"
        else:
            cfg, origin = auto_discover_config(repo_root)
            if config.local_config_path(repo_root).is_file():
                # keep the user's file untouched even when unusable
                origin = origin + "+stale-config-kept"
    config_written = not config.local_config_path(repo_root).is_file()

    worldbox = _scan_worldbox(cfg, repo_root)
    neomodloader = _scan_neomodloader(cfg)
    reference_mods, problems = _scan_reference_mods(cfg)
    if worldbox["root"] is None:
        problems.append("worldbox root not found")

    return {
        "config_origin": origin,
        "config_written": config_written,
        "config": cfg,
        "worldbox": worldbox,
        "neomodloader": neomodloader,
        "reference_mods": reference_mods,
        "problems": problems,
    }
