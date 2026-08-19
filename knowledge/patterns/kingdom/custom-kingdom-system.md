# Pattern: custom-kingdom-system

## Status

Verified

## Goal

为王国（Kingdom）添加可配置的"类型/政体"层：类型资产 + 实例状态 + 行为接管三层结构。

## When to Use

做政体/文化/国策/称号等王国级系统。XNTM 用此结构实现 57 种国家类型。

## Relevant Systems

Kingdom, Diplomacy, Traits, City, Save/Persistence

## Core WorldBox Types

`KingdomTrait` / `AssetManager.kingdoms_traits` / `kingdom.data.custom_data_string` / `KingdomBehCheckKing.execute`（ai.behaviours）/ `SuccessionTool.findNextHeir` / `WorldLogAsset` / `kingdom.data`

## Implementation Flow

1. **定义表**：纯 C# List&lt;Definition&gt; 描述全部类型（id/继承模式/头衔/加成）——内容与逻辑分离，扩展只加行
2. **资产层**：每个定义注册 KingdomTrait 到 `AssetManager.kingdoms_traits`（意见加成等交给引擎）
3. **实例层**：kingdom 的当前类型 ID 存 `kingdom.data.custom_data_string`（键加 mod 前缀）
4. **行为接管**：Prefix `KingdomBehCheckKing.execute` 按政体短路原版王位行为树（`__result = BehResult.Continue; return false`）；继承用 `SuccessionTool.findNextHeir` Prefix
5. 展示：TooltipLibrary/KingdomWindow showStatsRows Postfix 注入头衔行

## Reference Implementations

Primary:
- Mod: ref:xavii-nation-types — File: Code/Utils/NationTypeManager.cs:13,92-150,1262,1705-1747 — Symbol: NationTypeManager
  Why: 三层结构完整实现（57 类型验证规模）

## Caveats

- **Short-circuit 行为树影响全局王位逻辑**：其他 mod 同点 patch 会冲突——检查返回值语义（BehResult）
- custom_data_string 的 WBKB 索引验证未通过（见 unresolved.jsonl），以 mod 运行代码为准并自行回归
- 换代/灭国时清理实例状态（setKing/ removeObject hook）

## Evidence

- ref:xavii-nation-types Code/Utils/NationTypeManager.cs:13,1262,1705-1747
- ref:xavii-nation-types Code/Patches/KingdomBehCheckKingPatch.cs:8-34
- WorldBox: KingdomTrait/AssetManager.kingdoms_traits/KingdomBehCheckKing（WBKB 索引 verified）

## Provenance

Derived from: ref:xavii-nation-types（Single-reference pattern——但实现规模大、结构清晰）
WorldBox evidence: kingdoms_traits 注册面 + ai.behaviours KingdomBehCheckKing.execute（WBKB symbol/refs verified）
