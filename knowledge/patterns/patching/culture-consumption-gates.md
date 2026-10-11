---
title: Culture capability gates at native consumption points
aliases:
  - 文化许可与原版消费条件
  - CityBehBuild knowledge gating
---

# Pattern: culture-consumption-gates

## Status

Verified — WorldBox 0.51.2 / NewEra 1.0.0。直接消费点、文化归属与完整世界重载有既有受控实机证据；自然 AI 全循环并未全部验证。

## Goal

把文化知识接入建筑、升级、装备和书籍的实际消费点，同时保留原版资源、地形、人口、金币和建造前置条件。

## When to Use

技术已经注册、授予和显示，但还需要证明原版行为确实消耗该许可；尤其是多个 City 共享 Culture、City 易主后 Culture 又变化的场景。

## Relevant Systems

Culture, Buildings, Items, City, Kingdom, Books, Patching

## Implementation Flow

1. 先查原版实际调用链，再区分“取得资格”“进入候选”“尝试执行”“完成效果”。仅调用 getter 或直接往集合加 ID 不能证明消费链接入。
2. 建造门禁：在 `CityBehBuild.canUseBuildAsset` Prefix 拒绝缺失许可；有许可时返回 true 继续原版。升级另经 `CityBehBuild.upgradeBuilding`，必须同时覆盖已有建筑升级入口。
3. 装备门禁：`ItemCrafting.hasEnoughResourcesToCraft` Postfix 仅在原版 `__result == true` 时再检查文化知识；不能把资源不足的 false 改成 true。
4. 门禁基于执行时的 `city.culture` / `actor.culture`，不根据 Kingdom 名称或长期缓存的归属判断。同一文化可跨国家；易主并不等于文化立即切换。
5. 效果接管到原版消费点后，避免原 CultureTrait 与新节点同时加成。完整替换方法体时逐项保留无关原版效果；NewEra 阅读接管仍调用幸福、XP 和 mana 消费。
6. 书籍产出奖励只在 `BookManager.generateNewBook` 返回实际非空 Book 后发放；年度累计存在 CultureData，以共享文化年度上限约束多个作者和城市。
7. 原版 AI fixture 的建筑占地、领土 zone、废墟索引、库存与领袖身份必须真实成立。先找最早无效的原版状态，不能通过生产代码放宽条件把夹具误判掩盖掉。

## Effect Ownership and Asset Retirement

- 迁走 CultureTrait 后，除了 `library.list/dict`，还要处理随机授予池、`_array` cache、opposites、Actor 默认特质、biome spawn 特质和 achievement unlock references。只删注册项不能证明其他来源不再授予。
- NewEra `CultureNodeEffects.RetireNativeTraits()` 在实际消费点接管后清理这组入口；`Culture.save` 保存 ownership 并移除已接管的 `saved_traits`，`Culture.recalcBaseStats` Postfix 重放已掌握节点。不要给用户旧开发存档迁移作额外保证。
- 效果归属可能不同：农业许可实际使用 `actor.city.culture`，军训使用 `actor.culture`。城市劳动产出和角色个人成长不能默认共用一种文化判断。
- 农业额外 wheat 加到 `Actor` inventory，由原版后续运送处理；风车增益还需要升级风车、真实 harvest target 和距离条件。直接改 City storage 不能替代验证这条链。

## Reference Implementations

- `consumer:NewEra@fe2d2c88320e8a3d6544b2f5b2f0b3bf88c645ef`: `Source/Content/Buildings/PatchBuildingKnowledge.cs:8`、`:20`。
- 同 consumer: `Source/Content/Paths/Metallurgy/PatchEquipmentKnowledge.cs:7`; `Source/Content/Paths/Knowledge/PatchBooks.cs:10`, `:34`。
- `ref:civilization-trait-expansion` v1.5.0：`Code/CivilizationTraitExpansionPatches.cs:15-47,200-228,358-377`；建筑上限、住房、资源入库分别是独立消费点。它扩展 CultureTrait，不是 NewEra 的 asset retirement 实现。
- Related pattern IDs: `harmony-prefix-recipes`, `culture-research-state`, `actor-annual-persistent-stat-growth`。

## Regression Checks

- 对照同一地形、人口、库存、资产和随机种子：无节点拒绝；授予节点后原版消费成功；去掉节点再次拒绝。
- 即使有节点，原版资源或地形不足仍拒绝；原有“不受本 mod 管理”的资产保持既有行为。
- 测试建造与升级两个入口，不只查询 BuildOrder 是否可用。
- 使用真实多个 City、真实易主，再明确切换 Culture；检查文化许可不随 Kingdom 错误外溢。
- 完整 world save/load 后逐节点校验状态，再回到原版消费路径。对象内 JSON round-trip 不能替代完整世界重载。

## Caveats

- NewEra 对 `city.culture == null` 的资产门禁沿用原版行为；这是本实现的确定行为，不是通用“所有无文化单位都应拒绝”的政策。
- `BookManager.generateNewBook` 门禁不代表写书计划的开始、继续、完成均已接管。NewEra 1.0 将该完整链明确留到第二计划。
- 受控直接调用、自然 AI 样本、世界重载和 UI 截图分别说明不同边界；不能把一种证据当成另一种。
- 历史住宅升级、农田／风车及原版攻占空引用有间歇性失败。后续通过不意味着所有未知根因都已修复。
- 年度 health 增益重放的是最大属性；不自动代表原版当前 `data.health` 被立刻补满或原版重算行为被修改。
- 效果持有者须与消费点匹配：文明特质拓展的小麦倍率使用 `city.kingdom` 的 `kingdom_efficient_farming`，渔获倍率使用 `city.culture` 的 `improved_craftsmanship`。同一入库入口也承担搬运，不能未经 harvest 证据将全部正入库计作生产；分封搬运会再次触发倍率与计数。

## Evidence

- NewEra `Source/Content/Buildings/BuildingKnowledge.cs:8`, `:35`, `:42`; `Source/Content/Paths/Metallurgy/EquipmentKnowledge.cs:8`。
- NewEra `Source/Content/Paths/Knowledge/PatchBooks.cs:10`, `:34`; `Source/Content/Paths/Knowledge/BookKnowledge.cs:25`。
- NewEra `Source/Content/Paths/Culture/CultureNodeEffects.cs:67`; `Source/Content/Paths/Culture/PatchCultureNodes.cs:6`; `Source/Content/Paths/Agriculture/AgricultureEffects.cs:12`; `Source/Content/Paths/Agriculture/PatchAgricultureHarvest.cs:12`。
- 文明特质拓展 `Code/CivilizationTraitExpansionService.cs:683-752,830-866`；`Code/FeudalPartitionService.cs:952-957`；WorldBox snapshot `worldbox-0.51.2-51d275f0168b` 的 `City.cs:2883-2891`。2026-10-11 静态核对，确认效果归属与共享入库路径；不新增实机通过声明。
- 既有最后全绿完整基准 `bin/acceptance-6d25cebba77e4c3c895fdbbf5ed191cb.tsv`: 1376 PASS / 42 INFO / 0 FAIL，SHA256 `40654F825B473168AE440ACA91FDE077792A4E1968162A0875BA64FE98919781`。包括普通节点研究、六级住宅升级、装备制造、共享文化、易主与文化切换、完整世界存读档。
- 此后完整审查 `bin/acceptance-91146bd634d046849f72f5e1db2bc555.tsv`: 1380 PASS / 37 INFO / 1 FAIL；营火英文截图完成时 tooltip inactive。该次不能取代全绿完整基准，也不宣称失败根因已关闭。

## Provenance

消费者证据固定在 NewEra 上述 commit；来源仓库 `https://github.com/xuanz421/NewEra`，原始台账 `Doc/第一计划/第四阶段验收记录.md`。这是可复用接入方法，不导入消费者的节点平衡或玩法规划。

Additional reference: `ref:civilization-trait-expansion`，用户提供 v1.5.0 zip；仅补充消费点归属与入库反例，不改变 NewEra 验收结论。
