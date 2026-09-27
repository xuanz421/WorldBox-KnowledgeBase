---
title: SHToolkit
aliases:
  - shtoolkit
---

# SHToolkit（寒海辅助工具）

## Identity

- Name: SHToolkit v0.1.4（WorldBox 0.51.0+）
- Source ID: `ref:shtoolkit`
- Dir: `SHToolkitmod0.1.4-WorldBox0.51.0+`
- Files: 140 total / 20 C#
- Confidence: Mostly Verified

## Purpose

综合辅助工具集：自定义地图尺寸、超级暂停、随机刷兵 WorldBehaviour、自动存档间隔调节、UI 增强（Tooltip/拖拽排序/时钟按钮）、本地化扩展、原生 DLL 释放（bass.dll）。中文社区典型"百宝箱"型 mod。

## Systems

- Primary: Utility, UI, Save/Persistence, Mod Lifecycle
- Secondary: World（tile 追踪/自动存档）, Actor, Events, Assets

## Key Implementation

- `Code/sh_toolkit_main.cs` (L78-170) — 入口与完整生命周期；L96-115 WorldBehaviourAsset 匿名闭包注册随机刷兵
- `Code/sh_toolkit_harmony_save.cs` (L46-119) — AutoSaveManager Prefix 自定义间隔 + generateNewMap/loadData Postfix + landTile 缓存重建
- `Code/sh_toolkit_harmony_world.cs` (L46-91) — WorldTile.setTopTileType + 3 个 setTileType 重载合并 Postfix 维护 landTile 集合；超级暂停
- `Code/sh_toolkit_harmony_ui.cs` (L46-158) — PowerButton/DragOrderElement/PowerClockButton UI patch
- `Code/sh_toolkit_set.cs` (L33-45) — toggleActions/toggleBools 字典 + UnityAction<bool> 回调注册中心

## Unique Methods

筛选口径：剔除补丁接线与设置样板后，承载核心机制且原版无对应物的模组自有方法。

- `sh_toolkit_harmony_save.loadToolkitData` (Code/sh_toolkit_harmony_save.cs:107-119) — 全图扫描 Ground 层 `pot_spawn_units_auto` 瓦片重建 landTile 刷兵缓存（换图/读档经 SmoothLoader 排队执行）
- `sh_toolkit_harmony_save.update` (sh_toolkit_harmony_save.cs:48-75) — Prefix 重写自动存档计时：ForceAutoSave 在 lowMemory 下强制 autoSave（窗口激活/控制单位时推迟）
- `sh_toolkit_harmony_save.resetAutoSaveTimer` (sh_toolkit_harmony_save.cs:78-86) — skip-Prefix 把原版计时重置替换为写入自定义 `auto_save_interval`
- `sh_toolkit_harmony_world.setTileType` (sh_toolkit_harmony_world.cs:50-61) — 3 重载合并 Postfix：按 layer_type+biome_asset 增量增删 landTile 集合
- `sh_toolkit_harmony_world.checkMainSimulationUpdate` (sh_toolkit_harmony_world.cs:64-76) — SuperPause skip-Prefix：强制 `_is_paused`+`Config.paused` 并拦截模拟推进
- `Main.OnModLoad 匿名 WorldBehaviour action` (Code/sh_toolkit_main.cs:96-117) — 运行时注册 7.2~14.4s 随机刷兵 WorldBehaviour（空城/密度/概率/数量区间四重检查）
- `Main.Update SHAggression 段` (sh_toolkit_main.cs:206-216) — 每帧为空闲军队队长派发自定义任务 `sh_aggression_warrior_army_leader_move_to_attack_target`
- `Main.GetTilesBetweenPos` (sh_toolkit_main.cs:347-391) — Bresenham 直线瓦片遍历算法（供 RangedAttackIfClear 视线遮挡检查，消费点 harmony_other.cs:99-115）

## Techniques

Harmony.CreateAndPatchAll 分组注册、运行时创建 WorldBehaviourAsset 匿名 action（闭包）、JSON 设置持久化到 persistentDataPath、NCMS Utils（Windows.CreateNewWindow）、原生 DLL 部署、多载方法合并 patch、Toggle 字典驱动设置

## WorldBox Usage

WorldBehaviourAsset / WorldBehaviour / AssetManager.world_behaviours / World.world.units.createNewUnit / AutoSaveManager / MapBox.{generateNewMap,checkMainSimulationUpdate} / SaveManager.loadData / WorldTile.setTileType(3 overloads) / Finder.getUnitsFromChunk / Config.set_paused / ProjectileManager.checkCollision / PowerButton.showTooltip / LocalizedTextManager.loadLocalizedText

## NeoModLoader Usage

- BasicMod.OnModLoad / GetDeclaration().FolderPath（Verified）
- [ModEntry]（Unverified——可能来自 NCMS 而非 NML）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| AutoSaveManager.update | Prefix | sh_toolkit_harmony_save.cs:46 | 可配置自动存档间隔 |
| MapBox.checkMainSimulationUpdate | Prefix | sh_toolkit_harmony_world.cs:62 | SuperPause 冻结模拟 |
| WorldTile.setTileType×3 + setTopTileType | Postfix | sh_toolkit_harmony_world.cs:46-49 | 维护陆地瓦片缓存 |
| PowerButton.showTooltip | Postfix | sh_toolkit_harmony_ui.cs:72 | 自定义 tooltip |
| PowerLibrary.spawnCrabzilla / ControllableUnit.setControllableCreature | Prefix | sh_toolkit_harmony_ui.cs:157-159 | SuperPause 复位 + 速度归 x1 |
| PowerLibrary.spawnUnit | Prefix | sh_toolkit_harmony_other.cs:74-87 | 刷兵增强 |
| MonthLibrary.getMonth | Prefix | sh_toolkit_harmony_world.cs:90-102 | 月份环回修正 |
| LocalizedTextManager.loadLocalizedText | Prefix | sh_toolkit_harmony_other.cs:47 | 外置语言文件热载 |

## Reusable Ideas

- 运行时 `AssetManager.world_behaviours.add(new WorldBehaviourAsset{ action = delegate{...} })` 实现周期性世界 tick 任务，无需继承（main.cs L96-115）
- persistentDataPath + JSON 双向设置持久化，与存档解耦（main.cs L73-75,120-145）
- 多重载方法用一个 Postfix 类 + 多个 [HarmonyPatch] attribute 声明同一处理方法
- mod 文件夹内 DLL 复制到游戏目录实现原生库部署（main.cs L155-160）

## Pattern Candidates

- `worldbehaviour-runtime-scheduler`
- `dictionary-toggle-settings-center`
- `persistent-json-config`

## Evidence

- sh_toolkit_main.cs:77-84,96-115,127-145
- sh_toolkit_harmony_world.cs:46-49,62-63
- sh_toolkit_save.cs / set.cs:33-35

## Notes

NCMS 依赖使 NML-only 迁移需替换 Windows.CreateNewWindow 等。
