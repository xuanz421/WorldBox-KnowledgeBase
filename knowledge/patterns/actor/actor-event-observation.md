# Pattern: actor-event-observation

## Status

Strong Verified

## Goal

以纯观察方式采集 Actor 生命周期事件（死亡/击杀/出生/登基/联盟等），构建史书、统计或历史记录系统。

## When to Use

做"记录/观察/统计"类功能，不修改游戏行为时。核心风险点：死亡后 Actor 对象被回收，必须在事件发生时抢存数据。

## Relevant Systems

Actor, Events, Save/Persistence

## Core WorldBox Types

`Actor.checkDeath` / `Actor.newKillAction` / `BabyMaker.makeBaby(iesViaSexual)` / `WarManager.{newWar,endWar}` / `Kingdom.setKing` / `Alliance.join` / `Actor.{lover,clan,parents}` / `AttackType`

## Implementation Flow

1. 选事件→Patch 点映射：死亡 `Actor.countDeath`/`checkDeath`、击杀 `newKillAction`、出生 `BabyMaker`、政治 `Kingdom.setKing`、外交 `Alliance.join`
2. Postfix（非侵入）内**立即快照**所需亲属关系（死后无法再查）：parent_id/lover.id/clan.id/kills
3. 入队+节流批量落盘（内存 buffer → 定时 Flush），全程 try/catch 包裹——观察类 patch 绝不能抛异常影响原版
4. 持久化选型见 persistent-mod-data（SQLite 带世界键 / txt）
5. 世界隔离：WorldKey 存 map_stats.custom_data（"wd-{life_dna}-{Guid}"），换世界重置

## Reference Implementations

Primary（Recommended）:
- Mod: ref:actorhistory — File: code/LogService.cs:93-142 + code/patch/CombatPatch.cs:40-76 — Symbol: EnqueueLog / checkDeath Prefix
  Why: 40+ 事件钩子→分类→节流→SQLite 全链路，观察类范本

Alternative:
- Mod: ref:familytree — File: Patch/PatchActorDeath.cs:10-14 + History/DeathRecordManager.cs:38-49 — Why: 死亡快照最小实现（抢存亲属 id）

## Caveats

- **死亡快照时机**：countDeath Postfix 时 Actor 即将回收——之后任何 `actor.getParents()` 都不可靠（familytree 的核心教训）
- **try/catch 必须包全程**：观察 patch 抛异常会破坏原版调用链
- **性能**：高频事件（getHit 级）需先过滤（如只记录收藏单位）再入队

## Evidence

- ref:actorhistory code/patch/CombatPatch.cs:40-76 / LogService.cs:85-142
- ref:familytree Patch/PatchActorDeath.cs:10-14 / DeathRecordManager.cs:38-49
- WorldBox: 事件方法均在 WBKB 索引（callers 可查原版调用链）

## Provenance

Derived from: ref:actorhistory, ref:familytree
