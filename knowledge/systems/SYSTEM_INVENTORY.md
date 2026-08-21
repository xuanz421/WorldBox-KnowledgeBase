# WorldBox System Inventory

基于 WBKB 索引（worldbox-0.51.2-51d275f0168b）的机械扫描 + 命名核实。Tier 依据 Modding 价值与 Z5/Z6 缺口。

| system_id | Title | Category | Tier | 核心类型（WBKB verified） | 状态 |
|---|---|---|---|---|---|
| jobs | Jobs / Professions | economy | S | ActorJob, ActorJobLibrary, CitizenJobAsset, CitizenJobLibrary, CitizenJobCondition, ProfessionAsset, ProfessionLibrary, UnitProfession, BehCityActorFindNewJob, BehEndJob, BehCheckEndCityActorJob | planned |
| resources | Resources / Storage | economy | S | ResourceAsset, CityStorageSlot, BehCityActorGetResourceFromStorage, BehCityActorFindStorage(Wheat) | planned |
| items | Items / Equipment | economy | S | ItemAsset, ItemLibrary, ActorEquipment, ItemCrafting | planned |
| city | City | settlement | S | City, CityData, CityManager + Beh*City* 节点群 | planned |
| buildings | Buildings / Construction | settlement | S | BuildingAsset, BuildingLibrary, BuildingManager | planned |
| actor | Actor / Entity | entity | S | Actor, ActorAsset, ActorData, BaseActorComponent, ActorManager | planned（部分被 Z5/Z6 覆盖） |
| traits | Traits | entity | S | ActorTrait, TraitGroupAsset, AssetManager.traits/trait_groups | planned（Z6 pattern 已覆盖注册面） |
| kingdom | Kingdom / Political | political | S | Kingdom, KingdomData, KingdomManager, ClanTrait, Alliance, WarManager, Diplomacy*（详见 xavii profile） | planned |
| assets | Asset Framework | technical | S | AssetManager, *Library, *Asset 基类群 | planned（Z6 patterns 部分覆盖） |
| save | Save / Persistence | technical | S | SaveManager, SaveCustomData, AutoSaveManager, SaveConverter | planned |
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
