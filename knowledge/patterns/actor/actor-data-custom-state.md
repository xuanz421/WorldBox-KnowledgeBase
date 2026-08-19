# Pattern: actor-data-custom-state

## Status

Strong Verified

## Goal

用 `actor.data.get/set`（ActorData 字符串键）为单位保存自定义状态，随原版存档自动持久化，零额外存档工作。

## When to Use

任何需要 per-actor 且跨存档保留的状态：境界修为、血统、计数器、family_name 等。

## Relevant Systems

Actor, Actor Data, Save/Persistence

## Core WorldBox Types

`Actor.data`（ActorData）/ `Actor.data.get<T>(key, out T, default)` / `Actor.data.set(key, value)`

## Core NeoModLoader APIs

（无——纯 WorldBox API）

## Implementation Flow

1. 定义集中键常量（如 `Constants.DataKeyXiuWei = "xiuxian.xiu_wei"`，mod 前缀防冲突）
2. 读：`actor.data.get(key, out float v, 0f)`；写：`actor.data.set(key, v)`
3. 封装扩展方法三件套 Get/Set/Change 减少样板
4. 大量键时建集中读写层（如 CultivationData 4700 行键值层）

## Reference Implementations

Primary（Recommended）:
- Mod: ref:incensefiredway — File: code/utils/ActorExtensions.cs:213-230 — Symbol: ActorExtensions
  Why: Get/Set/Change 三件套扩展方法模板，最小可直接照抄

Alternatives:
- Mod: ref:guigu-cultivation — File: Code/Core/CultivationData.cs:112-116,417-424 — Why: 大规模集中键管理（4700 行键值层）
- Mod: ref:xuanmen-daojie — File: code/Core/ActorExtensions.cs:289-304 — Why: data/stats 双轨变体（读走 stats 供引擎显示）

## Minimal Example

```csharp
public static float GetXiuWei(this Actor a) =>
    a.data.get("mymod.xiu_wei", out float v, 0f) ? v : 0f;
public static void SetXiuWei(this Actor a, float v) =>
    a.data.set("mymod.xiu_wei", v);
```

## Caveats

- **键前缀必须带 mod id**：所有 mod 共享同一 ActorData 键空间
- **类型版本兼容**：换类型（float→string）旧档不迁移，需版本键兜底
- **每帧读写性能**：热路径值可镜像到内存字典，定期回写（guigu 月结式）
- 与 map_stats.custom_data（世界级）区分：本 pattern 是 per-actor

## Evidence

- ref:incensefiredway code/utils/ActorExtensions.cs:213-230
- ref:guigu-cultivation Code/Core/CultivationData.cs:112-116
- ref:chinesename Code/Patches/ActorNamePatch.cs:42-56（family_name 遗传）
- ref:xuanmen-daojie code/Core/ActorExtensions.cs:289-304

## Provenance

Derived from: ref:guigu-cultivation, ref:incensefiredway, ref:xuanmen-daojie, ref:chinesename（4 个独立实现，多模组共识）
WorldBox evidence: actor.data get/set 调用面（WBKB refs Actor.data 84+ 处）
