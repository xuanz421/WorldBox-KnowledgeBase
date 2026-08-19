# Pattern: register-actor-trait

## Status

Strong Verified

## Goal

为 Actor 注册自定义特质（ActorTrait），并挂接每帧/攻击/特殊效果回调，实现被动技能、境界、buff 等系统。

## When to Use

需要给单位添加可堆叠、可遗传、带图标和属性修正的"特性"时。这是 Reference Mods 中使用频率最高的资产注册模式。

## Relevant Systems

Traits, Actor, Assets, Combat

## Core WorldBox Types

`ActorTrait` / `BaseStats` / `ActorTraitGroupAsset` / `AssetManager.traits` / `AssetManager.trait_groups` / `Actor.addTrait`

## Core NeoModLoader APIs

（注册本身不需要 NML API；mod 入口用 BasicMod&lt;T&gt;.OnModLoad）

## Implementation Flow

1. `new ActorTrait { id = "modid.trait_x", path_icon = "...", group_id = "...", base_stats = new BaseStats{ ["lifespan"] = ... } }` 构造（图标可省或用 SpriteTextureLoader 路径）
2. `AssetManager.traits.add(trait)` 注册；如需分组同时向 `AssetManager.trait_groups` 注册 ActorTraitGroupAsset
3. 需要行为时挂委托：`trait.action_special_effect += new WorldAction(Class.method)`（每帧 tick）或 `trait.action_attack_target += new AttackAction(...)`（攻击时）
4. 需要 vanilla 兼容时同步检查去重（见 safe-asset-registration）
5. 运行期用 `actor.addTrait(trait)` / trait 阶梯切换（upTrait 式交换）

## Reference Implementations

Primary（Recommended）:
- Mod: ref:incensefiredway — File: code/trait.cs:25-99,166 — Symbol: traits.Init
  Why: 52 个特质统一注册 + action_special_effect/action_attack_target 挂接的最规整样板

Alternatives:
- Mod: ref:thefantasyworld — File: code/trait.cs:15-25 — Symbol: RankTalentst_AddActorTrait
  Why: 工厂方法批量造境界天赋
- Mod: ref:guigu-cultivation — File: Code/ModEntry.cs L15-109 — Why: trait_groups + traits 顺序注册（大数量）

## Minimal Example

```csharp
var trait = new ActorTrait {
    id = "mymod.example_trait",
    path_icon = "ui/icons/example",
    base_stats = new BaseStats { ["lifespan"] = 10f },
};
AssetManager.traits.add(trait);
trait.action_special_effect += new WorldAction(MyEffects.tick);
```

## Caveats

- **ID 冲突**：无命名空间隔离，务必加 mod 前缀；重复 add 同 ID 行为未定义（见 safe-asset-registration）
- **action_special_effect 每帧调用**：重逻辑必须自带节流（比较 guigu 分帧 / xuanmen 0.5s 节流）
- **注册时机**：必须在 OnModLoad 内完成；读档时已序列化的 trait id 需已存在，否则丢弃

## Evidence

- WorldBox: ActorTrait 类（WBKB 索引 verified，symbol ActorTrait）
- ref:incensefiredway code/trait.cs:25-99,166（traits.Init 注册+委托）
- ref:thefantasyworld code/trait.cs:15-25（trait 工厂）
- ref:guigu-cultivation Code/ModEntry.cs:15-109（批量注册）

## Provenance

Derived from: ref:incensefiredway, ref:thefantasyworld, ref:guigu-cultivation, ref:xuanjian-xianzu, ref:xuanmen-daojie
WorldBox evidence: AssetManager.traits 注册面（WBKB symbol/refs 可查）
