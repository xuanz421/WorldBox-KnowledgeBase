---
title: MapDeal
aliases:
  - mapdeal
---

# MapDeal

## Identity

- Name: MapDeal v1.0.5（NCMS 时代 mod）
- Source ID: `ref:mapdeal`
- Dir: `MapDeal_1.0.5`
- Files: 6 total / 3 C#
- Confidence: Verified

## Purpose

IMGUI 地图工具：整张地图 tile 类型快照成数组，以镜像/颠倒/列阵/四角/中心/缩放方式"盖章"回（新）地图，附带最近邻去噪、自定义 Zone 尺寸重建地图、诅咒世界全解锁。

## Systems

- Primary: Map
- Secondary: World（生成管线）, UI（OnGUI）, Assets/Reflection

## Key Implementation

- `Code/Base.MapChange.cs` (L29-312) — 快照/贴图/缩放/去噪/重建地图全部算法
- `Code/Base.Main.cs` (L34-167) — NCMS [ModEntry] + 可拖动 IMGUI 控制面板
- `Code/Base.MapConfig.cs` — 四角常量

## Unique Methods

筛选口径：剔除 IMGUI 面板样板后，承载核心机制且原版无对应物的模组自有方法。

- `MapChange.save()` (Code/Base.MapChange.cs:27-41) — 反射取 MapBox.tiles_map，摊平为 main_type/top_type 两个二维数组快照
- `MapChange.setMap(string pStart)` (Code/Base.MapChange.cs:43-84) — 按四角起点翻转索引 + 镜像/颠倒/列阵取模平铺，terraformTile 逐 tile 盖章
- `MapChange.从中心开始布置()` (Code/Base.MapChange.cs:86-139) — 以地图中心对称向四象限展开，奇偶分块 extraX/Y 实现中心模式下的列阵
- `MapChange.recalcMap()` (Code/Base.MapChange.cs:141-182) — neighboursAll 邻域 main_type 多数投票（>4 票，或 =4 票且自身不在集合）触发 terraformTile 去噪
- `MapChange.suoFang()` (Code/Base.MapChange.cs:184-212) — 快照尺寸/当前地图尺寸比例做最近邻采样缩放贴图
- `MapChange.generateNewMap2()` (Code/Base.MapChange.cs:214-312) — 复刻原版 SmoothLoader 任务链（addClearWorld→反射写 ZONE_AMOUNT/world_laws→MapStats.initNewWorld→…→finishingUpLoading），注入自定义 Zone 数量重建地图

## Techniques

反射取 MapBox.tiles_map（WorldTile[,]）快照、MapAction.terraformTile 批量改地形、neighboursAll 多数投票去噪、复刻原版 SmoothLoader 生成任务链（addClearWorld→setMapSize→...→finishingUpLoading，自定义 ZONE_AMOUNT_X/Y）、反射读写私有字段、world_law 全解锁

## WorldBox Usage

MapBox.{tiles_map,setMapSize,addClearWorld,redrawTiles,cleanUpWorld,finishMakingWorld,lastGC} / WorldTile.{main_type,top_type,neighboursAll} / MapAction.terraformTile / SmoothLoader / MapStats.initNewWorld / MapSizeLibrary.getSize / WorldLaws/WorldLawLibrary / Config.ZONE_AMOUNT

## NeoModLoader Usage

无（NCMS [ModEntry] 旧式入口 + ReflectionUtility，仅以 mod.json 元数据被加载）

## Patch Targets

无 —— 纯反射+公共 API+OnGUI，零 Harmony 补丁

## Reusable Ideas

- 地图快照→印章配方：反射 tiles_map + main/top_type 二维组 + terrafoamTile 循环 = 任意"复制/变换地图"工具核心（Base.MapChange.cs:27-84）
- SmoothLoader 任务链完整复刻示例——自定义 Zone 数量重建地图，研究世界生成管线调序的最佳样本（:214-312）
- neighboursAll 多数投票去噪可泛化为地形平滑滤镜（:148-181）

## Pattern Candidates

- `map-snapshot-stamp`
- `smoothloader-generation-chain`

## Evidence

- Base.MapChange.cs:29,81,154-179,214-312 / Base.Main.cs:34,150-151,167

## Notes

NCMS 时代风格（targetGameBuild 523）；无 Harmony、无本地化；全解锁按钮是彩蛋功能。
