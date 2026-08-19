# Pattern: world-tick-integration

## Status

Strong Verified

## Goal

为持续运行的世界级系统（月结修炼/经济/生态）选择正确的每帧/周期驱动入口——三条已验证路线及选择标准。

## When to Use

系统需要"随游戏时间推进"而非事件触发时。选错入口会导致暂停/读档期间偷跑或性能崩坏。

## Relevant Systems

World, Mod Lifecycle, Utility

## Core WorldBox Types

`BatchActors.u8_checkUpdateTimers` / `WorldBehaviourAsset` + `AssetManager.world_behaviours` / `MapBox.updateSimulation` / `MapBox.on_world_loaded`（一次性） / ai.behaviours 节点（如 `KingdomBehCheckKing.execute`）

## Implementation Flow

按需求三选一：

**路线 A — BatchActors Postfix（重度系统）**：挂在引擎已有批处理帧循环上，配 HashSet 特质缓存 + 年份缓存 + 节流（0.5s）+ 分帧预算（每帧处理 N 个单位）
**路线 B — WorldBehaviourAsset 闭包（周期任务）**：运行时 `new WorldBehaviourAsset{ action = delegate{...} }` 注册到 world_behaviours，零继承零 patch
**路线 C — 行为树节点 Prefix（实体级系统）**：Patch `XxxBehCheckYyy.execute` 作为该类实体的 tick 入口，天然按实体节奏

一次性初始化用 `MapBox.on_world_loaded` Delegate.Combine（guigu）。

## Reference Implementations

Route A:
- Mod: ref:xuanmen-daojie — File: code/Patches/BatchActorsPatches.cs:47 — Why: 每帧系统总线+缓存+节流完整工程
- Mod: ref:guigu-cultivation — File: Code/Core/CultivationSystem.cs:44-118 — Why: 分帧切片+读档牺牲窗（重负载最佳实践）

Route B:
- Mod: ref:shtoolkit — File: Code/sh_toolkit_main.cs:96-115 — Why: 匿名闭包注册周期刷兵

Route C:
- Mod: ref:xavii-nation-types — File: Code/Patches/KingdomBehCheckKingPatch.cs:11-33 — Why: 政体系统借行为树 tick

## Caveats

- **暂停语义**：BatchActors/updateSimulation 随游戏暂停停止；要"暂停仍跑"用 Unity 协程并自查 `Config.paused`（buzzoff 反例：轮询不查暂停）
- **读档窗口**：世界半初始化时 tick 会 NRE——guigu 的"牺牲窗"（读档后首帧放弃处理）与 Phase 延迟链是解法
- **Route B 无法精细控制顺序**，重逻辑勿用

## Evidence

- ref:xuanmen-daojie code/Patches/BatchActorsPatches.cs:47,88-160
- ref:guigu-cultivation Code/Core/CultivationSystem.cs:44-118 / Code/Sect/SectBootstrap.cs:124-210
- ref:shtoolkit Code/sh_toolkit_main.cs:96-115
- ref:xavii-nation-types Code/Patches/KingdomBehCheckKingPatch.cs:11-33
- WorldBox: BatchActors/WorldBehaviourAsset（WBKB 索引 verified）

## Provenance

Derived from: ref:xuanmen-daojie, ref:guigu-cultivation, ref:shtoolkit, ref:xavii-nation-types, ref:xuanjian-xianzu
