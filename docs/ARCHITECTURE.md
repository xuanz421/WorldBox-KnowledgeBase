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

## Discovery Layer (v0.2)

```text
External Sources (read-only)
      ↓
Discovery  (tools/wbkb — python -m wbkb discover)
      ↓
Local Source Registry  (data/cache/source-registry.local.json — 不进 Git，含绝对路径)
      ↓
Committed Source Manifest  (manifests/source-registry.json — 进 Git，仅身份信息)
```

* `config/wbkb.local.json`（不进 Git）记录本机源位置；`config/wbkb.example.json`（进 Git）是 schema 模板。发现优先级：explicit override → local config → `WBKB_WORLDBOX_ROOT` 环境变量 → Steam library 探测 →（交互式）用户输入。**WBKB must never inspect or depend on consumer mod projects for source discovery.**
* **Committed manifest = source identity**（hash、版本、稳定 ID：`worldbox` / `worldbox-publicized` / `neomodloader` / `ref:<name>`）；**Local registry = source location**（绝对路径、时间戳）。二者严格分离，manifest 不得包含本机绝对路径。
* External sources 严格 read-only；重复运行 discover 输出每个源的 `UNCHANGED / CHANGED / NEW / MISSING`，内容未变时不重写文件。
* `python -m wbkb doctor` 提供简短健康检查（optional source 缺失不算致命）。

## WorldBox Extraction Layer (v0.3)

```text
Source Registry
      ↓
WorldBox Extraction  (tools/wbkb — python -m wbkb extract worldbox)
      ↓
Generated Raw Source Snapshot  (data/generated/worldbox/snapshots/, 不进 Git)
      ↓
Future Structured Index  (Z3)
```

* raw source = **generated evidence**：反编译产物，非原始 WorldBox 源码，不手工维护。
* snapshot 以 `game_version + assembly_sha256` 为 key（如 `worldbox-0.51.2-51d275f0168b`）；extraction identity 还包含 extractor 与 extractor_version——同一 assembly、不同 extractor 版本视为不同 extraction configuration。
* extractor = `ilspycmd`（local .NET tool，版本固定于 `.config/dotnet-tools.json`，`dotnet tool restore` 可复原）。
* 幂等：相同 assembly + extractor → `UNCHANGED`，跳过重新反编译；`--force` 才允许重建。临时目录验证通过后才原子替换 snapshot。
* 完整反编译源码只留在本地：`data/generated/*` 不进 Git，也不上传。

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
