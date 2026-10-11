---
title: 文明特质拓展
aliases:
  - CivilizationTraitExpansion
  - Civilization Trait Expansion
---

# 文明特质拓展

## Identity

- Name: 文明特质拓展 v1.5.0（`mod.json:2-8`）
- Author: 言西早雨，信仰芙芙&博士
- GUID: `CIVILIZATION_TRAIT_EXPANSION`
- Source ID: `ref:civilization-trait-expansion`
- Source: 用户提供的 `文明特质拓展 (3).zip`，包内 `CivilizationTraitExpansion/`，2026-10-11 静态核查
- Local evidence root: `data/raw/reference-mods/civilization-trait-expansion/`（git-ignored；原始文件字节保持不变；不是游戏安装目录）
- Files: 模组目录 18 total / 5 C# / 3,879 C# lines / 11 PNG；无 `.csproj`、编译产物或自动化测试
- Confidence: Mostly Verified — 5 个 C# 文件的主要实现已阅读，关键边界经 WorldBox/NML snapshot 核对；未编译、启动游戏或验证 mod 组合

## Purpose

扩展 Culture / Kingdom / Actor 三层 trait：城市建筑与经济加成、累计小麦解锁国家传统、帝国管理与继承人教育，以及将非首都 City 切分并分封给国王子嗣。使用原生 trait editor 与 WorldLog 展示，没有独立窗口或自建 tab。

## Systems

- Primary: Culture, Kingdom, City, Buildings, Resources, Traits, Save/Persistence
- Secondary: Actor, Items, World, UI, Assets, Events, Localization, Mod Lifecycle, Utility
- Related pattern IDs: `safe-asset-registration`, `culture-consumption-gates`, `actor-annual-persistent-stat-growth`, `persistent-mod-data`, `world-tick-integration`
- Related system paths: `knowledge/systems/civilization/culture.md`, `knowledge/systems/political/kingdom.md`, `knowledge/systems/settlement/city.md`

## Key Implementation

`ModClass.OnModLoad`：建立默认关闭的 `logging/show_debug_logs` config → 注册 locales 和 trait assets → 注册分封日志 → `new Harmony(GUID).PatchAll()`。只有 config 初始化单独隔离异常；其余 service 自行 catch；没有逐 patch 类安装失败隔离或卸载处理。证据：`Code/CivilizationTraitExpansionMod.cs:40-81`。

| File | 职责 |
| --- | --- |
| `Code/CivilizationTraitExpansionMod.cs:37-84` | `BasicMod<ModClass>` 入口与初始化顺序 |
| `Code/CivilizationTraitExpansionPatches.cs:12-501` | 13 个 Harmony target，原版调用点与 service 接线 |
| `Code/CivilizationTraitExpansionService.cs:423-2227` | trait 注册、城市经济、国家解锁、身份任期与属性重放 |
| `Code/FeudalPartitionService.cs:145-1002` | 文化年龄解锁、分封条件、地块/人口/资源划转、日志 |
| `Code/CivilTraitExpLog.cs:18-61` | config 控制 Debug.Log；Warn/Error 始终输出 |

## Topics

- [城市建筑与经济](civilization-trait-expansion/city-economy.md) — trait 定义、默认授予、多风车、住房、哨塔成本、锻造复制、小麦/渔获入库
- [帝国管理与继承人教育](civilization-trait-expansion/imperial-administration.md) — 120/500 年解锁、身份计时、三档倍率、教育 trait、存档键和清理缺口
- [裂土封侯](civilization-trait-expansion/feudal-partition.md) — 月度条件、真实亲子查询、TileZone 切割与资源搬迁顺序

## Unique Methods

以下保留机制级入口；详细算法与风险由对应子主题承载。

- `CivilizationTraitExpansionService.RunFarmCheck / ScanZone` — 多风车共同重建四组田地集合（`Code/CivilizationTraitExpansionService.cs:981-1060`）。
- `CivilizationTraitExpansionService.OnBlacksmithCraftSuccess / CreateItemCopy` — 复制成品并按价值追加 gold（`Code/CivilizationTraitExpansionService.cs:1153-1246`）。
- `CivilizationTraitExpansionService.AddKingdomWheatProduction / TryUnlockKingdomEfficientFarming` — per-Kingdom 累计投入量与动态解锁门槛（`Code/CivilizationTraitExpansionService.cs:735-870`）。
- `CivilizationTraitExpansionService.GetAdminStage / ApplyImperialAdministrationStats` — 多身份分别计时取最高档，重算后逐层向上取整（`Code/CivilizationTraitExpansionService.cs:1653-1706,1818-1920`）。
- `CivilizationTraitExpansionService.TickImperialAdministration / EnsureHeirEducationTrait` — 解锁来源、继承人变化与两级教育授予（`Code/CivilizationTraitExpansionService.cs:1750-1811,1925-2092`）。
- `FeudalPartitionService.GetEligibleChildren / SelectCutZones / ExecutePartition` — 全世界亲子筛选、按坐标取边缘地块、建城并分封（`Code/FeudalPartitionService.cs:555-596,675-830`）。
- `FeudalPartitionService.TransferResources` — 按源 Building 槽位余额差额计算实际取走量（`Code/FeudalPartitionService.cs:922-960`）。

## Techniques

Harmony Prefix/Postfix（无 Transpiler）、原版 trait asset 注册、typed custom data、原版 WorldAgeManager 节拍、WorldLogAsset/text_replacer、NML config 和 LM locales。图标由包内 `GameResources/ui/Icons/` 提供；未单独验证运行时资源加载效果。

## WorldBox Usage

`Culture.createCulture/addTrait`、`City.getLimitOfBuildingsType/getBuildingOfType/updateCityStatus/setLeader`、`CityBehCheckFarms.check`、`ai.behaviours.CityBehBuild.tryToBuild`、`Building.addResources/takeResource`、`ItemCrafting.craftItem`、`Actor.updateStats/isStatsDirty/isChildOf`、`Kingdom.setKing`、`SuccessionTool.findNextHeir`、`WorldAgeManager.update`、`CityManager.newCity/updateDirtyBuildings`、`City.addZone/addResourcesToRandomStockpile`。

## NeoModLoader Usage

- `BasicMod<T>` / `GetConfig`：Verified API，NML snapshot `neomodloader-02266fe8185d` 的 `NeoModLoader/NeoModLoader.api/BasicMod.cs:8,42`；模组入口 `Code/CivilizationTraitExpansionMod.cs:37,46-49`。
- `ModConfig.CreateGroup/AddConfigItem`：Verified API，NML `NeoModLoader/NeoModLoader.api/ModConfig.cs:235,248`；模组使用 `ConfigItemType.SWITCH`，config 实际显示未实机验证。
- `LM.Add / LM.AddToCurrentLocale`：Verified API，NML `NeoModLoader/NeoModLoader.General/LM.cs`；使用位置 `Code/CivilizationTraitExpansionService.cs:398-416`，按当前语言分流，语言包含 `cz/ch/en`。无 `IReloadable`。

## Patch Targets

证据列均相对于 `Code/CivilizationTraitExpansionPatches.cs`。

| Target | Type | Line | Purpose |
| --- | --- | --- | --- |
| `City.getLimitOfBuildingsType` | Postfix | 12 | 风车增量、哨塔与矿洞上限覆写 |
| `Culture.createCulture` | Postfix | 59 | 新文化默认 trait |
| `City.getBuildingOfType` | Prefix | 72 | 多风车选择替换 |
| `CityBehCheckFarms.check` | Prefix | 112 | 多中心田地计算 |
| `CityManager.updateDirtyBuildings` | Prefix | 152 | 全局建筑列表重建，跳过 null / null asset |
| `City.updateCityStatus` | Postfix | 197 | housing 补量与人口解锁哨塔 |
| `ai.behaviours.CityBehBuild.tryToBuild` | Prefix + Postfix | 243 | 放大成本预检与成功后补扣 |
| `ItemCrafting.craftItem` | Postfix | 331 | 成功锻造后复制与 gold 奖励 |
| `Building.addResources` | Prefix | 355 | 资源倍率与小麦原量累计 |
| `Kingdom.setKing` | Postfix | 394 | 国王任期与继承人计时延续 |
| `City.setLeader` | Postfix | 407 | 新村长任期 |
| `Actor.updateStats` | Prefix + Postfix | 425 | dirty 守卫后的管理倍率 |
| `WorldAgeManager.update` | Postfix | 469 | 管理、分封、农业三个独立异常边界 |

## Reusable Ideas

- 在消费点检查效果真正归属的 Culture / Kingdom，而非只给 trait asset 设置 value；建筑数量、农田、住房与入库是不同消费路径。
- typed custom data 存事实状态，stats 由原版重建后重放；入口 dirty 状态防止早退时重复相加/相乘。已补充到 `actor-annual-persistent-stat-growth`，无需新建重复模块。
- 国家解锁应持久化 unlock source，便于区分持续前置与一次性资格；年龄达到另一通道是否晋级是单独的设计决定。
- 亲子关系使用 parent ID，不能把默认当前 Family 枚举等同于全部子嗣。
- 分封与入库计量目前有交互缺口，作为 candidate 留存，不作为可直接复制的成熟模块。

## Pattern Candidates

- `culture-trait-city-consumption` — 已有 `culture-consumption-gates` 的补充证据
- `dirty-gated-stat-replay` — 已有 `actor-annual-persistent-stat-growth` 的补充证据
- `kingdom-resource-progression` — 延后：计量入口不能区分生产与搬运
- `city-zone-partition` — 延后：库存列表刷新、守恒与失败回滚待验证

## Evidence

包 SHA256：`0b0ea61fa38df9cc1ad454f4a1180dd966e72fbfd6afd3243a149d41d4636368`。

| File | SHA256 |
| --- | --- |
| `Code/CivilizationTraitExpansionMod.cs` | `039bd1ed590676d22ec36742b3500d22c88e9fef8936490171add12cf72348f9` |
| `Code/CivilizationTraitExpansionPatches.cs` | `c3cea81d480fb937fff783d1bb89ff83ff9de62bf36fda2fd14372b238e21b0c` |
| `Code/CivilizationTraitExpansionService.cs` | `bcd393d3f6f28532bc93b9142eafa0a7ac39b40a91f0f622780b089f934e3a8d` |
| `Code/CivilTraitExpLog.cs` | `88d5f79a70d40490e753a9506e4cc2516b38460e50b3066973086e48779dba18` |
| `Code/FeudalPartitionService.cs` | `554e941a9b818747cae067cf5888e74e35fbf58565198565fae492d8c3c3215e` |

WorldBox 边界核对使用保留 snapshot `worldbox-0.51.2-51d275f0168b`（assembly SHA256 与本地 registry 相同）：`Randy.cs:81-83`、`Actor.cs:1747-1753,2844-2856,2894-2910`、`City.cs:360-370,1955-1971,2883-2891`、`CityManager.cs:12-32,119-139`、`Building.cs:1517-1529`、`ItemCrafting.cs:81-102`。现有 registry 的 `game_version=null` 导致 `index status` 为 STALE、`index all` 找不到按该身份计算的 snapshot；本次未改写游戏版本或重建外部源码。

本地来源通过 `config/wbkb.local.json` 的 `reference_mods_roots` 和 local registry 登记；可移植 registry 不保存绝对路径。当前 CLI `index all` 只组装 WorldBox/NML specs，不自动建立 Reference Mod C# index；知识查询入口是本 profile、catalog 与 markdown vector corpus。vector build 没有在本次运行。

## Notes

README / mod.json / 注释含历史规则，不能作为当前行为的唯一依据。文档差异、代码确定性错误、静态风险与实机待验证项分别记录在子主题中。尤其不能把包内“已实机复现”的自述当成本次验收。

来源文件只作为资料，未执行安装说明、未安装模组或修改游戏/其他 reference mod。可由原 zip 恢复上述 evidence root，再使用既有 discovery；C# hashes 用于核对证据版本。
