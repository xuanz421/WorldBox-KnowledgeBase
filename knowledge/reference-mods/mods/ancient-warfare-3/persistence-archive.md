---
title: AW3 SQLite 档案与存档集成
aliases:
  - ancient-warfare-3-persistence
---

# Ancient Warfare 3 — SQLite 档案与存档集成（R3-AW3 C1）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批覆盖 `Code/core/db/`（118 文件：管线 14 个 + 表类 6 个精读，其余按簇勘察）、`Code/patch/AW_SavePatch.cs`（全读）与 `Code/core/historyapi/AW3HistoryReadService.cs`（全读）。除注明外核心主张全部逐行 Verified。

## Scope

- 覆盖：schema 生命周期、异步写管线、读路径与订阅、存档 save/load 集成、进程隔离运行时库
- 不覆盖：调度协议本身（→ [async-and-performance.md](async-and-performance.md)）、写请求的域来源（Mandate/Court 等 → C2/C3 批）

## Schema 生命周期

- **建库** `LineageArchiveManager.CreateDataBase`（Code/core/db/LineageArchiveManager.cs:81-103）：CloseAndDeleteRuntimeDb(:85) → SQLiteConnection.CreateFile(:87) → Open → `LineageArchivePragmaService.Configure`(:90) → epoch++(:91) → InitializeTables(:92)。失败仅置 `InitializeSuccessful=false`(:98) 档案停用
- **Pragma**（LineageArchivePragmaService.cs:15-46）：`journal_mode=WAL`、`synchronous=NORMAL`、`busy_timeout=2500`、`cache_size=-32768`（32MB，注释含实测）、`wal_autocheckpoint=0`（检查点移交后台服务，注释含 266ms 提交尖刺实测）
- **反射建表**（LineageArchiveManager.cs:518-524）：先 `LocalizedNameIdentitySchema.Ensure`(:520，自带主键迁移/Repair)，再遍历程序集 `[TableDef]` 类字段类型推断列型 → CreateTable → `LineageArchiveIndexManager.EnsureIndexes`（索引声明式 `CREATE [UNIQUE] INDEX IF NOT EXISTS`，LineageArchiveIndexRules.cs:15-21）
- **迁移策略**：无 schema version 表、无 user_version——迁移=幂等补列 `EnsureLoadedSchema`(:530-549，剔除"版本自有列" `ARCHIVE_RESOLUTION`，LineageFamilyArchiveMigration.cs:50-57) + 个别表自愈 + 专用 Serializable 事务迁移（LineageFamilyArchiveMigration.Run:59-75）。**跨大版本演进脆弱（反模式）**

## 写路径端到端

- **生产者**：11 处调用 `HistoricalWriteService.TryAppendHistory/TryUpsertState/TryEnqueueCustom`，分布在 HistoryWriter、LineageArchiveWriter、ActorDeathArchiveService、CivilServiceExamService、EraAtomicPersistence、RulerTitleCommitService 等（core/lineage|court 下）
- **入队**（HistoricalWriteService.cs:186-253）：Gate 锁内分配 EVENT_ID(:203)、`HistoricalWriteSqlBuilder.BuildInsert` 参数化 SQL（标识符白名单校验，HistoricalWriteSqlBuilder.cs:116-138）；State 写用 `UPDATE...;INSERT...WHERE changes()=0`（:47-102）。容量 Append 8192 / State 4096 / 完成批 512（AWAsyncWorkRules.cs:46-50）；State 信封按 OperationKey 去重替换（HistoricalWriteQueue.cs:43-52）
- **Worker**：单条专用后台线程 "AW3 Historical DB Writer"、BelowNormal（HistoricalWriteWorker.cs:239-245），批 64(:164)。**事务边界=整批**：BeginTransaction → 逐条 ExecuteNonQuery → Commit（HistoricalSqliteBatchSink.cs:57-81）
- **失败语义**：仅 SQLITE_BUSY/LOCKED 可重试（指数退避 4ms×2^n、最多 3 次，HistoricalWriteWorker.cs:147-148,471-473）；超限→**终态故障**：当前批+整队封装为失败 completion、回调 onFailed、后续 Flush 立即报错（:573-593）——不静默丢。epoch 守卫：库被换即拒写（BatchSink:107-112）
- **同步回退**：逐操作而非全局——`HistoricalSynchronousWriteCoordinator.TryAppendOrExecute`(:77-127)：异步失败且已预留 eventId → 先 barrier 排空 worker 再在调用者连接上同步 Insert（HistoryWriter.cs:646-667）；`TryExecute` 用于原子多表事务（EraAtomicPersistence.cs:70 等）
- **lane 关系**：写线程是独立 Thread，不占 AWAsyncWorkCoordinator 的 lane；协调器只提供 WorldGeneration/生命周期（AWAsyncRuntime.cs:24,52）

## 读路径与订阅

- **直连**：约 40 个服务文件直接 `LineageArchiveManager.Instance?.OperatingDB` 裸写 SQL（如 MandateService.cs:60）——主线程短查询（反模式：绕过异步管线，主线程尖刺风险）
- **后台读** `AW3HistoryReadConnection.TryRead`（AW3HistoryReadConnection.cs:11-32）：捕获 epoch → Task.Run 在外部线程开**只读独立连接**（ReadOnly/FailIfMissing/Pooling=false）→ 读毕校验 epoch 未变否则弃结果——"自带连接 + epoch 快照一致性"
- **分页**：游标键 `(WorldTime, Domain, Source, RecordId)`；SQL 侧 `LIMIT 512` 预取（AW3HistoryReadService.cs:286,343,652）+ 内存侧游标过滤/排序截断（:765-793）——反模式：无条件预取 512 行再内存过滤
- **订阅发布**：纯内存事件非 DB 轮询——写提交后 `PublishHistoryRow` 从 OperatingDB 读回已提交行（AW3HistoryEventPublisher.cs:104-112）、identity+projection 双键去重（:114-132）、入队上限 1024 溢出丢最旧（AW3HistorySubscriptionRegistry.cs:32-36）。失败写对订阅者不可见（:41-44）

## 存档 save/load 集成

- **保存前**（AW_SavePatch.cs:33-58 Prefix）：`EnterOwnedSaveBarrier`（AWAsyncWorldLifecycle.TryEnterSaveBarrier 5s）→ `TryPrepareForSave`(:108-186) 按序 Flush 各持久队列（含 `HistoricalWriteService.FlushForSave(5s)` :142-143），任一未清即抛 `AWSaveBoundaryException` **阻止存档**(:145-169)；最后 `CheckpointForSave`（PASSIVE wal_checkpoint，与后台检查点共享 Gate 串行）
- **保存后**（:60-92 Postfix）：`TryExportLineageArchive`（LineageArchiveManager.cs:185-267）——`_db.BackupDatabase` 到 .tmp(:211-222)，快照目标连接配 `journal_mode=DELETE; synchronous=FULL`(:216-221)，quick_check + journal 校验 + 无 -wal/-shm 残留(:224-239) → 原子 `File.Replace`(:241-245)。**文件布局：`<存档目录>/aw3_lineage_archive.db`**
- **读档侧**：loadWorld Prefix 观察(:230-240)、loadData Postfix 入队(:369-379) → `AW3WorldLoadCoordinator` 调度 → `AW3RuntimeRestorePipeline.TryRestoreFromDirectory`（AW3RuntimeRestorePipeline.cs:116-136）从 `<saveFolder>/aw3_lineage_archive.db` File.Copy 覆盖运行时库 + EnsureLoadedSchema + presence 重建
- **新世界/分支**：缺失档案且规则判 `InitializeFresh` → `CreateDataBase()` 空库；否则 `DisableRuntimeArchive()` fail-closed（:129-131）——**恢复失败绝不以空库顶替**，错误码 `IsMissingArchiveError` 区分"缺失可重建"与"损坏须终止"

## 进程隔离运行时库

- 路径 `<modFolder>/.runtime/process-<pid>/aw3_lineage_archive.db`（LineageRuntimePathRules.cs:8,18-20）——多开互不干扰。多人复制安装 `TryInstallReplicationArchive`(:269-447)：SHA-256 校验 + quick_check + staging/backup 三段式安全热替换
- **清理缺口**：无过期 `process-<pid>` 目录清扫（grep 无命中）——崩溃残留目录会遗留
- **后台 WAL 检查点**：权威周期 ~50Hz 调 `RequestIfDue`（AWAuthorityCycleService.cs:442；LineageArchiveCheckpointService.cs:73-99），≥2s 间隔、连败 3 次自禁用；关库唯一收口 `CloseRuntimeDatabase`(:457-469) 必须先 `CheckpointService.Shutdown()`（否则第二条连接使 Windows File.Delete 失败，:459-462）

## Unique Methods（C1 批新增候选）

- `LineageArchiveManager.TryExportLineageArchive` (Code/core/db/LineageArchiveManager.cs:185-267) — BackupDatabase + journal_mode=DELETE + quick_check + sidecar 检查 + 原子 Replace 的五重快照导出
- `HistoricalWriteService.TryAppendHistory` (Code/core/db/HistoricalWriteService.cs:186-253) — 锁内分配 EVENT_ID、构建插入信封、入异步队列
- `HistoricalWriteWorker.WorkerLoop` (Code/core/db/HistoricalWriteWorker.cs:384-548) — 单线程批量取批→整批事务→busy 退避→终态故障聚合上报
- `HistoricalSqliteBatchSink.Execute` (Code/core/db/HistoricalSqliteBatchSink.cs:44-95) — 整批单事务 + epoch 守卫 + 可重试分类
- `AW3HistoryReadConnection.TryRead<T>` (Code/core/historyapi/AW3HistoryReadConnection.cs:11-32) — 外部线程只读连接 + epoch 快照一致性的统一读封装
- `LineageArchiveManager.TryInstallReplicationArchive` (Code/core/db/LineageArchiveManager.cs:269-447) — 多人复制档案的 staging/backup/live 三段式安全热替换

## Reusable / Anti-patterns

做法：五重保障快照导出（BackupDatabase+DELETE 模式+quick_check+sidecar+原子 Replace）=「SQLite 随存档持久化」可移植模板；读档 fail-closed 绝不用空库顶替；事务整批化 + 仅 BUSY/LOCKED 可重试 + 终态 onFailed 显式回调——异步写丢数据语义清晰；epoch 计数器统一守卫写连接与读快照，世界切换自动作废新旧操作；checkpoint 双路（后台 PASSIVE 保延迟、存档前主线程 PASSIVE 保确定性，共享 Gate 串行）。

反模式：~40 个服务直连 OperatingDB 裸写 SQL 绕过异步管线；读服务手写字符串 SQL + 按列序号取值（列变更即错位）；分页先 LIMIT 512 无条件拉取再内存过滤；无 schema 版本管理（隐式迁移跨大版本脆弱）；Worker 异常路径靠 catch-all 兜底（自述"转义异常会静默杀进程"，HistoricalWriteWorker.cs:497-523）。

## 表类清单（118 文件，未精读部分按簇）

精读：管线 14（Manager/Pragma/Checkpoint/IndexManager/IndexRules/RuntimePathRules/WriteService/WriteQueue/WriteWorker/BatchSink/SqlBuilder/SyncCoordinator/ModeRules/LocalizedNameIdentitySchema）+ 表类抽样 6（PersonBiography/ActorArchive/KingdomHistory/CourtOfficer/FamilyEdge/LineageGroup）。
按簇：王朝天命（DynastyPeriod/MandateState…）、王国史典章（KingdomCore/Reign/PolicyState…）、官制科举（CourtOfficer/CivilServiceExam/OfficialCareerState…）、学派（SchoolInstitution/HistoricalSchoolMaster…）、战争外交（WarRecord/WarScoreSnapshot/PeaceSettlement/Diplomacy*…）、谱系人物（FigureState/FamilyEdge/RulerHousehold/PosthumousTitle…）、封建城邑（Feudatory/FiefGrant/CityHistory…）、僭主继承（SuccessionDispute/RestorationCampaign/SpyNetwork…）、运维规则（HistoryEventIdAllocator/各 MigrationState）。

## Confidence

管线核心（第 1-5 节全部主张）Verified——逐行核对；表类簇清单文件名级 Mostly Verified；AW3WorldLoadCoordinator / HistoryWriter / AW3RuntimeRestorePipeline 为上下文摘读（属 C2/C5 批，相关行号已直接引用）。

## Known Gaps

- 表类 118 个中 ~110 仅文件名级勘察；具体列定义与索引设计未逐一记录
- 写请求的域级来源语义（Mandate/Court 各自写什么表）归 C2/C3 批
- AW3WorldLoadCoordinator 的完整调度时序归 C5 批（多人/加载协调）
- checkpoint 服务与 authority cycle 的交互频率仅确认调用点，未量化实测
