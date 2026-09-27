---
title: AW3 异步调度与性能工程
aliases:
  - ancient-warfare-3-async
---

# Ancient Warfare 3 — 异步调度与性能工程（R3-AW3 C0）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批覆盖 `Code/core/asyncwork/`（11 文件全读）、`Code/core/performance/`（81 文件，核心 10-15 全读 + 按簇勘察）、`Code/core/pathfinding/`（33 文件，核心全读）与三个接管 patch。除注明外全部逐行 Verified。

## Scope

- 覆盖：AWAsyncWorkCoordinator 调度协议、世界生命周期协调、帧预算 governor、协作式主模拟接管、dirty-meta 索引现状、AW3 自有寻路引擎、`[MethodReplace]` 方法体重定向
- 不覆盖：SQLite 写管线（→ [persistence-archive.md](persistence-archive.md)）、lineage/court 域逻辑（→ C2/C3 批）、UI/呈现渲染实现细节（→ C5 批）

## 调度器端到端链路

- **请求模型** `AWAsyncWorkRequest`（Code/core/asyncwork/AWAsyncWorkCoordinator.cs:8-34）：`Key`（去重合并键）、`Lane`（Database/Traversal/Ui/Ai，AWAsyncWorkRules.cs:14-21）、**三元世代戳** `Stamp`（WorldGeneration+CaptureTick+SourceRevision，:29-42）、`Execute/Commit/Fault` 回调、两阶段 `TryAdmit` 准入、`CommitMode`（MainThread/Background，:23-27）
- **入队** `TrySchedule`（Coordinator:299-347）：`CanScheduleLocked`（:992-1001）校验运行态/屏障/世代/lane 容量；队列是 `AWBoundedLatestQueue`——**按 Key 合并的 latest-wins 有界队列**（AWAsyncWorkQueue.cs:6-74），同 Key 重复请求替换旧项并记 merged（Coordinator:368-372）。容量 Traversal=1、Ui=32、Ai=256（:164-169）
- **后台执行**：最多 2 个 BelowNormal 后台线程（"池必须刻意小"，AWAsyncWorkRules.cs:64-78；线程创建 Coordinator:265-277）；`AWAsyncPriorityRules.SelectComputeLane`（AWAsyncWorkRules.cs:172-188）做 lane 仲裁：Traversal/Ui 交替 + Ai 反饥饿（最多连续 3 次高优后强制 Ai）。CommitMode=Background 时在 worker 直接 commit（Coordinator:787-860），否则结果进 `_completions`（容量 512）
- **主线程提交** `DrainMainThread(ms,maxBatches)`（Coordinator:404-455）：Stopwatch 时间预算 + 批数上限，世代不符记 stale（:425-429），异常走 Fault 回调。实际帧驱动是 `AW_DeferredRuntimeWorkPatch.MapBoxUpdate_Postfix`（AW_DeferredRuntimeWorkPatch.cs:17-80）：**0.35ms 帧预算**（AWAsyncCompletionDrainRules.cs:9）、itemLimit≤2，串行排空 async completion→历史读→历史写→编年史事件
- **lane 用途**：Traversal=寻路通行性快照构建（AWTraversalCache.cs:393,476,549）；Ai=王国战略/军队 RTS 规划（AsyncKingdomStrategyService.cs:110,215）；Database=历史写入旁路开关（AWPerformanceSettings.cs:35-39）；Ui=历史读查询
- **存档屏障** `TryEnterSaveBarrier`（Coordinator:484-533）：置 pending → 主线程循环 `DrainMainThread(1.0,16)` 直到全静默（`SaveBoundaryQuiescentLocked`:1065-1073）→ 置屏障；屏障期非 drain 线程被拒（:1014-1019）。上层 `AWAsyncWorldLifecycle.TryEnterSaveBarrier`（AWAsyncWorldLifecycle.cs:212-248）把它与历史读服务屏障原子组合，失败即回滚两者

## 世界生命周期协调

- `AWAsyncWorldLifecycle.StartWorld`（:130-204）：coordinator.StartWorld 拿 generation → HistoricalWrite/ReadService.StartWorld，失败逐级回滚清理。`TryBeginWorldChange`（:31-85）：FlushForSave → reader.ClearWorld → writer.StopWorld → `ClearWorld`（世代++、派生任务取消、等 activeWorker 归零，Coordinator:546-595），任一步失败带回滚重启动链；触发点是 `AW_AsyncWorldLifecyclePatch` 的 **MapBox.clearWorld prefix**（AW_AsyncWorldLifecyclePatch.cs:13-24）
- `TryShutdown`（:287-338；Coordinator:597-679）：Draining → 取消线程 join → worker join → 清 completions/commits → Stopped；ModClass 退出钩子以 2s 超时调用（ModClass.cs:325）
- `AWCooperativeWorldMaintenanceRunner`（AWCooperativeWorldMaintenanceRunner.cs:9+）：把原版 World.updateObjects 的 **28 个维护阶段**（:19-46 枚举）改成可分步 `Step()` 协作式状态机，脏 meta manager 走 `Parallel.For`（:99-101）。由 `AWCooperativeSimulationRunner` 持有（:148-149,1130-1134），后者经 `AW_FramePrioritySchedulerPatch.TakeOverMainSimulation`（AW_FramePrioritySchedulerPatch.cs:383-439）**接管 MapBox.checkMainSimulationUpdate** 后逐帧驱动
- **dirty-meta 索引现状（反模式实证）**：`AWDirtyMetaActorIndex`（AWDirtyMetaActorIndex.cs:9-32）按 11 类归属建位图索引、由 maintenance runner 持续构建；但消费它的 12 个 `AW_DirtyMetaActorIndexPatch` prefix 全部列入 `DormantPatchTypes` 停用（ModClass.cs:47-59）——**索引成本在付、收益未接**

## 帧预算与性能设施

- `AWFramePriorityGovernor`（performance/AWFramePriorityGovernor.cs）：`BeginFrame`（:88-103）按 `目标fps − 渲染预留2ms − 基线P90(120帧滚动)` 算预算，超支按 ≤50% 比例摊还下帧避免零预算帧（`RecalculateBudget`:323-346）；`CanRun`（:121-146）按相位指数平滑(0.8/0.2)准入 + 反饥饿 slice（:373-393）；战时动态降 fps（:348-371）
- 插桩纯诊断向：`TryLogSchedulerDiagnostics` 每 10s 汇总打日志（AW_FramePrioritySchedulerPatch.cs:1632-1654）、prefix 分段计时（:41-84）、`RuntimePerformanceDiagnostic.AccountFrameCost` 最坏帧归因桶（:52-61）；benchmark（RecentFeatureBenchmark / AWSimulationTickBenchmark）只出报告，无自适应闭环
- `AWPerformanceSettings`（AWPerformanceSettings.cs）：全部开关中枢——目标 fps=60、MaxSimMs=8、Mode(Native/Large/Aw3)、五个 async 开关、并行预算/worker 数
- performance 81 文件按簇：协作调度核心（AWCooperativeSimulationRunner/ActorParallelJobRunner 等）、帧调度规则类（~15 个纯函数 *Rules）、worker 池、呈现管线（~14 文件快照绘制）、增量索引簇、军队 RTS 调度簇（~10）、空闲节流、诊断门、月度队列

## 寻路接管架构

- **引擎源自 Cultiway-Reborn(MIT)**（AWPathFinder.cs:1 头注）。`AWPathFinder`（pathfinding/AWPathFinder.cs:96+）：专用线程池 1-8 个 "AW3 Path Worker"（:141-158）、三优先级 ConcurrentQueue（Starved/Initial/Continuation，公平规则最多连跑 8 个 starved，AWPathSession.cs:6-22）、按 actor session 记录去重/替换（:102,174+）
- **算法** `AWStreamingPathGenerator`（AWStreamingPathGenerator.cs:8+）：分段流式 A*——ThreadStatic 搜索工作区、`AWBinaryHeap` 开放集、短程 3000/长程 12000 节点预算 + fallback 走廊（AWPathfindingConfig.cs:11-16）、风险加权代价（火/熔岩/溺水/死亡风险，:25-35）、低水位续段（SegmentStepBudget=16 / LowWatermark=8，AWPathFinder.cs:99-100）
- **通行性缓存** `AWTraversalCache`：分块快照 + 脏瓦片标记（由 WorldTile.setTileType/建筑 setState 等 postfix 驱动，AW_GlobalPathfindingPatch.cs:414-461），初始/拓扑构建经 **AWAsyncLane.Traversal 异步提交**（:476,549）
- **goTo 分流** `AW_GlobalPathfindingPatch.GoTo_Prefix`（:31-102）：`PathfindingOwnershipService.ShouldIntercept`（AWPathfindingOwnershipService.cs:23-26，= AW3 模式 + ownership 状态机 Ready + Cultiway 冲突检测）不满足→放行原版；RTS 运输船/军用路径→原版或拒绝；否则 `AWPathMovementBridge.Submit` 提交 finder 并 return false。`updatePathMovement` prefix 轮询桥（:125-150）。**寻路走专用 worker 池，不经 asyncwork coordinator；asyncwork 只承载 traversal 快照构建**
- Bootstrap（AWPathfindingBootstrap.cs）由 AWAuthorityCycleService 每周期调 `ProcessFrame`（AWAuthorityCycleService.cs:361）；第三方 patch 挂载时让位（OwnershipService.cs:80-87）

## [MethodReplace] 方法体重定向

- `MethodReplaceAttribute`（Code/attributes/MethodReplaceAttribute.cs:20-101）：三种构造（目标类+名 / 仅名 / 同名走基类链）；实例方法自动剥 this 参数重试匹配（:94-98）
- `HarmonyTools.ReplaceMethods`（Code/utils/HarmonyTools.cs）：扫全程序集（:22-79，重复目标告警 :53-59）；每目标独立 Harmony owner 打**纯 Transpiler**：丢弃原 IL、重排 `ldarg`（含实例 Castclass）→ `callvirt 替换方法` → `ret`（:91-114）。只替换方法体层，目标上的第三方 Prefix/Postfix 链不受影响（:11-16）

## Unique Methods（C0 批新增候选）

- `AWAsyncWorkCoordinator.TryEnterSaveBarrier(TimeSpan, Action, out string)` (Code/core/asyncwork/AWAsyncWorkCoordinator.cs:484-533) — 主线程自旋排空全部异步在途工作直到静默再进屏障的存档一致性协议
- `AWAsyncPriorityRules.SelectComputeLane` (Code/core/asyncwork/AWAsyncWorkRules.cs:172-188) — Traversal/Ui 交替 + Ai 反饥饿的 lane 仲裁
- `AWFramePriorityGovernor.RecalculateBudget` (Code/core/performance/AWFramePriorityGovernor.cs:323-346) — 渲染 P90 基线 + 超支 50% 摊还的每帧模拟预算
- `AWCooperativeWorldMaintenanceRunner.Step` (Code/core/performance/AWCooperativeWorldMaintenanceRunner.cs) — 28 阶段原版世界维护的协作式分步状态机
- `AWPathFinder.Request` (Code/core/pathfinding/AWPathFinder.cs:174+) — 按 actor session 去重/替换/复用的多线程寻路准入
- `AWStreamingPathGenerator.GenerateSegment` (Code/core/pathfinding/AWStreamingPathGenerator.cs:44+) — 风险加权、节点预算、分段续算的流式 A*
- `AWAsyncWorldLifecycle.TryBeginWorldChange` (Code/core/asyncwork/AWAsyncWorldLifecycle.cs:31-85) — 三服务串行清世界且每步可回滚的换界协议
- `HarmonyTools._method_replace_patch` (Code/utils/HarmonyTools.cs:91-114) — 丢弃原 IL 重定向为转调替换方法的通用 Transpiler

## Reusable / Anti-patterns

做法：latest-wins 有界队列按 Key 合并天然背压（AWAsyncWorkQueue.cs:39-53）；worker 池刻意小(2)+BelowNormal（AWAsyncWorkRules.cs:64-71）；三元世代戳使陈旧结果各层廉价作废（AWAsyncWorkRules.cs:29-42）；两阶段 TryAdmit 避免死占容量（Coordinator:321-346）；换界/关停每步带回滚并汇总错误（AWAsyncWorldLifecycle.cs:31-85,287-338）。

反模式：索引常建无人消费——dirty-meta 索引与消费 patch 脱钩（ModClass.cs:47-51）；屏障 drain 慢 commit 拉长存档卡顿（Coordinator:1021-1063）；ReplaceMethods 无 feature toggle、签名漂移仅运行期日志可见（HarmonyTools.cs:61-76）；worker 异常只降级记日志继续转（Coordinator:696-714）；呈现快照接管大量 draw* 且每处需手动 EnsureActorReadBoundary，漏一处即竞态（AW_FramePrioritySchedulerPatch.cs:807-943）。

## Confidence

Verified（asyncwork 11 文件、3 接管 patch、HarmonyTools、governor、pathfinder/generator/bridge/traversal-cache 核心段逐行核对）；performance/pathfinding 其余 ~85 文件按名簇勘察为 Mostly Verified。

## Known Gaps

- AWCooperativeSimulationRunner 全文与 ActorParallelJobRunner 并行 job 粒度未逐行（C0 只核对接线）
- 呈现渲染簇 14 文件、ArmyRts 调度簇 10 文件仅聚类（部分归 C2a/C5）
- AWDock* 海运 6 文件、AWRegionRouteCache、AWPathRecoveryManager 未读
- dirty-meta 索引的实际收益（若接通 12 个停用 patch）未评估
