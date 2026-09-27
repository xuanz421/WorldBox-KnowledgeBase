---
title: AW3 天命、战争导演与外交封臣域
aliases:
  - ancient-warfare-3-mandate-diplomacy
---

# Ancient Warfare 3 — 天命、战争导演与外交封臣域（R3-AW3 C2b）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批全文精读 MandateService（3,606 行）、ArmyRtsTransportService（1,223 行）、KingdomWarDirectorService（2,146 行）、MandatePhaseService 与相关 Rules；外交/封臣/继承/间谍域为签名+局部段级证据。

## Scope

- 覆盖：天命六指标与改朝换代链路、战争导演分帧规划、海运四相位、外交/封臣/继承争端/复辟/间谍/奴隶域、域→表持久化映射
- 不覆盖：军队控制器与状态机（→ [army-rts.md](army-rts.md)）、SQLite 管线本体（→ [persistence-archive.md](persistence-archive.md)）、朝廷科举（→ [court-county-schools.md](court-county-schools.md)）

## 天命系统（MandateService.cs）

- **单行状态机**：STATE_ID=1 单行 `MandateState`（:53），`ReadReportFromDb` 读 20 列 + `FillDynamicReport` 动态算 core_control/vassal_loyalty（:2726-2781）。core_control = 已控法理核心占比（owner==天命国或其宗主才计入，:3220-3232）；vassal_loyalty = 附庸外交 opinion 归一平均（:3258-3270）
- **六指标**（MandateReport :15-40）：authority 每年重算 `25 + mandate×0.35 + core_control×25 + vassal_loyalty×15 + 城数×1.2` clamp 0-100（:2628-2633）；prestige 只增不减 clamp 0-999（:397）
- **年度 delta**（MandateAnnualDeltaRules.cs:49-95）：战争 −2/和平 +1；最强竞争国压制；core≥0.85→+2、<0.5→−4；loyalty≥0.7→+1、<0.35→−2；继承人稀缺；史实君主 +5/幼君 −1/智≤5 −1；**age_despair/ash/chaos −12**
- **crisis 阶梯**（:3528-3535）：≤−30 collapse、<20 lost、<40 shaken、≥80 golden、其余 stable
- **崩溃链路**：value≤−30 或 chaos 超时（满 8 年未解决，MandateDeclineRules.cs:14,35-39）→ 史实君主一次性 4 年宽限（MandatePhaseService.ResolveCollapseProtection:131-147）→ `CollapseMandate`（:1617-1630）= ForceChaos + FeudatoryCollapseService + MandateRebelService + ClearMandate。恢复条件：mandate≥40/authority≥40/core≥0.7/无宣称者/无逐鹿战争/catalyst≤40 连续 3 年（:57-64）
- **阶段机**（MandatePhaseService.cs）：Golden/Decline/Chaos/Renewal 四相，catalyst_score 年度衰减+事件增减，阶段变更回调 CentralizationService/MandateMilitaryPhaseService（:288-289）；Renewal 期战争导演转扩张、Decline/Chaos 转保守（KingdomWarDirectorService.cs:1478-1482）
- **tianming 战争生命周期**：OnWarStarted 给参战方盖"开战首都"快照编码进 War.data 键（"a|id|cap;d|id|cap"，:1904-1928，只补缺不覆盖）；OnWarEnded（:1697-1762）：天命防守败→首都圈划转+ClearMandate+按胜者身份转朝（rebel→tianmingrebel_war / 非夏→pseudo_foreign_war / 否则 tianming_war）；防守胜 +12；普通败按 WarScore −4/−7/−9
- **首都圈级联**：OnCityCaptureCompleted（:1216-1340，joinAnotherKingdom Postfix）：敌对占领者拿下开战首都 → 法理州城+接壤城合并划转（MandateCoreTransferRules），**50% 概率只划一半、留后半给旧朝最年轻高属性宗室男性作"枭雄割据"候选人**（TryFindRumpClaimant :1342-1388）；[ThreadStatic] 防级联重入（:50-51）
- **改朝换代**：OnRulerSucceeded（:291-339）迁移 aw_tianming trait + Emperor 称号；声明走 **outbox 事务**：TryDeclareMandateCore（:469-629）写 MandateDeclarationPersistence + MandateProjectionOutbox，再幂等逐条发布（:631-727）；OnKingdomDestroyed → "最后一城征服者"缓存转移天命（:2111-2157）
- **自动天命**：无天命时逐年选最强独立国（GetAutoMandateCandidateId :2488-2541）；宣言门槛：非附庸、完成 aw_policy_mandate_rites、≥4 城、core≥0.65（:905-968）

## 战争导演（KingdomWarDirectorService.cs，2,146 行）

- **规划循环**：分帧四阶段 PlanningStage Wars→Armies→Fronts→Publish（:40-46），每帧一个 work item，generation 递增失效旧任务（Schedule :377-388）；world tick 驱动 ProcessFrame :624-671
- **战争筛选**：WarAllocationFacts 打分取前 N（:834-885）；威胁源=首都被冻结占领/正在被攻（IsCapitalThreatened :1864-1872）；军队 EffectiveForce 由 ArmyOperationalDirectorRules.Project(兵力,补给,组织) 折算（:934-947）
- **前线目标**：FrontScanWork 增量扫描己方城（防御）+敌方城（进攻）逐城记 FrontTargetFacts（含 formalGoal/corridor/transportReachable :262-322）；可 async 预取（:1098-1110）
- **任务发布**：PublishShadow（:973-993）构建 KingdomWarDirectorShadowSnapshot（含 RequiredRatioBasisPoints :8-36）→ ApplyDirectorSnapshot 落地；三阶段分派（BuildFrontTargetAssignments :1285-1407）含搁浅军队 Rebalance；联盟盟主经 CoalitionWarTaskService 账本声明式领任务（TryResolveTarget :257-313）+ ReplaceLeaderReservations 向盟友发布预留（:1390-1402）；任务 ID 稳定=StableTaskId(city,side)，优先级 formalGoal 400/首都 300/弱守 200/其他 100（:110-119）
- **玩家边界**：director 使命一律 PlayerOrder=false（:559,613,763）；进攻连续性 EnsureOffensiveContinuity :519-563 与攻下城后同军续派 TryContinueSameArmyAfterCapture :565-617

## 海运四相位（ArmyRtsTransportService.cs 全读）

- **状态机**：内部 8 态 ArmyRtsTransportP0Stage（RoutePending→AssembleAtEntry→BoatToPickup→Boarding→Sailing→Landing→Complete/Failed，Rules:12-22），对外四相位映射 GetPhase（Service:126-143）；每帧 `ResolveP0Stage` 由五个纯函数条件推导（Rules:127-142, Service:415-432）
- **临时船生命周期**：`TryProvisionAtRoute`（ArmyRtsTransportProductionService.cs:227+）在路线船坞 buildBoatFromHere 即时造船——每国上限 3 艘（:13）、需求 30s 过期/3s 重试（:14-15）；OwnedTransportBoats 注册后跳过 batch 重建，由原生 b4/b5/u10 管线驱动（Service:721-737）；统一销毁 DestroyTemporaryTransportBoats :1061-1074 + 每帧清残（ProductionService:282-315）
- **超时与诊断**：Pending 120s / Assigned 240s / 最多 3 次预登船超时（Rules:123-125，配合 ArmyRtsTransportActiveClock 剔除暂停时间）；Interlocked 计数器（ArmyRtsTransportDiagnostics.cs:7-14）；完成=全员登陆目标岛（LandRoster :603-638）→ 销船并回调 march/controller（CompleteVoyage :888-899）；释放强制紧急登陆（ResolveEmergencyLandingTile :962-991）；航程中压制战斗（:346-354）
- **供给**：ArmyRtsAbstractSupplyService——P0 军人从锚定城吃军粮（TryConsumeHomeRation :63-100，1s 冷却），替代原版觅食任务（Rules:13-16）

## 外交/封臣/继承域（签名+局部段级）

- **VassalService**：附庸关系持久化 VassalRelation 表 + kingdom.data.VASSAL_RELATION_ID（:445,979）；SubjectKind 三种（vassal/military_governorate/tributary :95-118）；GetRootSuzerain 递归找宗主（天命 core 计数依赖）；附庸禁宣天命（MandateService.cs:932-936）
- **DiplomacyProposalService**：提案/评估/PairChanged 事件（:105-1004+）；**DiplomaticCoalitionService**：Prepare 预览→TryCommit→OnWarStarted 挂接（:20-238）
- **SuccessionDisputeService**：BuildPreparationFacts（:86-158）依派系支持选 claimant + **领土对半分裂**（CanFormBalancedTerritorialSplit :105）；超 DeadlineYear 且实体化 → PermanentSplit + **ForceChaos("succession_permanent_split")**（:265）
- **TemporaryLevyService**：LevyPool 批量复员 + 月度征兵泵（累计扫描计数防死循环，:47-56 注释）；战损触发补充（OnMilitaryCasualty :321）
- **复辟**：AutonomousRestorationService.TryStartSelfRestoration（:98，阶段门 MandatePhaseService.CanLaunchAutonomousRestoration）；origin_type "self_restoration" 获得 refunds 清除（MandateService.cs:769-777）
- **SpyNetwork**：每年 +12 上限 200，Weak/Strong 宣称 40/100 点，Accrue 按年份差补点（SpyNetworkPointRules.cs:25-40）
- **SlaveService**：开关/管制/口粮配额（:82-158）

## 持久化映射（域→[TableDef] 表）

天命→MandateState/MandatePeriod/MandateCoreCity/MandateEvent/MandateProjectionOutbox；封臣→VassalRelation；外交→DiplomacyProposal/DiplomaticMarriage/DiplomaticCoalition/DiplomaticWarDeclaration/DiplomaticRelationModifier；继承→SuccessionDispute(+City)；复辟→RestorationCampaign；间谍→SpyNetwork(+ClaimPurchase)；奴隶→SlaveState；战争→WarGoal/WarClaim/WarScoreSnapshot/WarPeaceSettlement*/WarRecord/WarReparationsObligation。

## Unique Methods（C2b 批新增候选）

- `MandateService.OnCityCaptureCompleted` (Code/core/lineage/MandateService.cs:1216-1340) — 首都沦陷的首都圈级联划转，含 50% 枭雄割据分支
- `MandateService.TransferCapitalRingAfterMandateWar` (:1764-1871) — 战末保底：按开战首都快照补划转
- `MandateService.TryDeclareMandateCore` (:469-629) — 天命声明的 outbox 事务（三表 + 投影队列）
- `ArmyRtsTransportRules.ResolveP0Stage` (Code/core/lineage/ArmyRtsTransportRules.cs:127-142) — 海运八态阶段纯函数推导
- `ArmyRtsTransportProductionService.TryProvisionAtRoute` (:227+) — 路线船坞即时造临时船并绑定航程
- `KingdomWarDirectorService.BuildShadowMissions` (:1144+) — 战争分配+前线目标折算影子使命快照
- `CoalitionWarTaskService.TryResolveTarget` (:257-313) — 联盟战争任务的声明式领取
- `SuccessionDisputeService.BuildPreparationFacts` (:86-158) — 继承争端的领土对半分裂准备事实
- `MandateService.ReadYearlyDeltaBreakdown` (:2571+) — 年度天命增减逐项分解（供 UI）

## Reusable / Anti-patterns

做法：纯函数 Rules + Service 薄壳分离（ResolveP0Stage / MandateAnnualDeltaRules）；**Outbox 幂等投影**——写库与运行时副作用解耦，断电/副本可续投（:618-628, ResumePendingProjections :137-175）；开战时点快照编码进 War.data 且"只补缺不覆盖"规避迁都错位（:1904-1928）；分帧增量规划 + generation 失效 + 前线 async 预取（:377-388,:1098-1110）。

反模式：泛 catch{} 吞异常遍布域逻辑（:248 等）；MandateService 单文件 3,606 行混合 DTO/状态机/SQL/地图着色；`CanMutate(IsReplicaSession)` 在 20+ 入口重复；反射访问私有字段（TransportProductionService.cs:17-19 `City._boats`）；字符串编码复数状态进单键（首都快照 "a|id|cap;…"）无版本校验；魔数散落（50% 割据 `UnityEngine.Random.value < 0.5f` :1282-1283）。

## Confidence

MandateService/TransportService/DirectorService/PhaseService/AnnualDelta/Decline/SupplyRules 全文精读 Verified；外交/封臣/继承域签名+局部段 Mostly Verified（DiplomacyProposalService.Assess 内部 ~700 行、CoalitionWarTaskService Ledger 实现 :330-727、~40 个 Rules 文件未读）。

## Known Gaps

- DiplomacyProposalService.Assess 评估权重内部逻辑
- KingdomWarDirectorRules（1,213 行纯函数侧）仅经调用点推断
- MandateRebelService.SettleRebelGovernment、Restoration* 三服务（Coup/Uprising/Protection）主体
- AsyncKingdomStrategyService（Ai lane 战略规划）归 C0 后续/C2b 补遗
