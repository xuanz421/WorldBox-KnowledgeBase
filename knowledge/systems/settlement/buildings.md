# System: Buildings / Construction

WorldBox 建筑系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。本文件关闭 city.md 的 storages/CityResources 边界 Known Gap（见回写记录）。

## Scope

覆盖：BuildingAsset/Building/BuildingData 数据模型、创建（addBuilding/setBuilding）、施工与完成（同对象生命周期）、销毁与状态机（Normal/Construction/Ruins/Abandoned/Removed）、BuildingManager 职责与 tick、City/Zone/Tile 关联维护、data.resources（CityResources）真实结构、City.storages 聚合、资源容量归属澄清、资产注册（Asset Framework 三阶段参与）、save/load 恢复。

不覆盖：ResourceAsset 定义与资源生产/消耗循环（deferred: resources）、建筑建造行为（behaviour 域的 BehCity* 建造决策）、BuildingAsset 渲染/动画细节、StorageBooks/书系统。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `Building` | 建筑运行时实例（1638 行）：tiles 占用、状态机、居民、施工进度 | Building.cs:6-1638 |
| `BuildingAsset` | 建筑蓝图（174 字段：fundament/storage/book_slots/construction_progress_needed 等） | BuildingAsset.cs |
| `BuildingData` | 持久化 DTO：mainX/mainY/asset_id/cityID/state/resources/books/frameID | BuildingData.cs:6-65 |
| `BuildingManager` | SimSystemManager 容器 + JobManagerBuildings 批处理 + 可见性/渲染数据 | BuildingManager.cs:7-579 |
| `CityResources` | **建筑级**资源容器（_resources dict + food/other 列表缓存 + saved_resources） | CityResources.cs:4-208 |
| `CityStorageSlot` | 资源槽（id + amount；`asset : ResourceAsset` 惰性取） | CityStorageSlot.cs |
| `BuildingLibrary` | 建筑库（代码定义 12 类 init + post_init 从 Architecture 派生） | BuildingLibrary.cs:7-2008 |
| `BaseBuildingComponent` | 建筑组件（池化，addComponent 泛型注入，如 BuildingSmokeEffect） | Building.cs addComponent |

继承：`Building : BaseSimObject`（与 Actor 同基类！实现 `ILoadable<BuildingData>`）；`BuildingLibrary : AssetLibrary<BuildingAsset>`（标准资产库）。

## Data Model

**与 Actor 同构的蓝图-实例-数据三层**：

```text
BuildingAsset (蓝图, AssetManager.buildings, fundament 定占地)
      │ asset.buildings : 反向实例列表（setTemplate 时加入）
      ▼
Building (运行时, BaseSimObject, 持久 tiles 占用)
      │ 1:1
      ▼
BuildingData (持久化: mainX/mainY + asset_id + cityID + state + resources + books + frameID)
```

- **BuildingData**（BuildingData.cs:6-65）：位置存 `mainX/mainY`（**主 tile 坐标**，非 long id）；`asset_id` string；`cityID` long（prepareForSave 时写，Building.cs:845-858）；`state : BuildingState`（状态机持久化）；`resources : CityResources`（**storage 资产的建筑物才有**）；`books : StorageBooks`；`frameID` 动画帧；施工进度走 `data.change("construction_progress", ...)`（**custom_data int 容器**，Building.cs:1138）
- **runtime-only**：`tiles : List<WorldTile>`（fundament 展开）、`zones`、`residents`、`components_list`、`chopped`、动画状态、`kingdom`（对象引用）
- **CityResources**（CityResources.cs:4-208）：`_resources : Dictionary<string, CityStorageSlot>` + `_list_food/_list_other` 缓存 + `saved_resources : List<CityStorageSlot>`（持久化载体，save() 只留非零槽）；`change()` 上限裁剪 `value.asset.maximum`
- **容量归属（重要澄清，Verified）**：单资源上限在 **ResourceAsset**（`maximum`/`storage_max`，CityResources.cs:53-76 引用）；**建筑不定义容量**——capacity 判定 `hasSpaceForResource(asset)` 完全查询 ResourceAsset；City 层无独立容量

## Lifecycle / Flow

### 创建（Verified）

```text
BuildingManager.addBuilding(assetID/asset, tile, checkForBuild, sfx, type)   BuildingManager.cs
 1. 可选 canBuildFrom（fundament 占地/地形/adaptation tag 检查）
 2. building = newObject()（map_stats.getNextId("building")）
 3. building.create()（setObjectType(Building) + startShake）
 4. building.setBuilding(tile, asset, pData: null)                          Building.cs
    ├─ current_tile.zone.addBuildingMain(this)  ← zone 即时登记
    ├─ setTemplate(pAsset)：asset = pAsset; data.asset_id; asset.buildings.Add
    │   （canBeOccupied → manager.occupied_buildings）
    ├─ data.mainX/mainY 记录 + setState(Normal) + updateStats + setMaxHealth
    └─ fillTiles()：fundament 矩形展开 → setBuildingTile（tiles[i].building = this）
    后续: storage 资产 → data.resources = new CityResources()
          book_slots > 0 → data.books = new StorageBooks()
          smoke 等组件注入（addComponent，池化）
          asset.kingdom 非空 → setKingdom(kingdoms_wild.get(asset.kingdom))
```

### 施工与完成（Verified，同一对象生命周期）

- 施工开始：建造行为调 `setUnderConstruction()`——**仅当 `asset.has_sprite_construction`** 才生效（无施工贴图的建筑跳过施工态，Building.cs:1341-1347）；标记存 `data.addFlag("under_construction")`
- 进度：`updateBuild(progress)` → `data.change("construction_progress", p)` → 累计超过 `asset.construction_progress_needed` → `completeConstruction()`（删 custom key + 删 flag + makeZoneDirty）+ 建成音效/动画（Building.cs:1136-1157）
- **结论**：construction 与 finished 是**同一 Building 对象的状态切换**（flag + custom_data int），不是两个实体；施工中建筑在 saved 里就是普通 BuildingData + flag

### 状态机与销毁（Verified）

```text
BuildingState: Normal → (Ruins) → Removed
放弃: makeAbandoned()  → setKingdom(abandoned wild 单例)
        施工中 → startDestroyBuilding；has_ruin_state → startMakingRuins；否则直接拆
荒废化: startMakingRuins → makeRuins（setKingdom("ruins") + setState(Ruins)）
物理摧毁: startDestroyBuilding → has_ruins_graphics 且非施工 → Ruins 态，然后 startRemove
最终移除: removeBuildingFinal → setState(Removed) → clearZones/clearTiles
        （tiles[i].building = null 解除占用）→ kill() → zone.removeBuildingMain
        → manager.scheduleDestroyOnPlay（回池）
setState 内部: data.state = pState + checkAutoRemove + checkMaterial + clearZones/fillTiles
```

### tick（Verified）

```text
MapBox → BuildingManager.update(pElapsed)                                  BuildingManager.cs
  → _job_manager.updateBase（JobManagerBuildings 批处理，与 Actor 同构）
  渲染路径独立: calculateVisibleBuildings → fillVisibleObjects → precalculateRenderData*
```

### City / Zone / Tile 关联（Verified）

- **zone 是登记点**：`setBuilding` 即 `zone.addBuildingMain`；City 侧 cities 缓存经 `updateDirtyBuildings` 遍历 `zone.buildings_all`（`asset.city_building && isUsable()`）重建（见 settlement/city.md）
- **tile 占用**：fillTiles 按 fundament 展开写 `tile.building`；removeBuildingFinal → clearTiles 解除
- **city 判定**：`building.city => current_tile.zone.city`（**运行时通过 zone 间接推导，无直接字段**，Building.cs:102）；持久化靠 `data.cityID`（prepareForSave 写，load 后 setHomeBuildings 管线恢复一致性）
- `setKingdomCiv`/`setKingdom`：wild→civ 边界（`asset.kingdom` string 字段 + setKingdom 联动 dirty）

### Save / Load（Verified）

```text
保存: SavedMap.create → building.prepareForSave（cityID id 化 + resources.save()
      只留非零槽 + frameID + data.save()）                        Building.cs:845-858
加载: loadBuildings（管线在 cities/actors 之后）                  save.md 管线序
  BuildingManager.loadObject(pData)                                BuildingManager.cs
    ├─ state == Removed → null（跳过）
    ├─ AssetManager.buildings.get(asset_id) miss → null（资产丢失静默丢弃）
    ├─ GetTileSimple(mainX, mainY) + canBuildFrom(Load)（占地校验失败 → null）
    └─ base.loadObject + create() + setBuilding(tile, asset, pData)
       （setData + setTemplate + fillTiles 重建占用 + kingdom 恢复）
       + loadBuilding：frameID 动画恢复 + resources.loadFromSave()
       （saved_resources 逐槽 AssetManager.resources.get 校验 + 重建 dict）
```

### 资产注册（Verified，与 technical/assets.md 三阶段互证）

`BuildingLibrary.init()`：12 类代码定义（addTrees/addVegetation/addMinerals/addPoop/addGrownResources/addGeneralCityBuildings/addNatureBuildings/addMobBuildings/addCreeps/addHumans/addOrcs/addElves/addDwarves）；`post_init`：`initBuildingsFromArchitectures`（**从 Architecture 资产派生建筑**——post 阶段因依赖 architecture_library）；`linkAssets`：跨库链接。注册走标准 `AssetLibrary.add`（last-wins + create 钩子）。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `World.world.buildings` | BuildingManager 入口 | MapBox.cs |
| `BuildingManager.addBuilding(asset, tile, check)` | 建筑创建主入口（internal） | BuildingManager.cs |
| `AssetManager.buildings.get(id)` | 建筑资产查找 | AssetLibrary.cs |
| `building.data.resources` | CityResources（仅 storage 资产） | Building.cs:104 |
| `building.state` / `isUnderConstruction()` | 状态机查询 | BuildingData.cs / Building.cs |
| `building.updateBuild(n)` | 施工推进（behaviour 侧调用） | Building.cs:1136 |
| `building.setKingdom(k)` / `setKingdomCiv` | 归属变更 | Building.cs |
| `City.getTotalResourceSlots()` | City 侧聚合视图（遍历 storages） | City.cs:2963 |
| `BuildingManager.occupied_buildings` | 可驻留建筑集合 | BuildingManager.cs |

## Extension Points

1. **注册新建筑**：`AssetManager.buildings.add(new BuildingAsset{...})`（clone-modify-asset pattern 的主用例——派生原版建筑改字段）
2. **per-building 持久数据**：`data.get/set`（custom_data；注意 `under_construction`/`construction_progress` 已占用这两个 key——冲突避免）
3. **创建介入**：Harmony postfix `BuildingManager.addBuilding` / `Building.setBuilding`
4. **资源容器扩展**：storage 资产自动获得 `data.resources`（CityResources API：get/change/set/hasSpaceForResource）——新资源类型需先注册 ResourceAsset（→ resources 系统）
5. **状态机介入**：`makeAbandoned`/`makeRuins` patch（危房/废墟玩法）

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| City | `zone.buildings_all` → cities 重建；`data.cityID`；`city.storages/stockpiles` 聚合 storage 资产 | 已覆盖（settlement/city.md） |
| Resources | 容量在 ResourceAsset（maximum/storage_max）；生产/消耗循环、strategic_resource_assets | deferred: resources |
| Kingdom | `asset.kingdom` string（wild 归属）；setKingdom/setKingdomCiv | 已覆盖（political/kingdom.md） |
| Zone/Tile | addBuildingMain/fillTiles 占用；`building.city` 经 zone 推导 | deferred: world |
| Actor | residents 居住（hasResidentSlots）；getNearbyBuildingToLive | 已覆盖边界 |
| Assets | BuildingLibrary 三阶段 + Architecture 派生 | 已覆盖（technical/assets.md） |
| Save | prepareForSave/loadObject（Removed 跳过 + canBuildFrom(Load) 校验） | 已覆盖（technical/save.md） |

## Evidence

| 结论 | source | location |
|---|---|---|
| 三层数据模型 + zone 登记 + fundament 占用 | worldbox | Building.cs:219, 484-493, fillTiles; BuildingData.cs:6-65 |
| 创建链（addBuilding → create → setBuilding） | worldbox | BuildingManager.cs（addBuilding 两重载） |
| 施工 = 同对象 flag + custom_data 进度 | worldbox | Building.cs:1136-1157, 1319-1347 |
| 状态机与销毁链 | worldbox | Building.cs:882-963（startDestroy/makeRuins/removeBuildingFinal/kill） |
| BuildingManager tick + JobManagerBuildings | worldbox | BuildingManager.cs update |
| CityResources 结构与容量归属（ResourceAsset） | worldbox | CityResources.cs:4-208, 43-60, 70-77; CityStorageSlot.cs |
| City.storages 聚合来源 | worldbox | CityManager.updateDirtyBuildings; City.listBuilding |
| 资产注册（12 init + Architecture 派生在 post_init） | worldbox | BuildingLibrary.cs init/post_init |
| save/load（Removed 跳过 + Load 校验 + resources 往返） | worldbox | Building.prepareForSave:845-858; BuildingManager.loadObject; CityResources.loadFromSave/save |
| building.city 经 zone 推导 | worldbox | Building.cs:102 |

## Confidence

- Verified：全部机制结论
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- ResourceAsset 完整字段（maximum/storage_max/strategic_resource_assets 语义）——deferred: resources 系统
- 资源生产/采集循环（BehCityActorGetResourceFromStorage 等）——deferred: resources/jobs
- 建造决策行为（谁决定 addBuilding + canBeUpgraded/upgradeBuilding）——deferred: behaviour
- StorageBooks/书槽（book_slots）内部
- BuildingFundament 旋转/异形占地规则全貌
- `initBuildingsFromArchitectures` 的派生映射规则

## Related Patterns

- [clone-modify-asset](../../patterns/assets/clone-modify-asset.md) — 建筑派生注册（本系统 add 路线的 modding 实践）
- [custom-kingdom-system](../../patterns/kingdom/custom-kingdom-system.md) — 建筑 kingdom 联动玩法
- [safe-asset-registration](../../patterns/assets/safe-asset-registration.md) — last-wins 防御
- [persistent-mod-data](../../patterns/persistence/persistent-mod-data.md) — 建筑级数据选型
