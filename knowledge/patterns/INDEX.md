# Pattern Index

按 Goal / System 组织。所有条目 ≥ Verified；Inferred 不进入本索引（见 DEFERRED.md）。

## By Goal（我要实现 X）

**给单位加能力/状态**
- 加被动特性/境界/buff → [register-actor-trait](assets/register-actor-trait.md)
- 存 per-actor 跨存档状态 → [actor-data-custom-state](actor/actor-data-custom-state.md)
- 加自定义数值属性 → [register-custom-stat](actor/register-custom-stat.md)
- 记录单位生平/事件 → [actor-event-observation](actor/actor-event-observation.md)

**加资产/神力**
- 注册新特质 → [register-actor-trait](assets/register-actor-trait.md)
- 派生/魔改现有资产 → [clone-modify-asset](assets/clone-modify-asset.md)
- 注册可点击神力 → [register-godpower](assets/register-godpower.md)
- 防重复/防 NRE 注册 → [safe-asset-registration](assets/safe-asset-registration.md)

**改原版行为**
- 拦截/否决/替换方法 → [harmony-prefix-recipes](patching/harmony-prefix-recipes.md)
- 组织大量 patch → [harmony-safe-batch-patching](patching/harmony-safe-batch-patching.md)

**加 UI**
- 原生窗口加按钮 → [ui-button-injection](ui/ui-button-injection.md)
- 自建神力 tab → [custom-power-tab](ui/custom-power-tab.md)

**系统级**
- 王国政体/类型系统 → [custom-kingdom-system](kingdom/custom-kingdom-system.md)
- 周期/每帧系统驱动 → [world-tick-integration](lifecycle/world-tick-integration.md)
- 数据持久化选型 → [persistent-mod-data](persistence/persistent-mod-data.md)
- mod 工程组织（NML Feature） → [nml-feature-authoring](lifecycle/nml-feature-authoring.md)
- 访问私有 API → [private-api-reflection](utility/private-api-reflection.md)

## By System

- **Actor**：actor-data-custom-state, register-custom-stat, actor-event-observation
- **Traits**：register-actor-trait, register-custom-stat
- **Assets**：register-actor-trait, clone-modify-asset, register-godpower, safe-asset-registration
- **Buildings**：clone-modify-asset
- **Kingdom**：custom-kingdom-system
- **UI**：ui-button-injection, custom-power-tab, register-godpower
- **Save/Persistence**：actor-data-custom-state, persistent-mod-data, actor-event-observation
- **Mod Lifecycle**：nml-feature-authoring, world-tick-integration, harmony-safe-batch-patching
- **Patching**：harmony-prefix-recipes, harmony-safe-batch-patching
- **Utility**：private-api-reflection
