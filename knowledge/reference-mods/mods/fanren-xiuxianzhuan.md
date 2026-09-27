---
title: 凡人修仙传
aliases:
  - fanren-xiuxianzhuan
---

# FanRen Standalone（凡人修仙传）

## Identity

- Name: 凡人修仙传 v0.53.1（mod.json:1-8，guid `FANREN_STANDALONE`，namespace FanRenStandalone）
- Source ID: `ref:fanren-xiuxianzhuan`
- Dir: `凡人修仙传`
- Files: 244 total / 74 C#
- Confidence: Verified

## Purpose

WorldBox 独立修仙体系（standalone overhaul）：11 境界 37 层修炼状态机、灵根五行相克、功法/法术/法宝/丹药/职业、宗门/灵脉/灵石六品经济、天劫与伪金丹。全部状态走 actor.data，自有 MonoBehaviour 心跳驱动帧切片模拟，不依赖原版修炼概念。

## Systems

- Primary: Actor, Traits, Combat, UI, World
- Secondary: Mod Lifecycle, Save/Persistence, Assets, Events, AI, City, Items, Resources, Localization, Utility

## Key Implementation

- `Code/ModEntry.cs` (L25-94) — 入口：`Safe(stepName, Action)` 分段执行器隔离每步初始化（特质注册 → CultivationUpdater GameObject → Harmony.PatchAll + 手动精确 Patch → UI tab/决策注册）
- `Code/Core/CultivationUpdater.cs` (L19-286) — DontDestroyOnLoad 心跳：2s 单位扫描、逐帧节流系统 tick、10 秒=1 游戏年的 YearTick 级联（L64-79）；`CompatOldSaves` 幂等回填 12 类缺失数据（L100-213）
- `Code/Core/CultivationSystem.cs` (L12-206) — `TickUnit` 修炼状态机：年龄→游戏年换算、13 重乘数经验结算（L84-98）、功法扣减门控突破（L108-131）、15 步副作用级联（天劫→金丹→境界能力→职业→特质同步）
- `Code/Core/RealmDef.cs` (L11-188) — 纯数据表：11 境界/37 层、经验曲线、属性加成、寿命上限、战力估算
- `Code/Core/LingGenSystem.cs` (L227-269) — 灵根修炼乘数：纯度均值 × 元素数基数 × 五行相克矩阵（表 L35-40），状态存 `fanren.elements/purities` CSV 键
- `Code/Core/ZongMenSystem.cs` (L235-1135) — 宗门：内存字典 + 宗门数据挂宗主 actor.data 持久化（L539-552）+ `EnsureRebuilt` 两遍扫描重建（L1029-1135）
- `Code/Core/LingMaiSystem.cs` (L244-372) — 灵脉福地生灭/占领状态机：每档上限 `RollTierWithCap`（L157-171）、潮汐衰减/复苏、不对称占领规则
- `Code/Core/SpiritStoneSystem.cs` (L67-123) — 灵石六品经济：面额比 1:100:…:10¹⁰，`AddStones` 低→高填充 / `TrySpend` 高→低找零
- `Code/Core/TianJieSystem.cs` (L39-140) — 天劫结算：数据表驱动（5 场劫 L18-35）、减伤聚合、三结局分支
- `Code/RealmStatPatch.cs` (L18-125) — `Actor.updateStats` Transpiler 在 `BaseStats.normalize` 前注入境界/灵根/功法/法宝/金丹乘数

## Unique Methods

筛选口径：剔除 Harmony 管线、配置样板、getter 与 UI 接线后，承载核心机制且原版无对应物的模组自有方法。

- `CultivationSystem.TickUnit(Actor)` (Code/Core/CultivationSystem.cs:L12-206) — 修炼心跳状态机：经验结算与突破门控完全自创，原版无修炼概念
- `CultivationUpdater.TickAllUnits()` (Code/Core/CultivationUpdater.cs:L215-286) — 帧切片全图模拟：快照拷贝 + 旋转游标 `_tickOffset` + 4000 单位/tick 上限，任意世界规模恒定心跳成本
- `LingGenSystem.CalculateCultivationMultiplier(string[], int[])` (Code/Core/LingGenSystem.cs:L227-269) — 灵根纯度 × 元素数 × 五行相克矩阵的数值核心（0.05 下限）
- `ZongMenSystem.EnsureRebuilt()` (Code/Core/ZongMenSystem.cs:L1029-1135) — 从 per-actor 持久化键两遍扫描重建整个组织实体（宗门），含僵尸宗主标记 GC
- `LingMaiSystem.YearTick()` / `ResolveOccupation()` (Code/Core/LingMaiSystem.cs:L244-299, L331-372) — 灵脉生灭与占领：潮汐驱动的衰减/复苏 + 宗门可夺个人、个人不可夺宗门的不对称规则
- `GongFaSystem.TryDeduceNextGongFa(Actor,int)` (Code/Core/GongFaSystem.cs:L480-521) — 功法推演瓶颈门：经验扣减 + 纯度推导概率，成功以境界索引位掩码记录（L472-477）并阻塞突破循环
- `SpiritStoneSystem.TrySpend(Actor,int,out int)` (Code/Core/SpiritStoneSystem.cs:L96-123) — 六品灵石找零算法（高位币种支付、低位找零），原版无此经济原语
- `TianJieSystem.TryTrigger(Actor,int)` (Code/Core/TianJieSystem.cs:L39-140) — 天劫三结局结算：伪金丹救回（永久封顶 L104-105）/ 死亡标记 / 降 3 层

## Techniques

Harmony Prefix/Postfix/Transpiler（updateStats Transpiler pre-normalize 注入）、Custom data（`fanren.*` data keys，Constants.cs:18-28）、MonoBehaviour 常驻 updater（DontDestroyOnLoad）、Asset registration（traits/trait_groups/tasks_actor/decisions_library 代码注册）、UI injection（TabManager.CreateTab + UnitWindow postfix）、存档目录 JSON sidecar、帧切片模拟、幂等旧档回填与逐系统迁移

## WorldBox Usage

Actor.data / Actor.updateStats / Actor.getHit / Actor.die / Actor.goTo / Actor.updateFall / AssetManager.{traits, trait_groups, tasks_actor, decisions_library} / World.world.{units, cities} / NameplateText.setText / ScrollWindow.showWindow / ActionLibrary.openUnitWindow / UnitWindow.OnEnable / SaveManager.{currentSavePath, folderPath} / BaseStats.normalize / ActorTool.applyForceToUnit（反射）/ BehaviourTaskActor / DecisionAsset / NeuroLayer / WorldLogMessage

## NeoModLoader Usage

- BasicMod<T>.OnModLoad（Verified）
- TabManager.CreateTab + PowerButtonCreator.CreateSimpleButton（Verified，FanRenTab.cs:43-149）
- ModConfigureWindow.ShowWindow（Verified，FanRenTab.cs:144-145）
- default_config.json 声明式配置（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.updateStats | Transpiler + Postfix | Code/RealmStatPatch.cs:18-49,154-165 | 境界/灵根/功法/法宝乘数 pre-normalize 注入 + 盾色/金丹爆发/领域 |
| Actor.getHit | Prefix ×2 + Postfix | Code/RealmStatPatch.cs:187-205、Code/RealmSuppressionPatch.cs:30-86 | 灵盾免致命远程 / 境界压制 −30%/层 / 真火破甲等 |
| Actor.updateFall / Actor.goTo | Prefix skip | Code/RealmStatPatch.cs:209-234 | 飞行高度与直线飞行路径 |
| ActorTool.applyForceToUnit | Prefix | Code/RealmSuppressionPatch.cs:90-111（挂载 ModEntry.cs:69-75） | 境界差 ≥2 免疫击退 |
| Actor.die | Prefix ×2 | Code/Core/FenShenSystem.cs:110-113、Code/Core/NascentSoulSystem.cs:14-16 | 化神分身替死 / 元婴出窍取消死亡 |
| NameplateText.setText | Prefix | Code/NameplateFactionPatch.cs:16-43 | 城市名牌追加 `·【宗门名】` |
| ScrollWindow.showWindow / ActionLibrary.openUnitWindow / UnitWindow.OnEnable | Prefix（手动精确 Patch 避免重载歧义） | Code/ModEntry.cs:52-66 → Code/UI/WindowManagerPatches.cs:9-11 | 模组窗口互斥 |
| UnitWindow.showStatsRows / OnEnable | Postfix | Code/UnitWindowPatch.cs:17-19,66-68、Code/CultivatorInfoButton.cs:18-20 | 注入修仙属性行 / 修仙信息页签 |

## Reusable Ideas

- 全状态 actor.data 键值集中管理（`fanren.*`），组织实体挂"宗主"actor 持久化，读档后从单位扫描重建内存缓存（ZongMenSystem.cs:1029-1135）
- 帧切片心跳：快照 + 旋转游标 + 每 tick 上限，2 秒心跳覆盖任意世界规模（CultivationUpdater.cs:226-234）
- `Safe()` 分段初始化：单步崩溃不拖垮整个加载（ModEntry.cs:14-23）
- Transpiler 在 `BaseStats.normalize` 之前注入乘数，避免被 normalize 抹平（RealmStatPatch.cs:18-49）
- 存档目录 JSON sidecar 承载组织数据（FangShiSystem.cs:353-411）
- 幂等 CompatOldSaves 全量回填 + 每系统独立迁移（SpiritStoneSystem.TryMigrate :162-174）

## Pattern Candidates

- `actor-data-key-state-store`
- `frame-sliced-world-simulation`
- `runtime-cache-rebuild-from-unit-scan`
- `save-folder-json-sidecar`
- `transpiler-pre-normalize-stat-injection`
- `legacy-save-idempotent-backfill`

## Evidence

- Code/ModEntry.cs:29-45 — Safe() 特质注册 + CultivationUpdater GameObject
- Code/ModEntry.cs:48-49 — `new Harmony(Constants.HarmonyInstanceId)` + PatchAll
- Code/Core/CultivationUpdater.cs:15 — `MaxUnitsPerTick=4000`
- Code/Core/CultivationUpdater.cs:64-79 — 10s YearTick 级联
- Code/Core/CultivationSystem.cs:84-131 — 经验乘数与突破门控
- Code/Core/LingGenSystem.cs:35-40 — 五行相克矩阵
- Code/Core/ZongMenSystem.cs:24-44 — 宗门挂宗主 actor.data 的键清单
- Code/Core/LingMaiSystem.cs:157-171 — RollTierWithCap 每档上限
- Code/Core/SpiritStoneSystem.cs:27 — 面额比率表
- Code/Core/TianJieSystem.cs:18-35 — 天劫数据表
- Code/RealmStatPatch.cs:18-49 — updateStats Transpiler
- Code/Constants.cs:17-28 — `fanren.*` data key 声明

## Notes

法宝/丹药/灵石多为 data key 而非 AssetManager item，装备实体仅法宝编辑器显示物（FaBaoEquipmentAssets.Init）。UI 18 文件为抽样精读。与 guigu-cultivation（`ref:guigu-cultivation`）同属独立修仙体系但实现路线不同：本模组自建心跳循环，guigu 挂原版月结定时器——对照阅读价值高。
