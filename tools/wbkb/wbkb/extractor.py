"""WorldBox assembly -> decompiled raw source snapshot pipeline (Z2).

Decompiled source is generated evidence, not hand-maintained code. The
snapshot is keyed by game version + assembly SHA-256 and reproducible via
`dotnet tool restore` + `python -m wbkb extract worldbox`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import util

EXTRACTION_MANIFEST_SCHEMA_VERSION = 1
GENERATED_ROOT = Path("data/generated/worldbox")
SNAPSHOTS_DIR = GENERATED_ROOT / "snapshots"
TMP_DIR = GENERATED_ROOT / ".tmp"

MIN_CSHARP_FILES = 50
CORE_TYPES = ("Actor", "City", "Kingdom")
CONTENT_SAMPLES = 5
DECOMPILE_TIMEOUT_SECONDS = 30 * 60

_ILSPY_VERSION_RE = re.compile(r"ilspycmd:\s*(\S+)", re.IGNORECASE)
_TYPE_DECL_RE = re.compile(r"\b(class|struct|interface|enum)\s+")
_ASSEMBLY_ATTR_RE = re.compile(r"^\s*\[assembly:", re.MULTILINE)


class ExtractionError(RuntimeError):
    pass


# --- Identity ----------------------------------------------------------------


def snapshot_id(game_version: str | None, assembly_sha256: str) -> str:
    sha12 = (assembly_sha256 or "").lower()[:12]
    version = (game_version or "").strip()
    return f"worldbox-{version}-{sha12}" if version else f"worldbox-{sha12}"


# --- Extractor detection -----------------------------------------------------


def _parse_ilspy_version(text: str) -> str | None:
    m = _ILSPY_VERSION_RE.search(text)
    return m.group(1) if m else None


def detect_extractor(repo_root: Path, runner=subprocess) -> dict | None:
    """Detect the local dotnet tool ilspycmd (pinned via .config/dotnet-tools.json)."""
    try:
        proc = runner.run(
            ["dotnet", "ilspycmd", "--version"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    version = _parse_ilspy_version(proc.stdout or "")
    if not version:
        return None
    return {
        "name": "ilspycmd",
        "version": version,
        "mode": "dotnet-local-tool",
        "install": ".config/dotnet-tools.json (dotnet tool restore)",
        "options": ["-p"],
    }


# --- Validation --------------------------------------------------------------


def _walk_cs_files(source_dir: Path) -> list[Path]:
    files = []
    for base, _dirs, names in os.walk(source_dir):
        for fn in names:
            if fn.lower().endswith(".cs"):
                files.append(Path(base) / fn)
    return sorted(files, key=str)


def _find_core_types(cs_files: list[Path]) -> dict[str, bool]:
    wanted = {name: re.compile(rf"\bclass\s+{name}\b") for name in CORE_TYPES}
    found = {name: False for name in CORE_TYPES}
    for path in cs_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, pattern in wanted.items():
            if not found[name] and pattern.search(text):
                found[name] = True
        if all(found.values()):
            break
    return found


def _check_content_samples(cs_files: list[Path]) -> list[str]:
    problems = []
    if not cs_files:
        return ["no .cs files produced"]
    step = max(1, len(cs_files) // CONTENT_SAMPLES)
    samples = cs_files[::step][:CONTENT_SAMPLES]
    for path in samples:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            problems.append(f"unreadable sample {path.name}: {exc}")
            continue
        if not text.strip():
            problems.append(f"empty sample {path.name}")
        elif "\x00" in text:
            problems.append(f"binary content in sample {path.name}")
        elif not (_TYPE_DECL_RE.search(text) or _ASSEMBLY_ATTR_RE.search(text) or "using " in text):
            problems.append(f"no C# syntax in sample {path.name}")
    return problems


def validate_source(source_dir: Path) -> dict:
    cs_files = _walk_cs_files(source_dir)
    total_files = 0
    total_bytes = 0
    project_files = 0
    for base, _dirs, names in os.walk(source_dir):
        for fn in names:
            total_files += 1
            p = Path(base) / fn
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass
            if fn.lower().endswith((".csproj", ".sln")):
                project_files += 1
    core = _find_core_types(cs_files)
    problems = _check_content_samples(cs_files)
    ok = len(cs_files) >= MIN_CSHARP_FILES and not problems
    return {
        "ok": ok,
        "csharp_files": len(cs_files),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "project_files": project_files,
        "core_types": core,
        "core_types_missing": [k for k, v in core.items() if not v],
        "problems": problems,
    }


# --- Manifest ----------------------------------------------------------------


def build_extraction_manifest(
    *,
    snapshot: str,
    game_version: str | None,
    assembly: dict,
    extractor: dict,
    validation: dict,
    publicized: dict | None,
    status: str,
) -> dict:
    return {
        "schema_version": EXTRACTION_MANIFEST_SCHEMA_VERSION,
        "source_id": "worldbox",
        "snapshot_id": snapshot,
        "status": status,
        "game_version": game_version,
        "assembly": {"sha256": assembly["sha256"], "size": assembly.get("size")},
        "extractor": {
            "name": extractor["name"],
            "version": extractor["version"],
            "mode": extractor.get("mode"),
            "install": extractor.get("install"),
            "options": extractor.get("options", []),
        },
        "publicized": publicized or {"available": False},
        "output": {
            "csharp_files": validation["csharp_files"],
            "total_files": validation["total_files"],
            "total_bytes": validation["total_bytes"],
            "project_files": validation["project_files"],
        },
        "validation": {
            "core_types": validation["core_types"],
            "content_problems": validation["problems"],
        },
        "notes": "Decompiled source is reconstructed reference material, not original source code.",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }


# --- Orchestration -----------------------------------------------------------


def _worldbox_source(registry: dict) -> dict:
    source = (registry.get("sources") or {}).get("worldbox")
    if not source or not source.get("assembly"):
        raise ExtractionError("worldbox source not found in local registry; run: python -m wbkb discover")
    return source


def _verify_assembly(source: dict) -> dict:
    assembly = source["assembly"]
    path = assembly.get("path")
    if not path or not Path(path).is_file():
        raise ExtractionError(f"registered assembly missing on disk: {path}")
    actual = util.sha256_file(path)
    if actual != assembly.get("sha256"):
        raise ExtractionError("assembly changed since last discovery; run: python -m wbkb discover")
    return {"path": path, "sha256": actual, "size": Path(path).stat().st_size}


def snapshot_state(repo_root: Path, registry: dict, extractor_info: dict | None = None) -> dict:
    """OK / MISSING / STALE for the currently registered assembly."""
    source = _worldbox_source(registry)
    assembly = source.get("assembly") or {}
    snap = snapshot_id(source.get("game_version"), assembly.get("sha256", ""))
    manifest_path = Path(repo_root) / SNAPSHOTS_DIR / snap / "extraction-manifest.json"
    if not manifest_path.is_file():
        has_any = (Path(repo_root) / SNAPSHOTS_DIR).is_dir() and any(
            (Path(repo_root) / SNAPSHOTS_DIR).iterdir()
        )
        return {"snapshot": snap, "state": "MISSING" if not has_any else "STALE"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"snapshot": snap, "state": "STALE"}
    if manifest.get("assembly", {}).get("sha256") != assembly.get("sha256"):
        return {"snapshot": snap, "state": "STALE"}
    if manifest.get("status") != "completed":
        return {"snapshot": snap, "state": "STALE"}
    state = "OK"
    if extractor_info and manifest.get("extractor", {}).get("version") != extractor_info["version"]:
        state = "OK-EXTRACTOR-CHANGED"
    return {"snapshot": snap, "state": state, "manifest": manifest}


def perform_extraction(
    repo_root: Path,
    registry: dict,
    force: bool = False,
    runner=subprocess,
    extractor_info: dict | None = None,
) -> dict:
    repo_root = Path(repo_root)
    source = _worldbox_source(registry)
    assembly = _verify_assembly(source)

    extractor = extractor_info or detect_extractor(repo_root, runner=runner)
    if extractor is None:
        raise ExtractionError(
            "no decompiler available; run `dotnet tool restore` in the WBKB root (requires .NET SDK)"
        )

    snap = snapshot_id(source.get("game_version"), assembly["sha256"])
    snap_dir = repo_root / SNAPSHOTS_DIR / snap
    manifest_path = snap_dir / "extraction-manifest.json"

    if manifest_path.is_file() and not force:
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if (
            isinstance(existing, dict)
            and existing.get("status") == "completed"
            and existing.get("assembly", {}).get("sha256") == assembly["sha256"]
        ):
            if existing.get("extractor", {}).get("version") == extractor["version"]:
                if (snap_dir / "source").is_dir():
                    return {"status": "UNCHANGED", "snapshot": snap, "dir": snap_dir, "manifest": existing}

    # publicized metadata only (no decompilation of the publicized assembly)
    pub_source = (registry.get("sources") or {}).get("worldbox-publicized")
    publicized = {"available": False}
    if pub_source and pub_source.get("file"):
        pub_file = pub_source["file"]
        publicized = {
            "available": True,
            "sha256": pub_file.get("sha256"),
            "size": pub_file.get("size"),
        }

    temp_dir = repo_root / TMP_DIR / snap
    source_out = temp_dir / "source"
    log_path = repo_root / "data/cache" / f"extract-{snap}.log"
    shutil.rmtree(temp_dir, ignore_errors=True)
    source_out.mkdir(parents=True)

    cmd = ["dotnet", "ilspycmd", assembly["path"], "-p", "-o", str(source_out)]
    try:
        proc = runner.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=DECOMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExtractionError(f"decompiler timed out after {DECOMPILE_TIMEOUT_SECONDS}s; log: {log_path}")
    except OSError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExtractionError(f"failed to launch decompiler: {exc}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n--- stdout ---\n{proc.stdout or ''}\n--- stderr ---\n{proc.stderr or ''}\n",
        encoding="utf-8",
    )
    if proc.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExtractionError(
            f"decompiler exited with {proc.returncode}; log: {log_path}"
        )

    validation = validate_source(source_out)
    if not validation["ok"]:
        summary = "; ".join(validation["problems"]) or f"only {validation['csharp_files']} .cs files"
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExtractionError(f"extraction validation failed: {summary}; log: {log_path}")

    status = "CREATED"
    if snap_dir.exists():
        status = "REPLACED-EXTRACTOR" if manifest_path.is_file() else "REPLACED"

    manifest = build_extraction_manifest(
        snapshot=snap,
        game_version=source.get("game_version"),
        assembly=assembly,
        extractor=extractor,
        validation=validation,
        publicized=publicized,
        status="completed",
    )
    manifest_path_out = temp_dir / "extraction-manifest.json"
    manifest_path_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    _atomic_swap(snap_dir, temp_dir)
    result = {"status": status, "snapshot": snap, "dir": snap_dir, "manifest": manifest}
    if validation["core_types_missing"]:
        result["warnings"] = [f"core type not found: {t}" for t in validation["core_types_missing"]]
    return result


def _atomic_swap(snap_dir: Path, temp_dir: Path) -> None:
    """temp -> snap_dir without ever leaving a half-written snapshot in place."""
    snap_dir.parent.mkdir(parents=True, exist_ok=True)
    trash = snap_dir.parent / f".trash-{snap_dir.name}-{os.getpid()}"
    shutil.rmtree(trash, ignore_errors=True)
    if snap_dir.exists():
        os.rename(snap_dir, trash)
    try:
        os.rename(temp_dir, snap_dir)
    except OSError:
        if trash.exists():
            os.rename(trash, snap_dir)  # restore previous snapshot
        raise
    shutil.rmtree(trash, ignore_errors=True)
