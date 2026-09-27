---
title: AW3 内容资产与文化命名
aliases:
  - ancient-warfare-3-content-naming
---

# Ancient Warfare 3 — 内容资产与文化命名（R3-AW3 C4）

父节点：[ancient-warfare-3](../ancient-warfare-3.md)（`ref:ancient-warfare-3`）。本批覆盖 `Code/content/`（76 cs：root 44 + figures 22 + policies 1 + schools 8 + supporters 1）、`Code/content/GodPowerLibrary.cs`（1,292 行）、`Code/core/naming/`（46 文件）与数据目录。计数来自 grep 精确匹配，file:line 均实读；部分 Xia*/naming 正文按簇勘察。

## 资产注册清单

全部走原版 AssetManager 的 add/clone（非 NML feature）：ActorAsset 1（`Xia`←clone human，XiaRace.cs:42）、KingdomAsset 2（nomads_Xia←nomads_human、Xia←nomads_Xia，XiaKingdom.cs:15,25）、GodPower 1 clone + ~15 map-mode/toggle/action power（GodPowerLibrary.cs:111-1103）、ItemAsset 3 件武器（ji/ge/binfa←clone `$sword`，XiaItems.cs:33,38）、StatusAsset 3+、ActorTrait 12+ 与 TraitGroup 2 组（XiaTraits.cs:38,41）、NameSetAsset 1 + NameGeneratorAsset stub、学校系统全套 CitizenJobAsset/ActorJob/BehaviourTaskAsset/WorldLogAsset（HistoricalSchoolContent.cs:159-342）。注册顺序契约：特质组→特质→状态→物品→王国→船→建筑→种族→Service（XiaContent.cs:5-49）。

## 夏 content 关键机制

- 种族 genome 用**差额累加**（addGenome 同名基因是加法，XiaRace.cs:89-105），base_stats 的 lifespan/offspring 归零避免与 genome 重复相加（:114-117）
- **手动补 `check_flip` 委托**：mod 注册晚于 linkAssets，原版默认委托缺失会 NRE（XiaRace.cs:76-82，引用 ActorMovement.cs:91）
- 武器 clone 后**必须手动补 post_init 漏掉的 path_gameplay_sprite**（原版 post_init 不回补新物品→loadSprites null 崩溃，XiaItems.cs:40-46）

## 历代君主卡（figures/，22 文件 6,866 行）

- `HistoricalFigureDef`（HistoricalFigureDef.cs:15-76）：**91 位开国君主**静态表（Count=91 :178），SpawnSequence/SpawnRegistryOrder（降临流程归 C2b/mandate-diplomacy-vassalage.md）
- 卡模型：`HistoricalFigureCardDefinition`（HistoricalFigureCardModels.cs:90）+ 五档稀有度（概率总和校验=1，CardCatalog.cs:431）；Catalog 91 君主→legacy card→EmperorSeeds→346 行 MinisterSeeds→SupporterSeeds 动态生成（CardCatalog.cs:227-275）；fame→rarity 映射 ≥98金/≥90红/≥75粉/≥55紫（:313-320）
- **静态自校验** `Validate`：重复 id、地理前缀国名、亲代引用、生卒年、每 crate ≥40 谋臣/蓝卡下限/文武齐全（:338-434）
- **传记 691 条全文硬编码进 cs**（六朝代 100/89/155/109/137/101，CuratedBiographies.cs:28-33）+ 113 条焦点词条；7 个 crate 按年份区间分桶（Crates.cs:14-66）
- **赞助者进游戏**：supporters.csv（24 行）→ `SupporterRosterData.Parse`（SupporterRosterData.cs:15-60）→ 按贡献聚合 + 2/20红+3/20粉+5/20紫配额生成赞助者卡包（SupporterSeeds.cs:20-45）

## 政策系统（KingdomPolicyDefs.cs，1,114 行）

**63 条 def**（Tech 26 / Social 24 / Decision 13）纯数据 + 静态构造即 Validate（:1076-1079）；def 本身无 effect 挂钩——`KingdomPolicyEffectService.Read(Kingdom)`（core/policy/KingdomPolicyEffectService.cs:31，带 revision 缓存）经 `KingdomPolicyEffectRules` 聚合为 26 字段不可变 `KingdomPolicyEffects` 快照，消费方为 core/policy 90+ 服务（KingdomPolicyService 2,972 行为中枢）。

## 命名引擎（core/naming 46 文件 + patch/naming 10 文件）

- **数据流**：`AWNamingContent.Initialize(modPath)`（ModClass.cs:109）→ `AWNamingResourceLoader`（:143-171）加载 `word_libraries/default` **261 个 txt**（一行一词，items 87/mobs/mottos/CK3 城名等）→ `AWWordLibraryManager.ReplaceAll`；`name_generators/default` 15 JSON（templates[{format,weight}]）→ `AWNameGeneratorLibrary.Initialize`
- `AWNameGeneratorAsset.GenerateIdentity`（AWNameGeneratorAsset.cs:37-60）：确定性加权模板抽样、10 次重试后落 `#NO_NAME#`
- **vanilla stub 模式**：每 mod generator 向 `AssetManager.name_generator.add` 注册**空 stub** 防原版引用缺失（AWNameGeneratorLibrary.cs:65-72）；显示层 `AW_ActorLocalizedNamePatch` Prefix 懒投影 + Postfix 让托管名直通（patch/naming/AW_ActorLocalizedNamePatch.cs:10-34）
- **XiaNaming**：lib 20 txt + Xia 8 JSON 生成器；NameSetAsset `Xia_default_set` 全指向 Xia_*；覆写 clan/alliance parameter_getter（姓氏/氏）；`LM.AddToCurrentLocale("familyname","姓"/"clanname","氏")`（XiaNaming.cs:38-69）
- **localization repair**：`CourtLocalizationRepair.Ensure()` 把 ~40 个 aw_court_* 键中英 fallback 补进当前语言（CourtLocalizationRepair.cs:11-56,108-120）
- 历史州郡法理名录：`XiaHistoricalDeJureCatalog`（States/Commanderies/County 三层，数据源 `name_generators/lib/Xia历史州郡.json`，XiaNaming.cs:22）——与 C3 郡县匹配共用

## GodPowerLibrary（1,292 行）

- spawn_xia clone（:111-125，必须在 AW_LineageTab 之前）；~7 个 map-mode（school/shi-lineage/tech/vassal/mandate×2/feudatory/war/core）统一模式：RegisterMapModeOption 建 PlayerConfig → 已有 power 则 ConfigureMapModePower 复用否则 add（:521-526 等）；点击类 power 12 个（vassal_set/remove、royal_enfeoffment、military_governorate、grant_mandate、bandit_*、de_jure_region create/assign/retire 三态共用注册器 :1075-1103）；静态 runtime 状态集中 `ClearRuntime()`（:88-109）

## Unique Methods（C4 批新增候选）

- `AWNameGeneratorAsset.GenerateIdentity` (Code/core/naming/AWNameGeneratorAsset.cs:37-60) — 确定性加权模板抽样生成姓名，10 次重试 + fallback
- `KingdomPolicyEffectService.Read` (Code/core/policy/KingdomPolicyEffectService.cs:31) — 按 revision 缓存把政策集合聚合为不可变效果快照
- `HistoricalFigureCardCatalog.Validate` (Code/content/figures/HistoricalFigureCardCatalog.cs:338-434) — 卡目录静态自校验（唯一 id/亲代/稀有度配额/生卒年）
- `AWNameGeneratorLibrary.RegisterVanillaStub` (Code/core/naming/AWNameGeneratorLibrary.cs:65-72) — 向原版库注册空 stub 防引用缺失
- `SupporterRosterData.Parse` (Code/content/supporters/SupporterRosterData.cs:42-60) — CSV→赞助者条目（表头嗅探 + # 注释）
- `GodPowerLibrary.RegisterDeJureRegionPower` (Code/content/GodPowerLibrary.cs:1075-1103) — 三态 power 共用一个注册器与复位按钮

## Reusable / Anti-patterns

做法：纯数据 + 静态构造即 Validate（63 政策/691 传记/346 谋臣行，数据错误加载期暴露）；clone 大模板 + 差额覆盖（种族 clone human / 武器 clone $sword，继承陷阱有注释）；容错目录加载逐文件 try/catch 降级（AWNamingResourceLoader.cs:23-77）。

反模式：`\uXXXX` 转义中文与直接中文混用（KingdomPolicyDefs.cs:85 vs :1083）；GodPowerLibrary 单文件 1,292 行 + 十余个 static 缓存字段手工 ClearRuntime；**691 条传记硬编码进 cs**（改文案需重编译，与 word_libraries 已外置 txt 标准不一致）。

## Confidence / Known Gaps

Verified：资产清单与计数、夏种族/物品陷阱、君主卡模型与校验、政策效果聚合、命名数据流、GodPower 注册模式。Mostly Verified：Xia* 其余正文、core/naming 其余 ~40 文件、patch/naming 其余 9 patch、MinisterSeeds 各朝代函数体（仅抽样）。天命/朝代 map-mode（MandateDynastyMapModeService）归天命批（mandate-diplomacy-vassalage.md）。
