# Pattern: clone-modify-asset

## Status

Strong Verified

## Goal

以最小成本创建派生资产：`clone` 现有资产（GodPower/ActorAsset/BuildingAsset）后修改少量字段。

## When to Use

需要"和原版几乎一样但改几个参数"的资产时——比从零构造可靠得多（自动继承全部未显式设置的字段与贴图）。

## Relevant Systems

Assets, Buildings, Actor

## Core WorldBox Types

`AssetManager.powers.clone(id, templateId)` / `AssetManager.actor_library.clone(id, sourceId)` / `BuildingAsset`（直接改字段+缓存原值）

## Implementation Flow

1. **powers**：`powers.clone("mymod.power_x", "$template_drops$")` 克隆模板神力，再改 icon/click_action
2. **actor**：`actor_library.clone(id, sourceId)` 派生生物，需要自定义贴图时反射调 `loadTexturesAndSprites` 重载（guigu）
3. **buildings**：直接修改 BuildingAsset 数值字段——先缓存原值作基线，配置回调可能早于 OnModLoad 触发（creepmob）
4. clone 后按需 add 到对应 library（clone 通常已注册，核对）

## Reference Implementations

Primary:
- Mod: ref:sandbox — File: Features/MakeUnitKing.cs:4-18 — Symbol: MakeUnitKing
  Why: powers.clone + 自建 DropAsset 的完整落地触发模板

Alternatives:
- Mod: ref:powerbox — File: Code/Features/Actors/Mastef.cs:10 — Why: actor_library.clone 派生生物
- Mod: ref:creepmobboost — File: CreepMobBoost.cs:44-78 — Why: BuildingAsset 数值修改+基线缓存+配置化

## Minimal Example

```csharp
var power = AssetManager.powers.clone("mymod.zap", "$template_drops$");
power.click_power_action = new ClickPowerAction(MyPower.clickZap);
```

## Caveats

- **模板 ID 依赖版本**：`"$template_drops$"` 等魔法常量是 NML/community 约定（Unverified 来源），升级需回归验证
- **clone 不深拷引用字段**：action/asset 引用可能与源共享，修改前确认字段语义
- **BuildingAsset 直改是全局的**：影响所有该建筑实例；要恢复需缓存原值

## Evidence

- ref:sandbox Features/MakeUnitKing.cs:4-18
- ref:powerbox Code/Features/Actors/Mastef.cs:10（+ loadTexturesAndSprites 反射：guigu ModCreatureRegistry.cs:28-41）
- ref:creepmobboost CreepMobBoost.cs:44-78
- WorldBox: AssetManager.powers/actor_library 的 clone 方法（WBKB symbol AssetManager 相关 verified）

## Provenance

Derived from: ref:sandbox, ref:powerbox, ref:creepmobboost, ref:guigu-cultivation
