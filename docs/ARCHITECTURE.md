# WBKB Architecture — v0 Baseline

这是 v0 baseline 架构，只定义方向和目录职责，不过度设计。

## Planned Layered Structure

```text
External Sources
      ↓
Ingestion / Extraction
      ↓
Structured Index / Database
      ↓
Knowledge / Retrieval
      ↓
Humans + Coding Agents
```

* **External Sources** — WorldBox assemblies / Assembly-CSharp, NeoModLoader, reference mods。一律 read-only。
* **Ingestion / Extraction** — 从外部来源提取 symbols、strings、references、Harmony patches 等结构化数据。
* **Structured Index / Database** — SQLite 等可快速查询的索引层（具体 schema 属于后续任务）。
* **Knowledge / Retrieval** — 面向人类与 coding agents 的检索入口：structured code search、API usage lookup、pattern lookup、version diff。
* **Humans + Coding Agents** — 最终消费者（Codex / ZCode / 其他 agent，以及人类）。

## Directory Responsibilities

### `tools/`

未来放：

* ingestion
* extraction
* indexing
* search
* diff
* validation CLI

### `schemas/`

未来放：

* database schema
* structured data schema

### `data/raw/`

外部输入或本地生成的原始数据。

默认不进入 Git。

### `data/generated/`

自动生成的数据库、index 等。

是否进入 Git 以后根据体积决定。

### `data/cache/`

临时缓存。

不得进入 Git。

### `knowledge/`

经过整理且有证据来源的高层知识：

* systems
* API notes
* patterns

### `manifests/`

记录：

* WorldBox version
* assembly hash
* NeoModLoader version
* reference-mod metadata
* schema version

## Out of Scope for v0

具体 SQLite tables、DLL extraction、WorldBox/NeoModLoader/reference mod 索引流程均属于后续任务（Z1+），现在不做决定。
