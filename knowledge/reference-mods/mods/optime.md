# Optime

## Identity

- Name: Optime v0.3.2-pre
- Source ID: `ref:optime`
- Dir: `Optime_0.3.2-pre`
- Files: 17 total / 10 C#
- Confidence: Verified

## Purpose

QoL+性能优化合集：相机不动时跳过 ZoneCamera 更新、暂停时冻结弹道、屏蔽分析/欢迎窗、高帧率下平滑模拟步长、开发者模式开关。

## Systems

- Primary: Utility（性能）, World
- Secondary: UI（OnGUI FPS 计数）, Config

## Key Implementation

- `Feature.cs` (L20-34) — `Feature<T> : MonoBehaviour` 框架：每功能一个组件、独立 Harmony 实例、OnEnable/OnDisable 时 PatchAll/UnpatchSelf 动态装卸
- `Main.cs` (L26-50) — 入口 + AddComponent 挂载全部功能组件按配置启用
- `QoL/FPS.cs` (L6-28) — calculateCurElapsed 按帧率缩放模拟步长
- `Optimizations/LazyZoneCamera.cs` — 相机静止时跳帧更新

## Techniques

泛型 Feature<T> 框架 + 配置 Callback 字符串绑定（`Class:SetLoaded`）、Prefix 返回 false 跳过、`ref bool __runOriginal = false` 变体、静态配置旗标直写（Config.firebase_available 等）

## WorldBox Usage

Config（静态旗标） / MapBox.{calculateCurElapsed,isPaused} / ZoneCamera.update / Projectile.update / MapStats.recalcCounters / MoveCamera / DebugConfig.setOption

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / GetConfig()/ModConfig（分区+BoolVal/IntVal）（Verified）
- default_config.json Callback 字符串绑定（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| ZoneCamera.update | Prefix(skip) | LazyZoneCamera.cs:13 | 相机静止跳过更新 |
| MapBox.calculateCurElapsed | Prefix(replace result) | FPS.cs:6 | 帧率平滑 |
| Projectile.update | Prefix(__runOriginal) | TimeStopProjectiles.cs:9 | 暂停冻结弹道 |
| MapStats.recalcCounters | Prefix(skip) | DisableMapStats.cs:7 | 跳过统计重算 |

## Reusable Ideas

- "每功能一个 Feature<T> 组件 + 配置 Callback 热切换补丁"框架，可直接移植到任何 NML mod（Feature.cs 全文 54 行）
- 高刷屏模拟稳定性：按 fps 缩放 fixedDeltaTime，解决 >60fps 游戏加速（FPS.cs:11-13）
- `__runOriginal = false` 写法让 Prefix 与其他 mod 更兼容

## Pattern Candidates

- `feature-toggle-framework`
- `frame-rate-adaptive-sim`

## Evidence

- Main.cs:34-36 / Feature.cs:34 / FPS.cs:8-15 / LazyZoneCamera.cs:15-24 / DisableMapStats.cs:9-11
