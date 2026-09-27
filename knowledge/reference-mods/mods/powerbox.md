---
title: PowerBox
aliases:
  - powerbox
---

# PowerBox

## Identity

- Name: PowerBox v1.5.1（Harmony id `key.worldbox.powerbox`）
- Source ID: `ref:powerbox`
- Dir: `PowerBox_1.5.1new`
- Files: 179 total / 104 C#
- Confidence: Verified

## Purpose

通过 NML Feature 体系添加 "PowerBox" 神力标签页，内含 40+ 新神力：建筑升降级、划界扩缩、指定国王/领袖/首都、创建文化/语言/宗教/子种/氏族/联盟/殖民地（含复制现有）、生成特殊生物与船只、资源编辑窗口、全生物查找窗口等。NML Feature 体系的教学样本。

## Systems

- Primary: Assets, UI, Mod Lifecycle
- Secondary: Kingdom, City, Culture, Religion, Actor, Diplomacy, Utility

## Key Implementation

- `Code/PowerBox.cs` (L30-50) — 入口：OnModLoad 为空（全部由 NML Feature 自动发现注册），Update 驱动 Scheduler
- `Code/Features/Buttons/PowerboxTab.cs` (L17-90) — 自建神力 tab + Spawns/Metas 分区切换 + 三层 ButtonFeature 抽象基类
- `Code/Features/GodPowers/BuildingUpgradePower.cs` (L4-45) — GodPower+DropAsset 注册范式：AssetManager.drops.add + click_power_action 绑定
- `Code/Features/Actors/Mastef.cs` (L6-29) — actor_library.clone 派生新生物 + loadTexturesAndSprites
- `Code/Features/Windows/WindowBase.cs` (L6-73) — ScrollWindow ModObjectFeature 基类（网格布局+高亮器）
- `Code/Scheduling/Scheduler.cs` (L5-29) — 时间片轮转任务调度器

## Unique Methods

筛选口径：剔除 Feature 注册样板与 NML 生命周期后，承载核心机制且原版无对应物的模组自有方法。

- `Scheduler.Run` (Code/Scheduling/Scheduler.cs:13-27) — 时间片调度核心：每帧按各任务 `MaxBlockingTime` 毫秒预算连续取步执行，超时让出下帧，任务取尽自动移除
- `PowerboxTab.SwitchSection` (Code/Features/Buttons/PowerboxTab.cs:50-63) — Spawns/Metas 二级分区切换：全 tab 按钮按注册分区批量 SetActive
- `PowerboxTab.PositionButton` (Code/Features/Buttons/PowerboxTab.cs:29-42) — 覆写 NML 按钮定位钩子，把按钮归入分区字典并默认隐藏（仅 All 区可见）
- `BuildingUpgradePower.BuildingUpgradeAction` (Code/Features/GodPowers/BuildingUpgradePower.cs:34-44) — DropAsset 落地回调：按 `upgrade_to` 模板升级建筑并回满血/重算 stats
- `CityBorderExpansionPower.CityBorderExpansionAction` (Code/Features/GodPowers/CityBorderExpansionPower.cs:20-27) — 两段式划界：点到城市记住目标，点到野外把该 zone 并入目标城
- `EditResourcesWindow.CheckInput` (Code/Features/Windows/EditResourcesWindow.cs:108-120) — 城市资源编辑：输入值 clamp 0-999 写入首仓库、清零其余仓库并回写合计
- `WhisperOfAllianceLine.DrawWhisperOfAllianceLine` (Code/Features/QuantumSpriteAssets/WhisperOfAllianceLine.cs:21-34) — QuantumSprite 每帧从选定王国各城向鼠标画联盟连线预览

## Techniques

NML Feature registration（ModAssetFeature/ModButtonFeature/ModPowerTabFeature/ModObjectFeature/ModWindowButtonFeature + ModFeatureRequirementList 依赖声明）、Asset registration（GodPower+DropAsset、ActorAsset.clone、NameGeneratorAsset）、UI injection（TabManager.CreateTab + 分区按钮）、自定义帧调度器、Reflection/ResourcesFinder、EmbeddedResources sprite 加载

## WorldBox Usage

AssetManager.{drops, powers, actor_library, buildings} / GodPower / DropAsset / WorldTile.building / Building.setTemplate,updateStats / Kingdom.setKing / Actor.setProfession / Finder.getUnitsFromChunk / TabManager.CreateTab / PowerButtonCreator.CreateSimpleButton / PowersTab.AddPowerButton

## NeoModLoader Usage

- NeoModLoader.api.features.{ModAssetFeature, ModButtonFeature, ModPowerTabFeature, ModObjectFeature, ModWindowButtonFeature, ModGodPowerButtonFeature, ModFeatureRequirementList}（WBKB Verified）
- BasicMod<T>、NeoModLoader.General.UI.Tab、ResourcesFinder（Unverified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| UiUnitAvatarElement.OnDisable | Transpiler（feature Init 动态 Patch） | Features/Patches/PreventSettingActorToNullInUiUnitAvatarOnDisablePatch.cs:10-13 | IL 把 Ldnull 换成加载自身 `_actor` 字段，防关闭单位头像时置空 actor |
| StatsWindow.create | Postfix（一次性钩子） | Features/Windows/EditResourcesWindow.cs:20-23 | 注入资源编辑按钮，首次命中后自 Unpatch |

共 2 个动态补丁点、0 个 attribute 补丁类——该 mod 几乎全走 NML Feature 资产路线。

## Reusable Ideas

- 每个神力 = 一个 ModAssetFeature<GodPower> 类（InitObject 内建资产），按钮 = ModGodPowerButtonFeature<T,Tab>，NML 自动发现 + 按 ModFeatureRequirementList 依赖排序（CultureCreationButton.cs:5-10、Mastef.cs:7）
- DropAsset+GodPower 配对注册并复用原版 drop 落点管线（BuildingUpgradePower.cs:27-28）
- 自建 tab 内做二级分区（Spawns/Metas）切换 SetActive，而非塞爆一个 tab（PowerboxTab.cs:50-63）
- actor_library.clone(id, sourceId) 最小成本造派生生物（Mastef.cs:10）
- Update() 内置时间片 Scheduler 处理长任务（PowerBox.cs:41、Scheduler.cs:13-27）

## Pattern Candidates

- `nml-feature-per-power`
- `godpower-dropasset-pair`
- `custom-power-tab-sections`
- `clone-derive-actor-asset`

## Evidence

- Code/PowerBox.cs:30 — `class PowerBox : BasicMod<PowerBox>`，L43 OnModLoad 为空
- Code/Features/Buttons/PowerboxTab.cs:23 — `TabManager.CreateTab("PowerBox", ...)`
- Code/Features/GodPowers/BuildingUpgradePower.cs:16 — `AssetManager.drops.add(upgradeBuildingDrop)`
- Code/Features/Actors/Mastef.cs:10 — `AssetManager.actor_library.clone(...)`
- Code/Features/Buttons/CultureCreationButton.cs:5 — Feature 继承范式
