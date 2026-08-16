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

* WBKB 不是 NewEra 的专属文档库
* WBKB 不包含 NewEra gameplay design
* WBKB 不修改 WorldBox 原始文件
* WBKB 不修改 reference mods
* WBKB 不修改 NeoModLoader

## Quick Start

Configure / auto-discover sources:

```bash
cd tools/wbkb
python -m wbkb discover
python -m wbkb doctor
```

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
