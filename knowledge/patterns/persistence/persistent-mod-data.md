# Pattern: persistent-mod-data

## Status

Strong Verified

## Goal

按数据生命周期选择正确的持久化方案——五个已验证层级的选型表。

## When to Use

任何需要跨会话/跨存档保留的数据。核心问题永远是：跟存档走、跟世界走、还是跟 mod 走？

## Relevant Systems

Save/Persistence

## Core WorldBox Types

`Actor.data`（per-actor，随存档） / `MapStats.custom_data`（世界级，随存档） / `SaveManager.currentSavePath/getCurrentSlot`（存档槽目录） / `kingdom.data.custom_data_string` / `city.data`

## Implementation Flow

选型表（作用域从窄到宽）：

| 层级 | 载体 | 适用 | 代表 |
|---|---|---|---|
| per-actor | actor.data get/set | 单位状态 | actor-data-custom-state |
| 世界级 | map_stats.custom_data.{bool,string} | 世界资源/开关/世界键 | xuanmen-daojie |
| 存档附属 | 存档槽目录文件（txt/json） | 大体积/结构化 | guigu |
| mod 级 | persistentDataPath + JSON | 用户设置（跨存档） | shtoolkit |
| 外部库 | sqlite-net（mod 目录） | 大量查询型记录 | actorhistory |

关键配套：世界键（"wd-{life_dna}-{Guid}" 存 custom_data）做跨存档隔离；换世界检测用 seed/life_dna 指纹自动重置（xuanjian/xuanmen）。

## Reference Implementations

Primary（每个层级一个）:
- 世界级: ref:xuanmen-daojie — File: code/Systems/Cultivation（custom_data 存灵炁经济）+ Globals.cs:20,138
- 存档槽: ref:guigu-cultivation — File: Code/Core/ReincarnationPersistence.cs:82-106 — Why: 定位存档槽目录写文件
- mod 级: ref:shtoolkit — File: Code/sh_toolkit_main.cs:73-75,120-145 — Why: persistentDataPath JSON 设置
- SQLite: ref:actorhistory — File: code/ActorHistoryStorage.cs:46,156-202 — Why: sqlite-net 事务批插+世界键+覆盖索引

## Caveats

- **反例**：familytree 死亡记录只存内存静态字典——重开存档全丢（profile 已记录）
- **存档槽路径 API**（SaveManager.folderPath/getCurrentSlot）属于半私有，版本升级需回归
- **sqlite-net 在 Mono 可用**但需随 mod 分发依赖程序集
- custom_data 键也要 mod 前缀（世界级键空间同样共享）

## Evidence

- ref:guigu-cultivation Code/Core/ReincarnationPersistence.cs:82-106
- ref:shtoolkit Code/sh_toolkit_main.cs:73-75,120-145
- ref:actorhistory code/ActorHistoryStorage.cs:46,156-202,276-294
- ref:xuanmen-daojie code/Core/Globals.cs:20,138（life_dna 指纹）
- ref:xuanjian-xianzu Persistence.cs:63-168（seed 检测+重试+脏检查）

## Provenance

Derived from: ref:guigu-cultivation, ref:shtoolkit, ref:actorhistory, ref:xuanmen-daojie, ref:xuanjian-xianzu（5 个独立实现覆盖全部层级）
