---
title: Ancient Warfare 3（古代战争·春秋）
aliases:
  - ancient-warfare-3
---

# Ancient Warfare 3（古代战争·春秋）

## Identity

- Name: Ancient Warfare 3 v1.2.7g（mod.json:2-9，guid `ANCIENTWARFARE3`，author GoatDie#4068，RepoUrl github.com/monpai-lover/AncientWarfare3.0）
- Source ID: `ref:ancient-warfare-3`
- Dir: `古代战争_春秋3.0`
- Files: 4263 total / 2018 C#
- Confidence: Mostly Verified

## Purpose

历史战争 overhaul：郡县制、朝廷官僚与科举、天命系统、族谱 SQLite 档案、军队 RTS 控制、历代开国君主降临、多人快照。核心域 1619 文件（court 213 / lineage 831 / db 118）、150 个补丁文件。**本轮 survey 级建档**（抽查入口/DB/API/8 个代表性补丁），court/lineage 内部为名录+抽查推断；深挖子批 C0-C6 已列入 deferred。

## Systems

- Primary: Actor, City, Kingdom, War, Save/Persistence, UI, AI
- Secondary: Diplomacy, Culture, Combat, Events, Assets, Mod Lifecycle, Buildings, Jobs

## Key Implementation

- `Code/ModClass.cs` (L27-196) — `BasicMod<ModClass>, IReloadable`：`DormantPatchTypes` 停用门（L55-59，附中文风险注记 L37-54）、反射扫描 `[HarmonyPatch]` 逐类有序上补丁 + 空结果告警（L137-196）、`[MethodReplace]` Transpiler 方法体重定向（L108-109）
- `Code/core/asyncwork/AWAsyncWorkCoordinator.cs` (L215-404) — 协作式异步调度：lane/stamp/commit-mode 工作请求、主线程按时间预算 `DrainMainThread(ms,maxBatches)` 分批提交、存档屏障
- `Code/core/db/LineageArchiveManager.cs` (L25-590) — SQLite 档案：反射 `[TableDef]` 建表（118 表类）+ `AddMissingColumns` 幂等补列（L527-552）、进程隔离 `.runtime/process-<pid>/` 运行时库、fail-closed 存档隔离 `DisableRuntimeArchive`（L119-132）
- `Code/core/lineage/MandateService.cs` (L46-3606) — 天命系统：单行状态（STATE_ID=1）+ 报告缓存 + 年度涨落 `CalculateYearlyDelta`（L2566）+ DB 重算 `ReadReportFromDb`（L2726）
- `Code/core/court/CourtService.cs` (L119-3414) — 朝廷：官职 id 配置、空缺填补、`CourtSnapshot` 画像（效率/集中度/民生/战争/秩序/科技）
- `Code/core/county/CountyAdministrationService.cs` (L10-240) — 郡县制：zone 邻接图分区 + 历史郡名录匹配 + 空郡失活
- `Code/core/lineage/ArmyRtsControllerService.cs` (L22-7283) — 军队 RTS：mission 模型、每帧 32 控制器上限、战略抵达半径
- `Code/content/figures/HistoricalFigureService.cs` (L28-731) — 开国君主降临：严格顺序生成（前代不死不出）、SQLite 持久化防重刷、私有 `System.Random`（MapBox 会播种 UnityEngine.Random）
- `Code/api/history/AW3HistoryApi.cs` (L9-77) + `Code/core/historyapi/AW3HistoryReadService.cs` (L59-832) — 历史查询公共 API：分页读 + IDisposable 订阅
- `Code/patch/AW_SavePatch.cs` (L34-172) — `SaveManager.saveWorldToDirectory` 前后缀把运行时档案导出进存档目录

## Unique Methods

筛选口径：剔除补丁管线与样板后，代表性模组自有机制方法（survey 级精选，非穷举）。

- `CountyAdministrationService.ReconcileCity(City)` (Code/core/county/CountyAdministrationService.cs:L12-227) — 郡县制核心：对城市 zone 邻接图重新划分郡，匹配历史郡名录，失活空郡并持久化
- `AWAsyncWorkCoordinator.TrySchedule(...)` / `DrainMainThread(double,int)` (Code/core/asyncwork/AWAsyncWorkCoordinator.cs:L299-404) — 异步工作请求入列 + 主线程时间预算分批提交，存档经 TryEnterSaveBarrier 屏障（AWAsyncRuntime.cs:78）
- `ArmyRtsCommandService.Dispatch(AW3CommandRequest)` (Code/api/commands/ArmyRtsCommandService.cs:L13-48) — 军令 RPC：replica 只读校验 + 主线程/王国/军队归属校验后执行集结点/目标城/姿态/取消
- `MandateService.ReadReport()` / `ReadReportFromDb()` (Code/core/lineage/MandateService.cs:L273, L2726) — 天命报告：缓存未脏直接读，否则从 SQLite 重算 mandate/authority/core_control/crisis_level
- `HistoricalFigureService.TrySpawnOn(Actor,string)` (Code/content/figures/HistoricalFigureService.cs:L124-233) — 君主降临：严格顺序 + 存活互斥 + 私有无种子随机
- `AW3HistoryReadService.ReadEvents(AW3HistoryQuery)` (Code/core/historyapi/AW3HistoryReadService.cs:L59-832) — 历史事件分页查询引擎（SQLite 只读连接 + DTO 映射）
- `CourtService.GetSnapshot(Kingdom)` (Code/core/court/CourtService.cs:L357) — 朝廷画像快照：多学阀 dominant_school/faction 缓存

- `AWFramePriorityGovernor.RecalculateBudget` (Code/core/performance/AWFramePriorityGovernor.cs:L323-346) — 帧预算 governor：渲染 P90 基线 + 超支 ≤50% 摊还下帧的每帧模拟预算
- `AWCooperativeWorldMaintenanceRunner.Step` (Code/core/performance/AWCooperativeWorldMaintenanceRunner.cs) — 把原版 World.updateObjects 的 28 个维护阶段改造成协作式分步状态机（经 TakeOverMainSimulation 接管驱动）
- `AWPathFinder.Request` / `AWStreamingPathGenerator.GenerateSegment` (Code/core/pathfinding/AWPathFinder.cs:L174+、AWStreamingPathGenerator.cs:L44+) — 按 actor session 去重复用的多线程寻路准入 + 风险加权/节点预算/分段续算的流式 A*
- `HistoricalWriteWorker.WorkerLoop` (Code/core/db/HistoricalWriteWorker.cs:L384-548) — 单线程批量取批→整批单事务→busy 退避→终态故障聚合上报的异步写循环
- `LineageArchiveManager.TryExportLineageArchive` (Code/core/db/LineageArchiveManager.cs:L185-267) — BackupDatabase + journal_mode=DELETE + quick_check + 原子 Replace 的五重存档快照导出

## Research Map

- [async-and-performance.md](ancient-warfare-3/async-and-performance.md) — R3-AW3 C0：异步调度协议/世界生命周期/帧预算 governor/寻路接管/[MethodReplace]（2026-09-27 完成）
- [persistence-archive.md](ancient-warfare-3/persistence-archive.md) — R3-AW3 C1：SQLite schema 生命周期/写管线/读路径与订阅/存档集成/进程隔离库（2026-09-27 完成）
- [army-rts.md](ancient-warfare-3/army-rts.md) — R3-AW3 C2a：军队 RTS 状态机/调度/战斗所有权/海运降级/多人投影（2026-09-27 完成）
- [mandate-diplomacy-vassalage.md](ancient-warfare-3/mandate-diplomacy-vassalage.md) — R3-AW3 C2b：天命六指标与改朝换代/战争导演/海运四相位/外交封臣继承域（2026-09-27 完成）
- [court-county-schools.md](ancient-warfare-3/court-county-schools.md) — R3-AW3 C3：朝廷官职与科举/郡县分区/学派流水线/Courtjson 模板（2026-09-27 完成）
- [content-naming.md](ancient-warfare-3/content-naming.md) — R3-AW3 C4：资产注册清单/夏种族陷阱/91 君主卡与 691 传记/63 政策/命名引擎（2026-09-27 完成）
- [ui-api-multiplayer.md](ancient-warfare-3/ui-api-multiplayer.md) — R3-AW3 C5：UI 读路径分档/uiquery read-model/多人复制围栏/公共 API 契约（2026-09-27 完成）
- [patch-catalog.md](ancient-warfare-3/patch-catalog.md) — R3-AW3 C6：150 补丁文件全枚举（620 方法/分类表/特殊类别/风险标记）（2026-09-27 完成）

## Techniques

Harmony Prefix/Postfix/Transpiler（150 patch 文件；目标直方图 Actor 100 / City 83 / MapBox 47 / QuantumSpriteLibrary 46 / Kingdom 35）、`[MethodReplace]` 通用方法体重定向（attributes/MethodReplaceAttribute.cs + utils/HarmonyTools.cs）、SQLite 持久化（System.Data.SQLite 随包）、`[TableDef]` 反射 schema 迁移、协作式异步调度 + 存档屏障、进程隔离运行时库、IReloadable 热重载、GodPower 注册（GodPowerLibrary.cs:121-256）

## WorldBox Usage

Actor.newCreature / Actor.goTo / City / CityBehCheckLeader / KingdomManager.makeNewCivKingdom / SaveManager.saveWorldToDirectory / War / Army / BabyMaker.makeBaby / MapBox / QuantumSpriteLibrary / AssetManager.powers / StatusManager.update / Building

## NeoModLoader Usage

- BasicMod<T> + IReloadable.Reload（Verified，ModClass.cs:27,339-344）
- NeoModLoader General/UI/Tab/Window（Mostly Verified，14 文件使用）
- GodPower + PlayerConfig 功能开关（Verified，HistoricalFigureService.cs:31-33）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| SaveManager.saveWorldToDirectory | Pre+Post | Code/patch/AW_SavePatch.cs:34-62 | 运行时档案导出进存档目录 |
| Actor.newCreature | Postfix | Code/patch/AW_BirthPatch.cs:26 | 出生路由（含历代君主） |
| Actor.goTo / updatePathMovement / isUsingPath | Prefix ×3 | Code/patch/AW_GlobalPathfindingPatch.cs:32-153 | AW3 自有寻路接管 |
| BabyHelper.canMakeBabies / BabyMaker.makeBaby | Pre+Post | Code/patch/AW_DynasticReproductionPatch.cs:14-107 | 王朝生育控制 |
| CityBehCheckLeader.checkFindLeader | Prefix | Code/patch/AW_CityLeaderPatch.cs:13 | 城主选拔接管 |
| KingdomManager.makeNewCivKingdom / removeObject | Postfix/Prefix | Code/patch/AW_ChroniclePatch.cs:39-51 | 王国编年史与生命周期 |
| StatusManager.update | Prefix | Code/patch/AW_FramePrioritySchedulerPatch.cs:114 | 帧预算插桩（SpecialPatch 手动装载） |

（150 patch 文件未逐一列表；2 个 dormant 停用类见 ModClass.cs:55-59。）

## Reusable Ideas

- `DormantPatchTypes` 停用门：缺类级 `[HarmonyPatch]` 从未真正装载的补丁显式停用并写明风险与验证条件（ModClass.cs:37-59）
- SQLite 档案随存档走：进程隔离运行时库 + saveWorldToDirectory 前后缀复制，实现跨存档保留（LineageArchiveManager.cs:23 注释明说设计动机）
- 反射 `[HarmonyPatch]` 逐类有序上补丁 + 空结果告警，区分"意外漏打"与 `[HarmonyPrepare]` 主动停用（ModClass.cs:137-196,276-299）
- 主线程时间预算 drain 的异步协调器：后台算、主线程按 ms 预算收结果（AWAsyncWorkCoordinator.cs:404）
- fail-closed 存档加载：档案打不开就 `DisableRuntimeArchive` 隔离，绝不用空库顶替存档数据（LineageArchiveManager.cs:119-132）

## Pattern Candidates

- `sqlite-sidecar-save-archive`
- `process-isolated-runtime-db`
- `async-work-coordinator-save-barrier`
- `tabledef-reflection-schema-migration`
- `dormant-patch-gate`
- `replica-read-only-facade`

## Evidence

- Code/ModClass.cs:27 — `class ModClass : BasicMod<ModClass>, IReloadable`
- Code/ModClass.cs:55-59 — DormantPatchTypes 停用门
- Code/ModClass.cs:137-196 — 反射扫描逐类上补丁
- Code/core/db/LineageArchiveManager.cs:23 — "运行时库 + 随存档复制"设计注释
- Code/core/db/LineageArchiveManager.cs:87-88,527-552 — 建库与幂等补列
- Code/core/lineage/MandateService.cs:18-59 — MandateReport DTO 与常量
- Code/core/asyncwork/AWAsyncWorkCoordinator.cs:299,404 — TrySchedule / DrainMainThread
- Code/core/court/CourtService.cs:121-136,357 — CourtSnapshot 指标与 GetSnapshot
- Code/core/county/CountyAdministrationService.cs:28-45 — 分区规则与历史名录
- Code/api/commands/ArmyRtsCommandService.cs:19-27 — replica 只读/主线程校验
- Code/content/figures/HistoricalFigureService.cs:16-27 — 顺序生成与私有 Random 设计注释
- Code/patch/AW_SavePatch.cs:34-35,61-62 — saveWorldToDirectory 前后缀

## Notes / Deferred

建档时为 survey 级；**R3-AW3 全部 7 个子批（C0 异步调度 / C1 SQLite 档案 / C2a 军队 RTS / C2b 天命外交 / C3 朝廷郡县学派 / C4 内容命名 / C5 UI-API-多人 / C6 补丁目录）已于 2026-09-27 完成**，见 Research Map 子节点，各批核心主张均逐行 Verified。本模组深挖收口；后续如需补遗按各子文档 Known Gaps 追踪。Assemblies\ 含完整 Assembly-CSharp.dll 发布副本与 .runtime 运行时产物，复验可用公开 GitHub repo 作更净源。mod.json:12-14 声明与 一米_中文名 不兼容（ModClass.cs:139-149 有冲突检测实现）。
