---
title: 生物学 — 架构基线
aliases:
  - Biology Architecture Baseline
---

# Biology — Architecture Baseline

Source: `ref:biology`（生物学 1.0.7，信仰芙芙の博士，无 git）。31 .cs，`Code/` 平铺，namespace `RimWorldMod`。
批次：R2-B0（2026-09-08）。只做架构基线；器官数值/疾病内容/UI 细节留给 B1/B2。Biology 研究分支子节点（B0 记录，父节点 [biology.md](../biology.md) profile）。

## Scope

- 已读全文件：Main / HealthSimulator / OrganSystem / OrganStats / HealthDrainBehaviour / BioExperience / NutritionGuard / BrainStat / FamilyTracker / BioResurrect(关键段) / UnitHealthTab(骨架段) / DiseaseLibrary(框架段+尾部) / OrganInfo/BioHeight/BioHeadHair/OrganTooltip(抽样段)
- 仅扫类名/一级结构：BioBodyDoll / BioDollSkin / OrganEditor / BioGraveTab / LayoutEditor / BioFoldDrag / BioPanelWidth / SexIcon* / BioClickProbe / BioHeadDump / BioHeightRuler / BioFlowLayout / BioText
- 深入疾病定义：0 个完整 profile（DiseaseLibrary 头 200 行按类别采样 + 尾部 API）；符合"≤2 个 disease 深读"边界
- 证据位置均相对 `Mods/Biology_1.0.7/Code/`

## File Responsibility Map

| 类别 | 文件（大小） | 职责 |
|---|---|---|
| Mod lifecycle | Main.cs (8K) | BasicMod&lt;Main&gt;.OnModLoad：读 NML 配置（GetConfig 中文键）→ 依次 Ensure() 各子系统 → 建 2 个常驻 GameObject（DontDestroyOnLoad） |
| Actor state（核心） | HealthSimulator.cs (54K) | 器官/伤口/疾病模拟器 + **唯一权威状态表**（static Dictionary&lt;long,ActorWoundState&gt;）+ Simulate() 全量重算 |
| Organs（定义） | OrganSystem.cs (13K) | Organ/OrganGroup plain class + OrganData 静态目录（47 器官 id、Human/Animal 两套分组计划、物种 substring 分类函数族） |
| Organs（stat 联动） | OrganStats.cs (14K) | 器官缺失/弱化 → Actor stats 乘算修正（health/damage/speed/attack_speed/armor/birth_rate），反推基础值 + statsDirtyVersion 去重 |
| Organs（编辑） | OrganEditor.cs (97K) | OrganEditorUI：器官右键菜单（增删/强化弱化/发色肤色/侵犯/撸管）、摘器官→授 crippled/weak 特质、大脑/骨骼特质双向同步、神之子分娩接管（BabyMaker.makeBabyFromPregnancy prefix） |
| Organs（展示数据） | OrganInfo.cs (22K) | 器官风味文本（血型/智商/体温…，per-actor 定死 rng）→ tooltip |
| Disease definitions | DiseaseLibrary.cs (45K) | **Content Definition**：~120 Disease 静态表（Id/名/描述/类别/Severity/Organs/Infectious/Cancer 标志）+ TraitBinding fluent 表（trait id 或模糊名 → 疾病/强化/惩罚，BindingKind 6 种）+ Find/FindBinding/PickRandom* 线性扫描 |
| Disease runtime | HealthSimulator 内 | DiseaseHit（Def+Severity+来源）、OrganWound（trait 伤，按世界时间每月回 1）、ModDiseases（手术持久病，阶段升级） |
| Health tick | HealthDrainBehaviour.cs (4K) | MonoBehaviour Update（0.2s 节流）：**仅 SelectedUnit** — OrganStats/BrainStat.ApplyStats、无胃清饱食、致命病持续扣血（getHit Divine） |
| Event wear | BioExperience.cs (10K) | 3 个 Harmony postfix（getHit/birthEvent/precalcMovementSpeed）→ 器官磨损写 HpMods（共用通道）；双腿摘除强制移速 0 |
| Persistence（准） | BioResurrect.cs (19K) | Actor.die **prefix** 快照收藏单位（ActorData JSON 深拷贝 + 整条 ActorWoundState）→ Grave 列表；Resurrect 反向注回（实验性） |
| 观察器 | FamilyTracker.cs (5K) | BabyMaker.makeBaby postfix → child→(父,母) 静态表 + 高潮/射精计数 |
| Harmony patches | NutritionGuard / BrainStat / BioHeadHair | 营养 clamp prefix×2+饥饿条 postfix×3；getMaxMana postfix；发色 6 补丁（checkSpriteHead/setHeadSprite/DynamicSpriteCreator.getSpriteUnit/drawPixelsAll/DynamicActorSpriteCreatorUI×2） |
| UI（主） | UnitHealthTab.cs (99K) | UnitWindow.OnEnable postfix → 克隆 WindowMetaTab 注入"生物学"页；tab_action→Rebuild→Simulate；性别图标 5 处 postfix 拦截；Actor.updateStats postfix→OrganStats.ApplyAfterRecalc |
| UI（辅） | BioGraveTab / BioBodyDoll / BioDollSkin / BioHeadHair / BioHeadDump / BioHeight / BioHeightRuler / BioPanelWidth / OrganTooltip / BioText / LayoutEditor / BioFoldDrag / BioFlowLayout / BioClickProbe | 墓地页（同款克隆注入）、立绘贴图层上色、头贴图重绘、调试导出、身高推导、面板动画、悬停提示、NML 本地化回退、布局编辑器（persistentDataPath/biology_layout.txt）、点击探针 |
| UI（性别图标） | SexIconKeeper / SexIconSync / SexIconGuardBehaviour | 双性人图标：多方法重绘拦截 + 每帧廉价守卫 MonoBehaviour |
| Utilities | BioText / Main 静态配置字段 | 本地化键回退；全局开关（AnimalOrgans/OrganWear/NudeDoll/ClickProbe/MenuScale…） |

统计：8 个 Harmony 实例（rimworld_health_tab/experience/stomach/brain/family/resurrect/headhair/divine_birth）、2 个常驻 MonoBehaviour、其余纯静态类。

## Bootstrap

Main.OnModLoad（Main.cs:89-152）顺序：读配置 → UnitHealthTab.Ensure（挂 UnitWindow/updateStats/性别图标补丁）→ BioHeadHair.Ensure（渲染管线 6 补丁）→ BioPanelWidth/BioClickProbe.Ensure → FamilyTracker.Ensure → OrganEditorUI.EnsureDivineBirthPatch → BioExperience.Ensure → BioResurrect.Ensure → NutritionGuard.Ensure → BrainStat.Ensure → new GameObject+HealthDrainBehaviour/SexIconGuardBehaviour（DontDestroyOnLoad）。每个 Ensure 自带 `_patched` 幂等位；每个 Harmony 实例独立 ID、独立 try/catch——逐补丁隔离风格（同 guigu）。

## State Ownership

**权威状态源 = `HealthSimulator._states : static Dictionary<long, ActorWoundState>`**（HealthSimulator.cs:75），按 actor id 键控，进程内存，**无任何持久化**。

- ActorWoundState = Wounds（trait 引发的器官伤，字典 organId→OrganWound）+ Mods（ActorMods：RemovedOrgans/AddedOrgans/HpMods/ModDiseases/Violations/计数器/DivinePregnancy/StatPenalties/FailedOrgans/HairColor/BoneSynced）
- **不是** actor.data custom_data、不是 Actor 组件、不是 NML persistent data
- 旁路状态表（同样 static、同样不持久）：BioExperience._wear（磨损累计，8000 上限）、FamilyTracker._parents（无上限）、BioResurrect._graves/_byId（无上限）、OrganStats._lastMod/_leglessSpeedBase/_recalcVersion（无上限）
- 唯一落入原版持久层的写：`data["intelligence"]`（BrainStat.cs:71-72）与 `data.sex` 回写（HealthSimulator.cs:374）；均随 ActorData 存档

## Actor Lifecycle

- **创建**：无钩子。状态懒创建——首次 Simulate/GetState 时 GetOrCreateState
- **更新**：分三层（见 Update Strategy）
- **死亡**：Actor.die prefix 只为**收藏单位**拍快照（BioResurrect.cs:86-96）；其余单位状态不清理。`BioExperience.Forget()` 已定义但**零调用**（全库 grep 确认）——死亡清理缺失，靠容量上限兜底
- **save**：不存在。器官/疾病/磨损/血缘/墓地全部不写存档
- **load**：不存在。读档后一切 Biology 状态归零重建（transient 疾病用 `new Random(actor.GetHashCode())` 重掷；身高用 actor id 定死推导——BioHeight.cs:7-8 注释明示"不进存档，由 id 推导"的替代哲学）

## Organ Model

- Organ = plain data class（Id+Name+本地化键），**非 asset 非 runtime 实例**；全物种共享一张静态目录（OrganSystem.cs:39-87）
- Actor **不拥有**持久 organ instance；每次 Simulate 由 BuildOrgans 按模板（Human/AnimalGroups）+ 增删集合 + 物种规则（毒牙/泄殖腔/喙/鳃/角…）**现算** OrganHealth 列表（HealthSimulator.cs:234-351）
- organ health = `Hp : int`（0~999，基准 100），由五路合成的瞬时值：woundHp − transient 病 − 通用损伤 + 特质 boost + HpMods − penalties（HealthSimulator.cs:164）
- 多器官：47 id 支持任意增删；左右对称仅剩 eye/wing（GetSymmetricPair，HealthSimulator.cs:939-947）
- 与 Actor HP 的关系：两条通道——① Simulate 时整体 healthRatio 参与器官扣血（反向：血量低→器官差）；② OrganStats 把器官状态乘算回 `stats["health"/"damage"/"speed"…]`（正向），`getHealthRatio()` 显示值受 respiratory_failure/uremia/paralysis 钳制（HealthSimulator.cs:106-115）

## Disease Model

- Disease = 纯静态 definition（content table）；**runtime 无 disease 实例类**，携带形式三种：
  1. `OrganWound`（trait 绑定伤：Disease 引用+HpAtDamage+世界时间戳，月回 1；trait 移除即痊愈，HealthSimulator.cs:809-815）
  2. `DiseaseHit`（transient：每次 Simulate 由 actor-hash 种子重掷、按 healthRatio/年龄概率 roll 3 次，不落状态）
  3. `Mods.ModDiseases`（手术/侵犯持久病：organId→diseaseId，可按器官 Hp 阶段升级——失禁→肛裂→烂屁眼，ApplyStageDisease，HealthSimulator.cs:210-231）
- 注册：无注册机制——静态 List 初始化 + Find() 线性扫 id；TraitBinding 双匹配（id 精确 OR 翻译名双向 Contains，DiseaseLibrary.cs:684-707）是为兼容本地化差异
- 概念面：Severity 有（int）、duration 无、stage 仅 ModDiseases 特例、contagious 有标志（Infectious）**但无传播机制**（只用于随机池筛选）；effect 无独立分发——疾病的全部"效果"就是扣 OrganHealth.Hp + 少数硬编码致命病名（respiratory_failure/uremia/paralysis/internal_bleeding/no_stomach/anal_blockage，HealthDrainBehaviour.cs:44-73）
- 结构样本（未深读内容）：pneumonia（Infectious+GeneralInfection，lung）、fracture（多器官运动系）——仅作定义形状证据

## Update Strategy

**三层混合，核心 = 选中单位单点模拟（selected-actor-only simulation）**：

1. **常驻 5Hz MonoBehaviour**（HealthDrainBehaviour.Update，0.2s 节流）：只处理 `SelectedUnit.unit`——stat 联动、脑 buff、无胃清零、Header 刷新、致命病扣血。不做任何场景扫描
2. **UI 事件驱动**：tab 点击/编辑操作 → Rebuild → `Simulate(actor)` 全量重算（每次 Simulate 重建全部 OrganHealth + 3 次 transient roll + BuildOrgans 物种判定 + substring 物种分类）。Simulate 调用点仅 2 处（UnitHealthTab.cs:1631、OrganInfo.cs:386）
3. **原版事件 postfix**（世界级、全单位但极廉价）：getHit/birthEvent/precalcMovementSpeed 磨损（字典查找+浮点累加，跨档才写状态）、makeBaby 血缘、die 快照、updateStats postfix → OrganStats.ApplyAfterRecalc（getStatsDirtyVersion 去重，NanoObject.cs:129 确认）

复杂度评估：无分帧、无 BatchActors 作业、无世界 tick 循环。全单位成本 = 3 个 postfix 常数开销；重开销只在玩家查看单个单位时发生。**大世界规模天然安全，但"没选中就不模拟"**——疾病不进展、致命病不发作（除非选中）。

## Persistence

- Organ health：**不持久化**（Hp 是 Simulate 瞬时值；HpMods/Removed/Added 持久于内存状态表，读档即失）
- Diseases：不持久化（wound/transient/mod-disease 全失）
- duration/stage：wound 的 DamageTime 世界时间戳参与恢复量计算，但本身不落盘
- Actor 消失时：不清理（Forget 死代码；唯一回收 = _states 满 4000 整表 Clear()、_wear 满 8000 整表 Clear()——HealthSimulator.cs:1023-1025、BioExperience.cs:183）
- 缺失 definition：不适用（疾病全静态内置，无外部资产引用）
- **风险记录：作者完全放弃持久化，属有意设计**（BioHeight/身高与 transient 病的"id 推导"哲学、mod.json 无相关承诺）。读档 = 全部手术/磨损/伤病清零，仅 data.sex 与 data["intelligence"] 两项残留——两项都会在无对应器官状态时产生**孤儿效果**（改回性别/残留智力）

## WorldBox Integration Points

实际依赖（源码证据）：

| API | 用途 | 位置 |
|---|---|---|
| `Actor.traits / addTrait / removeTrait / getTranslatedName` | 特质↔器官双向同步、绑定匹配 | OrganEditor.cs:742, HealthSimulator.cs:354-363 |
| `Actor.updateStats` (postfix) | stats 重建后重应用器官修正 | UnitHealthTab.cs:129-136 |
| `Actor.stats[...]` / `setStatsDirty()` / `getStatsDirtyVersion()` | 乘算修正与去重 | OrganStats.cs:65-95 |
| `Actor.getHit` (postfix+调用) | 磨损累计；致命病扣血（AttackType.Divine） | BioExperience.cs:74, HealthDrainBehaviour.cs:84 |
| `Actor.birthEvent` (postfix) | 分娩磨损 | BioExperience.cs:78 |
| `Actor.precalcMovementSpeed` (postfix) + `_current_combined_movement_speed` | 走路磨损 + 无腿强制移速 0（绕原版保底 1） | BioExperience.cs:83-84, 140 |
| `Actor.setNutrition / addNutritionFromEating / getMaxNutrition / getMaxMana` | 胃/脑系统 clamp 替换 | NutritionGuard.cs:26-32, BrainStat.cs:30 |
| `Actor.data`（`data["intelligence"]`、`data.sex`、`data.nutrition`） | 仅有的持久写点 + 饱食清零 | BrainStat.cs:72, HealthSimulator.cs:374, HealthDrainBehaviour.cs:25 |
| `Actor.die` (prefix) | 收藏单位快照 | BioResurrect.cs:76 |
| `ActorManager.createNewUnit` | 复活重建单位 | BioResurrect.cs:148+ |
| `BabyMaker.makeBaby / makeBabyFromPregnancy` | 血缘记录 / 分娩接管 | FamilyTracker.cs:20, OrganEditor.cs:1515 |
| `Actor.checkSpriteHead / setHeadSprite / clearSprites / clearLastColorCache`、`DynamicSpriteCreator.getSpriteUnit/drawPixelsAll`、`DynamicActorSpriteCreatorUI.getSpriteHeadForUI/getUnitSpriteForUI` | 头发重绘制管线（最深耦合点） | BioHeadHair.cs:154-169 |
| `UnitWindow.OnEnable`、`WindowMetaTab`（克隆+`tabs._tabs.Insert`+`addTabContent`）、`SelectedUnitTab.showStatsGeneral`、`UnitBarsElement.showHunger`、`TooltipLibrary.showActorBars`、`PossessionUnitInfo.showForUnit`、`Tooltip.show` | UI 注入与图标/饥饿条拦截 | UnitHealthTab.cs:75,1002-1061; NutritionGuard.cs:35-45 |
| `SelectedUnit.isSet()/unit` | 选中单点模拟入口 | HealthDrainBehaviour.cs:15 |
| `MapBox.instance.getCurWorldTime()` / `World.world.units.get(id)` | 伤口恢复计时 / id→名字 | HealthSimulator.cs:1003-1011, FamilyTracker.cs:99 |

未用：AssetManager 注册、GodPower、custom_data 大规模存储、NML Feature、TabManager.CreateTab（走克隆注入而非 CreateTab——同 actorhistory/familytree 路线）。

## Performance Risks

1. **Simulate 全量重算 + 大量分配**：每次 Rebuild 新建 BodyHealth/全部 OrganHealth/List/Dictionary + `PickRandomGeneral` 每次调用线性扫 120 病病表建池（DiseaseLibrary.cs:739-753）。单次可接受（<1ms 级），但 Rebuild 由 tab 点击/编辑/0.2s Header 路径（仅数值）触发，且 `RefreshAfterEdit` 连跑两次 Rebuild（UnitHealthTab.cs:1677-1678）
2. **BuildOrgans 物种 substring 分类**：每次 Simulate 对动物 asset.id 做 100+ 次 `Contains`（GetAnimalKind 等），无缓存（仅 LogInfo 级浪费；HealthSimulator.cs:265-266 每次还打日志）
3. **`Main.LogInfo` 高频刷日志**：Simulate/磨损/扣血路径大量无条件 LogInfo——NML 日志 IO 在大世界选中单位时是实际开销
4. **静态表无淘汰**：_states(4000 cap)、_wear(8000 cap) 满则**整表清空**——不仅是内存策略，还会把活跃单位的手术/磨损状态一起抹掉（功能性 bug 面）；_parents/_graves/OrganStats 三表**无上限无清理**，长寿世界单调增长
5. **updateStats postfix 全单位触发**：每单位每次 stats 重建都进 ApplyAfterRecalc（有 version 去重，未参与单位早退，实际便宜）——依赖 getStatsDirtyVersion 不变式，属脆弱优化

## Compatibility Risks

1. **渲染管线深耦合**：6 个贴图补丁 + 防内联双挂（checkSpriteHead/setHeadSprite），游戏版本升级或渲染类 mod（中文名、立绘类）冲突面最大
2. **性别图标 5 处 postfix + 每帧守卫**：与其他改 UI 的 mod 竞争同一批私有字段（icon_right/_icon_sex 反射），画面拉锯
3. **setNutrition/addNutritionFromEating prefix 返回 false 完全替换**：任何同样 hook 营养的 mod（如食谱类）会被否决
4. **makeBabyFromPregnancy prefix 返回 false**：替换原版分娩逻辑（神之子/强化子宫双胞胎），生育类 mod 冲突点
5. **状态不持久 + id 复用**：读档后 _states 若残留旧 id 数据（跨档同 session 切世界），新单位可能继承前一个世界的器官状态——GetOrCreateState 无世界校验
6. **TraitBinding 模糊名匹配**（双向 Contains）：本地化 mod 改特质译名可能误匹配/漏匹配绑定

## Unknowns（留给 B1/B2）

- OrganEditor 97K 的完整手术后果矩阵（RemoveTrait 映射、CheckWeakenedToZero、ApplyRemoveDisease）——B1
- UnitHealthTab RenderBody/BioBodyDoll 立绘贴图层结构与 OrganInfo 风味文本全集——B1
- DiseaseLibrary 中段 ~400 行 TraitBinding 全集（哪些原版 trait 绑病）与疾病数量精确统计——B2
- transient roll 的 `actor.GetHashCode()` 跨 session 稳定性（Unity/Mono 对 Actor 的默认 GetHashCode 是否地址基）——影响"同单位每次开档病情一致"体验，非正确性问题
- BioResurrect.Resurrect 的 id 索引改写完整链（units dict 操作）与失败回退——复活机制单列风险
- LayoutEditor/BioFoldDrag 的 biology_layout.txt 格式（UI 偏好持久化，非游戏数据）

## Pattern Candidates（仅记录，不新增正式 Pattern）

- `selected-actor-singlepoint-simulation`（候选：以"仅选中单位"换零常驻成本的世界级健康模拟）——最强候选，无先例
- `static-dict-state-capacity-wipe`（候选：static Dictionary 容量上限整表清空替代逐条淘汰）——含已知副作用，价值在反面教训
- `derive-from-id-instead-of-persistence`（候选：身高/transient 病由 actor id 确定性推导，规避存档字段）——与 actor-data-key-state-store 互补的对立面
- `trait-fuzzy-name-binding`（候选：本地化健壮的 trait→效果绑定，id 优先+译名模糊回退）
- `post-stat-recalc-reapply`（候选：updateStats postfix + 脏版本去重的"重建后再修正"stat 集成）——与 xuanmen 的 updateStats Transpiler 是同一问题的两种解法，对比价值高
- `death-snapshot-preserve-mod-state`（候选：die prefix 快照 data+mod 状态供复活）——familytree 死亡快照的进阶版（含 mod 自有状态搬迁）

（B1 增补候选与确认状态见同分支 organs-health.md 的 Pattern Candidates。）
