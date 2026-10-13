"""Read-only stdio MCP adapter around WBKB's existing SQLite query API."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from . import query

mcp = FastMCP("WorldBox Knowledge Base")

def _root():
    return Path(os.environ["WBKB_ROOT"]).expanduser().resolve() if os.environ.get("WBKB_ROOT") else Path(__file__).resolve().parents[3]

def _plain(value):
    if isinstance(value, sqlite3.Row):
        return {k: _plain(value[k]) for k in value.keys()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value

def _run(fn, *args, **kwargs):
    try:
        return {"ok": True, "data": _plain(fn(_root(), *args, **kwargs))}
    except (query.QueryError, sqlite3.Error, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

def _valid_limit(limit):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return limit

@mcp.tool()
def wbkb_search(term: str, source: str | None = None, limit: int = 20, exact: bool = False) -> dict:
    """Find indexed types, methods, fields, properties, strings and filenames."""
    try:
        return _run(query.search, term, source=source, limit=_valid_limit(limit), exact=exact)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

@mcp.tool()
def wbkb_symbol(name: str, source: str | None = None) -> dict:
    """Inspect a type's members, inheritance and source location."""
    return _run(query.symbol, name, source=source)

@mcp.tool()
def wbkb_lookup(spec: str, source: str | None = None) -> dict:
    """Resolve a type or member definition (e.g. Actor.data)."""
    return _run(query.lookup_symbol, spec, source=source)

@mcp.tool()
def wbkb_references(spec: str, from_source: str | None = None, limit: int = 50) -> dict:
    """Find references to a symbol."""
    try:
        return _run(query.refs, spec, from_source=from_source, limit=_valid_limit(limit))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

@mcp.tool()
def wbkb_callers(spec: str, source: str | None = None, limit: int = 50) -> dict:
    """Find methods calling an indexed method."""
    try:
        return _run(query.callers, spec, source=source, limit=_valid_limit(limit))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

@mcp.tool()
def wbkb_callees(spec: str, depth: int = 1, limit: int = 50) -> dict:
    """Explore calls made by a method (depth 1-3)."""
    if not 1 <= depth <= 3:
        return {"ok": False, "error": "depth must be between 1 and 3"}
    try:
        return _run(query.callees, spec, depth=depth, limit=_valid_limit(limit))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

@mcp.tool()
def wbkb_derived(type_name: str, recursive: bool = False, source: str | None = None) -> dict:
    """Find derived types."""
    return _run(query.derived, type_name, recursive=recursive, source=source)

@mcp.tool()
def wbkb_overrides(spec: str) -> dict:
    """Find method overrides."""
    return _run(query.overrides, spec)

@mcp.tool()
def wbkb_strings(value: str, exact: bool = False, limit: int = 20) -> dict:
    """Search literal strings in the local index."""
    try:
        return _run(query.string_search, value, exact=exact, limit=_valid_limit(limit))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

@mcp.tool()
def wbkb_source_context(location: str, context: int = 5) -> dict:
    """Read local extracted source context (file.cs:line). Requires a local snapshot."""
    if not 0 <= context <= 30:
        return {"ok": False, "error": "context must be between 0 and 30"}
    return _run(query.show, location, context=context)

@mcp.tool()
def wbkb_stats() -> dict:
    """Get index coverage and source statistics."""
    return _run(query.source_stats)

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
