# Pattern: harmony-prefix-recipes

## Status

Strong Verified

## Goal

掌握三种经过验证的 Harmony Prefix 用法——填充放行、否决、全量替换——覆盖绝大多数"修改原版行为"需求。

## When to Use

需要拦截/修改 WorldBox 原版方法行为时，先在此三式中选择，再考虑 Transpiler。

## Relevant Systems

Patching（作用于任意系统）

## Core WorldBox Types

被 patch 的目标方法（示例：Actor.getName / BuildingManager.addBuilding / StatusLibrary.burningEffect）

## Implementation Flow

三式（按侵入性从低到高）：

**Recipe 1 — 填充放行（非破坏式）**：Prefix 只在空值时填充，`return true` 放行原逻辑
**Recipe 2 — 否决（veto）**：Prefix 设 `__result = null/false` 并 `return false` 掐掉原方法
**Recipe 3 — 全量替换（replace）**：Prefix 重写原方法逻辑（复刻必要副作用）后 `return false`
变体：泛型类用 `MakeGenericType + CreateProcessor`（attribute 无法标注开放泛型）；`ref bool __runOriginal = false` 更兼容

## Reference Implementations

Recipe 1:
- Mod: ref:chinesename — File: Code/Patches/ActorNamePatch.cs:15-25 — Symbol: set_actor_name
  Why: 空名时生成中文名写回 data.name，return true 保留原版

Recipe 2:
- Mod: ref:buzzoff — File: Main.cs:14-27 — Why: `__result = null; return false` 否决蜂巢生成（70 行教科书）

Recipe 3:
- Mod: ref:nerffiredamage — File: BurningEffectPatch.cs:14-42 — Why: 重写 burningEffect 并复刻皮肤烧伤/粒子副作用
- Mod: ref:worldresilience — File: WorldResilience.cs:95-276 — Why: 大型算法级替换（updateErosion）

泛型变体:
- Mod: ref:sandbox — File: Patches/MetaObjectWithTraits_Patch.cs:26-40 — Why: MakeGenericType + CreateProcessor

## Minimal Example

```csharp
// Recipe 2: veto
[HarmonyPatch(typeof(BuildingManager), nameof(BuildingManager.addBuilding))]
static bool Prefix(BuildingAsset pAsset, ref Building __result) {
    if (pAsset.id == "beehive") { __result = null; return false; }
    return true;
}
```

## Caveats

- **Recipe 3 必须复刻副作用**（粒子/音效/联动状态），否则行为静默缺失——nerffiredamage 的复刻清单是范本
- **`return false` 与其他 mod 冲突**：能用 Recipe 1 就不用 2/3；`__runOriginal` 变体更友好（optime）
- **多重载方法**：Patch attribute 需指定参数类型数组（shtoolkit 三重载合并样本）
- **替换整方法风险**：游戏更新后原方法变化时 Replace 静默失效于新逻辑

## Evidence

- ref:chinesename Code/Patches/ActorNamePatch.cs:15-25
- ref:buzzoff Main.cs:14-27,30-51（含双目标注解堆叠）
- ref:nerffiredamage BurningEffectPatch.cs:14-42
- ref:sandbox Patches/MetaObjectWithTraits_Patch.cs:26-40
- ref:optime QoL/TimeStopProjectiles.cs:9-13（__runOriginal 变体）

## Provenance

Derived from: ref:chinesename, ref:buzzoff, ref:nerffiredamage, ref:worldresilience, ref:sandbox, ref:optime
WorldBox evidence: 目标方法均在 WBKB 索引（StatusLibrary/BuildingManager/Actor）
