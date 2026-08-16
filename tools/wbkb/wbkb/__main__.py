"""WBKB CLI: python -m wbkb discover | doctor | extract"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config, discovery, extractor, manifest as manifest_mod, registry as registry_mod, util


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
    if scan["worldbox"]["root"] is None and sys.stdin.isatty():
        # last resort: interactive user input
        print("WorldBox not found automatically.")
        answer = input("Enter WorldBox installation path (empty to abort): ").strip().strip('"')
        if answer and Path(answer).is_dir():
            scan = discovery.discover_sources(root, worldbox_root_override=answer)

    print(f"Config origin: {scan['config_origin']}")
    if scan["config_written"]:
        config.save_local_config_if_changed(root, scan["config"])
        print(f"Config written: {config.local_config_path(root).relative_to(root)}")
    elif scan["config_origin"] == "local-config":
        print(f"Config: using local {config.local_config_path(root).relative_to(root)}")

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


def cmd_extract(args) -> int:
    root = repo_root()
    registry = registry_mod.load_local_registry(root)
    if registry is None:
        print("Registry missing; run: python -m wbkb discover", file=sys.stderr)
        return 1

    if args.extract_command == "status":
        return _cmd_extract_status(root, registry)

    extractor_info = extractor.detect_extractor(root)
    if extractor_info is None:
        print("Decompiler       MISSING", file=sys.stderr)
        print("Run `dotnet tool restore` in the WBKB root (requires .NET SDK).", file=sys.stderr)
        return 1

    try:
        result = extractor.perform_extraction(root, registry, force=args.force, extractor_info=extractor_info)
    except extractor.ExtractionError as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        return 1

    source = registry["sources"]["worldbox"]
    manifest = result["manifest"]
    print(f"WorldBox {source.get('game_version') or 'unknown'}")
    print(f"Assembly {manifest['assembly']['sha256'][:12]}…")
    print(f"Extractor {manifest['extractor']['name']} {manifest['extractor']['version']}")
    print(f"Snapshot {result['snapshot']}")
    print(f"Source files {manifest['output']['csharp_files']} .cs / {manifest['output']['total_files']} total")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Status {result['status']}")
    return 0


def _cmd_extract_status(root: Path, registry: dict) -> int:
    source = registry.get("sources", {}).get("worldbox")
    if not source or not source.get("assembly"):
        print("Current Assembly: none (run: python -m wbkb discover)")
        return 1
    sha = source["assembly"].get("sha256", "")
    print(f"Current Assembly: {sha[:12]}… ({source.get('game_version') or 'unknown'})")
    extractor_info = extractor.detect_extractor(root)
    print(f"Extractor: {extractor_info['name'] + ' ' + extractor_info['version'] if extractor_info else 'MISSING'}")
    state = extractor.snapshot_state(root, registry, extractor_info)
    print(f"Snapshot: {state['snapshot']} [{state['state']}]")
    print(f"Status: {'OK' if state['state'] == 'OK' else state['state']}")
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

    extractor_info = extractor.detect_extractor(root)
    print(f"{'Decompiler':<16}{'OK' if extractor_info else 'MISSING'}"
          + (f" {extractor_info['name']} {extractor_info['version']}" if extractor_info else ""))

    if registry is not None and registry.get("sources", {}).get("worldbox"):
        state = extractor.snapshot_state(root, registry, extractor_info)
        print(f"{'WorldBox Source':<16}{state['state'].replace('OK-EXTRACTOR-CHANGED', 'OK')}")
    else:
        print(f"{'WorldBox Source':<16}MISSING")

    hard_ok = wb["root"] and wb["assembly"]
    return 0 if hard_ok else 1


def _doctor_config_state(root: Path, scan: dict) -> str:
    path = config.local_config_path(root)
    if path.is_file() and scan["config_origin"] == "local-config":
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
    extract_parser = sub.add_parser("extract", help="extract registered sources into local snapshots")
    extract_sub = extract_parser.add_subparsers(dest="extract_command", required=True)
    extract_worldbox = extract_sub.add_parser("worldbox", help="decompile Assembly-CSharp into a source snapshot")
    extract_worldbox.add_argument("--force", action="store_true", help="re-extract even if snapshot exists")
    extract_sub.add_parser("status", help="show current assembly/snapshot state")
    args = parser.parse_args(argv)
    if args.command == "discover":
        return cmd_discover(args)
    if args.command == "extract":
        return cmd_extract(args)
    return cmd_doctor(args)


if __name__ == "__main__":
    sys.exit(main())
