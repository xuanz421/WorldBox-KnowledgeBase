"""WBKB CLI: python -m wbkb discover | doctor | extract | index | search | symbol | string | show | stats"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import config, discovery, extractor, indexer, query, manifest as manifest_mod, registry as registry_mod, util


def _rows_to_dicts(rows):
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


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
        if args.extract_command == "worldbox":
            result = extractor.perform_extraction(root, registry, force=args.force, extractor_info=extractor_info)
            source_label = registry["sources"]["worldbox"].get("game_version") or "unknown"
        elif args.extract_command == "neomodloader":
            result = extractor.perform_nml_extraction(root, registry, force=args.force, extractor_info=extractor_info)
            nml = registry["sources"]["neomodloader"]
            source_label = f"commit {(nml.get('commit') or 'unknown')[:12]}"
        else:
            print(f"Unknown source: {args.extract_command}", file=sys.stderr)
            return 1
    except extractor.ExtractionError as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        return 1

    manifest = result["manifest"]
    print(f"Source {args.extract_command} {source_label}")
    print(f"Extractor {manifest['extractor']['name']} {manifest['extractor']['version']}")
    print(f"Snapshot {result['snapshot']}")
    mode = manifest.get("source_mode", "decompiled")
    print(f"Mode {mode}")
    print(f"Source files {manifest['output']['csharp_files']} .cs / {manifest['output']['total_files']} total")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Status {result['status']}")
    return 0


def _cmd_extract_status(root: Path, registry: dict) -> int:
    extractor_info = extractor.detect_extractor(root)

    source = registry.get("sources", {}).get("worldbox")
    if source and source.get("assembly"):
        sha = source["assembly"].get("sha256", "")
        print(f"WorldBox Assembly: {sha[:12]}… ({source.get('game_version') or 'unknown'})")
        state = extractor.snapshot_state(root, registry, extractor_info)
        print(f"WorldBox Snapshot: {state['snapshot']} [{state['state']}]")

    nml = registry.get("sources", {}).get("neomodloader")
    if nml:
        nml_state = extractor.nml_snapshot_state(root, registry, extractor_info)
        label = nml_state.get("snapshot") or nml_state.get("reason", "?")
        print(f"NML Snapshot:      {label} [{nml_state['state']}]")
    print(f"Extractor: {extractor_info['name'] + ' ' + extractor_info['version'] if extractor_info else 'MISSING'}")
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
        print(f"Schema:            v{meta.get('schema_version', '?')}"
              f" (indexer {meta.get('indexer_version', '?')}, resolver {meta.get('resolver_version', '?')})")
        print(f"WorldBox snapshot: {meta.get('snapshot:worldbox', '-')}")
        print(f"NML snapshot:      {meta.get('snapshot:neomodloader', '-')}")
        print(f"State: {state['state']}" + (f" ({state['reason']})" if state.get("reason") else ""))
        return 0 if state["state"] == "OK" else 1

    try:
        result = indexer.perform_unified_indexing(root, registry, force=args.force, requested=args.index_command)
    except indexer.IndexError_ as exc:
        print(f"Index failed: {exc}", file=sys.stderr)
        return 1
    included = ", ".join(s["source_id"] for s in result["specs"])
    if result["status"] == "UNCHANGED":
        print(f"Sources {included}")
        print("Status UNCHANGED")
        return 0
    stats = result["stats"]
    counts = stats["counts"]
    print(f"Sources {included}")
    print(f"Parsed {counts['files']} files"
          f" (OK {stats['parse'].get('OK', 0)} / PARTIAL {stats['parse'].get('PARTIAL', 0)}"
          f" / FAILED {stats['parse'].get('FAILED', 0)})")
    print(f"Types {counts['types']}  Methods {counts['methods']}"
          f"  Fields {counts['fields']}  Properties {counts['properties']}")
    print(f"Strings {counts['strings']}  Inheritance {counts['inheritance']}")
    print(f"Symbol refs {counts['symbol_references']}  Method calls {counts['method_calls']}"
          f"  Type refs {counts['type_references']}")
    print(f"Status {result['status']}")
    return 0


def cmd_search(args) -> int:
    root = repo_root()
    try:
        result = query.search(root, args.query, limit=args.limit, exact=args.exact,
                              include_generated=args.all, source=args.source)
    except query.QueryError as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    limit = result["limit"]
    if args.json:
        payload = {key: _rows_to_dicts(value) for key, value in result.items() if key != "limit"}
        payload["limit"] = limit
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Types")
    print("-----")
    for row in result["types"]:
        print(f"  [{row['source_id']}] [{row['kind']}] {row['full_name']}  ({row['relative_path']}:{row['start_line']})")
    if not result["types"]:
        print("  (none)")

    print("\nMethods")
    print("-------")
    for row in result["methods"]:
        print(f"  [{row['source_id']}] {row['type_full']}.{row['signature']}  ({row['relative_path']}:{row['start_line']})")
    if not result["methods"]:
        print("  (none)")

    print("\nFields")
    print("------")
    for row in result["fields"]:
        print(f"  [{row['source_id']}] {row['type_full']}.{row['name']} : {row['field_type']}  ({row['relative_path']}:{row['start_line']})")
    if not result["fields"]:
        print("  (none)")

    print("\nProperties")
    print("----------")
    for row in result["properties"]:
        print(f"  [{row['source_id']}] {row['type_full']}.{row['name']} : {row['property_type']}  ({row['relative_path']}:{row['start_line']})")
    if not result["properties"]:
        print("  (none)")

    print("\nStrings")
    print("-------")
    for row in result["strings"]:
        print(f'  [{row["source_id"]}] "{row["value"]}"  {row["relative_path"]}:{row["start_line"]}')
    if not result["strings"]:
        print("  (none)")

    print("\nFiles")
    print("-----")
    for row in result["files"]:
        print(f"  [{row['source_id']}] {row['relative_path']}")
    if not result["files"]:
        print("  (none)")

    suffix = f", source: {args.source}" if args.source else ""
    print(f"\n(limit {limit} per category{suffix})")
    return 0


def cmd_symbol(args) -> int:
    root = repo_root()
    try:
        result = query.symbol(root, args.name, include_generated=args.all, source=args.source)
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
        print("Index database missing; run: python -m wbkb index all")
        return 1
    stats = indexer.read_stats(path)
    meta = stats["meta"]
    counts = stats["counts"]
    print(f"Indexer           {meta.get('indexer_version', '?')} (schema v{meta.get('schema_version', '?')},"
          f" resolver {meta.get('resolver_version', '?')})")
    print(f"Built at          {meta.get('built_at', '?')}")
    print(f"WorldBox          {meta.get('worldbox_version', '?')}  assembly {meta.get('assembly_sha256', '?')[:12]}…"
          f"  snapshot {meta.get('snapshot:worldbox', '-')}")
    if meta.get("snapshot:neomodloader"):
        print(f"NeoModLoader      commit {meta.get('nml_commit', '?')[:12] or '?'}"
              f"  mode {meta.get('nml_source_mode', '?')}"
              f"  snapshot {meta.get('snapshot:neomodloader', '-')}")
    ref_status = stats.get("ref_status", {})
    print(f"Source files      {counts['files']}"
          f"  (parse OK {stats['parse'].get('OK', 0)} / PARTIAL {stats['parse'].get('PARTIAL', 0)}"
          f" / FAILED {stats['parse'].get('FAILED', 0)};"
          f" ref pass {ref_status.get('OK', 0)}/{sum(ref_status.values())})")
    try:
        per_source = query.source_stats(root)
    except query.QueryError:
        per_source = None
    if per_source:
        for source_id, row in per_source["per_source"].items():
            print(f"[{source_id}]")
            print(f"  Files {row['files']}  Types {row['types']}  Methods {row['methods']}"
                  f"  Fields {row['fields']}  Properties {row['properties']}  Strings {row['strings']}")
        cross = per_source.get("cross", {})
        if cross:
            print("Cross-source edges (neomodloader → worldbox, resolved)")
            print(f"  type refs       {cross.get('nml_to_worldbox_type_refs', 0)}")
            print(f"  method calls    {cross.get('nml_to_worldbox_method_calls', 0)}")
            print(f"  member refs     {cross.get('nml_to_worlddb_symbol_refs', cross.get('nml_to_worldbox_symbol_refs', 0))}")
    cr = stats.get("call_resolution", {})
    rr = stats.get("ref_resolution", {})
    total_calls = sum(cr.values()) or 1
    total_refs = sum(rr.values()) or 1
    print(f"Symbol references {counts.get('symbol_references', 0)}"
          f"  (resolved {rr.get('resolved', 0)} {rr.get('resolved', 0) / total_refs:.0%}"
          f" / ambiguous {rr.get('ambiguous', 0)} {rr.get('ambiguous', 0) / total_refs:.0%}"
          f" / unresolved {rr.get('unresolved', 0)} {rr.get('unresolved', 0) / total_refs:.0%}"
          f" / external {rr.get('external', 0)} {rr.get('external', 0) / total_refs:.0%})")
    print(f"Method calls      {counts.get('method_calls', 0)}"
          f"  (resolved {cr.get('resolved', 0)} {cr.get('resolved', 0) / total_calls:.0%}"
          f" / ambiguous {cr.get('ambiguous', 0)} {cr.get('ambiguous', 0) / total_calls:.0%}"
          f" / unresolved {cr.get('unresolved', 0)} {cr.get('unresolved', 0) / total_calls:.0%}"
          f" / external {cr.get('external', 0)} {cr.get('external', 0) / total_calls:.0%})")
    print(f"Type references   {counts.get('type_references', 0)}")
    print(f"Database size     {_fmt_size(stats['db_size'])}  ({path.relative_to(root)})")
    return 0


def cmd_refs(args) -> int:
    root = repo_root()
    try:
        result = query.refs(root, args.symbol, limit=args.limit, include_all=args.all, from_source=args.from_source)
    except query.QueryError as exc:
        print(f"Refs failed: {exc}", file=sys.stderr)
        return 1
    if result["target"]["kind"] == "not_found":
        print(f"Symbol not found: {args.symbol}")
        return 1
    if result["target"]["kind"] == "ambiguous":
        print(f"Ambiguous symbol: {args.symbol}")
        for candidate in result["target"]["candidates"]:
            print(f"  {candidate}")
        return 2
    if args.json:
        print(json.dumps({"definition": result["definition"], "references": result["references"]}, ensure_ascii=False, indent=2))
        return 0
    print("Definition")
    print("----------")
    print(f"  {result['definition'] or '?'}")
    print("\nReferences")
    print("----------")
    for ref in result["references"]:
        prefix = f"[{ref['from_source']}] " if ref.get("from_source") else ""
        print(f"  {prefix}{ref['location']}  {ref['kind']}  [{ref['status']}]")
    if not result["references"]:
        print("  (none)")
    if args.context > 0:
        for ref in result["references"][: args.limit]:
            _print_context(root, ref["location"], args.context)
    print(f"\n(limit {args.limit}" + (", --all)" if args.all else ", resolved only)"))
    return 0


def _print_context(root: Path, location: str, context: int) -> None:
    try:
        snippet = query.show(root, location, context=context)
    except query.QueryError:
        return
    print(f"\n  --- {location} ---")
    for number, text in snippet["lines"]:
        marker = ">" if number == snippet["line"] else " "
        print(f"  {marker}{number:6d}  {text}")


def cmd_callers(args) -> int:
    root = repo_root()
    try:
        result = query.callers(root, args.symbol, limit=args.limit, include_all=args.all, source=args.source)
    except query.QueryError as exc:
        print(f"Callers failed: {exc}", file=sys.stderr)
        return 1
    if result["target"]["kind"] == "ambiguous":
        print(f"Ambiguous symbol: {args.symbol}")
        for candidate in result["target"]["candidates"]:
            print(f"  {candidate}")
        return 2
    if args.json:
        payload = {key: value for key, value in result.items() if key != "target"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Caller")
    print("------")
    for caller in result["callers"]:
        print(f"  {caller['caller']}  [{caller['status']}]")
    if not result["callers"]:
        print("  (none)")
    print(f"\n(limit {args.limit})")
    return 0


def cmd_callees(args) -> int:
    root = repo_root()
    try:
        result = query.callees(root, args.symbol, depth=args.depth, limit=args.limit)
    except query.QueryError as exc:
        print(f"Callees failed: {exc}", file=sys.stderr)
        return 1
    if result["target"]["kind"] == "ambiguous":
        print(f"Ambiguous symbol: {args.symbol}")
        for candidate in result["target"]["candidates"]:
            print(f"  {candidate}")
        return 2
    if args.json:
        payload = {key: value for key, value in result.items() if key != "target"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    def dump(entries, indent=2):
        for entry in entries:
            print(" " * indent + f"-> {entry['call']}  [{entry['status']}]  {entry['location']}")
            dump(entry["children"], indent + 2)

    print("Callees")
    print("-------")
    dump(result["tree"])
    if not result["tree"]:
        print("  (none)")
    print(f"\n(depth {args.depth}, limit {args.limit})")
    return 0


def cmd_derived(args) -> int:
    root = repo_root()
    try:
        result = query.derived(root, args.symbol, recursive=args.recursive, source=getattr(args, "source", None))
    except query.QueryError as exc:
        print(f"Derived failed: {exc}", file=sys.stderr)
        return 1
    if not result.get("found"):
        print(f"Type not found: {args.symbol}")
        return 1
    if result.get("ambiguous"):
        print(f"Ambiguous type: {args.symbol}")
        for candidate in result["candidates"]:
            print(f"  {candidate}")
        return 2
    label = "Derived (recursive)" if result["recursive"] else "Derived (direct)"
    print(label)
    print("-" * len(label))
    for name in result["derived"]:
        print(f"  {name}")
    if not result["derived"]:
        print("  (none)")
    return 0


def cmd_overrides(args) -> int:
    root = repo_root()
    try:
        result = query.overrides(root, args.symbol)
    except query.QueryError as exc:
        print(f"Overrides failed: {exc}", file=sys.stderr)
        return 1
    print("Overrides")
    print("---------")
    for entry in result["overrides"]:
        print(f"  {entry}")
    if not result["overrides"]:
        print("  (none)")
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

    nml_source_state = "MISSING"
    if registry is not None and registry.get("sources", {}).get("neomodloader"):
        nml_state = extractor.nml_snapshot_state(root, registry, extractor_info)
        nml_source_state = nml_state["state"].replace("OK-EXTRACTOR-CHANGED", "OK")
    print(f"{'NeoModLoader Src':<16}{nml_source_state}")

    index = indexer.index_state(root, registry)
    print(f"{'WorldBox Index':<16}{index['state']}")
    meta = index.get("meta") or {}
    schema = meta.get("schema_version")
    nml_indexed = meta.get("snapshot:neomodloader")
    if index["state"] == "OK":
        nml_index_state = "OK" if nml_indexed else "MISSING"
    else:
        nml_index_state = "MISSING" if not nml_indexed else index["state"]
    print(f"{'NeoModLoader Idx':<16}{nml_index_state}")

    if index["state"] == "OK" and nml_indexed:
        try:
            cross = query.source_stats(root).get("cross", {})
            graph_state = "OK" if sum(cross.values()) > 0 else "EMPTY"
        except query.QueryError:
            graph_state = "BROKEN"
    elif nml_indexed:
        graph_state = index["state"]
    else:
        graph_state = "MISSING"
    print(f"{'Cross-Source':<16}{graph_state}")
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
    extract_nml = extract_sub.add_parser("neomodloader", help="decompile the registered NML core assemblies")
    extract_nml.add_argument("--force", action="store_true", help="re-extract even if snapshot exists")
    extract_sub.add_parser("status", help="show current assembly/snapshot state")

    index_parser = sub.add_parser("index", help="build the unified SQLite index")
    index_sub = index_parser.add_subparsers(dest="index_command", required=True)
    for name, help_text in (
        ("worldbox", "rebuild the unified index (WorldBox + any other available sources)"),
        ("neomodloader", "rebuild the unified index including the NML snapshot"),
        ("all", "rebuild the unified index from every available snapshot"),
    ):
        index_src = index_sub.add_parser(name, help=help_text)
        index_src.add_argument("--force", action="store_true", help="rebuild even if index is current")
    index_sub.add_parser("status", help="show current index state")

    search_parser = sub.add_parser("search", help="search types/methods/fields/properties/strings/files")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    search_parser.add_argument("--exact", action="store_true", help="exact match instead of substring")
    search_parser.add_argument("--all", action="store_true", help="include compiler-generated symbols")
    search_parser.add_argument("--source", help="restrict to a source (worldbox / neomodloader)")
    search_parser.add_argument("--json", action="store_true", help="machine-readable output")

    symbol_parser = sub.add_parser("symbol", help="inspect a type by name")
    symbol_parser.add_argument("name")
    symbol_parser.add_argument("--all", action="store_true", help="include compiler-generated types")
    symbol_parser.add_argument("--source", help="restrict to a source (worldbox / neomodloader)")
    symbol_parser.add_argument("--json", action="store_true", help="machine-readable output")

    refs_parser = sub.add_parser("refs", help="definition + references of a symbol (Type or Type.member)")
    refs_parser.add_argument("symbol")
    refs_parser.add_argument("--limit", type=int, default=query.RELATION_LIMIT)
    refs_parser.add_argument("--all", action="store_true", help="include unresolved/external references")
    refs_parser.add_argument("--from-source", dest="from_source", help="only references made by this source")
    refs_parser.add_argument("--context", type=int, default=0, help="attach source context lines")
    refs_parser.add_argument("--json", action="store_true", help="machine-readable output")

    callers_parser = sub.add_parser("callers", help="who calls this method")
    callers_parser.add_argument("symbol")
    callers_parser.add_argument("--limit", type=int, default=query.RELATION_LIMIT)
    callers_parser.add_argument("--all", action="store_true", help="include ambiguous/unresolved callers")
    callers_parser.add_argument("--source", help="only callers from this source")
    callers_parser.add_argument("--json", action="store_true", help="machine-readable output")

    callees_parser = sub.add_parser("callees", help="what this method calls")
    callees_parser.add_argument("symbol")
    callees_parser.add_argument("--depth", type=int, default=1, help="1-5, default 1")
    callees_parser.add_argument("--limit", type=int, default=query.RELATION_LIMIT)
    callees_parser.add_argument("--json", action="store_true", help="machine-readable output")

    derived_parser = sub.add_parser("derived", help="types directly inheriting from a type")
    derived_parser.add_argument("symbol")
    derived_parser.add_argument("--recursive", action="store_true")
    derived_parser.add_argument("--source", help="only derived types from this source")

    overrides_parser = sub.add_parser("overrides", help="derived overrides of a base method")
    overrides_parser.add_argument("symbol", help="Type.method")

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
    if args.command == "refs":
        return cmd_refs(args)
    if args.command == "callers":
        return cmd_callers(args)
    if args.command == "callees":
        return cmd_callees(args)
    if args.command == "derived":
        return cmd_derived(args)
    if args.command == "overrides":
        return cmd_overrides(args)
    return cmd_doctor(args)


if __name__ == "__main__":
    sys.exit(main())
