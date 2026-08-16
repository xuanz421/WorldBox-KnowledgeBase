# 玄鉴仙族（WuLin）

## Identity

- Name: 玄鉴仙族 v0.5.1（mod.json GUID `WULIN`，内部 id shiyue.worldbox.mod.WuLin）
- Source ID: `ref:xuanjian-xianzu`
- Dir: `玄鉴仙族_0.5.1`
- Files: 627 total / 110 C#
- Confidence: Mostly Verified

## Purpose

大型修仙文明模拟：修为境界 trait 体系（练气→金丹→元婴等）、法宝自定义物品、洞天建筑与秘境、权柄（QuanBing）争夺元系统，配血脉/排行/真君录 UI。大量代码为反编译产物（含"偏移_xxxx"注释），硬依赖 VideoCopilot mod（using VideoCopilot.code）。

## Systems

- Primary: Actor, Traits, Buildings, Combat, Items, UI, Save/Persistence
- Secondary: World, Events, Utility, Config

## Key Implementation

- `InterestingTrait.cs:12` (WuLinClass.OnModLoad) — 唯一入口（文件名极具误导性），初始化全部系统
- `code/XuanJian/Core/Patches/ShiJieSimulationHooks.cs:43` — MapBox.updateSimulation Postfix 作为全部系统 tick 总线
- `code/XuanJian/Systems/Cultivation/Definitions/XiuXingTraits.cs:130-1580` — 境界 trait 定义/注册（48+ WorldAction 技能）
- `code/XuanJian/Systems/Cultivation/QuanBing/XuanJianDaoTuQuanBingSystem.Persistence.cs:176` — 世界字符串持久化范本（Serialize/Deserialize）
- `code/XuanJian/Core/XuanJianUIManager.cs:40-58` — TabManager.CreateTab + PowerButtonCreator 自定义 tab
- `code/XuanJian/Systems/FaBao/ZiDingYiItems.cs` — 法宝 item class/group 资产注册

## Techniques

逐方法安全打补丁（反射枚举 Prefix/Postfix/Transpiler/Finalizer，单个失败仅跳过）、自定义 TSV+Base64 世界持久化（seed 换世界检测/重试/脏检查）、帧级单位快照缓存、HarmonyFinalizer 吞 NRE、反射探测持久化容器字段、trait 注册 + Delegate.Combine 挂 action_special_effect

## WorldBox Usage

AssetManager.traits / Actor.{getHit,addTrait,updateAge,die,setAlive,updateStats,makeStunned} / MapBox.updateSimulation / World.world.buildings.addBuilding / Building.{getHit,kill} / ActorEquipmentSlot.setItem / EffectsLibrary.spawnAt / SpriteTextureLoader / UnitWindow / BabyMaker.makeBaby / MapStats.custom_data

## NeoModLoader Usage

- BasicMod.OnModLoad（Verified）
- TabManager.CreateTab / PowerButtonCreator.{CreateSimpleButton,AddButtonToTab,GetTab} / ModConfigureWindow / default_config.json Callback（Verified）
- 部分 NeoModLoader.api.attributes（Unverified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| MapBox.updateSimulation | Postfix | Core/Patches/ShiJieSimulationHooks.cs:43 | 系统 tick 总线 |
| Actor.getHit | Prefix | Systems/Combat/Patches/ZhanDouDamagePatches.cs:25 | 伤害改算/护盾 |
| Actor.updateAge | Postfix | Core/Patches/XiuXingRuntimePatches.cs:27 | 寿命/修为同步 |
| Actor.checkNaturalDeath | Prefix | Core/Patches/ShouJinPatches.cs:43 | 寿元控制 |
| Actor.die/dieAndDestroy/setAlive | Pre/Post | Systems/Death/SiWangLifecyclePatches.cs:25-516 | 死亡/转世 |
| Building.kill/startMakingRuins | Prefix | Systems/DongTian/Patches/DongTianBuildingPatches.cs:47-80 | 洞天废墟 |
| ActorEquipmentSlot.setItem | Prefix | Systems/FaBao/Patches/FaBaoEquipmentPatches.cs:37 | 法宝装备 |
| MapAction.checkLightningAction | Prefix(replace) | Core/Patches/ShiJieSimulationHooks.cs:14 | 快照缓存重写 |

## Reusable Ideas

- ApplyHarmonyPatchesSafely：容错式批量补丁，目标缺失只 warn 不炸 mod（InterestingTrait.cs:77）
- 世界字符串持久化：seed 变更换重置、1s 重试、payload 去重写（Persistence.cs:63-168）
- WorldUnitsFrameCache 帧缓存 + Finalizer 吞异常，低成本保护引擎热路径
- 克隆/反射探测持久化容器字段名兜底（Persistence.cs:531）

## Pattern Candidates

- `safe-harmony-batch-apply`
- `world-string-tsv-persistence`
- `sim-tick-bus-postfix`

## Evidence

- InterestingTrait.cs:12,61 — 入口与初始化
- ShiJieSimulationHooks.cs:43 — tick 总线
- XiuXingTraits.cs:146 — trait 注册
- XuanJianDaoTuQuanBingSystem.Persistence.cs:72,176 — 序列化
- XuanJianUIManager.cs:44 — UI
- DongTianBuildings.cs:199 / ZiDingYiItems.cs:9

## Notes

反编译代码；依赖 VideoCopilot 但 mod.json 无 dependencies 字段（硬依赖未声明）；mod 处于禁用名（.close）。
