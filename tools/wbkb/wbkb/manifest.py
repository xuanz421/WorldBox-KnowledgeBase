"""Committed source manifest — source identity only, never local paths.

manifests/source-registry.json is committed to Git and must contain no
absolute paths; data/cache/source-registry.local.json carries locations.
"""

from __future__ import annotations

from pathlib import Path

MANIFEST_SCHEMA_VERSION = 1
_MANIFEST_REL = Path("manifests/source-registry.json")


def manifest_path(repo_root: Path) -> Path:
    return Path(repo_root) / _MANIFEST_REL


def build_manifest(scan: dict, generated_at: str) -> dict:
    wb = scan.get("worldbox") or {}
    assembly = wb.get("assembly") or {}
    publicized = wb.get("publicized") or {}
    nml = scan.get("neomodloader") or {}

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "worldbox": {
            "game_version": wb.get("game_version"),
            "game_version_status": wb.get("game_version_status"),
            "steam_buildid": wb.get("steam_buildid"),
            "assembly_size": assembly.get("size"),
            "assembly_sha256": assembly.get("sha256"),
            "publicized_sha256": publicized.get("sha256"),
        },
        "neomodloader": {
            "version": nml.get("version"),
            "commit": nml.get("commit"),
            "assemblies": [
                {"filename": a["filename"], "sha256": a["sha256"], "size": a["size"]}
                for a in nml.get("assemblies", [])
                if a.get("filename") and a.get("sha256")
            ],
        },
        "reference_mods": sorted(
            (
                {
                    "id": m["id"],
                    "name": m["name"],
                    "git_commit": m.get("git_commit"),
                    "csharp_file_count": m.get("csharp_file_count", 0),
                }
                for m in scan.get("reference_mods", [])
            ),
            key=lambda m: m["id"],
        ),
    }
