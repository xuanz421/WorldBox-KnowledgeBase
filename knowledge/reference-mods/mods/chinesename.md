---
title: ChineseName
aliases:
  - chinesename
---

# ChineseName（中文名）

## Identity

- Name: ChineseName v1.5.0new
- Source ID: `ref:chinesename`
- Dir: `ChineseName_1.5.0new`
- Files: 154 total / 23 C#
- Confidence: Verified

## Purpose

用中文词库+模板引擎替换全游戏命名（单位/城市/王国/宗教/文化/战争/氏族/物品/书/语言/亚种/联盟）。数据驱动：name_generators/word_libraries 目录 JSON+文本，支持热重载（IReloadable）。

## Systems

- Primary: Utility（命名）, Assets, Mod Lifecycle
- Secondary: Save/Persistence（actor data family_name）, Events, Culture/Religion/City/Kingdom（patch 目标）

## Key Implementation

- `Code/ModClass.cs` (L33-50) — BasicMod+IReloadable，反射扫描 IPatch 自动注册全部 patch
- `Code/Patches/ActorNamePatch.cs` (L15-59) — Actor.getName Prefix + turnIntoZombie/Skeleton Transpiler；family_name 经 actor data 遗传
- `Code/CN_NameGeneratorLibrary.cs` (L61-105) — 自定义 AssetLibrary<CN_NameGeneratorAsset>，同步向 vanilla name_generator 注册占位 asset 保证兼容
- `Code/CN_NameTemplate.cs` (L62-107 GenerateName, L118-415 Parse) — 原子化模板解析（atoms + required_parameters）+ 拓扑排序，[Hotfixable] GenerateName
- `Code/WordLibraryManager.cs` (L41-52) — 文本词库（每行一词）→ WordLibraryAsset，SubmitDirectoryToLoad

## Unique Methods

筛选口径：剔除补丁接线与注册样板后，承载核心机制且原版无对应物的模组自有方法。

- `CN_NameTemplate.Parse` (Code/CN_NameTemplate.cs:118-415) — 字符级状态机解析模板（`{} <> $ # :` 定界，Parameter/RawText/WordLibrary 三原子），尾部按 tag 依赖做拓扑排序得 atoms_before_generate（L364-414）
- `CN_NameTemplate.GenerateName` (Code/CN_NameTemplate.cs:62-107) — [Hotfixable] 生成：先按拓扑序填充 tag 原子，再拼接三类原子，必填词库取词为空则整体返回空串
- `CN_NameTemplateAtom.GetFilledTemplate` (Code/CN_NameTemplate.cs:434-456) — 参数键依次查 actor 参数表→`ModClass.GlobalParameters`，string.Format 填充原子
- `CN_NameGeneratorLibrary.Submit` (Code/CN_NameGeneratorLibrary.cs:61-105) — 逐模板 Parse 失败剔除 + 双注册：add 自身库同时向 `AssetManager.name_generator` 补占位 NameGeneratorAsset（L91-97）
- `WordLibraryManager.SubmitDirectoryToLoad` (Code/WordLibraryManager.cs:41-50) — 文本词库整目录（每行一词）加载为 WordLibraryAsset，`submitted_dir` 去重支撑 IReloadable 热重载
- `ActorNamePatch.set_actor_name` (Code/Patches/ActorNamePatch.cs:23-59) — Prefix 仅空名时生成；family_name 从父母 data（男性优先，L42-51）遗传并回写 `data.name`/`data.family_name`
- `ActorNamePatch.undead_creature_name` (Code/Patches/ActorNamePatch.cs:61-67) — Transpiler 把 IL 字面量 `"Un"` 换成 `"亡-"`（僵尸/骷髅前缀）
- `ModClass.Update` (Code/ModClass.cs:12-18) — 每帧运行 `ParameterGetters.global_parameter_getters` 刷新全局模板参数（反射扫描注册在 L33-50）

## Techniques

反射自动发现 IPatch 实现类并 Invoke Initialize（程序集扫描）、自定义 AssetLibrary<T> 子类、Harmony manual Patch + AccessTools、Transpiler 修改字符串字面量（"Un"→"亡-"）、[Hotfixable]、委托参数获取器 (parameter_getter)

## WorldBox Usage

Actor.getName / Actor.GetNameTemplate / ActionLibrary.{turnIntoZombie,turnIntoSkeleton} / Kingdom.{newCivKingdom,getMotto} / City.generateName / Religion.generateName / WarManager.newWar / Actor.data.get/set / MetaType

## NeoModLoader Usage

- BasicMod / IReloadable.Reload / NeoModLoader.api.attributes.Hotfixable（Verified）
- AssetLibrary<T> 继承 + Instance 单例约定（Verified）；GeneralUtils.DeserializeAllFromLoad 为 mod 自带（Verified 非 NML）

## Patch Targets

| Target | Type | File | Purpose |
|---|---|---|---|
| Actor.getName | Prefix(set_actor_name) | Patches/ActorNamePatch.cs:15 | 空名时生成中文名并写回，return true 放行原逻辑 |
| ActionLibrary.turnIntoZombie | Transpiler | Patches/ActorNamePatch.cs:17-20 | IL Ldstr "Un"→"亡-" |
| City.generateName | Prefix | Patches/CityNamePatch.cs:14 | 城市名 |
| Kingdom.newCivKingdom | Prefix | Patches/KingdomNamePatch.cs:15 | 王国名 |
| WarManager.newWar | Prefix | Patches/WarNamePatch.cs:12 | 战争名 |
| Religion.generateName | Prefix | Patches/ReligionNamePatch.cs:11 | 宗教名 |

## Reusable Ideas

- IPatch 接口 + 程序集反射扫描：每个 patch 自包含 Initialize()，入口零改动扩展（ModClass.cs L33-50）
- 双注册兼容：自定义 generator 同时向 AssetManager.name_generator add 占位，vanilla 代码路径不 NRE（CN_NameGeneratorLibrary.cs:91-96）
- "Prefix 填充后放行"：只在 data.name 为空时生成并写回，return true 保留原版行为——非破坏式 hook
- IReloadable + submitted_dir 集合实现词库热重载不清档（WordLibraryManager.cs:19-29）

## Pattern Candidates

- `assembly-scan-auto-patch-registration`
- `dual-asset-registration-compat`
- `transpiler-literal-replace`
- `non-destructive-prefix-fill-and-pass`

## Evidence

- ModClass.cs:8,33-50 — 入口与自动注册
- ActorNamePatch.cs:15-20,25,42-56 — 核心 patch
- CN_NameGeneratorLibrary.cs:8,91-96 — 双注册
- CN_NameTemplate.cs:61-69 — 模板
- WordLibraryManager.cs:6-13,41-52 — 词库

## Notes

最干净的 patch 组织范本，推荐作为 Harmony patch 工程化参考。
