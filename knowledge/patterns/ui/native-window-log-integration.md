---
title: Native window lifecycle and pooled culture log rows
aliases:
  - 原生窗口首次打开与日志接入
  - AbstractWindow first-open lifecycle
---

# Pattern: native-window-log-integration

## Status

Verified — WorldBox 0.51.2 / NML snapshot `neomodloader-02266fe8185d` / NewEra 1.0.0。窗口首次 Configure 打开有修复前失败与修复后实机专项证据。

## Goal

复用原版窗口、按钮与日志行，同时正确处理首次创建、窗口动画、pool 行复用、稳定对象身份及异步截图边界。

## When to Use

NML 自定义设置入口、主功能栏按钮、独立历史视图、点击记录打开 Culture 或为节点添加编号 overlay。

## Relevant Systems

UI, Culture, History, Save/Persistence, NML

## Implementation Flow

1. `AbstractWindow<T>.CreateAndInit(id)` 创建并关闭 GameObject，设置 `Instance`、content/background，调用 `Init`，最后标记 initialized；不是普通无副作用构造函数。
2. NewEra 首次打开顺序为 `ScrollWindow.hideAllEvent(pWithAnimation: false)` → `CreateAndInit` → `ScrollWindow.finishAnimations()` → `ScrollWindow.showWindow(id)`。已有窗口直接 show。不要用第二次 Configure 点击掩盖首次失败。
3. 每帧懒创建窗口时，仅在没有 active window、没有 animation 时执行。第一次空窗口创建可能扰动原窗口当前引用。
4. 功能栏入口通过 `PowerButtonCreator.CreateSimpleButton` 和 `AddButtonToTab` 接入原版布局，先用固定 transform name 做幂等检查，不用手算屏幕像素坐标。
5. 独立日志借用 `WorldLogWindow` 的行 prefab、object pools、排序、国家色与地图定位；按独立 group 过滤数据，普通文化发展与国家时代提示分开。
6. 普通文化记录每文化一次；用 `WorldLogMessage.special3` 存 culture ID，以 `World.world.cultures.get(id)` 在点击时查现存对象。同名 culture 不能按名称识别，消亡后保留文字但禁用跳转。
7. pool 行的 click/hover listener 每次读取当前 `__instance.message`，不要闭包固定首次绑定 message。仅首次创建 Button 时 AddListener；每次换绑都更新 enabled 与 raycastTarget。
8. NewEra 普通发展记录通过 `db.DBInserter.insertLog` 保存；时代晋升仍用原版 `.add()` 提示入口。需要分别验证保存、展示、去重和世界重载。
9. overlay 用原版 font、单实例 Text，`raycastTarget = false`；编号与节点名称、成品图分离。设置页面重建后测试读取实际新 root，不扫描同帧刚停用但尚未 Destroy 的旧对象。

## Reference Implementations

- `consumer:NewEra@fe2d2c88320e8a3d6544b2f5b2f0b3bf88c645ef`: `Source/UI/EraSettingsWindow.cs:35`, `Source/UI/EraDevelopmentLog.cs:16`, `Source/UI/EraDevelopmentLogWindow.cs:21`。
- NML `NeoModLoader/NeoModLoader.api/AbstractWindow.cs:22`；WorldBox `ScrollWindow.cs:728`, `:871`。
- Related pattern IDs: `ui-button-injection`, `persistent-mod-data`, `nml-acceptance-release`。

## Regression Checks

| Case | Assertion |
| --- | --- |
| 游戏启动后首次 Configure | 单次点击后新窗口 active，旧列表 inactive |
| 重复打开 / 关闭 | 无重复按钮、listener 或 rank Text |
| 同名 Culture / pool row 换绑 | 跳转按当前行的 culture ID |
| Culture 消亡 | 文字仍可读，不跳转失效对象 |
| 同文化多国家 | 普通记录一条；时代国家事件按设计分开 |
| 中英与 2560×1600 / 1280×800 | 滚动可达、tooltip title 正确、边界完整 |
| world reload | 原版数据库记录及 special3 身份保留 |

## Caveats

- 非空／非黑截图只说明有画面，不能证明 tooltip 对象、文字、布局正确；需同步记录 active state、title、目标 node ID 和 bounds。
- `ScreenCapture.CaptureScreenshot` 异步落盘；文件存在但零字节不能算完成。实际鼠标位置也可能在切换窗口后落到视口外。
- 最新完整审查的 Campfire 英文 tooltip inactive 与此前六级房屋 tooltip 被其他节点标题替换的根因仍未知；不得把通过的设置专项称作全量 UI 通过。
- 原版 `startShowingWindow` 声明于 `WindowMetaGeneric<,>`，不是每个子窗口自己的方法；Harmony 字符串目标要核对真正声明类。
- 原版简体中文语言代码为 `cz`，不要误当 Czech；证据是 `GameLanguageLibrary.cs:12`。

## Evidence

- NewEra `Source/UI/EraDevelopmentLogWindow.cs:70`, `:98`; `Source/Content/Research/EraDevelopmentHistory.cs:53`, `:60`; `Source/UI/EraNodeRank.cs:31`。
- 原版 `WindowMetaGeneric.cs:75`, `GameLanguageLibrary.cs:12`；NML `AbstractWindow.cs:22`。
- 修复前首次入口 `bin/acceptance-67b35b49816a449984e501eb17f0255d.tsv`: 0 PASS / 1 FAIL；修复后 `bin/acceptance-b1783a2a16164f7e867aabb89b9b04a1.tsv`: 97 PASS / 1 INFO / 0 FAIL。
- 最新设置专项 `bin/acceptance-6a7f20a65eea4826bce6cc21bd6d946c.tsv`: 97 PASS / 1 INFO / 0 FAIL，SHA256 `53F498DACE297C74A092742B8D03C7880538F00A032A9A7E5DF26842BA7AB369`；24 张非空截图与单次真实入口检查。该证据来自既有台账，不是本次新跑。

## Provenance

2026-10-10 从 NewEra 1.0 收尾经验提炼；consumer 源码版本与仓库为上述 commit / `https://github.com/xuanz421/NewEra`。NML 和 WorldBox 证据来自 WBKB 本地版本化 snapshot；不复制 UI 资产或游戏源码入 Git。
