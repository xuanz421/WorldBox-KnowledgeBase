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

## Reference Graph Layer (v0.5)

```text
Raw Source
   ↓
Declaration Index  (schema v1 layer)
   ↓
Symbol Resolution  (tools/wbkb/resolver.py — 继承链 + 作用域 + overload 仲裁)
   ↓
Reference Graph  (symbol_references / method_calls / type_references, schema v2)
   ↓
Query Layer  (refs | callers | callees | derived | overrides | show, 支持 --json)
```

> WBKB reference resolution is best-effort static analysis and explicitly
> preserves unresolved/ambiguous edges rather than guessing.

* 两遍构建：Pass 1 声明 → Pass 2 引用（局部作用域推导：参数/局部/`var new`/cast/as/链式访问/隐式 this）。
* resolution status 四态：resolved / ambiguous / unresolved / external，precision 优先于 recall。
* virtual/interface 调用按 compile-time 目标链接；`derived`/`overrides` 经 inheritance graph 独立查询。
* 幂等 identity = source snapshot + schema version + indexer version + resolver version。

## Structured Index Layer (v0.4)

```text
External Sources
       ↓
Discovery / Registry
       ↓
Extraction
       ↓
Raw Source Snapshot
       ↓
Structured Index  (tools/wbkb — python -m wbkb index worldbox, tree-sitter C# parser)
       ↓
SQLite  (data/generated/index/wbkb.db, schema v1, 不进 Git)
       ↓
Search / Symbol / Show  (wbkb search | symbol | string | show | stats)
```

* raw source = **generated evidence**；index = **structured retrieval layer**——只存原始事实、source location、symbol identity、relationships、searchable text，不存 LLM 摘要。
* 索引以 source snapshot 为 key（assembly sha + extractor 版本），数据库 meta 自描述对应关系；重复运行 `index worldbox` 在输入未变时返回 UNCHANGED。
* 解析 best-effort：单文件 parse failure 记录 parse_status（OK/PARTIAL/FAILED）后继续，失败率超阈值才判定 index 无效。
* 所有查询结果都带 `relative_path:line`（相对 snapshot，无机器路径）；`show` 只能读 snapshot 内文件（path traversal 防护）。
* deterministic tooling：全程不调用 LLM/外部 API，可无限免费 rebuild。

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
