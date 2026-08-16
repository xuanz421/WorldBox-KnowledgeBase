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


def search(repo_root: Path, query: str, limit: int = DEFAULT_LIMIT, exact: bool = False, include_generated: bool = False) -> dict:
    conn, _ = _connect(repo_root)
    try:
        gen = "" if include_generated else " AND t.is_compiler_generated = 0"

        if exact:
            types = conn.execute(
                f"""SELECT t.full_name, t.kind, f.relative_path, t.start_line
                    FROM types t JOIN files f ON f.id = t.file_id
                    WHERE (t.name = ? OR t.full_name = ?){gen}
                    ORDER BY t.full_name LIMIT ?""",
                (query, query, limit),
            ).fetchall()
        else:
            pattern = f"%{_escape_like(query)}%"
            types = conn.execute(
                f"""SELECT t.full_name, t.kind, f.relative_path, t.start_line
                    FROM types t JOIN files f ON f.id = t.file_id
                    WHERE (t.name LIKE ? ESCAPE '\\' OR t.full_name LIKE ? ESCAPE '\\'){gen}
                    ORDER BY t.is_compiler_generated, t.full_name LIMIT ?""",
                (pattern, pattern, limit),
            ).fetchall()

        methods = conn.execute(
            f"""SELECT m.signature, t.full_name AS type_full, f.relative_path, m.start_line
                FROM methods m JOIN types t ON t.id = m.type_id JOIN files f ON f.id = m.file_id
                WHERE m.name {'= ?' if exact else 'LIKE ?'}{gen}
                ORDER BY t.full_name, m.signature LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), limit),
        ).fetchall()

        fields = conn.execute(
            f"""SELECT fl.name, fl.field_type, t.full_name AS type_full, f.relative_path, fl.start_line
                FROM fields fl JOIN types t ON t.id = fl.type_id JOIN files f ON f.id = fl.file_id
                WHERE fl.name {'= ?' if exact else 'LIKE ?'}{gen}
                ORDER BY t.full_name, fl.name LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), limit),
        ).fetchall()

        properties = conn.execute(
            f"""SELECT p.name, p.property_type, t.full_name AS type_full, f.relative_path, p.start_line
                FROM properties p JOIN types t ON t.id = p.type_id JOIN files f ON f.id = p.file_id
                WHERE p.name {'= ?' if exact else 'LIKE ?'}{gen}
                ORDER BY t.full_name, p.name LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), limit),
        ).fetchall()

        value_match = _match("s.value", query, exact)
        strings = conn.execute(
            f"""SELECT s.value, f.relative_path, s.start_line
                FROM strings s JOIN files f ON f.id = s.file_id
                WHERE {value_match[0]}
                ORDER BY s.value, f.relative_path, s.start_line LIMIT ?""",
            (*value_match[1], limit),
        ).fetchall()

        files = conn.execute(
            f"""SELECT relative_path FROM files
                WHERE relative_path {'= ?' if exact else 'LIKE ?'}
                ORDER BY relative_path LIMIT ?""",
            ((query if exact else f"%{_escape_like(query)}%"), limit),
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


def symbol(repo_root: Path, name: str, include_generated: bool = False) -> dict:
    """Look up a type by name (or full name); report candidates when ambiguous."""
    conn, _ = _connect(repo_root)
    try:
        gen = "" if include_generated else " AND t.is_compiler_generated = 0"
        rows = conn.execute(
            f"""SELECT t.*, f.relative_path FROM types t JOIN files f ON f.id = t.file_id
                WHERE (t.name = ? OR t.full_name = ?){gen}
                ORDER BY t.full_name""",
            (name, name),
        ).fetchall()
        if not rows:
            return {"found": False}
        if len(rows) > 1:
            return {"found": True, "ambiguous": True, "candidates": [r["full_name"] for r in rows]}
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


def current_snapshot_dir(repo_root: Path) -> Path:
    """Source dir of the snapshot the current index was built from."""
    conn, _ = _connect(repo_root)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='source_snapshot_id'").fetchone()
    finally:
        conn.close()
    if not row or not row["value"]:
        raise QueryError("index has no source_snapshot_id")
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

    source_dir = current_snapshot_dir(repo_root)
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
