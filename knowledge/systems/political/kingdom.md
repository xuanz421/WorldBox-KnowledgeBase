---
title: Kingdom 系统
aliases:
  - Kingdom and Political
---

# System: Kingdom / Political

WorldBox 王国系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。本文件同时关闭 city.md 的 Kingdom 边界类 Known Gap 项（见回写记录）。

## Scope

覆盖：Kingdom/KingdomData/KingdomManager 三层职责、创建（civ + wild 双轨）、初始化、销毁、tick、City 归属（dirty 重建）、King/Leader 关联、持久化分界、save/load 引用恢复、KingdomAsset 概念澄清、war/alliance/diplomacy 系统边界、Modding 入口。

不覆盖：War 战争流程内部、Alliance 管理内部、Diplomacy opinion 计算内部（各 deferred）；Culture 系统；Clan/royal clan 细节（仅记录接口）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `Kingdom` | 王国运行时实例（1540 行）：king/capital/cities/buildings/power/AI | Kingdom.cs:7-1540 |
| `KingdomData` | 持久化 DTO：kingID/capitalID/allianceID/royal_clan_id/saved_traits/past_rulers | KingdomData.cs:7-111 |
| `KingdomManager` | civ 王国容器 + dirty cities/buildings 重建 + 历史 DB | KingdomManager.cs:6-260 |
| `WildKingdomsManager` | **独立** wild 王国容器（每个 KingdomAsset 一个静态实例；负 id） | WildKingdomsManager.cs:3+ |
| `MetaObjectWithTraits<KingdomData,KingdomTrait>` | 带 trait 的 meta 基类（Clan/Culture/Language/Religion/Subspecies 同层） | MetaObjectWithTraits.cs:5-420 |
| `KingdomAsset` | 王国**类别**资产（civ/mobs/neutral/nature/nomads 等布尔标签族 + friendly/enemy tags） | KingdomAsset.cs:7-167 |
| `Alliance` / `War` / `DiplomacyManager` | 边界系统（仅接口级） | Alliance.cs:5-675 等 |

继承：`Kingdom : MetaObjectWithTraits<KingdomData, KingdomTrait> : MetaObject<KingdomData>`；派生 `DeadKingdom`（仅历史 DB 查询用）。

## Data Model

**概念澄清（重要，Verified）**：Kingdom 有**双层身份**：
1. `KingdomAsset`（注册于 `AssetManager.kingdoms`，~33 布尔/标签字段）——王国**类别**："civilization"“mobs”“neutral”“nature”"nomads" 等是 `KingdomAsset` 上的布尔字段（`civ/mobs/neutral/nature/nomads`，KingdomAsset.cs:字段清单），不是独立类型
2. `Kingdom` 实例——**每个 KingdomAsset 对应一个 wild Kingdom 常驻实例**（`WildKingdomsManager` 构造时为全部 KingdomAsset 创建，`newWildKingdom`，负 id 序列，WildKingdomsManager.cs:22-48）；civ Kingdom 是运行时动态创建的正 id 实例

- **持久化（KingdomData，Verified）**：`kingID/capitalID/last_capital_id/allianceID/royal_clan_id/id_culture/id_language/id_religion`（long 引用）、`original_actor_asset`（string）、`saved_traits : List<string>`、`past_rulers : List<LeaderEntry>/total_kings`、`motto/colorId/raceId/banner_*`、时间戳族（alliance/last_war/new_conquest/king_rule）+ `timer_new_king`、left/joined/moved/migrated 统计 + BaseSystemData 基础（name/id/custom_data_*）
- **runtime-only**：`cities : List<City>` / `buildings : List<Building>`（**dirty 重建缓存**）、`king : Actor` / `capital : City`（对象引用，从 data id 恢复）、`culture/language/religion`、`ai : AiSystemKingdom`、`power`、`cache_enemy_check`、tax 缓存
- **KingdomTrait**：与 ActorTrait 同 BaseTrait 族（`trait_library` 属性 → `AssetManager.kingdoms_traits`；`default_traits`/`saved_traits` 虚属性接入基类通用 trait 管线）

## Lifecycle / Flow

### 创建（Verified 双轨）

```text
civ 王国:
behaviour 触发 → KingdomManager.makeNewCivKingdom(actor, pID, pLog)     KingdomManager.cs
 1. kingdomsCreated 统计
 2. kingdom = newObject()（map_stats.getNextId("kingdom") 正 id）
 3. kingdom.newCivKingdom(actor)                                        Kingdom.cs
    asset = AssetManager.kingdoms.get(actor.asset.kingdom_id_civilization)
    （**资产由单位物种的 kingdom_id_civilization 字段决定**）
    data.original_actor_asset 记录 + 生成名 + generateNewMetaObject
 4. actor.stopBeingWarrior + joinKingdom + setKing（King 职业设定）
 5. addObject → createAI（AiSystemKingdom，仅 Globals.AI_TEST_ACTIVE）
    + zone_calculator.setDrawnZonesDirty
 6. WorldLog.logNewKingdom

wild 王国:
WildKingdomsManager 构造期 → newWildKingdom(asset)（负 id _latest--）    WildKingdomsManager.cs:22-48
  kingdom.asset = pAsset; createWildKingdom()（wild = true + 默认色）
  静态单例：abandoned / ruins / nature / neutral（neutral.original_actor_asset = "druid"）
```

### tick（Verified）

```text
MapBox → _list_meta_main_managers: KingdomManager.update(pElapsed)      KingdomManager.cs
  逐 kingdom clearCursorOver；!World.world.isPaused() → updateCivKingdoms
  → kingdom.updateCiv(pElapsed)：data.timer_new_king 递减；
    ai != null 时 timer_action 递减 → ai.update()（AiSystemKingdom 边界）
另有 updateAge（年龄推进，独立入口）
```

### City 归属（Verified，与 city.md 互证）

- **ground truth 是 `city.kingdom` 引用 + `CityData.kingdomID`**（City.setKingdom 内部维护双向）
- `kingdoms.setDirtyCities()` → `beginChecksCities → updateDirtyCities`：**清空全部 kingdom.cities 后遍历 `World.world.cities` 按 `city.kingdom` 重新 listCity**（KingdomManager.cs，与 City 侧 citizens 重建同机制）；buildings 同构（`updateDirtyBuildings` 遍历 city zones）
- 归属变更入口全在 City 侧（setKingdom/turnCityToNeutral，见 settlement/city.md）；Kingdom 侧被动接收

### King / Leader（Verified）

- `setKing(actor, pFromLoad)`：`king = actor` + `setProfession(UnitProfession.King)`；非加载路径补 total_kings/addRuler/时间戳/幸福事件 + `trySetRoyalClan`（Kingdom.cs）
- 空位：`data.timer_new_king` 倒计时驱动新王选举（kingLeftEvent → removeKing → timer 置随机 5-20f，Kingdom.cs:625-626）
- Actor 侧：`data.civ_kingdom_id` 持久化 + `joinKingdom`（统计）/`setKingdom`（双容器 dirty 联动：wild→kingdoms_wild、civ→kingdoms，Actor.cs）

### 销毁（Verified）

`KingdomManager.removeObject`：统计 + logKingdomDestroyed → `diplomacy.removeRelationsFor` → 幸存者降 nomads（makeSurvivorsToNomads）→ 逐 war removeFromWar → alliance leave → cultures/languages/religions setDirtyKingdoms → base.removeObject → **`DBInserter.insertData(data, "kingdom")`**（死亡王国入 stats DB，`db_get` 可查 DeadKingdom）。

### Save / Load（Verified）

- 保存：`Kingdom.save()` 覆写——culture/religion/language/king id 化 + `saved_traits`（Kingdom.cs）；随 `kingdoms.save()` 进 SavedMap.kingdoms
- 加载顺序（save.md 管线）：`loadKingdoms`（kingdoms.loadFromSave）在 **cities 之前**；Kingdom `loadData` → `loadTraits()`（基类通用管线，MetaObjectWithTraits.cs:47-51）——**不走 addTrait**、直填 `_traits` 后 recalcBaseStats
- 二次恢复（`load2`，Kingdom.cs）：`World.world.cities.get(data.capitalID)` → setCapital；`units.get(data.kingID)` → setKing(pFromLoad: true)——**依赖 cities/actors 均已加载**（管线序保证）
- alliance 边界：`getAlliance()` 惰性解析 `data.allianceID`（miss → 置 -1），allianceJoin/Leave 维护 id + 时间戳（Kingdom.cs）

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `World.world.kingdoms` / `kingdoms_wild` | 双容器（civ 正 id / wild 负 id） | MapBox.cs |
| `KingdomManager.getCivOrWildViaID(id)` | 跨容器查询（id<0 → wild） | KingdomManager.cs |
| `KingdomManager.makeNewCivKingdom(actor)` | civ 建国入口 | KingdomManager.cs |
| `kingdom.setKing(actor)` / `setCapital(city)` | King/首都设定（内部维护 data id） | Kingdom.cs |
| `kingdom.isCiv()/isMobs()/isNeutral()/isNature()/isNomads()` | 类别判定（转 asset 字段） | Kingdom.cs |
| `kingdom.getWars()` / `getAlliance()` / `isEnemy(k)` | war/alliance 边界查询 | Kingdom.cs |
| `WildKingdomsManager.neutral/abandoned/ruins/nature` | 静态 wild 单例 | WildKingdomsManager.cs |
| `kingdom.data` | KingdomData（含 custom_data） | KingdomData.cs |

## Extension Points

1. **per-kingdom 持久数据**：`kingdom.data.get/set`（custom-kingdom-system pattern 的核心，与本体机制一致——Verified 互证）
2. **建国介入**：Harmony patch `KingdomManager.makeNewCivKingdom`（NML KingdomSetupListener 即以 Transpiler 在此发事件——跨源 Verified）
3. **KingdomTrait 注册**：`AssetManager.kingdoms_traits.add`（走 BaseTraitLibrary 通用管线，与 traits.md 模型一致）
4. **wild 单例复用**：neutral/abandoned/ruins 常驻可用于归属重置类玩法

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| City | `city.kingdom`/`setKingdom`；`kingdoms.setDirtyCities` 重建 cities 缓存；setCapital | 已覆盖（settlement/city.md） |
| Actor | `king`/`joinKingdom`/`setKingdom`；`data.civ_kingdom_id`；`actor.asset.kingdom_id_civilization` 决定建国资产 | 已覆盖（entity/actor.md） |
| War | `getWars/isInWarWith/attacker/defender`；War.main_attacker/main_defender id（含 db_get 死王兜底） | deferred: war/combat |
| Alliance | `data.allianceID` 惰性解析 + join/leave 时间戳 | deferred: alliance |
| Diplomacy | `World.world.diplomacy.getOpinion(a,b)`；销毁时 removeRelationsFor | deferred: diplomacy |
| Culture/Language/Religion | kingdom.culture/language/religion 引用 + setDirtyKingdoms | deferred: culture |
| Save | kingdoms.save/loadFromSave/load2 二次恢复 | 已覆盖（technical/save.md） |

## Evidence

| 结论 | source | location |
|---|---|---|
| 双层身份（Asset=类别 + wild 常驻实例） | worldbox | KingdomAsset.cs:7-167; WildKingdomsManager.cs:22-48; Kingdom.isCiv 系 |
| civ 创建链（资产由单位 species 决定） | worldbox | KingdomManager.makeNewCivKingdom; Kingdom.newCivKingdom |
| wild 创建（负 id + 静态单例） | worldbox | WildKingdomsManager.cs 构造 + newWildKingdom |
| tick 与 AI 门控 | worldbox | KingdomManager.update/updateCivKingdoms; Kingdom.updateCiv/createAI |
| City 归属 dirty 重建 | worldbox | KingdomManager.updateDirtyCities/beginChecksCities |
| King 关联与空位计时 | worldbox | Kingdom.setKing/kingLeftEvent（timer_new_king 5-20f） |
| 销毁链（含 DB 归档） | worldbox | KingdomManager.removeObject; db_get/DeadKingdom |
| save/load + load2 二次恢复 | worldbox | Kingdom.save; Kingdom.load2; MetaObjectWithTraits.loadData→loadTraits |
| alliance 惰性解析 | worldbox | Kingdom.getAlliance/allianceJoin/allianceLeave |
| NML 建国事件 patch 点 | neomodloader | KingdomSetupListener.cs:44-48（Transpiler makeNewCivKingdom） |

## Confidence

- Verified：全部机制结论（含与 custom-kingdom-system pattern 的互证）
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- War 生命周期（newWar/endWar/peace 流程）与 renown 结算——deferred: war/combat 系统
- Alliance 内部（createNewAlliance/成员管理/renown 加成）
- DiplomacyManager opinion 计算与 newDiplomacyTick 周期
- `KingdomTrait` 特有字段（tax trait 两类）与 trait 完整清单
- `power` 的计算来源与用途
- royal clan 继承完整规则（trySetRoyalClan 已见入口）
- `makeSurvivorsToNomads` 降级细节

## Related Patterns

稳定 pattern_id（完整索引：knowledge/patterns/模式索引.md）：

- `custom-kingdom-system` — per-kingdom data + KingdomTrait 的 modding 实践（与本体 dirty 重建/trait 管线一致）
- `harmony-prefix-recipes` — 介入建国/灭亡流程
- `persistent-mod-data` — 王国级持久数据选型
- `world-tick-integration` — 王国 AI 周期驱动
