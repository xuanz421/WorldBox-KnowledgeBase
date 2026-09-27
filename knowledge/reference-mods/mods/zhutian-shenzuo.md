---
title: 诸天神座
aliases:
  - zhutian-shenzuo
---

# ZhuTianShenZuo（诸天神座）

## Identity

- Name: 诸天神座 v0.2.1（mod.json:1-8，guid `zhutianshenzuo`，author 星望泡泡）
- Source ID: `ref:zhutian-shenzuo`
- Dir: `诸天神座（0.2.1-时间神殿）`
- Files: 199 total / 166 C#
- Confidence: Mostly Verified

## Purpose

万象修仙框架的早期测试版：31 个自定义 BaseStat、万象词条（CiTiao）获取/技能/职业体系、天劫三态状态机、起源领域、源脉地图生成，以及**时间神殿**——存档级世界快照时间线（自动快照/时间回溯/分支创建）。mod.json 自述"测试版，添加测试特质组"，实际测试范围仅 10 个 Ce1-Ce10 测试特质；其余系统是完整实现（52,380 行，注释详尽）。

## Systems

- Primary: Actor, Combat, World, Save/Persistence, Traits, UI
- Secondary: Assets, Map, Resources, Events, Utility, Localization, Mod Lifecycle

## Key Implementation

- `code/Main.cs` (L14-84) — 入口：Stats/TraitGroups/TraitDefinitions 注册 → PatchAll → 五个词库 Prewarm（各自 try/catch 隔离）→ YuanMaiLayerManager/WanXiangTab/CiTiaoHoverPanel 初始化，顺序纪律严格（ShiDaiLibrary 必须先于 YuanMaiTicker）
- `code/Patches/BatchActorRuntimeDispatcher.cs` (L8-78) — 唯一逐单位调度入口：`BatchActors.u8_checkUpdateTimers` Postfix 按固定顺序驱动天劫/回复/天寿/词条/领域系统，finally 排空命定死队列
- `code/Systems/TianJieSystem.cs` (L32-535) — 天劫三态状态机（空闲→待命→落雷）：1 秒节流落雷 + 闪电染色池化还原（L82-93）、每雷独立致死骰（L217-233）、渡劫完成即时道途晋升（L505-533）
- `code/Core/CiTiaoRuntime.cs` (~940 行) — 词条运行时：唯一发放闸门（L171/191）、互斥/限量/附赠链（L459）、职业升级、技能冷却窗口（L665-793）、按持有串算属性加成缓存（L810-919）
- `code/Core/ShiDaiTimeTemple.cs` (L86-800) — 时间神殿：存档目录内快照仓库 `zhutianshenzuo_time_temple/`，manifest 外置防回滚（L81-93）
- `code/Systems/OriginDomainSystem.cs` (L15-499) — 领域型起源：展开/维持/结束状态机，1s 目标脉冲 + 5s 维护费扣四池，临时词条"租约"计数续期
- `code/Core/YuanMaiGenerator.cs` (~1566 行) — 源脉网络：单主脉有向随机游走 + 树状分叉，显式队列 + 全局步数预算（1.2/tile），seed 确定性可后台线程复现（头注释 L5-30）
- `code/Core/ModSaveData.cs` (L40-449) — 用户创作数据落盘 mod 目录 `SaveData\<分类>\`：原子写入（.tmp+Replace L292-311）+ persistentDataPath 3 代轮换备份 + 空文件自动恢复

## Unique Methods

筛选口径：剔除 Harmony 管线、配置样板、getter 与 UI 接线后，承载核心机制且原版无对应物的模组自有方法。

- `TianJieSystem.ProcessActor/AdvanceTrial/ApplyDamage` (code/Systems/TianJieSystem.cs:L109-139, L201-262, L379-419) — 天劫状态机：空闲试给予→待命判条件→落雷（1s 节流、每雷独立致死骰、"由正值扣到 ≤0"边沿判死），完成即时晋升境界
- `ActorCombatPatches.Actor_GetHit_Prefix_WanXiang` (code/Patches/ActorCombatPatches.cs:L46-106) — 万象战斗公式：`(物力×(1−物御%)+法力×(1−法御%))×(1−位阶压制%)` 扣目标万象之命，归零即命定死；19 种 AttackType 全免疫（patch 方法体承载核心机制，非转发胶水）
- `MingDingSiSystem.Mark/Execute/DrainPending` (code/Systems/MingDingSiSystem.cs:L26-29, L40-68, L70-89) — 命定死：标记→下一 u8 tick 记功→`dieAndDestroy(Weapon)` 彻底销毁，绕过生命锁定与免疫
- `OriginDomainSystem.TryExpand/RefreshTargets/ApplyEntries` (code/Systems/OriginDomainSystem.cs:L134-178, L314-367, L395-432) — 起源领域：战斗触发展开、脉冲式半径目标收集、敌我词条租约（计数续期、出界/结束回收）
- `WanXiangEnergyReleaseSystem.TryRelease/FindTarget/ApplyDamage` (code/Systems/WanXiangEnergyReleaseSystem.cs:L90-119, L129-169, L252-278) — 能量放出：索敌环带最近敌人、扣法力池、sqrt 缩放飞行物纯表现、法系伤害乘位阶压制走命池
- `CiTiaoAcquireSystem.TryRollAndGrant/IsConditionMet/BuildCandidates` (code/Systems/CiTiaoAcquireSystem.cs:L272-295, L209-263, L89-130) — 词条发放：亚种∪通用∪道途绑定候选集，14 种获取条件（年龄/击杀/天资/位阶/境界…），一次摇骰永久记档
- `ShiDaiTimeTemple.CreateSnapshot/Tick/LoadNode` (code/Core/ShiDaiTimeTemple.cs:L387-440, L442-465, L601-641) — 时间神殿：全存档快照入库（调原版 `saveWorldToDirectory`）、每 N 世界年自动快照、反射调私有 `loadWorld` 时间回溯并自动建分支（`分支·{年}年` L732-748）
- `ActorTickGate.ComputeSteps` (code/Core/ActorTickGate.cs:L51-108) — 逐单位补步门禁纯函数：修"全局时间戳被首个批次吃光"的饥饿 bug，含 NaN/时钟倒退/欠账封顶三种防御

## Techniques

Harmony Prefix/Postfix（12 补丁文件 + 3 处散布 Harmony 文件，无 Transpiler）、Custom data（`zhutianshenzuo.*` actor/sub/map_stats.custom_data 三级键）、存档目录快照时间线（反射调私有 loadWorld）、mod 目录 JSON 用户内容库 + 3 代备份、MonoBehaviour DontDestroyOnLoad 帧驱动（YuanMaiTicker）、AccessTools.FieldRefAccess 私有字段

## WorldBox Usage

Actor.{getHit, die, dieAndDestroy, checkNaturalDeath, addForce, makeStunned, addStatusEffect, newKillAction} / BaseSimObject.changeHealth / BatchActors.u8_checkUpdateTimers / ActorManager.{createNewUnit, destroyObject} / BabyMaker.makeBaby / Subspecies.mutateFrom / Projectile.checkHitOnNearbyUnits / World.world.map_stats.custom_data / SaveManager.{loadData, saveWorldToDirectory, loadWorld(反射)} / SavedMap.create / MapBox.{finishMakingWorld, startTheGame} / SmoothLoader.prepare / AssetManager.base_stats_library

## NeoModLoader Usage

- BasicMod<T> + GetDeclaration().FolderPath（Verified，Main.cs:10、ModSaveData.cs:74）
- TabManager.CreateTab / PowersTab / SpriteTextureLoader / LocalizedTextManager（Verified，WanXiangTab.cs:30-33）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| BatchActors.u8_checkUpdateTimers | Postfix | code/Patches/BatchActorRuntimeDispatcher.cs:8-11 | 逐单位系统总调度 |
| Actor.getHit | Prefix (Priority.Low) + Postfix ×2 | code/Patches/ActorCombatPatches.cs:43-45、WanXiangCombatStatPatches.cs:146-147、CiTiaoCombatPatches.cs:31-32 | 万象伤害公式 / 溅射 / OnAttack 词条触发 |
| BaseSimObject.changeHealth | Prefix (Priority.First) | code/Patches/WanXiangProtectionPatches.cs:21-23 | 万象之命屏蔽一切原版掉血 |
| Actor.checkNaturalDeath | Prefix | code/Patches/WanXiangProtectionPatches.cs:43-44 | 老死免疫（寿命判定权交万象天寿） |
| Actor.addForce / makeStunned / addStatusEffect | Prefix ×3 | code/Patches/WanXiangCombatStatPatches.cs:31-117 | 抗击退/抗眩晕双闸 |
| Projectile.checkHitOnNearbyUnits | Prefix | code/Patches/WanXiangReleaseProjectilePatches.cs:44-45 | 能量飞行物摘除原版武器伤害 |
| Actor.die | Postfix ×3 | code/Patches/ActorKarmaRewardPatches.cs:18-20、CiTiaoCombatPatches.cs:60-61、CiTiaoKillDropPatches.cs:27-29 | 业力奖励 / 职业经验 / 词条掉落 |
| ActorManager.destroyObject | Postfix | code/Patches/ActorLifecycleCleanupPatches.cs:11-12 | 清四套运行时缓存 + 结束领域 |
| MapBox.finishMakingWorld / SaveManager.loadData | Postfix | code/Patches/OriginDomainPatches.cs:52-65、code/Core/YuanMaiWorldHooks.cs:61-194 | 世界切换/读档边界清理与恢复 |
| ActorManager.createNewUnit / BabyMaker.makeBaby | Postfix | code/Systems/ActorBirthInitializationSystem.cs:24-32 | 延迟出生初始化队列 |
| Subspecies.mutateFrom | Postfix | code/Systems/WanZuInheritSystem.cs:34-35 | 子亚种继承 5 类配置 |
| SavedMap.create | Prefix | code/Core/YuanMaiWorldHooks.cs:226-227 | 存盘前把源脉精确值写进 custom_data |
| UnitWindow.showStatsRows ×5 / SubspeciesWindow.showStatsRows | Postfix ×6 | code/Patches/UnitWindowPatches.cs:47-193、SubspeciesWindowPatches.cs:28-29 | 注入 5 行单位面板 + 万族编辑行 |

## Reusable Ideas

- manifest 外置的存档级快照时间线：快照仓库放存档目录、索引放外部 manifest，载旧图无法回滚索引（ShiDaiTimeTemple.cs:81-93）
- ActorTickGate 补步门禁：修批量调度器时间戳饥饿的纯函数防御写法（ActorTickGate.cs:51-108）
- 命定死三段式（Mark→记功→dieAndDestroy 绕过免疫）：需要"必死"机制时的完整管线
- 词库 Prewarm 各自 try/catch + 初始化顺序纪律（ShiDaiLibrary 先于每帧读它的 YuanMaiTicker，Main.cs:33-72）
- ModSaveData 原子写 + 3 代轮换备份 + 空文件自恢复（ModSaveData.cs:292-311,132-222）

## Pattern Candidates

- `u8-batch-dispatch-tick-gate`
- `actor-data-key-state-store`
- `karma-doomed-death-deferred-destroy`
- `save-folder-snapshot-timeline-branching`

## Evidence

- code/Main.cs:14-84 — 初始化顺序与 Prewarm 隔离
- code/Core/YuanMaiTicker.cs:28-96 — 帧驱动管线
- code/Core/ActorTickGate.cs:51-108 — 补步门禁纯函数
- code/Systems/TianJieSystem.cs:109-139,217-233 — 天劫状态机与致死骰
- code/Patches/ActorCombatPatches.cs:46-106 — 万象伤害公式
- code/Systems/MingDingSiSystem.cs:26-89 — 命定死管线
- code/Core/ShiDaiTimeTemple.cs:81-93,387-440,601-641,732-748 — 快照仓库/建快照/回溯/分支
- code/Core/ModSaveData.cs:292-311 — 原子写入
- code/Core/YuanMaiGenerator.cs:5-30 — 源脉生成设计注释
- code/Systems/CiTiaoAcquireSystem.cs:89-130,209-295 — 词条候选与条件判定
- mod.json:5 — 自述测试版；iconPath 声明 `icon.png` 与实际 `icon .png`（含空格）不符

## Notes

自述测试范围仅 10 个 Ce1-Ce10 测试特质（TraitDefinitions.cs:22-92）；其余系统为完整实现但从未实机验证（静态阅读 Mostly Verified，运行时行为未知）。Core 78 文件中约 58 个仅签名级勘察。诸天时代（ShiDaiAdvanceSystem）与时间神殿是两个独立机制：前者推进世界纪元并一次性覆写本源上限，后者做存档快照时间线。
