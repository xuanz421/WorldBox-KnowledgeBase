# Pattern: nml-feature-authoring

## Status

Verified

## Goal

用 NeoModLoader 的 Feature 体系（自动发现 + 依赖排序）组织 mod 功能，而非手写注册顺序。

## When to Use

新 mod、或多功能 mod 想要零样板注册与模块解耦时。PowerBox 40+ 神力全部走此路线，OnModLoad 为空。

## Relevant Systems

Mod Lifecycle, Assets, UI

## Core WorldBox Types

（数据资产仍落到 AssetManager；Feature 层在 NML 侧）

## Core NeoModLoader APIs

`NeoModLoader.api.features.ModAssetFeature&lt;T&gt;` / `ModButtonFeature&lt;TTab,TFeature&gt;` / `ModPowerTabFeature` / `ModObjectFeature&lt;T&gt;` / `ModWindowButtonFeature` / `ModGodPowerButtonFeature&lt;T,TTab&gt;` / `ModFeatureRequirementList`（依赖声明）——均 WBKB Verified（NeoModLoader.api.features 命名空间）

## Implementation Flow

1. 每个功能一个 Feature 类：资产型继承 `ModAssetFeature<GodPower>` 并在 `InitObject` 内建资产；按钮型继承 `ModGodPowerButtonFeature<T,Tab>`
2. 依赖用 `ModFeatureRequirementList` 声明（如按钮 Require 其 Power 的 Feature）——NML 自动按依赖排序初始化
3. mod 入口 `BasicMod<T>` 可为空 OnModLoad；Update 驱动的逻辑可在 mod 类写 Update 或用 Feature 生命周期
4. 跨 Feature 取对象：`GetFeature<T>().Object`

## Reference Implementations

Primary:
- Mod: ref:powerbox — File: Code/Features/Buttons/CultureCreationButton.cs:5-10 + Code/PowerBox.cs:30-50 — Symbol: CultureCreationButton / PowerBox
  Why: 权威样本：40+ Feature 一比一配对，结构极规整

## Caveats

- **单一样本库**：目前只有 PowerBox 大规模使用（Single-reference-rich pattern）——API 面以 NML 源码为准（WBKB `--source neomodloader` 可查）
- **与手动注册混用**：Feature 初始化时机由 NML 排序，依赖 Harmony 早绑定的逻辑仍放 OnModLoad
- 要求 NML 版本支持 api.features（旧 NML/NCMS mod 不适用）

## Evidence

- ref:powerbox Code/PowerBox.cs:30-50（空 OnModLoad）+ Features/ 全目录结构
- NML evidence: NeoModLoader.api.features 命名空间（WBKB neomodloader 源索引 Verified）

## Provenance

Derived from: ref:powerbox
WorldBox evidence: 无（纯 NML 层）
NML evidence: WBKB `search --source neomodloader ModAssetFeature`
