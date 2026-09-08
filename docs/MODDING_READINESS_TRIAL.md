# Modding Readiness Trial — Phase 1

- 基线：WBKB v0.17.0（worldbox-0.51.2-51d275f0168b + neomodloader-02266fe8185d）
- 日期：2026-09-08
- 方法：模拟 coding agent 视角,严格按固定消费顺序(知识库索引 → 源代码索引 → system doc → pattern → reference mod → wbkb targeted verification),禁止从源码扫描开始
- 结论先行:**6/6 PASS,0 PARTIAL,0 FAIL**。全部 6 个 scenario 的答案均可由现有知识库直接给出,wbkb 仅用于签名级 confirmation,无大范围源码阅读。

---

## T1 — 注册 ActorTrait 并手动添加到 Actor

### Result
**PASS**

### Knowledge Used
- system: entity/traits.md(add/remove/has 全流程 + 注册时序 caveat)、technical/assets.md(add last-wins + create 钩子)
- pattern: register-actor-trait(Minimal Example 即答案)、safe-asset-registration
- reference mod: incensefiredway code/trait.cs:25-99(52 trait 统一注册样板)、guigu-cultivation(批量 + trait_groups)

### Required APIs
- `new ActorTrait { id = "mod.trait_x", path_icon = "...", base_stats = new BaseStats{...} }`
- `AssetManager.traits.add(trait)`(含 checkDefault:rate_inherit 默认补全)
- `actor.addTrait(trait)` / `actor.addTrait(id)`(两个重载均验证:Actor.cs:9189/9199)
- 可选行为钩子:`action_special_effect`(周期)/`action_attack_target`/`action_on_augmentation_add/remove/load`

### Minimal Implementation Plan
1. OnModLoad 中构造 ActorTrait(mod 前缀 id)
2. `AssetManager.traits.add(trait)`;需分组时同步注册 ActorTraitGroupAsset
3. 手动赋予:`actor.addTrait(trait)`(即时生效:setStatsDirty + clearTraitCache)
4. 需要效果时挂委托(action_special_effect + special_effect_interval)

### Initialization Constraints
- mod 注册晚于 linkAssets → 不进 pot_traits_birth/growup 自然池、opposite/default_for_actor_assets 反向索引不更新(**手动 addTrait 不受影响**)
- affects_mind + strong_mind 标签会被拒绝;opposite trait 冲突拒绝(pRemoveOpposites=false 时)

### Persistence
- 自动:`ActorData.saved_traits` 随 map.wbox 往返;load 侧 TraitTools.loadTraits 直填(不走 addTrait,不触发 add 钩子,触发 load 钩子)
- 要求:读档时 trait id 必须已注册,否则该条目静默丢弃

### Source Verification
- `search addTrait`:确认 `Actor.addTrait(ActorTrait,bool)` / `addTrait(string,bool)` 双重载存在(1 次 search)

### Retrieval Cost
- 0 次 show/refs/symbol 专用于本任务;1 次 search;无源码阅读;约 3 分钟

### Gap
- 无。traits.md 是知识库中覆盖最完整的 system doc 之一,modding caveat(池不更新)预先写明

---

## T2 — 注册 BuildingAsset 最小可用流程

### Result
**PASS**

### Knowledge Used
- system: settlement/buildings.md(创建链/资产注册三阶段/save-load)、technical/assets.md(clone 反射复制 + 共享引用 caveat)
- pattern: clone-modify-asset(派生原版建筑是主用例)、private-api-reflection
- reference mod: xuanjian-xianzu(`World.world.buildings.addBuilding` 实际用法 + DongTianBuildings.cs:199)

### Required APIs
- `AssetManager.buildings.add(new BuildingAsset { id, fundament, building_type, ... })`(174 字段,关键:fundament 占地/building_type/sprite 路径/city_building/kingdom)
- 派生路线(推荐):`AssetManager.buildings.clone(newId, fromId)` + 逐字段覆写
- 生成实例:`World.world.buildings.addBuilding(asset, tile, ...)` — **internal**,mod 需 reflection 或 Harmony(private-api-reflection)
- 关联:`CityBuildOrderAsset`/Architecture(城市 AI 自动建造,post_init 派生不重跑)

### Minimal Implementation Plan
1. `clone(newId, "human_house")` 派生(避开 174 字段全配置)
2. 覆写必要字段(fundament/sprite/name)
3. `AssetManager.buildings.add(...)`(clone 内置 add)
4. 实例化走 reflection 调 `BuildingManager.addBuilding` 或 patch 其 caller

### Initialization Constraints
- linkAssets/post_init 不重跑:不进 Architecture 派生链与城市 AI 建造清单 → 城市**不会自动建**它,需 mod 自行放置或 Harmony 介入 CityBehBuild(后者 deferred: behaviour)
- 注意 clone 共享引用 caveat:非 Cloneable 类字段是共享引用,改嵌套可变对象会影响原资产

### Persistence
- 自动:BuildingData.asset_id 往返;**资产 id 缺失 → 建筑整体静默丢弃**(loadObject 返回 null)

### Source Verification
- `symbol BuildingAsset`(174 字段确认)、`search addBuilding`、`show BuildingManager.cs:77`(确认 internal 修饰符)— 3 次,全部与 docs 记载一致

### Retrieval Cost
- 1 symbol + 1 search + 1 show;无源码阅读;约 5 分钟

### Gap
- **B(知识缺失,轻微)**:全新 BuildingAsset(非 clone)的最小字段清单(哪些字段不设会 NRE/渲染失败)没有 checklist 形态的文档;clone 路线可完全绕开,故不阻塞
- `initBuildingsFromArchitectures` 派生映射规则是已知 Known Gap(buildings.md 已记录)

---

## T3 — 注册 ResourceAsset + Building/City storage + save/load

### Result
**PASS**

### Knowledge Used
- system: economy/resources.md(Extension Point 第 1 条就是本任务完整答案)、settlement/buildings.md(storage 资产 → CityResources 自动创建)、technical/save.md
- reference mod: xuanmen-daojie XiuXingStats.cs:267-320(仅 add 的实证用法)

### Required APIs
- `AssetManager.resources.add(new ResourceAsset { id, type = ResType.X, storage_max, maximum, path_icon, ... })`
- 存入:`city.addResourcesToRandomStockpile(id, n)` / `building.addResources(id, n)`(→ CityResources.change,钳制于 maximum)
- 读取:`city.getResourcesAmount(id)` / `building.data.resources.get(id)`
- 容量语义:`storage_max` = 每栋 storage Building 单资源容量(hasSpaceForResource);`maximum` = change 钳制上限
- storage 前提:目标建筑资产 `BuildingAsset.storage = true` → setBuilding 自动建 data.resources

### Minimal Implementation Plan
1. 注册 ResourceAsset(设 type/storage_max/maximum;food 类注意 _list_food 分类缓存自动生效)
2. 向既有 storage 建筑(或 clone 一个 storage=true 的新建筑)`addResources` 即完成存取
3. mod 自调 `ResourceLibrary.loadSprites()`(post_init 不重跑,full_sprite_path 为默认)

### Initialization Constraints
- linkAssets 不重跑 → Strategic 类型不进 strategic_resource_assets(hasResourcesForNewItems 门槛忽略它)、give_trait/give_status/diet 交叉解析缺失——不依赖则无影响
- 存取 API(change/set/get/addNew)全部即时生效,无三阶段依赖

### Persistence
- 自动:非零槽随 BuildingData.saved_resources 往返;**ResourceAsset id 缺失 → 该槽静默跳过**
- City 层无持久化(纯实时聚合 storages)

### Source Verification
- `symbol ResourceAsset`(确认 storage_max/maximum/type/food 字段)— 1 次

### Retrieval Cost
- 1 symbol;无源码阅读;约 3 分钟

### Gap
- 无。resources.md 的 Extension Points 一节几乎逐条对应该任务的三问

---

## T4 — 注册 CitizenJob(为何 add 不够 / priority list / unit_job_default)

### Result
**PASS**(注册与三问全部有答案;新任务类型编排止于 behaviour 边界,符合任务声明"不需要解决 Behaviour engine 内部")

### Knowledge Used
- system: economy/jobs.md(Extension Point 第 1 条逐字回答三问)、technical/assets.md(三阶段不重跑机制)
- 无需 reference mod(无现成 mod 注册过新工种——这本身也是知识:21 个 reference mod 均未触及,佐证这是高难度操作)

### Required APIs
- `AssetManager.citizen_job_library.add(new CitizenJobAsset { id, priority, priority_no_food, common_job = true, unit_job_default = "...", should_be_assigned = ... })`
- 三张分配列表:`AssetManager.citizen_job_library.list_priority_normal / list_priority_high / list_priority_high_food`(linkAssets 产物)
- 配套:`AssetManager.job_actor.add(new ActorJob { id, tasks = ... })`
- 验证字段:`CitizenJobAsset` 十字段(priority/priority_no_food/common_job/ok_for_king/only_leaders/should_be_assigned/unit_job_default...)

### Minimal Implementation Plan(三问答案)
1. **为何 add 不够**:linkAssets 不重跑 → 新工种不进三张优先级列表(common_job=true 是进列表前提)→ `City.setCitizenJob` 的 checkCitizenJobList 永远扫不到 → 永不被分配
2. **进入 priority list**:手动向 `list_priority_normal`(或按 priority>0 → high)Add 该资产;名额由 CityBehCheckCitizenTasks 按环境派生,自定义名额需 patch 该 Beh 或 addToJob 逻辑
3. **unit_job_default**:默认 null → `ai.setJob(null)` 无效;原版由 post_init 对 common_job 工种做 `unit_job_default = id` 同名对齐,mod 必须自设为有效 ActorJob id(可指向既有 "unit_citizen" 或自建 ActorJob)
4. 自建 ActorJob 的 tasks 引用 BehaviourTaskActorLibrary 既有 task 资产(如 chop_trees);**全新 Beh task 注册 → deferred: behaviour**

### Initialization Constraints
- 受 linkAssets 影响最深的资产类型(三张列表全部 linkAssets 产物)
- City.jobs 名额池 runtime-only,load 后由 AI 重选——无需 mod 持久化

### Persistence
- 无需 custom_data:仅 `ActorData.profession` 枚举持久化,citizen_job 天然不持久化(重载后重选,名额池重建)

### Source Verification
- `symbol CitizenJobAsset`(十字段与 jobs.md 记载完全一致)— 1 次

### Retrieval Cost
- 1 symbol;无源码阅读;约 4 分钟

### Gap
- **D(依赖未 Harvest 系统,已声明边界)**:全新 Beh task 类型需 behaviour 域知识;jobs.md 已显式记录该边界而非留空,消费时无歧义

---

## T5 — 注册 EquipmentAsset + Item 实例 + 装备 + AI crafting cache

### Result
**PASS**

### Knowledge Used
- system: economy/items.md(Extension Point 第 1 条覆盖全部三问 + KeyNotFound caveat)、entity/traits.md(共享 BaseAugmentationAsset 框架)
- pattern: clone-modify-asset(材质族装备路线)
- reference mod: xuanjian-xianzu ZiDingYiItems.cs(法宝 item 注册)+ FaBaoEquipmentPatches(ActorEquipmentSlot.setItem patch)

### Required APIs
- 注册:`AssetManager.items.add(new EquipmentAsset { id, equipment_type, base_stats, ... })`(add 自动补 base_stats)
- 创建实例(唯一正式入口):`World.world.items.generateItem(asset, kingdom, who, tries, actor, ...)`(签名验证:ItemManager.cs:159)
- 装备:`actor.equipment.setItem(item, actor)` / `actor.equipment.getSlot(EquipmentType.X).setItem`(验证:ActorEquipment.cs:113)
- 前置:`actor.canUseItems()`(asset.use_items 门控)

### Minimal Implementation Plan
1. 注册 EquipmentAsset(equipment_type 六值之一;subtype 复用既有字符串如 "sword")
2. `generateItem` 创建带词缀/身份/耐久的 Item 实例
3. `equipment.setItem(item, actor)` 即时装备(内置 setStatsDirty → updateStats 自动合并装备段)
4. AI crafting cache 限制:见下

### Initialization Constraints(AI crafting cache 限制,三问核心)
- linkAssets 不重跑 → **不进 `equipment_by_subtypes`** → `ItemCrafting.craftItem` 选型查不到 → **永不被 AI 合成**
- 使用全新 subtype 字符串更糟:craftItem 直接 dict 索引 → **KeyNotFoundException**(Inferred,jobs/items 文档标注)→ 必须复用既有 subtype
- 不进 pot_weapon/pot_equipment 池 → 装备雨/transmute/解锁池不可见;`needs_to_be_explored=true` 默认 → isAvailable false(但 craftItem 不检查 isAvailable,合成侧不受此限——本任务手动路线完全绕开)
- **手动 generateItem + setItem 路线完全无阻**:不经池/选型,stats merge 正常消费

### Persistence
- 自动三处:SavedMap.items + ActorData.saved_items(槽位 id 列表)+ CityData.equipment;ItemAsset 缺失 → 物品静默丢弃;quality/value 每次 load 重算(不持久化)

### Source Verification
- `search generateItem` + `search setItem`(签名确认)— 2 次

### Retrieval Cost
- 1 次组合 search(2 query);无源码阅读;约 4 分钟

### Gap
- 无阻塞。crafting 的 culture 偏好内部(getPreferredWeaponSubtypeIDs)是 deferred: culture,但已被记录为边界且不影响本任务

---

## T6 — Actor/Kingdom 自定义数据持久化

### Result
**PASS**

### Knowledge Used
- pattern: actor-data-custom-state(Get/Set/Change 三件套 Minimal Example)、persistent-mod-data(五级选型表)
- system: technical/save.md(custom_data 三层落盘 + BaseSystemData 五型容器)、political/kingdom.md(kingdom.data.get/set 互证)
- reference mod: incensefiredway ActorExtensions.cs:213-230、guigu CultivationData.cs(大规模键管理)、xuanmen-daojie(世界级 custom_data + life_dna 指纹)

### Required APIs
- `actor.data.set(key, value)` / `actor.data.get(key, out T, default)` — 五型重载(int/long/float/string/bool,BaseSystemData 验证)
- `kingdom.data.get/set`(同一 BaseSystemData 容器,KingdomData 内嵌)
- 世界级备选:`World.world.map_stats.custom_data.get/set`
- 加载恢复钩子:`MapBox.on_world_loaded`(世界级重建观察者用)

### Minimal Implementation Plan
1. 定义 mod 前缀键常量(`"mymod.xiu_wei"`)
2. 写扩展方法三件套 Get/Set/Change(照抄 actor-data-custom-state Minimal Example)
3. Kingdom 同构:`kingdom.data.set("mymod.k", v)`

### Initialization Constraints
- 无:custom_data 容器随实体数据天然存在,读写无时序依赖(存活期内任意时刻)

### Persistence(load 后恢复,任务核心)
- **自动**:custom_data 五型容器内嵌 ActorData/KingdomData JSON,随 map.wbox 往返;load 后 `actor.data.get` 直接命中,无需任何恢复代码
- 注意:类型不可换(float→string 旧档不迁移,需版本键兜底);空容器在 data.save() 时被清空(无数据的键不占体积)

### Source Verification
- `symbol BaseSystemData`(五型 get/set/change/remove 全家福确认)— 1 次

### Retrieval Cost
- 1 symbol;无源码阅读;约 3 分钟

### Gap
- 无。此任务是知识库最强项:2 个 pattern + 2 个 system doc + 5 个 reference mod 多重互证

---

## 汇总

### 结果统计
- **PASS: 6 / PARTIAL: 0 / FAIL: 0**

### 无需源码重查的任务
**全部 6 个**。每个 scenario 的实现路径、caveat、持久化语义均由 system doc / pattern 直接给出;wbkb 仅做签名确认(合计 4 symbol + 4 search + 1 show + 1 stats ≈ 10 次查询,零大范围源码阅读,全程约 25 分钟)。

### 仍需 targeted investigation 的任务
- 无(在"最小注册"口径下)。扩展口径下的残留点:
  - T2:全新(非 clone)BuildingAsset 最小字段清单;Architecture 派生规则
  - T4:全新 Beh task 类型注册(behaviour 域)
  - T5:culture 武器偏好内部(culture 域)
  - 以上均已作为 Known Gap/deferred 边界记录在案,非本阶段任务

### Knowledge Gap
- **B(轻微,仅 T2)**:全新 BuildingAsset 最小可用字段 checklist 缺失(有 clone 路线替代,不阻塞)
- 其余任务无 Knowledge Gap;D 类边界(behaviour/culture)全部是**预先声明的 deferred**,而非调查后发现的漏洞——知识库的边界诚实度经受住了测试

### Retrieval Gap
- 知识导航(索引 → system doc → pattern)路径全部直达,无迷路
- 工具层两个小问题:
  1. `wbkb stats` 在 Windows cp1252 控制台因 Unicode 箭头字符崩溃(需 `PYTHONIOENCODING=utf-8`;纯 cosmetic,不影响查询)
  2. wbkb 无 markdown 文档全文检索(设计如此——知识树靠索引导航),若未来知识量增长,跨 doc 关键词查找会退化;当前规模下无碍
- pattern 与 system doc 的互链(Related Patterns / cross-references)工作良好,无断链

### Documentation Gap
- 无系统性缺口。可能的增强(非必须):把 6 类资产注册的 "add 是否足够 + linkAssets 缺失影响 + 持久化行为" 汇总为一张横向对照表(信息已散布在各 system doc 的 Extension Points,集中化可进一步降低消费成本)

### 最大 Blocker
**没有真正阻塞项。** 最接近 blocker 的是 T2 全新建筑字段清单(B 类轻微),但有 clone-modify-asset 替代路线。

### 结论
现有 WBKB 已达到"让 coding agent 快速准确解决 WorldBox Modding 注册类问题"的实用状态:S-Tier 知识的 Extension Points 节对该类问题的命中率是 6/6,且 caveat(linkAssets 不重跑/静默丢弃语义/internal 修饰符)预先写明,避免了 agent 最容易踩的坑。
