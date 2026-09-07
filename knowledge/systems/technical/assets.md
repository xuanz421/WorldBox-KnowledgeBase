# System: Asset Framework

WorldBox 资产框架的系统级调查。基于 worldbox-0.51.2-51d275f0168b 源码直接阅读 + NML 交叉验证。

## Scope

覆盖：Asset/Library/AssetManager 三层模型、注册与 ID 管理、duplicate 行为、初始化三阶段（init → post_init → linkAssets）、clone 机制、模板资产、库生命周期、与 NML mod 加载的时序关系。

不覆盖：各具体 Library 的业务语义（traits 见 entity/traits.md；其余系统独立调查）、NML ResourcesPatch 资源文件加载内部（仅入口级）、JSON 资源文件格式细节。

## Core Types

| 类型 | 职责 | 位置 |
|---|---|---|
| `Asset` | 资产抽象基类：`id : string`、create() 钩子、hash/index 身份 | Asset.cs:4-57 |
| `AssetLibrary<T>` where T : Asset | 泛型库：list + dict 双索引、add/get/clone | AssetLibrary.cs:8-232 |
| `BaseAssetLibrary` | 库基类：init/post_init/linkAssets 三阶段、JSON 导入导出 | BaseAssetLibrary.cs:10-190 |
| `AssetManager` | 静态门面：~134 个静态库字段、启动装配、按名查库 | AssetManager.cs:7-503 |

三个核心问题的回答（本文件主旨）：

```text
Asset 是什么？    —— 一个有字符串 id 的可序列化定义对象（数据 + 委托钩子），
                    create() 是它被 add 进库时的一次性初始化钩子。
Library 是什么？  —— 同类资产的容器：List（有序/可枚举）+ Dict（id 查找）双结构，
                    并负责该类资产特有的 init/link 后处理。
AssetManager 是什么？—— 启动期装配器 + 静态访问门面：创建全部库、驱动三阶段、
                    之后以静态字段形式供全游戏访问。
```

## Data Model

- **Asset 身份**：`id`（字符串，默认 "ASSET_ID"，Asset.cs:10）；`setHash(BaseAssetLibrary._latest_hash++)` 全局自增（Asset.cs:20-23）——`Equals/GetHashCode` 基于 hash 而非 id；`setIndexID(list.Count)` 列表位置（Asset.cs:25-33）
- **模板资产**：`isTemplateAsset()` —— id 以 `$` 或 `_` 开头（Asset.cs:45-56）：`add` 时进 dict 但**不进 list**（AssetLibrary.cs:74-77），即 get 可查、枚举不可见。原版示例：`$basic_unit$`（ActorAssetLibrary.initTemplates）
- **库双索引**：`list : List<T>`（序列化载体、遍历、getArray 缓存源）+ `dict : Dictionary<string,T>`（O(1) 查找）+ `_not_found : HashSet<string>`（未命中 id 记录，AssetLibrary.cs:12-23）
- **JSON 序列化**：Newtonsoft + `DelegateConverter`（BaseAssetLibrary.cs:27-55）——**委托可 JSON 往返**（这是 trait action 委托能存在 JSON 资产里的基础）；另有 `JsonUtility.FromJson` 的 `loadFromFile<TAssetLib>()`（AssetLibrary.cs:128-134，Resources 路径）
- **序列化开关**：`loadFromFile` 用 Unity JsonUtility；导出/导入用 Newtonsoft 全功能序列化（exportAssets/importAssets，BaseAssetLibrary.cs:65-105）

## Lifecycle / Flow

### 游戏启动装配（Verified）

```text
InitLibraries.Awake() (Unity 场景)                    InitLibraries.cs:10-13
 → initLibs() → initMainLibs()                        InitLibraries.cs:49-62
   Config → LogHandler → AssetManager.initMain()      （创建实例 + 早期库：
   InitLibraries.cs:43; AssetManager.cs:282-300        game_languages / options）
   → GameProgress → PlayerConfig → LocalizedTextManager
 → AssetManager.init() → initLibs()                   InitLibraries.cs:57; AssetManager.cs:290-293
   for 每个库：add(library, name)                      AssetManager.cs:302-432
     ├─ pLibrary.init()   ← 原版资产在此载入           AssetManager.cs:~466
     │   （两种来源：代码定义，如 ActorTraitLibrary.addTraits*；
     │     JSON 文件，如 loadFromFile(Resources)）
     └─ 注册进 _list/_dict（版本门控 _assetgv[0]=='0'）
   for 每个库：post_init()                             AssetManager.cs:433-436
   for 每个库：linkAssets()                            AssetManager.cs:437-440
```

三阶段语义：
- **init**：装载/定义资产（库自治，可 JSON 可代码）
- **post_init**：依赖本库已全量的后处理（排序、rarity 自动分级、钩子补挂）
- **linkAssets**：**跨库** id → 对象解析（opposite 反向解析、combat/spell/decision 挂接、ActorAsset.traits → default_for_actor_assets 反向索引、加权池构建）

### 注册与 ID 管理（Verified）

```text
AssetLibrary<T>.add(asset)                            AssetLibrary.cs:55-81
  1. dict 已含同 id → 从 list 移除旧项 + dict.Remove
     + logAssetError("duplicate asset - overwriting")  ← last-wins 覆盖
  2. t.create()（资产一次性初始化钩子）
  3. setHash(_latest_hash++)；非模板 → list.Add
  4. setIndexID(list.Count)；dict.Add(id, asset)
```

- 查找：`get(id)` dict 命中返回；miss → null + `_not_found` 记录（AssetLibrary.cs:27-35）
- `has(id)` / `getSimple(id)` / `getArray()`（缓存快照，AssetLibrary.cs:136+）
- 库级查库：`AssetManager.get(library_name)` / `has` / `getList()`（静态，AssetManager.cs）

### clone（Verified）

```text
AssetLibrary<T>.clone(newId, fromId)                  AssetLibrary.cs:83-90
 → clone(out T pNew, T pFrom)                         AssetLibrary.cs:92-126
   Activator.CreateInstance<T>() + 反射复制全部 public instance 字段：
   string 按值 / ICloneable 调 Clone() / ICollection·IEnumerable 走拷贝构造 /
   其余按引用赋值 → add(t)（走完整注册流程）
```

注意：引用赋值分支意味着非 Cloneable 非集合的类字段是**共享引用**——clone-modify-asset pattern 中修改嵌套可变对象会影响原资产的根因（Inferred，由反射复制规则直接推出）。

### 库生命周期与 NML 时序（Verified）

- `AssetManager.clear()` 置空单例（世界清理时用，AssetManager.cs:277-280）；库实例随 initLibs 重建
- NML：`Config.game_loaded == true` 之后才开始 SmoothLoader 分阶段管线（NML WorldBoxMod.cs:87-121）：
  1. Initialize NML（ResourcesPatch/locales/TabManager/ListenerManager…）
  2. 发现 mods + 依赖求解 + 编译准备
  3. 逐 mod 编译 + 资源加载（`ResourcesPatch.LoadResourceFromFolder`）
  4. `ModCompileLoadService.loadMods` + **`Builder.BuildAll()`（MasterBuilder：NML 资产构建器批量注册）** + IStagedLoad mod 逐个 Init / PostInit
  5. NML 后初始化

**何时可安全访问**：AssetManager 静态字段自 `initLibs` 后全程可访问；但"原版库内容已齐备 + linkAssets 已跑完"的时点是游戏加载完成（`Config.game_loaded`）——NML mod 的 Init 即在此之后。mod 注册的新资产晚于 linkAssets（opposite 解析/加权池/反向索引不会为其重跑——traits.md 已记录该 caveat）。

## Important APIs

| API | 说明 | 位置 |
|---|---|---|
| `AssetManager.<lib>` | ~134 个静态库字段（actor_library/traits/buildings/items/powers/…) | AssetManager.cs:9-265 |
| `library.add(asset)` | 注册（last-wins 覆盖 + create() 钩子） | AssetLibrary.cs:55 |
| `library.get(id)` / `has(id)` | 查找（miss → null） | AssetLibrary.cs:27, 50 |
| `library.clone(newId, fromId)` | 反射深拷贝 + 注册 | AssetLibrary.cs:83-126 |
| `library.list` / `getArray()` | 枚举（模板资产不在内） | AssetLibrary.cs:12, 136 |
| `AssetManager.get(libName)` | 按库名查库 | AssetManager.cs |
| `BaseTraitLibrary` 家族 | 8 个 trait 型库共享基类（opposite/池逻辑） | BaseTraitLibrary.cs:4-315 |

## Extension Points

1. **注册新资产**：`AssetManager.<lib>.add(...)`（受 last-wins 覆盖影响 → 重载时需防重复，pattern safe-asset-registration）
2. **派生资产**：`library.clone(newId, fromId)` 后修改（pattern clone-modify-asset）
3. **JSON 资产加载**：NML `ResourcesPatch.LoadResourceFromFolder` + MasterBuilder（mod 目录资源自动注册，跨源 Verified）
4. **查找安全**：始终处理 `get` 返回 null（含 `_not_found` 静默记录）
5. **模板前缀**：`$`/`_` 开头 id 可注册"不可枚举"资产（dict-only）

## Evidence

| 结论 | source | location |
|---|---|---|
| 三层模型与启动装配 | worldbox | InitLibraries.cs:10-62; AssetManager.cs:282-300, 302-441 |
| add last-wins 覆盖 + create 钩子 | worldbox | AssetLibrary.cs:55-81 |
| get/has/_not_found | worldbox | AssetLibrary.cs:27-53 |
| clone 反射复制规则 | worldbox | AssetLibrary.cs:83-126 |
| 模板资产 $/_ 前缀 | worldbox | Asset.cs:45-56; AssetLibrary.cs:74-77 |
| 委托可 JSON 往返（DelegateConverter） | worldbox | BaseAssetLibrary.cs:27-55 |
| 三阶段 post_init/linkAssets 顺序 | worldbox | AssetManager.cs:433-440 |
| 原版资产代码定义示例 | worldbox | ActorTraitLibrary.cs:28-38; ActorAssetLibrary（initTemplates/initCivsClassic/initAnimalsNormal） |
| NML 加载时序与 MasterBuilder | neomodloader | WorldBoxMod.cs:87-229（NeoModLoader/NeoModLoader/） |
| NML 动态资产构建器存在 | neomodloader | NeoModLoader.utils.Builders（ActorTraitBuilder/ActorAssetBuilder 等） |

## Confidence

- Verified：全部机制结论（标注行号）；NML 时序为跨源 Verified
- Inferred：clone 引用共享分支对 modding 的影响（由反射规则直接推出，未做运行时验证）
- Unknown：见 Known Gaps

## Known Gaps

- `ResourcesPatch`/`MasterBuilder` 内部：mod JSON → Asset 的字段映射规则、AssetBundle 加载（NML 源深挖任务）
- 版本门控 `_assetgv[0] == '0'` 的完整语义（`Config.gv = Application.version`，InitLibraries.cs:24；门控行为仅在 0.x 版本验证过）
- `exportAssets/importAssets`（GenAssets/wbassets）在正式游戏中的实际用途（疑似开发期工具）
- ~~各业务 Library 的 post_init/linkAssets 特有逻辑清单~~ **S 级库已覆盖（2026-09-08 audit）**：traits（加权池/opposite/反向索引）、resources（strategic/order/sprite/diet）、citizen_jobs（三张优先级列表）、items（subtype/词缀池/unlock 池）、buildings（Architecture 派生）——逐库细则见各系统文档；A/B 级库（culture/combat/world 等）待各自 harvest 补充
- NML `NCMSCompatibleLayer` 兼容层的资产桥接行为

## Related Patterns

- [register-actor-trait](../../patterns/assets/register-actor-trait.md) — add() 的 modding 用法
- [clone-modify-asset](../../patterns/assets/clone-modify-asset.md) — clone() 的 modding 用法与共享引用 caveat
- [safe-asset-registration](../../patterns/assets/safe-asset-registration.md) — last-wins 覆盖的防御模式
- [register-godpower](../../patterns/assets/register-godpower.md) — PowerLibrary 注册
- [nml-feature-authoring](../../patterns/lifecycle/nml-feature-authoring.md) — NML 构建器路线
