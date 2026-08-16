# Cross-Mod Summary

21 个 Reference Mods 的横向对比。分层：Tier A（核心玩法/系统深度）9 个、Tier B（单功能有技术价值）8 个、Tier C（微型/本地化）4 个。

## Most Valuable References（按技术价值）

| Mod | 一句话用途 |
|---|---|
| **chinesename** | Harmony patch 工程化范本：IPatch 接口+程序集扫描自动注册、双注册兼容、非破坏式 hook——任何新 mod 的组织结构首选参考 |
| **powerbox** | NML Feature 体系权威样本：40+ 神力全部走 ModAssetFeature/ModButtonFeature 自动发现，零样板 |
| **xavii-nation-types** | 王国/政体/外交系统改造全链路：定义表驱动+KingdomTrait+custom_data+行为树 tick 入口 |
| **guigu-cultivation** | 大型世界级模拟的工程实践：分帧切片、读档牺牲窗、Phase 延迟加载、逐补丁隔离 |
| **xuanmen-daojie** | 深度 Actor 改造：stats/data 双轨持久化、updateStats Transpiler、BatchActors 系统总线 |
| **actorhistory** | 事件观察类 mod 范本：40+ 事件钩子→分类叙事→SQLite 世界键隔离存储 |
| **optime** | Feature<T> 配置热切换补丁框架（54 行可移植）+ 高帧率模拟修复 |
| **sandbox** | 泛型类 manual Harmony patch 配方 + powers.clone 落地神力模板 |
| **familytree** | 死亡快照模式 + 纯 UGUI 平移缩放关系图 |
| **mapdeal** | 零 Harmony 深度地图操作：反射 tiles_map + SmoothLoader 生成链复刻 |

## 覆盖：Harmony 三种组织法

```text
逐类 CreateAndPatchAll（故障隔离）   guigu-cultivation, xuanjian-xianzu
Assembly.PatchAll（一次挂载）        xavii-nation-types, xuanmen-daojie, actorhistory
程序集扫描自动发现                   chinesename（扩展性最佳）
Manual CreateProcessor（泛型类）     sandbox
```

## 覆盖：神力/系统入口

```text
NML Feature 体系          powerbox
powers.clone + DropAsset  sandbox, powerbox
WorldBehaviourAsset 闭包  shtoolkit
行为树节点 Prefix tick    xavii-nation-types, guigu-cultivation(BatchActors)
```

## 覆盖：持久化频谱

```text
actor.data 字符串键（随存档）   guigu, incensefiredway, xuanmen-daojie, chinesename
map_stats.custom_data（世界级） thefantasyworld, xuanmen-daojie, actorhistory(世界键)
存档槽目录文件                   guigu
persistentDataPath JSON         shtoolkit, xuanmen-daojie
SQLite（sqlite-net）            actorhistory
内存静态字典（会丢失）           familytree——已知反例
```

## Coverage by System

- **多例子**（≥5 primary）：Actor(5), Traits(6), UI(5)
- **中等**（2-4）：Kingdom(3), Combat(4), Save/Persistence(4), Buildings(3), Assets(2), World(2), Events(2), Map(2), Mod Lifecycle(2), Utility(2)
- **少/无例子**：Jobs(0), Professions(0), Diplomacy(1), Culture(0 primary—仅 powerbox secondary), Religion(0 primary), Resources(0), Items(1), Equipment(1), Boats(0), Books(0), Mining/Farming(0), Localization(1)

## Coverage by Technique

- Harmony Prefix：14 mods；Postfix：11；Transpiler：3
- UI injection：9；Asset registration：9；Custom data：8；Save/load：7
- Reflection：6；Localization：3；Event subscription：2

## Knowledge Gaps（21 mods 未覆盖的重要领域）

1. **经济/资源循环**（Resources/Mining/Farming/Storage）——无任何 primary 例子
2. **Jobs/Professions 深度改造**——仅 powerbox/sandbox 顺带调用 setProfession
3. **Culture/Religion 创建型 API**——powerbox 有创建神力但未深挖数据结构
4. **Boats/海运、Books、Items/Crafting**——几乎空白
5. **多人协作模组间通信**——玄鉴仙族的未声明 VideoCopilot 硬依赖是唯一直接证据（反面教材）
6. **性能工程**——仅 optime；大型中文 mod 的分帧实践（guigu/xuanmen）可部分弥补

这些缺口应写入 Z8（System Knowledge Map）的待调查清单。
