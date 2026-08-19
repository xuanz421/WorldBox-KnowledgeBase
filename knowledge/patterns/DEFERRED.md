# Deferred / Rejected Candidates

Z5 的 56 个 candidate 中未晋升为 Pattern 的部分。简洁记录理由，不做深度分析。

## Deferred（证据在但暂不提炼）

| Candidate | Reason |
|---|---|
| transpiler-literal-replace + transpiler-stat-injection（合并） | 证据强（chinesename/xuanmen/guigu），但 IL Transpiler 高风险高门槛，适用面窄——待有第二个强需求场景再提炼独立 pattern |
| runtime-decision-injection（custom-actor-behavior） | creepmobboost 单一实现；BehaviourTaskActor/DecisionAsset 注入很有价值但仅一样本，且 Jobs/Professions 系统上下文不足 |
| worldlog-asset-text-replacer | 仅 xavii 使用；WorldLogAsset 面向事件日志，适用面中等 |
| map-snapshot-stamp + smoothloader-generation-chain（合并） | mapdeal 单一样本且为 NCMS 旧式；价值高但版本耦合深（targetGameBuild 523），提炼需先确认当前版本管线 |
| reverse-erosion-regrow / custom-world-law-option | worldresilience 单一实现；custom-world-law-option 可作为 persistent-mod-data 的附录证据 |
| locale-hot-reload + localizedtext-refresh-postfix（合并） | 两个 mod 实现一致且简单——更适合作为 localization 小抄而非独立 pattern（额度原因暂缓） |
| dictionary-toggle-settings-center / frame-rate-adaptive-sim / feature-toggle-framework | optime 框架已并入 harmony-safe-batch-patching 的卸载式路线；独立 pattern 价值边际 |
| ugui-pan-zoom-overlay | familytree 单一样本，纯 Unity UGUI 技能与 WorldBox 无关 |
| death-protection-prefix-chain / immunity-prefix-veto-suite | 已并入 harmony-prefix-recipes 的 replace/veto 式证据 |

## Rejected

| Candidate | Reason |
|---|---|
| gameprogress-debug-unlock | 单行官方后门调用，无模式价值（保留为 clone-modify-asset 的 caveat 级证据） |
| world-law-default-flip | 同上——单字段翻转，已并入 clone-modify-asset |
