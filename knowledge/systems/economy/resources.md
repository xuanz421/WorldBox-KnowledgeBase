# System: Resources / Storage

WorldBox 资源系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读 + reference mod 用法交叉验证。本文件关闭 buildings.md / city.md / save.md 的 Resources 边界 Known Gap（见回写记录）。

## Scope

覆盖：ResourceAsset 定义与注册（三阶段）、amount 的真实存放位置、CityResources/CityStorageSlot 职责、maximum 与 storage_max 语义、change/set/get/hasSpaceForResource、slot 创建与初始化、storage 失效处理、save/load、food/other 分类、strategic_resource_assets、生产/消耗/搬运的 API 级调用边界。

不覆盖：Beh* 节点决策逻辑（→ behaviour）、CitizenJob 调度（→ jobs）、ItemCrafting 配方经济（→ items）、DropAsset 掉落表设计（仅入口级）、贸易（trade_* 字段语义在资产上，流转 → boats/trade 域）、supply_* 字段用途（city 供给循环 → jobs 域）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `ResourceAsset` | 资源定义（45 字段：type/maximum/storage_max/食物恢复系/贸易系/给 trait-status 系） | ResourceAsset.cs:4-137 |
| `ResourceLibrary : AssetLibrary<ResourceAsset>` | 资源库（代码定义 + 模板 clone + 分类缓存） | ResourceLibrary.cs:4-770 |
| `CityResources` | **建筑级**资源容器（dict + food/other 缓存 + saved_resources） | CityResources.cs:4-208 |
| `CityStorageSlot` | 资源槽（id + amount；asset 惰性取） | CityStorageSlot.cs:4-23 |
| `ResType` | 枚举：Currency / Strategic / Ingredient / Ingredient_Food / Food | ResType.cs:1-8 |
| `ActorBag` + `ResourceContainer` | Actor 携带层（dict<string, ResourceContainer> struct） | ActorBag.cs:5-13 |
| `DropManager` / `Drop` | 世界掉落物（视觉 + action_landed；与资源 id 共享 namespace） | DropManager.cs:4-157 |

## Data Model

**（本系统无独立 runtime manager——定义在 Asset 层，状态分散在 Building/Actor 两级）**

```text
definition:  ResourceAsset (AssetManager.resources, 代码定义 + 模板)
                        │ id
             ┌──────────┴──────────┐
             ▼                     ▼
persistent:  Building.data.resources    Actor.inventory (ActorBag)
             : CityResources            : dict<string, ResourceContainer>
             （storage 资产建筑才有）      （搬运/携带，随 ActorData.inventory 持久化）
             │ _resources : Dict<string, CityStorageSlot>   ← amount 真实存放处
             │ saved_resources : List<CityStorageSlot>       ← 序列化载体
             ▼
aggregation: City.storages/stockpiles → City.getResourcesAmount/takeResource
             （纯运行时聚合，无持久化）
```

- **amount 存在 CityStorageSlot.amount**（int），物理上位于**每个 storage Building 的 data.resources** 中——City **没有统一 resource store**
- `ActorBag.dict` 是搬运中间层（`ResourceContainer` struct：id+amount，ActorBag.cs:5-13；`ActorData.inventory` 持久化，见 actor.md）
- City 聚合视图（getResourcesAmount 等）每次实时遍历 storages，不缓存总量（`_storage_version` 计数器仅供 UI 刷新判定，City.cs）

**capacity 语义（Verified，重要）**：
- `ResourceAsset.storage_max`：**每栋 storage Building 的单资源容量**（`hasSpaceForResource` 判定 `get(id) < storage_max`，CityResources.cs:70-77）——food 类典型值 100
- `ResourceAsset.maximum`：`change()` 的**钳制上限**（`value.asset.maximum`，CityResources.cs:53-55）——food/经济类典型 999；**两者都在 ResourceAsset 上**，与 Building/City 无关（上一批结论修正：`hasSpaceForResource` 用的是 `storage_max` 而非 `maximum`——buildings.md 原表述不精确，已回写）
- 原版大量资源**未显式设置**这两个字段（默认 0）：`storage_max=0` 意味着 `hasSpaceForResource` 恒 false（不能存入该建筑）但 `change()` 仍可直接设置（钳制上限 0 会立即清零——见 Known Gaps 边界讨论）；实际写入路径依赖调用方先有 slot

## Lifecycle / Flow

### 注册与初始化（Verified 三阶段，与 technical/assets.md 互证）

```text
AssetManager.initLibs → add(resources = new ResourceLibrary(), "resources")
  → ResourceLibrary.init()：initTemplates → initOther(gold) → initStrategic
    → initFoodIngredients → initFood → initFoodRecipes
    （全部代码定义；模板 $TEMPLATE_FOOD$ / $TEMPLATE_STRATEGIC_MINERAL$ 先行，
      具体资源多为 clone(新id, 模板id) + 逐字段覆写 t.*；AssetLibrary.add 含
      create() 钩子 + dict/list 双注册，模板 $ 前缀不进 list）
→ post_init：按 list 顺序赋 order（UI 排序）+ full_sprite_path
→ linkAssets（**modding 关键**）：
   ├─ type == Strategic → strategic_resource_assets.Add   ResourceLibrary.cs:~695
   ├─ give_trait_id → AssetManager.traits.get 解析
   ├─ give_status_id → AssetManager.status.get 解析
   └─ diet × subspecies_traits 交叉标记（is_diet_related）
→ loadSprites（独立入口，运行期按 full_sprite_path 惰性加载）
```

### 存取 API（Verified）

```text
CityResources.get(id)          dict 命中 → slot.amount；miss → 0
CityResources.change(id, n)    命中 → slot.amount += n → 超过 asset.maximum 钳制
                               miss → addNew(id, n)（新建 CityStorageSlot + putToDict）
CityResources.set(id, n)       命中直接覆写；miss addNew（无钳制）
CityResources.hasSpace(res)    get(res.id) < res.storage_max
putToDict(slot)                dict + asset.food ? _list_food : _list_other 双分类缓存
```

**slot 创建时机**：首次 `change`/`set`（addNew）或 `loadFromSave` 重建——**无预分配**，只存出现过的资源。

### 生产 / 消耗 / 搬运边界（Verified，API 级）

```text
产出（deposit）:
  BehThrowResources.execute                      BehThrowResources.cs:~40-55
    pActor.takeFromInventory(key,1) → beh_building_target.addResources(key,1)
    （Actor 从 inventory 转入 Building.data.resources）
  AutoCivilization / BuildingBiomeFoodProducer（90s 定时, <10 补 1）
    → city.addResourcesToRandomStockpile(id, n) → getRandomStockpile().addResources
  City.addResourcesToRandomStockpile             City.cs:2883-2892
    随机 stockpile → Building.addResources → CityResources.change

提取（withdrawal）:
  BehExtractResourcesFromBuilding → building.extractResources(actor)   Building.cs
    （按 building_type 分支：作物类摧毁/树砍伐/矿物移除/果树 component 重置）
    + asset.resources_given → pActor.addToInventory（进入 ActorBag）
  BehCityActorGetResourceFromStorage → pActor.addToInventory  （从 storage 取）

消耗（consumption）:
  City.takeResource(id, n)                       City.cs
    遍历 usable storages 逐栋 takeResource 直至凑满（**跨建筑凑单**）
    → Building.takeResource → CityResources.change(id, -n)
  BehTryToEatCityFood.eatFood → city.eatFoodItem(id) → takeResource(id,1)
    + data.total_food_consumed++                 City.cs:1934-1941
    + actor.consumeFoodResource（恢复 nutrition/happiness 等 + favorite_food 概率更新）
  ItemCrafting → pCity.takeResource(cost_id, cost) （合成扣料，→ items 系统）
```

上层调度（谁决定 Beh 执行）→ deferred: behaviour / jobs。

### storage 失效（Verified）

- `BuildingData.Dispose`：`resources?.Dispose()`（清 dict/list 缓存）+ 置 null（BuildingData.cs）——**资源随建筑数据对象丢弃，无转移**；City 聚合自动少一栋（storages 重建排除非 usable）
- City 侧每次聚合都过滤 `storage.isUsable()`（City.takeResource/getResourcesAmount）

### Save / Load（Verified，关闭 save.md 边界项）

```text
保存: Building.prepareForSave → resources.save()          Building.cs:845-858
      （只留 amount != 0 的槽 → saved_resources）          CityResources.cs save()
加载: BuildingManager.loadObject → building.loadBuilding
      → resources.loadFromSave()                           CityResources.cs:18-32
        saved_resources 逐槽:
          AssetManager.resources.get(id) != null 且 amount >= 0 才重建
          （slot.create(id) 重挂 asset 引用 + putToDict 进分类缓存）
          → **id 缺失时静默跳过该槽（数据丢弃，无迁移）**
```

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `AssetManager.resources.get(id)` / `.add(asset)` | 定义查询/注册 | AssetLibrary.cs |
| `AssetManager.resources.strategic_resource_assets` | strategic 分类列表（linkAssets 产物） | ResourceLibrary.cs:75 |
| `city.getResourcesAmount(id)` | 跨 storages 聚合量 | City.cs |
| `city.takeResource(id, n)` / `addResourcesToRandomStockpile(id, n)` | 跨建筑取/随机库存存 | City.cs |
| `building.addResources/takeResource/getResourcesAmount` | 单建筑级存取 | Building.cs:1517-1530 |
| `building.resources.hasSpaceForResource(asset)` | 容量判定（storage_max） | CityResources.cs:70 |
| `actor.addToInventory/takeFromInventory` | 携带层 | Actor.cs:7366-7382 |
| `city.getTotalResourceSlots(resTypes)` | UI 聚合视图（含 _storage_version） | City.cs:2963-2999 |

## Extension Points

1. **注册新资源**（modding 核心问题，Verified）：
   - **必须**：`AssetManager.resources.add(new ResourceAsset{ id, type, path_icon, ... })`（标准 AssetLibrary.add）
   - **仅 add 不足，还受影响**：
     a. `linkAssets` 不重跑 → **type == Strategic 的新资源不进 strategic_resource_assets**（hasResourcesForNewItems 判定忽略它）；give_trait/give_status/diet 交叉解析同样缺失
     b. `post_init` 不重跑 → order/full_sprite_path 为默认值（UI 排序/贴图路径）
     c. `loadSprites` 按需调用 `ResourceLibrary.loadSprites()` 可补（mod 应自调）
   - **可正常工作**：dict/list 注册即时生效；change/set/get 存取无依赖；saved_resources 往返正常（loadFromSave 只做 get(id) 校验）
   - reference mod 实证（xuanmen 派系修仙 mod）：`((AssetLibrary<ResourceAsset>)AssetManager.resources).add(new ResourceAsset{ id, type=(ResType)1, ... })`——即仅 add，接受 linkAssets 缺失（其资源不依赖 strategic 判定）
2. **修改数量**：`city.addResourcesToRandomStockpile` / `city.takeResource`（保持聚合语义）；直接 `building.data.resources.change` 绕过 UI 刷新
3. **容量扩展**：改 ResourceAsset.storage_max/maximum（per-resource，全局生效——无法 per-building 定制容量，除非 clone 新 ResourceAsset）
4. **新存储建筑**：BuildingAsset.storage = true → setBuilding 自动建 CityResources（见 buildings.md）
5. **携带层操作**：actor.addToInventory/takeFromInventory（配合 city 两侧 API 完成搬运闭环）

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| Buildings | data.resources（storage 资产）；addResources/takeResource/extractResources；失效随 Dispose | 已覆盖（settlement/buildings.md） |
| City | storages 聚合 API + _storage_version；无统一 store | 已覆盖（settlement/city.md） |
| Actor | ActorBag 携带 + consumeFoodResource（食物效果）；BehThrowResources 转运 | 已覆盖 API 级 |
| Jobs | BehCityActorGetResourceFromStorage 等 Beh 由 job 调度（woodcutter/gatherer/farmer/builder 驱动链已闭环，见 2026-09-07 更新注） | 已覆盖（economy/jobs.md） |
| Behaviour | Beh* execute 是所有搬运的驱动源 | deferred: behaviour |
| Items | ItemCrafting cost_resource 扣料 + EquipmentAsset 经济字段 | 已覆盖（economy/items.md，2026-09-08 回写：合成材料全为 ResourceAsset（wood/stone/common_metals/silver/mythril/adamantine/gems/bones/leather）；Item 与 Resource 无转换/无 salvage；`hasResourcesForNewItems`（strategic>10 硬编码）是 make_items decision 门槛；ItemAsset.minimum_city_storage_resource_1 为 write-only 死字段，实际门槛非它） |
| Subspecies | diet/getAllowedFoodByDiet 过滤食物（linkAssets 交叉） | deferred: culture/subspecies 域 |
| Assets | ResourceLibrary 三阶段（strategic/give_trait 在 linkAssets） | 已覆盖（technical/assets.md） |
| Save | saved_resources 往返（零值不存/缺失丢弃） | 已覆盖（technical/save.md） |

## Evidence

| 结论 | source | location |
|---|---|---|
| ResourceAsset 字段（maximum/storage_max 并存） | worldbox | ResourceAsset.cs:4-137 字段清单 |
| 注册三阶段 + strategic/traits/status/diet 在 linkAssets | worldbox | ResourceLibrary.cs init/post_init:673-682/linkAssets:~690-720 |
| 模板 + clone 定义模式 | worldbox | ResourceLibrary.cs initTemplates:93-110, initFood 系 |
| amount 存放（Building.data.resources dict slot） | worldbox | CityResources.cs:8-16, 43-60; Building.cs:264-267 |
| capacity 语义（storage_max=每建筑容量, maximum=change 钳制） | worldbox | CityResources.cs:53-55, 70-77; ResourceLibrary 数值样本 |
| slot 创建（addNew/loadFromSave，无预分配） | worldbox | CityResources.cs:62-68, 18-32 |
| food/other 分类缓存 | worldbox | CityResources.cs:103-117 putToDict |
| deposit/withdrawal/consumption 调用链 | worldbox | BehThrowResources.cs:40-55; City.cs:2883-2892, takeResource, 1934-1941; Building.cs:1517-1530; BehExtractResourcesFromBuilding.cs |
| extractResources 按建筑类型分支 | worldbox | Building.cs extractResources |
| storage 失效（Dispose 丢弃，无转移） | worldbox | BuildingData.cs Dispose |
| save/load（非零才存/缺失静默跳过） | worldbox | CityResources.cs save/loadFromSave:18-32 |
| City 聚合实时遍历 + _storage_version | worldbox | City.cs getResourcesAmount/takeResource/getStorageVersion |
| mod 注册实际用法（仅 add） | ref mod（用法验证） | xuanmen 派系 XiuXingStats.cs:267-320 |

## Confidence

- Verified：全部机制结论；mod 用法项标注为 reference mod 证据（仅验证用法，不定义本体）
- Inferred：`storage_max=0` 的完整行为链（由代码路径推出：hasSpace false + change 钳 0 → 实际不可存；原版数据未见显式依赖此状态）
- Unknown：见 Known Gaps

## Known Gaps

- `supply_bound_give/supply_bound_take/supply_give`（城邦供给循环）与 `trade_*`（贸易数值）的实际消费位置——deferred: boats-trade 域（**jobs 侧已确认非消费方**，2026-09-07 jobs 调查未见引用）
- `mine_rate/drop_per_mass/produce_min` 的产出数值计算（矿/植被再生循环）
- ~~`ingredients/ingredients_amount` 与 ItemCrafting 的完整经济（→ items）~~ **已关闭（2026-09-08，→ economy/items.md）**：ItemCrafting **不消费 ingredients**——合成成本是 EquipmentAsset 自身的 `cost_gold + cost_resource_id_1/2 + cost_resource_1/2` 字段（无 recipe asset）；扣费走 `actor.spendMoney` + `pCity.takeResource`×2。ingredients/ingredients_amount 属 ResourceLibrary 食物配方链（initFoodRecipes），与 item crafting 无关——其消费位置仍 Unknown
- DropAsset 掉落 → Actor 拾取入口（未见直接 pickup API；Beh 侧拾取行为 → behaviour）
- `getRandomSuitableFood` 的 diet 交集算法细节（subspecies.getAllowedFoodByDiet 内部）
- NML ResourcesPatch 对 mod 资源 JSON 的加载映射（→ NML 深挖）

> 更新（2026-09-07，→ economy/jobs.md）：搬运的 job 侧驱动已闭环——woodcutter/gatherer/farmer 工种 → ActorJob task（chop_trees/collect_*）→ extractResources/addToInventory；builder → BehBuildTarget → updateBuild。仅 Beh 节点内部仍 deferred: behaviour。

> 更新（2026-09-08，→ economy/items.md）：crafting 扣料链已闭环——ItemCrafting.craftItem → pCity.takeResource(cost_resource_id_1/2)（本文件 110 行预估的调用链确认无误）；Item 不进 CityResources（城市侧装备存于 CityData.equipment : CityEquipment，与资源存储完全分离）。

## Related Patterns

稳定 pattern_id（完整索引：knowledge/patterns/模式索引.md）：

- `persistent-mod-data` — 资源量持久化随 BuildingData（本系统 saved_resources 的 modding 语境）
- `clone-modify-asset` — 资源模板 clone 路线（原版 initFood 同模式）
- `safe-asset-registration` — last-wins 防御
- `register-custom-stat` — 平行的 BaseStatAsset 注册（linkAssets 缺失 caveat 同构）
