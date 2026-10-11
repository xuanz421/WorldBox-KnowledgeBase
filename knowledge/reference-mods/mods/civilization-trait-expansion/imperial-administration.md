---
title: 帝国管理与继承人教育
---

# 帝国管理与继承人教育

## Scope and Status

`ref:civilization-trait-expansion` v1.5.0；Mostly Verified。来源均为 `Code/CivilizationTraitExpansionService.cs` 与 `Code/CivilizationTraitExpansionPatches.cs`。数值来自执行代码，不沿用旧 README 的 50% / 80 年；本次没有游戏运行证据。

## Assets and Unlock State

Culture trait `civ_imperial_administration` 位于 knowledge，创建时 33% roll；注册允许 editor given/removed。Kingdom trait `efficient_administration` 位于 fate，禁止 random spawn、允许 given/removed。Actor `admin_rank_1/2/3` 与 `heir_education_1/2` 位于 cognitive，禁止 birth/inherit/grow-up/random spawn。rank trait 自身没有倍率 base_stats；倍率由 `Actor.updateStats` patch 重放。教育 trait 则含固定 base_stats。证据：`Code/CivilizationTraitExpansionService.cs:138-185,544-621,1337-1412`。

`TickImperialAdministration(pElapsed)` 每累计 2 个传入 elapsed 单位扫描一次；挂在 `WorldAgeManager.update` Postfix。不要把这一计时器未经引擎节奏核查称为固定 wall-clock 2 秒。证据：`Code/CivilizationTraitExpansionService.cs:1925-1941`、`Code/CivilizationTraitExpansionPatches.cs:469-480`。

| KingdomData `ia_admin_unlock` | 解锁与持续条件 |
| --- | --- |
| 0 / 缺失 | 无状态；有 trait 的旧数据会迁移为 1 或 2 |
| 1 | Culture 有帝国管理且国家 age ≥120；失去 Culture 前置时移除状态并清 rank |
| 2 | 无状态的国家 age ≥500，优先走该通道；之后不依赖 Culture 前置 |

age 来自 `kingdom.data.created_time`；新解锁发原生 WorldLog。旧 trait 缺 source 时，仅在 **没有 Culture 前置且 age ≥500** 才迁移为 2，其余为 1。证据：`Code/CivilizationTraitExpansionService.cs:1948-1990,2135-2224`。

**状态机缺口（代码确认）**：已有 source=1 的王国到 500 年没有主动升级到 2。之后失去前置会先被移除并 continue，下次扫描才可重新按 500 年授予；当次清理可能导致短暂失效与重复日志。不能把“满 500 年自动永久化”解释为现有 source=1 的确定行为。

## Identity Tenure and Persistence

| Owner | Keys | 用途 |
| --- | --- | --- |
| KingdomData | `ia_admin_unlock` | 解锁来源 |
| KingdomData | `ia_king_id`, `ia_king_start` | 在任国王与起点 |
| KingdomData | `ia_heir_id`, `ia_heir_start` | 追踪继承人与起点 |
| CityData | `ia_mayor_id`, `ia_mayor_start` | 在任村长与起点 |
| ActorData | `ia_tendency` | 一次性统治倾向 |

键定义证据：`Code/CivilizationTraitExpansionService.cs:203-214`。get/set 使用原版 typed custom data，不额外写文件；这确认存储载体，完整 world save/load 仍待实机验收。

- `OnKingSet` 读档 `pFromLoad=true` 跳过；新王与持久化 heir ID 一致时继承 heir_start，否则从当前 world time 起。授予 tendency 后即时核算 rank（`Code/CivilizationTraitExpansionService.cs:1447-1477`）。
- `OnCityLeaderSet` 只在 pNew=true 时写当前 ID/time；不重新随机已有 tendency（同文件 `:1482-1522`）。
- 周期扫描用 `SuccessionTool.findNextHeir` 确定 heir，变更后写新 ID/time；旧国王缺 ID 时回退 `timestamp_king_rule`，村长缺 ID 时回退 `past_rulers` 中对应 leader 的最近记录（同文件 `:1581-1604,1995-2074`）。
- 身份计时 `start<=0` 会视为缺失/无效；世界时间恰好 0 的任期是边界待验证。
- actor data 的 tendency 不因退位/重新任命自动清除；“上任随机一次”实际是角色缺该键时随机一次。

## Rank Selection and Stat Replay

| 身份 | 一阶 | 二阶 | 三阶 |
| --- | --- | --- | --- |
| King | 15 年 | 30 年 | 45 年 |
| Tracked heir | 15 年 | 30 年 | 禁止（三阶 clamp 为 2） |
| City leader | 30 年 | 60 年 | 120 年 |

各身份分别算 stage，最后 Math.Max，不按最大年数统一套同一套门槛。`EnsureAdminRankTrait` 仅保留目标 rank；失去身份时 desired=0 清三档。其自身没有先检查管理状态，因此任命 hook 可在尚未解锁时暂时授予 rank；周期未解锁路径会清理。证据：`Code/CivilizationTraitExpansionService.cs:1608-1740,1473,1497,1989`。

重放先要求有效 Actor/stats、`IsImperiumKingdom`、King/leader/tracked heir、stage≥1。stewardship 先按 1.5 / 2.25 / 3.38 向上取整。King/leader 再按 tendency 向上取整：

| tendency | 效果 |
| --- | --- |
| 0 militarist | warfare ×1.5 / 2.25 / 3.38 |
| 1 diplomat | diplomacy ×1.5 / 2.25 / 3.38 |
| 2 tyrant | stewardship 再 ×1.25 / 1.56 / 1.95 |
| 3 balanced | warfare/diplomacy/stewardship 再 ×1.25 / 1.56 / 1.95 |

城市上限只加 `floor(new stewardship/6)-floor(original stewardship/6)` 的正增量，保留原版其他 cities 来源。例：原管理 7、tyrant 一阶 → ceil(7×1.5)=11 → ceil(11×1.25)=14；README 写 17 的示例使用错误倍率。证据：`Code/CivilizationTraitExpansionService.cs:1818-1915`。

`Actor.updateStats` 原版在 !isStatsDirty 时早退（WorldBox `Actor.cs:1747-1753`）。mod Prefix 记录 dirty，Postfix 只在 dirty=true 时重放，所以不会仅因原版早退再次放大旧 stats。**可复用的是该判定纪律**；mod 将 `_didFullRecalc` 放在 static field，存在嵌套调用覆盖风险，后续实现宜采用已有模块中的 per-call `__state`。证据：`Code/CivilizationTraitExpansionPatches.cs:425-453`；相关 pattern ID：`actor-annual-persistent-stat-growth`。

**确定性随机错误**：`EnsureTendency` 使用 `Randy.randomInt(0, 3)`（`Code/CivilizationTraitExpansionService.cs:1515`）；原版 `Randy.cs:81-83` 上界 exclusive，新授予只会产生 0/1/2，balanced 分支虽然存在却无法从此 roll 获得。已保存 tendency=3 仍可执行该分支。

## Heir Education

教育根据 tracked heir 任期独立授予：10 年 `heir_education_1`（stewardship +5 / diplomacy +2 / warfare +2），20 年替换为 `heir_education_2`（+10 / +4 / +4）。有高效管理 trait 才处理；grade 由固定 base_stats 合并，不是临时倍率。证据：`Code/CivilizationTraitExpansionService.cs:97-123,1381-1412,1750-1811`。

**生命周期缺口（代码确认）**：失去继承人身份、管理 trait 消失、年数回退不足 10 时函数直接 return；更换 heir 和 `CleanupKingdomRanks` 仅移除 admin_rank，没有移除教育 trait。因而“教育只作用于当前继承人”不能由代码保证，登基后是否保留亦没有显式清理规则。20 年升级确实会移除一级，但已有二级进入 10–19 年路径时可能再加一级。证据：`Code/CivilizationTraitExpansionService.cs:1760-1785,1802-1806,2001-2019,2097-2125`。

## Risks and Deferred Verification

- 无 King 时不会进入 heir 查找分支，旧 tracked heir ID 未被当场清掉；可能继续通过身份判定。证据：`Code/CivilizationTraitExpansionService.cs:1995-2021`。
- 已达最高档以后，周期扫描不再添加/移除 trait；同文件 `:1723-1734` 不调用额外 setStatsDirty。兼容修改 tendency / Culture / unlock source 时能否及时刷新 stats，需实机验证。
- 每次扫描遍历所有王国及其全部单位；2 秒节流并不等于有分帧预算或常量成本。异常边界覆盖整次扫描，一个王国异常可中止余下王国。
- 帝国管理可 editor given/removed，README 的“不可手动移除”已过时；手动删除后下一扫描可能按年龄再次授予。
- 没有实现 HungerEra 税收/饥荒接口；README 将其列为后续事项，不能收录为当前能力。

待实机检查：15/30/45 与 30/60/120 年边界、多身份、heir 登基/被替换、教育清理、source 1→500 年→失去 Culture、重复 dirty=false updateStats、完整 save/load。以上是待验证范围。
