"""Read-only query layer over the WBKB structured index (search/symbol/show)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import indexer

DEFAULT_LIMIT = 20


class QueryError(RuntimeError):
    pass


def _connect(repo_root: Path) -> tuple[sqlite3.Connection, Path]:
    path = indexer.db_path(repo_root)
    if not path.is_file():
        raise QueryError("index database missing; run: python -m wbkb index worldbox")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn, path


def _loc(file_row) -> str:
    if file_row is None:
        return "?"
    rel = file_row["relative_path"]
    line = file_row["line_hint"]
    return f"{rel}:{line}" if line is not None else rel


def _match(column: str, query: str, exact: bool) -> tuple[str, tuple]:
    if exact:
        return f"{column} = ?", (query,)
    return f"{column} LIKE ? ESCAPE '\\'", (f"%{_escape_like(query)}%",)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(repo_root: Path, query: str, limit: int = DEFAULT_LIMIT, exact: bool = False, include_generated: bool = False, source: str | None = None) -> dict:
    conn, _ = _connect(repo_root)
    try:
        gen = "" if include_generated else " AND t.is_compiler_generated = 0"
        src = " AND s.source_id = ?" if source else ""
        src_args = (source,) if source else ()

        if exact:
            types = conn.execute(
                f"""SELECT s.source_id, t.full_name, t.kind, f.relative_path, t.start_line
                    FROM types t JOIN files f ON f.id = t.file_id JOIN sources s ON s.id = t.source_id
                    WHERE (t.name = ? OR t.full_name = ?){gen}{src}
                    ORDER BY t.full_name LIMIT ?""",
                (query, query, *src_args, limit),
            ).fetchall()
        else:
            pattern = f"%{_escape_like(query)}%"
            types = conn.execute(
                f"""SELECT s.source_id, t.full_name, t.kind, f.relative_path, t.start_line
                    FROM types t JOIN files f ON f.id = t.file_id JOIN sources s ON s.id = t.source_id
                    WHERE (t.name LIKE ? ESCAPE '\\' OR t.full_name LIKE ? ESCAPE '\\'){gen}{src}
                    ORDER BY t.is_compiler_generated, t.full_name LIMIT ?""",
                (pattern, pattern, *src_args, limit),
            ).fetchall()

        methods = conn.execute(
            f"""SELECT s.source_id, m.signature, t.full_name AS type_full, f.relative_path, m.start_line
                FROM methods m JOIN types t ON t.id = m.type_id JOIN files f ON f.id = m.file_id
                JOIN sources s ON s.id = t.source_id
                WHERE m.name {'= ?' if exact else 'LIKE ?'}{gen}{src}
                ORDER BY t.full_name, m.signature LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), *src_args, limit),
        ).fetchall()

        fields = conn.execute(
            f"""SELECT s.source_id, fl.name, fl.field_type, t.full_name AS type_full, f.relative_path, fl.start_line
                FROM fields fl JOIN types t ON t.id = fl.type_id JOIN files f ON f.id = fl.file_id
                JOIN sources s ON s.id = t.source_id
                WHERE fl.name {'= ?' if exact else 'LIKE ?'}{gen}{src}
                ORDER BY t.full_name, fl.name LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), *src_args, limit),
        ).fetchall()

        properties = conn.execute(
            f"""SELECT s.source_id, p.name, p.property_type, t.full_name AS type_full, f.relative_path, p.start_line
                FROM properties p JOIN types t ON t.id = p.type_id JOIN files f ON f.id = p.file_id
                JOIN sources s ON s.id = t.source_id
                WHERE p.name {'= ?' if exact else 'LIKE ?'}{gen}{src}
                ORDER BY t.full_name, p.name LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), *src_args, limit),
        ).fetchall()

        value_match = _match("str.value", query, exact)
        strings = conn.execute(
            f"""SELECT src.source_id, str.value, f.relative_path, str.start_line
                FROM strings str JOIN files f ON f.id = str.file_id JOIN sources src ON src.id = f.source_id
                WHERE {value_match[0]}{' AND src.source_id = ?' if source else ''}
                ORDER BY str.value, f.relative_path, str.start_line LIMIT ?""",
            (*value_match[1], *src_args, limit),
        ).fetchall()

        files = conn.execute(
            f"""SELECT s.source_id, f.relative_path FROM files f JOIN sources s ON s.id = f.source_id
                WHERE f.relative_path {'= ?' if exact else 'LIKE ?'}{' AND s.source_id = ?' if source else ''}
                ORDER BY f.relative_path LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), *src_args, limit),
        ).fetchall()
    finally:
        conn.close()
    return {
        "types": types,
        "methods": methods,
        "fields": fields,
        "properties": properties,
        "strings": strings,
        "files": files,
        "limit": limit,
    }


def symbol(repo_root: Path, name: str, include_generated: bool = False, source: str | None = None) -> dict:
    """Look up a type by name (or full name); report candidates when ambiguous."""
    conn, _ = _connect(repo_root)
    try:
        name = name.strip()
        if "::" in name:
            source, _, name = name.partition("::")
            source = source.strip() or None
        gen = "" if include_generated else " AND t.is_compiler_generated = 0"
        src = " AND s.source_id = ?" if source else ""
        src_args = (source,) if source else ()
        rows = conn.execute(
            f"""SELECT t.*, f.relative_path, s.source_id AS source_id FROM types t
                JOIN files f ON f.id = t.file_id JOIN sources s ON s.id = t.source_id
                WHERE (t.name = ? OR t.full_name = ?){gen}{src}
                ORDER BY s.source_id, t.full_name""",
            (name, name, *src_args),
        ).fetchall()
        if not rows:
            return {"found": False}
        if len(rows) > 1:
            return {"found": True, "ambiguous": True,
                    "candidates": [f"[{r['source_id']}] {r['full_name']}" for r in rows]}
        row = rows[0]
        bases = conn.execute(
            """SELECT i.relation, i.target_name FROM inheritance i
               WHERE i.type_id = ? ORDER BY i.relation, i.target_name""",
            (row["id"],),
        ).fetchall()
        methods = conn.execute(
            """SELECT signature, visibility, is_static, is_virtual, is_override FROM methods
               WHERE type_id = ? ORDER BY start_line""",
            (row["id"],),
        ).fetchall()
        fields = conn.execute(
            """SELECT name, field_type, visibility, is_static, is_const FROM fields
               WHERE type_id = ? ORDER BY start_line""",
            (row["id"],),
        ).fetchall()
        properties = conn.execute(
            """SELECT name, property_type, has_getter, has_setter, is_static FROM properties
               WHERE type_id = ? ORDER BY start_line""",
            (row["id"],),
        ).fetchall()
        derived = conn.execute(
            """SELECT t2.full_name FROM inheritance i JOIN types t2 ON t2.id = i.type_id
               WHERE i.target_type_id = ? ORDER BY t2.full_name LIMIT 50""",
            (row["id"],),
        ).fetchall()
        return {
            "found": True,
            "ambiguous": False,
            "type": row,
            "bases": bases,
            "methods": methods,
            "fields": fields,
            "properties": properties,
            "derived": [d["full_name"] for d in derived],
        }
    finally:
        conn.close()


def string_search(repo_root: Path, value: str, limit: int = DEFAULT_LIMIT, exact: bool = False) -> list:
    conn, _ = _connect(repo_root)
    try:
        where, params = _match("s.value", value, exact)
        rows = conn.execute(
            f"""SELECT s.value, s.classification, f.relative_path, s.start_line
                FROM strings s JOIN files f ON f.id = s.file_id
                WHERE {where}
                ORDER BY s.value, f.relative_path, s.start_line LIMIT ?""",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return rows


def snapshot_dir_for(repo_root: Path, relative_path: str) -> Path:
    """Locate the extraction snapshot directory that owns a relative file path."""
    conn, _ = _connect(repo_root)
    try:
        rows = conn.execute(
            """SELECT s.source_id, s.snapshot_id FROM files f
               JOIN sources s ON s.id = f.source_id WHERE f.relative_path = ?""",
            (relative_path,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        if row["source_id"] == "worldbox":
            base = Path(repo_root) / indexer.extractor.SNAPSHOTS_DIR
        elif row["source_id"] == "neomodloader":
            base = Path(repo_root) / indexer.extractor.NML_SNAPSHOTS_DIR
        else:
            continue
        source_dir = base / row["snapshot_id"] / "source"
        if source_dir.is_dir():
            return source_dir
    raise QueryError(f"file not found in any indexed snapshot: {relative_path}")


def current_snapshot_dir(repo_root: Path) -> Path:
    """Source dir of the WorldBox snapshot the current index was built from."""
    conn, _ = _connect(repo_root)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='snapshot:worldbox'").fetchone()
    finally:
        conn.close()
    if not row or not row["value"]:
        raise QueryError("index has no worldbox snapshot")
    source_dir = indexer.snapshot_source_dir(Path(repo_root), row["value"])
    if not source_dir.is_dir():
        raise QueryError(f"snapshot source dir missing: {row['value']}")
    return source_dir


def show(repo_root: Path, location: str, context: int = 5) -> dict:
    """Read file:line (+/- context) from the current extraction snapshot only."""
    if ":" in location:
        rel, _, line_text = location.rpartition(":")
        if not line_text.isdigit():
            raise QueryError(f"invalid location: {location}")
        line = int(line_text)
    else:
        rel, line = location, None
    rel = rel.replace("\\", "/").strip("/")
    if not rel or rel.startswith(".") or ":" in rel:
        raise QueryError("path must be relative to the snapshot source directory")

    source_dir = snapshot_dir_for(repo_root, rel)
    candidate = (source_dir / rel).resolve()
    if candidate != source_dir and source_dir not in candidate.parents:
        raise QueryError("path escapes the extraction snapshot")

    if not candidate.is_file():
        raise QueryError(f"file not found in snapshot: {rel}")
    lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    if line is None:
        line = 1
    line = max(1, min(line, len(lines)))
    start = max(1, line - context)
    end = min(len(lines), line + context)
    return {
        "path": rel,
        "line": line,
        "lines": [(no, lines[no - 1]) for no in range(start, end + 1)],
    }


# --- Z4: cross-symbol navigation ----------------------------------------------

RELATION_LIMIT = 50


def _parse_symbol_spec(conn: sqlite3.Connection, spec: str, source: str | None = None) -> dict:
    """Resolve '[source::]Type[.member[(sig)]]' to a definition."""
    spec = spec.strip()
    if "::" in spec:
        source, _, spec = spec.partition("::")
        source = source.strip() or None
    sig = None
    if "(" in spec:
        spec, _, sig_tail = spec.partition("(")
        sig = "(" + sig_tail
    source_filter = " AND s.source_id = ?" if source else ""
    source_args = (source,) if source else ""

    def find_types(name: str):
        return conn.execute(
            f"""SELECT t.id, t.full_name, t.kind, t.file_id, t.start_line, s.source_id
                FROM types t JOIN sources s ON s.id = t.source_id
                WHERE (t.full_name = ? OR t.name = ?){source_filter}
                ORDER BY s.source_id, t.full_name""",
            (name, name, *source_args),
        ).fetchall()

    parts = spec.split(".")
    for split in range(len(parts) - 1, 0, -1):
        type_name = ".".join(parts[:split])
        member = ".".join(parts[split:])
        rows = find_types(type_name)
        if len(rows) == 1 and member:
            return _resolve_member_spec(conn, rows[0], member, sig)
        if len(rows) == 1 and not member:
            return {"kind": "type", "row": rows[0]}
        if len(rows) > 1:
            return {"kind": "ambiguous", "candidates": [f"[{r['source_id']}] {r['full_name']}" for r in rows]}
    rows = find_types(spec)
    if len(rows) == 1:
        return {"kind": "type", "row": rows[0]}
    if len(rows) > 1:
        return {"kind": "ambiguous", "candidates": [f"[{r['source_id']}] {r['full_name']}" for r in rows]}
    return {"kind": "not_found"}


def _resolve_member_spec(conn: sqlite3.Connection, type_row, member: str, sig: str | None) -> dict:
    def with_file(sql, params, kind):
        row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return {"kind": kind, "row": row, "owner": type_row["full_name"]}

    if sig:
        full_sig = f"{member}{sig}"
        m = with_file(
            "SELECT id, name, signature, return_type, type_id, file_id, start_line FROM methods"
            " WHERE type_id=? AND signature=?",
            (type_row["id"], full_sig), "method",
        )
        if m:
            return m
    methods = conn.execute(
        "SELECT id, name, signature, return_type, type_id, file_id, start_line FROM methods"
        " WHERE type_id=? AND name=? ORDER BY signature",
        (type_row["id"], member),
    ).fetchall()
    if len(methods) == 1:
        return {"kind": "method", "row": methods[0], "owner": type_row["full_name"]}
    if len(methods) > 1:
        return {
            "kind": "ambiguous",
            "candidates": [f"{type_row['full_name']}.{m['signature']}" for m in methods],
        }
    field = with_file(
        "SELECT id, name, field_type AS type, type_id, file_id, start_line FROM fields"
        " WHERE type_id=? AND name=?",
        (type_row["id"], member), "field",
    )
    if field:
        return field
    prop = with_file(
        "SELECT id, name, property_type AS type, type_id, file_id, start_line FROM properties"
        " WHERE type_id=? AND name=?",
        (type_row["id"], member), "property",
    )
    if prop:
        return prop
    return {"kind": "not_found"}


def _definition_line(conn: sqlite3.Connection, file_id: int, line: int | None) -> str:
    row = conn.execute("SELECT relative_path FROM files WHERE id=?", (file_id,)).fetchone()
    if row is None:
        return "?"
    return f"{row['relative_path']}:{line}" if line else row["relative_path"]


def lookup_symbol(repo_root: Path, spec: str, source: str | None = None) -> dict:
    conn, _ = _connect(repo_root)
    try:
        return _parse_symbol_spec(conn, spec, source=source)
    finally:
        conn.close()


def source_stats(repo_root: Path) -> dict:
    """Per-source counts + cross-source edges (Z5 metrics)."""
    conn, _ = _connect(repo_root)
    try:
        sources = [row["source_id"] for row in conn.execute("SELECT source_id FROM sources ORDER BY source_id")]
        per_source = {}
        for source_id in sources:
            row = conn.execute(
                """SELECT
                     (SELECT COUNT(*) FROM files f JOIN sources s ON s.id=f.source_id WHERE s.source_id=?) AS files,
                     (SELECT COUNT(*) FROM types t JOIN sources s ON s.id=t.source_id WHERE s.source_id=?) AS types,
                     (SELECT COUNT(*) FROM methods m JOIN sources s ON s.id=m.source_id WHERE s.source_id=?) AS methods,
                     (SELECT COUNT(*) FROM fields fl JOIN sources s ON s.id=fl.source_id WHERE s.source_id=?) AS fields,
                     (SELECT COUNT(*) FROM properties p JOIN sources s ON s.id=p.source_id WHERE s.source_id=?) AS properties,
                     (SELECT COUNT(*) FROM strings st JOIN sources s ON s.id=st.source_id WHERE s.source_id=?) AS strings""",
                (source_id,) * 6,
            ).fetchone()
            per_source[source_id] = dict(row)
        cross = {}
        if "neomodloader" in sources and "worldbox" in sources:
            cross["nml_to_worldbox_type_refs"] = conn.execute(
                """SELECT COUNT(*) FROM type_references tr
                   JOIN types tgt ON tgt.id = tr.target_type_id JOIN sources sto ON sto.id = tgt.source_id
                   JOIN files ff ON ff.id = tr.from_file_id JOIN sources sfrom ON sfrom.id = ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND tr.resolution_status='resolved'"""
            ).fetchone()[0]
            cross["nml_to_worldbox_method_calls"] = conn.execute(
                """SELECT COUNT(*) FROM method_calls mc
                   JOIN methods callee ON callee.id = mc.callee_method_id
                   JOIN types ct ON ct.id = callee.type_id JOIN sources sto ON sto.id = ct.source_id
                   JOIN files ff ON ff.id = mc.file_id JOIN sources sfrom ON sfrom.id = ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND mc.resolution_status='resolved'"""
            ).fetchone()[0]
            cross["nml_to_worldbox_symbol_refs"] = conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN fields fl ON fl.id = sr.target_id AND sr.target_kind='field'
                   JOIN types ft ON ft.id = fl.type_id JOIN sources sto ON sto.id = ft.source_id
                   JOIN files ff ON ff.id = sr.from_file_id JOIN sources sfrom ON sfrom.id = ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND sr.resolution_status='resolved'"""
            ).fetchone()[0] + conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN properties pr ON pr.id = sr.target_id AND sr.target_kind='property'
                   JOIN types pt ON pt.id = pr.type_id JOIN sources sto ON sto.id = pt.source_id
                   JOIN files ff ON ff.id = sr.from_file_id JOIN sources sfrom ON sfrom.id = ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND sr.resolution_status='resolved'"""
            ).fetchone()[0]
        return {"sources": sources, "per_source": per_source, "cross": cross}
    finally:
        conn.close()


def refs(repo_root: Path, spec: str, limit: int = RELATION_LIMIT, include_all: bool = False, from_source: str | None = None) -> dict:
    conn, _ = _connect(repo_root)
    try:
        target = _parse_symbol_spec(conn, spec)
        if target["kind"] in ("not_found", "ambiguous"):
            return {"symbol": spec, "target": target, "definition": None, "references": []}
        row = target["row"]
        kind = target["kind"]
        status_filter = "" if include_all else " AND r.resolution_status IN ('resolved')"
        from_filter = ""
        from_args = ()
        if from_source:
            from_filter = " AND src.source_id = ?"
            from_args = (from_source,)

        references = []
        if kind == "type":
            definition = f"[{row['source_id']}] [{row['kind']}] {row['full_name']}  ({_definition_line(conn, row['file_id'], row['start_line'])})"
            hits = conn.execute(
                f"""SELECT r.reference_kind, r.resolution_status, r.line AS start_line, f.relative_path, src.source_id AS from_source
                    FROM type_references r
                    JOIN files f ON f.id = r.from_file_id JOIN sources src ON src.id = f.source_id
                    WHERE r.target_type_id = ?{status_filter}{from_filter}
                    ORDER BY f.relative_path, r.line LIMIT ?""",
                (row["id"], *from_args, limit),
            ).fetchall()
            for hit in hits:
                references.append(
                    {"location": f"{hit['relative_path']}:{hit['start_line']}",
                     "kind": hit["reference_kind"], "status": hit["resolution_status"],
                     "from_source": hit["from_source"]}
                )
        elif kind in ("field", "property"):
            table = "fields" if kind == "field" else "properties"
            owner = conn.execute("SELECT full_name FROM types WHERE id=?", (row["type_id"],)).fetchone()
            definition = f"[{kind}] {owner['full_name']}.{row['name']}  ({_definition_line(conn, row['file_id'], row['start_line'])})"
            hits = conn.execute(
                f"""SELECT r.reference_kind, r.resolution_status, r.start_line, f.relative_path, src.source_id AS from_source
                    FROM symbol_references r
                    JOIN files f ON f.id = r.from_file_id JOIN sources src ON src.id = f.source_id
                    WHERE r.target_id = ? AND r.target_kind = ?{status_filter}{from_filter}
                    ORDER BY f.relative_path, r.start_line LIMIT ?""",
                (row["id"], kind, *from_args, limit),
            ).fetchall()
            for hit in hits:
                references.append(
                    {"location": f"{hit['relative_path']}:{hit['start_line']}",
                     "kind": hit["reference_kind"], "status": hit["resolution_status"],
                     "from_source": hit["from_source"]}
                )
        else:  # method: call sites live in method_calls
            owner = conn.execute("SELECT full_name FROM types WHERE id=?", (row["type_id"],)).fetchone()
            definition = f"[method] {owner['full_name']}.{row['signature']}  ({_definition_line(conn, row['file_id'], row['start_line'])})"
            hits = conn.execute(
                f"""SELECT mc.resolution_status, mc.line, f.relative_path, src.source_id AS from_source
                    FROM method_calls mc
                    JOIN files f ON f.id = mc.file_id JOIN sources src ON src.id = f.source_id
                    WHERE mc.callee_method_id = ?{''
                        if include_all else " AND mc.resolution_status = 'resolved'"}{from_filter}
                    ORDER BY f.relative_path, mc.line LIMIT ?""",
                (row["id"], *from_args, limit),
            ).fetchall()
            for hit in hits:
                references.append(
                    {"location": f"{hit['relative_path']}:{hit['line']}",
                     "kind": "call", "status": hit["resolution_status"],
                     "from_source": hit["from_source"]}
                )
        return {"symbol": spec, "target": target, "definition": definition,
                "references": references, "limit": limit}
    finally:
        conn.close()


def callers(repo_root: Path, spec: str, limit: int = RELATION_LIMIT, include_all: bool = False, source: str | None = None) -> dict:
    conn, _ = _connect(repo_root)
    try:
        target = _parse_symbol_spec(conn, spec)
        if target["kind"] in ("not_found", "ambiguous"):
            return {"symbol": spec, "target": target, "callers": []}
        if target["kind"] != "method":
            return {"symbol": spec, "target": target, "callers": [], "error": "not a method"}
        row = target["row"]
        owner = conn.execute("SELECT full_name FROM types WHERE id=?", (row["type_id"],)).fetchone()
        status_filter = "" if include_all else " AND mc.resolution_status = 'resolved'"
        src_filter = " AND cs.source_id = ?" if source else ""
        src_args = (source,) if source else ()
        hits = conn.execute(
            f"""SELECT cs.source_id AS caller_source, m.signature, m.name, mc.resolution_status, mc.line, f.relative_path
                FROM method_calls mc
                LEFT JOIN methods m ON m.id = mc.caller_method_id
                LEFT JOIN types ct ON ct.id = m.type_id
                LEFT JOIN sources cs ON cs.id = ct.source_id
                JOIN files f ON f.id = mc.file_id
                WHERE mc.callee_method_id = ?{status_filter}{src_filter}
                ORDER BY f.relative_path, mc.line LIMIT ?""",
            (row["id"], *src_args, limit),
        ).fetchall()
        return {
            "symbol": spec,
            "target": target,
            "definition": f"[method] {owner['full_name']}.{row['signature']}",
            "callers": [
                {"caller": (f"[{hit['caller_source']}] " if hit["caller_source"] else "")
                           + (hit["signature"] or "?") + (f"  ({hit['relative_path']}:{hit['line']})"),
                 "status": hit["resolution_status"]}
                for hit in hits
            ],
            "limit": limit,
        }
    finally:
        conn.close()


def callees(repo_root: Path, spec: str, depth: int = 1, limit: int = RELATION_LIMIT) -> dict:
    conn, _ = _connect(repo_root)
    try:
        target = _parse_symbol_spec(conn, spec)
        if target["kind"] in ("not_found", "ambiguous"):
            return {"symbol": spec, "target": target, "tree": []}
        if target["kind"] != "method":
            return {"symbol": spec, "target": target, "tree": [], "error": "not a method"}
        depth = max(1, min(depth, 5))
        visited: set[int] = set()
        tree = _callees_level(conn, target["row"]["id"], depth, limit, visited, 0)
        return {"symbol": spec, "target": target, "tree": tree, "limit": limit}
    finally:
        conn.close()


def _callees_level(conn, method_id: int, depth: int, limit: int, visited: set, level: int) -> list:
    if level >= depth or method_id in visited:
        return []
    visited.add(method_id)
    hits = conn.execute(
        """SELECT mc.callee_method_id, mc.callee_name, mc.callee_signature_hint,
                  mc.declaring_type_hint, mc.resolution_status, mc.line, f.relative_path,
                  m.signature AS caller_sig, cs.source_id AS callee_source
           FROM method_calls mc
           LEFT JOIN methods m ON m.id = mc.callee_method_id
           LEFT JOIN types ct ON ct.id = m.type_id
           LEFT JOIN sources cs ON cs.id = ct.source_id
           JOIN files f ON f.id = mc.file_id
           WHERE mc.caller_method_id = ?
           ORDER BY f.relative_path, mc.line LIMIT ?""",
        (method_id, limit),
    ).fetchall()
    out = []
    for hit in hits:
        entry = {
            "call": (f"[{hit['callee_source']}] " if hit["callee_source"] else "")
                    + (hit["declaring_type_hint"] or "?") + "." + (hit["callee_signature_hint"] or hit["callee_name"] + "()"),
            "status": hit["resolution_status"],
            "location": f"{hit['relative_path']}:{hit['line']}",
            "children": [],
        }
        if hit["callee_method_id"] is not None:
            entry["children"] = _callees_level(conn, hit["callee_method_id"], depth, limit, visited, level + 1)
        out.append(entry)
    return out


def derived(repo_root: Path, type_spec: str, recursive: bool = False, source: str | None = None) -> dict:
    conn, _ = _connect(repo_root)
    try:
        src_filter = " AND s.source_id = ?" if source else ""
        src_args = (source,) if source else ()
        rows = conn.execute(
            f"""SELECT t.id, t.full_name, t.kind, s.source_id FROM types t
                JOIN sources s ON s.id = t.source_id
                WHERE (t.full_name=? OR t.name=?){src_filter}""",
            (type_spec, type_spec, *src_args),
        ).fetchall()
        if not rows:
            return {"type": type_spec, "found": False}
        if len(rows) > 1:
            return {"type": type_spec, "found": True, "ambiguous": True,
                    "candidates": [f"[{r['source_id']}] {r['full_name']}" for r in rows]}
        root_id = rows[0]["id"]
        result: list[str] = []
        frontier = [root_id]
        seen = {root_id}
        while frontier:
            current = frontier.pop(0)
            hits = conn.execute(
                """SELECT t.full_name, t.id, s.source_id FROM inheritance i
                   JOIN types t ON t.id = i.type_id JOIN sources s ON s.id = t.source_id
                   WHERE i.target_type_id = ? ORDER BY s.source_id, t.full_name""",
                (current,),
            ).fetchall()
            for hit in hits:
                if hit["id"] in seen:
                    continue
                seen.add(hit["id"])
                if source is None or hit["source_id"] == source:
                    result.append(f"[{hit['source_id']}] {hit['full_name']}")
                if recursive:
                    frontier.append(hit["id"])
        return {"type": rows[0]["full_name"], "found": True, "derived": result, "recursive": recursive}
    finally:
        conn.close()


def overrides(repo_root: Path, spec: str) -> dict:
    """Type.method -> derived types that override it (via inheritance graph)."""
    conn, _ = _connect(repo_root)
    try:
        target = _parse_symbol_spec(conn, spec)
        if target["kind"] != "method":
            return {"symbol": spec, "target": target, "overrides": []}
        row = target["row"]
        base_name = row["name"]
        sig = row["signature"]
        hits = conn.execute(
            """SELECT DISTINCT t.full_name, m.signature FROM methods m
               JOIN types t ON t.id = m.type_id
               WHERE m.name = ? AND m.is_override = 1
                 AND t.id IN (
                   WITH RECURSIVE sub(id) AS (
                     SELECT ? UNION SELECT i.type_id FROM inheritance i JOIN sub ON i.target_type_id = sub.id
                   ) SELECT id FROM sub
                 )
               ORDER BY t.full_name""",
            (base_name, row["type_id"]),
        ).fetchall()
        return {"symbol": spec, "overrides": [f"{h['full_name']}.{h['signature']}" for h in hits]}
    finally:
        conn.close()
