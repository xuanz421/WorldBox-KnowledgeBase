---
title: WorldResilience
aliases:
  - worldresilience
---

# WorldResilience

## Identity

- Name: WorldResilience v0.4.0（NML 旧式 IMod 接口）
- Source ID: `ref:worldresilience`
- Dir: `WorldResilience_0.4.0`
- Files: 5 total / 2 C#
- Confidence: Verified
- 本地源码：已移除（2026-09-27 discover 时目录不存在；以下证据基于移除前的源码阅读，证据状态不变）

## Purpose

侵蚀反向化：重写 WorldBehaviourActionErosion.updateErosion，让岩石风化成土、沙退化成土壤/草地、荒地复绿、偶发生成群系——世界被摧毁后自然"愈合"。注册 world_regrow 世界法则开关。

## Systems

- Primary: Map, World
- Secondary: Assets（法则）, Utility

## Key Implementation

- `WorldResilience.cs` (L95-276) — updateErosion Prefix 全量替换：岩→土→沙→浅海循环与海洋均质化（PerlinNoise 控制）
- `WorldResilience.cs` (L279-292) — WorldLaws.init Postfix + PlayerOptionData 注册自定义世界法则

## Techniques

NML 旧式 IMod 接口（OnLoad/OnUnload + Harmony.UnpatchID 卸载）、Prefix 返回 false 全量替换、Traverse 访问私有字段（islands_calculator/getRandomTile/IsOceanAround/tiles_list）、PerlinNoise、批量收集后统一 terraformMain

## WorldBox Usage

WorldBehaviourActionErosion.updateErosion / WorldLaws.init / PlayerOptionData / IslandsCalculator/TileIsland / TileLibrary/TileType / MapAction.{terraformMain,growGreens} / BiomeLibrary.pool_biomes / WorldLawLibrary / MapBox.instance

## NeoModLoader Usage

- IMod(OnLoad/OnUnload/GetDeclaration/GetGameObject)（Verified——旧式接口，非 BasicMod）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| WorldBehaviourActionErosion.updateErosion | Prefix | WorldResilience.cs:95 | 逆向侵蚀=世界自愈 |
| WorldLaws.init | Postfix | WorldResilience.cs:279 | 注册 world_regrow 法则 |

## Unique Methods

筛选口径说明：补丁方法体内承载完整算法时，方法本体计为独特方法（管线接线部分除外）。

- `WorldResilience.updateErosion 重写体` (WorldResilience.cs:L95-276) — 逆向侵蚀算法本体：岩→土→沙→浅海循环 + 海洋均质化（PerlinNoise 控制、Traverse 取私有字段、批量收集后统一 terraformMain）——整个模组的核心即此 ~180 行 Prefix 替换

## Reusable Ideas

- "Prefix 收集-统一 terraform"批处理地形改造（MAX_TILES_IN_LIST 限流）
- WorldLaws.init Postfix + PlayerOptionData 是自定义世界法则的标准入口

## Pattern Candidates

- `reverse-erosion-regrow`
- `custom-world-law-option`
- `traverse-private-map-api`

## Evidence

- WorldResilience.cs:31-43,95-104,110-112,270-275,279-291 / WorldResilienceLaws.cs:7-8

## Notes

mod.json 无 GUID；world_regrow 开关未被侵蚀逻辑消费（近似死代码）；GodPower/PowerButton 字段未用。
