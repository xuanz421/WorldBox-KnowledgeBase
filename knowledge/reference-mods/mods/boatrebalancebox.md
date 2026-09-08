---
title: BoatRebalanceBox
aliases:
  - boatrebalancebox
---

# BoatRebalanceBox

## Identity

- Name: BoatRebalanceBox v1.2.4
- Source ID: `ref:boatrebalancebox`
- Dir: `BoatRebalanceBox_1.2.4`
- Files: 14 total / 8 C#（根 1 + Content 7）
- Confidence: Verified

## Purpose

行星船重平衡（自述 "planet ship are too OP"）：削弱/重构船武器与船体数值，给运输船扩展索敌与连发攻击，消除船只受击抖动/击退与投降减伤；海豹运输船换霰弹枪。

## Architecture / Entry

- `BoatRebalanceBoxMain : BasicMod<BoatRebalanceBoxMain>`，OnModLoad（BoatRebalanceBox.cs:9-21）
- 3× `Harmony.CreateAndPatchAll`（Boat_Sight / Patch_Boat_Rapid_Fire / Patch_Boat_No_Shake）→ 逐类隔离，一类失败不连坐
- 随后 `BoatRebalanceBoxContent.Init()`：纯资产数据修改（Boat_Weapons / Boat_States / Boat_Weapon_Projectile）
- **无配置系统**（无 GetConfig / default_config.json），数值全硬编码
- 时序：NML 在游戏资产初始化后加载 mod（neomodloader WorldBoxMod.cs:87-121）→ OnModLoad 直改静态全局资产即生效；不依赖 game_loaded / SmoothLoader / post-init；世界创建晚于 OnModLoad

## Boat Modification Strategy（核心发现）

**双层混合：纯数据层（零 Harmony）+ 行为层（Harmony）**

### 数据层（Content 三个静态类）

1. **改共享 vanilla 武器资产**：8 个 boat_* EquipmentAsset `base_stats`（damage/range/projectiles/attack_speed/targets/accuracy/area_of_effect）全量覆写（Boat_Weapons.cs:33-115）——vanilla 船武器本就是 ItemLibrary 里的隐藏攻击模板（ItemLibrary.initBoats，见 economy/items.md:238）
2. **clone 派生新武器**：`tradeboat_arrow`（← boat_arrow，给商船）与 `boat_shotgun`（← boat_cannonball，projectile="shotgun_bullet"，6 连发，给海豹船；`AssetManager.actor_library.get("boat_transport_seal").default_attack = "boat_shotgun"`，Boat_Weapons.cs:125-145）——`AssetLibrary.clone(pNew, pFrom)` = 深拷贝 + `add()` 注册（last-wins，AssetLibrary.cs:83-90）
3. **改船体 ActorAsset**：`boat_trading_*`（default_attack + health 400 + crit ×2 + cost ConstructionCost(12,12,0,100)）、`boat_transport_*`（health 1000 / armor 20 / cost(50,50,0,400)），按 id 前缀遍历 `actor_library.list`（Boat_States.cs:15-43）——前缀族与 vanilla 一致（ActorAssetLibrary.cs:3142-3301）
4. **clone-rewire 弹丸**：每武器 get-or-clone `"<weapon>_newProjectile"`（幂等，Boat_Weapon_Projectile.cs:195-199）+ 反射写 ProjectileAsset 公共字段（speed/scale_start/scale_target/hit_freeze/sound_launch/sound_impact，`Convert.ChangeType` 适配类型如 int terraform_range）+ 全局默认 `can_be_blocked=false / can_be_collided=false / terraform_range=2` + **重接 `weapon.projectile = newProjId`**（:180-227）——改的是 vanilla 武器的 projectile 引用，原弹丸资产保留未动

### 行为层（见 Patch Targets）

## 船只战斗能力数据链（vanilla 验证）

```text
ActorAsset.default_attack（ActorAsset.cs:107）
  → AssetManager.items.get()（无武器路径：Actor.updateStats :1826 / getWeaponAsset :2771）
  → EquipmentAsset.base_stats["damage/range/projectiles/..."] + .projectile（ItemAsset.cs:59）
  → AttackData.projectile_id（Actor.cs:6107-6113）
  → CombatActionLibrary.attackRangeAction 发射（stats["projectiles"] 在 :243 读取）
  → ProjectileAsset（AssetManager.projectiles:163）飞行 → checkAttackFor / applyAttack 结算
```

- vanilla `attackRangeAction` 是**单帧齐射**全部弹丸（CombatActionLibrary.cs:261-277 loop）→ 时间分布连发必须 Harmony
- vanilla 索敌半径 = `SimGlobals.unit_chunk_sight_range = 1` chunk（SimGlobalAsset.cs:28，EnemiesFinder.cs:21-30）→ 船武器 range 11-20 **超视野**，想打到远程目标必须自建索敌（Boat_Sight 存在的根因）

## Systems

- Primary: Boats, Combat
- Secondary: Actor, Assets

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| BaseSimObject.findEnemyObjectTarget | Prefix（找到即否决） | Boat_Sight.cs:25-58 | 运输船自定义索敌：per-kingdom 64 槽环形缓存 + 当前 chunk ±2 偏移搜索（超 vanilla 1 chunk 视野），跳过建筑内/船上单位，**仅回 isInAttackRange 内目标**（不追击远程敌人→防御型行为）；未找到则放行原逻辑 |
| CombatActionLibrary.attackRangeAction | Prefix（替换） | Boat_RapidFire.cs:17-84 | projectiles>1 的运输船：单帧齐射改协程连发（0.10/0.15s 间隔按弹数×攻速选；≥4 发且偶数时每 tick 双发）；目标死亡转 hit_position 继续射 |
| MapBox.applyAttack | Prefix（替换） | Boat_NoShake.cs:12-34 | 船攻击或 boat_transport 被击：跳过 BEFORE_HIT deflect/block 战斗动作池、击退力（applyForceToUnit）、attackTargetActions、进食逻辑；对建筑伤害 ×1.2；直接 getHit(pSkipIfShake:true) |
| Actor.startShake | Prefix（参数改写） | Boat_NoShake.cs:36-46 | **`pTimer=0` 在 boat 检查前执行→全局生效**（所有单位受击抖动时长归零，`_shake_timer=Min(0,max)`，Actor.cs:761-769）；船再清 vol/h/v |
| Actor.calculateForce | Prefix（否决） | Boat_NoShake.cs:48-54 | 船永不击退（**有** is_boat guard） |
| Actor.checkSpecialAttackLogic | Postfix | Boat_NoShake.cs:56-63 | **无 guard 全局生效**：`pDamageFinal = pInitialDamage` 撤销原版低血量投降/lost_fight 减伤（vanilla 在 :6335 置 1f、:6359 置 0f，Actor.cs:6306-6366）→ 全局战斗更致命 |

## Persistence

- **零自定义状态**：无 actor.data / custom_data / 文件存储——纯资产 + patch 型 mod
- 修改位于静态全局资产 + 常驻 Harmony：同会话跨世界保持（clearWorld 不重置 AssetManager，MapBox.cs:862+）；每次游戏启动 OnModLoad 重放
- **存档无痕**：船 stats 每次从（已改）资产重算；移除 mod 即回 vanilla，存档无残留、无需迁移
- Projectile clone get-or-clone 幂等（热重载安全）
- 注意：已存在的 Actor 实例不自动重读资产 stats（需 setStatsDirty）——boot 时序（世界晚于 OnModLoad）下无此问题；**热重载进已运行世界则旧船保持旧值**

## Compatibility / Risks

- 共享 vanilla 资产直改（boat_* items / boat_trading|transport_* actors / ProjectileAsset 字段）：其他 mod 改同字段 → last-writer-wins，加载序决定
- **两个全局无 guard patch**（本 mod 最大兼容性问题）：checkSpecialAttackLogic Postfix 全局撤投降减伤；startShake `pTimer=0` 全局消受击抖动——影响所有单位与其他 mod 预期，属反模式
- `Boat_Sight._kingdomPool` 静态字典跨世界不清理：陈旧引用 + 无界增长（每 kingdom 仅 64 槽，泄漏有限但存在）
- 反射字段名硬编码（ProjectileAsset 字段改名→静默跳过）；资产 id 硬编码（vanilla 改名→null 保护静默 no-op）
- 私有方法 patch 目标（applyAttack private static / checkSpecialAttackLogic private）跨游戏版本脆弱
- findEnemyObjectTarget prefix 忽略 `asset.can_attack_buildings` 参数（无条件可攻击建筑）

## Reusable Findings

1. **vanilla 船只战斗 = 三资产链**（ActorAsset.default_attack → EquipmentAsset → ProjectileAsset），纯改数据即可 rebalance 数值/弹道，无需 Harmony——`is_boat`（ActorAsset.cs:296）/`is_boat_transport`（:298）是现成的行为分流标志
2. `AssetLibrary.clone(pNew, pFrom)` = 深拷贝 + 注册（AssetLibrary.cs:83-90）；`AssetManager.projectiles` 与 items 同构可用——克隆武器/弹丸即新增变体，`weapon.projectile` 是武器→弹丸的唯一接点
3. `stats["projectiles"]` 语义 = 单帧齐射数（CombatActionLibrary.cs:243,261-277）——**时间分布连发（连射手感）必须 patch attackRangeAction**，本 mod 的协程+双发分帧+目标存活检查（Boat_RapidFire.cs:86-128）是该问题的参考实现
4. 原版索敌半径 = `unit_chunk_sight_range`(1 chunk)（SimGlobalAsset.cs:28）——远程武器（range > 视野）需要自建索敌；per-kingdom 环形缓存 + 扩 chunk 搜索（Boat_Sight）是性能友好参考
5. `ProjectileAsset.can_be_blocked=false` 跳过格挡/偏转战斗动作池（MapBox.cs:813-821）、`can_be_collided=false` 跳过碰撞——弹丸级"不可防御"开关
6. `Actor.checkSpecialAttackLogic` = 原版投降/lost_fight 减伤阀（Actor.cs:6306）——"战斗到底"类 mod 的 patch 点（但应加 guard，本 mod 反面示范）
7. `MapBox.applyAttack` 是命中结算总闸：deflect→block→BEFORE_HIT→伤害→getHit→击退→attackTargetActions（MapBox.cs:793-855）——替换它等于绕过整条高级战斗链

## Anti-patterns / Limitations

- 无 guard 全局 Postfix / 参数改写（见 Risks）——跨 mod 干扰面大
- applyAttack 替换丢掉 dodge/block/deflect 高级战斗链（对船或为特性，但被击方是 boat_transport 时也全局跳过）
- `ExistsInArray` 死代码（Boat_Sight.cs:152-159）；`boat_shotgun` 关闭 has_locales/show_in_meta_editor/knowledge window（隐藏资产正确做法）
- 无本地化 / 无配置；数值全硬编码；商船/海豹船特殊分支依赖魔法 id

## Pattern Candidates

- `candidate:rebalance-vanilla-asset-stats` — OnModLoad 直改共享资产 base_stats（零 Harmony rebalance）
- `candidate:clone-rewire-weapon-projectile` — clone 武器 + clone 弹丸 + 改 projectile 引用（非破坏派生）
- `candidate:timed-burst-projectile-patch` — 同帧齐射 → 协程时间分布连发
- `candidate:extended-sight-ring-cache-targeting` — per-kingdom 环形缓存 + 扩 chunk 索敌（超视野远程武器）

## Evidence

- mod：BoatRebalanceBox.cs:9-21 / Content.cs:8-13 / Boat_Weapons.cs:16-145 / Boat_States.cs:15-43 / Boat_Weapon_Projectile.cs:17-227 / Boat_Sight.cs:25-159 / Boat_RapidFire.cs:17-151 / Boat_NoShake.cs:12-63 / mod.json（v1.2.4，GUID GX4BoatRebalanceBox）
- vanilla：ActorAsset.cs:107,296,298,519 / ActorAssetLibrary.cs:3142-3301 / Actor.cs:761-769,1826,2771,6107-6113,6306-6366 / AssetLibrary.cs:55-90 / AssetManager.cs:163,409 / BaseSimObject.cs:363-386 / CombatActionLibrary.cs:235-280 / EnemiesFinder.cs:21-30 / SimGlobalAsset.cs:28 / MapBox.cs:703-743,746-791,793-855,862+ / ProjectileAsset.cs:14-88 / Projectile.cs:462 / ItemAsset.cs:59

## Unknowns

- Boat simple component（乘客登船，Actor.cs:3158 `getSimpleComponent<Boat>().hasPassengers()`）与船体数值如何影响乘客——未调查（本批边界外，deferred: boats system）
- `terraform_range=2` + 空 `terraform_option` 的实际地形效果（Projectile.cs:462 damageWorld 路径）——可能 no-op
- vanilla boat_trading_*/boat_transport_* 家族完整清单与原数值基线（仅确认前缀族与部分 default_attack，ActorAssetLibrary.cs:3142-3301）
- 运行时手感（连发观感、索敌行为差异）未实测——本库不运行游戏
