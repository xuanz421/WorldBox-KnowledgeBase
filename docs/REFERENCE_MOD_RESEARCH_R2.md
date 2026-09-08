# Reference Mod Research R2

Batch R2-0（inventory，无机制研究）。产出日期：2026-09-08。
基线：catalog 21 mods / registry 21 条 / system-matrix 21 mods，全部一致。

## Current Baseline

当前正式 21 mods（`knowledge/reference-mods/catalog.json`，Tier A9/B8/C4）。
覆盖缺口（见 CROSS_MOD_SUMMARY）：Economy/Resources(0)、Jobs/Professions(0)、Culture/Religion 创建(浅)、Boats(0)、Books/Items/Crafting(几乎空白)、性能(仅 optime)。

## New / Changed Sources

比对：`python -m wbkb discover`（无 --force）→ NEW=3, CHANGED=1(worldbox 检测), UNCHANGED=23；MISSING=0。

| Source | State | Domain | Scale | Value | Suggested Batch |
|---|---|---|---|---|---|
| ref:boatrebalancebox — BoatRebalanceBox 1.2.4（GGGG-G4X，GUID GX4BoatRebalanceBox） | NEW | Boats / Combat / World | S（8 .cs：根 1 + Content 7） | High — Boats 是显式空白，含武器/投射物/状态/无摇晃改造 | R2-1 |
| ref:biology — 生物学 1.0.7（信仰芙芙の博士） | NEW | Biology/Actor / UI | M（31 .cs，Code/ 平铺） | High — 器官健康/100+疾病库/家族追踪，全新领域无重复 | R2-2 |
| ref:economymod — 古典经济学 1.2.1fix（Jake，targetGameBuild 719） | NEW（源码缺失） | Economy / Resources / Trade | 未知（本地仅 EconomyMod.dll，0 个 .cs；UI/图标/4 语言资源齐全） | Medium — 补最大空白 Economy，但无源码，无法做 source 证据化 profile | R2-E（blocked，见 Unknown） |
| Cultiway-Reborn 修仙[重塑] v0.0.29（inmny，GUID CULTIWAY，master@641e92b2f12fe6be69c9d421641efb0110fc0e86，2026-09-06，工作树干净） | NEW（外部 git source） | Cultivation / Actor / Items-Crafting / Combat-Abilities / Sects-Social | XL（1643 .cs） | High — 唯一源码可得的大型修仙 mod，Items/Crafting/Jobs 缺口的主要候选 | R2-C0..C5 |
| worldbox | CHANGED（检测伪变更） | — | — | — | follow-up：版本探测复验（见 Unknown） |

SAME：其余 21 个既有 reference mods 全部 UNCHANGED（含 guigu/xuanmen/xuanjian 三个修仙 mod）。
MISSING：无。
Cultiway-Reborn 克隆位置：`E:\WorldBox Modding\ReferenceSources\Cultiway-Reborn`（WBKB repo 外部 source 区域，read-only 使用）。

## Coverage Impact

- **Boats**：0 → 1（BoatRebalanceBox，船只武器/平衡/状态）
- **Biology/Health/疾病**：0 → 1（Biology，器官-疾病-负面特质联动）
- **Economy/Resources/Trade**：0 → 1 潜力（EconomyMod：GDP/基尼/贸易网络/银行信贷——但需先解决源码来源）
- **Items/Crafting/Materials**：Cultiway Artifacts(77) + Crafting + Components(84) + Libraries(44)，显著补强
- **Jobs/Tasks/自主行为**：Cultiway Behaviours(94) + Core/ControlledTasks + Systems(59)
- **Cultivation 深度**：3 个既有修仙 mod 未更新；Cultiway-Reborn 提供更深、源码完整的体系（灵根→化神、宗门、炼丹炼器）
- **Climate/World**：本批**无**任何新 climate 来源 → R2-2 Climate 取消
- **性能工程**：Cultiway Core/Performance 可与 optime 互补（注意 mod.json 自述"无优化"）

## Batch Queue

| Batch | 对象 | 边界 |
|---|---|---|
| R2-1 Boats | BoatRebalanceBox | 8 文件全读；船只武器/投射物/状态机制；1 批完成 |
| R2-2 Biology | Biology_1.0.7 | 器官系统/疾病库/健康模拟/UI tab；31 文件按簇分 2-3 批。B0/B1 已完成 → [biology profile](../knowledge/reference-mods/mods/biology.md)（2026-09-08 入正式 catalog，`ref:biology`），余 B2 |
| R2-E Economy | EconomyMod | **blocked**：先决定源码获取（作者源/GitHub）或 ilspycmd 反编译路线；未解决前不启动 |
| R2-C0..C5 | Cultiway-Reborn | 见下节拆分；每子批 1 核心机制或 2-4 文件簇 |
| R2-5 Cultivation Delta | （取消） | 旧修仙 mod 均 UNCHANGED，无 delta 可研究 |
| R2-6 Cross-Mod Synthesis | 全部 R2 新 profile | 最后执行；更新 CROSS_MOD_SUMMARY / gaps |

推荐第一个正式批次：**R2-1 BoatRebalanceBox**（S 规模、零重复、直接补显式空白，可单批收口）。

## Cultiway-Reborn Split

源码分布：Source/Core(523) + Source/Content(800) + Source/UI(161) + Source/Patch(37) + Abstract(21) + Utils(46) + Const/LocaleKeys/Debug/Tables(31) + 根级其余。

| Sub-batch | 范围（按实际目录） | 文件簇规模 |
|---|---|---|
| R2-C0 Architecture Baseline | mod 生命周期、Cultiway.csproj/Assemblies 装配、Core（EventSystem/Persistence/Coordination/Performance/Logging/Localization/Systems）、Patch 组织、module 边界与注册策略 | 只画架构，不深入玩法 |
| R2-C1 Actor / Cultivation Core | Core/Progression、Content/Attributes、ActorComponents、CreatureCompositions(31)、Yao(21)；cultivation state/境界/Actor 组件 | ~54+ 文件簇 |
| R2-C2 Materials / Items / Crafting | Content/Crafting、Artifacts(77)、Components(84 部分)、Libraries(44 部分)、SpiritVeins(28)；材料框架/丹药/炼器/物品集成 | ~150 文件簇，需再拆 2-3 批 |
| R2-C3 Jobs / Tasks / Autonomous Behaviour | Content/Behaviours(94)、Systems(59)、Core/ControlledTasks、Coordination；自主炼制/服用/学习与原版 ActorJob 边界 | ~160 文件簇，需再拆 |
| R2-C4 Abilities / Combat | Content/ActiveAbilities、Magic(11)、Combat、KnightCombat(18)、WeaponControl、Core/SkillLibV3；法术框架/自动释放/战斗集成 | ~48 文件簇 |
| R2-C5 Social Systems | Content/Sects(23)、Events(9)、CollectiveProjects(6)、SubWorlds(5)；宗门/传承/文明层 | ~43 文件簇 |

约束：禁止一次处理 C0-C5；C2/C3 内部还需按文件簇二次拆分。注意 README 自述"预览版，存档无效，无优化"——持久化研究须标注该限制。

## Unknown

- **EconomyMod 源码不可得**：本地仅 DLL（无 .cs、无 git）；mod.json 标 `targetGameBuild: 719`（与当前 game build 19962337 的关系待确认）；作者源仓库未知。研究路线（获取源码 vs ilspycmd 反编译）未定。
- **worldbox 版本探测降级**：registry 由 `0.51.2 verified:local-metadata` 变为 `null unknown`，但 assembly sha256（51d275f0…）与 steam buildid（19962337）完全未变 → 游戏**未更新**，是探测元数据问题（可能本地元数据文件被移动/改名，或与 OWL 启动器有关）。manifest 按 discover 机制原样接受，未手工干预；需后续单独复验。
- **Biology/BoatRebalanceBox/EconomyMod 无 git**：版本身份仅来自 mod.json，无法做 commit 级追踪。
- **Cultiway-Reborn 内容边界**：AIGC(9)/Semantics(6)/Core/AIGCLib 等 AI 相关目录用途未确认；Doc/、Prompts/ 目录内容未读——归入 C0 时再确认。
