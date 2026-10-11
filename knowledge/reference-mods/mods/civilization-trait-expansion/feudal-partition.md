---
title: 裂土封侯
---

# 裂土封侯

## Scope and Status

`ref:civilization-trait-expansion` v1.5.0；Mostly Verified，主要实现为 `Code/FeudalPartitionService.cs`。当前可确认算法和 API 边界，但不能确认运行时库存守恒、地块连通或异常后的世界一致性。

## Monthly Entry and Eligibility

`WorldAgeManager.update` Postfix 独立 try/catch 调 `CheckTick`。world/map/kingdoms 缺失或暂停则退出；`year*12+month` 去重；先检查文化年龄再 snapshot 所有 Kingdom 逐一判定。文化 `created_time>0`、非 rekt、满 100 年且无 `feudal_partition` 才授予该 Culture trait。证据：`Code/CivilizationTraitExpansionPatches.cs:483-489`、`Code/FeudalPartitionService.cs:248-342`。

`TryPartition` 的实际条件与顺序：

1. Kingdom 非空、非 rekt、isCiv、非 wild；有存活 King；`getWars` 中没有非空 War。
2. 收集非 rekt 且有 zones 的 City；从全世界 units 找可分封子嗣。
3. 可分封子嗣数量必须 **大于**收集到的 City 数；距 `cte_last_partition_time` ≥36 months（缺/≤0 当作首次）。
4. 首次（没有 `feudal_partition_kingdom`）：King 的 Culture 或任一候选 City 的 Culture 有 `feudal_partition`，且 King 有 `greedy`。后续没有这两项要求。
5. 选 **非首都中面积最大** City；非 ocean tile 数 ≥80，zones≥2。
6. 从边缘选部分 zones；为空或取走全部则退出；随机选一个候选 child 并执行。

证据：`Code/FeudalPartitionService.cs:351-484,494-543,621-668`。README 的“小国最小/大国第三大”没有当前执行分支；`SMALLEST_RULE_MAX_VILLAGES=3` 常量仍在但未使用。`mod.json` / 入口注释的 ≥40 / ≥1 年也与实际常量不符（同文件 `:48-66`）。

## Parent IDs and Candidate Filtering

`GetEligibleChildren` 枚举 `World.world.units`，用 `unit.isChildOf(pKing)` 判定亲子，排除 rekt、自身、未成年、King、明确住在另一个国家的 City、已任所收集 City leader 的单位。没有 City 的孩子不因国家归属筛选自动排除。证据：`Code/FeudalPartitionService.cs:555-615`。

WorldBox `Actor.cs:2844-2856` 使用 parent_id_1/2；`Actor.getChildren(bool pOnlyCurrentFamily=true)` 默认只枚举当前 Family（`Actor.cs:2894-2910`），因此默认调用不等于全部子嗣。原版也提供 `getChildren(false)`；不能把 mod 避开默认枚举解释为原版完全没有跨 Family 查询。mod 当前选用全世界扫描，成本随 world units 增长。

## TileZone Cutting

面积资格按每个 zone.tiles 的非 ocean tile 数，但 **切割比例按 zone 数**计算：`RoundToInt(total * randomFloat(0.40,0.50))`，clamp 1..total-1。随机 x/y 排序与高/低端，取 target 个 zones；没有按地块 group 的完整行/列边界扩展，也没有 flood-fill 检查两边连通。证据：`Code/FeudalPartitionService.cs:643-703`。

因此可确认“按坐标从一侧取块”，不能保证 README 的“整条垂直/水平条带”、严格 40–50% 陆地面积或连通两城。zone 很少时 rounding/clamp 也会超出名义比例。`SelectCoreZone` 选切割集合中距源 City tile 平方距离最远的中心作为新核心（同文件 `:835-861`）。

## Mutation Sequence

`ExecutePartition` 按如下顺序改变世界（`Code/FeudalPartitionService.cs:719-830`）：

1. `CityManager.newCity(pKingdom, core, pChild)`，`setUnitMetas(pChild)`，`newCityEvent(pChild)`。
2. 其余 cut zones 调 `newCity.addZone`。WorldBox `City.cs:1955-1971` 确认会先从旧 City 移除，再 setCity。
3. 找陆地 tile 并尝试 `buildings.addBuilding("stockpile", ...)`，没有检查返回值是否非空。
4. 从源 population / units total 算 floor(40–45%)；snapshot 可移人口（排除 King、源 leader、child、boat），shuffle 后最多移动该数。额外将 child 加入新城并 `setLeader(true)`。
5. `TransferResources` 按每个存储槽位 floor(35–45%) 取走，按 before-after 得到实际 taken，再向新城随机 stockpile 存入。
6. 首次加国家 trait，记录 `cte_last_partition_time` 当前 world time 的 long 值。
7. **最后** `zone_calculator.setDrawnZonesDirty()` 与 `cities.updateDirtyBuildings()`，发首次/后续 WorldLog。

新 City 留在同一 Kingdom；文化/语言/宗教等 metas 来自被分封 child，而不是无条件复制母城文化。目标搬迁量依赖 status.population，实际排除后的 pool 可能不够；child 额外加入，所以总迁入数不是严格人口百分比。

WorldBox `CityManager.cs:12-32` 的 newCity 会同时吞并核心周边未归属 zones；新城实际面积可能不止选出的 cut 集合。

## Storage Ordering and Conservation

`TransferResources` 使用源 `storages` 的 snapshot；`Building.takeResource` 返回资源变更后的余额（WorldBox `Building.cs:1517-1520`），取 before-after 的写法与 API 匹配。问题在于目标容器与消费补丁：

- mod 的 `updateDirtyBuildings` 在转移资源之后。原版 `City.listBuilding` 才建立 stockpiles/storages 列表（`City.cs:360-370`）；`City.addResourcesToRandomStockpile` 在找不到 stockpile 时返回 0（`:2883-2891`）。生成 stockpile 对列表的即时可见性需要结合 BuildingManager 路径核查，不能仅凭“创建了仓库”保证可存。
- cut zones 已移动，而源 storages 列表尚未显式重建；其中可能仍包括建筑实际已归新 City 的仓库，混淆真正的源剩余库存。
- `taken` 已被扣除，目标 `addResourcesToRandomStockpile` 返回值未检查、无补偿；无仓库/放置失败的分支存在资源丢失风险。
- 目标入库又执行同一 mod 的小麦 ×2 / fish ×3 与累计 wheat Prefix。可达条件成立时搬运产生额外资源与进度，不能保证守恒。证据：`Code/FeudalPartitionService.cs:752-812,922-957`；`Code/CivilizationTraitExpansionPatches.cs:358-377`。

前两项是顺序与 runtime 列表可见性的静态风险；后两项是代码缺少回执处理与共用入库入口的已确认事实，具体资源损失规模尚未实机复现。

## Logs and Persistence

两条日志 `log_feudal_partition_first` / `log_feudal_partition` 注册到 `kings` 组，共用 trait icon，text_replacer 优先用 special1；消息带 Kingdom/color 与新城位置。`PostPartitionLog` 不检查 `CivilTraitExpLog` debug 开关，开关只控制 Debug.Log。README 的“随模组日志开关控制”不能等同于 WorldLog 也被关闭。证据：`Code/FeudalPartitionService.cs:186-240,967-994`；`Code/CivilTraitExpLog.cs:23-48`。

`feudal_partition` 位于 Culture miscellaneous；`feudal_partition_kingdom` 位于 Kingdom fate，关闭 needs_to_be_explored 并允许 editor given/removed。冷却存在 KingdomData `cte_last_partition_time`，没有独立 sidecar。证据：`Code/FeudalPartitionService.cs:145-176,508-516,806`。

## Failure Boundaries and Reuse

- 执行 catch 返回 false，但之前的 newCity/addZone/joinCity/扣资源没有回滚。重建列表的内部 catch 仅 warning，仍继续日志并返回 true。
- `_lastTickMonth` 为跨世界 static marker，无 load/exit reset；同月切图会暂时跳过；有中间月份跳跃不补次数。
- 全世界单位筛选、反复 CountCityArea 排序与全城建筑列表重建无工作预算；大地图开销未知。
- README 自述曾实机修复亲子枚举，不是本次验收证据；AW3 联玩、save/load、新城 AI、pathfinding 和继承行为都未复测。

Related pattern IDs: `persistent-mod-data`, `world-tick-integration`。parent ID、before-after 余额核算与用 `City.addZone` 更新归属可参考；完整分封流程保留为 `candidate:city-zone-partition`，必须先验证库存可见性、守恒、连通与失败恢复再晋升。

待验收最小场景：仅首都；有两块非首都；子嗣跨 Family/另国/无 City；候选数等于 City 数；战争中；36 个月边界；建 stockpile 失败；源仓库落在 cut 集合；wheat/fish 带倍率；执行中途异常；完整 world save/load。以上均未声称已通过。
