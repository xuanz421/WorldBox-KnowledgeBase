---
title: Save 系统
aliases:
  - Save and Persistence
---

# System: Save / Persistence

WorldBox 存档系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。本文件同时关闭 actor.md / traits.md 的 Save deferred 项。

## Scope

覆盖：SavedMap 快照模型、保存主流程（saveWorldToDirectory）、加载主流程（loadWorld/loadData + SmoothLoader 管线）、runtime→persistent 转换（prepareForSave 家族）、id 分配与跨存档稳定性、custom_data 落盘路径、JSON converter 层（Long/Delegate）、SaveConverter 版本迁移、AutoSave、stats DB（SQLite）双库结构、mod custom data 可靠层级。

不覆盖：WorldTileData/tile 压缩细节（world 系统）、DBTables 各历史表结构（stats 域）、MapMetaData 面板字段、NML mod 自管文件持久化（persistent-mod-data pattern 已覆盖）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `SavedMap` | **整世界快照 DTO**：tiles/cities/actors_data/kingdoms/... 20+ 数据列表 + camera/mapStats/worldLaws | SavedMap.cs:11-534 |
| `SaveManager` | MonoBehaviour 门面：槽位/路径管理、saveWorldToDirectory、loadWorld/loadData、meta/preview | SaveManager.cs:11-1360 |
| `SaveConverter` | 静态版本迁移：convert(SavedMap) 按 saveVersion 阶梯升级 + asset/kingdom id fixer | SaveConverter.cs:5-804 |
| `AutoSaveManager` | 静态定时器：update → autoSave（非压缩路径） | AutoSaveManager.cs:7-185 |
| `MapStats` | 世界元数据 + **id 计数器族**（id_unit/id_city/...）+ `custom_data : SaveCustomData` | MapStats.cs:10+ |
| `SaveCustomData` | 世界级自定义数据容器（空壳类 : BaseSystemData，五型 custom_data 继承自基类） | SaveCustomData.cs:3-6 |
| `DBManager` / `DBTables` | 第二持久层：SQLite stats 库（map_stats.s3db），历史表插入/迁移 | db/DBManager.cs:8-208 |
| `JsonHelper` + `LongJsonConverter` / `DelegateConverter` | 序列化层：long 宽容解析（字符串/前缀/GUID 兼容）、委托单向序列化 | JsonHelper.cs:3-54 等 |

## Data Model

**一个存档 = 一个目录，三个文件**（SaveManager.cs:19-37 常量）：

```text
saves/<slot>/
  map.wbox        主数据（zlib 压缩 JSON，SavedMap）
  map.meta        元数据（MapMetaData JSON，槽位列表/预览用）
  map_stats.s3db  SQLite 历史统计库（DBManager）
autosaves/<epoch>/   自动存档（map.wbax 非压缩 JSON + meta）
```

- `SavedMap` 顶层持有全部实体数据列表：`actors_data : List<ActorData>`、`cities : List<CityData>`、`kingdoms/clans/alliances/wars/plots/relations/cultures/books/subspecies/languages/religions/families/armies/items`、tiles（tileArray 行程编码 + fire/conway/frozen id 列表）、`mapStats : MapStats`、`worldLaws`、camera（SavedMap.cs:14-86）
- **双持久层**：map.wbox（实体状态）+ map_stats.s3db（历史统计，SQLiteAsyncConnection，DBManager.cs:8-208）；`Config.disable_db` 可关后者（SaveManager.cs:933）
- `saveVersion`（SavedMap.cs:14）随 `Config.WORLD_SAVE_VERSION` 写入（SavedMap.cs:226）

## Lifecycle / Flow

### 保存（Verified 全链）

```text
UI: clickSaveSlot → saveToCurrentPath → saveWorldToDirectory(path)   SaveManager.cs:65-101
 1. saveImagePreview(path)
 2. saveMapData(path, compress)
    ├─ currentWorldToSavedMap()                       SaveManager.cs:103-109
    │    World.world.items.diagnostic(); new SavedMap(); savedMap.create()
    ├─ saveMetaData(map.meta) + saveStatsIn(s3db)     SaveManager.cs:134-135, 289-299
    └─ compress ? savedMap.toZip("map.wbox.tmp")      zlib BestCompression + JsonHelper.writer
                : savedMap.toJson("map.wbax.tmp")     SaveManager.cs:136-149
       成功 → Toolbox.MoveSafely(tmp, final)（原子替换）；失败删 tmp
```

`SavedMap.create()`（SavedMap.cs:218-331）——**runtime → persistent 的唯一转换点**：
- 20+ manager 依次 `save()`：`items/books/subspecies/families/armies/languages/religions/cultures/kingdoms/clans/alliances/wars/plots/relations(diplomacy)/cities`（SavedMap.cs:231-245）
- tiles 行程编码（同类型连续 tile 合并计数，SavedMap.cs:264-313）
- **actors**：`foreach unit: isAlive() && !asset.skip_save` → `unit.prepareForSave()` → `actors_data.Add(unit.data)`（SavedMap.cs:314-322）
- **buildings**：`state != Removed` → 同样 prepareForSave + 收集（SavedMap.cs:323-330）

`Actor.prepareForSave()`（Actor.cs）17 步：saveCoordinates/AssetID/Profession/HomeBuilding/Equipment/Lover/**City**/KingdomCiv/Culture/Clan/Subspecies/Family/Army/Language/Plot/Religion/**Traits**/finishSaving——把所有 runtime 对象引用降级为 data 里的 long id / string id，最后 `data.save()`（清空空 custom_data 容器）。

### 加载（Verified 全链）

```text
loadWorld() → loadWorld(path)                         SaveManager.cs:~460-500
  getMapFromPath: Zip.Decompress + JsonConvert.DeserializeObject<SavedMap>(read_settings)
  savedMap.check()  （null 字段补默认）                SavedMap.cs:94-216
  loadData(savedMap, path)                            SaveManager.cs:911-1083
    ├─ SaveConverter.convert(data)                    ← 版本迁移最先执行
    ├─ addClearWorld(w,h) + setMapSize + map_stats/world_laws 回填
    ├─ stats DB: loadStatsFrom / createDB + createOrMigrateTablesLoader
    ├─ saveVersion < 8 → 旧 tile 格式兼容；else loadTileArray/frozen/fire/conway
    └─ SmoothLoader 顺序管线（依赖序）：
       subspecies → families → languages → religions → items → books → cultures
       → clans → kingdoms → cities → wars → armies → alliances → plots
       → loadActors（units.loadFromSave(data.actors_data)）
       → lovers/armyCaptains/plotAuthors 引用二次连接
       → checkOldCityZones → buildings → checkSimManagerLists
       → setHomeBuildings → civs → leaders → diplomacy
       → 地图 chunk 重绘/清理 → finishMakingWorld → on_world_loaded 回调 → data = null
```

加载顺序即**引用安全序**：cities 先于 actors（`Actor.loadFromSave` 里 `World.world.cities.get(data.cityID)` 才能命中，Actor.cs:8873-8877）；kingdoms 先于 cities（loadCity 里 kingdoms.get）；lovers/leaders 等跨对象引用在两端都就绪后二次连接（loadActorLovers/loadLeaders）。

### id 分配与跨存档稳定性（Verified）

- 分配：`SystemManager.newObject()` → `World.world.map_stats.getNextId(type_id)`（"unit"/"building"/... 各自 `id_xxx++`，MapStats.cs:120-160 计数器族 + getNextId）
- `MapStats` 本身就在 SavedMap 内（`savedMap.mapStats = World.world.map_stats`，SavedMap.cs:228），**随存档往返** → 已分配 id 不会重复使用，**跨存档稳定**（加载时 `map_stats.load()` 回填计数器，SaveManager.cs:925-926）
- 旧档兼容：`loadFromSave` 中 `id == -1` 重新分配（SystemManager.cs）；SaveConverter.kingdomIDFixer 修复非法 0 id（SaveConverter.cs:39-51）

### custom_data 落盘（Verified）

三层全部走同一序列化（JSON 内嵌 map.wbox）：
1. **世界级**：`MapStats.custom_data : SaveCustomData`（MapStats.cs:20）——`World.world.map_stats.custom_data.get/set`
2. **实体级**：`ActorData/CityData/...` 继承 `BaseSystemData.custom_data_*` 五型容器（BaseSystemData.cs:17-32）
3. **DB 级**：SaveCustomData 亦为 `BaseSystemData`（SQLite ORM 属性 `[PrimaryKey] id`，可入 stats DB 表）

### Converter 层作用（Verified）

- `LongJsonConverter`（LongJsonConverter.cs:6-87）：**读侧宽容**——接受 integer / "u_123" 前缀串 / 任意字符串（GUID 8/36 长度静默映射、其余串从 100000000 起分配伪 id 并告警）；`OnDeserializing` 时 reset（SavedMap.cs:530-533）。**写侧 CanWrite=false**（原样输出 long）
- `LongListJsonConverter / NullableLongJsonConverter / NullableLongListJsonConverter` 同族（JsonHelper.cs:46-49）
- `DelegateConverter`（DelegateConverter.cs:4-38）：**单向**——WriteJson 把委托调用列表序列化为 "Type.Method" 字符串数组（调试/资产导出用），**ReadJson 恒返回 null**（存档加载后委托全部重建，见 traits.md 的 load 钩子路径）
- 这些 converter 注册在 `JsonHelper.read_settings`（读）而 `JsonHelper.writer` 仅 IgnoreAndPopulate（JsonHelper.cs:11-52）——读宽容、写标准

### 版本迁移（Verified 边界）

`SaveConverter.convert`（SaveConverter.cs:11-37）：saveVersion 15 显式拒绝；<12 convertOldAges；≤15 checkOldBuildingID + convertTo15；≤16 convertTo16；≤17 convertTo17。另有 assetIDFixer（旧资产 id 改名映射，SaveConverter.cs:53-90）、checkOldCityZones（加载管线中段调用）。**边界**：只做数据结构升级（旧格式字段搬运/重命名），不含 mod 数据迁移；mod 数据兼容由 mod 自行处理（version 字段约定见 persistent-mod-data pattern）。

### AutoSave（Verified 与主流程共享）

`AutoSaveManager.update`（AutoSaveManager.cs）：`Config.autosaves` 且窗口/控制单位空闲时触发 → `autoSave` → **`SaveManager.saveWorldToDirectory(autosaves/<epoch>, pCompress: false)`**（与手动存档同入口，仅非压缩 + epoch 目录 + checkClearSaves 清理旧档）；低内存时 OnLowMemory 强制跳过/触发。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `SaveManager.saveWorldToDirectory(path, compress, check)` | 保存主入口（UI/AutoSave/workshop 共用） | SaveManager.cs:85 |
| `SaveManager.currentWorldToSavedMap()` | runtime → SavedMap（调 create()） | SaveManager.cs:103 |
| `SavedMap.create()` | 全实体 prepareForSave 收集 | SavedMap.cs:218 |
| `SaveManager.loadData(SavedMap, path)` | 加载编排（SmoothLoader） | SaveManager.cs:911 |
| `<Manager>.loadFromSave(List<TData>)` | 各系统加载入口（SystemManager 泛型） | SystemManager.cs |
| `World.world.map_stats.getNextId(type)` | 新对象 id 分配 | MapStats.cs |
| `World.world.map_stats.custom_data` | 世界级自定义数据 | MapStats.cs:20 |
| `SaveConverter.convert(SavedMap)` | 旧档迁移 | SaveConverter.cs:11 |
| `MapBox.on_world_loaded` | 世界加载完成静态回调（mod 集成点） | MapBox.cs:247 |

## Extension Points

1. **per-actor / per-city 持久数据**：`data.get/set`（容器随 SavedMap JSON 往返，Verified）
2. **世界级数据**：`map_stats.custom_data`（Verified，reference mod 普遍使用——persistent-mod-data pattern 5 级选型）
3. **加载完成钩子**：`MapBox.on_world_loaded`（MapBox.cs:247，addLoadWorldCallbacks 注册，Verified）
4. **保存/加载介入**：Harmony postfix `SavedMap.create`（注入自定义收集）/ `SaveManager.loadData`；NML 未 patch 保存链（跨源验证：NML 全源码无 SaveManager/SavedMap patch）→ mod 数据必须挂在 SavedMap 已有可序列化字段（custom_data / stats DB 表）上
5. **stats DB**：`DBInserter`/HistoryTable（历史统计域，深挖 deferred）

## Cross-System Relationships

- **Actor**：prepareForSave 17 步 id 化（Actor.cs）；loadFromSave 恢复（见 actor.md 存档加载节——本文件为其 deferred 的关闭证据源）
- **City**：`cities.save()` 收集 CityData；loadCity 恢复 zones/culture/kingdom（见 settlement/city.md）
- **Traits**：`saved_traits : List<string>` 在 prepareForSave.saveTraits 写入、TraitTools.loadTraits 直填恢复（traits.md 已记，本文件确认往返路径为 map.wbox JSON）
- **Assets**：data.asset_id / original_actor_asset 存 string id，加载时 `AssetManager.<lib>.get(id)` 重解析；资产缺失 → 对象静默丢弃（ActorManager.loadObject null 返回，ActorManager.cs:782-798）
- **Items**（2026-09-08 补，→ economy/items.md）：三处持久化——`SavedMap.items : List<ItemData>`（ItemManager.save，alive 过滤）、`ActorData.saved_items : List<long>`（equipment 槽位 id 列表）、`CityData.equipment : CityEquipment`（分桶 id 列表）；加载序 **items 先于 cities/actors**（引用安全序）；ItemAsset 缺失 → 物品整体丢弃，ItemModAsset 缺失 → 从 data.modifiers 剔除；id 走 map_stats.id_item（SaveConverter.cs:362-375 旧档 fixup）

## Evidence

| 结论 | source | location |
|---|---|---|
| 存档目录结构与三文件 | worldbox | SaveManager.cs:19-37, 85-101, 126-184 |
| 保存主流程 + 原子替换 | worldbox | SaveManager.cs:126-184 |
| SavedMap.create 收集逻辑（含 skip_save/Removed 过滤） | worldbox | SavedMap.cs:218-331 |
| Actor.prepareForSave 17 步 | worldbox | Actor.cs（prepareForSave/saveTraits/finishSaving） |
| 加载管线与顺序 | worldbox | SaveManager.cs:911-1083 |
| id 计数器随档往返 → 跨存档稳定 | worldbox | MapStats.cs:120-160, SavedMap.cs:228, SaveManager.cs:925 |
| LongJsonConverter 宽容读/单向 Delegate | worldbox | LongJsonConverter.cs:6-87, DelegateConverter.cs:4-38, JsonHelper.cs:38-52 |
| 版本迁移阶梯与边界 | worldbox | SaveConverter.cs:11-90 |
| AutoSave 共享主入口（非压缩） | worldbox | AutoSaveManager.cs（update/autoSave） |
| stats DB 双库 + disable_db | worldbox | SaveManager.cs:247-299, 933-967 |
| 世界加载回调 | worldbox | MapBox.cs:247（on_world_loaded），SaveManager loadData 尾部 add |
| NML 不 patch 保存链 | neomodloader | NML 全源 HarmonyPatch 清单（仅 Listener/AssetPatches/TabManager/ResourcesPatch/CustomAudio） |

## Confidence

- Verified：全部机制结论（含 id 稳定性、custom_data 落盘、converter 语义、AutoSave 共享、迁移边界）
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- WorldTileData / tileArray 行程编码的位级格式（→ world 系统）
- DBTables 各历史表 schema 与 createOrMigrateTablesLoader 迁移细节（→ stats/历史域）
- `Config.WORLD_SAVE_VERSION` 当前值与 saveVersion 18+ 的具体差异（仅见 ≤17 阶梯）
- SaveConverter.convertTo15/16/17 各自搬运的具体字段清单（800 行细节，按需再查）
- Workshop 上传链路（generateWorkshopPath）与存档校验

## Related Patterns

稳定 pattern_id（完整索引：knowledge/patterns/模式索引.md）：

- `persistent-mod-data` — mod 数据 5 级选型（本系统各层级的 modding 实践）
- `actor-data-custom-state` — 实体级 custom_data 用法
- `actor-event-observation` — 死亡快照（配合 on_world_loaded 重建观察者）
- `world-tick-integration` — 加载后初始化时机
