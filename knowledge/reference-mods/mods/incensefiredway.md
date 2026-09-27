---
title: 香火神道
aliases:
  - incensefiredway
---

# IncensefiredWay（香火神道）

## Identity

- Name: IncensefiredWay v0.0.4.1（命名空间 PeerlessThedayofGodswrath，mod.json.close）
- Source ID: `ref:incensefiredway`
- Dir: `IncensefiredWay_0.0.4.1`
- Files: 84 total / 13 C#
- Confidence: Mostly Verified

## Purpose

修仙/神道内容：单位 6 岁按权重随机获得"神性天赋"Divinity1-7，随香火值沿 GodsandBuddhas1→93 阶梯升级（属性/攻击/转化信徒/传送/召唤），注册自定义属性与投射物。

## Systems

- Primary: Traits（52 个 ActorTrait）, Actor
- Secondary: Combat, Assets, UI, Audio, Save/Persistence, Kingdom

## Key Implementation

- `code/patch.cs` (L34-305) — 10 个 Harmony 补丁：updateAge 天赋分发、getHit 减伤、神明免疫套件（其中 updateStamina 为 Postfix 锁体力）
- `code/trait.cs` (L25-99,166) — 52 特质资产+委托挂接样板
- `code/traitAction.cs` (2618 行，采样精读) — 升级/攻击/转化/召唤 WorldAction/AttackAction 实现
- `code/utils/ActorExtensions.cs` (L96-113，文件共 114 行) — actor.data 自定义浮点属性 Get/Set/Change 三件套

## Unique Methods

筛选口径：剔除补丁接线与注册样板后，承载核心机制且原版无对应物的模组自有方法。

- `patch.updateWorldTime_KnightPostfix` (code/patch.cs:34-52) — 基础四族/civ_ 单位 6 岁时 50% 概率获得随机神性天赋（配套 HandleBasicRaceTraits:59-70）
- `patch.SelectRandomDivinity` (code/patch.cs:72-99) — 4000:2000:1000:500:250:50:1 权重表随机选 Divinity1-7
- `patch.ApplyTraitEffects` (code/patch.cs:101-155) — 按境界区间（Divinity1-7 / GodsandBuddhas7-93）随机增长香火值
- `patch.actorGetHit_prefix` (code/patch.cs:186-229) — GodsandBuddhas4-93 特质按优先级乘数减伤（当前配置全部乘 0 = 免伤）
- `patch.HasProtectedQWE 六方法套件` (code/patch.cs:231-289,299-303) — 香火阶梯单位"霸体"：禁残疾/锁满体力/禁击飞/禁睡眠/禁眩晕/禁部分异常
- `traitAction.attack_Conversion` (code/traitAction.cs:1818-1990) — 按攻击者特质查半径/HP 阈值/授予包，范围 10% 攻击伤害后将濒死敌人转化为信徒（参数解析 ResolveParamsForAttacker9:1787）
- `traitAction.upTrait` (code/traitAction.cs:146-176) — 升级链换特质并重写单位名的境界后缀与随机尊号（UpdateXianSuffix/ApplyXianTitle:30-96，40+ 尊号/阶）
- `traitAction.teleportRandom` (code/traitAction.cs:1446-1496) — OfType 反射取 CityManager，优先传回王国首都、否则随机存活城市
- `ActorExtensions.ChangeIncenseandfire 三件套` (code/utils/ActorExtensions.cs:96-113) — `actor.data.get/set("wushu.*")` 随存档持久化的自定义浮点属性（Believers :80-94，另四组同构）

## Techniques

特质注册（new ActorTrait + action_special_effect/action_attack_target 委托）、BaseStatAsset 注册、ProjectileAsset + World.world.projectiles.spawn、upTrait 升级链、信徒转化、神明免疫 Prefix 批量否决、FMOD Core 直放 wav、UnitWindow 克隆 i_kills 图标注入

## WorldBox Usage

ActorTrait/BaseStats / BaseStatAsset / ProjectileAsset / AssetManager.* / Actor.{updateAge,getHit,addTrait,data} / World.world.{units,projectiles} / CityManager / UnitWindow/UnitStatsElement / WorldTip / LocalizedTextManager / Randy

## NeoModLoader Usage

- BasicMod<T>（GetDeclaration/GetConfig）、ModConfig SWITCH Callback、[Hotfixable]、LogService（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.updateAge | Postfix | patch.cs:34 | 天赋分发+香火增长 |
| Actor.getHit | Prefix | patch.cs:186 | 特质减伤乘数 |
| Actor.{addInjuryTrait,calculateForce,applyRandomForce,makeSleep,makeStunned,addStatusEffect} | Prefix 批量 | patch.cs:231-289 | 神明免疫（霸体） |
| Actor.updateStamina | Postfix | patch.cs:231-289 区段 | 锁满体力 |
| ActionLibrary.showWhisperTip | Prefix | patch.cs:305 | 提示停留 15s |
| UnitWindow.OnEnable | Pre+Post | Upgradethesystem.cs:28,48 | 初始化+文本注入 |
| UnitStatsElement.showContent | Prefix | Upgradethesystem.cs:38 | 自定义属性数值显示 |

## Reusable Ideas

- `actor.data.get/set("modid.键")` 扩展方法三件套 = 零成本随存档持久化的自定义属性（ActorExtensions.cs:213-230）
- 克隆 i_kills StatsIcon + setIconValue 给单位窗口加自定义属性图标的最短路径（UnitWindowStatsIcon.cs:285-352）
- FMOD Core 直放 mod 目录 wav（含 3D 距离衰减），绕过音频 bank 打包（PlayWaveDirectly.cs:111-141）
- Prefix 批量否决 Actor 负面状态方法 = "霸体"类免疫实现（patch.cs:231-289）

## Pattern Candidates

- `actor-data-custom-stat`
- `trait-upgrade-chain`
- `immunity-prefix-veto-suite`

## Evidence

- patch.cs:34-52,186-229,231-289 / trait.cs:25-26,70-99,166
- traitAction.cs:146-176,1567-1645 / stats.cs:7-25 / Upgradethesystem.cs:38-45
- UnitWindowStatsIcon.cs:32-113 — 克隆 i_kills 注入

## Notes

targetGameBuild 115（旧 beta）；代码质量低（复制阶梯、死代码）；命名空间混杂。
