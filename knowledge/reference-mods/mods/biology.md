---
title: 生物学
aliases:
  - biology
  - Biology
---

# 生物学（Biology）

## Identity

- Name: 生物学 1.0.7（信仰芙芙の博士，无 git）
- Source ID: `ref:biology`
- Dir: `Biology_1.0.7`（31 .cs，`Code/` 平铺，namespace `RimWorldMod`；证据位置相对 `Mods/Biology_1.0.7/Code/`）
- Confidence: Mostly Verified

## Purpose

器官系统与健康模拟：47 器官瞬时合成状态、~120 疾病静态表、手术状态突变链（摘除/强化弱化/恢复）、家族追踪与收藏单位复活链、生物学 UI tab 与立绘贴图重绘。核心设计：**零持久化**——全部运行时状态收敛于进程内存，读档即失（有意设计）。

## Systems

- Primary: Actor, Traits, UI
- Secondary: Events, Save/Persistence, Mod Lifecycle

## Architecture Summary

Biology 不给 WorldBox Actor 增加任何持久组件：全部运行时状态收敛于 `HealthSimulator._states : static Dictionary<long, ActorWoundState>`（进程内存、无持久化、4000 上限整表清空），按 actor id 键控。器官没有 runtime 实例——每次 Simulate 由静态 OrganData 目录（47 器官）+ 分组模板与物种规则 + ActorWoundState 稀疏通道（Wounds/Removed/Added/HpMods/ModDiseases）+ traits + healthRatio 五路合成瞬时 OrganHealth。疾病同样是纯静态 content 表（~120 Disease + TraitBinding），runtime 三种携带形态：OrganWound（trait 绑定伤）/ DiseaseHit（transient 重掷）/ ModDiseases（手术持久病）。

更新三层混合：5Hz MonoBehaviour 只处理选中单位（stat 联动、致命病扣血）；UI 事件驱动 Simulate 全量重算——重开销只在玩家查看单个单位时发生；世界级 postfix 极廉价（磨损/血缘/死亡快照/updateStats 重放）。大世界规模天然安全，但"没选中就不模拟"（疾病不进展、致命病不发作）。

对外影响面：OrganStats 以乘算修正 stats，靠 updateStats postfix + 脏版本守卫在每次原版重建后权威重放（5Hz 写入只是注定被覆盖的瞬态显示层）；trait 全部是器官状态的单向输出，读档后 saved_traits 残留使其成为事实上的部分持久层，与易失 backing state 失配形成孤儿（反模式）。集成最深处在 UI/渲染管线：克隆 WindowMetaTab 注入"生物学"页、6 个头贴图补丁、性别图标拦截、营养/分娩 prefix 替换。

## Key Implementation

- `Main.cs:89-152` — OnModLoad 有序初始化（读 NML 配置 → 逐子系统 Ensure → 2 个常驻 DontDestroyOnLoad GameObject）；每个 Ensure 自带 `_patched` 幂等位
- `HealthSimulator.cs:75` — 唯一权威状态表 `static Dictionary<long, ActorWoundState>`（4000 上限整表清空）
- `HealthSimulator.cs:143-176` — Simulate 五路合成器官 HP（woundHp − transient − extra + boost + hpMod − penalty）
- `UnitHealthTab.cs:75,1002-1061` — UnitWindow.OnEnable postfix 克隆 WindowMetaTab 注入"生物学"页
- `UnitHealthTab.cs:129-136` — updateStats postfix + 脏版本守卫权威重放（OrganStats）
- `BioResurrect.cs:76-96,170-236` — die prefix 快照收藏单位 + 复活链（units.dict 手术 + PutState 同引用整条搬回）

## Techniques

8 个独立 Harmony 实例逐补丁隔离（rimworld_health_tab / experience / stomach / brain / family / resurrect / headhair / divine_birth）、静态字典状态（零持久化）、选中单位单点 5Hz 模拟 + UI 事件全量重算、updateStats postfix 版本守卫重放、克隆 WindowMetaTab UI 注入、渲染管线 6 补丁贴图重绘、die prefix 死亡快照

## WorldBox Usage

Actor.{traits, addTrait, removeTrait, updateStats, getHit, birthEvent, precalcMovementSpeed, setNutrition, addNutritionFromEating, die} / Actor.stats / setStatsDirty / getStatsDirtyVersion / Actor.data（data.sex, data["intelligence"], data.nutrition）/ ActorManager.createNewUnit / BabyMaker.{makeBaby, makeBabyFromPregnancy} / SelectedUnit.unit / UnitWindow.OnEnable / WindowMetaTab / SelectedUnitTab.showStatsGeneral / UnitBarsElement.showHunger / TooltipLibrary.showActorBars / PossessionUnitInfo.showForUnit / MapBox.instance.getCurWorldTime / World.world.units.get(id) / DynamicSpriteCreator 渲染管线（checkSpriteHead / setHeadSprite / drawPixelsAll 等 6 处）

## NeoModLoader Usage

- BasicMod&lt;T&gt;.OnModLoad / GetConfig（中文键）（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| UnitWindow.OnEnable | Postfix | UnitHealthTab.cs:75,1002-1061 | 克隆 WindowMetaTab 注入生物学页 |
| Actor.updateStats | Postfix | UnitHealthTab.cs:129-136 | stats 重建后权威重放器官修正 |
| Actor.getHit / birthEvent / precalcMovementSpeed | Postfix | BioExperience.cs:74-84 | 器官磨损累计（世界级廉价路径） |
| Actor.setNutrition / addNutritionFromEating | Prefix(替换) | NutritionGuard.cs:26-32 | 无胃清零、营养 clamp |
| Actor.getMaxMana | Postfix | BrainStat.cs:30 | 脑 buff |
| BabyMaker.makeBaby | Postfix | FamilyTracker.cs:20 | 血缘记录 |
| BabyMaker.makeBabyFromPregnancy | Prefix(替换) | OrganEditor.cs:1515 | 神之子分娩接管 |
| Actor.die | Prefix | BioResurrect.cs:76 | 收藏单位快照 |
| checkSpriteHead / setHeadSprite 等 6 处 | Postfix | BioHeadHair.cs:154-169 | 头发重绘管线（最深耦合点） |

未用：AssetManager 注册、GodPower、custom_data 大规模存储、NML Feature、TabManager.CreateTab（走克隆注入而非 CreateTab——同 ref:actorhistory / ref:familytree 路线）。

## Current Findings

- 状态所有权 = `static Dictionary<long, ActorWoundState>`（HealthSimulator.cs:75）——不是 actor.data custom_data、不是 Actor 组件、不是 NML persistent data；旁路静态表（_wear/_parents/_graves 等）同样不持久化
- 模拟入口 = 选中单位单点：5Hz HealthDrainBehaviour（0.2s 节流）+ UI 事件 Simulate 全量重算；**没选中就不模拟**（疾病不进展、致命病不发作）
- 无 Biology 持久化：读档后手术/磨损/伤病/血缘/墓地全失，仅 `data.sex` 与 `data["intelligence"]` 两项残留（且各自产生孤儿效果）
- 器官 HP 是计算值而非持久对象状态：每次 Simulate 五路合成（wound − transient − extra + boost + hpMod − penalty），器官无持久身份、单一出口
- stats 集成双通道：5Hz 瞬态写（注定被覆盖的显示层）+ updateStats postfix 权威重放（脏版本守卫，每次重建恰好重放一次）
- 所有手术 = 纯状态突变：摘除/强化弱化/恢复三链同构，只改 ActorWoundState 稀疏通道，器官 HP 永远经 Simulate 重建
- persistent trait × ephemeral backing state 失配（反模式）：强化 trait / muscle-strong / DivinePregnancy 三类读档孤儿
- 唯一真正的"器官状态持久化"是复活链：die prefix 快照收藏单位 → PutState 同引用整条搬回（仅覆盖收藏单位）

## Reusable Ideas / 反模式

- "仅选中单位"换零常驻成本的世界级健康模拟——大世界天然安全
- updateStats postfix + 脏版本守卫的"重建后重放"stat 集成——与 ref:xuanmen-daojie 的 Transpiler 注入构成同一问题的对偶解法（共存性分析见 organs-health.md）
- **反模式**：persistent trait × ephemeral backing state 失配——用原版持久层表达 mod 状态时，必须保证读档后能从该层完整重建或显式清理
- 静态表容量上限整表清空会把活跃单位状态一起抹掉（功能性 bug 面，非内存策略）

## Research Map

- [architecture.md](biology/architecture.md) — B0 架构基线：文件职责 / bootstrap / 状态所有权 / actor 生命周期 / 器官与疾病模型（架构级）/ 更新策略 / 持久化 / WorldBox 集成点 / 性能与兼容风险
- [organs-health.md](biology/organs-health.md) — B1 器官与健康机制：状态合成 / 手术链（摘除/强化弱化/恢复）/ stats 反馈 / trait 交互 / 死亡与读档行为

推荐阅读顺序：architecture.md → organs-health.md。B2 Disease Lifecycle 完成后在此增加子节点（不预建空文件）。

## Research Status

研究范围：器官系统 / 健康模拟 / 疾病框架 / 手术与特质联动 / Biology UI tab。

- B0 Architecture Baseline — COMPLETE（2026-09-08）
- B1 Organ / Health Mechanics — COMPLETE（2026-09-08）
- B2 Disease Lifecycle — PLANNED（范围：DiseaseLibrary 中段 TraitBinding 全表 + HealthSimulator wound/transient/stage 三态终态 + BioExperience 磨损数值 + BioResurrect/BioGraveTab 复活链；~120 病表抽样统计——类别分布/严重度/传染标志比例，不逐条 profile）

## Pattern Candidates

- `selected-actor-singlepoint-simulation`（B0，最强候选，无先例）
- `computed-organ-state-from-sparse-wounds`（B1 确认）
- `post-stat-recalc-reapply`（B1 确认；与 `transpiler-stat-injection` 构成对偶，建议将来成对入档）
- `surgery-as-state-mutation-plus-stat-rebuild`（B1 确认）
- `failure-equivalence-guard`（B1，摘除≡衰竭统一后果 + FailedOrgans 去重结算）
- `static-dict-state-capacity-wipe` / `derive-from-id-instead-of-persistence` / `trait-fuzzy-name-binding` / `death-snapshot-preserve-mod-state`（B0 记录）
- Anti-pattern：`persistent-trait-ephemeral-backing-mismatch`（B1 实证，多 mod 通用教训，入档价值高）

## Evidence

- HealthSimulator.cs:75,143-176 — 状态表与五路合成
- Main.cs:89-152 — bootstrap 顺序与幂等位
- UnitHealthTab.cs:75,129-136,1002-1061 — UI 注入与 stats 重放
- OrganStats.cs:65-95 — 乘算修正与版本去重
- BioResurrect.cs:76-96,170-236 — 死亡快照与复活链
- OrganEditor.cs:534-553,1089-1224,1226-1236 — 三条手术链

## Deferred

- B2 详细待确认项：见 [organs-health.md](biology/organs-health.md) 的 Unknown / Deferred（单一来源，不重复两份）
- BioBodyDoll / RenderBody 立绘渲染层与 OrganInfo 风味文本全集（B0 列为 B1 项、B1 实际未触——仍开放）
- pattern 入档决策留待 R2-6 Cross-Mod Synthesis 汇总
