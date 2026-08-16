# CreepMobBoost

## Identity

- Name: CreepMobBoost v1.0.2
- Source ID: `ref:creepmobboost`
- Dir: `CreepMobBoost_1.0.2`
- Files: 9 total / 2 C#
- Confidence: Verified

## Purpose

让四大天灾衍生生物（肿瘤怪/小南瓜/生物质/Cyber 同化体）通过 AI 决策主动寻找地点筑巢（生成 creep 建筑后自毁），配置可调生长步数/工人数/间隔。

## Systems

- Primary: Actor, Buildings
- Secondary: AI, Assets, UI(config)

## Key Implementation

- `CreepMobBoost.cs` (L21-78) — OnModLoad：task+decision 注册及在役 Actor 决策数组扩容
- `Beh_buld_creep_mob_hive.cs` (L13-42) — 自定义 BehaviourActionActor：生物群落约束+距离查重+addBuilding+die

## Techniques

运行时注册 BehaviourTaskActor + DecisionAsset 挂到现有 actor_library 资产、继承 BehaviourActionActor 自定义行为、Toolbox.checkArraySize 扩容决策数组（热加载兼容）、BuildingAsset 数值修改（先缓存原值基线）、NML ModConfig 分组读取

## WorldBox Usage

AssetManager.{tasks_actor,decisions_library,actor_library,buildings} / DecisionAsset(NeuroLayer.Layer_3_High) / World.world.{units,buildings.addBuilding} / Finder.getBuildingsFromChunk / Toolbox.checkArraySize / WorldTile.top_type.biome_id

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / Instance.GetConfig()[group][key]{BoolVal,FloatVal,IntVal}（Verified）

## Patch Targets

无 —— 纯运行时资产注入，零 Harmony

## Reusable Ideas

- 给现有种族注入新 decision+task 的标准三步注册（task→decision→挂资产）
- 决策库扩容时遍历在役 Actor 修数组，避免旧单位越界（CreepMobBoost.cs:39-42）
- 配置 setter 触发早于 OnModLoad 时的基线缓存技巧（cs:62）

## Pattern Candidates

- `runtime-decision-injection`
- `building-asset-rebalance-config`

## Evidence

- CreepMobBoost.cs:21-37,39-42,44-57,60-78 / Beh_buld_creep_mob_hive.cs:11-12,19-38
