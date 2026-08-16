"""Structured index builder: raw source snapshot -> SQLite wbkb.db (Z3).

Deterministic tooling: parses C# with tree-sitter, builds the database in a
temporary file, validates it, then atomically replaces the live database.
The database is generated data and never committed to Git.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from . import csharp, extractor, references, resolver as resolver_mod, util

SCHEMA_VERSION = 2
INDEXER_VERSION = "2.0.0"
DB_REL = Path("data/generated/index/wbkb.db")
TMP_DB_REL = Path("data/generated/index/wbkb.tmp.db")
SCHEMA_REL = Path("schemas/schema-v2.sql")

MAX_FAILED_RATIO = 0.01  # more than 1% FAILED files => validation failure
CORE_TYPES = ("Actor", "City", "Kingdom")


class IndexError_(RuntimeError):
    pass


# --- Meta --------------------------------------------------------------------


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


# --- Build -------------------------------------------------------------------


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
    """Parse every .cs under source_dir into a SQLite db at db_file.

    Never touches a pre-existing db_file: builds into a sibling *.build file
    and atomically replaces on success; a pre-existing db survives failures.
    """
    source_dir = Path(source_dir)
    db_file = Path(db_file)
    build_target = db_file if not db_file.exists() else db_file.with_name(db_file.name + ".build")
    _remove_db_file(build_target)

    cs_files = sorted(
        (p for p in source_dir.rglob("*.cs") if p.is_file()), key=lambda p: p.relative_to(source_dir).as_posix()
    )
    if not cs_files:
        raise IndexError_("no .cs files found in source snapshot")

    conn = sqlite3.connect(build_target)
    try:
        conn.executescript(schema_sql)
        conn.execute(
            "INSERT INTO sources (source_id, source_kind, version, content_hash, snapshot_id) VALUES (?,?,?,?,?)",
            ("worldbox", "game", meta.get("worldbox_version"), meta.get("assembly_sha256"), meta.get("source_snapshot_id")),
        )
        source_row = conn.execute("SELECT id FROM sources WHERE source_id='worldbox'").fetchone()
        db_source_id = source_row[0]

        stats = {"OK": 0, "PARTIAL": 0, "FAILED": 0}
        totals = {"types": 0, "methods": 0, "fields": 0, "properties": 0, "strings": 0, "inheritance": 0}
        type_db_ids: dict[int, int] = {}  # local -> db id
        method_db_ids: dict[int, int] = {}

        for path in cs_files:
            rel = path.relative_to(source_dir).as_posix()
            data = path.read_bytes()
            result = csharp.parse_source(data)
            stats[result["parse_status"]] += 1

            cur = conn.execute(
                "INSERT INTO files (source_id, relative_path, filename, extension, size, sha256, line_count, parse_status, parse_error)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    db_source_id,
                    rel,
                    path.name,
                    path.suffix.lower(),
                    len(data),
                    util.sha256_file(path),
                    data.count(b"\n") + 1,
                    result["parse_status"],
                    result["parse_error"],
                ),
            )
            file_id = cur.lastrowid

            for type_record in result["types"]:
                cur = conn.execute(
                    "INSERT INTO types (source_id, file_id, namespace, name, full_name, kind, visibility,"
                    " is_abstract, is_static, is_sealed, is_compiler_generated, parent_type_id, start_line, end_line)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id,
                        file_id,
                        type_record["namespace"],
                        type_record["name"],
                        type_record["full_name"],
                        type_record["kind"],
                        type_record["visibility"],
                        type_record["is_abstract"],
                        type_record["is_static"],
                        type_record["is_sealed"],
                        type_record["is_compiler_generated"],
                        type_db_ids.get(type_record["parent_local_id"]),
                        type_record["start_line"],
                        type_record["end_line"],
                    ),
                )
                type_db_ids[type_record["local_id"]] = cur.lastrowid
                totals["types"] += 1

            for method in result["methods"]:
                cur = conn.execute(
                    "INSERT INTO methods (source_id, type_id, file_id, name, signature, return_type, visibility,"
                    " is_static, is_virtual, is_override, is_abstract, start_line, end_line)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id,
                        type_db_ids.get(method["type_local_id"]),
                        file_id,
                        method["name"],
                        method["signature"],
                        method["return_type"],
                        method["visibility"],
                        method["is_static"],
                        method["is_virtual"],
                        method["is_override"],
                        method["is_abstract"],
                        method["start_line"],
                        method["end_line"],
                    ),
                )
                method_db_ids[method["local_id"]] = cur.lastrowid
                totals["methods"] += 1

            for field in result["fields"]:
                conn.execute(
                    "INSERT INTO fields (source_id, type_id, file_id, name, field_type, visibility,"
                    " is_static, is_readonly, is_const, start_line) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id,
                        type_db_ids.get(field["type_local_id"]),
                        file_id,
                        field["name"],
                        field["field_type"],
                        field["visibility"],
                        field["is_static"],
                        field["is_readonly"],
                        field["is_const"],
                        field["start_line"],
                    ),
                )
                totals["fields"] += 1

            for prop in result["properties"]:
                conn.execute(
                    "INSERT INTO properties (source_id, type_id, file_id, name, property_type, visibility,"
                    " has_getter, has_setter, is_static, start_line, end_line) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id,
                        type_db_ids.get(prop["type_local_id"]),
                        file_id,
                        prop["name"],
                        prop["property_type"],
                        prop["visibility"],
                        prop["has_getter"],
                        prop["has_setter"],
                        prop["is_static"],
                        prop["start_line"],
                        prop["end_line"],
                    ),
                )
                totals["properties"] += 1

            for string in result["strings"]:
                conn.execute(
                    "INSERT INTO strings (source_id, file_id, type_id, method_id, value, classification, start_line)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (
                        db_source_id,
                        file_id,
                        type_db_ids.get(string["type_id"]),
                        method_db_ids.get(string["method_id"]) if string["method_id"] is not None else None,
                        string["value"],
                        string["classification"],
                        string["start_line"],
                    ),
                )
                totals["strings"] += 1

            for edge in result["inheritance"]:
                conn.execute(
                    "INSERT INTO inheritance (source_id, type_id, relation, target_name, target_type_id)"
                    " VALUES (?,?,?,?,NULL)",
                    (
                        db_source_id,
                        type_db_ids[edge["type_local_id"]],
                        edge["relation"],
                        edge["target_name"],
                    ),
                )
                totals["inheritance"] += 1

        _resolve_inheritance(conn)
        _run_reference_pass(conn, source_dir, cs_files, stats, db_source_id)
        _write_meta(conn, meta, stats, totals)
        conn.commit()
        _validate_index(
            conn,
            cs_count=len(cs_files),
            stats=stats,
            require_core_types=require_core_types,
            max_failed_ratio=max_failed_ratio,
        )
    except Exception:
        conn.close()
        for leftover in (build_target, build_target.with_name(build_target.name + "-journal")):
            _remove_db_file(leftover)
        raise
    conn.close()
    if build_target != db_file:
        os.replace(build_target, db_file)
    return read_stats(db_file)


def _resolve_inheritance(conn: sqlite3.Connection) -> None:
    """Fill target_type_id where the target name resolves to an indexed type."""
    edges = conn.execute("SELECT id, type_id, target_name FROM inheritance WHERE target_type_id IS NULL").fetchall()
    for edge_id, type_id, target in edges:
        row = conn.execute("SELECT namespace FROM types WHERE id = ?", (type_id,)).fetchone()
        if not row:
            continue
        ns = row[0]
        base_name = target.split("<")[0].split(".")[-1]  # strip generics + qualification
        candidates = []
        if ns:
            parts = ns.split(".")
            for i in range(len(parts), 0, -1):  # innermost -> outermost namespace
                candidates.append(".".join(parts[:i]) + "." + base_name)
        candidates.append(base_name)
        resolved = None
        for candidate in candidates:
            rows = conn.execute("SELECT id FROM types WHERE full_name = ?", (candidate,)).fetchall()
            if len(rows) == 1:
                resolved = rows[0][0]
                break
            if len(rows) > 1:
                break  # ambiguous
        if resolved is None:
            rows = conn.execute("SELECT id FROM types WHERE name = ?", (base_name,)).fetchall()
            if len(rows) == 1:
                resolved = rows[0][0]
        if resolved is not None:
            conn.execute("UPDATE inheritance SET target_type_id = ? WHERE id = ?", (resolved, edge_id))


def _run_reference_pass(conn: sqlite3.Connection, source_dir: Path, cs_files: list[Path], stats: dict, db_source_id: int) -> None:
    """Pass 2: resolve and record symbol references, call edges, type references."""
    symbol_resolver = resolver_mod.Resolver(conn)
    type_ids = {full: info["id"] for full, info in symbol_resolver.types.items()}
    method_ids: dict[tuple[str, str], int] = {}
    for owner, by_name in symbol_resolver.methods.items():
        for methods in by_name.values():
            for method in methods:
                method_ids[(owner, method["signature"])] = method["id"]

    file_ids = {row[0]: row[1] for row in conn.execute("SELECT relative_path, id FROM files")}
    for path in cs_files:
        rel = path.relative_to(source_dir).as_posix()
        file_id = file_ids.get(rel)
        if file_id is None:
            continue
        try:
            code = path.read_bytes()
            result = references.extract_references(
                code, references.ReferenceContext(symbol_resolver, file_id, type_ids, method_ids)
            )
            for row in result["symbol_references"]:
                conn.execute(
                    "INSERT INTO symbol_references (source_id, from_file_id, from_type_id, from_method_id,"
                    " target_kind, target_name, target_logical_key, target_id, reference_kind,"
                    " start_line, start_column, end_line, end_column, resolution_status, resolution_confidence)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id, row["from_file_id"], row["from_type_id"], row["from_method_id"],
                        row["target_kind"], row["target_name"], row["target_logical_key"], row["target_id"],
                        row["reference_kind"], row["start_line"], row["start_column"],
                        row["end_line"], row["end_column"], row["resolution_status"],
                        row["resolution_confidence"],
                    ),
                )
            for row in result["method_calls"]:
                conn.execute(
                    "INSERT INTO method_calls (source_id, caller_method_id, callee_method_id, callee_name,"
                    " callee_signature_hint, declaring_type_hint, file_id, line, column, resolution_status)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id, row["caller_method_id"], row["callee_method_id"], row["callee_name"],
                        row["callee_signature_hint"], row["declaring_type_hint"], row["file_id"],
                        row["line"], row["column"], row["resolution_status"],
                    ),
                )
            for row in result["type_references"]:
                conn.execute(
                    "INSERT INTO type_references (source_id, from_file_id, from_type_id, from_method_id,"
                    " target_type_id, target_name, reference_kind, line, resolution_status)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        db_source_id, row["from_file_id"], row["from_type_id"], row["from_method_id"],
                        row["target_type_id"], row["target_name"], row["reference_kind"],
                        row["line"], row["resolution_status"],
                    ),
                )
        except Exception as exc:  # per-file best-effort: keep declarations, mark PARTIAL
            stats["REF_PARTIAL"] = stats.get("REF_PARTIAL", 0) + 1
            conn.execute(
                "UPDATE files SET reference_status='PARTIAL', reference_error=? WHERE id=?",
                (str(exc)[:200], file_id),
            )


def _write_meta(conn: sqlite3.Connection, meta: dict, stats: dict, totals: dict) -> None:
    entries = {
        "schema_version": str(SCHEMA_VERSION),
        "indexer_version": INDEXER_VERSION,
        "resolver_version": resolver_mod.RESOLVER_VERSION,
        "source_id": "worldbox",
        "worldbox_version": meta.get("worldbox_version") or "unknown",
        "assembly_sha256": meta.get("assembly_sha256") or "",
        "extractor_name": meta.get("extractor_name") or "",
        "extractor_version": meta.get("extractor_version") or "",
        "source_snapshot_id": meta.get("source_snapshot_id") or "",
        "parsed_ok": str(stats["OK"]),
        "parsed_partial": str(stats["PARTIAL"]),
        "parsed_failed": str(stats["FAILED"]),
        "built_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }
    for key, value in entries.items():
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))


def _validate_index(conn: sqlite3.Connection, cs_count: int, stats: dict, require_core_types: bool, max_failed_ratio: float) -> None:
    problems = []
    file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    if file_count != cs_count:
        problems.append(f"file coverage mismatch: {file_count} indexed vs {cs_count} raw .cs files")
    failed_ratio = stats["FAILED"] / cs_count if cs_count else 1
    if failed_ratio > max_failed_ratio:
        problems.append(f"too many FAILED files: {stats['FAILED']}/{cs_count} ({failed_ratio:.1%})")
    for table in ("types", "methods", "fields", "properties", "strings", "inheritance"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count <= 0:
            problems.append(f"table {table} is empty")
    # reference layer sanity (schema v2) — strict mode only; tiny fixtures
    # may legitimately contain no calls
    if require_core_types:
        for table in ("symbol_references", "method_calls", "type_references"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count <= 0:
                problems.append(f"table {table} is empty")
        resolved_calls = conn.execute(
            "SELECT COUNT(*) FROM method_calls WHERE resolution_status='resolved'"
        ).fetchone()[0]
        if resolved_calls <= 0:
            problems.append("no resolved method calls — resolver failure?")
    if require_core_types:
        for name in CORE_TYPES:
            found = conn.execute(
                "SELECT COUNT(*) FROM types WHERE name = ? AND is_compiler_generated = 0", (name,)
            ).fetchone()[0]
            if found == 0:
                problems.append(f"core type {name} not found")
        known = conn.execute("SELECT COUNT(*) FROM strings WHERE value = 'kingdom'").fetchone()[0]
        if known == 0:
            problems.append("known literal 'kingdom' not found in strings")
    if problems:
        raise IndexError_("index validation failed: " + "; ".join(problems))


# --- Orchestration -----------------------------------------------------------


def snapshot_source_dir(repo_root: Path, snapshot_id: str) -> Path:
    return Path(repo_root) / extractor.SNAPSHOTS_DIR / snapshot_id / "source"


def index_state(repo_root: Path, registry: dict | None) -> dict:
    """OK / STALE / MISSING / BROKEN for the structured index."""
    path = db_path(repo_root)
    if not path.is_file():
        return {"state": "MISSING"}
    meta = read_meta(path)
    if meta is None:
        return {"state": "BROKEN", "reason": "unreadable or missing meta table"}
    state = {"state": "OK", "meta": meta, "db": path}
    if meta.get("schema_version") != str(SCHEMA_VERSION):
        # older schema is rebuildable, not corrupt
        state["state"] = "STALE"
        state["reason"] = f"schema v{meta.get('schema_version')} (current v{SCHEMA_VERSION}); rebuild required"
        return state
    if registry is not None:
        source = (registry.get("sources") or {}).get("worldbox")
        if source and source.get("assembly"):
            current_snapshot = extractor.snapshot_id(
                source.get("game_version"), source["assembly"].get("sha256", "")
            )
            if meta.get("source_snapshot_id") != current_snapshot:
                state["state"] = "STALE"
                state["reason"] = "source snapshot changed since last index"
    return state


def perform_indexing(repo_root: Path, registry: dict, force: bool = False) -> dict:
    repo_root = Path(repo_root)
    snap = extractor.snapshot_state(repo_root, registry)
    if snap["state"] not in ("OK", "OK-EXTRACTOR-CHANGED"):
        raise IndexError_(
            f"WorldBox source snapshot {snap['state']}; run: python -m wbkb extract worldbox"
        )
    snap_id = snap["snapshot"]
    manifest = snap.get("manifest") or json.loads(
        (repo_root / extractor.SNAPSHOTS_DIR / snap_id / "extraction-manifest.json").read_text(encoding="utf-8")
    )

    meta = {
        "worldbox_version": manifest.get("game_version"),
        "assembly_sha256": manifest.get("assembly", {}).get("sha256"),
        "extractor_name": manifest.get("extractor", {}).get("name"),
        "extractor_version": manifest.get("extractor", {}).get("version"),
        "source_snapshot_id": snap_id,
    }

    final_db = db_path(repo_root)
    if not force:
        existing = read_meta(final_db)
        if existing and (
            existing.get("schema_version") == str(SCHEMA_VERSION)
            and existing.get("indexer_version") == INDEXER_VERSION
            and existing.get("resolver_version") == resolver_mod.RESOLVER_VERSION
            and existing.get("source_snapshot_id") == snap_id
            and existing.get("extractor_version") == (meta["extractor_version"] or "")
        ):
            return {"status": "UNCHANGED", "snapshot": snap_id, "db": final_db, "meta": existing}

    source_dir = snapshot_source_dir(repo_root, snap_id)
    tmp_db = repo_root / TMP_DB_REL
    tmp_db.parent.mkdir(parents=True, exist_ok=True)
    for stale in (tmp_db, tmp_db.with_name(tmp_db.name + "-journal")):
        _remove_db_file(stale)

    stats = build_index(source_dir, tmp_db, meta, _schema_sql(repo_root), require_core_types=True)
    os.replace(tmp_db, final_db)
    return {"status": "CREATED", "snapshot": snap_id, "db": final_db, "stats": stats}


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
