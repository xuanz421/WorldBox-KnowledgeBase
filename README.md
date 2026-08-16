# WorldBox Knowledge Base (WBKB)

WBKB 是一个独立的、本地优先的 WorldBox Modding 知识基础设施项目。

## Purpose

WBKB 未来负责：

* ingest WorldBox source / assemblies
* ingest NeoModLoader references
* index reference mods
* structured code search
* API usage lookup
* pattern lookup
* version tracking
* AI-agent-friendly retrieval

## Non-goals

* WBKB 不是任何具体模组项目的专属文档库
* WBKB 不包含任何 consumer mod 的 gameplay design
* WBKB 不修改 WorldBox 原始文件
* WBKB 不修改 reference mods
* WBKB 不修改 NeoModLoader

## Quick Start

Configure / auto-discover sources, extract the registered WorldBox
Assembly-CSharp into a local generated source snapshot (requires .NET SDK;
run `dotnet tool restore` once in the repository root), then build the
structured SQLite index (requires `pip install -r tools/wbkb/requirements.txt`):

```bash
cd tools/wbkb
python -m wbkb discover
python -m wbkb extract worldbox
python -m wbkb index worldbox
python -m wbkb doctor
```

Query the index (search types/methods/fields/properties/strings/files,
inspect a symbol, navigate the reference graph, or show exact source
context from the snapshot):

```bash
python -m wbkb search miner --limit 20
python -m wbkb symbol Actor
python -m wbkb string citizen_job
python -m wbkb show Actor.cs:3875 --context 10
python -m wbkb refs Actor.data
python -m wbkb callers "AssetLibrary.get(string)"
python -m wbkb callees Actor.foo --depth 2
python -m wbkb derived BaseSimObject --recursive
python -m wbkb overrides BaseSimObject.update
python -m wbkb stats
```

Most query commands support `--json` for deterministic machine-readable
output. Reference resolution is precision-first: ambiguous stays ambiguous,
unknowns stay unresolved — never guessed.

Decompiled snapshots and the index database stay local under
`data/generated/` and are never committed.

## Layout

```text
docs/        architecture documents
config/      local source config (wbkb.local.json, not in Git; example committed)
schemas/     future database / structured data schemas
tools/       future ingestion, indexing, search CLIs
knowledge/   curated high-level knowledge with evidence sources
manifests/   version / metadata records
data/raw/       external raw inputs (not in Git)
data/generated/ generated databases / indexes (Git TBD by size)
data/cache/     temporary cache (not in Git)
```
