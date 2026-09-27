---
title: AW3 UI、公共 API 与多人复制
aliases:
  - ancient-warfare-3-ui-api-multiplayer
---

# Ancient Warfare 3 — UI、公共 API 与多人复制（R3-AW3 C5）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批覆盖 `Code/ui/`（107 文件 ~38.9k 行，精读 3 个代表窗口）、`Code/core/uiquery/`（10 文件全读）、`Code/api/multiplayer/`（20 文件 3,851 行）、`Code/api/history`+`api/commands` 公共 API 面。file:line 均实读。

## UI 层架构

- **聚类**：ui/windows 47（其中 WarPeaceNegotiation 两件套 12.5k 行）+ 6 controller；ui/items 33（列表行/树节点/气泡 view）；ui/components 14（自定义 chrome/下拉/地图 viewport/朝廷 workflow canvas）；根 13（L10n/tab/tooltip）。`AW_L10n` 全部英中字面量双参回退（ui/AW_L10n.cs:3-5）；自定义 "aw_raw" tooltip 类型（ModClass.cs:128）
- **窗口生命周期**：继承 NML `AbstractWindow<T>`，静态 `Open()` → `CreateAndInit(id)` → `AW_LineageWindowIds.SafeShow`（AncestryAnalysisWindow.cs:12-21）；入口按钮统一在自定义 lineage tab（AW_LineageTab.cs:30-100，五组布局，ModClass.cs:131 装配）；窗口恢复规则 AWWindowCreationRules.cs:6-13
- **代表窗口数据流（读路径分档）**：
  - 轻量同步：AncestryAnalysisWindow → `AncestryAnalysisService.BuildReport(actorId)` 直接 AddLine（:9-56）
  - 中量内存 read model：**CourtWindow 不查 db**，每次刷新调 `CourtReadModelService.Build/BuildLocal` 直读 live 内存态（CourtWindow.cs:410-427；CourtReadModelService.cs:112,313,419），渲染对象池 + 协程分帧头像（PortraitsPerFrame=8 :37）
  - 重量异步 SQLite：HistoryListWindow 用 `AWHistoricalReadService.TrySchedule` 排队后台读，主线程 Commit + 同步回退路径（HistoryListWindow.cs:266,450-486）；FamilyTreeWindow 自维护 `_childIdsCache` + TryScheduleBulkSnapshot（:104,623-955）
- **UI 不写状态**：CivilServiceExamWindow 的排名操作经 `AW3MultiplayerCommandFacade.DispatchFromUi(AW3CommandRequest.SubmitCivilServiceRanking(...))`（:350-370,413,532）；军令按钮同样走 DispatchFromUi

## Read-model 层（core/uiquery）

**请求-排队-主线程提交**：`AWHistoricalReadRequest`（Key/Stamp 源修订号/Execute(SQLiteConnection)/Commit/Fault 闭包，AWHistoricalReadWorker.cs:11-35），单后台 worker 串行执行；缓存按 `AWUiQueryKey(windowId, contextId, filter, revision, queryGeneration)` 精确寻址 + 不可变 `AWUiPage<T>`（深拷贝 Items，AWUiQueryModels.cs:4-45）；增量工作票券化 `AWUiIncrementalWorkState`（Generation 递增，DefaultStepsPerFrame=8 分帧）。

## 多人复制（api/multiplayer）

- **会话围栏**：`AW3MultiplayerReplicaScope`（:8-92）静态单持有者 + 递增 sessionRevision；`EnterApply()` 返回**线程绑定 ApplyLease**（:62-88，跨线程释放抛异常）——投影安装的强制围栏；约 20+ core 服务与 patch 以 `IsReplicaSession`（会话级）+ `IsApplying`（线程级）双层做写抑制
- **快照导出（导演端）**：`TryCreateGeneration`（AW3MultiplayerSnapshotFacade.cs:15-98）主线程借存档屏障：`SaveManager.currentWorldToSavedMap` → map.wbox(.tmp→Move) + map_stats.s3db + `TryExportLineageArchive`；`ValidateGeneration`（:103-170）逐文件校验 + **拒绝 WAL/SHM sidecar** + pragma/quick_check 校验
- **代次加载（副本端）**：状态机 AwaitingWorldData→LoadingWorld→RestoringAw3→CompleteRestore（AW3MultiplayerWorldLoadOperation.cs:16-105，带 UTC 截止 + revision 快照读）；恢复走 RuntimeRestorePipeline（C1 已验）
- **战略状态复制**：`Capture(tick)/Apply(snapshot)` 双主线程门面（StrategicStateFacade.cs:9-31）→ Coordinator 先校验身份再 `using(ReplicaScope.EnterApply())` 顺序 Apply 四类投影（:98-160）；ApplyArmy（:383-400）写 LineageKeys 后调 `ArmyRtsControllerService.InstallReplicaProjection`（自身再断言 IsApplying，C2a 已验）——C2b 快照的落点闭环
- **命令拒绝**：UI 统一 `DispatchFromUi`——无 dispatcher 且 replica → `Rejected(ProviderUnavailable)`；权威路由在 replica → `Rejected(Unauthorized, "aw3_command_replica_read_only")`（CommandFacade.cs:70-115）；dispatcher 一次性注册 + `_ownershipRevision` 双检（:28-68）；底层路由分发给 Court/Diplomacy/Household/Policy/Realm/Records 六个 handler
- **chat/diplomacy/继承**：同「门面 + 单提供者抢占注册」模式（DiplomacyChatFacade.cs:11-94，Changed 事件异常安全回调）；`AW3MultiplayerCatalog.PayloadSchemaVersion = 2`（:8）

## 公共 API 面

- **版本化**：`AW3HistoryApi.ApiVersion="1.0"`；编译符号 `AW3_RULES_TESTS` 双路径（测试下 IsAvailable=false/空页/NoopSubscription，AW3HistoryApi.cs:6,23-81）——存在独立测试工程消费同一契约
- **消费者反证**：`AW3HistoryApi/GenealogyApi/ChronicleApi` 在 mod 内仅 api/history 自引——是**面向外部 mod/工具的导出面**，自家 UI 走 core/uiquery 内部路径；而 `AW3CommandRequest/DispatchFromUi` 消费者全是自家 UI（9 个窗口 + naming patch）

## Unique Methods（C5 批新增候选）

- `AW3MultiplayerSnapshotFacade.TryCreateGeneration` (Code/api/multiplayer/AW3MultiplayerSnapshotFacade.cs:15-98) — 主线程借存档屏障一次性导出 map.wbox+stats+族谱库并三重校验
- `AW3MultiplayerReplicaScope.EnterApply` (:62-88) — 线程绑定的副本应用围栏（lease 析构校验同线程+深度）
- `AW3MultiplayerCommandFacade.DispatchFromUi` (:70-115) — UI 命令唯一入口：权威路由或类型化拒绝
- `AWHistoricalReadService.TrySchedule` (Code/core/uiquery/AWHistoricalReadService.cs:56-63) — 历史窗口异步读排队（带 epoch）
- `AWUiPage<T>` 构造 (Code/core/uiquery/AWUiQueryModels.cs:20-36) — 按(窗口,上下文,过滤,修订代)键控的不可变分页缓存单元
- `AW3MultiplayerUiFacade.TryOpen` (:18-110) — 多人受控的 13 种窗口打开分发器

## Reusable / Anti-patterns

做法：门面 + 单提供者抢占注册（`_ownershipRevision` 双检，事件订阅失败原子回滚，三个门面共用）；双层写抑制围栏（会话级 IsReplicaSession / 线程级 lease，patch 一行短路、投影安装违例抛异常而非静默）；**读路径按数据量分档**（同步直读 / 内存 read model / 异步 SQLite+同步回退）而非一刀切。

反模式：静态可变窗口上下文（CourtWindow._kingdomId 等 static 字段承载选中态，靠 WorldSwitchCacheRules 手工清理）；快照门面全部异常转枚举 Failure 且 13+ 种错误调用方逐个处理、ValidateGeneration 与 TryCreateGeneration 校验部分重复；**replica 会话 Activate 无 mod 内调用点**——会话真实性依赖外部驱动，宿主忘 Activate 则写抑制静默失效（集成测试缺口）。

## Confidence / Known Gaps

Verified：三个代表窗口数据流、uiquery 模式、多人围栏/快照/命令链、API 契约。Mostly Verified：47 窗口中 ~40 个按名归类、ui/items 33 文件、AW3MultiplayerCatalogModels(935 行)/StrategicStateModels/SuccessionFacade(406 行)、core/presentation 24 文件仅 ArmyRtsVisualizationService 签名层。replica Activate 调用方在外部（推断）；AW3HistoryApi 面向外部 mod 为 grep 反证 + 测试符号旁证。
