# AGENTS.md — WBKB Repository Rules

## Language

* 与用户沟通使用中文
* code identifiers / API / class / method / field / compiler errors 保持英文

## Core Principle

WBKB 的核心目标是：

> 将昂贵的一次性代码调查转换成可持续复用、可自动重建、可快速查询的结构化知识。

回答 WorldBox/NML modding 问题前，先查已有知识，而不是从头调查（人类导航入口：根 `知识库索引.md`，forest 结构——链接只从索引指向叶子，跨树引用使用稳定 id 而非链接）：

* `knowledge/patterns/catalog.json` — 16 个验证过的 modding pattern（导航见 `knowledge/patterns/模式索引.md`）
* `knowledge/reference-mods/catalog.json` — 21 个 reference mod 的证据化 profile（导航见 `knowledge/reference-mods/模组索引.md`）
* `knowledge/systems/catalog.json` — WorldBox 系统 map（core types → `file` 入口；导航见 `knowledge/systems/源代码索引.md`）
* `wbkb` 索引（见下）— 反编译源码的结构化查询

## Commands

首次 setup（repo root）：

```powershell
dotnet tool restore                                  # ilspycmd，版本钉在 .config/dotnet-tools.json
pip install -r tools/wbkb/requirements.txt
```

验证（改代码或 knowledge/ 后必跑；无 CI，这些命令是唯一门禁）：

```powershell
cd tools/wbkb; python -m pytest tests -q             # 115 tests，~30s；RAG 测试用 fake embedding backend，无需下载模型
python -m pytest tests/test_core.py -q               # 单文件
python -m pytest "tests/test_core.py::HashTests::test_name" -q   # 单测（unittest 风格 node id）
python tools/validate_patterns.py                    # 失败 exit 1 + FAILED 列表
python tools/validate_reference_mod_catalog.py
```

CLI 入口（必须在 `tools/wbkb` 下运行——包未安装，靠 cwd import）：

```powershell
cd tools\wbkb
python -m wbkb discover                              # 写 config/wbkb.local.json + 更新 registry/manifest
python -m wbkb doctor
python -m wbkb extract worldbox|neomodloader|status  # --force 才强制重建
python -m wbkb index all|status                      # complete unified rebuild，~20s
python -m wbkb search|symbol|refs|callers|callees|derived|overrides|string|show|stats
python -m wbkb vector build                          # 语义索引（heavy deps）
python -m wbkb semantic "query"                      # 需先 vector build
```

## Environment Gotchas (Windows)

* 控制台默认 cp1252：`stats` 等命令输出非 ASCII（`→`）会 `UnicodeEncodeError`。先 `$env:PYTHONUTF8='1'`。
* `semantic` 每次进程内加载 bge-m3（sentence-transformers + torch，模型 `BAAI/bge-m3`），单次查询可能数分钟、首次需联网下载模型；索引查询不需要它。
* `WBKB_ROOT` 环境变量可覆盖 repo root（`__main__.py: repo_root()`）。

## Repo Facts

* 查询类命令依赖本地 index `data/generated/index/wbkb.db`（git-ignored；缺失时先 `index all`）。
* vector 索引在 `data/generated/vector/`（local qdrant + `state.json`），语料 = `knowledge/` + `docs/` 全部 markdown。
* 幂等约定：`extract` / `index` / `vector build` 输入未变时返回 `UNCHANGED`，只有 `--force` 才重建。
* `manifests/source-registry.json` 进 Git，只存源身份（hash / 版本 / 稳定 ID `worldbox` / `worldbox-publicized` / `neomodloader` / `ref:<name>`），禁止绝对路径（tests 强制）；本机路径只存在于 `config/wbkb.local.json` 与 `data/cache/source-registry.local.json`（均 git-ignored）。
* 源发现优先级：explicit override → local config → `WBKB_WORLDBOX_ROOT` → Steam library 探测 → 交互输入。
* 查询结果均带 snapshot 相对路径 `relative_path:line`（无机器路径）；`show` 只接受 snapshot 内相对路径（path traversal 防护）；`--source worldbox|neomodloader` 过滤；多数命令支持 `--json`。
* commit 约定：`vX.Y.Z <短描述>`（见 `git log`）。

## Editing knowledge/

validators 硬编码期望条数（16 patterns / 21 mods）并校验结构；增删条目必须同步多处：

* patterns：`catalog.json` + `<category>/<id>.md`，文件必须含固定 section 集（`# Pattern:` / `## Status` / `## Goal` / … 完整列表见 `tools/validate_patterns.py`）且正文引用 `.cs:行号` 证据；不在 catalog 的散落 `.md` 会被拒。
* reference-mods：`catalog.json` / `catalog.csv` / `system-matrix.csv` / `mods/<mod-id>.md` 四处 id 与条数必须一致；catalog 的 `primary_systems` 必须等于 matrix 中该 mod 的 role=primary 系统集合。

## Source Reliability

知识来源优先级（从高到低）：

1. WorldBox actual code / Assembly-CSharp
2. NeoModLoader actual code
3. Reference mods actual code
4. Generated indexes
5. Verified knowledge documentation
6. Inference

不得凭记忆猜 WorldBox API。回答 API 问题优先用 `wbkb search / symbol / refs / show` 查索引。

## Evidence Status

知识必须标注证据状态，实际词汇（validators 强制）：

* patterns: `Strong Verified` / `Verified` / `Mostly Verified` / `Inferred`（Inferred 不得进默认库）
* reference-mods: `Verified` / `Mostly Verified` / `Partial`

## Read Policy

优先：

`search -> targeted read -> broader read only if necessary`

禁止无目的递归读取全部源码。

## Repository Boundaries

WBKB 自身允许修改。

以下均默认 read-only external sources：

* WorldBox
* Assembly-CSharp
* NeoModLoader
* Reference Mods
* Consumer mod projects

WBKB must never inspect or depend on consumer mod projects for source discovery.

## Generated Data

自动生成内容必须尽可能可重建。

不要把大型二进制、缓存和完整外部源码无脑提交到 Git。

## Git

* 不自动 force push
* 不覆盖用户修改
* commit 只包含当前任务
* destructive Git operations 禁止（`reset --hard` / `clean -fd` 等）

## Efficiency

避免：

* 无意义 Review
* 重复总结
* 重复扫描
* 一个 symbol 为了确认 API 扫完整代码库
* 为了"完整"生成大量低价值自然语言摘要

## Stop Condition

任务完成即停止。

不要顺手实现任务外功能。
