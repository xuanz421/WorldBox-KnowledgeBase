"""WBKB CLI: python -m wbkb discover | doctor"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config, discovery, manifest as manifest_mod, registry as registry_mod, util


def repo_root() -> Path:
    env = os.environ.get("WBKB_ROOT")
    if env:
        return Path(env).resolve()
    # tools/wbkb/wbkb/__main__.py -> parents[3] is the repository root
    return Path(__file__).resolve().parents[3]


def _fmt_size(n) -> str:
    if n is None:
        return "?"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.1f} KB"
    return f"{n} B"


def _short(sha) -> str:
    return sha[:12] + "…" if sha else "?"


def cmd_discover(_args) -> int:
    root = repo_root()
    scan = discovery.discover_sources(root)

    print(f"Config origin: {scan['config_origin']}")
    if scan["config_written"]:
        config.save_local_config_if_changed(root, scan["config"])
        print(f"Config written: {config.local_config_path(root).relative_to(root)}")
    elif scan["config_origin"] == "existing-config":
        print(f"Config: using existing {config.local_config_path(root).relative_to(root)}")

    wb = scan["worldbox"]
    if wb["root"]:
        print(f"WorldBox: {wb['root']}")
        version = wb.get("game_version") or "unknown"
        print(f"  version: {version} ({wb['game_version_status']})  buildid: {wb['steam_buildid'] or '?'}  exe: {'yes' if wb['exe_found'] else 'no'}")
    else:
        print("WorldBox: NOT FOUND")

    if wb["assembly"]:
        a = wb["assembly"]
        print(f"Assembly-CSharp: OK  {_short(a['sha256'])}  {_fmt_size(a['size'])}")
    else:
        print("Assembly-CSharp: MISSING")
    if wb["publicized"]:
        p = wb["publicized"]
        alt = f"  (+{len(wb['publicized_alternatives'])} alternatives)" if wb["publicized_alternatives"] else ""
        print(f"Publicized: OK  {_short(p['sha256'])}  {_fmt_size(p['size'])}{alt}")
    else:
        alt = f"  ({len(wb['publicized_alternatives'])} alternatives found)" if wb["publicized_alternatives"] else ""
        print(f"Publicized: MISSING{alt}")

    nml = scan["neomodloader"]
    if nml["root"] or nml["assemblies"]:
        commit = nml.get("commit")
        print(f"NeoModLoader: OK  commit={_short(commit) if commit else 'unknown'}  assemblies={len(nml['assemblies'])}")
    else:
        print("NeoModLoader: MISSING")

    mods = scan["reference_mods"]
    print(f"Reference mods: {len(mods)}")

    old_registry = registry_mod.load_local_registry(root)
    new_registry = registry_mod.build_local_registry(scan, util.now_iso())
    changes = registry_mod.diff_registries(old_registry, new_registry)

    if old_registry is None and new_registry["sources"]:
        print("Changes: first run, all sources recorded as NEW")
    else:
        counts = {}
        for status in changes.values():
            counts[status] = counts.get(status, 0) + 1
        summary = "  ".join(f"{k}={counts[k]}" for k in ("NEW", "CHANGED", "MISSING", "UNCHANGED") if k in counts)
        print(f"Changes: {summary or 'none'}")
        for sid, status in changes.items():
            if status != "UNCHANGED":
                print(f"  {sid}: {status}")

    if registry_mod.save_json_if_changed(registry_mod.local_registry_path(root), new_registry):
        print(f"Registry: written ({registry_mod.local_registry_path(root).relative_to(root)})")
    else:
        print("Registry: unchanged")

    new_manifest = manifest_mod.build_manifest(scan, util.now_iso())
    if registry_mod.save_json_if_changed(manifest_mod.manifest_path(root), new_manifest):
        print(f"Manifest: written ({manifest_mod.manifest_path(root).relative_to(root)})")
    else:
        print("Manifest: unchanged")

    for problem in scan["problems"]:
        print(f"Note: {problem}", file=sys.stderr)

    if wb["root"] is None:
        print("Blocked: WorldBox not found; set config/wbkb.local.json manually.", file=sys.stderr)
        return 1
    return 0


def cmd_doctor(_args) -> int:
    root = repo_root()
    scan = discovery.discover_sources(root)
    wb = scan["worldbox"]
    nml = scan["neomodloader"]

    print(f"{'Config':<16}{_doctor_config_state(root, scan)}")
    print(f"{'WorldBox':<16}{'OK' if wb['root'] else 'MISSING'}")

    if wb["assembly"]:
        try:
            util.sha256_file(wb["assembly"]["path"])
            print(f"{'Assembly':<16}OK")
        except OSError:
            print(f"{'Assembly':<16}FAIL (hash unreadable)")
    else:
        print(f"{'Assembly':<16}MISSING")

    print(f"{'Publicized':<16}{'OK' if wb['publicized'] else 'MISSING'}")
    print(f"{'NeoModLoader':<16}{'OK' if (nml['root'] or nml['assemblies']) else 'MISSING'}")

    valid_roots = [r for r in scan["config"].get("reference_mods_roots", []) if Path(r).is_dir()]
    if scan["config"].get("reference_mods_roots"):
        if valid_roots:
            print(f"{'Reference Mods':<16}{len(scan['reference_mods'])} detected")
        else:
            print(f"{'Reference Mods':<16}MISSING")
    else:
        print(f"{'Reference Mods':<16}not configured")

    registry = registry_mod.load_local_registry(root)
    if registry is None:
        print(f"{'Registry':<16}MISSING (run: python -m wbkb discover)")
    elif registry_mod.registry_paths_valid(registry):
        print(f"{'Registry':<16}OK ({len(registry['sources'])} sources)")
    else:
        print(f"{'Registry':<16}STALE (recorded paths invalid; run: python -m wbkb discover)")

    hard_ok = wb["root"] and wb["assembly"]
    return 0 if hard_ok else 1


def _doctor_config_state(root: Path, scan: dict) -> str:
    path = config.local_config_path(root)
    if path.is_file() and scan["config_origin"] == "existing-config":
        return "OK"
    if path.is_file():
        return "STALE (paths invalid; fix or delete to re-discover)"
    if scan["worldbox"]["root"]:
        return "discovered (not saved)"
    return "MISSING"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wbkb", description="WorldBox Knowledge Base tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="discover external sources, update registry/manifest")
    sub.add_parser("doctor", help="short health check of configured sources")
    args = parser.parse_args(argv)
    if args.command == "discover":
        return cmd_discover(args)
    return cmd_doctor(args)


if __name__ == "__main__":
    sys.exit(main())
