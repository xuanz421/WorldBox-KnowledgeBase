# 简单汉化

## Identity

- Name: 简单汉化 v1.0.8
- Source ID: `ref:simple-chinese-localization`
- Dir: `简单汉化_1.0.8`
- Files: 6 total / 1 C#
- Confidence: Verified

## Purpose

非官方汉化：Locales/cz.json、ch.json 覆盖/补充中文文本，修复 LocalizedText 切语言后不刷新问题；附带附身模式操作提示文本替换。

## Systems

- Primary: Localization
- Secondary: UI, Utility

## Key Implementation

- `ModClass.cs` (L45-50) — IReloadable.Reload 热重载语言文件标准实现
- `ModClass.cs` (L55-63) — LocalizedText.Start Postfix 强制 updateText，修 autoField=false 文本不刷新

## Techniques

NML IReloadable + LM.LoadLocale/ApplyLocale、LocalizedText.Start Postfix、Update 轮询一次性修补 PossessionUI 硬编码文本、Config.isEditor = true

## WorldBox Usage

LocalizedText.{Start,key,autoField,updateText} / LocalizedTextManager.instance.language / PossessionUI.instance._text_* / LM.Get/Has / Toolbox.coloredString

## NeoModLoader Usage

- BasicMod<T> / IReloadable.Reload / GetLocaleFilesDirectory(GetDeclaration()) / LM.LoadLocale/ApplyLocale / Config.isEditor（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| LocalizedText.Start | Postfix | ModClass.cs:55-63 | 语言热切换后刷新非 autoField 文本 |

## Reusable Ideas

- IReloadable + LM.LoadLocale 组合可在不重启游戏时重载汉化
- LocalizedText.Start Postfix 是修"切语言不刷新"类 bug 的通用点

## Pattern Candidates

- `locale-hot-reload`
- `localizedtext-refresh-postfix`

## Evidence

- ModClass.cs:10-16,18-22,45-50,55-63

## Notes

NML 本地化管线的参考实现；Config.isEditor=true 副作用未知。
