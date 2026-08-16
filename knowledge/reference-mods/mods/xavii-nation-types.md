# Xavii Nation Types (XNTM)

## Identity

- Name: Xavii Nation Types + Land Types（GUID `com.xavii.xntm`，namespace XNTM.Code）
- Source ID: `ref:xavii-nation-types`
- Dir: `XaviiNationTypes_1.6.1`
- Files: 181 total / 78 C#
- Confidence: Mostly Verified

## Purpose

为王国实现可扩展"国家类型"系统（57 种：王国/帝国/共和国/神权/汗国/商人共和国…），每种类型定义继承模式（血统/选举/宗教/议会/年龄/财富/无领袖）并驱动王位继承、统治头衔本地化、意见加成；另加 Land Types（村/城/州/附庸王国）按人口与宗主国类型给城市加成，BetterWars 重做战争结局（白和/停火/割让/傀儡/朝贡），NationalLaws 国策法系统。

## Systems

- Primary: Kingdom, Diplomacy, Traits, Events
- Secondary: City, Save/Persistence, UI, Culture, Religion, Combat, World, Mod Lifecycle

## Key Implementation

- `Code/XNTM.cs` (L11-308) — 入口：注册 traits/world laws/national laws + world_log_library 注册 20+ WorldLogAsset（L53-65 text_replacer 模板替换范式）
- `Code/Utils/NationTypeManager.cs` (L13-1940) — 核心：`nationals_type_id` 存 kingdom.data.custom_data_string（L13,1262）；57 类型定义表（L92-150）；RegisterTraits 注入 KingdomTrait（L1705-1747）
- `Code/Patches/KingdomBehCheckKingPatch.cs` (L8-34) — Prefix 拦截原版王位检查行为树：无领袖/议会政体短路
- `Code/Utils/LandTypeManager.cs` (L16-100) — 城市地格类型：人口阈值+修正，存 city.data key `xntm_land_type`
- `Code/Patches/CityLandTypePatches.cs` (L7-63) — City 生命周期四点挂钩 + getLoyalty ref 修正
- `Code/Data/NationTypeDefinition.cs` (L18-107) — 纯数据定义 + 本地化读取范式

## Techniques

Harmony Prefix/Postfix（40 patch 文件，Assembly.PatchAll 一次挂载）、Custom asset（KingdomTrait/ActorTrait/WorldLogAsset 含 text_replacer/WorldLawAsset）、Custom data（kingdom.data.custom_data_string / city.data）、UI injection（KingdomWindow/CityWindow/TooltipLibrary showStatsRows postfix）、Localization（stringExists 检查 + Prewarmer 预热）

## WorldBox Usage

AssetManager.{kingdoms_traits, traits, trait_groups, world_laws_library, world_log_library} / KingdomTrait / ActorTrait / WorldLawAsset / WorldLogAsset / kingdom.data.custom_data_string / KingdomBehCheckKing.execute / CityBehCheckArmy.execute / City.{newCity,loadCity,update,updateCityStatus,getLoyalty} / WarManager.{newWar,update,endWar} / AllianceManager.newAlliance / SuccessionTool.findNextHeir / LocalizedTextManager

## NeoModLoader Usage

- BasicMod<T>、ModObjectFeature<HarmonyLib.Harmony>（WBKB Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| KingdomBehCheckKing.execute | Prefix | Patches/KingdomBehCheckKingPatch.cs:8-34 | 按政体短路王位行为树 |
| CityManager.newCity | Postfix | Patches/CityLandTypePatches.cs:7-14 | 新城赋默认地格类型 |
| City.getLoyalty | Postfix(ref __result) | Patches/CityLandTypePatches.cs:47-53 | 地格忠诚修正 |
| WarManager.endWar/newWar/update | Pre/Post | Patches/BetterWarsWarPatches.cs | BetterWars 结局替换 |
| SuccessionTool.findNextHeir | Prefix | Patches/SuccessionToolPatch.cs | 按继承模式选继承人 |
| LocalizedTextManager.getText | Postfix | Patches/LocalizedTextManagerPatch.cs | 本地化键回退 |
| TooltipLibrary.showKingdom 等 | Postfix | Patches/TooltipLibraryPatches.cs | 头衔/国家类型显示 |
| WorldLogMessageExtensions.getFormatedText | Postfix | Patches/WorldLogMessageExtensionsPatch.cs | 战争日志模板替换 |

## Reusable Ideas

- "定义表→KingdomTrait 资产→kingdom.data.custom_data_string 存实例状态"三层结构（NationTypeManager.cs:13,1262,1705）
- WorldLogAsset 用 text_replacer 委托实现带参日志，random_ids=0 关掉原版随机（XNTM.cs:53-65,303-308）
- 用 ai.behaviours 行为树节点的 Prefix 作为政体/城市系统主 tick 入口，避免自建轮询（KingdomBehCheckKingPatch.cs:11-33）
- 纯 C# 定义列表驱动全部系统+本地化，扩展只加一行（NationTypeManager.cs:92-150）
- City 生命周期四点挂钩 + getLoyalty ref 修正（CityLandTypePatches.cs:7-53）

## Pattern Candidates

- `kingdom-trait-custom-data-hybrid`
- `worldlog-asset-text-replacer`
- `behaviour-node-prefix-system-tick`
- `definition-table-driven-content`

## Evidence

- Code/XNTM.cs:11 — `class XNTM : BasicMod<XNTM>`
- Code/Features/Harmony.cs:14 — `harmony.PatchAll(...Assembly)`
- Code/Utils/NationTypeManager.cs:13 — CustomDataKey 定义
- Code/Utils/NationTypeManager.cs:1705 — kingdoms_traits.add
- Code/XNTM.cs:40,53-65 — world_log_library + text_replacer
- Code/Patches/KingdomBehCheckKingPatch.cs:22-23 — `__result = BehResult.Continue; return false;`

## Notes

BetterWarsManager.cs 3906 行、NationTypeManager 1940 行仅读关键段；40 patch 文件中 UI/本地化占约一半。
