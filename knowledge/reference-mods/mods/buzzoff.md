# BuzzOff

## Identity

- Name: BuzzOff v1.1.1
- Source ID: `ref:buzzoff`
- Dir: `BuzzOff_1.1.1`
- Files: 15 total / 1 C#
- Confidence: Verified

## Purpose

阻止昆虫单位（bee/fly/butterfly/grasshopper/beetle）经方碑/飞升进化，并可阻止/定时清除蜂巢建筑。

## Systems

- Primary: Buildings, Actor
- Secondary: Utility

## Key Implementation

- `Main.cs` (L10-69) — 全部逻辑（70 行）：addBuilding 否决、双目标进化拦截、协程清扫

## Techniques

否决建筑生成（Prefix `__result = null; return false`）、单注解打两方法（[HarmonyPatch]×2 堆叠共用 Prefix）、协程低频轮询 World.world.buildings、NML SWITCH 配置即时读取

## WorldBox Usage

BuildingManager.addBuilding / BuildingAsset.id / Building.startDestroyBuilding / ActionLibrary.{tryToEvolveUnitViaMonolith,tryToEvolveUnitViaAscension} / World.world.buildings

## NeoModLoader Usage

- BasicMod<T> / GetConfig / default_config.json SWITCH+IconPath（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| BuildingManager.addBuilding | Prefix(skip+result null) | Main.cs:14 | 禁蜂巢生成 |
| ActionLibrary.tryToEvolveUnitViaMonolith / ViaAscension | Prefix | Main.cs:30-31 | 禁虫进化 |

## Reusable Ideas

- "否决生成"范式：Prefix 设 `__result=null` 并返回 false，源头掐掉建筑/单位创建（Main.cs:22-26）
- 多目标共用 Prefix 注解堆叠写法（Main.cs:30-31）
- 协程低频轮询做持续清理（Main.cs:57-69）

## Pattern Candidates

- `spawn-veto-prefix`

## Evidence

- Main.cs:10,16-27,32-51,59-68 / default_config.json（7 个 SWITCH 含图标）

## Notes

轮询协程每秒全建筑遍历，量大时有成本；纯行为 mod 无本地化问题。
