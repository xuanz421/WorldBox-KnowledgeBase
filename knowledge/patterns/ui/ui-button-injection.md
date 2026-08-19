# Pattern: ui-button-injection

## Status

Verified

## Goal

向原生 UI 窗口（UnitWindow/KingdomWindow 等）添加按钮而不破坏原布局。

## When to Use

在已有窗口加功能入口（族谱按钮/史书按钮/自定义属性行）。

## Relevant Systems

UI

## Core WorldBox Types

`UnitWindow.OnEnable` / 现成按钮 GameObject（如 `_icon_favorite` 行）/ `TipButton` / `StatsIcon` / `SpriteTextureLoader.getSprite`

## Implementation Flow

1. Postfix `UnitWindow.OnEnable`（窗口每次打开都会走）
2. **克隆现有按钮**：Instantiate 同行现成图标按钮（保留布局/TIP/样式），改 `Image.sprite`、`TipButton.textOnClick`、重绑 `onClick.AddListener`
3. 用静态 flag 保证只克隆一次（防 OnEnable 重复）
4. 图标用 `SpriteTextureLoader.getSprite("ui/icons/xxx")` 从 mod 资源目录取
5. 属性行变体：克隆 `i_kills` StatsIcon + `setIconValue` 显示自定义数值

## Reference Implementations

Primary:
- Mod: ref:familytree — File: Patch/PatchUnitWindow.cs:26-67 — Why: 克隆 favorite 按钮最干净的 40 行
Alternatives:
- ref:actorhistory — code/ui/ActorHistoryWindowUI.cs:701-770 — Why: 同法+主 tab 按钮
- ref:incensefiredway — code/UnitWindowStatsIcon.cs:285-352 — Why: StatsIcon 属性行变体

## Caveats

- 克隆位置必须在原按钮父物体下（同布局组），否则错位
- 窗口 prefab 每次开世界可能重建——OnEnable 内做幂等检查
- 反面路线：自绘 Builder 按钮（sandbox ButtonBuilder）可行但样式与原生不一致

## Evidence

- ref:familytree Patch/PatchUnitWindow.cs:26-67 / ref:actorhistory ActorHistoryWindowUI.cs:722-746 / ref:incensefiredway UnitWindowStatsIcon.cs:285-352

## Provenance

Derived from: ref:familytree, ref:actorhistory, ref:incensefiredway
