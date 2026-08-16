"""Unified multi-source index builder (Z3-Z5): source snapshots -> SQLite wbkb.db.

Deterministic tooling: parses C# with tree-sitter, builds declarations for
every included source (worldbox, neomodloader, ...), resolves references with
cross-source awareness, validates, then atomically replaces the live
database. Generated data — never committed to Git.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from . import csharp, extractor, references, resolver as resolver_mod, util

SCHEMA_VERSION = 2
INDEXER_VERSION = "3.0.0"
DB_REL = Path("data/generated/index/wbkb.db")
TMP_DB_REL = Path("data/generated/index/wbkb.tmp.db")
SCHEMA_REL = Path("schemas/schema-v2.sql")

MAX_FAILED_RATIO = 0.01  # more than 1% FAILED files => validation failure
CORE_TYPES = ("Actor", "City", "Kingdom")


class IndexError_(RuntimeError):
    pass


# --- Meta / paths -------------------------------------------------------------


def db_path(repo_root: Path) -> Path:
    return Path(repo_root) / DB_REL


def _schema_sql(repo_root: Path) -> str:
    path = Path(repo_root) / SCHEMA_REL
    if not path.is_file():
        raise IndexError_(f"schema file missing: {SCHEMA_REL}")
    return path.read_text(encoding="utf-8")


def read_meta(path: Path) -> dict | None:
    if not Path(path).is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT key, value FROM meta").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return dict(rows)


def snapshot_source_dir(repo_root: Path, snapshot_id: str) -> Path:
    return Path(repo_root) / extractor.SNAPSHOTS_DIR / snapshot_id / "source"


# --- Build core ---------------------------------------------------------------


def _remove_db_file(path: Path) -> None:
    """Best-effort delete; Windows AV/indexers can hold fresh files briefly."""
    for attempt in range(5):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            time.sleep(0.2 * (attempt + 1))


def build_index(
    source_dir: Path,
    db_file: Path,
    meta: dict,
    schema_sql: str,
    require_core_types: bool = False,
    max_failed_ratio: float = MAX_FAILED_RATIO,
) -> dict:
    """WorldBox-only convenience wrapper (Z3/Z4 API) over the unified builder."""
    spec = [{
        "source_id": "worldbox",
        "kind": "game",
        "version": meta.get("worldbox_version"),
        "snapshot_id": meta.get("source_snapshot_id"),
        "source_dir": source_dir,
        "meta": meta,
    }]
    return build_unified_index(spec, db_file, schema_sql, require_core_types=require_core_types,
                               max_failed_ratio=max_failed_ratio)


def build_unified_index(
    sources_spec: list[dict],
    db_file: Path,
    schema_sql: str,
    require_core_types: bool = False,
    max_failed_ratio: float = MAX_FAILED_RATIO,
) -> dict:
    """Build one database containing every source's declarations + references.

    Never touches a pre-existing db_file: builds into a sibling *.build file
    and atomically replaces on success; a pre-existing db survives failures.
    """
    if not sources_spec:
        raise IndexError_("no sources to index")
    db_file = Path(db_file)
    build_target = db_file if not db_file.exists() else db_file.with_name(db_file.name + ".build")
    _remove_db_file(build_target)

    all_cs = {}
    for spec in sources_spec:
        source_dir = Path(spec["source_dir"])
        cs_files = sorted(
            (p for p in source_dir.rglob("*.cs") if p.is_file()),
            key=lambda p: p.relative_to(source_dir).as_posix(),
        )
        if not cs_files:
            raise IndexError_(f"no .cs files found for source {spec['source_id']}")
        all_cs[spec["source_id"]] = cs_files

    conn = sqlite3.connect(build_target)
    try:
        conn.executescript(schema_sql)
        source_db_ids = {}
        for spec in sources_spec:
            cur = conn.execute(
                "INSERT INTO sources (source_id, source_kind, version, content_hash, snapshot_id) VALUES (?,?,?,?,?)",
                (spec["source_id"], spec.get("kind", "library"), spec.get("version"), None, spec.get("snapshot_id")),
            )
            source_db_ids[spec["source_id"]] = cur.lastrowid

        stats = {spec["source_id"]: {"OK": 0, "PARTIAL": 0, "FAILED": 0} for spec in sources_spec}
        totals = {key: 0 for key in ("types", "methods", "fields", "properties", "strings", "inheritance")}
        for spec in sources_spec:
            _index_declarations(conn, spec, all_cs[spec["source_id"]], source_db_ids[spec["source_id"]], stats[spec["source_id"]], totals)

        _resolve_inheritance_unified(conn)
        for spec in sources_spec:
            _run_reference_pass(conn, Path(spec["source_dir"]), all_cs[spec["source_id"]],
                                stats[spec["source_id"]], source_db_ids[spec["source_id"]], spec["source_id"])
        _write_meta(conn, sources_spec, stats, totals)
        conn.commit()
        _validate_index(conn, sources_spec, all_cs, stats, require_core_types, max_failed_ratio)
    except Exception:
        conn.close()
        for leftover in (build_target, build_target.with_name(build_target.name + "-journal")):
            _remove_db_file(leftover)
        raise
    conn.close()
    if build_target != db_file:
        os.replace(build_target, db_file)
    return read_stats(db_file)


def _index_declarations(conn: sqlite3.Connection, spec: dict, cs_files: list[Path], db_source_id: int, stats: dict, totals: dict) -> None:
    source_dir = Path(spec["source_dir"])
    type_db_ids: dict[int, int] = {}
    method_db_ids: dict[int, int] = {}
    seen_full_names: set[str] = set()  # multi-assembly sources may re-emit the
    # same type name (e.g. compiler-generated/module types); first wins,
    # deterministic by sorted file order
    for path in cs_files:
        rel = path.relative_to(source_dir).as_posix()
        data = path.read_bytes()
        result = csharp.parse_source(data)
        stats[result["parse_status"]] += 1

        cur = conn.execute(
            "INSERT INTO files (source_id, relative_path, filename, extension, size, sha256, line_count, parse_status, parse_error)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (db_source_id, rel, path.name, path.suffix.lower(), len(data), util.sha256_file(path),
             data.count(b"\n") + 1, result["parse_status"], result["parse_error"]),
        )
        file_id = cur.lastrowid

        dropped_type_locals: set[int] = set()
        for type_record in result["types"]:
            if type_record["full_name"] in seen_full_names:
                dropped_type_locals.add(type_record["local_id"])
                stats["DUP_TYPES"] = stats.get("DUP_TYPES", 0) + 1
                continue
            seen_full_names.add(type_record["full_name"])
            cur = conn.execute(
                "INSERT INTO types (source_id, file_id, namespace, name, full_name, kind, visibility,"
                " is_abstract, is_static, is_sealed, is_compiler_generated, parent_type_id, start_line, end_line)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (db_source_id, file_id, type_record["namespace"], type_record["name"], type_record["full_name"],
                 type_record["kind"], type_record["visibility"], type_record["is_abstract"], type_record["is_static"],
                 type_record["is_sealed"], type_record["is_compiler_generated"],
                 type_db_ids.get(type_record["parent_local_id"]), type_record["start_line"], type_record["end_line"]),
            )
            type_db_ids[type_record["local_id"]] = cur.lastrowid
            totals["types"] += 1

        for method in result["methods"]:
            if method["type_local_id"] in dropped_type_locals or type_db_ids.get(method["type_local_id"]) is None:
                continue
            cur = conn.execute(
                "INSERT INTO methods (source_id, type_id, file_id, name, signature, return_type, visibility,"
                " is_static, is_virtual, is_override, is_abstract, start_line, end_line)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (db_source_id, type_db_ids.get(method["type_local_id"]), file_id, method["name"],
                 method["signature"], method["return_type"], method["visibility"], method["is_static"],
                 method["is_virtual"], method["is_override"], method["is_abstract"],
                 method["start_line"], method["end_line"]),
            )
            method_db_ids[method["local_id"]] = cur.lastrowid
            totals["methods"] += 1

        for field in result["fields"]:
            if field["type_local_id"] in dropped_type_locals or type_db_ids.get(field["type_local_id"]) is None:
                continue
            conn.execute(
                "INSERT INTO fields (source_id, type_id, file_id, name, field_type, visibility,"
                " is_static, is_readonly, is_const, start_line) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (db_source_id, type_db_ids.get(field["type_local_id"]), file_id, field["name"],
                 field["field_type"], field["visibility"], field["is_static"], field["is_readonly"],
                 field["is_const"], field["start_line"]),
            )
            totals["fields"] += 1

        for prop in result["properties"]:
            if prop["type_local_id"] in dropped_type_locals or type_db_ids.get(prop["type_local_id"]) is None:
                continue
            conn.execute(
                "INSERT INTO properties (source_id, type_id, file_id, name, property_type, visibility,"
                " has_getter, has_setter, is_static, start_line, end_line) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (db_source_id, type_db_ids.get(prop["type_local_id"]), file_id, prop["name"],
                 prop["property_type"], prop["visibility"], prop["has_getter"], prop["has_setter"],
                 prop["is_static"], prop["start_line"], prop["end_line"]),
            )
            totals["properties"] += 1

        for string in result["strings"]:
            conn.execute(
                "INSERT INTO strings (source_id, file_id, type_id, method_id, value, classification, start_line)"
                " VALUES (?,?,?,?,?,?,?)",
                (db_source_id, file_id,
                 type_db_ids.get(string["type_id"]) if string["type_id"] not in dropped_type_locals else None,
                 method_db_ids.get(string["method_id"]) if string["method_id"] is not None else None,
                 string["value"], string["classification"], string["start_line"]),
            )
            totals["strings"] += 1

        for edge in result["inheritance"]:
            if edge["type_local_id"] in dropped_type_locals or type_db_ids.get(edge["type_local_id"]) is None:
                continue
            conn.execute(
                "INSERT INTO inheritance (source_id, type_id, relation, target_name, target_type_id)"
                " VALUES (?,?,?,?,NULL)",
                (db_source_id, type_db_ids[edge["type_local_id"]], edge["relation"], edge["target_name"]),
            )
            totals["inheritance"] += 1


def _resolve_inheritance_unified(conn: sqlite3.Connection) -> None:
    """Fill target_type_id; same-source candidates first, then worldbox API surface."""
    edges = conn.execute(
        """SELECT i.id, t.id AS type_id, i.target_name, s.source_id
           FROM inheritance i JOIN types t ON t.id = i.type_id JOIN sources s ON s.id = t.source_id
           WHERE i.target_type_id IS NULL"""
    ).fetchall()
    for edge_id, type_id, target, source_id in edges:
        row = conn.execute("SELECT namespace FROM types WHERE id = ?", (type_id,)).fetchone()
        if not row:
            continue
        ns = row[0]
        base_name = target.split("<")[0].split(".")[-1]

        def exact_lookup(source: str, name: str) -> int | None:
            rows = conn.execute(
                """SELECT t.id FROM types t JOIN sources s ON s.id = t.source_id
                   WHERE s.source_id = ? AND t.full_name = ?""",
                (source, name),
            ).fetchall()
            return rows[0][0] if len(rows) == 1 else None

        resolved = None
        candidates = []
        if ns:
            parts = ns.split(".")
            for i in range(len(parts), 0, -1):
                candidates.append(".".join(parts[:i]) + "." + base_name)
        candidates.append(base_name)
        for candidate in candidates:
            found = exact_lookup(source_id, candidate)
            if found is not None:
                resolved = found
                break
        if resolved is None and source_id != "worldbox":
            # cross-source: unique worldbox type with this name
            rows = conn.execute(
                """SELECT t.id FROM types t JOIN sources s ON s.id = t.source_id
                   WHERE s.source_id = 'worldbox' AND t.name = ?""",
                (base_name,),
            ).fetchall()
            if len(rows) == 1:
                resolved = rows[0][0]
        if resolved is None:
            rows = conn.execute(
                """SELECT t.id FROM types t JOIN sources s ON s.id = t.source_id
                   WHERE s.source_id = ? AND t.name = ?""",
                (source_id, base_name),
            ).fetchall()
            if len(rows) == 1:
                resolved = rows[0][0]
        if resolved is not None:
            conn.execute("UPDATE inheritance SET target_type_id = ? WHERE id = ?", (resolved, edge_id))


def _run_reference_pass(conn: sqlite3.Connection, source_dir: Path, cs_files: list[Path], stats: dict, db_source_id: int, source_id: str) -> None:
    """Pass 2: resolve and record references for one source (cross-source aware)."""
    symbol_resolver = resolver_mod.Resolver(conn)
    type_ids = {key: info["id"] for key, info in symbol_resolver.types.items()}
    method_ids: dict = {}
    for owner_key, by_name in symbol_resolver.methods.items():
        for methods in by_name.values():
            for method in methods:
                method_ids[(owner_key, method["signature"])] = method["id"]

    file_ids = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT relative_path, id FROM files WHERE source_id = ?", (db_source_id,)
        )
    }
    for path in cs_files:
        rel = path.relative_to(source_dir).as_posix()
        file_id = file_ids.get(rel)
        if file_id is None:
            continue
        try:
            code = path.read_bytes()
            result = references.extract_references(
                code, references.ReferenceContext(symbol_resolver, file_id, source_id, type_ids, method_ids)
            )
            for row in result["symbol_references"]:
                conn.execute(
                    "INSERT INTO symbol_references (source_id, from_file_id, from_type_id, from_method_id,"
                    " target_kind, target_name, target_logical_key, target_id, reference_kind,"
                    " start_line, start_column, end_line, end_column, resolution_status, resolution_confidence)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (db_source_id, row["from_file_id"], row["from_type_id"], row["from_method_id"],
                     row["target_kind"], row["target_name"], row["target_logical_key"], row["target_id"],
                     row["reference_kind"], row["start_line"], row["start_column"],
                     row["end_line"], row["end_column"], row["resolution_status"],
                     row["resolution_confidence"]),
                )
            for row in result["method_calls"]:
                conn.execute(
                    "INSERT INTO method_calls (source_id, caller_method_id, callee_method_id, callee_name,"
                    " callee_signature_hint, declaring_type_hint, file_id, line, column, resolution_status)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (db_source_id, row["caller_method_id"], row["callee_method_id"], row["callee_name"],
                     row["callee_signature_hint"], row["declaring_type_hint"], row["file_id"],
                     row["line"], row["column"], row["resolution_status"]),
                )
            for row in result["type_references"]:
                conn.execute(
                    "INSERT INTO type_references (source_id, from_file_id, from_type_id, from_method_id,"
                    " target_type_id, target_name, reference_kind, line, resolution_status)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (db_source_id, row["from_file_id"], row["from_type_id"], row["from_method_id"],
                     row["target_type_id"], row["target_name"], row["reference_kind"],
                     row["line"], row["resolution_status"]),
                )
        except Exception as exc:  # per-file best-effort: keep declarations, mark PARTIAL
            stats["REF_PARTIAL"] = stats.get("REF_PARTIAL", 0) + 1
            conn.execute(
                "UPDATE files SET reference_status='PARTIAL', reference_error=? WHERE id=?",
                (str(exc)[:200], file_id),
            )


def _write_meta(conn: sqlite3.Connection, sources_spec: list[dict], stats: dict, totals: dict) -> None:
    entries = {
        "schema_version": str(SCHEMA_VERSION),
        "indexer_version": INDEXER_VERSION,
        "resolver_version": resolver_mod.RESOLVER_VERSION,
        "sources_count": str(len(sources_spec)),
    }
    for spec in sources_spec:
        source_id = spec["source_id"]
        entries[f"snapshot:{source_id}"] = spec.get("snapshot_id") or ""
        src_stats = stats.get(source_id, {})
        entries[f"parsed_ok:{source_id}"] = str(src_stats.get("OK", 0))
        entries[f"parsed_partial:{source_id}"] = str(src_stats.get("PARTIAL", 0))
        entries[f"parsed_failed:{source_id}"] = str(src_stats.get("FAILED", 0))
        meta = spec.get("meta") or {}
        if source_id == "worldbox":
            entries["worldbox_version"] = meta.get("worldbox_version") or "unknown"
            entries["assembly_sha256"] = meta.get("assembly_sha256") or ""
            entries["extractor_name"] = meta.get("extractor_name") or ""
            entries["extractor_version"] = meta.get("extractor_version") or ""
            entries["source_snapshot_id"] = spec.get("snapshot_id") or ""  # legacy alias
        if source_id == "neomodloader":
            entries["nml_commit"] = meta.get("commit") or ""
            entries["nml_source_mode"] = meta.get("source_mode") or "decompiled"
    entries["built_at"] = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    for key, value in entries.items():
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))


def _validate_index(conn: sqlite3.Connection, sources_spec: list[dict], all_cs: dict, stats: dict, require_core_types: bool, max_failed_ratio: float) -> None:
    problems = []
    for spec in sources_spec:
        source_id = spec["source_id"]
        cs_count = len(all_cs[source_id])
        file_count = conn.execute(
            "SELECT COUNT(*) FROM files f JOIN sources s ON s.id = f.source_id WHERE s.source_id = ?",
            (source_id,),
        ).fetchone()[0]
        if file_count != cs_count:
            problems.append(f"[{source_id}] file coverage mismatch: {file_count} indexed vs {cs_count} raw")
        failed = stats[source_id].get("FAILED", 0)
        # NML decompiled output contains ILSpy-specific syntax (e.g. casts of
        # `ref` expressions) that tree-sitter cannot parse; a few FAILED files
        # are recorded per-file and are acceptable at this corpus size
        allowed_ratio = 0.02 if source_id == "neomodloader" else max_failed_ratio
        if (failed / cs_count if cs_count else 1) > allowed_ratio:
            problems.append(f"[{source_id}] too many FAILED files: {failed}/{cs_count}")

    for table in ("types", "methods", "fields", "properties", "strings", "inheritance"):
        if conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] <= 0:
            problems.append(f"table {table} is empty")

    if require_core_types:
        for table in ("symbol_references", "method_calls", "type_references"):
            if conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] <= 0:
                problems.append(f"table {table} is empty")
        resolved_calls = conn.execute(
            "SELECT COUNT(*) FROM method_calls WHERE resolution_status='resolved'"
        ).fetchone()[0]
        if resolved_calls <= 0:
            problems.append("no resolved method calls — resolver failure?")
        for name in CORE_TYPES:
            found = conn.execute(
                """SELECT COUNT(*) FROM types t JOIN sources s ON s.id = t.source_id
                   WHERE s.source_id='worldbox' AND t.name = ? AND t.is_compiler_generated = 0""",
                (name,),
            ).fetchone()[0]
            if found == 0:
                problems.append(f"core type {name} not found")
        known = conn.execute("SELECT COUNT(*) FROM strings WHERE value = 'kingdom'").fetchone()[0]
        if known == 0:
            problems.append("known literal 'kingdom' not found in strings")
        nml_spec = next((s for s in sources_spec if s["source_id"] == "neomodloader"), None)
        if nml_spec is not None:
            nml_types = conn.execute(
                """SELECT COUNT(*) FROM types t JOIN sources s ON s.id = t.source_id
                   WHERE s.source_id='neomodloader' AND t.namespace LIKE 'NeoModLoader%'"""
            ).fetchone()[0]
            if nml_types <= 0:
                problems.append("neomodloader indexed without NeoModLoader-namespace types")
    if problems:
        raise IndexError_("index validation failed: " + "; ".join(problems))


# --- Orchestration -----------------------------------------------------------


def _worldbox_spec(repo_root: Path, registry: dict) -> dict | None:
    snap = extractor.snapshot_state(repo_root, registry)
    if snap["state"] not in ("OK", "OK-EXTRACTOR-CHANGED"):
        return None
    snap_id = snap["snapshot"]
    manifest = snap.get("manifest") or json.loads(
        (Path(repo_root) / extractor.SNAPSHOTS_DIR / snap_id / "extraction-manifest.json").read_text(encoding="utf-8")
    )
    return {
        "source_id": "worldbox",
        "kind": "game",
        "version": manifest.get("game_version"),
        "snapshot_id": snap_id,
        "source_dir": snapshot_source_dir(repo_root, snap_id),
        "meta": {
            "worldbox_version": manifest.get("game_version"),
            "assembly_sha256": manifest.get("assembly", {}).get("sha256"),
            "extractor_name": manifest.get("extractor", {}).get("name"),
            "extractor_version": manifest.get("extractor", {}).get("version"),
            "source_snapshot_id": snap_id,
        },
    }


def _nml_spec(repo_root: Path, registry: dict) -> dict | None:
    snap = extractor.nml_snapshot_state(repo_root, registry)
    if snap["state"] not in ("OK", "OK-EXTRACTOR-CHANGED"):
        return None
    snap_id = snap["snapshot"]
    manifest = snap.get("manifest") or json.loads(
        (Path(repo_root) / extractor.NML_SNAPSHOTS_DIR / snap_id / "extraction-manifest.json").read_text(encoding="utf-8")
    )
    return {
        "source_id": "neomodloader",
        "kind": "mod-loader",
        "version": manifest.get("commit") or manifest.get("version"),
        "snapshot_id": snap_id,
        "source_dir": Path(repo_root) / extractor.NML_SNAPSHOTS_DIR / snap_id / "source",
        "meta": {
            "commit": manifest.get("commit"),
            "source_mode": manifest.get("source_mode"),
            "extractor_version": manifest.get("extractor", {}).get("version"),
        },
    }


def unified_identity(sources_spec: list[dict]) -> str:
    parts = [
        f"schema{SCHEMA_VERSION}",
        f"idx{INDEXER_VERSION}",
        f"res{resolver_mod.RESOLVER_VERSION}",
    ]
    for spec in sorted(sources_spec, key=lambda s: s["source_id"]):
        parts.append(f"{spec['source_id']}={spec.get('snapshot_id')}")
        if spec.get("meta", {}).get("extractor_version"):
            parts[-1] += "/" + spec["meta"]["extractor_version"]
    return ";".join(parts)


def index_state(repo_root: Path, registry: dict | None) -> dict:
    """OK / STALE / MISSING / BROKEN for the unified index."""
    path = db_path(repo_root)
    if not path.is_file():
        return {"state": "MISSING"}
    meta = read_meta(path)
    if meta is None:
        return {"state": "BROKEN", "reason": "unreadable or missing meta table"}
    state = {"state": "OK", "meta": meta, "db": path}
    if meta.get("schema_version") != str(SCHEMA_VERSION):
        state["state"] = "STALE"
        state["reason"] = f"schema v{meta.get('schema_version')} (current v{SCHEMA_VERSION}); rebuild required"
        return state
    if meta.get("indexer_version") != INDEXER_VERSION or meta.get("resolver_version") != resolver_mod.RESOLVER_VERSION:
        state["state"] = "STALE"
        state["reason"] = "indexer/resolver version changed"
        return state
    if registry is not None:
        wb_source = (registry.get("sources") or {}).get("worldbox")
        if wb_source and wb_source.get("assembly"):
            expected_wb = extractor.snapshot_id(
                wb_source.get("game_version"), wb_source["assembly"].get("sha256", "")
            )
            if meta.get("snapshot:worldbox", meta.get("source_snapshot_id")) != expected_wb:
                state["state"] = "STALE"
                state["reason"] = "worldbox source snapshot changed since last index"
                return state
        nml_spec = _nml_spec(repo_root, registry)
        nml_in_db = meta.get("snapshot:neomodloader")
        if nml_spec and nml_in_db != nml_spec["snapshot_id"]:
            state["state"] = "STALE"
            state["reason"] = "neomodloader source snapshot changed (or not yet indexed)"
            return state
        if not nml_spec and nml_in_db:
            # indexed NML no longer resolvable from the registry
            state["state"] = "STALE"
            state["reason"] = "indexed neomodloader snapshot no longer matches the registry"
            return state
    return state


def perform_unified_indexing(repo_root: Path, registry: dict, force: bool = False, requested: str = "all") -> dict:
    """Complete unified rebuild across all available source snapshots."""
    repo_root = Path(repo_root)
    specs: list[dict] = []

    wb_spec = _worldbox_spec(repo_root, registry)
    if wb_spec:
        specs.append(wb_spec)
    elif requested in ("worldbox", "all"):
        raise IndexError_("WorldBox source snapshot missing; run: python -m wbkb extract worldbox")

    nml_spec = _nml_spec(repo_root, registry)
    if nml_spec:
        specs.append(nml_spec)
    elif requested == "neomodloader":
        raise IndexError_("NeoModLoader snapshot missing; run: python -m wbkb extract neomodloader")

    final_db = db_path(repo_root)
    identity = unified_identity(specs)
    if not force:
        existing = read_meta(final_db)
        if existing and _identity_matches(existing, specs, identity):
            return {"status": "UNCHANGED", "specs": specs, "db": final_db, "meta": existing}

    tmp_db = repo_root / TMP_DB_REL
    tmp_db.parent.mkdir(parents=True, exist_ok=True)
    for stale in (tmp_db, tmp_db.with_name(tmp_db.name + "-journal")):
        _remove_db_file(stale)

    stats = build_unified_index(specs, tmp_db, _schema_sql(repo_root), require_core_types=True)
    os.replace(tmp_db, final_db)
    return {"status": "CREATED", "specs": specs, "db": final_db, "stats": stats}


def _identity_matches(existing_meta: dict, specs: list[dict], identity: str) -> bool:
    if existing_meta.get("schema_version") != str(SCHEMA_VERSION):
        return False
    if existing_meta.get("indexer_version") != INDEXER_VERSION:
        return False
    if existing_meta.get("resolver_version") != resolver_mod.RESOLVER_VERSION:
        return False
    recorded_sources = int(existing_meta.get("sources_count", "0") or 0)
    if recorded_sources != len(specs):
        return False
    for spec in specs:
        if existing_meta.get(f"snapshot:{spec['source_id']}") != spec.get("snapshot_id"):
            return False
        extractor_version = (spec.get("meta") or {}).get("extractor_version") or ""
        if spec["source_id"] == "worldbox" and existing_meta.get("extractor_version", "") != extractor_version:
            return False
    return True


# Backwards-compatible alias (Z3/Z4 callers)
def perform_indexing(repo_root: Path, registry: dict, force: bool = False) -> dict:
    return perform_unified_indexing(repo_root, registry, force=force, requested="worldbox")


def read_stats(db_file: Path) -> dict:
    conn = sqlite3.connect(f"file:{Path(db_file)}?mode=ro", uri=True)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        counts = {}
        for table in (
            "files", "types", "methods", "fields", "properties", "strings",
            "inheritance", "sources", "symbol_references", "method_calls", "type_references",
        ):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        parse = dict(
            conn.execute("SELECT parse_status, COUNT(*) FROM files GROUP BY parse_status").fetchall()
        )
        ref_status = dict(
            conn.execute("SELECT reference_status, COUNT(*) FROM files GROUP BY reference_status").fetchall()
        )
        call_resolution = dict(
            conn.execute("SELECT resolution_status, COUNT(*) FROM method_calls GROUP BY resolution_status").fetchall()
        )
        ref_resolution = dict(
            conn.execute("SELECT resolution_status, COUNT(*) FROM symbol_references GROUP BY resolution_status").fetchall()
        )
        size = Path(db_file).stat().st_size
    finally:
        conn.close()
    return {
        "meta": meta,
        "counts": counts,
        "parse": parse,
        "ref_status": ref_status,
        "call_resolution": call_resolution,
        "ref_resolution": ref_resolution,
        "db_size": size,
    }
