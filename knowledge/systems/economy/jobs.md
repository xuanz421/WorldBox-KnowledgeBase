# System: Jobs / Professions

WorldBox 职业/工作系统的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读。本文件关闭 actor.md / city.md / resources.md / buildings.md 的 Jobs 边界 Known Gap（见回写记录）。

## Scope

覆盖：Job/Profession 四层概念模型（UnitProfession / ProfessionAsset / CitizenJobAsset / ActorJob）、profession 生命周期、citizen job 生命周期（需求生成/分配/结束/重选）、City jobs 数据结构、Job→Resources/Buildings 的 API 级驱动、save/load 分界、modding 注册要求。

不覆盖：AiSystem/BehaviourTask 执行引擎内部（仅到 setJob/nextJob 委托层——deferred: behaviour）、Decision 决策机制、CityTasksData 之外的 city AI 编排、warrior 招募数值平衡、KingdomJob/JobCityAsset（同构层，仅提及）。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `UnitProfession` | **职业枚举**：Nothing/Unit/King/Leader/Warrior（Baby 已 Obsolete） | UnitProfession.cs:3-12 |
| `ProfessionAsset` | 职业资产（按枚举 1:1）：decisions/can_capture/is_civilian | ProfessionAsset.cs:4-52 |
| `ProfessionLibrary` | 职业库（5 个固定资产 + `_dict_profession_id` 枚举索引 + linkDecisions） | ProfessionLibrary.cs:4-90 |
| `CitizenJobAsset` | **市民工种**（分配资格/优先级/图标）：priority/priority_no_food/common_job/ok_for_king/should_be_assigned/unit_job_default | CitizenJobAsset.cs:4-29 |
| `CitizenJobLibrary` | 工种库（12 工种 + linkAssets 构建三张优先级列表） | CitizenJobLibrary.cs:3-168 |
| `CitizenJobs` | **City 持有的工种名额容器**（jobs/occupied 双 dict） | CitizenJobs.cs:5-118 |
| `CitizenJobCondition` | 分配条件委托 `bool(Actor)` | CitizenJobCondition.cs:1 |
| `ActorJob : JobAsset` | **AI 任务编排**（task id 列表 + 条件），供 AiSystem 逐步执行 | ActorJob.cs:3-6, JobAsset.cs:4-22 |
| `ActorJobLibrary` | ActorJob 库（initJobsCivs/initJobsMobs 代码定义） | ActorJobLibrary.cs:3-246 |
| `CityTasksData` | City 环境任务计数（trees/minerals/bushes/roads/poops...，runtime） | CityTasksData.cs |

**四层概念模型（Verified，本系统核心结论）**——这四个名字**不是同一层的四种叫法**，而是两个独立轴：

```text
轴 1「Profession 职业」——粗粒度社会身份，per-Actor，持久化：
  UnitProfession(枚举) ←1:1→ ProfessionAsset(资产)
      Actor._profession : UnitProfession        （runtime）
      Actor.profession_asset                    （runtime, get(pType) 解析）
      ActorData.profession : UnitProfession     （持久化, 枚举直存）

轴 2「Job 工作」——具体做什么，两层：
  层 A「CitizenJob 工种」（仅 sapients 有城市时）：
    CitizenJobAsset（资产） → Actor.citizen_job（runtime 引用，不持久化）
    City.jobs : CitizenJobs（名额池，runtime）
  层 B「ActorJob AI 编排」（所有 Actor）：
    ActorJob（资产 = task 列表） → Actor.ai.job（runtime）
    由 nextJobActor 按 Egg/Baby/City/Warrior/Kingdom/wild 分层选择
```

**两轴连接点**：`Actor.setCitizenJob(pJobAsset)` → `ai.setJob(pJobAsset.unit_job_default)`——**工种切换即切换 AI job**（CitizenJobLibrary.post_init 把 `unit_job_default = id` 对齐同名 ActorJob，CitizenJobLibrary.cs:134-142）。Warrior 职业改变 nextJobActor 分支（job_attacker 而非 job_citizen，Actor.cs:5028）。

## Data Model

- **持久化（Verified）**：仅 `ActorData.profession : UnitProfession`（枚举直存，无 id 解析，ActorData.cs:26-27）；King 的 `setKing(pFromLoad)` 恢复职业。**citizen_job / ai.job / City.jobs 名额全部不持久化**——load 后由 AI 重新选择
- **runtime-only**：`Actor._profession` + `profession_asset`、`Actor.citizen_job : CitizenJobAsset`、`Actor.ai.job : ActorJob` + `ai.task_index`、`City.jobs : CitizenJobs`（jobs/occupied）、`City.tasks : CityTasksData`、`City._last_checked_job_id`（轮转游标）
- **资产侧**：`AssetManager.professions`（ProfessionLibrary，注册名 "professions"）、`AssetManager.citizen_job_library`（"citizen_job_library"）、`AssetManager.job_actor`（ActorJobLibrary，"job_actor"，绑到 `ai.jobs_library`，Actor.create，见 actor.md）、`AssetManager.job_city/job_kingdom`（同构）
- `CitizenJobs`：`jobs : Dict<CitizenJobAsset,int>`（当前可用名额）+ `occupied : Dict<CitizenJobAsset,int>`（在职人数，checkOccupied 从 `actor.citizen_job` 反向统计）——**ground truth 是 actor.citizen_job 引用**，occupied 是重建缓存

## Lifecycle / Flow

### Profession 生命周期（Verified）

```text
赋予: Actor.setProfession(UnitProfession, pCancelBeh=true)        Actor.cs
  _profession = pType
  profession_asset = AssetManager.professions.get(pType)   （枚举→资产）
  setStatsDirty() + hasCity → setCitizensDirty + cancelAllBeh
  + timestamp_profession_set + clearGraphicsFully
默认: checkDefaultProfession → setProfession(Unit)        （创建链 finalizeActor 调用）
特殊: Kingdom.setKing → setProfession(King)；makeNewCivKing 先 stopBeingWarrior
     City.tryToMakeWarrior（gold>10+food 条件, setCitizenJob 前置分支）
存档: saveProfession → data.profession = _profession     Actor.cs:8692-8695
加载: loadFromSave → setProfession(data.profession, pCancelBeh:false)
     （sapient 无城者强制 Unit，Actor.cs:8868-8872）
```

**profession 影响（Verified，2026-09-08 audit 修正定位）**：① `profession_asset.hasDecisions()` → decisions 数组填充（`updateStats` → `registerDecisions()`，Actor.cs:1695 → 4867-4953，影响 AI 决策池而非数值）；② nextJobActor 选 job 分支（Warrior→job_attacker）；③ city `_professions_dict` 分组缓存（updateCitizens，见 city.md）。**不影响 base_stats 数值**。

### Citizen Job 生命周期（Verified 全链）

```text
1. 需求生成（City AI 侧, BehaviourTaskCityLibrary "do_initial_load_check" 等 task）:
   CityBehCheckCitizenTasks.execute(City)                CityBehCheckCitizenTasks.cs
   ├─ jobs.clearJobs() + checkOccupied（从 actor.citizen_job 反向统计在职数）
   ├─ _citizens_left = status.population_adults; tasks.clear()
   ├─ countFires/countResources/countRoads → CityTasksData（环境任务计数）
   └─ 按 hasBuildingToBuild/hasStorageBuilding/windmill/mine 等条件
      addToJob(工种, jobs, 增量, 任务上限[, 岗位上限])
      （名额从环境派生：bushes/plants/hives 数、farms、trees、roads、ruins、poops；
        warrior 由 world_law + food + 人口上限决定；_citizens_left 扣减）

2. 分配（Actor AI 侧）:
   BehCityActorFindNewJob.execute → city.setCitizenJob(actor)   BehCityActorFindNewJob.cs:7
   City.setCitizenJob                                     City.cs:1851-1871
   ├─ 前置: 可招 warrior 则 tryToMakeWarrior 优先
   ├─ checkCitizenJobList(list_priority_high)（priority>0 工种）
   ├─ 无食物时 list_priority_high_food（priority_no_food>0）
   └─ list_priority_normal 轮转扫描（_last_checked_job_id 游标防饿死）
   checkCitizenJob                                       City.cs:1886-1903
   ├─ only_leaders / should_be_assigned(Actor) 委托过滤
   └─ jobs.hasJob → jobs.takeJob(扣名额) + actor.setCitizenJob(工种)

3. 执行:
   Actor.setCitizenJob(pJobAsset)                        Actor.cs:4993-4997
   → citizen_job = pJobAsset + ai.setJob(unit_job_default)（同名 ActorJob）
   AiSystem.update → run → task==null 时 updateNewBehJob:
     next_job_delegate()（=Actor.getNextJob→nextJobActor）选 job → 逐 task 执行
     （citizen 分支取 asset.job_citizen 随机，即默认 "unit_citizen" ActorJob，
       其 tasks = make_decision/check_city_destroyed... 内含 find_new_job 循环）

4. 结束/重选:
   BehEndJob.execute → actor.endJob()                    BehEndJob.cs
     （ai.clearJob + citizen_job = null → 下轮 FindNewJob）
   BehCheckEndCityActorJob: occupied > 名额（城池缩水）→ endJob
   job 内 task 列表执行完 → task_index 回卷（AiSystem.updateNewBehJob）
```

### Job → Resources / Buildings 驱动（API 级，Verified）

```text
builder 工种 → ActorJob "builder" → task try_build_building
  → BehCityActorFindBuilding("new_building")（CityBehBuild 排程的建设目标）
  → task build_building → BehBuildTarget.execute
  → building.updateBuild(actor.getConstructionSpeed())      BehBuildTarget.cs:18
    （Building.updateBuild = construction_progress 推进 + 完成钩子，见 buildings.md）
woodcutter → task chop_trees → BehExtractResourcesFromBuilding 系（extractResources + addToInventory）
gatherer_* → collect_fruits/herbs/honey 同构（→ economy/resources.md 搬运链）
食物: BehTryToEatCityFood → city.eatFoodItem（consume 侧已录 resources.md）
```

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `actor.setProfession(type)` | 职业变更（internal） | Actor.cs |
| `actor.setCitizenJob(jobAsset)` | 工种设定（含 AI job 切换） | Actor.cs:4993 |
| `actor.endJob()` | 结束当前 job（AI + citizen 双清） | Actor.cs:4978-4982 |
| `city.setCitizenJob(actor)` | 分配入口（优先级 + 轮转 + 名额） | City.cs:1851 |
| `city.jobs.takeJob/freeJob/countOccupied` | 名额操作 | CitizenJobs.cs |
| `AssetManager.professions.get(UnitProfession)` | 枚举→资产 | ProfessionLibrary.cs |
| `AssetManager.citizen_job_library.list_priority_*` | 三张分配列表（linkAssets 产物） | CitizenJobLibrary.cs:143-167 |
| `AssetManager.job_actor` | AI job 库（ai.jobs_library） | AssetManager.cs:399 |

## Extension Points

1. **注册新工种（CitizenJobAsset）——modding 核心问题（Verified）**：
   - **必须**：`AssetManager.citizen_job_library.add(new CitizenJobAsset{ id, priority... })`
   - **仅 add 不足**：`linkAssets` 不重跑 → **不进 list_priority_normal/high/high_food 三张分配列表**（`common_job=true` 是进列表前提）→ 永不被 setCitizenJob 选中；**必须手动**向对应列表 Add 或等待其他机制
   - `unit_job_default` 默认 null → `ai.setJob(null)` 无效：需手动设为同名 ActorJob id（原版由 post_init 对 common_job 自动对齐，mod 需自设）
   - 配套 ActorJob（task 编排）需 `AssetManager.job_actor.add` + BehaviourTaskActorLibrary 有对应 task 资产（Beh 节点注册 → deferred: behaviour）
   - `should_be_assigned` 委托可控制资格
2. **注册新职业（ProfessionAsset）**：枚举封闭（UnitProfession 五值）→ **不能新增枚举职业**；只能改既有 ProfessionAsset 行为（如 addDecision）
3. **修改分配倾向**：调 priority/priority_no_food 或操作 city.jobs 名额
4. **观察/介入**：Harmony patch `Actor.setCitizenJob` / `City.setCitizenJob` / `CityBehCheckCitizenTasks`

## Cross-System Relationships

| 系统 | 边界接口 | 深入方向 |
|---|---|---|
| Actor | `_profession/profession_asset/citizen_job`；setProfession 联动 statsDirty/beh 取消 | 已覆盖（entity/actor.md） |
| City | `city.jobs : CitizenJobs`（名额池 runtime）+ `city.tasks : CityTasksData`（环境计数） | 已覆盖（settlement/city.md） |
| Resources | builder/woodcutter/gatherer 工种驱动 extract/deposit/consume（API 链见 resources.md） | 已覆盖（economy/resources.md） |
| Buildings | BehBuildTarget→updateBuild；CityBehBuild 选址（canBuildFrom） | 已覆盖（settlement/buildings.md） |
| Kingdom | setKing(King)；warrior 招募条件；stopBeingWarrior | 已覆盖（political/kingdom.md） |
| Behaviour | AiSystem/BehaviourTask 执行引擎、Decision 资产 | deferred: behaviour（本批止于 setJob/nextJob 委托） |
| Save | 仅 data.profession 持久化；job 全部重选 | 已覆盖（technical/save.md） |
| Items | **边界澄清（2026-09-08，→ economy/items.md）**：crafting/repair/take_item（make_items/repair_equipment/try_to_take_city_item）是 **Decision task 而非 CitizenJob 工种**——12 工种中无 blacksmith，装备相关任务全部由 Decision 层（make_decision）+ AutoCivilization 驱动；工种系统不调度任何 item 行为 | 已覆盖（economy/items.md） |

## Evidence

| 结论 | source | location |
|---|---|---|
| 四层概念模型（枚举/职业资产/工种/AI job 分属两轴） | worldbox | UnitProfession.cs:3-12, ProfessionAsset.cs, CitizenJobAsset.cs, ActorJob.cs+JobAsset.cs, Actor.cs:5013-5044 |
| profession 赋予/持久化/恢复 | worldbox | Actor.cs setProfession/checkDefaultProfession/saveProfession:8692-8695/loadFromSave:8868-8872 |
| profession 影响 decisions 而非数值 | worldbox | Actor.updateStats:1695 → registerDecisions:4867（profession 段 4943-4953） |
| 名额生成（环境派生 + occupied 反查） | worldbox | CityBehCheckCitizenTasks.cs execute/checkOccupied/addToJob |
| 三张优先级列表 linkAssets 构建 | worldbox | CitizenJobLibrary.cs:143-167 |
| 分配链（BehFindNewJob→City.setCitizenJob→checkCitizenJob→takeJob） | worldbox | BehCityActorFindNewJob.cs:7; City.cs:1851-1903 |
| 执行链（setCitizenJob→ai.setJob→updateNewBehJob） | worldbox | Actor.cs:4993-4997; AiSystem.cs:64-98, 217+ |
| 结束/重选（BehEndJob/BehCheckEndCityActorJob） | worldbox | BehEndJob.cs; BehCheckEndCityActorJob.cs |
| nextJobActor 分层选择（egg/baby/city/warrior/kingdom/wild） | worldbox | Actor.cs:5013-5044 |
| builder→updateBuild 驱动 | worldbox | ActorJobLibrary builder 定义; BehBuildTarget.cs:18 |
| City.jobs 不持久化（prepareForSave 无此项） | worldbox | City save 链（CoreSystemObject.save→data.save）；CityData 无 jobs 字段 |
| post_init unit_job_default 对齐 | worldbox | CitizenJobLibrary.cs:134-142 |

## Confidence

- Verified：全部机制结论
- Inferred：无
- Unknown：见 Known Gaps

## Known Gaps

- AiSystem 执行引擎细节（task 切换/条件调度/single actions/decisionRun 差异）——deferred: behaviour
- DecisionAsset 决策机制（decisions 数组如何被消费）——deferred: behaviour
- CityBehBuild 完整选址算法（建设目标如何进入 "new_building" 查找）——deferred: behaviour/buildings 深挖
- tryToMakeWarrior 招募数值与 warrior 平衡
- `ActorAsset.job/job_baby/job_kingdom` 数组在资产定义中的完整默认值面
- JobCityAsset/KingdomJob 与 ActorJob 的差异细节（同构层未展开）

## Related Patterns

稳定 pattern_id（完整索引：knowledge/patterns/模式索引.md）：

- `world-tick-integration` — City AI 周期驱动（CityBehCheckCitizenTasks 挂载点）
- `register-custom-stat` — 数值侧扩展（与 profession 解耦）
- `actor-data-custom-state` — per-actor 数据（profession 已占用 data.profession key）
- `clone-modify-asset` — 工种派生路线
