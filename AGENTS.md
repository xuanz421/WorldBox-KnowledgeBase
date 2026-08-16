# AGENTS.md — WBKB Repository Rules

## Language

* 与用户沟通使用中文
* code identifiers / API / class / method / field / compiler errors 保持英文

## Core Principle

WBKB 的核心目标是：

> 将昂贵的一次性代码调查转换成可持续复用、可自动重建、可快速查询的结构化知识。

## Source Reliability

知识来源优先级（从高到低）：

1. WorldBox actual code / Assembly-CSharp
2. NeoModLoader actual code
3. Reference mods actual code
4. Generated indexes
5. Verified knowledge documentation
6. Inference

不得凭记忆猜 WorldBox API。

## Evidence Status

知识必须可以区分：

* Verified — 直接来自实际代码/程序集证据
* Inferred — 由证据合理推断
* Unknown — 未确认

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
