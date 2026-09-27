---
title: 鬼谷修仙
aliases:
  - guigu-cultivation
---

# Guigu Cultivation（鬼谷修仙）

## Identity

- Name: Guigu Cultivation（mod.json.close，guid `XIUXIAN_STANDALONE`，namespace XiuxianStandalone）
- Source ID: `ref:guigu-cultivation`
- Dir: `Guigu_Cultivation_1.0.6.2`
- Files: 1082 total / 198 C#
- Confidence: Mostly Verified

## Purpose

在 WorldBox 上实现完整修仙/武道体系：单位按游戏月结算修炼经验、突破境界（炼气→筑基→金丹→元婴…）、习得功法/绝技（元素投射物攻击）、气运/轮回转世，以及宗门王国社会系统（宗主、政变、藏经阁、招收弟子）。附带大量读档稳定性与性能补丁。

## Systems

- Primary: Actor, Traits, Combat, Kingdom, Save/Persistence
- Secondary: City, Events, UI, World, Mod Lifecycle, Utility

## Key Implementation

- `Code/ModEntry.cs` (ModEntry, L15-109) — 入口：顺序注册 trait/creature/projectile + ~60 个逐类 ApplyPatch + world_loaded 挂钩；L231-239 单补丁失败隔离模式
- `Code/Core/CultivationSystem.cs` (L17-2442) — 月结修炼引擎：分帧切片（L44-50 帧预算）、读档"牺牲窗"（L105-118）、追赶切片；状态全存 actor.data
- `Code/Core/CultivationData.cs` (L15-4753) — 修炼数据键值层（`xiuxian.*` data key）+ 功法/词条/气运规则库
- `Code/Core/ProjectileDefinitionFramework.cs` (L19-69) — ProjectileAsset 统一注册框架，防重复注册
- `Code/Sect/SectBootstrap.cs` (L11-217) — 宗门系统分阶段延迟加载链（Phase0-4）
- `Code/Patches/HarmonyPatches.cs` (L26-214) — Actor.updateStats Pre/Post+Transpiler、Kingdom.setKing Prefix、UnitWindow/SelectedUnitTab UI 注入
- `Code/Core/ReincarnationPersistence.cs` (L80-139) — 轮回数据写存档槽目录
- `Code/Core/ModCreatureRegistry.cs` (L17-41) — 反射调私有 loadTexturesAndSprites 重载自定义生物贴图

## Unique Methods

筛选口径：剔除补丁管线与初始化样板后，承载核心机制且原版无对应物的模组自有方法。

- `CultivationSystem.TickMonthlyCultivationBatchOnWorldTime` (Code/Core/CultivationSystem.cs:378-492) — 月结总入口：世界切换/加载态/暂停早退后，按稳态排水与跨月追赶双路分帧切片推进全局游戏月
- `CultivationSystem.TickMonthlyExpAndLevelUpForMonth` (Code/Core/CultivationSystem.cs:885-1214) — 单位单月经验公式结算（资质×倍率×灵气）+ 境界突破门槛 + 属性/词条/宗门状态合并
- `CultivationSystem.ArmPostLoadMonthlyExpSacrificeWindow` (Code/Core/CultivationSystem.cs:105-111) — 读档后武装 12s（clamp 5-45s）"牺牲窗"：窗内只对齐 last_exp_month 不发经验，附 10s 低切片续窗
- `SectBootstrap.RunDeferredWorldLoadHeavy` (Code/Sect/SectBootstrap.cs:124-150) — 等 SmoothLoader/暂停结束（带重试上限）后把宗门重活拆 Phase0-4 逐帧入队
- `ReincarnationPersistence.TryGetWriteSaveRoot` (Code/Core/ReincarnationPersistence.cs:129-143) — 轮回写侧目录解析：优先 SaveWriteContext 活动存档文件夹，失败回退读侧槽位目录
- `LawUniquenessDuelSystem.TryBeginDuelIfNeeded` (Code/Core/LawUniquenessDuelSystem.cs:89-154) — "大道唯一"机制：天道词条超容时新挑战者与在世旧持道者登记强制决斗
- `RealmSuppression.ApplyRealmSuppression` (Code/Core/RealmSuppression.cs:95-109) — 跨大境界攻击伤害减免，带绝对最小伤害与比例双保底
- `InnateLuckBirth.RollAndApply` (Code/Core/InnateLuckBirth.cs:179-244) — 新生儿按配置权重掷先天气运（红/黄/紫/蓝/绿），含仙道凡人权重再分配

## Techniques

Harmony Prefix/Postfix/Transpiler（40+ patch 类，逐类 CreateAndPatchAll 隔离）、Reflection（ActorAsset._cached_sprite 等私有成员）、Asset registration（trait_groups/traits/projectiles/actor_library/powers.clone）、Custom data（actor.data 字符串键）、文件持久化（存档槽目录 txt/json）、Event subscription（MapBox.on_world_loaded）、UI injection（TabManager.CreateTab + UnitWindow postfix）、Localization

## WorldBox Usage

Actor.data / Actor.updateStats / AssetManager.{trait_groups, projectiles, actor_library, powers, kingdoms_traits} / Kingdom.setKing / MapBox.on_world_loaded / BatchActors.u8_checkUpdateTimers / SaveManager.{currentSavePath, getCurrentSlot, folderPath} / SmoothLoader.isLoading / TabManager.CreateTab / PowerButtonCreator.CreateSimpleButton / UnitWindow.OnEnable

## NeoModLoader Usage

- BasicMod<T>.OnModLoad（Verified）
- BasicMod<T>.GetConfig()（Unverified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.updateStats | Pre+Post+Transpiler | Patches/HarmonyPatches.cs:26-93 | 境界属性叠加进原版统计 |
| Kingdom.setKing | Prefix+2×Postfix | Patches/HarmonyPatches.cs:95-158 | 修 vanilla 换王不卸旧王 + 宗门角色同步 |
| BatchActors.u8_checkUpdateTimers | Postfix | Patches/ModOptimizationPatch.cs:183-190 | 驱动全局分帧任务队列 |
| UnitWindow.OnEnable | Postfix | Patches/HarmonyPatches.cs:159-175 | 单位面板注入修仙信息页 |
| SelectedUnitTab.showStatsGeneral | Postfix | Patches/HarmonyPatches.cs:176-184 | 宗门 UI 徽章/称号 |
| MapBox.finishingUpLoading 等 | Prefix/Postfix | Sect/SectBootstrap.cs | 读档半初始化窗口内同步宗门 hydrate |
| Kingdom.makeNewCiv 系列 | Prefix/Postfix | Patches/KingdomFoundingMergePatches.cs | 宗门建国与领土冷却 |

## Reusable Ideas

- 逐补丁类 try/catch Harmony.CreateAndPatchAll 隔离——单补丁炸不炸全 mod（ModEntry.cs:231-239）
- 全部自定义状态走 actor.data.get/set 集中键管理，随原版存档自动持久化（CultivationData.cs:112-116）
- "读档牺牲窗"+分帧切片月结解决读档后卡顿尖峰（CultivationSystem.cs:44-50,105）
- 重量级世界加载任务拆 Phase0-4 延迟链，等 SmoothLoader/暂停结束再逐帧消化（SectBootstrap.cs:124-210）
- 文件持久化直接定位存档槽目录（ReincarnationPersistence.cs:82-106）

## Pattern Candidates

- `per-patch-isolated-patching`
- `actor-data-key-state-store`
- `frame-sliced-world-simulation`
- `save-slot-file-persistence`

## Evidence

- Code/ModEntry.cs:13 — `class ModEntry : BasicMod<ModEntry>`
- Code/ModEntry.cs:236 — `Harmony.CreateAndPatchAll(patchType, Constants.HarmonyInstanceId)`
- Code/ModEntry.cs:106 — `MapBox.on_world_loaded = (Action)Delegate.Combine(...)`
- Code/Patches/HarmonyPatches.cs:26 — `[HarmonyPatch(typeof(Actor), nameof(Actor.updateStats))]`
- Code/Core/CultivationData.cs:417-424 — actor.data get/set 示例
- Code/Sect/SectScripturePavilionFilePersistence.cs:87 — 存档目录 JSON 写入
- Code/Core/ModCreatureRegistry.cs:28-41 — 反射私有成员

## Notes

mod.json 文件名为 mod.json.close（禁用态）。198 文件中约 60 个是单绝技模板实现，未逐个深读。中文注释含详细读档竞态分析，极有学习价值。
