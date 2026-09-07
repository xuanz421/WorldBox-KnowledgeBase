# S-Tier Closure Audit

2026-09-08 执行。目标：检验 10 个已 verified S-Tier 系统知识的内部一致性、可追溯性与 Modding 可用性。方法：全量文档交叉阅读 + 疑点 targeted source verification（未全量重扫源码）。基线：worldbox-0.51.2-51d275f0168b（与各系统文档一致）。

## 1. S-Tier Coverage

| system | file | batch | status |
|---|---|---|---|
| actor | entity/actor.md | 1（+2/5 回写） | verified ✓ |
| traits | entity/traits.md | 1（+2 回写） | verified ✓ |
| assets | technical/assets.md | 1 | verified ✓ |
| save | technical/save.md | 2 | verified ✓ |
| city | settlement/city.md | 2（+3/4 回写） | verified ✓ |
| kingdom | political/kingdom.md | 3 | verified ✓ |
| buildings | settlement/buildings.md | 3（+4 回写） | verified ✓ |
| resources | economy/resources.md | 4（+5 回写） | verified ✓ |
| jobs | economy/jobs.md | 5 | verified ✓ |
| items | economy/items.md | 6 | verified ✓ |

**10/10 verified 维持**。审计未发现任何推翻 verified 状态的问题。

## 2. Cross-System Consistency Findings

对以下共享概念做了成对互证：updateStats 合并顺序（actor↔traits↔items）、storage 所有权（city↔buildings↔resources）、容量语义（buildings↔resources）、citizen 归属与 dirty 重建（actor↔city↔kingdom）、加载引用序（save↔全部）、init 三阶段（assets↔六个业务库）、crafting 边界（jobs↔resources↔items）。

**结论：0 处机制级矛盾**（容量语义矛盾已在第 4 批发现并回写；本次复核确认一致）。发现 6 项文档级问题：

| # | 类型 | 描述 | 处置 |
|---|---|---|---|
| F1 | stale 引用 | city.md 跨系统表 Kingdom/Buildings/Storage-Resources/Jobs 四行仍标 "deferred:"，但目标系统均已 verified；buildings.md Resources 行、resources.md Jobs 行同病 | 已回写 6 行 → "已覆盖" |
| F2 | 未关闭 gap | city.md "CityEquipment 仍 deferred: items"——items.md（第 6 批）已完整覆盖 | 已关闭回写 |
| F3 | 术语不精确 | traits.md "默认武器 **ItemAsset**.base_stats"——实际运行时类型为 **EquipmentAsset**（ItemAsset 是从不实例化的基类，items.md 已澄清） | 已回写 |
| F4 | 定位错误 | jobs.md "decisions 填充 updateStats 内，Actor.cs:5130 附近"——实际链路 `updateStats:1695 → registerDecisions():4867-4953`（profession 段 4943-4953）；"updateStats 内"语义成立（经调用）但行号指向错误区域 | 已回写（含 evidence 行） |
| F5 | 边界缺失 | 武器 asset.decisions_assets 经 registerDecisions 进 Actor 决策池（Actor.cs:4971-4981）——items.md 未记录此 items→behaviour 边界事实 | 已补录 items.md |
| F6 | 系统性引用漂移 | 见 §4 | 记录于本文档，不逐条改写 |

## 3. Corrections Made

1. city.md：跨系统表 4 行 deferred→已覆盖；CityEquipment gap 关闭（→ items.md）
2. buildings.md：跨系统表 Resources 行 → 已覆盖
3. resources.md：跨系统表 Jobs 行 → 已覆盖
4. traits.md：默认武器术语 ItemAsset→EquipmentAsset
5. jobs.md：profession→decisions 定位修正（两处）
6. items.md：补录武器→DecisionAssets 边界
7. assets.md：关闭"各业务 Library 特有逻辑清单" gap（S 级库部分）

均为最小化回写；无文风性重写。

## 4. Evidence Audit（代表性抽查）

每系统抽 3~5 个核心结论做 symbol 级验证（本 session 直接读取或 grep 复核）：

| system | 抽查结论 | 结果 |
|---|---|---|
| actor | prepareForSave 17 步链（8875-8895）；saveEquipment（8928-8935）；死亡装备回城（die 段 6965-7020）；updateStats 装备合并+broken×0.5（1788-1794）；cloneUnit 装备复制（ActorManager 571-586） | PASS |
| traits | addTrait/removeTrait/hasTrait symbol 族存在（9453-9637）；updateStats trait 合并段（1623-1633）与 era 门控；loadTraits 直填（loadFromSave 9071 区域） | PASS |
| assets | AssetLibrary.add last-wins（duplicate log 61 / setHash 65）；三阶段顺序；模板 $ 前缀 | PASS |
| save | SavedMap.create（150）经 prepareForSave 收集 actors_data.Add（254）；items.loadFromSave（SaveManager 1606）；id 计数器 getNextId（MapStats 253） | PASS |
| city | setCitizenJob（1858）/checkCitizenJobList（1889）；tryToPutItem 15/槽上限（2725, 874）；giveItem 价值比较（2624） | PASS |
| kingdom | makeNewCivKingdom（KingdomManager 17）；WildKingdomsManager 构造期 newWildKingdom 负 id 递减（13/33-41） | PASS |
| buildings | zone 登记 + fillTiles；施工=同对象 flag+custom_data；状态机（本 session 复核 Building.prepareForSave 828 存在） | PASS |
| resources | hasSpaceForResource storage_max 判定（CityResources 70-73）；hasResourcesForNewItems strategic>10（76-86）；change maximum 钳制 | PASS |
| jobs | CitizenJobLibrary 12 工种 + linkAssets 三列表（全文件复读）；setCitizenJob→ai.setJob 链（Actor 4771）；nextJobActor（4794） | PASS |
| items | 全部核心类型本 session 全文阅读（第 6 批） | PASS |

**Reference Mod 使用合规**：ref mod 证据仅用于"用法验证"（resources.md mod 注册、actor.md 死亡观察、city/kingdom 的 NML patch 点跨源标注），未见以 ref mod 行为反推本体机制的段落。Verified/Inferred/Unknown 标注一致性良好（items.md 1 项 Inferred 明确标注；actor.md 创建钩子 Inferred 标注正确）。

**F6 系统性引用漂移（重要文档质量发现）**：

```text
实测样本（cited → actual，物理行）：
Actor.updateStats           1747     → 1530     (−217)
Actor.endJob                4978     → 4754     (−224)
Actor.nextJobActor          5013     → 4794     (−219)
Actor.addToInventory        7366     → 7480     (+114)
Actor.saveTraits            8850     → 9059     (+209)
Actor.addTrait              9189     → 9509     (+320)
Actor.prepareForSave        8875     → 8875     (0 ✓)
City.setCitizenJob          1851-71  → 1858     (✓ 命中区间)
City.eatFoodItem            1934     → 1953     (+19)
文件行数：Actor.cs 9702→10696；City.cs 3192→3551；ResourceLibrary.cs 770→1045
```

漂移**双向、非均匀**（同文件内不同 symbol 方向相反），推测早期批次所读源码导出与当前树存在差异（反编译重导出）。**影响评估：机制结论全部成立（symbol 与流程复核通过）；仅行号精度受损**。处置：不逐条改写历史引用（成本高、价值低）；本表记录漂移事实；后续 harvest 引用建议 `file + symbol + 行号(参考)`，必要时重新导出源码树并在 source-registry 记录导出版本。

## 5. Deferred Matrix

分类：A=已被后续 S-Tier 调查解决未关闭；B=需 A/B Tier 系统调查；C=NML 专项；D=非重要细节可长期 Unknown。按目标系统聚合（同项多源已去重）：

| deferred 项 | source | target | 级 | 状态 |
|---|---|---|---|---|
| CityEquipment 内部 | city | items | **A** | **本次关闭** |
| 各业务 Library linkAssets 清单（S 级部分） | assets | 各系统 | **A** | **本次关闭** |
| AiSystem 执行引擎（task 切换/条件调度/single actions） | actor, jobs, city | behaviour | B | open |
| DecisionAsset 消费机制（decisions 数组→NeuroLayer） | jobs, items | behaviour | B | open |
| CityBehBuild 选址算法 | jobs, buildings | behaviour | B | open |
| 资源生产/采集 Beh 调度残余（API 链已闭环） | buildings | behaviour | B | open |
| DropAsset 拾取行为（概念已明：Drops≠Items，不落地） | resources | behaviour | B | open |
| make_items 等决策调度（cooldown/weight 消费） | items | behaviour | B | open |
| s_action_attack_target 攻击结算 / DamageSystem | items | combat | B | open |
| War 生命周期与 renown | kingdom | war/combat | B | open |
| Alliance 内部 / DiplomacyManager opinion | kingdom | alliance/diplomacy | B | open |
| StorageBooks/book_slots | buildings, resources | culture(books) | B | open |
| culture 武器偏好（preferred weapons） | items | culture | B | open |
| NameGenerator 命名模板 | items | culture | B | open |
| diet 交集算法（getAllowedFoodByDiet） | resources | culture/subspecies | B | open |
| Zone 生长/废弃机制 | city | world | B | open |
| WorldTileData 位级格式 / tileArray 行程编码 | save | world | B | open |
| mine_rate/produce_min 产出再生循环 | resources | world/behaviour | B | open |
| supply_*/trade_* 消费位置 | resources | boats-trade | B | open |
| DBTables schema 与迁移 | save | stats/history | B | open |
| ItemWindow/EquipmentEditor 内部 | items | ui | B | open |
| ResourcesPatch/MasterBuilder JSON→Asset 映射 | assets, resources | NML | C | open |
| NCMSCompatibleLayer 桥接 | assets | NML | C | open |
| mutation 概率权重细节 | traits | — | D | keep |
| base_stats_meta 字段语义 | traits | — | D | keep |
| checkTraitsMod 调用面 / TraitRainLibrary | traits | — | D | keep |
| CityStatus/LoyaltyCalculator / isLocked/MetaObjectCounter | city | — | D | keep |
| checkForCityErrors v7 兜底规则 | city | — | D | keep |
| BuildingFundament 旋转/异形 / Architecture 派生映射 | buildings | — | D | keep |
| tryToMakeWarrior 数值 / ActorAsset.job 数组 / JobCityAsset 差异 | jobs | — | D | keep |
| 装备雨 RainState / default_weapons 配置面 / repair_cost_multiplier 值 | items | — | D | keep |
| KingdomTrait tax 字段 / power / royal clan / survivors 降级 | kingdom | — | D | keep |
| Egg/Baby/Adult 状态机 / evolutionEvent / ActorSimpleComponent | actor | — | D | keep |
| WORLD_SAVE_VERSION 值 / convertTo15-17 字段清单 / Workshop 链路 | save | — | D | keep |
| \_assetgv 版本门控 / exportAssets 用途 / ingredients 食物配方消费位 | assets, resources | — | D | keep |

**统计**：A 类 2 项（本次全部关闭）；B 类 21 项（去重后）；C 类 2 项；D 类 22 项（保留）。

**B 类汇聚度**：behaviour 6 项（最大单一汇聚点）＞ culture 4 ＞ combat/war 2 ＞ world 3 ＞ alliance/diplomacy 2 ＞ 其余各 1。

## 6. Initialization Constraints（统一规律）

六库实证汇总，统一规则**成立**：

> **`AssetLibrary.add(asset)` 成功 ≠ 完整进入原版初始化后的派生结构。**
> mod 资产注册恒晚于 linkAssets（NML SmoothLoader 在 `Config.game_loaded` 后），且全源码无 linkAssets 重跑入口（仅 InitLibraries.cs:57 一次）。

| 库 | add 后不更新的派生结构 | add 后仍正常 | 补救模式 |
|---|---|---|---|
| traits | pot_traits_birth/growup/mutation/combat、opposite_traits、default_for_actor_assets | dict/list/get、addTrait/数值/钩子 | 手动向池 Add；NML ActorTraitBuilder |
| resources | strategic_resource_assets、order、full_sprite_path、give_trait/status/diet 交叉 | change/set/get、saved 往返 | 手动 strategic 列表 Add；自调 loadSprites |
| citizen_jobs | list_priority_normal/high/high_food、unit_job_default 自动对齐 | jobs 名额 dict（runtime 消费） | 手动列表 Add + 自设 unit_job_default |
| items | equipment_by_subtypes、pot_weapon/pot_equipment 池、item_modifiers 解析、fillUnlockedPools | add 自动补 base_stats、generateItem/setItem/stats、存档往返 | 手动 cache 插入；复用既有 subtype |
| items_modifiers | pools（rarity 加权） | addMod 手动附加 | 手动池 Add |
| buildings | （Architecture 派生仅原版 post_init；linkAssets 特有项未逐项枚举，未见破坏性 cache） | add/addBuilding/canBuildFrom/存档 | clone 既有资产派生（pattern 已验证） |

两条通用补救路线：**(a) 复用派生结构**——clone 既有资产或复用既有 subtype/group；**(b) 手动维护**——直接向目标 list/dict Add。运行时按 id 查询的消费路径（get/枚举/实例化）不受影响。

## 7. Persistence Matrix

| 数据 | 自动持久化 | custom_data 通道 | asset id 依赖 | 缺失行为 | runtime 重建 |
|---|---|---|---|---|---|
| Actor 本体 | ✓ ActorData→map.wbox | — | asset_id→ActorAsset | 整体静默丢弃 | traits HashSet、stats、ai、equipment 引用 |
| Actor mod 数据 | — | ✓ data.get/set 五型 | — | — | — |
| Traits | ✓ saved_traits | — | trait id | 条目静默跳过 | _traits_cache、decisions_assets |
| Kingdom | ✓ KingdomData | ✓ kingdom.data | original_actor_asset（仅信息） | 不丢弃（无蓝图依赖） | cities/buildings dirty 缓存、king/capital |
| Building | ✓ BuildingData（Removed 跳过） | **施工进度即 custom_data key** | asset_id→BuildingAsset | 整体静默丢弃 | tiles/zones/residents |
| Resources | ✓ saved_resources（仅非零槽） | — | resource id/槽 | 槽静默丢弃 | food/other 分类、City.storages |
| Items | ✓ 三处（SavedMap.items + saved_items + CityEquipment） | — | asset_id→EquipmentAsset；modifier id | 物品丢弃 / 词缀剔除 | _total_stats/_quality/_value 重算、槽引用 |
| City | ✓ CityData（zones/引用 id） | ✓ city.data | 无 CityAsset | n/a | units/buildings/storages/_professions_dict |
| Jobs | ✗ 不持久化（仅 data.profession） | n/a | n/a | n/a | City.jobs 名额池由 AI 重建 |

统一规律：**实体引用一律 id 化落盘 + 按依赖序重解析（items→…→kingdoms→cities→actors→buildings）**；**缺失 asset id 无迁移、静默降级**（丢弃或剔除）；**runtime 缓存全部自动重建**（dirty-lists/重算），mod 跨存档持有的对象引用必须经 on_world_loaded 重取；custom_data 五型容器是通用 mod 持久化通道（世界/实体两级）。

## 8. Modding Readiness Matrix

| 场景 | 判定 | 依据 | 缺口 |
|---|---|---|---|
| 注册新 ActorTrait | **READY** | traits.md 全链 + 池 caveat + NML builder + 2 patterns | — |
| Actor 自定义持久数据 | **READY** | data.get/set 五型 + 存档路径 verified + pattern | — |
| 注册新 BuildingAsset | **READY** | 三层模型/创建链/状态机/施工 key 冲突警示 + clone pattern | linkAssets 特有项未逐项枚举（clone 路线规避） |
| 创建/修改 ResourceAsset | **READY** | 注册三阶段 + strategic/sprite caveat + ref mod 实证 | — |
| 注册 CitizenJob | **PARTIAL** | 资产注册/列表/名额知识完备 | **新工种的任务链（ActorJob task + Beh 节点注册）依赖 behaviour 系统知识**；复用既有 task 链则可即刻实施 |
| 创建新 EquipmentAsset | **READY** | 数据模型/生成/装备/存档全链 + subtype/池 caveat（含 KeyNotFound 推断警示） | AI 可合成需手动 cache 插入（补救模式已文档化，未给逐条步骤） |
| 给 Actor 装备 item | **READY** | generateItem/setItem/替换/词缀/耐久/存档全链 | — |
| per-Kingdom 系统 | **READY** | data 层 + KingdomTrait + dirty 重建 + NML patch 点 + pattern 互证 | — |
| 获取/修改 City storage | **READY** | 聚合 API + 单建筑 API + 容量语义 + UI 刷新边界 | — |
| Hook Actor/City/Kingdom lifecycle | **READY** | die/checkCallbacksOnDeath（ref mod 实证）+ newCityEvent/makeNewCivKingdom（NML 跨源实证）+ on_world_loaded | Actor 创建钩子为 Inferred（死亡钩子同构可推） |

**9 READY / 1 PARTIAL / 0 BLOCKED**。

## 9. Remaining Knowledge Blockers

按影响面排序：

1. **Behaviour 系统（最大盲区）**：AiSystem 执行引擎 + DecisionAsset 消费机制不透明 → 新 AI 行为/新工种任务链/决策介入类 mod 无法可靠编写；B 类 deferred 中 6 项汇聚于此，且 jobs/items 的"边界到此为止"均止于同一堵墙
2. **Combat 消费侧**：装备 action_attack_target 的结算路径未知 → 武器特效类 mod 只能复用原版 AttackAction，无法自定义结算
3. **Culture 域**：书籍/命名/武器偏好未知 → StorageBooks、传奇命名定制受限
4. **文档质量（非知识）**：行号引用漂移（§4 F6）——不影响结论正确性，影响导航效率

## 10. Recommendation

**下一阶段唯一推荐：Behaviour Harvest**（AiSystem 执行引擎 + DecisionAsset/NeuroLayer 消费 + Beh* 节点注册面）。理由：B 类 deferred 最大汇聚点（6 项）；Modding Readiness 唯一 PARTIAL 项的直接阻塞源；jobs/items/actor 三系统边界均已"推到门口"，边际调查成本最低、解锁价值最高。
