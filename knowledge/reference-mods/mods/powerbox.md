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
| UiUnitAvatar.OnDisable | Prefix | Features/Patches/PreventSettingActorToNullInUiUnitAvatarOnDisablePatch.cs | 防关闭单位头像时置空 actor |

仅 1 个 Harmony patch——该 mod 几乎全走 NML Feature 资产路线。

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
