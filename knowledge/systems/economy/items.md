# System: Items / Equipment

WorldBox 物品/装备系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。本文件关闭 resources.md 的 ItemCrafting 边界 Known Gap、actor.md 的 saved_items/equipment 语义、save.md 的 items 加载序确认（见回写记录）。

## Scope

覆盖：ItemAsset/EquipmentAsset/ItemModAsset 三层资产模型、Item 运行时实例与 ItemData 持久化、ItemManager 池化管理、ActorEquipment 六槽模型、CityEquipment 城市装备库、Item 生命周期（创建/装备/词缀/耐久/死亡/销毁）、ItemCrafting 合成链、stats 集成（updateStats 合并顺序 + attack actions + spells）、save/load 全链、modding 注册要求。

不覆盖：Combat 系统内部（s_action_attack_target 消费侧 → combat）、Decision/NeuroLayer 调度机制（仅记录 decision id 与 launch 条件——deferred: behaviour）、ItemWindow/EquipmentEditor UI 内部、NameGenerator 内部、GameProgress unlock 存储细节、CultureTrait getPreferredWeaponSubtypeIDs 内部（→ culture）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `ItemAsset` | 物品系资产**基类**（cost/equipment_type/quality/durability/mod_type 等全部字段在此层） | ItemAsset.cs:10-307 |
| `EquipmentAsset : ItemAsset` | **唯一被实例化的物品定义**（装备/武器/攻击模板；IHandRenderer） | EquipmentAsset.cs:6 |
| `ItemModAsset : ItemAsset` | 词缀定义（空壳类，字段全在 ItemAsset：mod_type/mod_rank/pool/rarity） | ItemModAsset.cs:5 |
| `Item : CoreSystemObject<ItemData>` | **运行时物品实例**（有身份：id/name/history/kills/durability/modifiers） | Item.cs:6 |
| `ItemData : BaseSystemData` | 持久化 DTO（asset_id/durability/modifiers/kills/creator 元数据） | ItemData.cs:6-64 |
| `ItemManager : CoreSystemManager<Item, ItemData>` | 物品池管理器（`World.world.items`，type_id "item"）+ 生成/词缀/GC | ItemManager.cs:7 |
| `ItemLibrary : ItemAssetLibrary<EquipmentAsset>` | 装备库（`AssetManager.items`，注册名 "items"） | ItemLibrary.cs:8 |
| `ItemModifierLibrary : ItemAssetLibrary<ItemModAsset>` | 词缀库（`AssetManager.items_modifiers`）+ rarity 加权池 | ItemModifierLibrary.cs:5 |
| `ItemGroupAsset/Library` | 装备分组（12 组，UI 分类） | ItemGroupLibrary.cs:4-83 |
| `ActorEquipment` | Actor 六槽装备容器（dict EquipmentType → slot） | ActorEquipment.cs:6 |
| `ActorEquipmentSlot` | 单槽（type + `Item _item` 引用） | ActorEquipmentSlot.cs:5 |
| `CityEquipment` | **CityData 内嵌**城市装备库（按槽位分桶的 `List<long>` item id） | CityEquipment.cs:6 |
| `ItemCrafting`（static） | 合成入口（**无 recipe asset**——成本直接在 EquipmentAsset 上） | ItemCrafting.cs:5 |
| `ItemTools`（static） | 物品数值计算（calcItemValues/mergeStats） | ItemTools.cs:4 |
| `EquipmentType` | 枚举：Weapon/Helmet/Armor/Boots/Ring/Amulet（封闭 6 值） | EquipmentType.cs:4-17 |
| `Rarity` | 枚举：R0_Normal/R1_Rare/R2_Epic/R3_Legendary | Rarity.cs:4-13 |

**资产继承链（Verified）**：`EquipmentAsset : ItemAsset : BaseAugmentationAsset : BaseUnlockableAsset : Asset`——物品与 trait 共享 augmentation 框架（`base_stats` 在 BaseUnlockableAsset.cs:174；`action_attack_target/spells/decisions/combat_actions` 在 BaseAugmentationAsset.cs:110-156）。**ItemAsset 自身从不直接实例化为物品**。

## Data Model

**（与 Actor 同构的"蓝图→实例→DTO"三层 + 双持有侧）**

```text
definition:  EquipmentAsset (AssetManager.items)          ItemModAsset (AssetManager.items_modifiers)
             （含 base_stats/cost/durability/mod 字段）     （词缀：mod_type 互斥、rarity 加权）
                        │ id (string)                              │ id (string)
                        ▼                                          │ data.modifiers : ListPool<string>
instance:    Item : CoreSystemObject<ItemData>  ←──────────────────┘（运行时合并出 _total_stats/_quality）
             （World.world.items 池化管理，id 走 map_stats.id_item）
                        │ data.id (long) 双向引用
             ┌──────────┴──────────┐
             ▼                     ▼
持有侧:      Actor.equipment           CityData.equipment : CityEquipment
             : ActorEquipment          （按 EquipmentType 分桶 List<long>）
             （6 × ActorEquipmentSlot，   （容量 status.maximum_items=15/槽，
              持 Item 引用，runtime）       超额按价值替换）
```

- **Item 与 Resource 是完全不同的两种东西**（本系统核心边界）：Item 是**有身份的对象**（long id、可命名、可 favorite、有创造者/王国/击杀历史、per-instance durability/modifiers）；Resource 是**纯数量**（string id + int amount，见 resources.md）。两者无转换关系、无共享容器
- **ItemData（持久化）**：`asset_id`(string)、`durability`(int, 默认 100)、`modifiers`(ListPool\<string\>，词缀 id 列表)、`kills`、`by/byColor/from/fromColor`（创造者/王国展示名）、`creator_id/creator_kingdom_id`(long)、`created_by_player`、继承 BaseSystemData 的 id/name/created_time/custom_data 五型
- **Item runtime-only**：`_asset`（EquipmentAsset 引用）、`_actor`/`unit_has_it`、`_city`/`city_has_it`（**互斥持有**——diagnostic 检查双持有为错误，ItemManager.cs:40-95）、`shouldbe_removed`、`_total_stats`（calcItemValues 产物）、`_quality`（派生，不持久化）、`_item_value`（派生）、`action_attack_target`（asset+mods 合并的委托）、`_texture_id`
- **quality/value 不持久化**：`calculateValues()` 每次 init/load 重算——quality = max(asset.quality, 各 mod 的 Rarity)；value = Σ(asset.equipment_value + mod.mod_rank×2)（ItemTools.cs:48-63）
- **material 是 asset 级字段**（leather/copper/…/adamantine，决定名称后缀与本地化）；`ItemData.material` 存在但**全代码无写入点**（遗留字段，Verified：全库仅 ItemAsset 声明与 ItemLibrary 赋值 `this.t.material`）
- `minimum_city_storage_resource_1`（ItemAsset.cs:209，原版大量设 10/15）：**write-only 死字段**——全库无读取方；实际门槛是 `CityResources.hasResourcesForNewItems()`（任一 strategic resource > 10，硬编码，CityResources.cs:76-86）

### ActorBag / saved_items / equipment 三者辨析（关闭 actor.md 边界）

| 概念 | 类型 | 内容 | 持久化 |
|---|---|---|---|
| `ActorData.inventory` | `ActorBag`（dict\<string, ResourceContainer\>） | **Resource 数量携带**（搬运层，见 resources.md）——与 Item 完全独立 | 随 ActorData JSON |
| `ActorData.saved_items` | `List<long>` | **equipment 的序列化形式**（各槽 Item data.id 列表，Actor.cs:8928-8935） | 随 ActorData JSON |
| `Actor.equipment` | `ActorEquipment` | runtime 六槽容器，持 `Item` 对象引用 | 不直接持久化（经 saved_items + SavedMap.items 重建） |

Item 不进 ActorBag、不进 CityResources——城市侧装备存于 `CityData.equipment`（CityEquipment）。

## Lifecycle / Flow

### 创建（Verified，唯一正式入口 generateItem）

```text
ItemManager.generateItem(EquipmentAsset, Kingdom, pWho, pTries, Actor, pFakeCreationYear, pByPlayer)
                                                ItemManager.cs:171-197
  1. newItem(pAsset) → newObject()（池取 Item + data.id = getNextId("item")）
     + item.newItem(pAsset)（setAsset + durability = pAsset.durability）
  2. generateModsFor(item, pTries, ...)          ItemManager.cs:128-168
     ├─ 每 try 50% 概率：getRandomModFromPool(asset.equipment_type)
     │   （pool 按 slot：Weapon→"weapon"，Ring/Amulet→"accessory"，其余→"armor"）
     │   + mod_can_be_given 过滤 + item.addMod（mod_type 互斥，Item.cs:234-251）
     └─ asset.item_modifiers（linkAssets 解析的强制词缀）逐个 addMod
     + legendary（R3）词缀生成唯一名（unique_legendary_names 防重，ItemManager.cs:220-239）
  3. 元数据：data.by/creator_id/created_by_player/kingdom 色彩/from 等
  4. item.initItem()（initFields: AssetManager.items.get(asset_id) 重挂引用
     + calculateValues: _total_stats/_item_value/_quality 全量重算）
```

生成调用方：`ItemCrafting.craftItem`（合成）、`Actor.createNewWeapon`（spawn 武器，Actor.cs:7340-7346）、`ActorManager.cloneUnit`（**克隆复制装备**：新 item + mods 拷贝并剔除 "eternal"，ActorManager.cs:571-586）、`DropsLibrary.useEquipmentRain`（装备雨，直接装备目标 actor）、`EquipmentEditor`（玩家编辑器）。

### 装备 / 卸下（Verified）

```text
装备:  equipment.setItem(item, actor)              ActorEquipment.cs:107-110
         → getSlot(asset.equipment_type).setItem   ActorEquipmentSlot.cs:62-71
           ├─ 旧 item takeAwayItem（clearUnit → 变 ownerless，不销毁）
           └─ _item = pItem + pItem.setUnitHasIt(actor) + pActor.setStatsDirty()
拿取:  City.giveItem(actor, list, city)            City.cs:2624-2661
         随机取一件，仅当价值高于当前槽位才换（旧 item 回城库）
掠夺:  Actor.tryToStealItems(target)               Actor.cs:~7440-7477
         逐槽随机，cursed 不可夺，价值更高才换（双方 setStatsDirty）
卸下:  slot.takeAwayItem()（_item=null + item.clearUnit）
       Actor.takeAwayItems()（全槽卸下，死亡流程用）
替换防御: slot.canChangeSlot()（cursed 装备锁槽）；craftItem 遇 cursed 直接 false
```

**旧装备去哪里**：装备新物品时旧 item 仅被 `takeAwayItem`（unlink），若在城市语境下被 `tryToPutItem` 收回城库，否则变 ownerless 等待 GC。

### 死亡处理（Verified，Actor.cs:6978-7017）

```text
die():
  listPool.AddRange(equipment.getItems()); takeAwayItems()   （先收集再解链）
  if current_tile.zone.hasCity() → city.tryToPutItems(listPool)  （装备回所在 zone 城市）
  if hasCity &&死于衰老 → this.city.tryToPutItems(剩余)          （第二次机会）
  最后 destroyAllEquipment()（兜底清空，正常应为空）
```

- **装备不掉落到世界 tile**——Item 不存在于地面；无城市接收则变 ownerless
- ownerless + `!isFavorite() && !isEternal()`（isDestroyable）→ `ItemManager.checkDeadObjects`（dirty 时）→ removeObject → 回池（ItemManager.cs:242-262）——**普通单位野外死亡的装备会被 GC 销毁**；favorite（玩家收藏）与 eternal（词缀）物品永久留存（ownerless 装备会被 `generateDefaultSpawnWeapons(pUseOwnerless)` 重新拾取，Actor.cs:7320-7329）

### 耐久与修理（Verified）

```text
受损: Actor.damageEquipmentOnGetHit(attacker)      Actor.cs:6356-6420
  （被武器击中时：每件装备 50% 概率受击，
   damage = 攻方 rigidity_rating / 守方 rigidity_rating × 4；pool weapon 不计防御和；
   攻方武器也磨损：近战 damage = 防具 rigidity 之和/5/武器 rigidity×4，远程 35% 概率 -1）
broken: durability ≤ 0 → isBroken；updateStats 中 stats 贡献 ×0.5（仍生效！）
修理: BehRepairEquipment（task "repair_equipment"：去 type_barracks 建筑，
   花费 cost_gold × SimGlobals.item_repair_cost_multiplier → fullRepair）
   前置 BehCheckCanRepairEquipment（有可修且付得起才去）
词缀 "eternal": getDamaged 无效（免疫磨损）；"cursed": 锁槽不可换不可夺
```

### ItemCrafting 合成链（Verified 全链，关闭 resources.md 边界项）

```text
触发（三处，均非 CitizenJob 工种——12 工种中无 blacksmith）:
  ① Decision "make_items"（cooldown 90s, weight 0.4:
     launch = hasHouse && inOwnCityBorders && city.hasResourcesForNewItems()）
     → task "make_items"（BehBuildingTargetHome→…→BehMakeItem→BehActorTryToTakeItemFromCity）
                                              DecisionsLibrary.cs:1069-1078
  ② AutoCivilization 城市周期（craft armor/weapon + 派发 try_to_take_city_item task）
                                              AutoCivilization.cs:260-263
  ③ CityWindow UI 按钮                        CityWindow.cs:191

ItemCrafting.craftItem(actor, name, type, pTries, city)   ItemCrafting.cs:39-100
  1. 选型: 武器→culture.getPreferredWeaponSubtypeIDs() 或 default_weapon_pool 随机
          → AssetManager.items.equipment_by_subtypes[subtype]（linkAssets 产物）
  2. 门槛: getItemAssetToCraft——只造升级（equipment_value > 当前槽位物品价值）
          且 hasEnoughResourcesToCraft（actor 钱 + 城市两种资源存量）        :103-125
  3. 产出: World.world.items.generateItem(asset, kingdom, actor名, pTries, actor)
     （pTries = actor.asset.item_making_skill(默认1) + culture trait
       weaponsmith_mastery/armorsmith_mastery 加成 → 影响词缀生成次数）      :8-28
  4. 装备: 槽位空→setItem；否则旧 item → pCity.tryToPutItem（回城库）
  5. 扣费: actor.spendMoney(asset.cost_gold)            （金币走 actor 钱）
          + pCity.takeResource(cost_resource_id_1, cost_resource_1)  ×2    （资源走城库）
```

- **recipe 不是 asset**：配方 = EquipmentAsset 自身的 `cost_gold + cost_resource_id_1/2 + cost_resource_1/2`（setCost 辅助，ItemAsset.cs:131-138）+ `equipment_value`（升级门槛）
- **crafting 不消费 `ingredients/ingredients_amount`**（那是 ResourceLibrary 食物配方字段，resources.md gap 前提修正）
- 产出直接是装备中的 Item 实例（不进城库、不落地面）；无 crafting 中间态（同步瞬时完成）
- 词缀随机性：仅 generateModsFor 的 50%×pTries 随机抽取

### Save / Load（Verified 全链）

```text
保存: SavedMap.create → items.save()（CoreSystemManager.save: 遍历 list，
     isAlive → item.save() → data.save()；Item 无 prepareForSave——ItemData
     全字段天然可序列化）→ SavedMap.items : List<ItemData>     SavedMap.cs:602
     Actor 侧: prepareForSave 第 5 步 saveEquipment →
     data.saved_items = equipment.getDataForSave()（各槽 item id；空→null）
                                                              Actor.cs:8875-8935
加载（SmoothLoader 引用安全序）:                          SaveManager.cs:1606
     religions → **items**（World.world.items.loadFromSave(data.items)）
     → books → … → cities（loadCity → data.equipment.loadFromSave(city)，
       City.cs:723：null/缺 asset 条目移除 + setInCityStorage 重建）
     → actors（loadObject → equipment.load(saved_items, actor)，
       ActorManager.cs:840-843：items.get(id)→按 asset.equipment_type 归槽；
       null 跳过）→ lovers/… 二次连接
缺失行为:
     ItemAsset 缺失 → ItemManager.loadObject 返回 null（物品整体静默丢弃）
                                                              ItemManager.cs:98-105
     ItemModAsset 缺失 → Actor.loadFromSave 中从 data.modifiers 逐个剔除
                                                              Actor.cs:9098-9118
     （city 侧装备条目指向已丢弃 item → CityEquipment.loadFromSave RemoveAll 清理）
id: map_stats.id_item 计数器随档往返（MapStats.cs:977, 394-397）；
     旧档 fixup：id_item≤1 时重扫 max(itemData.id)+1（SaveConverter.cs:362-375）
```

### Stats 集成（Verified，updateStats 完整合并顺序 Actor.cs:1530-1830）

```text
stats.clear() 后依序 mergeStats（全部 additive，multiplier=1 除装备 broken）:
  1. subspecies（无则 asset）base_stats + 性别差异
  2. clan（+性别）/ language / culture
  3. 教育属性（data["diplomacy"] 等四项直加）
  4. statuses（逐个 status.asset.base_stats）
  5. **无武器时: AssetManager.items.get(asset.default_attack).base_stats**
     （default_attack 默认 "base_attack"；jaws/claws/rocks/snowball 等
       攻击模板本身就是 ItemLibrary 里的隐藏 EquipmentAsset！）
  6. traits（era-gated）
  7. personality（king/leader 才有）
  8. 等级加成（health/mana/stamina + level）
  9. **装备: 逐槽 ItemTools.mergeStatsWithItem(this.stats, item, false,
       item.isBroken() ? 0.5f : 1f)**——asset.base_stats + 每 mod base_stats
 10. 派生（normalize/cities/bonus_towers/mana/era range/damage+=warfare/5/baby×0.5）

attack action 绑定（战斗系统边界）:
  updateStats 内: 无武器→default_attack 的 action_attack_target（+其 item_modifiers）
  有装备→逐槽 addItemActions(asset/mods) + s_action_attack_target =
  Delegate.Combine(…, item.action_attack_target)              Actor.cs:1734-1770
  攻击类型: checkAttackTypes → _attack_asset = 当前武器 asset；
  isRangeAttack = weapon.attack_type（WeaponType.Melee/Range）
spells: recalcSpells 逐槽合并 item.asset.spells               Actor.cs:5787-5800
触发: 任何装备变动 → slot.setItem/craft/steal 内置 setStatsDirty → 下次 updateStats 重算
sprite: 装备影响外观（helmet on warrior 头像 Actor.cs:4560、ItemInHand 枚举
  Tool/Resource/Weapon、pool weapon gameplay_sprites）——渲染细节不展开
profession/job 判断: **装备不参与**（仅 actor.asset.use_items 等 gate 行为能力）
```

### Asset 注册三阶段（Verified，与 technical/assets.md 互证）

```text
AssetManager.initLibs → add(ItemLibrary, "items") / add(ItemModifierLibrary,
  "items_modifiers") / add(ItemGroupLibrary, "item_groups")   AssetManager.cs:143-145
init（全部代码定义 + 模板 clone）:
  ItemLibrary: initTemplates（$equipment/$armor/$helmet/$boots/$accessory/
    $ring/$amulet/$weapon/$melee/$range/$bow/$sword/$axe/$hammer/$spear）
    → initNormalEquipment（armor/helmet/boots/ring/amulet ×9 材质）
    → initNormalWeapons（sword/bow/axe/spear/hammer ×9 材质 + stick_wood）
    → initWeaponsUnique（alien_blaster/shotgun 等成就解锁）
    → initBoats（boat_cannonball 等 10 个船用攻击模板）
    → initBaseAttacks（base_attack/hands/jaws/claws/bite/snowball/rocks/
      fire_hands——show_in_meta_editor=false 的隐藏攻击资产）
  ItemModifierLibrary: normal(占位)/power1-5/truth/protection/speed/balance/
    health/finesse/mastery/knowledge/sharpness（数值词缀 5 级）
    + flame/ice/stun/slowness/poison（AttackAction 词缀）
    + eternal/cursed/divine_rune（特殊词缀）
post_init: pool weapon 贴图路径 + path_icon 默认 + cost_coins_resources
  （= Σ cost_resource 的 ResourceAsset.money_cost）            ItemLibrary.cs:23-48
linkAssets: item_modifier_ids→ItemModAsset[]（miss 报错留空）
  + fillSubtypesAndGroups（equipment_by_subtypes / pot_weapon_assets_all /
    pot_equipment_by_groups_all）+ fillUnlockedPools（读 GameProgress
  unlocked_equipment 填 *_unlocked）+ linkSpells               ItemLibrary.cs:51-80
  ItemModifierLibrary.linkAssets: 按 rarity 权重填 pools["weapon"/"armor"/"accessory"]
loadSprites: 独立入口（pool weapon gameplay_sprites 惰性加载）
add() override: 自动补 base_stats = new BaseStats()（ItemLibrary.cs:83-91）
unlock 体系: EquipmentAsset.unlock() → pot_*_unlocked 池增量维护
  （ItemAsset.cs:161-187；progress_elements = GameProgressData.unlocked_equipment）
```

**base attack 也是 EquipmentAsset**：动物撕咬（jaws/claws/bite）、投掷（rocks/snowball）、船炮（boat_*）全部注册在 items 库中——"ItemLibrary" 实际承担**装备 + 全物种攻击模板**双重职责。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `World.world.items.generateItem(asset, kingdom, who, tries, actor, ...)` | 物品创建唯一正式入口 | ItemManager.cs:171 |
| `World.world.items.get(long)` | item id → Item | SystemManager |
| `actor.equipment.setItem(item, actor)` / `getSlot(type)` | 装备/取槽 | ActorEquipment.cs |
| `actor.canUseItems()` / `understandsHowToUseItems()` | `asset.use_items` / +isSapient | Actor.cs:3814-3824 |
| `actor.getWeapon()` / `getWeaponAsset()` / `hasWeapon()` | 武器槽访问（hasWeapon = canUseItems && weapon 非空） | Actor.cs:2624-2644 |
| `city.tryToPutItem(item)` / `City.giveItem(actor, list, city)` | 城库收纳 / 取用（价值比较） | City.cs:2725, 2624 |
| `item.addMod(id)` / `hasMod` / `removeMod` | 词缀操作（mod_type 互斥） | Item.cs:215-258 |
| `item.getFullStats()` / `getValue()` / `getQuality()` | 派生数值（重算产物） | Item.cs:412-427 |
| `ItemCrafting.craftItem(actor, name, type, tries, city)` | 合成主入口 | ItemCrafting.cs:39 |
| `AssetManager.items` / `items_modifiers` / `item_groups` | 三库入口 | AssetManager.cs:143-145 |

## Extension Points

1. **注册新装备（EquipmentAsset）——modding 核心问题（Verified）**：
   - **必须**：`AssetManager.items.add(new EquipmentAsset{ id, equipment_type, base_stats, ... })`——add 自动补 base_stats，dict/list 注册即时生效；`generateItem`/`setItem`/stats merge 均可正常消费
   - **仅 add 不足（linkAssets 不重跑）**：
     a. **不进 `equipment_by_subtypes`** → `craftItem` 选型查不到 → **永不被 AI 合成**（且若使用全新 subtype 字符串，craftItem 直接 dict 索引该 subtype 会 KeyNotFound——应复用既有 subtype 如 "sword"）
     b. `item_modifier_ids` 不解析（item_modifiers 数组为 null）
     c. 不进 `pot_weapon/pot_equipment_by_groups` 池 → transmute/装备雨/解锁池不可见
     d. `fillUnlockedPools` 依赖 GameProgress.unlocked_equipment（探索解锁）——mod 装备默认 `needs_to_be_explored=true` 且不在进度表 → `isAvailable()` false → 装备雨/池过滤排除（**craftItem 不检查 isAvailable，合成侧不受此限**）
   - **post_init 不重跑**：path_icon/cost_coins_resources 为默认值（mod 需自设 path_icon；cost_coins_resources 仅影响 UI 展示合计）
   - **可正常**：手动 `World.world.items.generateItem` + `equipment.setItem` 直接装备（不经池/选型）；存档往返正常（asset_id 重解析 + loadObject null 丢弃语义明确）
2. **注册新词缀（ItemModAsset）**：`AssetManager.items_modifiers.add(...)`——**pools 不重跑 → 永不被随机抽取**；可经 `item.addMod` 手动附加或被既有 EquipmentAsset.item_modifiers 引用（但后者解析在 linkAssets）。数值词缀直接写 base_stats；特殊效果用 action_attack_target（参考 flame/ice 实现，ItemModifierLibrary.cs:296-353）
3. **合成介入**：Harmony patch `ItemCrafting.craftItem` / `ItemManager.generateItem` / `ActorEquipmentSlot.setItem`
4. **给特定单位配装备**：改 `ActorAsset.default_weapons/default_attack`（spawn 链自动生效）或运行时 `actor.createNewWeapon(id)`
5. **词缀自定义**：`item.addMod` 后 setDirty 已内置；reforge/transmute（Item.cs:146-212）是原版重铸入口可参考
6. **装备数值调整**：改 EquipmentAsset.base_stats（全局）或 Harmony `ItemTools.mergeStatsWithItem`（per-call）

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| Actor | equipment/saved_items/canUseItems；死亡装备回城；updateStats 装备段 | 已覆盖（entity/actor.md） |
| Resources | crafting 扣 city.takeResource×2 + actor 钱；**hasResourcesForNewItems 是 make_items decision 门槛**（strategic>10）；无 salvage/recycle；Item 与 Resource 无转换 | 已覆盖（economy/resources.md，本批回写） |
| City | CityData.equipment 容器（15/槽 + 价值替换）；tryToPutItem/giveItem | 已覆盖（settlement/city.md） |
| Jobs | **crafting/repair/take_item 非 CitizenJob 工种**（12 工种无 blacksmith）——是 Decision task（make_items/repair_equipment/try_to_take_city_item）+ AutoCivilization 驱动 | 已覆盖（economy/jobs.md，本批回写边界澄清） |
| Behaviour | Decision 调度机制（cooldown/weight/action_check_launch 消费）、Beh* 内部 | deferred: behaviour（本批止于 task 链） |
| Combat | s_action_attack_target 消费、damageEquipmentOnGetHit 的战斗侧触发、AttackAction 结构 | deferred: combat |
| Culture | culture preferred weapons（getPreferredWeaponSubtypeIDs/hasPreferredWeaponsToCraft）+ weaponsmith/armorsmith_mastery trait | deferred: culture |
| Assets | ItemLibrary 三阶段（subtype/池/unlock 在 linkAssets）；与 trait 共享 BaseAugmentationAsset 框架 | 已覆盖（technical/assets.md） |
| Save | SavedMap.items + saved_items + CityEquipment 三处持久化；id_item 计数器；缺失丢弃/剔除语义 | 已覆盖（technical/save.md，本批确认加载序） |
| World | item 无 tile 存在（不落地）；装备雨以 chunk 搜索单位 | 边界记录（不展开） |

## Evidence

| 结论 | source | location |
|---|---|---|
| 三层资产模型（ItemAsset 基类不被实例化；Equipment/ItemMod 双子类） | worldbox | ItemAsset.cs:10, EquipmentAsset.cs:6, ItemModAsset.cs:5, BaseUnlockableAsset.cs:174, BaseAugmentationAsset.cs:110-156 |
| Item 实例/ItemData 字段分层（asset vs instance 状态） | worldbox | Item.cs:527-557, ItemData.cs:33-64, Item.setDefaultValues:134-143 |
| ItemManager 池化 + type_id "item" + id 分配 | worldbox | ItemManager.cs:7-17, MapStats.cs:977, 394-397 |
| generateItem 全链（mods/元数据/initItem） | worldbox | ItemManager.cs:171-197, 128-168 |
| quality/value 派生不持久化（重算规则） | worldbox | Item.cs:313-320, ItemTools.cs:48-63 |
| mod_type 互斥 + 词缀池按 slot/rarity | worldbox | Item.cs:234-251, ItemManager.cs:108-119, ItemModifierLibrary.cs:387-411 |
| 六槽模型 + setItem/takeAwayItem + statsDirty | worldbox | ActorEquipment.cs:140-164, ActorEquipmentSlot.cs:45-71 |
| Item 双持有互斥（actor/city）+ GC 条件 | worldbox | Item.cs:261-276, 51-60, ItemManager.cs:242-262 |
| 死亡装备回城（不落地）+ ownerless GC/重拾 | worldbox | Actor.cs:6978-7017, 7318-7337 |
| 耐久公式（rigidity 比值）+ broken×0.5 + 修理链 | worldbox | Actor.cs:6356-6420, 1788-1794, BehRepairEquipment.cs:8-33, BehCheckCanRepairEquipment.cs |
| crafting 全链（无 recipe asset；升级门槛；三触发源；扣费） | worldbox | ItemCrafting.cs:8-125, AutoCivilization.cs:260-263, DecisionsLibrary.cs:1059-1078, CityWindow.cs:191 |
| crafting 非 CitizenJob 工种（decision 驱动） | worldbox | CitizenJobLibrary.cs:8-100（12 工种无 blacksmith）, BehaviourTaskActorLibrary.cs:573, 630, 1089 |
| updateStats 合并顺序（default_attack fallback + 装备段 + broken） | worldbox | Actor.cs:1530-1830（装备段 1614-1621, 1750-1770, 1782-1797） |
| attack actions/spells 从装备合并 | worldbox | Actor.cs:1734-1770, 5787-5800 |
| CityEquipment 容器/上限/价值替换/loadFromSave | worldbox | CityEquipment.cs:15-130, City.cs:2725-2766, 874 |
| save/load 三处持久化 + 引用安全序（items 先于 cities/actors） | worldbox | SavedMap.cs:602, SaveManager.cs:1606, City.cs:723, ActorManager.cs:840-843, CoreSystemManager.cs:66-82 |
| 缺失行为（ItemAsset null 丢弃 / ItemMod 剔除） | worldbox | ItemManager.cs:98-105, Actor.cs:9098-9118 |
| id_item 旧档 fixup | worldbox | SaveConverter.cs:362-375 |
| 注册三阶段（模板/材质族/攻击模板混载/池构建） | worldbox | ItemLibrary.cs:11-48, 51-80, 211-271, 759-921 |
| 克隆复制装备（mods 拷贝剔 eternal） | worldbox | ActorManager.cs:571-586 |
| 掠夺/取用价值比较 + cursed 防御 | worldbox | Actor.cs:7440-7477, City.cs:2624-2661, ActorEquipmentSlot.cs:74-77 |
| ItemData.material 无写入点 / minimum_city_storage_resource_1 无读取方 | worldbox | 全库 grep（仅 ItemAsset.cs:209 声明 + ItemLibrary 赋值） |
| hasResourcesForNewItems 硬编码 >10（非 min 字段） | worldbox | CityResources.cs:76-86, DecisionsLibrary.cs:1076 |

## Confidence

- Verified：全部机制结论（含死字段判断——基于全库文本检索无消费方）
- Inferred：craftItem 对全新 subtype 字符串会 KeyNotFoundException（由 dict 直接索引代码路径推出，未运行时验证）
- Unknown：见 Known Gaps

## Known Gaps

- Decision/NeuroLayer 调度内部（weight/cooldown/action_check_launch 如何被消费）——deferred: behaviour
- Combat 侧 s_action_attack_target 的攻击结算、DamageSystem——deferred: combat
- `ItemWindow`/`EquipmentEditor`/`EquipmentGrid` UI 内部与 `EquipmentButton` 交互——deferred: ui
- `culture.getPreferredWeaponSubtypeIDs/hasPreferredWeaponsToCraft` 内部——deferred: culture
- `NameGenerator` 词缀/传说武器命名模板机制——deferred: culture（命名域）
- 装备雨（useEquipmentRain）的 RainState/PlayerConfig.equipment_editor 细节（仅入口级已录）
- `ActorAsset.default_weapons` 各物种完整配置面（仅抽样）
- `SimGlobals.item_repair_cost_multiplier` 当前数值

## Related Patterns

- [register-actor-trait](../../patterns/assets/register-actor-trait.md) — 同源 BaseAugmentationAsset 注册（trait 与 item 同框架）
- [clone-modify-asset](../../patterns/assets/clone-modify-asset.md) — 材质族装备（armor_iron ← $armor clone）即此模式
- [safe-asset-registration](../../patterns/assets/safe-asset-registration.md) — last-wins 防御
- [actor-data-custom-state](../../patterns/actor/actor-data-custom-state.md) — ItemData 继承同款 custom_data 容器（per-item mod 数据可挂此层）
