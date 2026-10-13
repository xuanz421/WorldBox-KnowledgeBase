# WBKB MCP integration

This is a **local, read-only MCP stdio server** powered by existing WBKB `query.py`. It does not redistribute or download WorldBox game source files.

## Install

From the repository root:

```bash
python -m pip install -r tools/wbkb/requirements.txt
python -m pip install -r tools/wbkb/requirements-mcp.txt
```

Build a local index using the existing README Quick Start (`discover`, `extract worldbox`, `index all`). In `tools/wbkb` run:

```bash
python -m wbkb.mcp_server
```

The process speaks MCP over stdio and must be started by an MCP-capable client, not used as an interactive shell.

Example configuration for MCP clients that support `mcpServers` and `cwd` (replace placeholders with **absolute paths**):

```json
{
  "mcpServers": {
    "wbkb": {
      "command": "python",
      "args": ["-m", "wbkb.mcp_server"],
      "cwd": "C:/path/to/WorldBox-KnowledgeBase/tools/wbkb",
      "env": {"WBKB_ROOT": "C:/path/to/WorldBox-KnowledgeBase"}
    }
  }
}
```

Some MCP clients do not support `cwd` or use different configuration keys; use a wrapper script or `PYTHONPATH` in that case.

## Available tools

`wbkb_search`, `wbkb_symbol`, `wbkb_lookup`, `wbkb_references`, `wbkb_callers`, `wbkb_callees`, `wbkb_derived`, `wbkb_overrides`, `wbkb_strings`, `wbkb_source_context`, `wbkb_stats`.

Responses return `{"ok": true, "data": ...}` or `{"ok": false, "error": "..."}`. Source-context queries require the local extracted source snapshot. This adapter uses the existing SQLite index and does not perform indexing.

## Safety and limitations

The current implementation serves an **existing local index**; it does not yet provide a source-free public distributable knowledge pack. That requires a separate, reviewed export/import pipeline. Do not deploy this source-reading process on a public network without access control and review of the content being exposed.

Verification: `python -m py_compile tools/wbkb/wbkb/mcp_server.py`, then connect through a compatible MCP inspector and invoke `wbkb_stats` and `wbkb_symbol(name="Actor")`.
