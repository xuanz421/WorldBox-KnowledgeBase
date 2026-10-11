---
title: 参考模组知识目录
aliases:
  - Reference Mod Knowledge Catalogue
---

# Reference Mod Knowledge Catalogue

对已收录 Reference Mods（28 个）的**证据化知识采掘**结果。回答：未来遇到某个 WorldBox Modding 问题时，应该看哪个 mod、看哪个文件、看哪个实现、以及为什么。

> Reference Mod profiles are evidence-backed knowledge artifacts, not copies of source projects.
> 所有 mod 原目录 READ ONLY；本目录只存放结论与 `file:line` 证据。

## 结构

```text
mod-index.md              导航根（By System / By Technique / By Tier）
catalog.json             机器可读目录（主入口）
catalog.csv              同内容的 CSV
system-matrix.csv        mod × system 矩阵（role: primary/secondary）
pattern-candidates.jsonl Z7 候选 pattern（未去重，多 mod 可同名）
unresolved.jsonl         采掘中发现的 WBKB 缺口/未解问题
mods/<mod-id>.md         每个 mod 的证据化 profile（28 个，均含 Unique Methods 段）
mods/civilization-trait-expansion/ 城市经济 / 帝国管理 / 裂土封侯子树
mods/biology/            biology 深度研究子树（architecture / organs-health，Branch 递归分支）
CROSS_MOD_SUMMARY.md     跨 mod 对比与覆盖总结
```

## Evidence Status

- **Verified** — 结论直接来自代码（带 file:line 证据）
- **Mostly Verified** — 主体 Verified，部分段落采样阅读或 NML API 来源待确认
- **Unverified** — 明确标注的不确定项（主要见于 NML/NCMS API 来源区分）

## Unique Methods 筛选口径

每个 profile 的 Unique Methods 段收录「模组自有的、承载核心机制的方法」：

- **排除**：Harmony patch 管线接线（Patch Targets 表已覆盖）、配置/序列化样板、纯 getter/setter、Unity/NML 生命周期（OnModLoad 等）、UI 纯接线
- **纳入**：自定义系统 tick、状态机、算法核心、数据驱动初始化、独特存储/持久化方案
- 补丁方法体内承载完整算法时，方法本体计为独特方法（管线接线除外）；纯补丁微型模组可为 1-2 条或标注无
- 每条 = 方法签名 + 一句机制说明 + `file:line` 证据；跨树关联用 stable ID（`pattern_id` / system 路径），不建叶子互链

## 如何找一个相关 mod

按系统：查 `system-matrix.csv`（role=primary 优先）；按技术：`catalog.json` 的 techniques/harmony_targets；按可复用做法：`pattern-candidates.jsonl`。

## 导航

按 System / Technique / Tier 的完整导航见 [mod-index.md](mod-index.md)；权威机器可读目录为 `catalog.json` / `system-matrix.csv`。

## Catalogue Regeneration

`python tools/gen_reference_mod_catalog.py` 重建四份 catalog 产物；原始 inline harvest 以外的已收录条目保留其 catalog、matrix 与 candidate 证据，避免后续 intake 被旧 generator 删除。修改已有 inline 条目时同时更新 generator；profile 和子主题仍为手工证据文档。

文明特质拓展 v1.5.0（`ref:civilization-trait-expansion`）来自用户 zip，本地证据放在 git-ignored `data/raw/reference-mods/` 并登记 local config/registry；可移植身份进入 `manifests/source-registry.json`，证据版本 hashes 存于 profile。没有将完整外部源码或 PNG 收入 Git。
