# Unlock all

## Identity

- Name: Unlock all（NCMS 模 mod）
- Source ID: `ref:unlock-all`
- Dir: `Unlock all`
- Files: 3 total / 1 C#
- Confidence: Verified

## Purpose

一键全解锁：强制开启诅咒世界法则并把诅咒献祭计数设为 500（献祭解锁线）。

## Systems

- Primary: World（法则）, Utility
- Secondary: 无

## Key Implementation

- `Code/Main.cs` (L40-67) — NCMS [ModEntry] + Awake；改 world_law_cursed_world.default_state=true；AccessTools.Method 手工 Harmony Postfix

## Techniques

NCMS ModEntry、直接改 WorldLawAsset.default_state、手工反射式打补丁

## WorldBox Usage

AssetManager.world_laws_library / CursedSacrifice.{reset,_current_sacrifice_count}

## NeoModLoader Usage

无（NCMS: ModEntry/Mod.Info，非 NML 模式）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| CursedSacrifice.reset | Postfix | Code/Main.cs:64-66 | 献祭计数重置为 500 保全解锁 |

## Reusable Ideas

- 修改 world_law 资产 default_state 是改开局面板的最低成本途径

## Pattern Candidates

- `world-law-default-flip`

## Evidence

- Code/Main.cs:30-38,44-45,53,64-66

## Notes

NCMS 遗留；引用 NCMS/ReflectionUtility；大量无用 using。
