# NerfFireDamage

## Identity

- Name: NerfFireDamage v1.0.0
- Source ID: `ref:nerffiredamage`
- Dir: `NerfFireDamage_1.0.0`
- Files: 7 total / 2 C#
- Confidence: Verified

## Purpose

大幅削弱燃烧伤害：每 tick 烧血从原版最大生命 10% 降到 1%，废墟建筑再乘 0.05。教科书级"Prefix 完全替换原版状态效果"微型补丁。

## Systems

- Primary: Combat
- Secondary: Utility

## Key Implementation

- `BurningEffectPatch.cs` (L14-42) — Prefix 重写 burningEffect 全逻辑并 return false 跳过原方法，复刻皮肤烧伤/火焰粒子

## Techniques

BasicMod.OnModLoad + 手动 new Harmony(id).PatchAll()

## WorldBox Usage

StatusLibrary.burningEffect / BaseSimObject.{getMaxHealthPercent,getHit,isActor,isBuilding} / Actor.addInjuryTrait / MapBox.isRenderGameplay / particles_fire.spawn / Randy

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / LogInfo（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| StatusLibrary.burningEffect | Prefix | BurningEffectPatch.cs:6 | 削弱烧伤害 |

## Reusable Ideas

- 用常量标注"原版值 vs 修改值"的 Prefix 全量替换模板（BurningEffectPatch.cs:9-33）

## Pattern Candidates

- `status-effect-replace-prefix`

## Evidence

- NerfFireDamageMod.cs:10-12 / BurningEffectPatch.cs:9-11,14,27-33
