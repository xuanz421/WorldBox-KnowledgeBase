# FamilyTree（族谱）

## Identity

- Name: FamilyTree v0.1.5
- Source ID: `ref:familytree`
- Dir: `FamilyTree_0.1.5`
- Files: 12 total / 8 C#
- Confidence: Verified

## Purpose

单位窗口加"族谱"按钮：弹出全屏可平移缩放的氏族思维导图（长辈/配偶/子女/孙辈，含已故成员与死因），通过 hook Actor.countDeath 记录死亡快照补全死者亲属关系。

## Systems

- Primary: UI
- Secondary: Actor（家族关系）, Events（死亡记录）, Kingdom/Clan

## Key Implementation

- `Patch/PatchActorDeath.cs` (L9-14) — countDeath Postfix 捕获 AttackType，死前抢存亲属 id 快照
- `History/DeathRecordManager.cs` (L23-52) — 死亡快照数据模型（kills/age/parent_id/lover.id/clan.id）
- `UI/ClanMindmapWindow.cs` (L81-1700) — 纯 UGUI 平移缩放思维导图（Canvas 550/1920x1080/中键拖拽/滚轮缩放/旋转拉长 Image 画线）
- `UI/ClanTreeWindowUI.cs` (L17-332) — NML AutoLayoutWindow<T> 四区分栏
- `Patch/PatchUnitWindow.cs` (L26-67) — 克隆 _icon_favorite 按钮注入族谱入口

## Techniques

死亡快照 Postfix、UnitWindow 按钮克隆注入、树构建（活体+死亡记录合并→parentMap→递归）、NML AutoLayoutWindow 布局、自绘全屏 Canvas 导图、遮罩期防误操作（ScrollWindow.isWindowActive 强制 true）

## WorldBox Usage

UnitWindow（_icon_favorite/OnEnable） / Actor.{countDeath,getParents,getChildren,lover,clan} / AttackType 枚举 / World.world.units.units_only_alive / Clan.{getChief,getID} / ScrollWindow / WorldTip / SpriteTextureLoader / LocalizedTextManager.current_font

## NeoModLoader Usage

- BasicMod.OnModLoad + LogInfo（Verified）
- AutoLayoutWindow<T>.CreateWindow / AutoVert,AutoHoriLayoutGroup / BeginVertGroup,AddChild / OnNormalEnable（Verified）
- Harmony PatchAll(assembly)（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.countDeath | Postfix | Patch/PatchActorDeath.cs:10 | 记录死亡 |
| UnitWindow.OnEnable | Postfix | Patch/PatchUnitWindow.cs:17 | 注入按钮 |
| ScrollWindow.isWindowActive | Prefix | Patch/PatchScrollWindow.cs:13 | 导图打开时冻结底层窗口判定 |
| ScrollWindow.updateRightClickBack | Prefix | Patch/PatchScrollWindow.cs:29 | 禁右键关闭 |

## Reusable Ideas

- 死亡快照模式：countDeath Postfix 抢存亲属 id（死者 Actor 即将被回收，事后无法再查关系）——任何"历史记录"类 mod 的关键时点（DeathRecordManager.cs:38-49）
- 克隆 UnitWindow 现成图标按钮（favorite 行）+ 重绑 onClick/TipButton = 向原生窗口加按钮的稳妥做法（PatchUnitWindow.cs:36-56）
- 无图资源依赖的连线绘制：中点定位 + Atan2 旋转 + length 拉长的 3px Image，配平移缩放即可做全屏关系图（ClanMindmapWindow.cs:1610-1636）

## Pattern Candidates

- `death-snapshot-recorder`
- `ugui-pan-zoom-overlay`

## Evidence

- FamilyTree.cs:14-21 / PatchActorDeath.cs:11-14 / DeathRecordManager.cs:41-51
- ClanTreeBuilder.cs:80-103 / ClanMindmapWindow.cs:104,137,1610-1700

## Notes

死亡记录仅存内存静态字典，未接存档持久化（重开存档丢失）——已知改进点。
