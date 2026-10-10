---
title: Culture research state and cold-cache repricing
aliases:
  - CultureData research persistence
  - 文化研究状态与设置重算
---

# Pattern: culture-research-state

## Status

Verified — WorldBox 0.51.2 / NewEra 1.0.0。源码与既有实机报告核对于 2026-10-10；本次知识整理没有重新运行游戏。

## Goal

用 `CultureData` 保存文化研究状态，以可丢弃 runtime cache 支持年度结算、前置判定和设置变化后的即时重算。

## When to Use

文化掌握节点、积累研究经验、维护当前研究槽；更改成本设置后须覆盖尚未访问、没有 runtime cache 的文化。不要为这些小量 per-culture 值额外引入 ECS 或数据库。

## Relevant Systems

Culture, Save/Persistence, Research, Settings, Mod Lifecycle

## Implementation Flow

1. 持久值写入带 mod prefix 的 `culture.data.get/set` 键：XP、slot ID、slot cost snapshot、owned node IDs。`BaseSystemData` 容器懒创建；直接索引 `custom_data_float/string` 可能读到 null。
2. runtime extension 从 `CultureData` 恢复；cache 只负责查找和计算，不成为另一份权威存档。世界开始、读档与退出时清掉 cache 和年度标记。
3. 年度处理先记录当前年；首次进入世界只设置标记，不补发一年收益。设置变化走独立 settlement 路径，不重复年度 XP、不为原本空槽抽新节点。
4. 节点获取拆成 `Research / InitialGrant / EraGrant / ConditionGrant`；研究池只收 `Research`，自动授予用集合 `Add` 保证幂等。尚未开放的 mastery 获取入口明确封闭。
5. 前置声明与解析结果数量不一致、未知 ID 或自引用时阻止研究。不能把“解析失败后数组变短”当成前置满足；槽内节点也要重新检查资格。循环另在初始化时诊断输出；当前代码没有独立 quarantine 标记，闭环通常因缺少已拥有前置而无法起步，不应声称强制授予后也必然拒绝。
6. 成本同时用于候选权重、结算和 UI；在最终 multiplier 与取整后限制至少 1 XP。只在中间式 clamp 仍可能被最终取整变成零成本。
7. 设置 Apply 遍历实际 `World.world.cultures.list`，通过 `GetExtend()` 恢复无缓存文化，再重算 active slot、`SaveToData()`、触发 settlement 并保存配置。只用 `TryGetExtend()` 会漏掉冷 cache。
8. NewEra 的抽样是先等概率无放回选最多 6 个候选，再按 `pool_weight * minimumCost / cost` 抽取；输出的是 shortlist 条件概率，不能宣称全池无条件概率。候选数与权重属于消费者设计参数。

## Reference Implementations

- `consumer:NewEra@fe2d2c88320e8a3d6544b2f5b2f0b3bf88c645ef`：`Source/Core/CultureExtend.cs:49`、`Source/Core/CultureExtendManager.cs:10`、`Source/Content/EraSettings.cs:35`。
- 原版 `CultureData.cs:8` 继承 `MetaObjectData`；键值 API 实际由 `BaseSystemData.cs:262`、`:302` 等提供。
- Related pattern IDs: `persistent-mod-data`, `world-tick-integration`, `culture-consumption-gates`。

## Regression Checks

| Trigger | Required invariant |
| --- | --- |
| cache 清空后 Apply | 已保存 slot 被重新计价并再次持久化 |
| 成本提高 / 降低 | 提高不误结算；降低后可结算；不重复年度 XP |
| 合法最低设置 | 零 XP 不完成；1 XP 可完成最低成本节点 |
| 空研究槽 | Apply 不抽新节点 |
| 无效前置 | pool 与 active slot 均拒绝 |
| 世界存读档 | owned IDs、XP、slot 和成本保持；首次年度不补发 |

## Caveats

- extension 构造会执行 automatic grants reconciliation；调用它并非完全无副作用的读取。需有存读档与重复授予测试。
- 不把 NewEra 的删除未知节点行为解释为通用旧存档 migration；该版要求首次体验新建世界。
- `ConcurrentDictionary` 只证明 cache 容器类型，不证明 Unity / WorldBox 对象可在后台线程访问。
- 人口公式、时代成本与候选偏好是具体模组平衡方案；120 年受控长局不证明自然世界长期平衡或所有模组组合兼容。

## Evidence

- WorldBox snapshot `worldbox-0.51.2-51d275f0168b`: `CultureData.cs:8`, `BaseSystemData.cs:262`, `BaseSystemData.cs:322`。
- NewEra: `Source/Core/CultureExtend.cs:49`, `:94`; `Source/ModClass.cs:46`, `:56`; `Source/Content/Systems/EraYearlySystem.cs:37`, `:69`, `:178`。
- NewEra: `Source/Content/Libraries/EraNodeLibrary.cs:440`; `Source/Content/Assets/EraNode.cs:98`; `Source/Content/Research/EraNodePool.cs:28`; `Source/Content/Research/EraCost.cs:77`。
- NewEra `Tests/CultureNodeValidation.cs:97-111`: invalid prerequisites、minimum effective cost、cold-cache repricing。
- 既有隔离报告 `bin/culture-node-b825007be2424a8daf66d1fa573c70a9.tsv`: 124 PASS / 0 FAIL，SHA256 `C10775296AE112F780BE34DBF07B128F30621AB8BBCC1844D72F5D12F2217FEC`。
- 冷 cache 修复前 `bin/culture-node-73149cb83b7a4ca69415afa7f865d254.tsv`: 123 PASS / 1 FAIL；不是凭复测通过推断旧失败原因。

## Provenance

来源仓库 `https://github.com/xuanz421/NewEra`，上述 consumer commit 固定源码版本；验收来源 `Doc/第一计划/第四阶段验收记录.md` 与 `Doc/第一计划/验收证据/最新隔离回归报告.tsv`。消费者项目只作为此次用户授权的经验输入，不加入 WBKB source discovery 或 Reference Mod catalog。
