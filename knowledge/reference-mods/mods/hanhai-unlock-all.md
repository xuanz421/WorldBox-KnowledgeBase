# 寒海的全解锁

## Identity

- Name: 寒海的全解锁 v1.2（NCMS 模 mod）
- Source ID: `ref:hanhai-unlock-all`
- Dir: `寒海的全解锁_1.2`
- Files: 4 total / 1 C#
- Confidence: Verified

## Purpose

游戏运行后自动全解锁（成就/科技/生物/基因/密谋等），F9+F10 手动重触发防失效。

## Systems

- Primary: Utility
- Secondary: 无

## Key Implementation

- `Main.cs` (L11-20) — MonoBehaviour.Update 轮询：首帧自动执行 unlockAllAchievements + debugUnlockAll，组合键重触发

## Techniques

NCMS [ModEntry] + Update 轮询、首帧布尔闸避免重复调用

## WorldBox Usage

GameProgress.instance.{unlockAllAchievements,debugUnlockAll} / Input/KeyCode / MonoBehaviour.print

## NeoModLoader Usage

无（NCMS 模）

## Patch Targets

无

## Reusable Ideas

- `GameProgress.debugUnlockAll()` 是全内容解锁的官方后门入口

## Pattern Candidates

- `gameprogress-debug-unlock`

## Evidence

- Main.cs:7-8,10-19

## Notes

组合键判定逻辑冗余；最小可行 mod 样本。
