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
- `Code/sh_toolkit_harmony_save.cs` (L46-98) — AutoSaveManager Prefix 自定义间隔 + generateNewMap/loadData Postfix
- `Code/sh_toolkit_harmony_world.cs` (L46-91) — WorldTile.setTopTileType + 3 个 setTileType 重载合并 Postfix 维护 landTile 集合；超级暂停
- `Code/sh_toolkit_harmony_ui.cs` (L46-158) — PowerButton/DragOrderElement/PowerClockButton UI patch
- `Code/sh_toolkit_set.cs` (L33-45) — toggleActions/toggleBools 字典 + UnityAction<bool> 回调注册中心

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
| PowerLibrary.spawnUnit / ControllableUnit.setControllableCreature | Prefix | sh_toolkit_harmony_ui.cs:156-158 | 刷兵增强 |
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
