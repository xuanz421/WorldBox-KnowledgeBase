---
title: 城市建筑与经济
---

# 城市建筑与经济

## Scope and Status

`ref:civilization-trait-expansion` v1.5.0；Mostly Verified（静态源码 + WorldBox snapshot 核对，无本次实机运行）。下列 `Service` / `Patches` 分别指 `Code/CivilizationTraitExpansionService.cs` / `Code/CivilizationTraitExpansionPatches.cs`；证据路径仍保留完整文件名。

## Trait Definitions and Ownership

| ID | 类型 / group | 实际效果或前置 |
| --- | --- | --- |
| `windmill_lovers` | Culture / buildings | 风车原版上限加 `CultureTraitLibrary.getValue`（新注册 value=1） |
| `larger_farms` | Culture / buildings | 距离半径 13（原版常量 9） |
| `bigger_homes` | Culture / knowledge | 完工、有 housing slots 的建筑，按正 upgrade_level 补住房 |
| `tower_expansion` | Culture / buildings | 上限 25；人口 ≥500 自动授予所属 Culture |
| `masterful_craftsmanship` | Culture / knowledge | 成功锻造复制一件；按 original value 向库存追加 gold |
| `more_mines` | Culture / buildings | 矿洞上限 3 |
| `efficient_farming` | Culture / buildings | 显示名「农耕传统」，仅是国家解锁前置 |
| `kingdom_efficient_farming` | Kingdom / fate | 小麦入库 ×2；解锁后代码不自动回收 |
| `improved_craftsmanship` | Culture / knowledge | 渔获入库 ×3 |

注册按 `library.has` 去重；遇到同 ID 旧 asset 不刷新它。所有 icon path 非空，部分使用原版资源。证据：`Code/CivilizationTraitExpansionService.cs:423-602`；显示名与农业描述：同文件 `:300-306`。

`OnCultureCreated` 在 creator / asset 非空时为所有新文化授予 `bigger_homes`；human 加 `windmill_lovers/larger_farms`；dwarf 加 `more_mines/masterful_craftsmanship`；human/elf/dwarf 加 `efficient_farming`；orc 加 `improved_craftsmanship`。所有种族另进行一次 0.33 的 `civ_imperial_administration` roll。没有读取旧存档文化后补发的实现。证据：`Code/CivilizationTraitExpansionService.cs:1253-1328`。

## Multiple Windmills and Farm Collections

上限用 Postfix 保留原结果后加 1；并不无条件固定为 2。`GetUsableWindmills` 按 type、完工/可用、free tile、island 筛选；只有多个风车且 Culture 有 `windmill_lovers` 才替换 `getBuildingOfType`。证据：`Code/CivilizationTraitExpansionPatches.cs:15-47,75-98`、`Code/CivilizationTraitExpansionService.cs:935-969`。

`CityBehCheckFarms.check` 遇到多风车或大农田则改走 `RunFarmCheck`：清空 place/field/crop/grown 四个集合，逐风车扫描自身 MapRegion 及 neighbours 的 chunk.zones，限制同城与 squared distance ≤81/169；根据 can_be_farm / farm_field / wheat 分类，再执行 `checkAddRemove` 与成熟 wheat 筛选。遇到多个风车但仅有 larger_farms 也会处理传入集合中的所有风车。证据：`Code/CivilizationTraitExpansionPatches.cs:115-142`、`Code/CivilizationTraitExpansionService.cs:981-1060`。

**确定性边界错误**：风车索引使用 `Randy.randomInt(0, windmills.Count - 1)`（`Code/CivilizationTraitExpansionPatches.cs:97`）。WorldBox `Randy.cs:81-83` 的上界为 exclusive，两个风车时恒选 index 0，多个时最后一项不可选；不是均匀使用两个风车。推广时应采用集合 Count 作为上界。

## Housing and Tower Construction

住房在 `City.updateCityStatus` 原版完成后，加入 `GetBiggerHomesBonus` 的 upgrade_level 总和，重算 housing_occupied/free。过滤 under-construction、null asset 与无 housing slots；不专门限制建筑 type 为 house，也不把 level clamp 到 5。人口恰好 500 已会解锁哨塔，README 的“突破 500”不够精确。证据：`Code/CivilizationTraitExpansionPatches.cs:200-228`、`Code/CivilizationTraitExpansionService.cs:1072-1138`。

哨塔成本由已有数量（包括在建）决定下一座倍率：0–3 →×1、4–18 →×2、≥19 →×4。Prefix 用 scaled wood/stone/common_metals/gold 预检，不足则 `__result=null; return false`；够则让原版按原价建造；Postfix 仅在 Building result 非空时补扣差额。证据：`Code/CivilizationTraitExpansionService.cs:1103-1113`、`Code/CivilizationTraitExpansionPatches.cs:249-318`。

**静态风险**：`_pendingExtraCost` 是全局 static 调用状态，嵌套/重入或其他 patch 改变原版扣费路径时可能失配；没有 Harmony per-call state、扣费回滚或 Finalizer。异常 catch 选择放行原版，不能保证异常路径仍保持放大成本。此风险未实机复现。

## Craft Duplication

成功 `craftItem` 的 Postfix 调 `OnBlacksmithCraftSuccess`，读取铁匠相应 equipment slot 的成品；原版 `ItemCrafting.cs:81-102` 确认新 Item 已换入该 slot。mod 用 `World.world.items.newItem` 创建副本，复制 modifiers/material/by/from/color/durability/name，调用 `calculateValues`；不复制完整 ItemData 或 ID，不能保证任意第三方自定义 ItemData 字段也继承。证据：`Code/CivilizationTraitExpansionPatches.cs:334-341`、`Code/CivilizationTraitExpansionService.cs:1153-1246`。

复制品仅在 CityEquipment 对应类型 Count < maximum_items 时加入；gold 奖励在容量不足时仍尝试发放。`_inCraftCopy` 由 finally 还原。**静态风险**：副本在容量检查前就创建，满库存分支没有销毁副本；gold 通过 stockpile 入库，不是直接修改 Kingdom treasury，无可用 stockpile 时原版返回 0。证据：`Code/CivilizationTraitExpansionService.cs:1181-1205`；WorldBox `City.cs:2883-2891`。

## Farming Progression and Storage Multipliers

`Building.addResources` Prefix 保存 rawAmount → 正数按目标 Building 所属 City 的 Kingdom/Culture 放大 → 正数 wheat 的 rawAmount 累加到 KingdomData `cte_wheat_total` → 原版执行实际存入。小麦查 `kingdom_efficient_farming`，渔获查 City Culture 的 `improved_craftsmanship`；其他资源 ×1。证据：`Code/CivilizationTraitExpansionPatches.cs:358-385`、`Code/CivilizationTraitExpansionService.cs:683-752`。

月度检查以 `year*12+month` 去重、暂停时返回。存活文明王国、有当前 Culture 的 `efficient_farming`、有 City、累计 wheat ≥ `2500 * countCities()` 才授予 `kingdom_efficient_farming` 并发 `kingdoms` WorldLog。已拥有则直接返回，没有随文化易主自动回收；trait asset 仍设置 can_be_removed=true，所以“永久”仅指没有自动清理，不等于玩家不可删除。证据：`Code/CivilizationTraitExpansionService.cs:773-931,586-600`。

**已确认的入口语义**：它累计的是全部正 wheat `addResources` 调用参数，发生在实际入库前，不是专用 harvest 事件。分封搬运也调用 `City.addResourcesToRandomStockpile`，最终到 `Building.addResources`（WorldBox `City.cs:2883-2891`）；因此搬运会再次累计且可能再次 ×2，fish 同样可能再次 ×3。函数返回值、容量与实际增量没有反馈给计数；资源计量和转移守恒不能按 README 的“实际收获量”保证。证据：`Code/FeudalPartitionService.cs:952-957`、`Code/CivilizationTraitExpansionPatches.cs:362-377`。

其他待验证：int 累计溢出、城市数量变化导致门槛下降/上升、同月切世界或读档造成 static month marker 跳过一次检查、月份快进只执行一次而不补历史月份。当前代码没有 world-load/exit marker reset。

## Compatibility and Documentation Differences

- 建筑重建 Prefix **全局**替代原版，并非检测 AW3 后才启用；跳过 null Building/null asset 的防御经对照 `CityManager.cs:119-139` 确认。AW3 是否是坏建筑来源、实际联玩是否修复，只有包内自述。证据：`Code/CivilizationTraitExpansionPatches.cs:152-186`。
- README/mod.json 把 `efficient_farming` 说成直接小麦 ×2；代码已改成 Culture 前置 + Kingdom trait，不应据旧描述接入。
- README 中“高效农耕不默认授予”和“human/elf/dwarf 默认授予”互相冲突；代码确定默认授予的是 `efficient_farming` 前置。
- README “每栋房屋 1–5”只是常见原版等级描述，不是 mod 的硬范围。

## Reuse and Verification Boundary

Related pattern IDs: `culture-consumption-gates`, `safe-asset-registration`, `clone-modify-asset`。可借鉴消费点归属判定、原版结果增量与 asset 去重；不要复制 randomInt 上界、全局调用状态或“任意入库=产量”的假设。

未来实机验收应覆盖两风车均被访问、哨塔第 4/5/19/20 座边界、住房反复重算、锻造库存已满、真实 harvest 与资源搬运区别、分封前后各资源总量、文化易主及存读档。这里是待验收范围，不是已通过的测试报告。
