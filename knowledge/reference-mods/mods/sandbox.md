---
title: Sandbox
aliases:
  - sandbox
---

# Sandbox

## Identity

- Name: Sandbox v1.0.8（kenoli & ApexLite）
- Source ID: `ref:sandbox`
- Dir: `Sandbox_1.0.8`
- Files: 51 total / 27 C#
- Confidence: Verified

## Purpose

上帝视角沙盒操控：强制单位归属（城市/文化/语言/宗教/Plot）、封王/立领袖、定居新城（量子精灵画线）、建筑自由放置、磁铁增强、基因强制编辑、四类特质禁用器。

## Systems

- Primary: Actor, City, Kingdom, UI
- Secondary: Traits（禁用）, World(GodPower), Assets, Buildings, Mod Lifecycle

## Key Implementation

- `Main.cs` (L7-26) — 入口：`Config.preload_windows = true` 后 10 个 Feature.Init()
- `Patches/MetaObjectWithTraits_Patch.cs` (L26-40,45-87) — 泛型类运行时 MakeGenericType patch + 按 trait 类型分支禁用
- `Features/MakeUnitKing.cs` (L4-18,44-45) — powers.clone + DropAsset 完整模板；kingdom.removeKing/setKing
- `Features/SettleCity.cs` (L7-33) — new GodPower + QuantumSpriteAsset 画线定居
- `UI/SandboxTab.cs` (L30-60) — TabManager.CreateTab + 分组布局 + AddPowerButton
- `Toolkit/Graphics/ButtonBuilder.cs` — 纯代码构建 PowerButton（四样式）

## Unique Methods

筛选口径：剔除补丁接线与注册样板后，承载核心机制且原版无对应物的模组自有方法。

- `MagnetPlus.MagnetAction` (Features/MagnetPlus.cs:71-122) — 复刻并扩展原版磁铁三态状态机（拾取/拖动/抛掷），窗口激活时强制放下已抓单位
- `MagnetPlus.PickupUnits` (Features/MagnetPlus.cs:124-161) — 按笔刷像素逐格抓取单位，尊重 `can_be_moved_by_powers` 与 PlayerConfig 的每单位磁铁开关
- `MagnetPlus.drawMagnetUnits` (Features/MagnetPlus.cs:14-32) — Postfix 将磁吸量子精灵重绘为单位自身贴图并按磁铁移动角旋转
- `SettleCity.ClickSettleCity` (Features/SettleCity.cs:36-81) — 两段式点击（先选王国、再点空地）用 `createNewUnit`+`buildNewCity` 为任意王国异地定居新城
- `SettleCity.DrawSettleLine` (Features/SettleCity.cs:83-105) — QuantumSprite draw_call 从王国首都向鼠标位置画彩色箭头预览
- `MetaObjectWithTraits_Patch.AddTraits_Prefix` (Patches/MetaObjectWithTraits_Patch.cs:45-87) — 按特质类型+窗口白名单否决 addTrait 并过滤 default_traits 列表（配套 FillTraitAssetsFromStringList_Prefix:89-116）
- `BuildingConstructor.UpdateAssets` (Features/BuildingConstructor.cs:11-33) — 遍历全部 BuildingAsset 批量克隆 power+drop 生成"放置任意建筑"神力（配套 SpawnBuilding:35-48）
- `MakeUnitKing.MakeKing` (Features/MakeUnitKing.cs:21-46) — 落地区域挑选单位（收藏优先）`removeKing`+`setKing` 强制封王

## Techniques

AssetManager.powers.clone 模板克隆 + DropAsset action_landed、泛型方法运行时 MakeGenericType manual patch（MetaObjectWithTraits<,>）、ScrollWindow prefab 克隆 UI、Builder 模式 UI 构建、GodPower select_button_action/click_special_action 组合、QuantumSpriteAsset 自定义绘制

## WorldBox Usage

AssetManager.{powers.clone,add,drops,quantum_sprites} / GodPower（click_power_brush_action/select_button_action/click_special_action/force_map_mode） / kingdom.{setKing,removeKing} / Finder.getUnitsFromChunk / MetaObjectWithTraits.{addTrait,fillTraitAssetsFromStringList} / WindowPreloader.getWindowPrefab / ScrollWindow / StatsIcon

## NeoModLoader Usage

- BasicMod.OnModLoad / Config.preload_windows / TabManager.CreateTab / SpriteTextureLoader.getSprite（Verified）
- PowersTab._children/SetLayout（Unverified——隐式契约）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| MetaObjectWithTraits<,>.addTrait | Prefix | MetaObjectWithTraits_Patch.cs:37 | 特质禁用过滤 |
| MetaObjectWithTraits<,>.fillTraitAssetsFromStringList | Prefix(改 pList) | MetaObjectWithTraits_Patch.cs:38-40 | 默认特质加载过滤（`pList == __instance.default_traits` 引用比较） |
| StatsIcon.Awake | Postfix | ForcedGeneEdit.cs:26-34 | 基因编辑器行加点击 |

## Reusable Ideas

- 泛型类 patch 配方：`typeof(X<,>).MakeGenericType(...)` + `harmony.CreateProcessor(method).AddPrefix(...).Patch()`——attribute 无法标注开放泛型（L26-40）
- `powers.clone(id, "$template_drops$")` + 自建 DropAsset = "点击落地触发"神力最短路径（MakeUnitKing.cs L4-18）
- Prefix 中 `pList = pList.Where(filter).ToList()` 重赋值参数实现列表过滤而非跳过原方法（L89-95）
- `Config.preload_windows = true` + WindowPreloader.getWindowPrefab 克隆 vanilla 窗口（ForcedGeneEdit.cs:14-19）

## Pattern Candidates

- `generic-type-manual-harmony-patch`
- `powers-clone-drop-power-template`
- `button-builder-fluent-ui`

## Evidence

- Main.cs:6-26 / MetaObjectWithTraits_Patch.cs:25-40,45-54,89-95
- MakeUnitKing.cs:4-18,44-45 / SettleCity.cs:7-28
- SandboxTab.cs:30-42 / ForcedGeneEdit.cs:14-19,26-34
