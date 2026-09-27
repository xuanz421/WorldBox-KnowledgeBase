---
title: 跨模组对比总结
aliases:
  - Cross-Mod Summary
---

# Cross-Mod Summary

27 个 Reference Mods 的横向对比。分层：Tier A（核心玩法/系统深度）12 个、Tier B（单功能有技术价值）11 个、Tier C（微型/本地化）4 个。每模组的机制级方法清单见各 profile 的 Unique Methods 段（稳定 ID 引用，不建横向链接）。

## Most Valuable References（按技术价值）

| Mod | 一句话用途 |
|---|---|
| **chinesename** | Harmony patch 工程化范本：IPatch 接口+程序集扫描自动注册、双注册兼容、非破坏式 hook——任何新 mod 的组织结构首选参考 |
| **powerbox** | NML Feature 体系权威样本：40+ 神力全部走 ModAssetFeature/ModButtonFeature 自动发现，零样板 |
| **xavii-nation-types** | 王国/政体/外交系统改造全链路：定义表驱动+KingdomTrait+custom_data+行为树 tick 入口 |
| **guigu-cultivation** | 大型世界级模拟的工程实践：分帧切片、读档牺牲窗、Phase 延迟加载、逐补丁隔离 |
| **fanren-xiuxianzhuan** | 独立修仙体系完整范本：自建帧切片心跳+actor.data 全状态+宗门组织实体重建+六品灵石找零——与 guigu（挂原版月结）构成对偶实现 |
| **xuanmen-daojie** | 深度 Actor 改造：stats/data 双轨持久化、updateStats Transpiler、BatchActors 系统总线 |
| **ancient-warfare-3** | 巨型 overhaul 工程样本：SQLite 档案随存档、协作式异步调度+存档屏障、DormantPatchTypes 停用门、自有寻路接管（survey 级建档，深挖 deferred C0-C6） |
| **actorhistory** | 事件观察类 mod 范本：40+ 事件钩子→分类叙事→SQLite 世界键隔离存储 |
| **zhutian-shenzuo** | 存档级快照时间线（时间神殿：manifest 外置+反射 loadWorld 回溯+自动分支）+ ActorTickGate 补步门禁 + 命定死管线；自述测试版但系统完整 |
| **xuanjian-xianzu** | 修仙内容模组：TSV+Base64 世界字符串持久化、安全批量打补丁、金丹转世/权柄争夺 |
| **thefantasyworld** | 职业 RPG 层：trait 工厂+action_special_effect 逐帧升级、死亡保护链、神明复活存档落盘 |
| **shtoolkit** | 百宝箱型工具集：WorldBehaviourAsset 匿名闭包、多载合并 patch、Bresenham 视线遍历 |
| **boatrebalancebox** | 船只 rebalance 双层范式：数据层直改共享资产（零 Harmony）+ 行为层重写索敌/齐射/命中链——Boats 系统唯一 reference |
| **biology** | 器官/疾病/手术健康系统：零持久化静态字典状态 + 选中单位单点模拟 + updateStats postfix 版本守卫重放（与 xuanmen Transpiler 构成对偶）——Actor 健康/疾病领域唯一 reference |
| **optime** | Feature<T> 配置热切换补丁框架（54 行可移植）+ 高帧率模拟修复 |
| **funboost** | 纯补丁包范式样板：42 项声明式配置回调驱动的运行时开关补丁（config-toggle-skip-prefix / SkipFlags 协同抑制） |
| **sandbox** | 泛型类 manual Harmony patch 配方 + powers.clone 落地神力模板 |
| **familytree** | 死亡快照模式 + 纯 UGUI 平移缩放关系图 |
| **incensefiredway** | 特质升级链（境界后缀重写）+ 神明免疫 Prefix 批量否决（霸体）+ FMOD 直放 wav |
| **mapdeal** | 零 Harmony 深度地图操作：反射 tiles_map + SmoothLoader 生成链复刻 |
| **creepmobboost** | 零 Harmony 运行时决策注入：BehaviourTaskActor+DecisionAsset 挂现有种族主动筑巢 |
| **worldresilience** | 逆向侵蚀世界自愈（~180 行 Prefix 替换本体）+ 自定义世界法则注册（NML 旧式 IMod） |
| **buzzoff** | spawn-veto 否决范式微型样本（`__result=null; return false`） |
| **nerffiredamage** | 教科书级 Prefix 全量替换微型样本（烧血 10%→1%） |
| **unlock-all** | world_law default_state 直改 + 献祭计数保全解锁（NCMS） |
| **hanhai-unlock-all** | GameProgress 官方解锁后门 + 首帧布尔闸（NCMS 微型样本） |
| **simple-chinese-localization** | NML 本地化管线参考实现：IReloadable 热重载 + LocalizedText.Start Postfix 修刷新 |

## 覆盖：Harmony 三种组织法

```text
逐类 CreateAndPatchAll（故障隔离）   guigu-cultivation, xuanjian-xianzu, boatrebalancebox
Assembly/PatchAll（一次挂载）        xavii-nation-types, xuanmen-daojie, actorhistory,
                                    fanren-xiuxianzhuan, zhutian-shenzuo, funboost, thefantasyworld
程序集扫描自动发现                   chinesename（扩展性最佳）
反射扫描逐类有序 + DormantPatchTypes  ancient-warfare-3（停用门 + 空结果告警区分意外/主动）
Manual CreateProcessor（泛型类）     sandbox
```

## 覆盖：神力/系统入口

```text
NML Feature 体系          powerbox
powers.clone + DropAsset  sandbox, powerbox
GodPowerLibrary 直建       ancient-warfare-3, zhutian-shenzuo
WorldBehaviourAsset 闭包  shtoolkit
行为树节点 Prefix tick    xavii-nation-types, guigu-cultivation(BatchActors)
MonoBehaviour 自建心跳    fanren-xiuxianzhuan(CultivationUpdater), zhutian-shenzuo(YuanMaiTicker)
原版按钮挂接配置窗口       funboost(纪元按钮右键), fanren-xiuxianzhuan(自建 tab)
```

## 覆盖：持久化频谱

```text
actor.data 字符串键（随存档）    guigu, incensefiredway, xuanmen-daojie, chinesename,
                                fanren(fanren.* 键族), zhutian-shenzuo(三级键族)
map_stats.custom_data（世界级）  thefantasyworld, xuanmen-daojie, actorhistory(世界键),
                                zhutian-shenzuo(时代/本源/时间神殿设置)
存档槽目录文件                    guigu
存档目录 JSON sidecar           fanren(fanren_fangshi.json), ancient-warfare-3(SQLite 档案随存档导出)
persistentDataPath JSON         shtoolkit, xuanmen-daojie, zhutian-shenzuo(用户内容 3 代备份)
SQLite（sqlite-net）            actorhistory
SQLite（System.Data.SQLite 随包） ancient-warfare-3(118 表档案 + 进程隔离运行时库)
存档目录快照时间线                zhutian-shenzuo(时间神殿)
内存静态字典（会丢失）            familytree, biology(零持久化有意设计 + 反模式实证)
零持久化（纯资产+patch）          funboost, boatrebalancebox, nerffiredamage, unlock-all
```

## Coverage by System（primary）

- **多例子**（≥5 primary）：Actor(12), UI(12), Traits(9), Combat(8), Save/Persistence(8), Mod Lifecycle(5), World(5)
- **中等**（2-4）：Kingdom(4), Utility(4), Buildings(3), Assets(2), City(2), Events(2), Map(2), AI(2)
- **少**（1）：Items, Diplomacy, Boats, Localization, **War**（ancient-warfare-3 新增首个 War primary）
- **仍无 primary**：Jobs, Culture, Religion, Resources, Clan, Alliance（fanren Resources / ancient-warfare Jobs 为 secondary 级）

## Coverage by Technique

- Harmony Prefix：19 mods；Postfix：17；Transpiler：5（guigu, xuanmen, chinesename, fanren, ancient-warfare-3）
- UI injection：15；Asset registration：11；Custom data：11；Reflection：11
- Save/load：5；Localization：5；Event subscription：4

## Knowledge Gaps（27 mods 仍未覆盖的重要领域）

1. **经济/资源循环**（Resources/Mining/Farming/Storage）——fanren 灵石六品经济、zhutian 本源四池均为 secondary 级样本，Resources 仍无 primary 深挖
2. **Jobs/Professions 深度改造**——ancient-warfare 朝廷科举/官职、fanren ProfessionSystem 均为 secondary，仍无 primary
3. **Culture/Religion 创建型 API**——powerbox 有创建神力但未深挖数据结构
4. **Books/Items/Crafting**——fanren 法宝/丹药走 data key 而非 ItemAsset（部分弥补 Items），正式 crafting 链仍空白
5. **多人协作模组间通信**——ancient-warfare api/multiplayer 的 replica 只读 facade 提供首个正面样本；玄鉴仙族未声明 VideoCopilot 硬依赖仍是反面教材
6. **性能工程**——显著增强：optime（Feature 开关）+ guigu/fanren 帧切片 + ancient-warfare 异步调度/主线程时间预算 + zhutian ActorTickGate 门禁；仍缺 profiler 驱动的系统研究

这些缺口应写入 Z8（System Knowledge Map）的待调查清单。
