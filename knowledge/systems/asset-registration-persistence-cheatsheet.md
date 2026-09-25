---
title: 资产注册与持久化速查
aliases:
  - Cheatsheet
---

# 资产注册与持久化速查（Cheatsheet）

单页消费层：6 类核心资产的注册与持久化结论速查。来源 = Modding Readiness Trial T1-T6 全 PASS 验证（[MODDING_READINESS_TRIAL](../../docs/MODDING_READINESS_TRIAL.md)）+ 2026-09-08 BuildingAsset targeted verification。**本页不替代 system doc**——每格只给消费级结论，机制细节/行号证据见「表 C 文档映射」。基线 worldbox-0.51.2-51d275f0168b。

通用背景（适用于全部资产类）：NML mod 注册晚于 `linkAssets` 且不重跑 → 一切 linkAssets 产物（反向索引/加权池/交叉解析）不含 mod 新资产；`AssetLibrary.add` 是 last-wins 覆盖 + `create()` 一次性钩子（重复注册防御见 pattern `safe-asset-registration`）。

## 表 A — 注册

| 资产 | 注册入口 | 仅 add 是否足够 | linkAssets 未重跑影响 | post_init 未重跑影响 | 需手动维护的 cache/list | 推荐补救路线 |
|---|---|---|---|---|---|---|
| ActorTrait | `AssetManager.traits.add(trait)` | 手动赋予：够；自然获取/遗传：不够 | 不进 pot_traits_birth/growup/mutation/combat 加权池；opposite / default_for_actor_assets 反向索引不解析 | health/mana/stamina 自动 restoreFullStats 钩子不挂；排序/autoSetRarity 不算 | 无强制；要自然获取时自填 pot_traits_*（weight>0 前提） | `actor.addTrait(trait)` 手动路线零缺失；挂效果用 action_special_effect/action_attack_target |
| BuildingAsset | `AssetManager.buildings.add(asset)` 或 `clone(newId, fromId)` | 手动放置：够；城市 AI 自动建造：不够 | atlas_asset 不链接（`checkAtlasLink` 可重跑，见下）；has_biome_tags/has_step_action 等 flag 恒 false；不进 Architecture 派生链 | 不进城市建造清单（initBuildingsFromArchitectures 只扫当时 list） | atlas_asset（补救：调 `AssetManager.buildings.checkAtlasLink(...)` 全量重链，public，BuildingLibrary.cs:91；或手动 `dynamic_sprites_library.get` 赋值） | clone 派生首选（pattern clone-modify-asset）；自放置 reflection 调 `BuildingManager.addBuilding`（internal）；城市自动建造需 CityBuildOrderAsset/Architecture 介入 |
| ResourceAsset | `AssetManager.resources.add(res)` | 存取+save/load：够；strategic 判定+UI 图标：不够 | Strategic 不进 strategic_resource_assets（hasResourcesForNewItems 门槛忽略）；give_trait/give_status/diet 交叉不解析 | order/full_sprite_path 默认值（UI 排序/图标路径） | strategic_resource_assets（strategic 资源需手动 Add） | change/set/get 存取即时生效；图标自调 `ResourceLibrary.loadSprites()` |
| CitizenJobAsset | `AssetManager.citizen_job_library.add(job)` | **不够**（影响最深的一类） | 不进 list_priority_normal/high/high_food 三张分配列表（common_job=true 也一样）→ 永不被 setCitizenJob 选中 | unit_job_default 不自动对齐同名 ActorJob（默认 null → ai.setJob 无效） | **必须**手动向对应 list_priority_* Add；unit_job_default 自设为有效 ActorJob id | add + 手动 Add 列表 + 自设 unit_job_default + 配套 `AssetManager.job_actor.add(new ActorJob{...})`（tasks 只能引用既有 Beh 资产） |
| EquipmentAsset | `AssetManager.items.add(eq)` | 手动生成+装备：够；AI 合成/池可见：不够 | 不进 equipment_by_subtypes → craftItem 选型查不到；item_modifiers 不解析；不进 pot_weapon/pot_equipment_by_groups（装备雨/transmute 不可见） | path_icon/cost_coins_resources 默认值 | equipment_by_subtypes / pot_* 池（需 AI 合成时手动补；subtype 必须复用既有字符串如 "sword"，全新字符串 craftItem 直接 dict 索引 → KeyNotFound） | `World.world.items.generateItem` + `equipment.setItem` 手动路线零缺失零池依赖 |
| Mod Custom Data | `actor.data.set` / `kingdom.data.set` / `map_stats.custom_data.set`（大结构 → 存档槽文件 / sqlite，见 pattern persistent-mod-data） | 不适用（无资产注册） | 不适用 | 不适用 | 无（热路径可镜像内存字典定期回写） | 直接读写；键带 mod 前缀；类型改动自管版本键 |

## 表 B — 持久化与恢复

| 资产/数据 | 持久化路径 | 自动？ | load 后如何恢复 | id/资产缺失时行为 |
|---|---|---|---|---|
| ActorTrait | `ActorData.saved_traits : List<string>`，随 map.wbox JSON | 自动 | TraitTools.loadTraits 直填 HashSet（**不走 addTrait**：无 opposite 检查、不触发 add 钩子），随后逐 trait 触发 action_on_augmentation_load——mod 状态重建挂此钩子 | trait id 缺失 → 该条目静默丢弃（无迁移） |
| BuildingAsset | `BuildingData`（asset_id/cityID/state/mainX/mainY + storage 资产带 saved_resources） | 自动（实例级；资产本身无持久化） | loadObject：`buildings.get(asset_id)` → setBuilding 重建占用/归属；需通过 canBuildFrom(Load) 占地校验 | 资产缺失或占地校验失败 → 整栋静默丢弃（Removed 态本来就跳过） |
| ResourceAsset | `BuildingData.resources.saved_resources`（只留非零槽） | 自动（随建筑） | loadFromSave 逐槽 `resources.get(id)` 校验重建 dict + food/other 分类缓存 | 资源 id 缺失 → 该槽静默丢弃 |
| CitizenJobAsset | **无持久化**（仅 `ActorData.profession` 枚举直存；citizen_job/City.jobs 全 runtime） | —（重载后 AI 重选） | 名额池由 CityBehCheckCitizenTasks 从环境重派生；mod 需记忆工种 → 自己写 actor.data 键 | 重选时资产缺失 → 该工种自然不出现 |
| EquipmentAsset | 三处：`SavedMap.items` + `ActorData.saved_items`（槽位 item id 列表）+ `CityData.equipment` | 自动 | 加载序 items 先于 cities/actors（引用安全序）；actor 侧按 asset.equipment_type 归槽；quality/value 每次 load 重算 | ItemAsset 缺失 → 物品整体丢弃；ItemModAsset 缺失 → 仅剔除该词缀 |
| Mod Custom Data | ActorData/KingdomData 内嵌 custom_data 五型容器；世界级 MapStats.custom_data；大结构 → 存档槽目录文件（guigu 路线）/ sqlite（actorhistory 路线） | 容器内：自动 | `data.get(key, out T, default)` 直接命中，**零恢复代码**；运行时观察者类结构用 `MapBox.on_world_loaded` 重建 | 键不存在 → 返回 default（不报错）；类型换了不迁移（旧值读不回） |

## 表 C — 文档映射

| 资产 | system doc（权威） | pattern | reference mod 样板 |
|---|---|---|---|
| ActorTrait | entity/traits.md | register-actor-trait / safe-asset-registration | incensefiredway trait.cs:25-99（52 trait）；guigu-cultivation（批量+分组） |
| BuildingAsset | settlement/buildings.md | clone-modify-asset / private-api-reflection（addBuilding 是 internal） | xuanjian-xianzu（addBuilding 用法 + DongTianBuildings.cs:199） |
| ResourceAsset | economy/resources.md | clone-modify-asset（模板路线） | xuanmen-daojie XiuXingStats.cs:267-320（仅 add 实证） |
| CitizenJobAsset | economy/jobs.md | —（无 mod 先例；21 个 reference mod 均未注册过新工种） | — |
| EquipmentAsset | economy/items.md | clone-modify-asset（材质族） | xuanjian-xianzu ZiDingYiItems.cs + FaBaoEquipmentPatches |
| Mod Custom Data | technical/save.md | actor-data-custom-state / persistent-mod-data（五级选型） | incensefiredway ActorExtensions.cs:213-230（三件套）；guigu（大规模键层）；actorhistory（sqlite） |

## BuildingAsset 最小字段 Checklist

> 2026-09-08 targeted verification（本页唯一新增源码调查；消费路径 + vanilla 4 个从零定义样本 tree_green_1/$flora_small$/$resource$/poop，BuildingLibrary.cs:190/441/602/675）。标 Required 的均有消费路径解引用证据。

### A. 推荐路线：clone 已有资产

```csharp
var t = AssetManager.buildings.clone("mymod.my_building", "human_house_0");
t.fundament = new BuildingFundament(1, 1, 1, 0); // 换新对象，勿原地改共享实例
```

- clone = 反射复制 + 完整 add；非 Cloneable 类字段是**共享引用**（fundament 等 struct/可变对象换新实例再赋值）
- 可从模板资产 clone（`$building$`/`$city_building$` 等，BuildingLibrary.cs:14-44）：dict-only 不可枚举，但 get/clone 正常

### B. 从零创建路线

**Required（源码确认，缺失即坏）**

| 字段 | 证据 | 说明 |
|---|---|---|
| `id` | AssetLibrary.add dict key | 不设默认 "ASSET_ID"（碰撞覆盖风险） |
| `fundament` | 裸字段无初始化器（BuildingAsset.cs:21）；fillTiles（Building.cs:717）/ canBuildFrom（BuildingManager.cs:141）/ checkTilesForUpgrade（Building.cs:653）无条件解引用 | **null = 放置时 NRE**。ctor(left, right, top, bottom)，width=left+right+1、height=top+bottom+1；`new BuildingFundament(0,0,0,0)` = 1×1 仅主 tile |
| `base_stats["health"]` | vanilla 4/4 从零样本全设 10f；`getMaxHealth() = (int)stats["health"]`（BaseSimObject.cs:640） | 缺省 → maxHealth 0 → setHealth Clamp 退化，血量异常脆弱 |
| `main_path` 或 `sprite_path`（二选一） | 解析规则：sprite_path 优先，否则 main_path + id（BuildingAsset.cs:686-689）；miss → `Resources.LoadAll` 空数组并缓存（SpriteTextureLoader.cs:28-41） | **稳定性 Optional / 可见性 Required**：路径无图 → 建筑隐形但不崩溃。main_path 默认 "buildings/"，mod 图走 NML 资源加载 |

**Recommended（vanilla 从零样本 100% 设置；不设不崩但行为语义错位）**

- `building_type`（enum 取默认首值；extractResources 采集分支 / Beh 目标选择依赖它）
- `kingdom`（默认 ""；nature 系设 "nature" → setKingdom 联动 kingdoms_wild）
- `group`（UI/批量分组）

**Optional（默认值安全）**

- `material`（默认 "building"）/ `atlas_id`（默认 "buildings"）——atlas_asset 由 `checkAtlasLink` 重链，public 可随时重跑（linkAssets + BuildingManager.checkWobblySetting 双入口，BuildingLibrary.cs:91-104）
- `type`（仅 editorDiagnostic 开发期警告，BuildingLibrary.cs:1940，运行时无消费）
- `has_sprite_construction`（施工态开关）/ `construction_progress_needed`（默认 0 → 立即建成）
- feature flags：`storage = true`（自动建 CityResources）/ `setHousingSlots(n)`（可居住）/ `burnable`、`destroy_on_liquid`、`has_ruins_graphics` 等（默认 false）
- linkAssets 产物 flag（has_biome_tags / has_step_action / has_get_map_icon_color）对 mod 建筑恒 false：无 biome 限制、无 step action——行为上等价"无门控"，通常无害

**Unknown（未验证，不猜）**

- `atlas_asset` 为 null 时 `DynamicSprites.getRecoloredBuilding` 是否 NRE（仅 has_kingdom_color 渲染路径触及）
- `building_sprites` 内部结构（animation_data 等）在最小配置下的行为——initAnimationData 会随机索引 animation_data.Count
- `upgrade_to`/`upgraded_from` 半配置时的升级状态一致性
- NML ResourcesPatch 对 mod 建筑 sprite 的具体加载映射（technical/assets.md 已记 Known Gap）

## 消费规则

1. 本页定位问题类型 → 表 C 跳对应 system doc 看机制与行号
2. 涉及注册防重复/热重载 → 叠加 pattern safe-asset-registration
3. 本页结论与 system doc 冲突时以 system doc 为准
