# Pattern: harmony-safe-batch-patching

## Status

Verified

## Goal

组织大量 Harmony patch 的注册方式：单补丁失败不炸全 mod，且可扩展、可卸载。

## When to Use

patch 数量超过 ~10 个，或目标方法在不同版本可能缺失时。

## Relevant Systems

Patching, Mod Lifecycle

## Core WorldBox Types

（目标任意；组织方式在 Harmony 层）

## Implementation Flow

三条已验证路线：

1. **逐类隔离**：对每个 patch 类单独 `try { Harmony.CreateAndPatchAll(type, id); } catch {}`——失败只跳过该类（guigu/xuanjian 推荐，兼容性最好）
2. **程序集扫描**：定义 `IPatch { void Initialize(); }` 接口，入口反射 `Assembly.GetTypes()` 找实现逐个 Invoke——新增 patch 零入口改动（chinesename，扩展性最佳）
3. **一次性 PatchAll(Assembly)**：`harmony.PatchAll(typeof(X).Assembly)`——最简但单点失败全炸（xavii/xuanmen；适合目标稳定的 UI 类 patch）

需运行时卸载：每功能独立 Harmony 实例 + UnpatchSelf（optime Feature 框架）。

## Reference Implementations

- Route 1: ref:guigu-cultivation — Code/ModEntry.cs:231-239（try/catch 循环）
- Route 2: ref:chinesename — Code/ModClass.cs:33-50（IPatch 扫描）+ Code/Patches/IPatch.cs（6 行接口）
- Route 3: ref:xavii-nation-types — Code/Features/Harmony.cs:14
- 卸载式: ref:optime — Feature.cs:20-34（PatchAll/UnpatchSelf + 配置回调）

## Caveats

- 静默 catch 会掩盖真实错误——catch 内必须 LogService 记日志（guigu 有完整日志）
- Route 3 的失败域是整个程序集，谨慎用于 patch 目标易变的 mod

## Evidence

- ref:guigu-cultivation Code/ModEntry.cs:231-239 / ref:xuanjian-xianzu InterestingTrait.cs:77-146
- ref:chinesename Code/ModClass.cs:33-50 / ref:optime Feature.cs:20-34

## Provenance

Derived from: ref:guigu-cultivation, ref:xuanjian-xianzu, ref:chinesename, ref:xavii-nation-types, ref:optime
