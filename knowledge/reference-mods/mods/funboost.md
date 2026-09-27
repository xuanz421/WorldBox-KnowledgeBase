---
title: 趣玩增益FunBoost
aliases:
  - funboost
---

# FunBoost（趣玩增益）

## Identity

- Name: 趣玩增益FunBoost v1.1.5（mod.json:2-7，guid `daybreak_funboost`，author 半梦半醒）
- Source ID: `ref:funboost`
- Dir: `FunBoost_1.1.5`
- Files: 49 total / 40 C#
- Confidence: Verified

## Purpose

通过 42 项运行时可开关的 Harmony 补丁实现"禁用功能式优化"与玩法微调：基础功能关闭（震动/瘟疫/退化/耐久）、粒子视觉瘦身、权能反应抑制、单位行为改写、城市经济改写、存档兼容修复。纯补丁包（无自有资源、无存档数据），是"声明式配置回调 → 补丁体内实时开关"范式的最完整样板。

## Systems

- Primary: Mod Lifecycle, AI, UI
- Secondary: Actor, City, Culture, Assets, Items, Map, Resources, Save/Persistence, Boats

## Key Implementation

- `Code/Main.cs` (L7-24) — BasicMod<Main> 入口：`Harmony.CreateAndPatchAll(Assembly)` 整程序集一次性上补丁（L13）；harmless_genes 时直接改 gene 资产（L16-22）
- `Code/config.cs` (L14-71) — 42 个配置回调把 default_config.json 的 `Callback` 反射写入静态字段；5 个带副作用级联（暂停纪元推进/重刷侧栏/重刷全文化）
- `Patch/FarmPatch.cs` (L8-193) — 全库最复杂补丁：6 补丁 + 静态缓存 + 篝火圆心分区扫描 + 岗位自动补充
- `Patch/ClaimLandPatch.cs` (L7-90) — 决策注入 + 双目标 Prefix + 远程宣称重写
- `Patch/GuardPowerPatch.cs` (L4-65) — SkipFlags 静态标志协调：外层 Pre/Post 包裹置位、内层方法按标志跳过
- `Patch/WindowArtPatch.cs` (L15-101) — 多窗口 Postfix 布局手术：插图隐藏白名单、标签重排、页头跳过
- `Patch/EraPatch.cs` (L21-93) — 原版纪元按钮右键挂接 NML 配置窗口 + 图标状态机刷新

## Unique Methods

筛选口径：剔除 Harmony 管线样板（补丁方法本体、OnModLoad、config 回调）后，机制含量最高的模组自有方法。纯补丁包中此类方法多内嵌于补丁方法体。

- `FarmPatch.CheckBonfireFarms/CheckRegion/CheckZone` (Patch/FarmPatch.cs:L142-193，GetBonfire L133-140) — 篝火农忙：以城市篝火为圆心扫描本区+邻区 36 格内 `can_be_farm`/`farm_field` 地块，去重后追加进城市 `calculated_place_for_farms/farm_fields/crops`
- `ClaimLandPatch.RemoteClaim` (Patch/ClaimLandPatch.cs:L63-90，CanClaim/IsRemote L49-61) — 远程宣称：按配置等级判定后经 `city_zone_helper.city_growth` 取目标区直接 `city.addZone`，扩张主义文化附带吞并相邻无主区并给予金币
- `HarmlessGenesPatch.CleanBadGenes` (Patch/HarmlessGenesPatch.cs:L19-36) — 遍历亚种细胞核每条染色体，把 id=="bad" 的基因替换为 `getRandomNormalGene()` 随机普通基因
- `CultureTraitPatch.ApplyToAllCultures` (Patch/CultureTraitPatch.cs:L12-18) — 配置切换时对全部现存文化重刷特质增删，使声明式开关即时生效
- `ResourcePatch.OpAddResources` (Patch/ResourcePatch.cs:L27-36) — 资源原地入库：遍历 `city.storages` 直送有空位仓库，跳过搬运动画
- `WindowArtPatch.DisableArt/SetGroupBottom` (Patch/WindowArtPatch.cs:L84-101) — 窗口插图按白名单隐藏与布局分组手术

## Techniques

Harmony Prefix/Postfix（38 文件 / 77 补丁方法 / 82 原版目标）、程序集级 CreateAndPatchAll、JSON 声明式配置 + 反射 Callback、补丁体内实时读 config 的运行时开关、Traverse/AccessTools 私有字段回写（TimeFixPatch.cs:18-20）、重入标志二次执行原版行为（KingdomColonizationPatch.cs:20-30）

## WorldBox Usage

Actor.{die, changeHappiness, setStamina, makeStunned, addForce, registerDecisions, hasTag, hasTelepathicLink} / ai.behaviours 18 个 Beh* 节点 execute / City.{addZone, storages, jobs, calculated_farm_fields} / CityResources.getSlots / MapBox.{calculateCurElapsed, Update, startShake, addLastStep} / WorldTile.startFire / AssetManager.{gene_library, decisions_library, culture_traits, happiness_library} / SaveManager.{loadWorld, convertPermafrost} / SubspeciesManager.newSpecies / GeneLibrary.getRandomGeneForMutation / CultureManager.newCulture / FamilyManager.newFamily / BabyMaker.makeBaby / ScrollWindow.show / ListWindow.Awake / PowerButton.OnPointerClick / AStarFinder.FindPath / Item.getDamaged / ProjectileManager.checkCollision

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / GetConfig()（Verified）
- NeoModLoader.ui.ModConfigureWindow.ShowWindow（Verified，EraPatch.cs:25）
- default_config.json 声明式配置管线：`Callback` 字段反射回调（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| WorldBehaviourTileEffects.tryToStartTileEffects 等 | Prefix skip | Patch/WavePatch.cs:6、SnowSummitPatch.cs:6 | 禁生物群系特效/顶峰积雪 |
| MapBox.startShake / ShortcutExtensions.DOShakePosition | Prefix skip | Patch/ScreenShakePatch.cs:6、NoUIShakePatch.cs:8 | 禁屏幕/UI 抖动 |
| ActionLibrary.tickPlagueInfection | Prefix skip | Patch/DiseasePatch.cs:6 | 禁瘟疫自动传播 |
| WorldBehaviourActions.updateRoadDecay/updateFarmDecay | Prefix skip ×2 | Patch/DecayPatch.cs:7-12 | 禁道路/农田退化 |
| Item.getDamaged | Prefix skip | Patch/EquipmentPatch.cs:6 | 装备不掉耐久 |
| ProjectileManager.checkCollision | Prefix skip | Patch/NoProjectileDeflectPatch.cs:6 | 禁子弹互弹 |
| Building.setState / WorldBehaviourActions.updateRuinRatSpawn | Prefix | Patch/RuinPatch.cs:6-21 | 禁废墟生成与废墟老鼠 |
| ScrollWindow.show 等 5 窗口目标 | Postfix/Prefix | Patch/WindowArtPatch.cs:15-82 | 插图隐藏/标签重排/页头跳过 |
| ActionLibrary.suprisedByArchitector 等 | Prefix skip | Patch/GuardPowerPatch.cs:8-21 | 禁权能反应（惊跑/光标特效/眩晕） |
| Magnet.dropPickedUnits 等 4 目标 | Pre+Post 包裹 | Patch/GuardPowerPatch.cs:23-45 | SkipFlags 抑制窗口置位 |
| Actor.makeStunned/applyRandomForce 等 | Prefix 条件skip | Patch/GuardPowerPatch.cs:47-65 | SkipFlags 时禁眩晕/击退 |
| BehTrySleep.execute | Postfix | Patch/SleepPatch.cs:6-24 | 优质睡眠：每级 −10 秒 +10 饱食 |
| WorldTile.startFire / ActionLibrary.addBurningEffectOnTarget | Prefix 条件skip | Patch/FirePatch.cs:6-18 | 火焰分级控制（地形/建筑/单位） |
| Plot.updateProgress | Prefix | Patch/PlotPatch.cs:6-10 | 谋划进度 ×config.plot_speed |
| Actor.hasTag("strong_mind") / Actor.hasTelepathicLink | Prefix/Postfix | Patch/ControllableUnitPatch.cs:6-10、SocializePatch.cs:7-11 | 附身永不反抗 / 心灵社交 |
| BehTryFindTargetWithStatusNearby.execute | Prefix 条件skip | Patch/SocializePatch.cs:17-31 | 笑/唱/骂等任务原地完成免寻路 |
| EnemiesFinder.findEnemiesFrom | Prefix | Patch/SightPatch.cs:6-18 | 视野减半（国王/士兵豁免） |
| BehFamilyFollowAlpha / BehFindTargetToStealFrom.execute | Prefix skip | Patch/FamilyFollowPatch.cs:7-14、StealPatch.cs:7-14 | 禁兽群跟随/偷窃 |
| BehKingCheckNewCityFoundation.* | Prefix+Postfix | Patch/KingdomColonizationPatch.cs:11-30 | 殖民跳过人口检查→一次两城 |
| Actor.registerDecisions | Postfix | Patch/ClaimLandPatch.cs:7-22 | 向士兵/队长注入 claim_land 决策 |
| BehActorCheckZoneTarget/BehGoToTileTarget.execute | Prefix 双目标 | Patch/ClaimLandPatch.cs:24-47 | 宣称任务改写（等级过滤/远程） |
| CultureManager.newCulture / FamilyManager.newFamily | Postfix | Patch/CultureTraitPatch.cs:6-10、FamilyReproductionPatch.cs:6-16 | 新文化应用特质 / 组建家庭立即生育 |
| Actor.die / Actor.giveAllLootAndMoney | Prefix | Patch/WealthInheritancePatch.cs:6-50 | 死亡遗产均分存活子女（含余数） |
| Actor.changeHappiness / setStamina / changeStamina | Prefix | Patch/HappinessPatch.cs:6-21、StaminaPatch.cs:6-15 | 幸福恒满（重实现）/ 体力钳制与免消耗 |
| BehCityActorFindStorageWheat 等 6 目标 | Prefix/Postfix | Patch/FarmPatch.cs:13-131 | 篝火农忙直送/补录田地/岗位补充 |
| BehCheckHasResources.execute | Prefix 条件skip | Patch/ResourcePatch.cs:7-25 | 资源原地入库 |
| CityBehCheckFarms.behFindTileForFarm | Prefix+Postfix | Patch/FarmPatch.cs:27-62 | 禁退化补录 + 篝火周围追加可耕地 |
| CityResources.getSlots 等 4 目标 | Postfix/Prefix | Patch/PoopPatch.cs:9-24 | 禁粪便时过滤槽位与任务短路 |
| BehCityActorFertilizeCrop.execute | Prefix 替换 | Patch/PoopPatch.cs:26-38 | 施肥改作物立即成熟+金币 |
| SubspeciesManager.newSpecies + GeneLibrary.* | Postfix | Patch/HarmlessGenesPatch.cs:9-49 | 无害基因：去 bad 特质 + 突变替换 |
| ActorEquipmentSlot.takeAwayItem/setItem | Prefix 双目标 | Patch/CursedItemPatch.cs:6-12 | 诅咒装备禁止更换 |
| AStarFinder.FindPath | Prefix | Patch/BoatPatch.cs:7-11 | 船只对角线寻路 |
| MapBox.calculateCurElapsed / Update | Prefix+Postfix | Patch/TimeFixPatch.cs:7-22 | 帧率无关时钟（Traverse 回写私有字段） |
| SaveManager.convertPermafrost / loadWorld | Prefix+Postfix | Patch/OldSnowCompatPatch.cs:9-33 | 旧存档雪块兼容修补 |
| WorldAgeManager.setDefaultAges 等 4 目标 | Postfix/Prefix | Patch/EraPatch.cs:15-50 | 纪元暂停 + 右键配置入口 + 图标状态机 |
| GraphyCaller.click/clickConsole | Prefix skip ×2 | Patch/QuickDebugPatch.cs:6-18 | 性能球点击转 debug/控制台 |

## Reusable Ideas

- `config-toggle-skip-prefix`：补丁首行实时读 config 的运行时开关门，改开关即时生效无需重载（DecayPatch.cs:8）
- SkipFlags 前后缀对：外层方法包裹置位、内层方法按标志跳过的跨补丁抑制窗口（GuardPowerPatch.cs:23-65）
- 声明式配置回调带副作用级联：改开关同步世界状态/重刷 UI/重刷全文化（config.cs:33-66）
- 重入标志二次执行原版行为：跳过人口检查后再跑一次 execute 达成一次两城（KingdomColonizationPatch.cs:20-30）
- 存档兼容双段式：拦截原版转换 + 载入后修补方块（OldSnowCompatPatch.cs:9-33）

## Pattern Candidates

- `config-toggle-skip-prefix`
- `skip-flag-prefix-postfix-pair`
- `decision-injection-postfix`
- `config-callback-runtime-reapply`

## Evidence

- Code/Main.cs:13 — `Harmony.CreateAndPatchAll(typeof(Main).Assembly)`
- Code/Main.cs:16-22 — harmless_genes 资产直改
- Code/config.cs:33-37 — 回调副作用级联（纪元暂停同步）
- Patch/FarmPatch.cs:8 — `MAX_DIST = 36`
- Patch/FarmPatch.cs:142-193 — CheckBonfireFarms/CheckRegion/CheckZone
- Patch/ClaimLandPatch.cs:63-90 — RemoteClaim
- Patch/GuardPowerPatch.cs:4-7 — SkipFlags 标志定义
- Patch/KingdomColonizationPatch.cs:20-30 — Postfix 重入 execute
- Patch/WealthInheritancePatch.cs:20-36 — 遗产余数逐份分配
- Patch/HarmlessGenesPatch.cs:19-36 — CleanBadGenes
- Patch/OldSnowCompatPatch.cs:17-33 — loadWorld 后雪层修补
- Patch/EraPatch.cs:21-29 — 右键打开 ModConfigureWindow

## Notes

无自有资产与存档数据；42 配置项全部走 NML default_config.json 管线。约 24 个微型单行 skip/augment 补丁未在 Patch Targets 逐条列出（按主题归并行）。`模组介绍及使用.txt` 标注 Steam 创意工坊 item 3793866329。
