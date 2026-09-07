# WorldBox System Inventory

基于 WBKB 索引（worldbox-0.51.2-51d275f0168b）的机械扫描 + 命名核实。Tier 依据 Modding 价值与 Z5/Z6 缺口。

| system_id | Title | Category | Tier | 核心类型（WBKB verified） | 状态 |
|---|---|---|---|---|---|
| jobs | Jobs / Professions | economy | S | ActorJob, ActorJobLibrary, CitizenJobAsset, CitizenJobLibrary, CitizenJobCondition, ProfessionAsset, ProfessionLibrary, UnitProfession, BehCityActorFindNewJob, BehEndJob, BehCheckEndCityActorJob | planned |
| resources | Resources / Storage | economy | S | ResourceAsset, CityStorageSlot, BehCityActorGetResourceFromStorage, BehCityActorFindStorage(Wheat) | verified（economy/resources.md，2026-09-07） |
| items | Items / Equipment | economy | S | ItemAsset, ItemLibrary, ActorEquipment, ItemCrafting | planned |
| city | City | settlement | S | City, CityData, CityManager + Beh*City* 节点群 | verified（settlement/city.md，2026-09-07） |
| buildings | Buildings / Construction | settlement | S | BuildingAsset, BuildingLibrary, BuildingManager | verified（settlement/buildings.md，2026-09-07） |
| actor | Actor / Entity | entity | S | Actor, ActorAsset, ActorData, BaseActorComponent, ActorManager | verified（entity/actor.md，2026-09-07） |
| traits | Traits | entity | S | ActorTrait, TraitGroupAsset, AssetManager.traits/trait_groups | verified（entity/traits.md，2026-09-07） |
| kingdom | Kingdom / Political | political | S | Kingdom, KingdomData, KingdomManager, ClanTrait, Alliance, WarManager, Diplomacy*（详见 xavii profile） | verified（political/kingdom.md，2026-09-07） |
| assets | Asset Framework | technical | S | AssetManager, *Library, *Asset 基类群 | verified（technical/assets.md，2026-09-07） |
| save | Save / Persistence | technical | S | SaveManager, SaveCustomData, AutoSaveManager, SaveConverter | verified（technical/save.md，2026-09-07） |
| culture | Culture / Knowledge / Books / Language | civilization | A | Culture, CultureData, KnowledgeAsset, KnowledgeLibrary, BookManager, BookData, BookTypeAsset, Language, GameLanguageLibrary | planned |
| combat | Combat / Military | military | A | AttackAction, CombatActionAsset, DamageSystem 相关（mod 证据多） | planned |
| boats | Boats / Transport / Trade | transport | A | Boat, BehBoatFindTargetForTrade, BehBoatMakeTrade | planned |
| behaviour | AI / Behaviour Trees | technical | A | Beh* 节点群（200+）, DecisionAsset, DecisionsLibrary, DecisionActionWeight, BehaviourTaskActor | planned（关键入口已被 Z6 world-tick pattern 记录） |
| world | World / Map / Time | world | B | MapBox, WorldTile, TileLibrary, BiomeLibrary, WorldBehaviour* | planned（mapdeal/guigu profile 有部分证据） |
| ui | UI | technical | B | UnitWindow, KingdomWindow, ScrollWindow, TabManager(NML) | partial（Z6 ui-button pattern 覆盖） |
| events | World Events / Disasters | world | B | WorldLogAsset, Meteorite 等 | partial |

关键命名修正（相对 Z7 初始 taxonomy）：
- 无独立 `JobLibrary`——jobs 分两层：`ActorJob`（运行时对象）+ `CitizenJobAsset/CitizenJobLibrary`（资产）；`ProfessionAsset/ProfessionLibrary` 是另一体系
- 无 `Storage`/`CityStorage` 类——存储由 `CityStorageSlot` 与 City 内部容器承担（待 jobs/resources 调查确认）
- Culture 系统实际存在且比预期丰富（Knowledge/Book/Language 均有类型）
- Boats 与 trade 行为直接相关（BehBoatFindTargetForTrade）

System Harvest 进度（第一批，2026-09-07）：
- actor / traits / assets 完成 evidence-backed 系统调查（verified）——覆盖 core_types / data_model / lifecycle / registration / runtime_access / cross_system_relationships / modding_extension_points / evidence / known_gaps 九维
- 已知 deferred：save 落盘细节（→ save 系统）、AiSystemActor 内部（→ behaviour 系统）、NML ResourcesPatch/MasterBuilder 内部（→ NML 深挖）
- 方法验证：search → targeted read → refs/callers 交叉确认的流程可行，建议继续用于下一批（city / save / behaviour 优先）

System Harvest 进度（第二批，2026-09-07）：
- save / city 完成 evidence-backed 系统调查（verified）；关闭第一批 deferred：ActorData 落盘路径、id 跨存档稳定性、saved_traits 漂移边界（已回写 actor.md / traits.md）
- 新增 deferred（归入各系统）：WorldTileData 位级格式（→ world）、DBTables 历史表（→ stats/历史域）、CityTasksData/AiSystemCity（→ behaviour）、CitizenJobs（→ jobs）、存储本体 CityResources（→ resources/buildings）
- 剩余 S 级未调查：jobs / resources / items / buildings / kingdom；下一批建议 kingdom（city 边界已就绪）或 behaviour（deferred 汇聚点）

System Harvest 进度（第三批，2026-09-07）：
- kingdom / buildings 完成 evidence-backed 系统调查（verified）；关闭第二批 city.md 两项边界 gap（kingdom 重建机制、CityResources 容量归属）
- 关键概念澄清：Kingdom 双层身份（KingdomAsset 类别 + wild 常驻实例 vs civ 动态实例）；建筑容量属于 ResourceAsset 而非 Building/City
- 新增 deferred：War/Alliance/Diplomacy 内部（→ war/alliance/diplomacy）、ResourceAsset 字段与生产循环（→ resources）、建造决策行为（→ behaviour）、StorageBooks（→ items/culture 域）
- 剩余 S 级：jobs / resources / items；建议下一批 resources（buildings 边界已就绪）

System Harvest 进度（第四批，2026-09-07）：
- resources 完成 evidence-backed 系统调查（verified）；关闭 buildings.md 资源字段 gap 并**修正其容量表述**（storage_max=每建筑容量 vs maximum=change 钳制）
- 关键结论：无统一 city store（amount 在各 Building.data.resources 的 CityStorageSlot）；生产/消耗/搬运 API 级调用链闭环；mod 新增资源仅 add 可用但 linkAssets 缺失（strategic 列表/order/sprite 不更新）
- 新增 deferred：供给/贸易数值消费位置（→ jobs/boats-trade）、产出数值计算、DropAsset 拾取（→ behaviour）
- 剩余 S 级：jobs / items
