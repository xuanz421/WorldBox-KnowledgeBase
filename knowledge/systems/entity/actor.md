# System: Actor / Entity

WorldBox 单位系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 反编译源码直接阅读与 WBKB Reference Graph 交叉验证。

## Scope

覆盖：Actor 运行时对象、ActorData 持久化数据、ActorAsset 类型蓝图、ActorManager 池化/批处理管理、创建-更新-死亡全生命周期、runtime state 与 persistent data 的分界、行为系统入口（仅到 ai.update() 一层）。

不覆盖：Behaviour Tree 内部（deferred: behaviour system）、Save 系统落盘细节（deferred: save system）、City/Kingdom/Jobs 等下游系统（独立调查）、渲染管线。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `Actor` | 运行时单位实例（9700 行大类）：状态、行为、战斗、社交 | Actor.cs:8-9702 |
| `ActorData` | 持久化 DTO：SQLite 行 + JSON 序列化载体 | ActorData.cs:7-241 |
| `ActorAsset` | 单位类型蓝图（264 字段：stats/sound/animation/默认 trait） | ActorAsset.cs:7-1386 |
| `ActorManager` | 池化容器 + 批处理调度 + 存档加载入口 | ActorManager.cs:8-898 |
| `BaseSimObject` | Actor/Building 共同基类：位置/tile/kingdom/stats/status | BaseSimObject.cs:6-716 |
| `BaseActorComponent` | MonoBehaviour 特殊组件（Crabzilla/Dragon/GodFinger/UFO），**不是**通用行为系统 | BaseActorComponent.cs:4-21 |
| `SystemManager<Actor,ActorData>` | 泛型池化基类：newObject/getNextObject/dict/生命周期 | SystemManager.cs:6-207 |

继承：`Actor : BaseSimObject : NanoObject`，实现 `ITraitsOwner<ActorTrait>`、`ILoadable<ActorData>`（Actor.cs:8-9702 符号信息）。

## Data Model

**三层结构（关键设计）：**

```text
ActorAsset (类型蓝图, 注册于 AssetManager.actor_library, 全局静态)
      │  1 asset : N instances（反向索引 ActorAsset.units : HashSet<Actor>）
      ▼
Actor (运行时实例, 池化, 由 ActorManager 持有)
      │  1 : 1
      ▼
ActorData (持久化数据, SQLite 行 + custom_data 键值容器)
```

- **ActorData**（ActorData.cs:7-241）：
  - 继承 `BaseObjectData`（health）→ `BaseSystemData`（BaseSystemData.cs:10-452）：`[PrimaryKey] id`、`name/created_time/died_time`、`custom_data_int/long/float/bool/string` + `custom_data_flags` 五型键值容器（BaseSystemData.cs:17-32）
  - Actor 特有：`saved_traits : List<string>`（trait id 列表）、`saved_items : List<long>`（**equipment 六槽的序列化形式**——各槽 Item data.id，见 economy/items.md）、`inventory : ActorBag`（Resource 携带层，与 item 无关）、`x/y`、`profession`、`homeBuildingID`、`transportID`、`cityID`、`civ_kingdom_id` 及 42 个属性（ActorData.cs:15-45 字段清单）
- **runtime-only state**（不持久化，重建）：`traits : HashSet<ActorTrait>`（从 saved_traits 重建）、`_traits_cache`、`stats : BaseStats`（脏标记重算）、`current_tile/current_position`（BaseSimObject.cs:17-33）、`ai : AiSystemActor`、`batch : BatchActors`
- **custom data 扩展点**：`actor.data.get("mod.key", out float v, default)` / `set("mod.key", v)`（BaseSystemData.cs:262-350）——五型 + flags + `change()` 带上下限、`cloneCustomDataFrom`（Actor.cs:533 克隆单位时复制）
- 教育属性持久化在 data 而非 asset：`stats["diplomacy"] += data["diplomacy"]`（Actor.cs:1804-1807）

## Lifecycle / Flow

### 创建（Verified，调用链已逐行确认）

```text
ActorManager.createNewUnit(statsID, tile, ...)        ActorManager.cs:574
 1. AssetManager.actor_library.get(statsID)           → ActorAsset（miss → null 返回）
 2. newObject()                                        SystemManager.cs
    ├─ data = new ActorData { id = map_stats.getNextId("unit"), created_time }
    ├─ getNextObject()：_dead_objects 池 pop / new Actor()
    └─ setData(data); addObject()                      → dict + batch + job manager
 3. actor.setAsset(actorAsset)                         Actor.cs:552
    （旧 asset.units.Remove / 新 units.Add / setStatsDirty / 建 equipment）
 4. subspecies 解析或 checkNewSpecies 突变              ActorManager.cs:583-605, 726-762
 5. addRandomTraitFromBiomeToActor                     ActorManager.cs:764-780
 6. finalizeActor(...)                                  ActorManager.cs:636-682
    ├─ spawnOn(tile)
    ├─ data.* 引用解析：World.world.<subspecies/family/language/plot/
    │  religion/clan/culture/armies>.get(id)            ActorManager.cs:642-673
    ├─ pActor.create()                                  Actor.cs:567-616
    │   （AiSystemActor 创建、job/task library 绑定、死亡回调委托、
    │    asset.base_stats["scale"] 应用、addChildren 特殊组件）
    ├─ checkDefaultKingdom / checkDefaultProfession
    └─ updateStats()
 7. actor.newCreature()                                 Actor.cs
    （generatePersonality → subspecies 出生 trait 或 asset.traits 默认 trait，
     mutation 检查，generateSex）
 8. generateDefaultSpawnWeapons / clearSprites
```

玩家入口 `spawnNewUnitByPlayer → spawnNewUnit`（ActorManager.cs:694-724，附加 wild kingdom 默认与 nutrition）；婴儿入口 `createBabyActorFromData`（ActorManager.cs:684-692）。

### 更新（tick）

```text
MapBox.update → updateActors → ActorManager.update(pElapsed)   ActorManager.cs:331
  → _job_manager.updateBase → BatchActors 作业链               BatchActors.cs:45-78
    （~30 个 Parallel/Post 作业：u4_deadCheck、b6_0_updateDecision、
      b6_updateAI、updateDeathCheck、u7_checkAugmentationEffects…）
  → Actor.b6_updateAI(elapsed)
     guard: !_update_done && !_beh_skip && !is_unconscious
             && !_has_status_possessed && asset.has_ai_system
     → ai.update()  （AiSystemActor — behaviour 系统边界）
```

死亡由 `updateDeathCheck/u4_deadCheck` 触发 `checkDeath()`（Actor.cs:6805）→ `die(pDestroy, type)`（Actor.cs:6843）。

### 死亡与销毁

- `die()`：`setAlive(false)`、`skipUpdates()`，随后 `checkCallbacksOnDeath()`（Actor.cs:6771-6803）按序触发：tile Type.unit_death_action → `asset.action_death` → **每个 trait 的 `action_death`** → status asset → clan/subspecies/religion 的 `all_actions_actor_death` → `callbacks_on_death` 委托
- `ActorManager.destroyObject`（ActorManager.cs:366-395）：asset.units.Remove、removeObject（dict 移除 + scheduleToDispose → 回池）、job manager 移除、avatar 销毁

### 存档加载（Verified）

```text
ActorManager.loadFromSave(List<ActorData>)          ActorManager.cs:772
 → SystemManager.loadFromSave                        SystemManager.cs
   （id == -1 → 重新分配 id；逐条 loadObject）
 → ActorManager.loadObject(ActorData)                ActorManager.cs:782-826
   ├─ dict 去重 / tile / asset 解析（fail → null 静默丢弃）
   ├─ base.loadObject：池取对象 + loadData（setData + data.load()）
   ├─ finalizeActor（同创建路径 6）
   ├─ equipment.load(saved_items) / reloadInventory
   ├─ actor.loadFromSave()                            Actor.cs:8860-8875
   │   （TraitTools.loadTraits 直接填 HashSet + 逐 trait
   │    action_on_augmentation_load；恢复 profession/city/kingdom）
   └─ 恢复 health/nutrition/stamina/mana → updateStats
```

保存侧：`saveTraits()` → `data.saved_traits = ids`（Actor.cs:8850）；`finishSaving()` → `data.save()`（Actor.cs:8855）。落盘路径已确认（→ technical/save.md）：`Actor.prepareForSave()` 17 步把全部对象引用 id 化，`ActorData` 作为 SavedMap.actors_data 列表元素随 `map.wbox`（zlib 压缩 JSON）写出；custom_data_* 容器内嵌同一 JSON。**id 跨存档稳定**：分配走 `map_stats.getNextId("unit")`，MapStats 计数器随存档往返（MapStats.cs:120-160, SavedMap.cs:228）。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `World.world.units` / `MapBox.units` | ActorManager 全局入口 | MapBox.cs:103, 335 |
| `actor.data.get/set(key, val)` | per-actor 持久化自定义数据（五型） | BaseSystemData.cs:262-350 |
| `actor.traits` | `HashSet<ActorTrait>`（readonly 字段，勿直接改） | Actor.cs:86 |
| `actor.addTrait / removeTrait / hasTrait` | 见 traits.md | Actor.cs:9189-9306 |
| `actor.asset` | 蓝图访问（BaseSimObject） | BaseSimObject.cs |
| `actor.setStatsDirty()` | 触发下次 updateStats 重算 | Actor.cs |
| `ActorManager.get(id)` | long id → Actor | SystemManager.cs |
| `AssetManager.actor_library.get(statsID)` | statsID → ActorAsset | AssetLibrary.cs:27 |

## Extension Points

1. **per-actor 持久状态**：`actor.data.get/set`（Verified；参考 pattern actor-data-custom-state）
2. **per-actor 运行时状态**：自定义组件挂 `GameObject`（BaseActorComponent 路线仅用于官方特殊单位；mod 实际用静态字典/扩展方法持有运行时状态——reference mod 证据）
3. **创建钩子**：Harmony prefix/postfix `ActorManager.createNewUnit` / `Actor.create` / `newCreature`（本库尚无 pattern，属于可行方向——Inferred）
4. **死亡观察**：Harmony postfix `Actor.die` / `checkCallbacksOnDeath`（reference mod 证据：actorhistory/familytree）
5. **行为介入**：`ai.update()` 之后的 Behaviour 层（deferred: behaviour system）

## Evidence

| 结论 | source | location |
|---|---|---|
| 创建主流程 | worldbox | ActorManager.cs:574-634, 636-682 |
| create() 内容 | worldbox | Actor.cs:567-616 |
| data 三层结构与 custom_data 容器 | worldbox | BaseSystemData.cs:10-452, ActorData.cs:7-241, ActorAsset.cs:621 |
| 池化与 ID 分配 | worldbox | SystemManager.cs（newObject/getNextObject/removeObject） |
| tick 链 MapBox→BatchActors→ai | worldbox | MapBox.cs:335, 2312; ActorManager.cs:331; BatchActors.cs:45-78; Actor.cs（b6_updateAI） |
| 死亡回调链 | worldbox | Actor.cs:6771-6803, 6805-6826, 6843 |
| 存档加载流程 | worldbox | ActorManager.cs:782-826; Actor.cs:8850-8875 |
| cloneUnit 复制 custom data | worldbox | ActorManager.cs:533 |
| NML mod 初始化时点（游戏加载后） | neomodloader | NeoModLoader/NeoModLoader/WorldBoxMod.cs:87-121 |

## Confidence

- Verified：本文件全部生命周期/数据结构结论（均标注 worldbox 源码行号）
- Inferred：创建钩子作为 modding 扩展点的可行性（基于死亡观察同类证据）
- Unknown：见 Known Gaps

## Known Gaps

- ~~Deferred: Save system investigation~~ **已关闭（2026-09-07，→ technical/save.md）**：ActorData 随 SavedMap.actors_data 写入 map.wbox（zlib JSON）；`data.save()` 仅清空空 custom_data 容器（BaseSystemData.checkInt 等）；id 经 map_stats 计数器随档往返，跨存档稳定
- **Deferred: Behaviour system investigation** — AiSystemActor 内部、BehaviourTaskActor/DecisionAsset 结构
- `ActorSimpleComponent`（children_pre_behaviour）与 `_dict_special` 的完整使用面
- `ActorManager.evolutionEvent`（进化）与 `checkNewSpecies` 突变机制的深层数值规则
- Egg/Baby/Adult 状态机（calcAgeStates，Actor.cs:1725-1745）与 age_overgrowth 的完整规则

## Related Patterns

稳定 pattern_id（完整索引：knowledge/patterns/模式索引.md）：

- `actor-data-custom-state` — per-actor 持久状态（本系统 data.get/set 的 modding 用法）
- `actor-event-observation` — 死亡快照观察
- `register-custom-stat` — 自定义数值属性
- `register-actor-trait` — 给 Actor 加 trait（见 traits.md）
