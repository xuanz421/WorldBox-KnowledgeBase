# System: City

WorldBox 城市系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。

## Scope

覆盖：City/CityData/CityManager 三层关系、创建（newCity/buildNewCity）、初始化、销毁、tick、citizen 关联维护（dirty-lists 重建机制）、Kingdom 关系、storage 真实数据结构、Building/Zone/Tile 接口边界、persistent/runtime 分界、加载恢复。

不覆盖：Building 系统内部（deferred: buildings）、CitizenJobs/Jobs 系统（deferred: jobs）、Resources 循环细节（deferred: resources）、Kingdom 系统内部（deferred: kingdom）、CityTasksData/AI 任务编排（deferred: behaviour）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `City` | 城市运行时实例（3192 行）：zones/citizens/buildings/storages/leader/kingdom | City.cs:8-3192 |
| `CityData` | 持久化 DTO：zones/equipment/rulers 统计/kingdomID/leaderID/文化引用 | CityData.cs:7-112 |
| `CityManager` | 容器 + dirty 重建调度 + 存档往返 + 创建入口 | CityManager.cs:3-287 |
| `MetaObject<CityData>` | 城市族基类（Alliance/Army/Family/Plot/War 同层）：units 列表 + dirty 标记 | MetaObject.cs:5-910 |
| `MetaSystemManager<City,CityData>` | manager 基类：beginChecksUnits/历史采集 | MetaSystemManager.cs |
| `CityStorageSlot` | 资源聚合计视图（id + amount，只读聚合非存储本体） | CityStorageSlot.cs:4-23 |
| `CityEquipment` | 城市装备（data.equipment，持久化） | CityData.cs:15 |

**无 CityAsset**：City 没有资产蓝图类型——城市身份由 `CityData.original_actor_asset`（创建者物种 asset id）+ 动态生成名决定（CityManager.newCity 直接 newObject，无 AssetManager 查询）。Kingdom 侧才有 `KingdomAsset`（civ 标志，CityManager.cs:88-91 使用）。

`World.world.cities : CityManager`（MapBox `_list_meta_main_managers`，MapBox.cs:328 附近）。

## Data Model

**三层同 Actor 模式但走 MetaObject 族**：

```text
（无 CityAsset 蓝图层）
City (运行时, MetaObject<CityData>)  ← CityManager 持有
 └ 1:1 CityData (持久化: zones/引用 id/统计)
```

- **CityData**（CityData.cs:7-112）：`zones : List<ZoneData>`（**城市持久化的核心**——领地即 zone 坐标列表）、`kingdomID/leaderID/founder_id/id_culture/id_language/id_religion`（long 引用）、`equipment : CityEquipment`、`total_food_consumed/timer_supply/timer_trade/past_rulers/total_leaders/timestamp_kingdom`、继承 MetaObjectData → BaseSystemData（name/id/custom_data_*）
- **runtime-only**（每帧或 dirty 事件重建，不持久化）：`units : List<Actor>`（citizens）、`buildings/buildings_dict_type/buildings_dict_id`、`storages/stockpiles : List<Building>`、`_professions_dict`、`_total_resource_slots : Dictionary<string,CityStorageSlot>`、`kingdom/culture/language/religion/leader/army`（对象引用，从 data id 恢复）、`zones : List<TileZone>`（TileZone 对象本身属于地图，City 只持有引用集合；持久化的是 ZoneData 坐标）
- **storage 真实位置**：城市**不拥有**资源存储——资源在各 `Building.data.resources : CityResources`（Building.cs:104，storage=true 的建筑）中；City 侧 `storages` 列表 + `_total_resource_slots` 是**聚合视图**（getTotalResourceSlots 遍历 storages 累加，City.cs:2963-2999）；`CityStorageSlot` 仅为 {id, amount} + `asset : ResourceAsset` 只读视图（CityStorageSlot.cs）

## Lifecycle / Flow

### 创建（Verified）

```text
behaviour 侧判定 canStartNewCityCivilizationHere(actor)            CityManager.cs:88-113
  （非 trait 强制王国 + canBuildNewCity + kingdom_asset.civ + 邻 zone 无同城）
buildNewCity(actor, zone)                                        CityManager.cs:75-82
 ├─ newCity(kingdom, zone, actor)                                CityManager.cs:55-73
 │   ├─ game_stats/map_stats.citiesCreated++
 │   ├─ city = newObject()（SystemManager 池 + map_stats.getNextId("city")）
 │   ├─ data.founder_id/founder_name/original_actor_asset 记录
 │   ├─ data.equipment = new CityEquipment()
 │   ├─ city.setKingdom(pKingdom)
 │   └─ city.addZone(zone) + 吞并周边无主 zone
 ├─ city.setUnitMetas(actor)（承接文化/语言/宗教）
 ├─ city.newCityEvent(actor)：recalculateCityTile + generateName   City.cs:756-760
 └─ WorldLog.logNewCity(city)
首城变体 buildFirstCivilizationCity（joinCity + convertSameSpeciesAroundUnit）CityManager.cs:115-121
```

`addZone`：zone 归属互斥（从原 city removeZone → setCity(this) → updateCityCenter → place_finder dirty → setStatusDirty，City.cs）。

### 初始化（Verified）

`CityManager.addObject` → `city.init()`：`createAI()`（AiSystemCity，仅 `Globals.AI_TEST_ACTIVE` 时；绑定 job_city/tasks_city 库 + build/check_loyalty/check_destruction 任务）+ `setStatusDirty()`（CityManager.cs:156-160, City init/createAI）。

### tick（Verified）

```text
MapBox.update
 → _list_meta_main_managers: CityManager.update(pElapsed)          CityManager.cs:95-105
    → 逐 city: current.update(pElapsed) + clearCursorOver
       City.update（City.cs）：timers（build/supply/trade/warrior）
       → updateTotalFood
       → isDirtyUnits() 提前返回（等重建）
       → !kingdom.wild && !hasUnits() → turnCityToNeutral()        City.cs:1246-1251
       → _dirty_city_status → updateCityStatus；_dirty_citizens → updateCitizens
```

**dirty-lists 重建机制（本系统核心调度）**：
- `MapBox.checkDirtyMetaObjects`（MapBox.cs:2098-2110）每帧调度：`cities.beginChecksBuildings()` / `kingdoms.beginChecksCities()` 等
- **citizens 重建**：`Actor.setCity` 触发 `cities.setDirtyUnits`（Actor.cs:7491-7498）→ `MetaSystemManager.parallelDirtyUnitsCheck`（MapBox 可并行分发，MapBox.cs:2091-2094）→ `updateDirtyUnits`：清空全部 city.units 后**遍历 `units.units_only_alive`，按 `actor.city` 重新 listUnit**（CityManager.cs:100-108, MetaSystemManager.cs:50-52）——即 citizen 归属的 ground truth 是 `actor.city` 引用 + `ActorData.cityID`，City.units 只是定期重建的缓存
- **buildings 重建**：`setDirtyBuildings` → `updateDirtyBuildings`：清空后遍历 city.zones 的 `zone.buildings_all`，`asset.city_building && isUsable()` → listBuilding（CityManager.cs:119-139）
- City.listUnit（City.cs）：boats 单列 `_boats`；base.units.Add + species 映射记录

### citizen 关联（Verified）

- Actor 侧入口：`joinCity`（Actor.cs:7750 附近，含 kingdom 联动/increaseJoined 统计）→ `setCity`（Actor.cs:7483-7501）：eventUnitRemoved/Added + `cities.setDirtyUnits` + `setKingdom(city.kingdom)` + setStatsDirty
- 持久化：`ActorData.cityID`（saveCity 写，Actor.cs:8734-8738）
- 恢复：`Actor.loadFromSave` → `World.world.cities.get(data.cityID)` → setCity（Actor.cs:8873-8877；依赖加载顺序 cities 先于 actors——见 technical/save.md）

### Kingdom 关系（Verified 边界）

- `city.kingdom` 引用 + `CityData.kingdomID/last_kingdom_id/timestamp_kingdom`
- `setKingdom`（City.cs，pFromLoad 区分）：setDirtyCities、首都清理、army 一致性检查
- 失去王国/公民 → `turnCityToNeutral`：boats 离城 + setKingdom(WildKingdomsManager.neutral) + 建筑强制中立（City.cs:1246-1251）
- Kingdom 系统计数（kingdoms.setDirtyCities 等）仅在边界处调用，内部 deferred: kingdom

### 销毁（Verified）

`CityManager.removeObject`（CityManager.cs）：citiesDestroyed 统计 + WorldLog.logCityDestroyed → `city.destroyCity()`（City.cs）: removeLeader/disbandArmy → 逐 zone.setCity(null) → **遍历全 units 解除该城 citizen** → equipment.clearItems → 清列表 → removeFromCurrentKingdom → `base.removeObject`（dict 移除 + dispose 调度）→ 各文化/王国/语言/宗教 setDirtyCities。

### 存档往返（Verified）

```text
保存: cities.save() → 逐 city.save()（CoreSystemObject.save → data.save()）→ List<CityData>  CityManager.cs:160-173
加载: loadCities(SavedMap)                                              CityManager.cs:126-139
  checkForCityErrors（zone 不可解析的 city 剔除；saveVersion<7 走 findZoneViaBuilding 兜底）
  → loadObject: base.loadObject（池+data）→ city.loadCity(pData)      CityManager.cs:122-127
     loadCity（City.cs）: loadCityZones（ZoneData → zone_calculator.getZone → addZone）
     → culture/language/religion 恢复 → equipment.loadFromSave
     → kingdom 恢复（kingdomID miss → neutral）
loadCities 之后再 addZone 一轮（saveVersion≥7 路径，CityManager.cs:131-138）
后续: loadLeaders（City.loadLeader：units.get(data.leaderID) → setLeader） City.cs:747-754
      setHomeBuildings / buildings 加载（见 save.md 管线序）
```

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `World.world.cities` | CityManager 入口 | MapBox.cs |
| `CityManager.buildNewCity(actor, zone)` | 建城主入口 | CityManager.cs:75 |
| `actor.joinCity(city)` / `actor.setCity` | citizen 关联（mod 应调 joinCity） | Actor.cs |
| `city.addZone(zone)` / `removeZone` | 领地变更（互斥归属） | City.cs |
| `city.setKingdom(kingdom)` | 归属变更（internal） | City.cs |
| `city.getStorageNear(tile, onlyFood)` | 就近存储建筑查找 | City.cs |
| `city.getTotalResourceSlots(resTypes)` | 全城资源聚合视图 | City.cs:2963-2999 |
| `city.data` | CityData（含 zones/引用 id/custom_data） | CityData.cs |
| `CityManager.setDirtyBuildings/units` | 触发列表重建 | CityManager.cs |

## Extension Points

1. **per-city 持久数据**：`city.data.get/set`（BaseSystemData 五型，随 map.wbox 往返——custom-kingdom-system pattern 已用）
2. **建城介入**：Harmony postfix `CityManager.buildNewCity` / `City.newCityEvent`（NML CityCreateListener 即 patch `newCityEvent` 发事件——跨源 Verified，NML CityCreateListener.cs:49）
3. **citizen 观察**：`Actor.setCity` patch 或 NML 事件（joinCity/leaveCity 统计在 joinCity 内）
4. **领地操作**：`addZone/removeZone`（注意互斥归属与 place_finder 联动）
5. **资源读取**：`getTotalResourceSlots`/`getStorageNear`（只读聚合；写存储属 buildings/resources 系统）

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| Actor | `actor.city` / `data.cityID` / `joinCity`/`setCity`；City.units 为重建缓存 | 已覆盖（entity/actor.md） |
| Kingdom | `city.kingdom` / `setKingdom` / `turnCityToNeutral`；kingdoms.setDirtyCities | deferred: kingdom |
| Buildings | `zone.buildings_all` → listBuilding（city_building 资产）；storages/stockpiles 分类缓存；Building.data.cityID 持久化 | deferred: buildings |
| Storage/Resources | 存储本体在 `Building.data.resources : CityResources`；City 仅聚合视图 | deferred: resources |
| Zone/Tile | `zones : List<TileZone>` / ZoneData 坐标持久化 / zone.city 互斥引用 | deferred: world |
| Jobs | `city.jobs : CitizenJobs` / `_professions_dict`（updateCitizens 重建） | deferred: jobs |
| Save | cities.save/loadCities/loadCity/loadLeader（本文件加载节 + technical/save.md） | 已覆盖 |

## Evidence

| 结论 | source | location |
|---|---|---|
| 三层关系与无 CityAsset | worldbox | City.cs:8, CityData.cs:7, CityManager.cs:55-73, City.getFounderSpecies |
| 创建链 | worldbox | CityManager.cs:55-121 |
| 初始化（AI 仅 AI_TEST_ACTIVE） | worldbox | CityManager.cs:156-160; City.cs（init/createAI） |
| tick 链与中立化 | worldbox | CityManager.cs:95-105; City.cs（update/turnCityToNeutral:1246） |
| dirty-lists 重建（citizens/buildings） | worldbox | MapBox.cs:2091-2110; CityManager.cs:100-153; Actor.cs:7483-7501 |
| citizen 关联与持久化 | worldbox | Actor.cs:7483-7501, 7750 附近 joinCity, 8734-8738, 8873-8877 |
| storage 聚合视图（本体在 Building） | worldbox | City.cs:2963-2999, CityStorageSlot.cs:4-23, Building.cs:104 |
| Kingdom 边界 | worldbox | City.cs（setKingdom/turnCityToNeutral）, CityManager.removeObject |
| 销毁链 | worldbox | CityManager.cs（removeObject）, City.cs（destroyCity） |
| 存档往返 + 旧档 zone 兜底 | worldbox | CityManager.cs:122-173 |
| NML 建城事件 patch 点 | neomodloader | CityCreateListener.cs:49（HarmonyPatch typeof(City) "newCityEvent"） |

## Confidence

- Verified：全部核心模型与流程结论
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- `CityTasksData`/`AiSystemCity` 任务编排（→ behaviour 系统）
- `CitizenJobs`/`CityEquipment` 内部结构（→ jobs/items 系统）
- Zone 生长/废弃机制（canGrowZones/_dirty_abandoned_zones）
- LoyaltyCalculator / CityStatus 状态机细节
- `CityManager.isLocked` / MetaObjectCounter 计数器用途全貌
- checkForCityErrors 的 saveVersion<7 findZoneViaBuilding 兜底完整规则
- ~~Kingdom 边界已知未知项~~ **已关闭（2026-09-07，→ political/kingdom.md）**：city.kingdom 双向 dirty 重建（kingdoms.updateDirtyCities 遍历 city.kingdom 重填 kingdom.cities）、setCapital/capitalID、turnCityToNeutral 全链、king 空位计时
- ~~存储本体 CityResources 边界~~ **已关闭（2026-09-07，→ settlement/buildings.md）**：CityResources 结构（_resources dict + saved_resources 持久化）、容量归属（ResourceAsset.maximum/storage_max，非建筑/城市定义）、City.storages 聚合自 zone.buildings_all 的 storage 资产

## Related Patterns

- [custom-kingdom-system](../../patterns/kingdom/custom-kingdom-system.md) — per-city data + kingdom 联动（本系统 data 层的 modding 实践）
- [persistent-mod-data](../../patterns/persistence/persistent-mod-data.md) — 城市级持久数据选型
- [world-tick-integration](../../patterns/lifecycle/world-tick-integration.md) — 城市周期驱动接入
- [harmony-prefix-recipes](../../patterns/patching/harmony-prefix-recipes.md) — 介入建城/吞并流程
