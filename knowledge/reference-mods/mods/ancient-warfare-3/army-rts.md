---
title: AW3 军队 RTS 控制
aliases:
  - ancient-warfare-3-army-rts
---

# Ancient Warfare 3 — 军队 RTS 控制（R3-AW3 C2a）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批以 `Code/core/lineage/ArmyRtsControllerService.cs`（7,283 行单文件，6 个类型）为主体，覆盖调度编排、命令流、移动/战斗、可视化与多人投影。核心段（~14 区段）逐行 Verified；其余区段经全成员签名枚举 + 重点段精读覆盖，状态见 Known Gaps。

## Scope

- 覆盖：ArmyRts 状态机与调度、命令管线、战斗所有权仲裁、战略路线与海运降级、可视化、replica 投影
- 不覆盖：天命/外交/封臣域（→ C2b 批）、ArmyRtsTransportService 主体细节（签名级，归 C2b/C5）、导演服务 KingdomWarDirectorService 内部（属 coalition 域）

## 架构总览

- **单文件 6 类型**（Code/core/lineage/ArmyRtsControllerService.cs）：`ArmyRtsControllerRecord`（Mission+State 对，:16-20）；`ArmyRtsControllerRules` 纯静态规则（:22-291，常量 `MaximumControllersPerFrame=32`、`StrategicArrivalRadius=2`）；`ArmyRtsControllerWorkIndex`（:353-517，记录字典 + **双优先级队列**）；`ArmyRtsMissionIndex`（:551-670，按 Kingdom/War/Front/City 倒排）；本体（:686-7283）含私有 `RuntimeState`（:697-768，每军约 50 项运行态字段）
- **状态机**：`ArmyRtsState` 十态 Idle→Rally→March→Deploy→Assault→Hold→Pursue→Retreat→Regroup→Replenish（Code/core/lineage/ArmyRtsModels.cs:14-26）；Role 五种（:5-12）、Posture 四种（:28-33）；转移事实 `ArmyRtsTransitionFacts` 约 28 个布尔+供给/组织（:35-70）。转移链：`BuildFacts`（:5306-5541）→ `ResolveAndSet`（:487-498）→ 纯函数 `ArmyRtsRules.ResolveState`
- **与 vanilla 关系 = 共存 + 任务级接管**：军队/ArmyManager 对象保留原样，通过 Job/Task 覆盖 actor 行为（Code/content/ArmyRtsContent.cs:11-44 定义 `aw_army_rts_captain/_follower/_front_hold` 等 JobId 与 per-state TaskId）；`AW_ArmyRtsSchedulerPatch` HarmonyPostfix 挂 `ArmyManager.update` 之后驱动调度（Code/patch/AW_ArmyRtsSchedulerPatch.cs:12-26，异常时 `Config.paused=true` 熔断）；`ArmyRtsRuntimeModeRules.ShouldAllowVanillaStrategicDecision` 白名单封禁 RTS 模式下的 vanilla 战略决策（ArmyRtsRuntimeMode.cs:39-56）
- **调度编排** `ArmyRtsSchedulingService.ProcessCycle`（Code/core/performance/ArmyRtsSchedulingService.cs:49-108）：双 owner token gate 防双跑（:10-47）→ 确保任务控制器入队 → `ArmyRtsExecutionBudgetRules.Capture` 预算 → 依次 Guard 执行 coalition/director/route_provider/**controller**/logistics/watchdog，大模式追加 lifecycle/reconciliation/succession（:83-107）
- **32 上限 = 轮转公平调度**：战争任务（WarId>=0）进优先队列（ShouldPrioritizeMission :27-29），`WorkIndex.Take` 每帧先优先后普通凑满预算（:460-478），处理完 `Requeue` 回队尾（ProcessOne 末尾 :4632）

## 命令流

1. 校验链（Code/api/commands/ArmyRtsCommandService.cs:15-60）：replica 会话拒绝（`aw3_command_replica_read_only`）→ 非主线程拒绝 → ShouldCommit（仅 On 模式）→ `ArmyStrategicIndexService.ResolveIndexedArmy` 校验归属
2. SetArmyRallyPoint/SetArmyTargetCity → `SetCityMission`（:63-104）：`ArmyRtsCommandRules.IsLegalCityTarget` 合法性检查后构造 Mission（PlayerOrder=true）→ `AssignMission` → `KingdomWarDirectorService.OnArmyChanged` 通知导演重规划（:58-59）
3. SetArmyPosture（:106-140）：Retreat 走 `ArmyRetreatService.AssignArmyRetreat` 后回写；其余改 Posture。CancelArmyOrder → 取消并 `ReleaseActor`（ControllerService.cs:3681-3726）
4. `AssignMission`（:1192-1344）：可发布校验 → **30 秒目标切换冷却防振荡**（:1222-1238，中文注释）→ 复制 mission+置 Rally → 清共享路线/成员独立路径/攻击目标（:1290-1307）→ 运输重置 → `ArmyMissionPersistence.Persist`（:1342）

## 移动与战斗

- **单军 tick `ProcessOne`**（:4325-4633）：有效性检查（30 世界秒宽限防夺城瞬间误杀 :712-715 + TryDeferTransientMissionInvalidation :4635）→ 编队观察分段计时（:4376-4388）→ **战斗所有权仲裁** `TryHandleWarCombatOwnership`（:4718-4828）→ 野战脱离 `TryHandleFieldCombat`（:4829-4889）→ `EnsureJobs`（:6132-6162）→ 战略路线 → BuildFacts/ResolveAndSet → 撤退门禁（AllowWithdrawal :4484-4592 三处）→ 补给员额游标分片对账（:4511-4551）→ AdvanceRoute → 完成移交并 Invalidate（:4625-4631）
- **寻路三层降级，不走 AW3 全局引擎**：`AdvanceRoute`（:5625-5722）同岛检测 → 失败指纹+指数退避（3s→30s，:695-696）→ `AWArmyMarchService.SubmitStrategicRoute` 共享异步 provider（:5689-5695）→ provider 拒绝时保留 vanilla 战略目标 + Attack 下发 `TryIssueVanillaCityAttackOrder`（:5701-5715）。`ProcessPendingStrategicRoute`（:5723-5827）单次 Poll（注释 "One poll is intentional"）；Completed 时 `ArmyRtsRouteChoiceRules.Resolve` 按陆路成本 vs 海运四段成本决定陆行或转运输。跨岛走 `ArmyRtsTransportService` 四相位（AwaitingPickup→Embarking→Sailing→Landing，:28-346），运输中禁止野战脱离（:4845-4847 中文注释）
- **编队**：JobCursor 每控制器每 tick 最多 128 次 job 突变（:693），分帧遍历 roster 安装 job（EnsureVanillaMarchJobs :6192-6242 / EnsureCustomMovementJobs :6288-6348）；队长为行军编队锚点（:196-202）
- **交战**：所有权仲裁四态 ReleaseToVanilla/KeepVanillaControl/ReacquireStrategicControl/ReacquireForWithdrawal（:4774-4826）；围城判定（城内有敌军+insideTarget :74-89）→ `EnterTargetCitySiegeCombat`（:4997-5040）；野战交火时把 actor 交给 vanilla 战斗 AI 打完再收回（:4824-4826）；行为侧 `Code/ai/behaviours/actor/BehArmyRtsCaptainCombat.cs:12-38` 只做邻近目标验证+攻击，战略移动仍归编队控制器

## 可视化与性能集群

- `AW_ArmyRtsVisualizationPatch` 挂 MapBox.Update postfix（Code/patch/AW_ArmyRtsVisualizationPatch.cs:10-22）：`ArmyRtsVisualizationService` 用 Unity **SpriteRenderer 池**（非 QuantumSprite；Code/core/presentation/ArmyRtsVisualizationService.cs:18-46,281-355）+ 攻击气泡 + PNG/GIF 战况快照服务（Rasterizer/Encoder 等 7 文件）；规则：最多 24 支可见军队、每帧刷新 8 项、仅 RTS On+选中王国时显示（ArmyRtsVisualizationRules.cs:41-48）
- performance 集群 10 文件：`AWMilitaryFrontLaneScheduler`（**债务制时间片**：2.5ms 帧预算+debt 累积 :13,86-95，驱动 P0 军事成员）、`ArmyMilitaryMovementPriorityIndex`（RtsMember 注册+去重）、`ArmyRtsBenchmark`（planner/route/formation/retreat 采样）、`ArmyRtsTransportDiagnostics`（运输失败计数器）

## 多人模型

- 命令面：replica 会话一律拒绝军队命令（ArmyRtsCommandService.cs:19-21）
- 投影面：`InstallReplicaProjection`（ControllerService.cs:850-890）**必须在 `AW3MultiplayerReplicaScope.IsApplying` 内调用**（:852-854 throw），把权威端字符串化的 State/Role/Posture/Supply/Organization 解析进只读 `ArmyRtsStrategicProjection`——replica 端不跑控制器，只持战略快照供 UI
- 权威端：`ApplyDirectorSnapshot`（:908-1029）消费导演影子快照——世代号校验（:913）、跳过 PlayerOrder 军队（:937）、目标分类失败释放主张并触发重规划（:970-982）、漏发军队在运输/未完成时保留控制器（ShouldPreserveDirectorOmission :1004-1019）

## Unique Methods（C2a 批新增候选）

- `ArmyRtsControllerService.ProcessOne` (Code/core/lineage/ArmyRtsControllerService.cs:4325-4633) — 单军完整 tick：有效性→战斗所有权→job 安装→路线→状态机→撤退/补给/完成
- `ArmyRtsControllerService.AssignMission` (:1192-1344) — 任务发布唯一入口：可发布校验、30 秒冷却、共享路线清理、持久化
- `ArmyRtsControllerService.TryHandleWarCombatOwnership` (:4718-4828) — 围城进入与四态战斗控制仲裁
- `ArmyRtsControllerService.AdvanceRoute` (:5625-5722) — 战略路线提交：同岛检查、失败指纹退避、海运切换、vanilla 兜底
- `ArmyRtsControllerService.ApplyDirectorSnapshot` (:908-1029) — 导演影子快照落地（世代校验、玩家命令保留、漏发保留）
- `AWMilitaryFrontLaneScheduler` (Code/core/performance/AWMilitaryFrontLaneScheduler.cs:86-95) — 2.5ms 帧预算 + debt 累积的债务制军事时间片

## Reusable / Anti-patterns

做法：双优先级轮转队列+每帧预算防饿死（WorkIndex.Take :460-478）；纯静态 Rules 类与可变 Service 严格分离，且 Service 包在 `#if !AW3_RULES_TESTS` 内使测试项目只编译规则——状态转移可单测；分片游标防尖峰（JobMutations≤128/RoutePolls≤64 + JobCursor 跨帧续跑 :693-694）；失败指纹+指数退避防重试风暴（:5829,:695-696）；债务制时间片欠账下帧补（FrontLaneScheduler :86-95）。

反模式：7,283 行单文件塞 6 类型 + RuntimeState ~50 可变字段（:697-768），其余域都拆了 Rules 独立文件唯独主 service 未拆；大量 `Safe*` 容错包裹吞 null（:7183-7268）掩盖不变量违反；帧缓存双点手动失效易漏（:3431-3441 与 :398/:410，注释自载"刚下达的任务看起来无效"既有 bug）；双队列去重靠两个平行 HashSet 手工同步（:358-361）；调度入口异常 `Config.paused=true` 全局暂停熔断但破坏体验且吞堆栈（AW_ArmyRtsSchedulerPatch.cs:20-24）。

## Confidence

核心主张（架构/命令流/移动战斗/可视化/多人投影的 file:line）Verified——本会话直接读取；ArmyRtsControllerService 约 40% 区段（含 BuildFacts :5306-5541）与 ~20 个 lineage ArmyRts* 辅助文件（MissionLock/Objective/RouteChoice/WarDoctrine 等）未逐行，状态 Mostly Verified；ArmyRtsTransportService/AbstractSupplyService 主体归 C2b。

## Known Gaps

- BuildFacts 事实收集全文（:5306-5541）未读——字段集经 TransitionFacts 定义推知
- ArmyRtsTransportService/TransportRules 主体（海运四相位细节）签名级
- ~20 个 ArmyRts* 辅助文件（MissionLock/Objective/RouteChoice/SuccessionRecovery）未读
- KingdomWarDirectorService（导演/coalition 规划）内部归 C2b
