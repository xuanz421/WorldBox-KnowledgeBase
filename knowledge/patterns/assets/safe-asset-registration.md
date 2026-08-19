# Pattern: safe-asset-registration

## Status

Verified

## Goal

向 AssetManager 注册自定义资产时防止：重复注册、vanilla 代码路径 NRE、热重载重复添加。

## When to Use

任何 `AssetManager.*.add(...)` 调用的 mod——尤其支持热重载（IReloadable）或注册量大时。

## Relevant Systems

Assets, Mod Lifecycle

## Core WorldBox Types

`AssetManager.*`（traits/projectiles/actor_library/powers/name_generator 等各 library）

## Implementation Flow

1. 注册前查重：按 id 检查 library 已存在则跳过（防热重载双注册）
2. 自定义 AssetLibrary&lt;T&gt; 子类时**双注册**：同时向对应 vanilla library add 占位 asset，保证 vanilla 代码路径不 NRE
3. 多类资产统一走注册框架（每类资产一个 register 方法，集中调用）
4. 注册失败 try/catch 隔离，不阻断其他资产

## Reference Implementations

Primary:
- Mod: ref:chinesename — File: Code/CN_NameGeneratorLibrary.cs:91-96 — Symbol: CN_NameGeneratorLibrary
  Why: 自定义 AssetLibrary 子类 + 向 AssetManager.name_generator 占位注册的兼容范本

Alternative:
- Mod: ref:guigu-cultivation — File: Code/Core/ProjectileDefinitionFramework.cs:19-69 — Why: ProjectileAsset 统一注册框架（防重复注册）

## Caveats

- **vanilla NRE 场景**：若 vanilla 遍历某 library 期待非空/特定条目，只注册私有 library 会崩——先确认 vanilla 是否读取该 library
- **热重载**：IReloadable.Reload 会再次调用注册代码，必须幂等（查重或先移除）
- **add 时序**：在 OnModLoad 之外注册需确认 library 已初始化

## Evidence

- ref:chinesename Code/CN_NameGeneratorLibrary.cs:91-96
- ref:guigu-cultivation Code/Core/ProjectileDefinitionFramework.cs:19-69

## Provenance

Derived from: ref:chinesename, ref:guigu-cultivation
