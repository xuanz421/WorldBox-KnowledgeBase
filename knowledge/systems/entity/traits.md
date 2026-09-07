# System: Traits

WorldBox 特质系统的系统级调查（WorldBox 本体视角）。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。

## Scope

覆盖：ActorTrait 类型族与继承结构、Actor 持有 trait 的数据结构、add/remove/has 流程、trait 与 stat 管线集成、trait 生命周期钩子（add/remove/load/death/special_effect）、持久化、库初始化顺序与自然获取池。

不覆盖：ClanTrait/CultureTrait/KingdomTrait 等平行家族的专有逻辑（仅记录共享基类）、status effect 系统、save 落盘细节（deferred: save system）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `ActorTrait` | 单位特质定义（rate_birth/rate_acquire_grow_up/rate_inherit、affects_mind、forced_kingdom、era 门控） | ActorTrait.cs:6-93 |
| `BaseTrait<T>` | 特质共享基类：value、action_death/growth/birth、action_get_hit、base_stats_meta、opposite_list/traits_to_remove | BaseTrait.cs:6-289 |
| `BaseAugmentationAsset` | 增强资产基类（trait/item/plot/phenotype/worldlaw 共用）：add/remove/load 钩子、periodic special_effect、combat/spell/decision 持有 | BaseAugmentationAsset.cs:5-125 |
| `ActorTraitLibrary` | trait 库：原版 trait 代码定义 + 加权池 | ActorTraitLibrary.cs:5-1671 |
| `ActorTraitGroupAsset` | trait 分组（空壳类，仅 group 载体） | ActorTraitGroupAsset.cs:3 |

继承链：`ActorTrait → BaseTrait<ActorTrait> → BaseAugmentationAsset → BaseUnlockableAsset → Asset`。

平行家族（同 BaseTraitLibrary 基类，Verified 派生列表）：`ClanTrait`、`CultureTrait`、`GeneAsset`、`KingdomTrait`、`LanguageTrait`、`ReligionTrait`、`SubspeciesTrait`。BaseAugmentationAsset 的其他子类：`ItemAsset`、`PlotAsset`、`PhenotypeAsset`、`WorldLawAsset`。

库注册：`AssetManager.traits : ActorTraitLibrary`（注册名 "traits"，AssetManager.cs:387）、`AssetManager.trait_groups : ActorTraitGroupLibrary`（"trait_groups"，AssetManager.cs:388）。`ActorTrait.getGroup()` → `AssetManager.trait_groups.get(group_id)`（ActorTrait.cs:~55）。

## Data Model

- **Actor 侧持有**：`Actor.traits : HashSet<ActorTrait>`（readonly 字段，Actor.cs:86）+ `_traits_cache : Dictionary<string,bool>`（hasTrait 缓存，Actor.cs:92，任何 add/remove 后 clearTraitCache）
- **Asset 侧持有**：`ActorAsset.traits : List<string>`（该物种默认 trait id 列表，ActorAsset.cs:545）；`BaseTrait.default_for_actor_assets : List<ActorAsset>`（反向索引，linkAssets 阶段构建，BaseTraitLibrary.linkActorAssets）
- **持久化**：`ActorData.saved_traits : List<string>`（trait id 列表，ActorData.cs:30）
- **互斥模型**：`opposite_list : List<string>`（声明 ids）→ `linkAssets` 时解析为 `opposite_traits : HashSet<T>`（BaseTraitLibrary.fillOppositeHashsetsWithAssets）；另有 `traits_to_remove_ids → traits_to_remove : T[]`（加入时直接移除）
- **数值**：`base_stats : BaseStats`（进 Actor stat 管线）、`base_stats_meta`（元界面显示）

## Lifecycle / Flow

### add / remove / has（Verified）

```text
Actor.addTrait(trait, pRemoveOpposites=false)        Actor.cs:9199-9226
  1. hasTrait 去重（重复 → false）
  2. affects_mind + actor hasTag("strong_mind") → 拒绝
  3. trait.traits_to_remove → removeTraits（直接移除）
  4. opposites：pRemoveOpposites ? removeOppositeTraits : 已有 opposite → 拒绝
  5. traits.Add（HashSet）
  6. trait.action_on_augmentation_add?.Invoke(this, trait)
  7. setStatsDirty() + clearTraitCache()

Actor.removeTrait(trait)                            Actor.cs:9146-9156
  traits.Remove → action_on_augmentation_remove?.Invoke → setStatsDirty + clearTraitCache

Actor.hasTrait(id)                                  Actor.cs:9294-9303
  _traits_cache 命中 → AssetManager.traits.get(id) → 集合判定 → 写缓存
```

`addTrait(string)` 先经 `AssetManager.traits.get` 解析（Actor.cs:9189，miss → false 静默失败）。

### 运行时钩子（全部 Verified 字段）

| 钩子 | 类型 | 触发点 |
|---|---|---|
| `action_on_augmentation_add` | WorldActionTrait | addTrait 步骤 6 |
| `action_on_augmentation_remove` | WorldActionTrait | removeTrait |
| `action_on_augmentation_load` | WorldActionTrait | 存档加载后逐 trait 调用（Actor.cs:8864-8867） |
| `action_death` | WorldAction | checkCallbacksOnDeath（Actor.cs:6778） |
| `action_birth` / `action_growth` | WorldAction | 出生/成长事件 |
| `action_get_hit` | GetHitAction | updateStats 时 Delegate.Combine 到 s_get_hit_action（Actor.cs:1837-1840） |
| `action_attack_target` | AttackAction | 战斗 |
| `action_special_effect` + `special_effect_interval` | WorldAction/float | 周期效果（BatchActors c_augmentation_effects 作业 u7） |

### Stat 集成（Verified）

`Actor.updateStats()`（Actor.cs:1747-1842+）在 stats.clear() 后按固定顺序 merge：

```text
subspecies base_stats（或 asset.base_stats）→ clan → language → culture
→ data 教育属性（diplomacy/stewardship/intelligence/warfare）
→ status effects → 默认武器 EquipmentAsset.base_stats（default_attack，见 economy/items.md）
→ 每个 trait 的 base_stats（era 门控：only_active_on_era_flag/
   era_active_moon/era_active_night 不满足则跳过）+ action_get_hit 委托合并
```

NML 侧补充（跨源 Verified）：`AssetPatches.MergeWithCustomStats`（NeoModLoader.utils/AssetPatches.cs:11-46）以 Transpiler 在 `stats.clear()` 后插入动态 per-actor stats（`ActorTraitBuilder.AdditionalBaseStatMethods[id] → BaseStats(actor)`）。

### 持久化（Verified）

- 保存：`Actor.saveTraits()` → `data.saved_traits = Toolbox.getListForSave(getTraits())`（Actor.cs:8850-8853）
- 加载：`Actor.loadFromSave()` → `TraitTools.loadTraits(this, data.saved_traits)`（Actor.cs:8860-8867）——**直接填 HashSet，不走 addTrait**（无 opposites 检查、不触发 add 钩子），随后逐 trait 触发 `action_on_augmentation_load`

### 库初始化顺序（Verified，modding 关键）

```text
AssetManager.init() → AssetManager.add(traits, "traits") → ActorTraitLibrary.init()
  （原版 trait 全部代码定义：addTraitsSpecial/Body/Mind/Spirit/Acquired/Fun/Misc，
    ActorTraitLibrary.cs:28-38）
→ AssetManager post_init 全库
   （ActorTraitLibrary.post_init：为带 health/mana/stamina 数值的 trait
    自动附加 restoreFullStats add/remove 钩子，ActorTraitLibrary.cs:1578-1592；
    BaseTraitLibrary.post_init：排序 + autoSetRarity + checkIcons）
→ AssetManager linkAssets 全库
   （ActorTraitLibrary.linkAssets：构建加权池 pot_traits_birth（rate_birth）、
    pot_traits_growup（rate_acquire_grow_up）、pot_traits_mutation_box、
    pot_traits_combat，ActorTraitLibrary.cs:1601-1638；
    BaseTraitLibrary.linkAssets：opposite 解析、decision/spell/combat 链接、
    default_for_actor_assets 反向索引）
```

自然获取路径：出生突变 `checkTraitMutationOnBirth`（Actor.cs:9250-9269，pot_traits_birth）、成长 `checkTraitMutationGrowUp`（Actor.cs:9271-9286，pot_traits_growup）、出生 biome `addRandomTraitFromBiomeToActor`（ActorManager.cs:764-780）、继承 `rate_inherit`（默认 `rate_birth * 10`，checkDefault，ActorTraitLibrary.cs:1640-1646）、subspecies 出生 trait（Actor.cs:1616-1638）。

**注册时序约束（modding caveat，Verified）**：mod 加载发生在 `Config.game_loaded` 之后（NML WorldBoxMod.cs:87 SmoothLoader 管线），即 **晚于 linkAssets**；且全源码未发现 linkAssets 重跑入口（仅 InitLibraries.cs:57 一次调用）→ mod 后注册的 trait 不会进入 pot_traits_* 自然池（除非 rate 为 0 本就不参与），default_for_actor_assets / opposite 反向索引同样不更新。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `AssetManager.traits.get(id)` | trait 查找（miss → null） | AssetLibrary.cs:27 |
| `AssetManager.traits.add(trait)` | 注册（含 checkDefault：rate_inherit 默认补全） | ActorTraitLibrary.cs:1594-1599 |
| `actor.addTrait(id/trait)` / `removeTrait` / `hasTrait` | 实例操作 | Actor.cs:9189-9306 |
| `actor.traits` | HashSet 直读（只读遍历安全，勿手工增删） | Actor.cs:86 |
| `trait.base_stats` | 数值贡献（进 updateStats） | BaseAugmentationAsset.cs |
| `AssetManager.traits.pot_traits_birth/growup/...` | 加权自然池（linkAssets 产物） | ActorTraitLibrary.cs:1605-1637 |

## Extension Points

1. **注册新 trait**：`AssetManager.traits.add(new ActorTrait{...})` 或 NML ActorTraitBuilder（pattern register-actor-trait / safe-asset-registration）
2. **动态数值**：NML `ActorTraitBuilder.AdditionalBaseStatMethods`（per-actor 动态 BaseStats，跨源 Verified）
3. **生命周期钩子**：直接组合 `action_on_augmentation_add/remove/load` 委托（原版自用同一路线，见 ActorTraitLibrary post_init）
4. **周期效果**：`action_special_effect + special_effect_interval`（被动 buff 类实现）

## Evidence

| 结论 | source | location |
|---|---|---|
| add/remove/has 完整流程 | worldbox | Actor.cs:9140-9306 |
| 持久化 saved_traits 往返 | worldbox | Actor.cs:8850-8867; ActorData.cs:30; TraitTools.cs（loadTraits） |
| stat 管线 merge 顺序与 trait 参与 | worldbox | Actor.cs:1747-1842 |
| 死亡钩子 | worldbox | Actor.cs:6771-6803 |
| 库初始化三阶段 + 加权池 | worldbox | ActorTraitLibrary.cs:28-38, 1578-1638; BaseTraitLibrary.cs（post_init/linkAssets） |
| rate_inherit 默认补全 | worldbox | ActorTraitLibrary.cs:1640-1646 |
| opposite/traits_to_remove 解析 | worldbox | BaseTraitLibrary.cs（fillOppositeHashsetsWithAssets） |
| mod 注册晚于 linkAssets（池不更新） | worldbox + neomodloader | InitLibraries.cs:49-62; NML WorldBoxMod.cs:87-121 |
| NML 动态 stats 注入 | neomodloader | AssetPatches.cs:11-46 |

## Confidence

- Verified：全部机制结论（含跨源 NML 项）
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- ~~Deferred: Save system investigation~~ **已关闭（2026-09-07，→ technical/save.md）**：saved_traits 随 ActorData 内嵌 map.wbox JSON 往返；加载侧 TraitTools.loadTraits 直填集合（id 经 AssetManager.traits.get 重解析，trait id 缺失时静默跳过该条目）；版本间 trait id 改名风险由 SaveConverter.assetIDFixer 仅部分覆盖（其映射表只含原版单位 id，不含 trait id）
- `BaseTrait.base_stats_meta` 与 `BaseStats` 的完整字段/标记语义（stats 系统深挖时补充）
- TraitRainLibrary（trait_rains）与 trait 掉落的交互
- `checkTraitsMod`（likeability 社交修正，ActorTraitLibrary.cs:1648-1670）的调用面
- 成长/出生 mutation 的具体概率权重细节（Randy 层）

## Related Patterns

- [register-actor-trait](../../patterns/assets/register-actor-trait.md) — 注册侧 modding pattern（本系统 add 流程的 modding 包装）
- [safe-asset-registration](../../patterns/assets/safe-asset-registration.md) — 防重复注册（对应 AssetLibrary.add 的 last-wins 行为）
- [register-custom-stat](../../patterns/actor/register-custom-stat.md) — BaseStatAsset 路线（与 trait.base_stats 平行的另一数值路线）
- [clone-modify-asset](../../patterns/assets/clone-modify-asset.md) — 派生已有 trait 的资产路线
