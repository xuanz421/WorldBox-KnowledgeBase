# Pattern: register-godpower

## Status

Strong Verified

## Goal

注册一个可点击/刷选的新神力（GodPower）：资产配对、图标、tab 归属、触发动作完整链路。

## When to Use

添加任何"上帝之手"操作：对地块/单位/建筑的点击效果、笔刷操作。

## Relevant Systems

Assets, UI, World

## Core WorldBox Types

`GodPower` / `DropAsset` / `AssetManager.powers` / `AssetManager.drops` / `TabManager.CreateTab` / `PowersTab.AddPowerButton` / `PowerButtonCreator`

## Implementation Flow

1. 建自建 GodPower 或 `powers.clone` 模板（见 clone-modify-asset）
2. 配对注册 DropAsset（`new DropAsset{ id, power_id, drop_id }`）→ `AssetManager.drops.add(...)`——复用原版 drop 落点管线（brush/spawn 自动工作）
3. 绑定动作：`click_power_action` / `click_special_action` / `click_power_brush_action` / `select_button_action` / `force_map_mode` 按触发形态选
4. 归属 tab：现有 tab 用 `PowersTab.AddPowerButton`；新 tab 见 custom-power-tab
5. 图标：EmbeddedResources sprite 或 SpriteTextureLoader

## Reference Implementations

Primary（Recommended）:
- Mod: ref:powerbox — File: Code/Features/GodPowers/BuildingUpgradePower.cs:4-45 — Symbol: BuildingUpgradePower
  Why: GodPower+DropAsset 配对注册 + drops 落点管线复用的最清晰范本

Alternatives:
- Mod: ref:sandbox — File: Features/MakeUnitKing.cs:4-18 / SettleCity.cs:7-33 — Why: powers.clone 路线 + QuantumSpriteAsset 画线变体
- Mod: ref:xuanjian-xianzu — File: XuanJianUIManager.cs:40-58 — Why: PowerButtonCreator 按钮挂 tab

## Caveats

- **GodPower 与 DropAsset 的 id 必须互相指向**（drop_id/power_id 配对错误→点击无反应）
- **三种触发形态别混**：click（单击）/brush（笔刷持续）/special（需选中目标）各自 action 字段
- **NML Feature 路线更省样板**：见 nml-feature-authoring——若 mod 已用 NML Feature，优先那条路

## Evidence

- ref:powerbox Code/Features/GodPowers/BuildingUpgradePower.cs:16,27-28
- ref:sandbox Features/MakeUnitKing.cs:4-18 / SettleCity.cs:7-33
- WorldBox: GodPower/DropAsset 类（WBKB 索引 verified）

## Provenance

Derived from: ref:powerbox, ref:sandbox, ref:xuanjian-xianzu
