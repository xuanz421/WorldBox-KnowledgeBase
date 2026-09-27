---
title: AW3 朝廷、郡县与学派
aliases:
  - ancient-warfare-3-court-county-schools
---

# Ancient Warfare 3 — 朝廷、郡县与学派（R3-AW3 C3）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批全文精读 CountyAdministrationService/CountyZonePartitionRules、CivilServiceExamService/Rules 与 CourtDirectionService，CourtService（3,414 行）策略性精读约 60%，core/schools 86 文件读核心 8 个。除注明外核心主张逐行 Verified。

## Scope

- 覆盖：朝廷层级/官职生命周期/六指标快照、科举考试状态机、郡县分区算法、学派实体与流水线、Courtjson 模板机制
- 不覆盖：天命/外交域（→ [mandate-diplomacy-vassalage.md](mandate-diplomacy-vassalage.md)）、UI 窗口（→ C5 批）、考试 SQL 细节

## 朝廷系统（CourtService.cs，3,414 行）

- **层级演进链**：primitive（启用+未完成 aw_tech_official_court）→ official → three-departments（CourtService.cs:176-197）；制度由 `CourtInstitutionService.Refresh` 按已解锁科技解析（Zhou→Han→Tang→Song 三条 tech，Western 线走 policy effect），写 `COURT_INSTITUTION`/`COURT_TIER`（CourtInstitutionService.cs:26-70）
- **年度驱动** `OnKingdomYear`（:745-817）：Refresh 制度 → 改制当年立即 ValidateOfficers（**绕过 5 年节流防旧官挂 5 年**，:756-762 注释）→ 记编年史 OnCourtFounded/OnCourtTierUpgraded → RecalculateFactionCache → 城市官署分片 → EvaluateStrongEvent → UpsertCourtSnapshot
- **官职补缺三级候选** `FillCentralOffice`（:1179-1250,1394-1424）：科举正式候选索引（CivilServiceFormalCandidateQuery，仅考试制开启）→ 花名册严格候选 → 署理（须 HistoricalSchoolEducationService.IsEducated；central 层禁署理兜底 :1230-1237）。资格门含 CivilServiceQualificationService（:1752-1772）
- **评分** `ScoreCandidate`（:1463-1517）：int+stewardship 基础，Marshal×2 warfare / 太医太史×2 intelligence，贵族 +4（封建 Unlock 后领主 +6、教育 +3），九品官品匹配 + **请托**（CourtPetitionService.AppointmentFavor）+ **世族恩荫**（CourtAristocraticGroupService.AppointmentPatronageBonus）+ 学派兼容
- **罢免/替换事务化**：ClearOfficer 清 actor 五键 → OfficialCareerService.End → vacancy 登记（:2750-2804）；ReplaceOfficer 旧官 close + 客卿 end + 新官 appointment 同事务（:1926-1998）；读档后从 OfficialCareerState 权威行重建投影（:2336-2360）+ 双写校验 IsValidActiveOfficeActor（:3328-3364）
- **六指标快照**（GetSnapshot :357-379）：efficiency = min(100, 35 + 在任官影响力总和×3)（:2939）；concentration = 主学派占比；**direction 七维**（livelihood/war/aggression/peace/order/commerce/technology）由 CourtDirectionService 按国王权重 8、储君 5、在任官 4×品级、将领 3、城主 5 聚合 + **EMA(α=0.25) 平滑**（CourtDirectionService.cs:16-126）
- **对模拟的实际影响**：efficiency → 年度城市官署工作分片（CityBureauAnnualWorkService.cs:26-46）；direction → 相权 DirectionMultiplier 与官职影响力修正（:92-95）；dominant 学派长期主政 + 危机/弱君 → 朝廷改制事件（:3031-3051）；任官改 SocialStandingService 门第（:2638-2653）；非署理任命授"氏+族"身份；县令任命迁居县治（RelocateCountyMagistrate :2709-2733）

## 科举考试（CivilServiceExamService.cs）

- **周期**：每王国锚定开考年（制度完成年+1），**每 3 年一科**（CivilServiceExamRules.cs:129-133）；ExamCycleService 统一驱动文/武两科
- **模式**：imperial_exam（乡试 Local→会试 Metropolitan→殿试 Palace→**玩家可提交排名**，前三授状元/榜眼/探花 :445-451）vs tributary_exam（Prefectural→National）（:110-114,811-846）
- **候选人**：成年男性/非奴/国内或客居学派 Resident（:219-238）；InviteForeignScholars 年限 4 名外国学者应邀入都（:250-289）；名额 = f(中央空缺+城空缺+等待池+储备目标)（:198-216）
- **评分**：knowledge(int) + 阶段能力（各试不同科目组合）+ **教育分 = 学派在读年限×5 上限 30 + 声望/10**（:940-951）+ 确定性抖动 DeterministicJitter(sessionId,actorId,stage)（Rules.cs:712）；PassMark=60
- **状态机**：DueSessions SortedSet 按世界日驱动 `ProcessAuthorityCycle`（:291-322），分页打分（8 人/步），ruler 死亡写请求带 worldGeneration 幂等键与重试队列（:1095-1180）；录取后唤醒补缺（:462-464）

## 郡县制（core/county/）

- **分区算法** `CountyZonePartitionRules.Partition`（CountyZonePartitionRules.cs:12-63）：每县 ≤25 zones、每城 ≤3 县（:9-10）；**BFS 连续性排序**（最小 zone id 起按邻接扩散，跨连通分量重启）后等分成 countyCount 段——确定性分区
- **ReconcileCity**（CountyAdministrationService.cs:12-148）：构建邻接图 → 分区 → 与既有 Active 记录按 zone 重叠**最大匹配**（:89-109）→ 无匹配新建 → 命名三级回退：历史 commandery 未用名 → 州内未用县名 → 全目录未用名，皆无则 城名+"县"+序号（:118-132）
- **历史名录**：XiaHistoricalDeJureCatalog 从 JSON 加载 states/commanderies/countyNames（:95-119），偏好持久化 id + seat 城
- **失活与同步**：zones 全死→Active=false（:20-29）；分区缩小退役保留历史（:141-147）；世界载入全量重跑 RepairAfterWorldLoaded（Store:79-85）+ 权威周期每轮 4 城 RepairDirtyCities（AWAuthorityCycleService.cs:335-342）
- **持久化特例**：**非 SQLite 表**——JSON sidecar `aw3_counties.json`（schemaVersion 2，原子写）随存档读写（CountyAdministrationStore.cs:11,35-55）

## 学派（core/schools/，86 文件）

- **实体模型**：学派挂 **actor 级成员资格**（SchoolMembership 表：actor/school/source/teacher/generation/reputation），学派无 kingdom 绑定；actor 另有 AffiliationSnapshot 生命周期机（Queued→Descended→…→Resident→Serving→Retired，HistoricalSchoolState.cs:9-25,230-260）
- **成员来源六种**：HistoricalDescent/DirectDiscipleship/LaterDiscipleship/ExplicitConversion/PreservedWork/AuthoredEvent（:27-35）；TryJoin 五步事务（flush 谱系→预留 id→Insert→索引→revision apply），失败回滚（SchoolMembershipService.cs:177-215）；TryConvert 禁止改谱系成员（:220-252）
- **调度** `HistoricalSchoolScheduler`：年度 **13 阶段流水线**（Bootstrap→AcademyRepair→Descent→ServiceClose→ServiceAppointment→Promotion→Recovery→LecturePlan→DebatePlan→Conversion→Rediscovery→RuntimeCommit），帧预算 0.75ms（HistoricalSchoolScheduler.cs:15-27,70-120）
- **大师**：content/schools 定义（Wave/PreferredStateNames/能力剖面），谱系分账每大师只 spawn 一次（HistoricalSchoolState.cs:166-202）
- **著作与复活**：SchoolWork 表记录写作产物；学派覆灭后靠"**遗书 rediscovery**"复活（CanRediscover：livingMembers + hasPreservedSource，HistoricalSchoolRules.cs:523；MaxRediscoveriesPerYear=4）
- **论战**：年度有界 pass（≤48 场/年、≤256 城、每城≤32 候选），胜负五档（Draw/Narrow/Decisive），胜场持久化
- **与朝廷耦合**：成员挂学派 trait（14 家儒/法/道/墨…，CourtService.cs:2888-2905）；在读年限 = 科举教育分来源；在任影响力决定 dominant_school/efficiency；Serving 态受聘客卿（SchoolGuestOfficeService）

## Courtjson 模板机制

- Root=`<mod>/Courtjson`（Central/Local 子目录，CustomCourtTemplatePathService.cs:12-39）；模板 JSON SchemaVersion 3：Offices（Layout X/Y/Lane、Requirements、Effects）+ Edges + 内嵌 LocalTemplates
- 原子持久化：TrySave tmp→round-trip hash 校验→File.Replace（CustomCourtTemplateStore.cs:35-76）
- 应用：TryApply 构造 CustomCourtInstance（TemplateId/Revision/Hash），旧模板被删官职在任者归档 LegacyOffices（CustomCourtApplicationService.cs:20-75）；运行期影响官职影响力修正（CourtDirectionService.cs:92-93）与任命前置 HasPrerequisiteOffice（CourtService.cs:1739-1750）

## 持久化映射（域→表）

朝廷→KingdomCourtState/CourtOfficer/OfficialCareerState/CityBureauState；科举武举→CivilServiceExamSession/Candidate、MilitaryExamSession/Candidate、MilitaryOfficerRecord；郡县→**aw3_counties.json sidecar（非 db 表）**；学派→SchoolMembership/SchoolAffiliation/SchoolWork/SchoolDebate/SchoolEvent/SchoolInstitution/HistoricalSchoolMaster/HistoricalSchoolRuntimeState。

## Unique Methods（C3 批新增候选）

- `CountyZonePartitionRules.Partition` (Code/core/county/CountyZonePartitionRules.cs:12-63) — BFS 空间连续排序后等分 ≤3 县的确定性分区
- `CourtService.RecalculateFactionCache` (Code/core/court/CourtService.cs:2907-2947) — 按学派累加在任官影响力得 dominant/concentration/efficiency
- `CourtService.ScoreCandidate` (:1463-1517) — 能力+出身+学派+恩荫+请托的多维候选评分
- `CivilServiceExamService.ProcessAuthorityCycle` (:291-322) — 世界日驱动的考试状态机（分页打分/排名/殿试玩家 pending）
- `CivilServiceExamService.EducationScore` (:940-951) — 学派在读年限+声望折算教育分
- `CourtDirectionService.RecalculateIfDirty` (Code/core/court/CourtDirectionService.cs:16-126) — 脏标记 + EMA(0.25) 平滑的朝廷七维方向重算
- `HistoricalSchoolScheduler.ProcessFrame` (Code/core/schools/HistoricalSchoolScheduler.cs:70-120) — 0.75ms 帧预算的年度 13 阶段学派流水线
- `HistoricalSchoolActionService.TryRediscover` (:286-311) — 依存世遗书复活覆灭学派
- `CountyAdministrationService.ReconcileCity` (:12-148) — zone 邻接分图与县记录按最大重叠匹配增删改

## Reusable / Anti-patterns

做法：双写校验 + 权威恢复（DB 行与 actor 运行时键互验，失败先 restore 再清行 :2806-2886）；候选选择按 (actor|office|layer) 记忆化（:127-174）；**代码内性能注释文化**——精确到索引的 SQL 重写说明（覆盖索引替换 9 列装箱扫描，"要一个整数却读回 96 行×9 列再 LINQ" 的 88ms 案例 :498-554）；原子 JSON 持久化模板（tmp→hash 校验→Replace）；有界工作（考试 8 人/步、学派 0.75ms、论战 48 场/年）。

反模式：**脏队列只进不出**——CountyAdministrationStore.RepairDirtyCities 曾无调用者导致新城市永远无县（AWAuthorityCycleService.cs:335-342 注释留证），CourtVacancyReconciliationService 同类断线；5 年节流闸挡改制清理（:755-762）；用失败布尔混同技术故障→死县无限重试（:2293-2298 注释）；sidecar 双源（郡县 JSON vs CourtOfficer SQLite）靠载入全量 reconcile + 每周期 4 城修补缝合。

## Confidence

郡县/科举/CourtDirectionService/学派核心全读 Verified；CourtService ~60% 精读（官职 profile 明细、OfficialCareer SQL 细节、SchoolGuestOfficeService 1,615 行、HistoricalSchoolStore 3,717 行、MilitaryExamService 仅签名级 → Mostly Verified 汇总）。

## Known Gaps

- CourtProfileRegistry/XiaCourtProfile/WesternCourtProfile 官位 profile 明细
- SchoolGuestOfficeService（1,615 行）、HistoricalSchoolTravelService（1,335 行）、HistoricalSchoolEliteEnrollmentService（1,056 行）主体
- CivilServiceExamCandidateQuery.Build 内部 SQL；MilitaryExamService 全文
- 县视图 UI（CourtReadModelService.BuildLocal）归 C5 批
