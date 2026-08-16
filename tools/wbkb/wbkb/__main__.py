"""WBKB CLI: python -m wbkb discover | doctor | extract | index | search | symbol | string | show | stats"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config, discovery, extractor, indexer, query, manifest as manifest_mod, registry as registry_mod, util


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


def cmd_index(args) -> int:
    root = repo_root()
    registry = registry_mod.load_local_registry(root)
    if registry is None:
        print("Registry missing; run: python -m wbkb discover", file=sys.stderr)
        return 1

    if args.index_command == "status":
        state = indexer.index_state(root, registry)
        meta = state.get("meta") or {}
        print(f"WorldBox version: {meta.get('worldbox_version', '?')}")
        print(f"Snapshot: {meta.get('source_snapshot_id', '?')}")
        print(f"Indexer: {meta.get('indexer_version', '?')} schema v{meta.get('schema_version', '?')}")
        print(f"State: {state['state']}" + (f" ({state['reason']})" if state.get("reason") else ""))
        return 0 if state["state"] == "OK" else 1

    try:
        result = indexer.perform_indexing(root, registry, force=args.force)
    except indexer.IndexError_ as exc:
        print(f"Index failed: {exc}", file=sys.stderr)
        return 1
    if result["status"] == "UNCHANGED":
        print(f"Snapshot {result['snapshot']}")
        print("Status UNCHANGED")
        return 0
    stats = result["stats"]
    print(f"Snapshot {result['snapshot']}")
    print(f"Parsed {stats['counts']['files']} files"
          f" (OK {stats['parse'].get('OK', 0)} / PARTIAL {stats['parse'].get('PARTIAL', 0)}"
          f" / FAILED {stats['parse'].get('FAILED', 0)})")
    print(f"Types {stats['counts']['types']}  Methods {stats['counts']['methods']}"
          f"  Fields {stats['counts']['fields']}  Properties {stats['counts']['properties']}")
    print(f"Strings {stats['counts']['strings']}  Inheritance {stats['counts']['inheritance']}")
    print(f"Status {result['status']}")
    return 0


def cmd_search(args) -> int:
    root = repo_root()
    try:
        result = query.search(root, args.query, limit=args.limit, exact=args.exact, include_generated=args.all)
    except query.QueryError as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    limit = result["limit"]

    print("Types")
    print("-----")
    for row in result["types"]:
        print(f"  [{row['kind']}] {row['full_name']}  ({row['relative_path']}:{row['start_line']})")
    if not result["types"]:
        print("  (none)")

    print("\nMethods")
    print("-------")
    for row in result["methods"]:
        print(f"  {row['type_full']}.{row['signature']}  ({row['relative_path']}:{row['start_line']})")
    if not result["methods"]:
        print("  (none)")

    print("\nFields")
    print("------")
    for row in result["fields"]:
        print(f"  {row['type_full']}.{row['name']} : {row['field_type']}  ({row['relative_path']}:{row['start_line']})")
    if not result["fields"]:
        print("  (none)")

    print("\nProperties")
    print("----------")
    for row in result["properties"]:
        print(f"  {row['type_full']}.{row['name']} : {row['property_type']}  ({row['relative_path']}:{row['start_line']})")
    if not result["properties"]:
        print("  (none)")

    print("\nStrings")
    print("-------")
    for row in result["strings"]:
        print(f'  "{row["value"]}"  {row["relative_path"]}:{row["start_line"]}')
    if not result["strings"]:
        print("  (none)")

    print("\nFiles")
    print("-----")
    for row in result["files"]:
        print(f"  {row['relative_path']}")
    if not result["files"]:
        print("  (none)")

    print(f"\n(limit {limit} per category)")
    return 0


def cmd_symbol(args) -> int:
    root = repo_root()
    try:
        result = query.symbol(root, args.name, include_generated=args.all)
    except query.QueryError as exc:
        print(f"Symbol lookup failed: {exc}", file=sys.stderr)
        return 1
    if not result["found"]:
        print(f"Type not found: {args.name}")
        return 1
    if result["ambiguous"]:
        print(f"Ambiguous type name: {args.name}")
        for candidate in result["candidates"]:
            print(f"  {candidate}")
        return 2
    t = result["type"]
    print(f"Type\n{t['name']}")
    print(f"\nFull name\n{t['full_name']}")
    print(f"\nKind\n{t['kind']}")
    print(f"\nNamespace\n{t['namespace'] or '-'}")
    print(f"\nFile\n{t['relative_path']}:{t['start_line']}-{t['end_line']}")
    mods = [m for m, on in (("abstract", t["is_abstract"]), ("static", t["is_static"]), ("sealed", t["is_sealed"])) if on]
    print(f"\nModifiers\n{t['visibility']}{' ' + ' '.join(mods) if mods else ''}")
    print("\nBase / interfaces")
    if result["bases"]:
        for b in result["bases"]:
            print(f"  {b['relation']}: {b['target_name']}")
    else:
        print("  (none)")
    if result["derived"]:
        print("\nDerived types (direct)")
        for name in result["derived"]:
            print(f"  {name}")
    print(f"\nMethods ({len(result['methods'])})")
    for m in result["methods"][:50]:
        flags = "".join(s for s, on in (("S", m["is_static"]), ("V", m["is_virtual"]), ("O", m["is_override"])) if on)
        print(f"  {m['visibility']} {m['signature']}" + (f" [{flags}]" if flags else ""))
    if len(result["methods"]) > 50:
        print(f"  ... and {len(result['methods']) - 50} more")
    print(f"\nFields ({len(result['fields'])})")
    for f in result["fields"][:50]:
        print(f"  {f['visibility']} {f['name']} : {f['field_type']}" + (" const" if f["is_const"] else ""))
    if len(result["fields"]) > 50:
        print(f"  ... and {len(result['fields']) - 50} more")
    print(f"\nProperties ({len(result['properties'])})")
    for p in result["properties"][:50]:
        accessors = ("get" if p["has_getter"] else "") + (" set" if p["has_setter"] else "")
        print(f"  {p['name']} : {p['property_type']} {{ {accessors.strip()} }}")
    if len(result["properties"]) > 50:
        print(f"  ... and {len(result['properties']) - 50} more")
    return 0


def cmd_string(args) -> int:
    root = repo_root()
    try:
        rows = query.string_search(root, args.value, limit=args.limit, exact=args.exact)
    except query.QueryError as exc:
        print(f"String search failed: {exc}", file=sys.stderr)
        return 1
    for row in rows:
        print(f'"{row["value"]}"  [{row["classification"]}]  {row["relative_path"]}:{row["start_line"]}')
    if not rows:
        print("(no occurrences)")
    print(f"\n(limit {args.limit})")
    return 0


def cmd_show(args) -> int:
    root = repo_root()
    try:
        result = query.show(root, args.location, context=args.context)
    except query.QueryError as exc:
        print(f"Show failed: {exc}", file=sys.stderr)
        return 1
    for number, text in result["lines"]:
        marker = ">" if number == result["line"] else " "
        print(f"{marker}{number:6d}  {text}")
    return 0


def cmd_stats(_args) -> int:
    root = repo_root()
    path = indexer.db_path(root)
    if not path.is_file():
        print("Index database missing; run: python -m wbkb index worldbox")
        return 1
    stats = indexer.read_stats(path)
    meta = stats["meta"]
    counts = stats["counts"]
    print(f"WorldBox version  {meta.get('worldbox_version', '?')}")
    print(f"Assembly          {meta.get('assembly_sha256', '?')[:12]}…")
    print(f"Snapshot          {meta.get('source_snapshot_id', '?')}")
    print(f"Extractor         {meta.get('extractor_name', '?')} {meta.get('extractor_version', '?')}")
    print(f"Indexer           {meta.get('indexer_version', '?')} (schema v{meta.get('schema_version', '?')})")
    print(f"Built at          {meta.get('built_at', '?')}")
    print(f"Source files      {counts['files']}"
          f"  (OK {stats['parse'].get('OK', 0)} / PARTIAL {stats['parse'].get('PARTIAL', 0)}"
          f" / FAILED {stats['parse'].get('FAILED', 0)})")
    print(f"Types             {counts['types']}")
    print(f"Methods           {counts['methods']}")
    print(f"Fields            {counts['fields']}")
    print(f"Properties        {counts['properties']}")
    print(f"Strings           {counts['strings']}")
    print(f"Inheritance edges {counts['inheritance']}")
    print(f"Database size     {_fmt_size(stats['db_size'])}  ({path.relative_to(root)})")
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

    index = indexer.index_state(root, registry)
    print(f"{'WorldBox Index':<16}{index['state']}")
    schema = (index.get("meta") or {}).get("schema_version")
    print(f"{'SQLite Schema':<16}{'v' + schema if schema else '-'}")

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

    index_parser = sub.add_parser("index", help="build the structured SQLite index")
    index_sub = index_parser.add_subparsers(dest="index_command", required=True)
    index_worldbox = index_sub.add_parser("worldbox", help="index the current WorldBox source snapshot")
    index_worldbox.add_argument("--force", action="store_true", help="rebuild even if index is current")
    index_sub.add_parser("status", help="show current index state")

    search_parser = sub.add_parser("search", help="search types/methods/fields/properties/strings/files")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    search_parser.add_argument("--exact", action="store_true", help="exact match instead of substring")
    search_parser.add_argument("--all", action="store_true", help="include compiler-generated symbols")

    symbol_parser = sub.add_parser("symbol", help="inspect a type by name")
    symbol_parser.add_argument("name")
    symbol_parser.add_argument("--all", action="store_true", help="include compiler-generated types")

    string_parser = sub.add_parser("string", help="search string literal occurrences")
    string_parser.add_argument("value")
    string_parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    string_parser.add_argument("--exact", action="store_true")

    show_parser = sub.add_parser("show", help="show source context from the extraction snapshot")
    show_parser.add_argument("location", help="<relative/path.cs>[:line]")
    show_parser.add_argument("--context", type=int, default=5)

    sub.add_parser("stats", help="index statistics")

    args = parser.parse_args(argv)
    if args.command == "discover":
        return cmd_discover(args)
    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "index":
        return cmd_index(args)
    if args.command == "search":
        return cmd_search(args)
    if args.command == "symbol":
        return cmd_symbol(args)
    if args.command == "string":
        return cmd_string(args)
    if args.command == "show":
        return cmd_show(args)
    if args.command == "stats":
        return cmd_stats(args)
    return cmd_doctor(args)


if __name__ == "__main__":
    sys.exit(main())
