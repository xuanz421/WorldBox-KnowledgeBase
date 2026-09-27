---
title: AW3 补丁目录
aliases:
  - ancient-warfare-3-patch-catalog
---

# Ancient Warfare 3 — 补丁目录（R3-AW3 C6）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。`Code/patch/` 全量 150 文件枚举（顶层 141 + naming/ 9）：**补丁方法 620**（Prefix 336 / Postfix 255 / Finalizer 23 / Transpiler 6，另有 utils 侧 [MethodReplace] Transpiler 2 处不在本目录）、目标声明 ~590 处 + TargetMethods 动态展开 ~30。装载机制见 C0（反射扫描逐类有序 + 空结果告警 + DormantPatchTypes）。目标类型 top：Actor×100、City×83、MapBox×47、QuantumSpriteLibrary×46、Kingdom×35。bool 前缀 88 文件 / 含 return false 80 文件。计数为 grep 精确匹配；用途一句话由目标方法名推断（attribute 级），个别 return false 可能属辅助方法（误差 <5%）。

## 分类表（全 150 文件）

**存档 / 世界生命周期**（clearWorld 被 16 个文件重复挂载，见风险）：AW_SavePatch（SaveManager×3+loadWorld/loadData+generateNewMap×2，P3Q3F1，存档序列化与读档恢复）；AW_WildKingdomPatch（野王国兼容 P7Q3）；AW_LoadBuildingsKingdomRepairPatch（读档修建筑归属）；AW_AutoSaveSafetyPatch；AW_AsyncWorldLifecyclePatch（clearWorld P1F1，异步生命周期）；AW_ActorDeathPatch（clearWorld+die×3+removeKing P2Q2F1）；AW_ActorDeathCheckPatch；AW_ActorBoatLifecyclePatch（BehBoat×5+embark/exitBoat+clearWorld P9Q3 船运全周期）；AW_ActorKingdomSafetyPatch（11 前缀王国空引用加固）；AW_EmptyCitySurvivalPatch（空城存活 P5Q6）；AW_WarRefugeePatch；AW_SyntheticPopulationPatch（TargetMethods 合成人口）；AW_RestorationPatch（复辟 P4Q1F1）；AW_RuntimeBenchmarkAutoLoadPatch。

**寻路与移动（热路径）**：AW_GlobalPathfindingPatch（goTo/updatePathMovement/isUsingPath+WorldTile 脏标记×5+clearWorld，P4Q8T1，[HarmonyPrepare]=IsAw3 条件启用）；AW_PathfindingSafetyPatch（F1 兜底，Prepare 条件）；AW_IdleBehaviourThrottlePatch（Beh*×3 节流 P7）；AW_WartimeMilitaryTaskPatch（战时禁社交/睡眠 P8）；AW_WesternTechnologyEffectPatch（西技工艺）；AW_ArmySafetyPatch（**18 前缀最大安全网**：Army/Actor/City 军队全链路 P18Q8F1）；AW_ArmyMembershipReconciliationPatch；AW_DockPathTransportPatch；AW_ArmyRtsTransportProductionPatch（buildBoatFromHere+TaxiRequest P6Q1）；AW_RtsAbstractSupplyPatch（TargetMethod 补给识别）。

**战斗 / 死亡**：AW_SpecialGovernmentCombatPatch（**休眠**）；AW_OccupiedCityCivilianProtectionPatch（占领城平民保护 P3Q1）；AW_KillPatch；AW_RoyalGuardPatch（禁卫军 P4Q1）；AW_EnlistPatch（征兵 P4Q3）；AW_RetirementPatch（Q5 退役）；AW_SlaveryPatch（奴隶制 P6Q8）；AW_KingdomCheckCachePatch（敌对缓存 P3）；AW_EnemyFinderCachePatch（P2F1）；AW_EnemyRelationThreadSafetyPatch（敌对线程安全 P3Q2）；AW_PromotionPatch（晋升事件 P4Q4）。

**模拟调度 / 性能**：AW_FramePrioritySchedulerPatch（**~1,700 行 58 方法【SpecialPatch 手动调用】**：StatusManager.update+MapBox.Update×5+QuantumSpriteLibrary draw*×44+Actor.updatePos 等 P48Q7T2F1，嵌套 DebugRenderBoundary 类 24 动态目标）；AW_DeferredRuntimeWorkPatch（MapBox.Update 排空，C0 已验）；AW_CityManagerMutationBoundaryPatch（P2F1）；AW_CityBenchmarkPatch；AW_ActorAiBenchmarkPatch；AW_RuntimePerformanceDiagnosticPatch（P5Q5F1）。

**城市 / 王国治理**：AW_CityLeaderPatch（C2a 已验）；AW_CityOccupationAccelerationPatch（占领加速 P4Q5）；AW_CityReservePoolPatch；AW_BanditStrongholdZonePatch；AW_BuildCityPatch；AW_BuildingKingdomSafetyPatch；AW_BuildingNullSafetyPatch；AW_CityBuildNullSafetyPatch；AW_BuildingTweenSafetyPatch；AW_EnclosedUnownedZonePatch；AW_KingdomAgeSafePatch；AW_KingdomExtinctionPatch（灭国控制）；AW_KingdomPolicyPatch（P1Q4）；AW_KingdomColorPatch；AW_KingdomRenamePatch；AW_RepublicGovernmentPatch（共和政体）；AW_MandateSuccessionPatch（天命继承）；AW_MandateBorderWallPatch；AW_HierarchicalVassalOccupationPatch（附庸着色）；AW_CivilianInstantBirthPatch；AW_XiaExpansionPatch（夏族扩张）。

**继承 / 家族 / 世系**：AW_BirthPatch（C2a 已验）；AW_DynasticReproductionPatch（P1Q1T1）；AW_BabyNamePatch；AW_FigurePatch（人物卡）；AW_NobleHeirPregnancyPatch（贵族怀孕 P4Q3F2）；AW_LovePatch/LoversPatch；AW_HeirPatch（继承人 P3Q2）；AW_ShiLineageSnapshotPatch（**士族世系快照 P4Q13**：joinCity/die/LineageService×5/HeirService×3 等）；AW_ClanEventPatch/ClanNamePatch；AW_HistoricalMasterVocationPatch；AW_HistoricalSchoolPatch（**书院全景 P13Q10F1**：Building×5+updateObjectAge+die×2+joinCity/setCity/setKingdom 等）；AW_HistoricalSchoolTaxiPatch；AW_HistoricalSchoolSpawnPatch（**[HarmonyPrepare] 恒 false 禁用**，诊断隔离）；AW_HistoricalFigureCardPatch（人物卡 UI）；AW_NameProtectPatch。

**外交 / 战争**：AW_WarPatch（War×8+WarManager×4+DiplomacyManager.startWar，P8Q7F1 战争全周期）；AW_WarBattleEpisodePatch（战役段落）；AW_WarPlotRedirectPatch（计谋重定向）；AW_DiplomacyConversationPatch（盟约 P3Q3F1）；AW_VassalDiplomacyPatch；AW_ManualAllianceToolPatch（手动结盟神力 P2F1）；AW_ChroniclePatch（编年史 P6Q10，C2a 已验部分）；AW_ArmyMapInformationMinimapPatch。

**UI / 渲染 / 地图模式**：AW_ArmyRtsSchedulerPatch / AW_ArmyRtsVisualizationPatch（C2a 已验）；AW_HierarchicalVassalMapClickPatch/LabelPatch/MinimapPatch/NameplatePatch/WaterPatch（附庸地图五件套）；AW_HeirMinimapPatch；AW_XiaMinimapKingPatch；AW_MinimapBuildingSafetyPatch；AW_ActorMainSpritePatch；AW_ActorVisualRolePatch；AW_AvatarHeadPatch（**唯一 is_boat 字面守卫**）；AW_HighResolutionSpritePatch；AW_BuildingSpritePatch；AW_MandateCapitalBuildingSpritePatch；AW_ItemRenderingPatch；AW_NameplateTitlePatch/VassalNameplatePatch；AW_CityTabPatch/KingdomTabPatch/KingdomWindowPatch/UnitTabPatch/UnitWindowPatch（窗口注入）；AW_TraitWindowSafetyPatch（泛型 sortTraits）；AW_WindowCreationPatch/WindowHistorySafePatch；AW_SelectedActorAvatarSafetyPatch；AW_CursorPresentationLifecyclePatch；AW_PowerButtonVisualPatch；AW_ModConfigSelectPatch；AW_MapModeMetaTypePatch（自定义地图模式元类型 P4）；AW_MapModeTooltipPatch；AW_MandateMapModePatch/WarMapModePatch/VassalMapModePatch/TechMapModePatch（四件套各 Q3）；AW_ZhuluWorldAgePatch；AW_UiWorldAgeInfoPatch（**SpecialPatch 手动调用**）；AW_WorldLogGuardPatch。

**内容 / 资产 / 命名**：AW_SkeletonSpawnPatch；AW_XiaCultureIntegrationPatch；AW_XiaKingScalePatch；AW_XiaNamingPatch（P2Q5 夏命名）；AW_WesternTechnologyEffectPatch（见移动组）。**naming/ 9 文件**（与外部中文取名 mod 冲突时按 namespace 整体跳过，ModClass:158-160 → AWNamingCollisionRules.cs:34-47）：AW_ActorLocalizedNamePatch / ActorManualNamePatch / CityStateNamePatch（泛型）/ CultureNamingTraditionPatch / FamilyIdentityPatch / KingdomNameEditPatch / LanguageChangeNamePatch / MottoEditPatch / WorldLocalizedNamePatches（P1Q13 命名总集）；ActorManualNameInputSynchronizer.cs 无补丁（辅助类）。

## 特殊类别

- **SpecialPatch 手动调用（2）**：AW_FramePrioritySchedulerPatch（ModClass:99）、AW_UiWorldAgeInfoPatch（:132，对已存在实例补挂 tooltip——Awake postfix 只对新实例生效）
- **Dormant（2）**：AW_DirtyMetaActorIndexPatch（11 前缀接管 updateDirtyUnits，索引常建收益未接）、AW_SpecialGovernmentCombatPatch（极热路径，待实机）——理由文档化于 ModClass.cs:37-54
- **[HarmonyPrepare]（3）**：AW_GlobalPathfindingPatch / AW_PathfindingSafetyPatch（`AWPathfindingRuntimeMode.IsAw3` 运行模式开关）；AW_HistoricalSchoolSpawnPatch（硬 return false 诊断隔离）
- **命名冲突跳过**：naming/ 全部 9 文件（检测外部中文取名 mod 时 namespace 级整体跳过 + 一次告警防刷屏）

## 风险标记

- **MapBox.clearWorld 被 16 个文件各自挂载**（ActorDeath/ActorBoatLifecycle/ActorKingdomSafety/ArmyRtsVisualization/AsyncWorldLifecycle/CityManagerMutationBoundary/DeferredRuntimeWork/FramePriorityScheduler/GlobalPathfinding/HierarchicalVassalMapLabel/HistoricalSchool/IdleBehaviourThrottle/Restoration/ShiLineageSnapshot/WarBattleEpisode/WarRefugee）——清空顺序敏感
- **高重复目标**：City.setKingdom ×8 文件、Kingdom.setKing ×7、Actor.die ×7 文件 9 处、BabyMaker.makeBaby ×5、Actor.joinCity ×5、MapBox.Update ×8 文件 12+ 处、QuantumSpriteLibrary.drawKings ×3
- **约 40% 目标用字符串名私有 API**（"u1_checkInside"/"u10_checkSmoothMovement"/"updateDirtyUnits"/泛型 sortTraits 等）——游戏更新静默失效风险（ModClass 空结果告警只覆盖类级）
- 全局无守卫 veto：Dormant 两个（当前停用是正确决策）

## Reusable / Anti-patterns

做法：类级 [HarmonyPatch] 必挂 + 空 Patch() 结果显式告警（防 PatchClassProcessor 静默失效）；[HarmonyPrepare] 做运行模式开关与诊断隔离 + DormantPatchTypes 灰度；namespace 级条件跳过（naming 冲突）+ 一次告警；安全网补丁（*SafetyPatch）与功能补丁文件分离。

反模式：clearWorld 16 文件各自挂载无统一生命周期分发器；字符串名私有目标 + 同目标多文件重复 patch，副作用叠加顺序不可控；单文件巨型补丁（FramePrioritySchedulerPatch 58 方法/46 处 QuantumSprite 目标）。

## Evidence Status

逐行：ModClass 装载段、AWNamingCollisionRules、SpecialPatch 两文件、[HarmonyPrepare] 三文件体、TargetMethod 两文件。attribute 级（grep）：全部 150 文件的目标行与补丁类型计数；用途一句话为方法名推断。
