# TheFantasyWorld（西幻世界）

## Identity

- Name: TheFantasyWorld v0.8.6（GUID Thefantasyworld，mod.json.close）
- Source ID: `ref:thefantasyworld`
- Dir: `TheFantasyWorld_0.8.6`
- Files: 1507 total（大量资源）/ 39 C#
- Confidence: Mostly Verified

## Purpose

大型东方玄幻/西方奇幻融合 RPG 层：12 职业系统（召唤师/圣骑士/刺客等）、修仙式升级突破（grade1-91）、天赋特质、战斗计算（闪避/命中/护盾/魔抗）、神明复活，含自定义 UI Tab 与单位窗口扩展。

## Systems

- Primary: Actor, Traits, Combat, Mod Lifecycle
- Secondary: UI, Save/Persistence, World(GodPower), Assets, Events

## Key Implementation

- `Thefantasyworld.cs` (L14-41) — BasicMod 入口：顺序 Init + 12 个 PatchAll
- `code/stats.cs` (L9-15) — 手工 new BaseStatAsset 15+ 自定义属性（经验/意志力/护盾/闪避）
- `code/trait.cs` (L15-25) — trait 工厂 `RankTalentst_AddActorTrait` 绑定 action_special_effect 委托
- `code/Resistance.cs` (L121-460) — 死亡保护系统：die/makeStunned/addStatusEffect 等多 Prefix
- `code/traitAction.cs` (L24-66) — 突破日志用 map_stats.custom_data.custom_data_bool 持久化
- `code/THEFANTASYWORLDUIManager.cs` (L29-34,75-82) — TabManager.CreateTab + PowerButtonCreator

## Techniques

Manual Harmony PatchAll per class、Asset registration（BaseStatAsset/ActorTrait/ActorTraitGroupAsset/GodPower）、NML TabManager UI injection、custom_data 持久化、trait action_special_effect 委托、string 前缀键 SaveCustomData

## WorldBox Usage

AssetManager.{base_stats_library,traits,trait_groups,powers} / Actor.{die,getHit,b6_updateAI,updateAge,updateStats,calculateForce} / BaseSimObject.{changeHealth,canAttackTarget,addStatusEffect} / BabyMaker.makeBaby / Actor.checkTraitMutationOnBirth / World.world.map_stats.custom_data / ArmyManager.update

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / GetDeclaration / GetConfig（Verified）
- NeoModLoader.General.UI.Tab.TabManager / PowerButtonCreator（Verified）
- ModConfig/ModDeclare 细节（Unverified：CreateSimpleButton 签名）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.die | Prefix | Resistance.cs:122 | 天賦免死拦截 + ForceKill 队列绕过 |
| BaseSimObject.changeHealth | Prefix | Battlecalculation.cs:320 | 伤害公式重算（护盾/魔抗） |
| Actor.checkTraitMutationOnBirth | Prefix | FantasyTalent.cs:27 | 出生天賦注入 |
| BabyMaker.makeBaby | Postfix | FantasyTalent.cs:368 | 婴儿天賦遗传 |
| UnitWindow.OnEnable | Postfix | Upgradethesystem.cs:28 | 单位窗口升级图标 |
| LoadWorldButton.loadWorld | Prefix | TheReturnofGod.cs:91 | 神明跨存档回归 |

## Reusable Ideas

- 基于队列的"绕过保护强杀"：ForceKillActors 队列在 die Prefix 中检查，eraser power 直接入队绕过一切复活逻辑（THEFANTASYWORLD_Powers.cs L75-80）
- string 前缀约定的 map_stats.custom_data 持久化，免自定义 SaveObject（traitAction.cs L36-49）
- trait 工厂 + action_special_effect 委托实现每帧 tick 升级条件检查（trait.cs L23）

## Pattern Candidates

- `custom-basestat-registration`
- `trait-factory-with-action-delegate`
- `death-protection-prefix-chain`

## Evidence

- Thefantasyworld.cs:7,25-37 — 入口
- stats.cs:9-15 / trait.cs:15-25 — 资产注册
- Resistance.cs:121-123 — 保护链
- traitAction.cs:36-49 / FantasyTalent.cs:355-368 — 持久化与遗传
- THEFANTASYWORLDUIManager.cs:29-34 — UI

## Notes

targetGameBuild=115（旧 beta）；mod.json 处于禁用名。
