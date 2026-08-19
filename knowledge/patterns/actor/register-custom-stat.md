# Pattern: register-custom-stat

## Status

Verified

## Goal

注册自定义单位属性（BaseStatAsset），使属性参与引擎统计管线并在 UI 显示。

## When to Use

原版 base_stats（力量/速度等）不够用，需要经验/护盾/灵力等新数值维度时。

## Relevant Systems

Actor, Traits, UI

## Core WorldBox Types

`BaseStatAsset` / `AssetManager.base_stats_library` / `BaseStats` / `BaseStats.normalize`

## Implementation Flow

1. `new BaseStatAsset { id = "mymod.shield", ... }` → `AssetManager.base_stats_library.add(...)`
2. trait/物品的 `base_stats = new BaseStats{ ["mymod.shield"] = 5f }` 即可消费该属性
3. 读值走 actor.curStats（引擎统计后）；写值走 actor.data 再由 updateStats 注入（见 caveats）
4. UI 显示：克隆 StatsIcon 行（见 ui-button-injection 属性行变体）

## Reference Implementations

Primary:
- Mod: ref:thefantasyworld — File: code/stats.cs:9-15 — Symbol: stats.Init — Why: 15+ BaseStatAsset 手工注册模板
Alternatives:
- ref:incensefiredway — code/stats.cs:45-61 — Why: 同法 + actor.data 双写
- ref:xuanmen-daojie — code/Systems/Cultivation/RealmSystem.cs:843 — Why: updateStats Transpiler 深度集成变体

## Caveats

- **读路径必须等 updateStats 归一化**：直接写 curStats 会被下次 update 覆盖——正确做法是 data 存真值 + updateStats hook 注入（xuanmen Transpiler 或 Prefix 叠加，guigu Pre+Post+Transpiler 三件套）
- 属性 id 同样全局共享，加 mod 前缀
- UI 图标需要 icon 资产配合

## Evidence

- ref:thefantasyworld code/stats.cs:9-15 / ref:incensefiredway code/stats.cs:45-61
- ref:guigu-cultivation Code/Patches/HarmonyPatches.cs:26-93（updateStats 三件套）
- WorldBox: BaseStatAsset（WBKB 索引 verified，BaseStatAsset.cs:4）

## Provenance

Derived from: ref:thefantasyworld, ref:incensefiredway, ref:guigu-cultivation, ref:xuanmen-daojie
