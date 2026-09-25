---
title: actor-annual-persistent-stat-growth
aliases:
  - Actor 年度永久属性成长
---

# Pattern: actor-annual-persistent-stat-growth

## Status

Verified

## Goal

让符合条件的 `Actor` 每年只判定一次，成功后永久累积某项属性；累计值随原版角色数据保存，并在 `Actor.updateStats()` 重建后恰好重放一次。

## When to Use

适合训练、衰老、修炼、职业成长等“低频判定 + per-actor 永久累计 + 派生属性可重算”的机制。若效果只是临时 buff，应改用 trait/status；若状态属于整个世界或 Kingdom，不应塞进 `ActorData`。

## Relevant Systems

Actor, Actor Data, Save/Persistence, Patching, Stats

## Core WorldBox Types

`Actor.updateAge` / `Actor.updateStats` / `Actor.data.get/set` / `Actor.stats` / `Actor.setStatsDirty` / `Date.getCurrentYear` / `Randy.randomChance`

## Core NeoModLoader APIs

Harmony `Prefix` / `Postfix` / `__state`

## Implementation Flow

1. 用带 mod id 的两个 `ActorData` 键分别保存“累计增益”和“上次判定年份”。
2. 在 `Actor.updateAge` Postfix 中先检查角色有效性与资格，再比较当前年份；相同年份直接返回。
3. **在随机判定之前写入年份**，这样失败结果也算本年已判定，重复调用不会无限重掷。
4. 成功时累计永久值并调用 `setStatsDirty()`；不要把修改后的最终 `stats` 当权威存档。
5. 在 `Actor.updateStats` Prefix 用 `__state` 记录入口时是否 dirty；Postfix 只在这次确实发生重建时，从 `ActorData` 读取累计值并加到目标 stat。
6. 测试同年重复调用、跨年成功/失败、连续 `updateStats`、序列化恢复、资格取得/失去和角色归属变化。

## Reference Implementations

Primary building blocks:
- Mod: ref:incensefiredway — File: code/patch.cs:34-52 — Why: 已验证的 `Actor.updateAge` Postfix 年龄事件入口
- Mod: ref:guigu-cultivation — File: Code/Patches/HarmonyPatches.cs:24-90 — Why: `ActorData` 临时状态与 `Actor.updateStats` Pre/Post 重建链组合
- Mod: ref:biology — File: Code/UnitHealthTab.cs:125-136 — Why: 明确证明持续属性修正必须在原版 `updateStats` 重建后重放

Supporting pattern IDs: `actor-data-custom-state`, `world-tick-integration`。

## Minimal Example

```csharp
private const string BonusKey = "mymod.training_health_bonus";
private const string YearKey = "mymod.training_health_year";

[HarmonyPatch(typeof(Actor), "updateAge")]
internal static class AnnualGrowthPatch
{
    private static void Postfix(Actor __instance)
    {
        if (__instance?.data == null || !__instance.isAlive() || !IsEligible(__instance)) return;

        int year = Date.getCurrentYear();
        __instance.data.get(YearKey, out int recordedYear, int.MinValue);
        if (recordedYear == year) return;
        __instance.data.set(YearKey, year);

        if (!Randy.randomChance(0.05f)) return;
        __instance.data.get(BonusKey, out float bonus, 0f);
        __instance.data.set(BonusKey, bonus + 2f);
        __instance.setStatsDirty();
    }

    private static bool IsEligible(Actor actor)
    {
        // Query the owning system's authoritative state here.
        return true;
    }
}

[HarmonyPatch(typeof(Actor), "updateStats")]
internal static class PersistentStatReplayPatch
{
    private static void Prefix(Actor __instance, out bool __state)
    {
        __state = __instance != null && __instance.isStatsDirty();
    }

    private static void Postfix(Actor __instance, bool __state)
    {
        if (!__state || __instance?.data == null || !__instance.isAlive()) return;
        __instance.data.get(BonusKey, out float bonus, 0f);
        if (bonus > 0f) __instance.stats["health"] += bonus;
    }
}
```

## Caveats

- `Actor.updateAge` 本身是低频入口；不要另开每帧全单位扫描来模拟年度事件。
- 年份必须在 roll 前记录，否则失败者可因重复调用在同一年反复重掷。
- `updateStats` 会从基础来源重建 stats；只在事件发生时直接改 `actor.stats` 会在下一次重建后丢失。
- Postfix 没有 dirty 守卫时，原方法早退也可能导致同一累计值被再次相加；Prefix `__state` 用于区分真正的重建。
- 永久增益是否在角色改宗、转职或失去资格后保留，必须由玩法规则明确；通常资格只控制未来判定，既得 per-actor 成长保留。
- 长期线性增长应评估概率、增量和可选硬上限；上限作用于持久累计值，不要只 clamp 显示结果。
- 自定义键在所有 mod 间共享，必须带命名空间前缀，并保持值类型稳定。

## Evidence

- WorldBox `Actor.cs:1237-1278` — `updateAge()` 年度入口及原版 30% 属性成长；原版候选不包含任意自定义永久 stat
- WorldBox `Actor.cs:1747-1750` — `updateStats()` 以 dirty 状态早退
- WorldBox `Actor.cs:1810-1820` — stats 重建合并 Culture 后再叠加角色外交、管理、智力、军事数据
- WorldBox `BaseSystemData.cs:264-348` — typed custom data 的 `get/set` 容器
- ref:incensefiredway code/patch.cs:34-52
- ref:guigu-cultivation Code/Patches/HarmonyPatches.cs:24-90
- ref:biology Code/UnitHealthTab.cs:125-136

## Provenance

Derived from: WorldBox 0.51.2 `Actor.updateAge` / `Actor.updateStats` / `BaseSystemData`, ref:incensefiredway, ref:guigu-cultivation, ref:biology。该模块组合的是已验证入口与持久化/重放机制；年度幂等键是对这些机制的通用化约束。
