# Pattern: custom-power-tab

## Status

Verified

## Goal

创建自定义神力标签页（tab）并组织其中的按钮分区。

## When to Use

mod 功能多到塞不进原版 tab，需要自己的入口页时。

## Relevant Systems

UI, Assets

## Core WorldBox Types

`TabManager.CreateTab` / `PowersTab` / `PowerButtonCreator`

## Core NeoModLoader APIs

`TabManager.CreateTab`（NML 侧，Verified）；`PowersTabExtension.SetLayout`（Unverified）

## Implementation Flow

1. `TabManager.CreateTab("MyTab", "tab_locale_key", "desc_key", iconSprite)` 建 tab
2. 大量按钮时做二级分区：建 Spawns/Metas 等 Section GameObject，SetActive 切换（powerbox 式），别塞爆单页
3. 按钮两种来源：`PowerButtonCreator.CreateSimpleButton`（绑定 GodPower）或纯代码 Builder（sandbox ButtonBuilder 四样式）
4. 分组布局可用 `SetLayout(List<string>)` 风格 API（Unverified，见 caveats）

## Reference Implementations

Primary:
- Mod: ref:powerbox — File: Code/Features/Buttons/PowerboxTab.cs:17-90 — Why: tab+分区切换+三层 ButtonFeature 抽象
Alternatives:
- ref:sandbox — UI/SandboxTab.cs:30-60 — Why: 分组布局 + Builder 按钮
- ref:xuanjian-xianzu — XuanJianUIManager.cs:40-58 — Why: 中文 mod 同法验证

## Caveats

- CreateTab 的 locale key 需在 Locales 提供，否则显示 key 本身
- 热重载下 tab 重复创建——xuanjian 用反射防热重载重复
- NML 布局 API（SetLayout/_children）属隐式契约（sandbox 魔法数 26），升级需回归

## Evidence

- ref:powerbox Code/Features/Buttons/PowerboxTab.cs:23,50-63
- ref:sandbox UI/SandboxTab.cs:30-42 / Toolkit/Graphics/ButtonBuilder.cs
- NML: TabManager（WBKB neomodloader 源索引 verified）

## Provenance

Derived from: ref:powerbox, ref:sandbox, ref:xuanjian-xianzu
