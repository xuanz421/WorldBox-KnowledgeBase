# Reference Mod Knowledge Catalogue

对本地登记的全部 Reference Mods（21 个）的**证据化知识采掘**结果。回答：未来遇到某个 WorldBox Modding 问题时，应该看哪个 mod、看哪个文件、看哪个实现、以及为什么。

> Reference Mod profiles are evidence-backed knowledge artifacts, not copies of source projects.
> 所有 mod 原目录 READ ONLY；本目录只存放结论与 `file:line` 证据。

## 结构

```text
catalog.json             机器可读目录（主入口）
catalog.csv              同内容的 CSV
system-matrix.csv        mod × system 矩阵（role: primary/secondary）
pattern-candidates.jsonl Z7 候选 pattern（未去重，多 mod 可同名）
unresolved.jsonl         采掘中发现的 WBKB 缺口/未解问题
mods/<mod-id>.md         每个 mod 的证据化 profile（21 个）
CROSS_MOD_SUMMARY.md     跨 mod 对比与覆盖总结
```

## Evidence Status

- **Verified** — 结论直接来自代码（带 file:line 证据）
- **Mostly Verified** — 主体 Verified，部分段落采样阅读或 NML API 来源待确认
- **Unverified** — 明确标注的不确定项（主要见于 NML/NCMS API 来源区分）

## 如何找一个相关 mod

按系统：查 `system-matrix.csv`（role=primary 优先）；按技术：`catalog.json` 的 techniques/harmony_targets；按可复用做法：`pattern-candidates.jsonl`。

## By System（primary，Top）

- **Actor**：guigu-cultivation, xuanjian-xianzu, xuanmen-daojie, thefantasyworld, sandbox
- **Traits**：guigu-cultivation, xuanjian-xianzu, xuanmen-daojie, thefantasyworld, incensefiredway, xavii-nation-types
- **Combat**：guigu-cultivation, xuanmen-daojie, thefantasyworld, incensefiredway
- **Kingdom**：guigu-cultivation, xavii-nation-types, sandbox
- **UI**：powerbox, xuanjian-xianzu, actorhistory, familytree, sandbox
- **Save/Persistence**：guigu-cultivation, actorhistory, xuanmen-daojie, xuanjian-xianzu
- **Buildings**：xuanjian-xianzu, buzzoff, creepmobboost
- **Map**：mapdeal, worldresilience
- **Events**：xavii-nation-types, actorhistory

## By Technique

- **Harmony Prefix 否决/替换**：buzzoff, nerffiredamage, worldresilience, xuanmen-daojie
- **Harmony Transpiler**：guigu-cultivation, xuanmen-daojie, chinesename
- **NML Feature 体系**：powerbox（教学样本）
- **运行时资产注入（零 Harmony）**：creepmobboost, mapdeal
- **actor.data 键值持久化**：guigu-cultivation, incensefiredway, xuanmen-daojie, chinesename
- **SQLite 存储**：actorhistory
- **UI 克隆注入**：actorhistory, familytree, sandbox
- **程序集扫描自动注册**：chinesename
