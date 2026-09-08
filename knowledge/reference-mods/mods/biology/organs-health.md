---
title: 生物学 — 器官与健康机制
aliases:
  - Biology Organ Health Mechanics
---

# Biology — Organ / Health Mechanics

Source: `ref:biology`（生物学 1.0.7）。Biology 研究分支子节点（B1 记录，父节点 [biology.md](../biology.md)）；mod 侧证据相对 `Mods/Biology_1.0.7/Code/`，原版侧为 WorldBox 反编译源码。
批次 R2-B1（2026-09-08）。输入：OrganEditor.cs 全手术链（symbol map 定向阅读）+ OrganStats/HealthSimulator 复核 + BioResurrect 复活链 + UnitHealthTab Rebuild 入口。原版侧验证：`BaseSimObject.updateStats()` 在每次重建开头 `stats_dirty_version++`（BaseSimObject.cs:288-293，字段声明 NanoObject.cs:13）。本批不触 DiseaseLibrary 内容表与 BodyDoll 渲染。

## State Composition

器官 HP 是**纯计算值，无持久身份**。每次 Simulate 五路合成（HealthSimulator.cs:143-176）：

```text
Static Definition（OrganData 目录 + 分组模板 + 物种规则）
    + ActorWoundState（内存独占）:
        Wounds        —— trait 绑定伤（organId → OrganWound：Disease+HpAtDamage+世界时间戳）
        Mods.RemovedOrgans / AddedOrgans / HpMods / ModDiseases / FailedOrgans
        （+ Violations/计数器/DivinePregnancy/StatPenalties/HairColor/BoneSynced）
    + Actor traits（经 DiseaseLibrary.TraitBinding → boosts/penalties/wounds）
    + Actor data（healthRatio 反向参与：血量低 → 器官差；data.sex 决定性器官模板）
        ↓ BuildOrgans（每次重建全量实例化 OrganHealth）
oh.Hp = clamp( woundHp − transientSev − extra + boost + hpMod − penalty, 0, 999 )
```

要点：

- **transient 疾病根本不是状态**——每次 Simulate 用 `new Random(actor.GetHashCode())` 重掷（HealthSimulator.cs:103-104,129-140），同 session 确定性、跨 session 不保证（与 BioHeight 的 id 推导不同源，后者跨 session 稳定）
- **woundHp 的"持久性"只在内存**：`GetWoundHp` 按世界时间每月回 1（HealthSimulator.cs:995-1001），DamageTime 是唯一时间维状态
- `extra = (1−healthRatio)*100 − tSev` 把原版血量反向灌入器官（战斗伤害体现为全身器官随机掉血）
- 双腿判定（IsLegless）只读 `RemovedOrgans.Contains("leg")`——弱化到衰竭的腿**不会**触发移速归零（OrganStats.cs:160-168 与 BioExperience.cs:165-173 同一判定），与 IsInactive（removed ∨ HpMods≤−100，OrganEditor.cs:604-610）的"衰竭≡摘除"语义**不一致**：后果结算认衰竭，移动限制只认摘除

## Surgery Flow

入口统一：`OrganClickTrigger.OnPointerClick → OpenOrganMenu`（OrganEditor.cs:11-19,92-153），按钮闭包直调手术函数，收尾统一 `Refresh() → UnitHealthTab.RefreshAfterEdit() → Rebuild()×2 → Simulate + Sync*`（OrganEditor.cs:1605-1611, UnitHealthTab.cs:1674-1679,1629-1642）。

**链 1 — 摘除（DeleteOrgan, OrganEditor.cs:534-553）**

```text
RemovedOrgans.Add + 清 HpMods/ModDiseases/FailedOrgans（leg→foot 级联，不重复结算）
→ ApplyRemoveConsequence(631-660):
   FatalOrgans{heart,brain,blood,head,neck,gills} → KillActor: getHit(health+1, Divine) 即死
   有 RemoveTrait 映射 → TryAddTrait(eyepatch/crippled/mute/infertile/ugly, 512-526)
     + crippled 特例: PinCrippledFracture 把 fracture 伤钉死在被摘器官上
       （短路 HasWoundFor，防 trait 系统随机把病挂到完好肢体，HealthSimulator.cs:914-936）
   ApplyRemoveDisease: RemoveDisease[organ]=[病,宿主] → ModDiseases[宿主]=病（557-601）
   双眼皆盲: IsInactive(other eye) → ModDiseases["head"]="blindness"
   无映射兜底 → TryAddTrait("weak")
→ CheckPairRemoval(678-716): IsInactive(肺/肾/四肢/脊椎/腹/胃/肛门)
   → 写致命 ModDiseases(respiratory_failure/uremia/paralysis/internal_bleeding/no_stomach/anal_blockage)
   + ApplyDrain: getHit(health×ratio, Divine) 首次扣血
→ GetRemoveDamageRatio 按重要性再 getHit(0.15~0.40)
→ SyncMuscleTrait → Refresh → Rebuild → 下个 0.2s tick OrganStats.ApplyStats
```

**链 2 — 强化/弱化（StrengthenOrgan/WeakenOrgan, 1089-1224）**

```text
HpMods ±10（×10 档 ±100，弱化下限 −1000）
强化跨 30 线一次性授 StrengthenTrait 特质（eagle_eyed/titan_lungs/fertile…，51-90）——不回退
弱化 ≤−100 → CheckWeakenedToZero(615-629): FailedOrgans 记账去重 → ApplyRemoveConsequence（≡摘除）
   回升 >−100 → FailedOrgans.Remove —— 代价结算可重复武装（先弱到死线付费，强化解除，再弱再付费）
弱化 ~50% 概率挂 WeakenDiseases 随机病（已挂不覆盖，1192-1200）
RefreshLimbTraits(1130-1151): leg/foot 任一 ≥30 ⇄ agile/weightless 授予/剥除（仅手术路径调用）
SyncMuscleTrait(761-798): 肌肉 hm≥150→strong / ≤−80→weak / 中间双清；摘除肌肉≡weak；
   天生 strong 且 hm<150 → 强推 150（注释自认"永远弱化不下去"的坑，只在此函数内）
```

**链 3 — 恢复（AddOrgan, 1226-1236 + SyncRestoredTraits, 881-942）**

```text
AddedOrgans.Add / RemovedOrgans.Remove + 清 HpMods/ModDiseases/FailedOrgans（"重长出来的不带旧伤"）
→ Refresh → Rebuild 时 SyncRestoredTraits:
   RemoveTrait 反向分组（trait → 其全部源器官）: 组内所有器官存在且 Hp≥100 → removeTrait
   （缺任一肢体则保留 crippled；全恢复才摘）
   RemoveDisease 反向分组: 组全满血 → ModDiseases.Remove(宿主)
   双眼 ≥100 → 摘 blindness；肛门/阴道满血 → 摘失禁/激素失衡
```

结构共性：**所有手术 = 只改 ActorWoundState 的稀疏通道，器官本体永远不直接写**——器官 HP 单一出口是 Simulate。`surgery-as-state-mutation-plus-stat-rebuild` 成立。

次要语义注记（记录不展开）：IsLegless 只认摘除不认衰竭（弱化到 0% 的腿仍能走）；WeakenDiseases 用 `new Random()` 非种子（同帧同结果）；ApplyDrain 命名"持续扣血"实际只打一次（真持续靠 HealthDrainBehaviour 按选中重查）。

## Stats Feedback

双通道互补（OrganStats.cs）：

1. **ApplyStats（5Hz，仅选中单位，HealthDrainBehaviour.cs:20）**——写入通道：`baseVal = cur/(1−lastMod)`（5% 下限守卫 + ×20 兜底），`stats[st] = baseVal×clamp(1−nm, 0.05, …)`，写完 `setStatsDirty()`。这是**注定被覆盖的瞬态写**，目的是让面板立刻可见
2. **ApplyAfterRecalc（updateStats postfix，UnitHealthTab.cs:129-136）**——权威通道：版本守卫 `getStatsDirtyVersion()` 与上次相同则跳过；不同则在**纯净基础值**上直接乘 factor，更新 `_recalcVersion`。原版每次重建开头 `stats_dirty_version++`（BaseSimObject.cs:291，已验证）→ **每次重建恰好重应用一次，无重复叠加**

闭环：ApplyStats 写+置脏 → 原版重建清空重并 → postfix 在纯基值上重放 → 稳态。反推公式只在"值还没被重建"的窗口内成立。

- 叠加方向不对称：削减 clamp(0.05,2)，加成（血液/肌肉/birth_rate）上不封顶（OrganStats.cs:86-88,145-147）——无限强化流
- 双腿摘除双保险：stats["speed"]=0（显示层）+ precalcMovementSpeed postfix 直接写 `_current_combined_movement_speed=0`（真移速，绕过原版末尾"combined<1 抬到 1"保底，BioExperience.cs:127-141）；`_leglessSpeedBase` 记录断腿前基础移速供恢复反推（OrganStats.cs:121-141）
- baseVal<1 强制抬 1（OrganStats.cs:144）——低基础值单位（部分动物）上修正失真
- **脆弱点**：反推假设 cur 仍含 lastMod、且无第三方写同一 stat。任何其他 mod 在两次 Biology 应用之间写 stats["health"/"speed"]（自己的 postfix/直接赋值，尤其同为 updateStats postfix 且补丁顺序未定），反推基值即被污染——误差按乘法传播，非叠加崩溃但单向漂移，难以察觉

## Trait Interaction

Biology **不把器官状态存进 trait**；trait 全部是器官状态转移的**单向输出**，分三类：

| 类型 | 时机 | 例子 | 可逆性 |
|---|---|---|---|
| 摘除惩罚 | ApplyRemoveConsequence 一次性 | eyepatch/crippled/mute/infertile/ugly | 组全满血自动摘（SyncRestoredTraits） |
| 强化授予 | 跨 30 线一次性 | eagle_eyed/titan_lungs/fertile/agile+weightless | **不可逆**（不回 30 线摘除；agile/weightless 仅手术路径剥除） |
| 阈值同步 | 每次 Rebuild 连续判定 | strong/weak（肌肉150/−80）、genius/stupid（脑显血70/150）、giant/tiny（骨显血150/80） | 双向，对抗对立特质（先摘后加，TryAddTrait 回读确认，968-983,1055-1083） |

反向路径两条：trait 被移除 → 对应伤口立即痊愈（ApplyTraitWounds 清 TraitKey 不存在的 wound，HealthSimulator.cs:809-815）；器官恢复 → trait 被移除（SyncRestoredTraits）。

**读档后 trait 成为事实上的部分持久层**——重建行为分三类（关键发现）：

- **自动重建**（trait → HpMods 回填）：genius → PrimeBrainMods 每次重建前把空 HpMods["brain"] 播回 30（OrganEditor.cs:824-835）；giant/tiny → BoneSynced 丢失后首视角反向回填骨 HpMods（1042-1053）
- **自动痊愈**（trait 被摘）：摘除惩罚 trait 读档后仍在 saved_traits，但器官全满 → 首次打开生物学 Tab 即被 SyncRestoredTraits 摘掉——**不查看就永不清**
- **永久孤儿**（trait 留存、状态无痕、不重建不可逆）：强化授予 trait（titan_lungs 等）；肌肉 strong 的 150 回填只在 SyncMuscleTrait 内、而它**不在 Rebuild 路径**（仅手术调用，对比 UnitHealthTab.cs:1629-1642 只调 Prime/SyncBrain/SyncBone/SyncRestored）→ 读档后 strong 挂着、肌肉 100%，直到玩家对肌肉做任意手术才被推回 150

同类失配不止 trait 通道：DivinePregnancy 存于 ActorMods（易失），怀孕中途存读档即全失——神之子静默降级为原版普通分娩（ActorMods 全失 + ConsumeDivinePregnancy 返 false → OnPregnancyFinish 放行原版，OrganEditor.cs:1527-1544）。

`trait-backed-persistent-effect-with-ephemeral-runtime-state` 作为候选不成立——真实形态是**反模式**：persistent trait + nonpersistent backing state mismatch（三类孤儿见 Anti-pattern Candidate）。

## Death / Load Behaviour

| 节点 | 行为 | 证据 |
|---|---|---|
| 死亡（收藏单位） | die **prefix** 快照：ActorData JSON 深拷贝 + **整条 ActorWoundState 引用**入 Grave；_states 中原条目**不清**（复活时 PutState 同 id 覆盖） | BioResurrect.cs:76-96,112-117 |
| 死亡（非收藏） | 什么都不做：状态留 _states 至 4000 上限整表清空；`BioExperience.Forget()` 零调用（死代码） | B0 已证 |
| disposal | 无钩子 | — |
| 复活 | createNewUnit(同 asset) → **CopyData 逐字段拷贝、跳过 custom_data_* 六容器**（JSON 反序列化容器内字典为 null → BatchActors.updateStats 每帧 NRE → 时间冻结——作者记录的第一版事故）→ units.dict 手术：删 freshId、写回原 id（占用则保新 id 断关系）→ Relink 七引用 → RestoreTraits（saved_traits 逐个 addTrait）→ **RestoreOrgans: PutState(原id, 快照)** → RecrownIfKing → setStatsDirty | BioResurrect.cs:170-236,254-276,335-342 |
| 读档 | _states/_wear/_parents/_graves 全失；ActorData 残留 saved_traits/data.sex/data["intelligence"] 三项 Biology 痕迹 | B0+B1 |

复活链的器官复用 = **同引用整条搬回**（非拷贝），手术/磨损/伤情/计数器全部原样回来——这是该 mod 唯一真正的"器官状态持久化"，且只覆盖死亡前被收藏的单位。

复活链风险（作者自标实验性）：`units.dict` 直接改写与 BatchActors 并行作业无同步；CopyData 跳过 custom_data_* 六容器是牺牲 mod 数据换不崩（含其他 mod 写入该容器的数据）；原 id 被占用时静默降级保新 id、断全部关系。

## Cross-Mod Note — updateStats 扩展的两种解法

同一问题：自定义 stat 修正如何穿越原版 `updateStats()` 的 stats.clear()+全量重并（traits.md 已证 Actor.updateStats 每次重建合并 subspecies/clan/culture/status/trait base_stats）。

| 维度 | xuanmen-daojie（RealmSystem.cs:843 Transpiler） | Biology（UnitHealthTab.cs:133 postfix + OrganStats） |
|---|---|---|
| 注入位置 | **重建管线内部**（normalize 前注入境界加成，labels 迁移） | **重建管线之后**（postfix 重放） |
| 存活性 | 构造性存活：修正成为重建产物的一部分 | 重放式存活：依赖"每次重建 bump 版本 + 恰好重放一次" |
| 持久化 | data 双轨（Get 走 stats / Set 走 data），跨存档 | 内存独占，读档即失 |
| 修正形态 | 加法注入（在 merge 流内加值） | 乘法重放（factor 乘基值，反推上次修正） |
| 脆弱面 | IL 结构耦合（labels/局部序，游戏更新高危） | 代数不变量耦合（无第三方写同 stat、版本单调），IL 稳定 |
| 共存性 | Transpiler 在方法体内先跑，Biology postfix 在外层后跑：Biology 反推的"基值"已含 xuanmen 确定性贡献——只要对方贡献是重建确定的，反推仍正确 | |

结论：两种方案不互斥，但 postfix-reapply 把正确性押在**独占写假设**上；Transpiler 把正确性押在 **IL 不变**上。组合安装时 Biology 的乘法层在 xuanmen 加法层之上，语义可共存。

（跨 mod 引用一律使用 stable ID `ref:xuanmen-daojie`，不建立横向 markdown 链接。）

## Pattern Candidates

- `computed-organ-state-from-sparse-wounds` —— **确认候选**（五路合成、器官无持久身份、单一 Simulate 出口）
- `post-stat-recalc-reapply` —— **确认候选**（版本守卫语义已对源码验证；与 `transpiler-stat-injection` 构成对偶，建议将来成对入档）
- `surgery-as-state-mutation-plus-stat-rebuild` —— **确认候选**（三条手术链同构）
- `failure-equivalence-guard`（候选：摘除≡衰竭统一后果 + FailedOrgans 可重武装的去重结算）——小而完整

## Anti-pattern Candidate

`persistent-trait-ephemeral-backing-mismatch` —— 三类孤儿实证（强化 trait / muscle-strong / DivinePregnancy），入档价值高（多 mod 通用教训：用原版持久层表达 mod 状态时，必须保证读档后能从该层完整重建或显式清理）。

## Unknown / Deferred

- DiseaseLibrary.TraitBinding 全表（哪些原版 trait 绑哪种病/boost/penalty）+ 疾病数量精确统计
- wound 月恢复节奏与 RegenPerMonth 是否有非 1 来源；stage disease 升级表全集
- transient 的 `actor.GetHashCode()` 跨 session 稳定性（疑地址基 → 重启后病情变化；BioHeight 走 id 是稳的，两者哲学不一致）
- 神之子/强化子宫分娩链（TwinChanceOf/BirthWithUterusMod/MakeExtraBabies）与 birth_rate stats 交互
- FamilyTracker._parents / OrganStats._lastMod 等辅助表无上限增长（B0 已记，B2 归并确认）
- Actor.updateStats override 调 base（版本递增点）未逐行验证——BaseSimObject.cs:291 + traits.md 的 Actor 全量重并记录支撑，置信高
