# 玄门道界

## Identity

- Name: 玄门道界 beta1.1.3（mod.json.close 禁用态）
- Source ID: `ref:xuanmen-daojie`
- Dir: `玄门道界_beta1.1.3`
- Files: 143 total / 55 C#
- Confidence: Mostly Verified

## Purpose

大型修仙模拟：Actor 注入 11 境界 trait 体系、18 个自定义属性（仙灵/五韵等）、真伤克制与境界压制战斗系统、全局灵炁经济（清/浊/混沌）、天劫/轮回/夺舍/飞行，幽冥领域地形改造（terraform 同心环）和多套自定义 UI（玄之涡 Tab、仙玄榜、修为/仙韵条）。

## Systems

- Primary: Actor, Traits, Combat, Save/Persistence, UI
- Secondary: World, Map, Events, Assets, Utility

## Key Implementation

- `XuanMenDaoJie.cs:15-46` — OnModLoad 严格有序初始化（Stats→Traits→SavedActorManager→Tooltip→PatchAll→Windows→Tab→ConfigCache）
- `code/Patches/BatchActorsPatches.cs:47` — BatchActors postfix 全系统每帧驱动入口（HashSet 缓存+年份缓存+0.5s 节流）
- `code/Core/ActorExtensions.cs:289-304` — Get 走 stats / Set 走 data 双轨持久化范式（1693 行）
- `code/Systems/Combat/DamageSystem.cs:208` — getHit Prefix：五韵护盾按序吸收+克制真伤+免疫集合
- `code/Systems/Cultivation/RealmSystem.cs:843` — updateStats Transpiler：normalize 前注入境界加成（labels 迁移）
- `code/Systems/Cultivation/YouMingLunHuiSystem.cs:295` — terraform 同心环领域

## Techniques

程序集级 PatchAll、BaseStatAsset/TraitAsset 运行时注册、actor.data 键值+stats 双写、MapStats.custom_data 世界级持久化、BatchActors postfix 主循环、IL Transpiler（stats/移速/物理）、persistentDataPath JSON 跨存档保存 Actor、TabManager 反射防热重载

## WorldBox Usage

Actor.{getHit,updateStats,checkNaturalDeath,goTo,updateFall,precalcMovementSpeed,newKillAction,...} / BatchActors / BaseStats / AssetManager.traits / MapStats.custom_data / MapAction.terraformMain / TileLibrary / Meteorite / UnitWindow / KingdomWindow / SelectedUnitTab / UnitBarsElement / Tooltip / WorldLawLibrary

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / Instance / GetConfig（Verified）
- TabManager.CreateTab / SpriteTextureLoader（Verified）；PowersTab（Unverified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| BatchActors.u8_checkUpdateTimers | Postfix | Patches/BatchActorsPatches.cs:47 | 全系统主循环 |
| Actor.getHit | Prefix(bool 控流) | Systems/Combat/DamageSystem.cs:208 | 护盾/真伤/压制 |
| Actor.updateStats | Transpiler | Systems/Cultivation/RealmSystem.cs:843 | normalize 前注入属性 |
| Actor.checkNaturalDeath | Prefix | Systems/Cultivation/NaturalDeathSystem.cs:75 | Sigmoid 渐进死亡 |
| Actor.goTo | Prefix | Systems/Flight/FlightSystem.cs:119 | 直线路径飞行 |
| Actor.precalcMovementSpeed | Transpiler | Systems/Flight/FlightSystem.cs:86 | 飞行 2x 移速 |
| Actor.newKillAction | Prefix | Systems/Cultivation/BodyPossessionSystem.cs:25 | 鬼魂夺舍 |
| Meteorite.explode | Prefix | Traits/TraitEffects/TeXingEffects.cs:447 | 无伤陨石特效 |

另约 10 处（Actor.u1_checkInside 原版空引用修复、updateFall、UnitWindow/KingdomWindow/SelectedUnitTab/UnitBarsElement/Tooltip UI 注入等）。

## Reusable Ideas

- Get(stats)/Set(data) 双轨：读走 stats 供引擎显示，写走 data 持久化，updateStats Transpiler 时同步
- custom_data 存世界资源 + life_dna 作世界指纹检测新世界自动重置
- BatchActors.u8 postfix 作"每帧系统总线"，配 HashSet 特质缓存/年份缓存/节流
- persistentDataPath JSON + NonPublic ContractResolver 完整保存 Actor 跨世界重放置（SavedActorManager.cs:23,38-47）

## Pattern Candidates

- `dual-track-stat-persistence`
- `custom-data-world-resource`
- `batchactors-system-bus`
- `transpiler-stat-injection`
- `persistent-actor-archive`

## Evidence

- XuanMenDaoJie.cs:33 — PatchAll
- BatchActorsPatches.cs:47,88-160 — 系统总线
- DamageSystem.cs:207-337 — 战斗改算
- RealmSystem.cs:842-871 — Transpiler
- FlightSystem.cs:85-105 — 飞行
- Core/Stats.cs:16-27 / ActiveActorCache.cs:18-28 / Features/SavedActorManager.cs:23,38-47

## Notes

约 1.6 万行；注释自述参考 XianniMod/GodTools 优化模式；禁用名（.close）。
