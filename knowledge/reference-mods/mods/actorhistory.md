# ActorHistory（角色史书）

## Identity

- Name: ActorHistory v1.8.0（guid xingyao_ActorHistory）
- Source ID: `ref:actorhistory`
- Dir: `ActorHistory_1.8.0`
- Files: 36 total / 23 C#
- Confidence: Verified

## Purpose

为"收藏"(favorite)单位自动记录生平事件史书：Harmony 钩住生死/战争/政治/社交/装备等 40+ 游戏事件，按 7 类叙事分类（机遇/抉择/挫折/成就/牵绊/日常/超越）生成带日期着色文本，写入 SQLite 与分类 txt；UI 提供史书窗口+目录+Ctrl+T 热键。

## Systems

- Primary: Events, Save/Persistence, UI
- Secondary: Actor, Kingdom/City/Clan/Alliance/War（只读观察）, Text 渲染

## Key Implementation

- `code/ActorHistoryMod.cs:6-19` — BasicMod 入口：PatchAll + 窗口/按钮安装
- `code/LogService.cs:93-142` — EnqueueLog：事件入队/5s 节流 Flush/收藏过滤中枢
- `code/ActorHistoryStorage.cs:46` — SQLite 存储：表/索引/CRUD/世界键/单调主键（L282-294）
- `code/patch/CombatPatch.cs:40` — checkDeath Prefix：死亡+牵绊通知范式（全程 try/catch 观察式）
- `code/ui/ActorHistoryWindowUI.cs:207` — NML SingleAutoLayoutWindow 窗口 + 分类页签；L701-770 克隆按钮注入
- `code/ui/ActorHistoryMainTabButton.cs:26` — 主 tab 加按钮

## Techniques

Prefix/Postfix 纯观察式事件采集（try/catch 包裹）、双持久化（内存缓冲→sqlite-net 事务批插 + 人类可读 txt）、WorldKey 存 map_stats.custom_data 跨存档隔离（"wd-{life_dna}-{Guid}"）、UI 克隆注入、SingleAutoLayoutWindow + Text 对象池、热键驱动、旧版 txt 迁移兼容

## WorldBox Usage

Actor.{checkDeath,newKillAction,addTrait,removeTrait,changeHappiness,setBestFriend,becomeLoversWith,setClan,setProfession,...} / BabyMaker / WarManager.{newWar,endWar} / Kingdom.setKing / City.{setLeader,giveItem} / Clan.addChief / Alliance / ActorEquipmentSlot / ItemCrafting / UnitWindow.{OnEnable,pressFavorite} / ScrollWindow / MapBox.{clearWorld,finishingUpLoading} / World.world.getCurWorldTime / actor.data

## NeoModLoader Usage

- BasicMod<T>.OnModLoad / GetDeclaration().FolderPath / LogInfo（Verified）
- SingleAutoLayoutWindow.CreateWindow / PowerButtonCreator.{GetTab,CreateSimpleButton,AddButtonToTab} / LocalizedTextManager.add（Verified）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.checkDeath | Prefix | code/patch/CombatPatch.cs:40 | 收藏者死亡+亲属牵绊记录 |
| Actor.newKillAction | Postfix | code/patch/WarPatch.cs:264 | 战争击杀 |
| BabyMaker.makeBabiesViaSexual | Postfix | code/patch/BirthPatch.cs:10 | 出生/家系事件 |
| WarManager.endWar | Postfix | code/patch/WarPatch.cs:217 | 战争结算 |
| Kingdom.setKing | Postfix | code/patch/PoliticsPatch.cs:33 | 登基事件 |
| Alliance.join | Prefix | code/patch/AlliancePatch.cs:162 | 外交事件 |
| MapBox.clearWorld | Prefix | code/ActorHistoryStorage.cs:297 | 换世界前 Flush |
| UnitWindow.OnEnable | Postfix | code/ui/ActorHistoryWindowUI.cs:12 | 注入按钮+热键 |

## Reusable Ideas

- "收藏者过滤 + 分类叙事 + 世界键隔离"三件套（LogService.cs:85-91）——任何生平/观察类 mod 可直接套用
- sqlite-net 轻量持久化：覆盖索引、事务批插、失败回灌缓冲（ActorHistoryStorage.cs:163-198）
- 克隆现有 UI 按钮重绑 onClick 的零布局侵入注入（ActorHistoryWindowUI.cs:722-746）
- MapBox.clearWorld Prefix 落盘 + finishingUpLoading Postfix 恢复的存档生命周期钩子对

## Pattern Candidates

- `favorite-actor-event-recorder`
- `sqlite-mod-storage`
- `clone-button-ui-injection`

## Evidence

- ActorHistoryMod.cs:8-18 — 入口
- LogService.cs:85-91,137 — 采集中枢
- ActorHistoryStorage.cs:97-103,266-270,297-313 — 存储与世界键
- CombatPatch.cs:40-76 — 死亡 patch
- ActorHistoryWindowUI.cs:243-248,722 — UI
- ActorHistoryMainTabButton.cs:26-48 — tab 按钮

## Notes

约 44 个 patch 类；WarTracker 仅内存态；Category 枚举用中文标识符。
