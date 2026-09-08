---
title: 模块库说明
aliases:
  - Pattern Library
---

# WorldBox Modding 模块库（Pattern Library）

从 Reference Mods 的证据化知识提炼的**可复用代码模块**库。回答："以后开发 Mod 时有什么可以直接拿来用——采用什么模块、参考哪些代码、涉及哪些 API、有哪些风险？"

## 状态含义

- **Strong Verified** — 多个独立 Reference Mod 实现 + WorldBox/NML API 对应关系经 WBKB 索引确认
- **Verified** — 一个可靠实现，核心 API 已确认
- **Mostly Verified / Inferred** — 不进入默认推荐（见 DEFERRED_CANDIDATES.md）

## 与 Reference Mod Profile 的关系

Profile（`knowledge/reference-mods/mods/`）描述"每个 mod 是什么"；模块（Pattern）描述"跨 mod 稳定的可复用实现"。模块的每条关键事实都通过 Evidence 回链到具体 mod 的 `file:line`——沿证据可直接回到源码（Reference Mods 目录只读）。

## 使用方式

- 人类：从 [模式索引.md](模式索引.md)（模块索引）按应用方向 / Goal / System 定位
- Agent：`catalog.json` 的稳定 `pattern_id`（如 `register-godpower`）可被直接引用；验证 API 时用 `wbkb search/symbol/refs/show`

## 消费统计

```text
Candidates (Z5): 56
Merged/consumed: 42
Verified patterns: 16（Strong Verified 8 / Verified 8）
Deferred: 12
Rejected: 2
```
