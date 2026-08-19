# Pattern: private-api-reflection

## Status

Verified

## Goal

通过反射/Traverse 访问 WorldBox 私有成员（tiles_map、_cached_sprite、私有方法），实现公开 API 覆盖不到的操作。

## When to Use

公开 API 无法达成时（地图数组访问、贴图重载、私有生成管线）。是"最后的手段"，不是首选。

## Relevant Systems

Utility, Map, Assets

## Core WorldBox Types

`MapBox.tiles_map`（私有 WorldTile[,]）/ `ActorAsset._cached_sprite` / `ActorAssetLibrary.loadTexturesAndSprites`（私有方法）/ SmoothLoader 内部任务链 / `IslandsCalculator`（Traverse）

## Implementation Flow

1. `AccessTools.Field/Method(typeof(X), "name")` 或 Harmony Traverse 取成员
2. 每次访问 try/catch + null 检查——成员名在版本更新中可能变化
3. 高频访问缓存 FieldInfo/MethodInfo
4. 批量场景（地图）：一次反射取数组引用，之后直接用数组索引（不要每 tile 反射）

## Reference Implementations

- ref:mapdeal — Code/Base.MapChange.cs:29-40（tiles_map 快照）+ :214-312（SmoothLoader 链复刻，反射 _first_gen 等 5 个私有字段）
- ref:guigu-cultivation — Code/Core/ModCreatureRegistry.cs:28-41（_cached_sprite + 私有 loadTexturesAndSprites 调用）
- ref:worldresilience — WorldResilience.cs（Traverse: islands_calculator/getRandomTile/IsOceanAround/tiles_list）

## Caveats

- **版本脆弱性最高**：所有私有成员名都无兼容承诺；WorldBox 更新后逐一回归（这也是 mapdeal targetGameBuild 停在旧版的原因）
- 反射调用私有方法的参数签名同样无承诺
- 能用公开 API（AssetManager/MapAction/Finder）就用——mapdeal 的 terrafoamTile 部分即公开 API

## Evidence

- ref:mapdeal Code/Base.MapChange.cs:29,218,254-276
- ref:guigu-cultivation Code/Core/ModCreatureRegistry.cs:28-41
- ref:worldresilience WorldResilience.cs:95-104（Traverse 用法）

## Provenance

Derived from: ref:mapdeal, ref:guigu-cultivation, ref:worldresilience
