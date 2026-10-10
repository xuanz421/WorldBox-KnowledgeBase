---
title: NML source mod acceptance, clean delivery and artifact retention
aliases:
  - NML 验收与玩家目录交付
  - NEWERA_TESTS isolation
---

# Pattern: nml-acceptance-release

## Status

Verified — NewEra 1.0.0 / WorldBox 0.51.2。编译、测试副本隔离、玩家初始化及逐文件同步有既有证据；不代表已经公开发布。

## Goal

把开发 probe 与纯玩家 source mod 分开，明确验收证据边界，并限制高频截图和测试副本的累积。

## When to Use

NML 在游戏内编译的 source mod，需要隔离回归、受控实机、world reload、UI capture、指定实例同步或结束一轮开发后的产物整理。

## Relevant Systems

NML, Mod Lifecycle, Testing, Release, UI, Save/Persistence

## Implementation Flow

1. 工程编译引用与测试实例的 publicized `Assembly-CSharp`、NML、Harmony、Unity modules 一致。NewEra `net48` 使用游戏 Managed 作为 `FrameworkPathOverride`；Debug 定义测试符号，Release 排除 Tests。
2. `dotnet build` 只验证语法和可用 API；NML 实际重新编译模组文件。WBKB NML snapshot 的 `ModCompileLoadService.cs:98` 递归扫描 mod folder 的 `.cs`，并跳过指定目录，不应推广成“永远只扫描 Source”。安全交付靠顶层白名单和去除开发源码。
3. 测试复制到独立游戏实例：Source / resources / locales / configuration 加 `Tests`，对测试副本每份源码显式添加 `#define NEWERA_TESTS`。不能只依赖 IDE Debug 属性影响 NML。
4. 分开运行 isolated regression、controlled native consumption、full world reload、focused UI、long-run observation；报告使用 `PASS / INFO / FAIL`。`INFO` 不折算成 PASS，外围脚本退出失败也必须记录。
5. UI capture 同时核对文件非零、画面非黑、真实对象 active/title/bounds；只在需要画面的 probe 显示游戏窗口。不能为截屏直接改变生产 tooltip 或世界机制。
6. 玩家导出只拷白名单：`Source`, `Locales`, `GameResources`, `mod.json`, `default_config.json`, `icon.png`。剥离开发 conditional blocks，不带 Tests、额外 DLL、工程、开发文档或 probe 参数入口。
7. 逐文件比较导出与用户指定正式实例的 SHA256，同时比较相对路径集合；只比文件数不足以发现 stale 文件。旧副本放到 mods 之外，避免两个副本同时被加载。
8. 修改源码并同步后重启游戏。NML ModListWindow 热更按钮被 `Config.isEditor` 限制，不能向普通玩家承诺可用；方法体 hotfix 也不等于能加新类型和字段。

## Reference Implementations

- `consumer:NewEra@fe2d2c88320e8a3d6544b2f5b2f0b3bf88c645ef`: `NewEra.csproj`, `Scripts/game-test-common.ps1`, `Scripts/test-culture-nodes.ps1`, `Scripts/run-acceptance-probe.ps1`, `Scripts/export-mod.ps1`。
- NewEra `Source/ModClass.cs:27` 测试入口与 `Tests/CultureNodeValidation.cs:97` 回归分层。
- Related pattern IDs: `native-window-log-integration`, `harmony-safe-batch-patching`。

## Pixel Asset Pipeline

- NewEra 的目标图是 32×32 PNG、最多 32 色、alpha 仅 0/255、无 dithering；主 icon 用 nearest-neighbor 放大至 64×64。这是该消费者对原版观感的约束，不是 NML 的强制格式。
- 用 `Scripts/icon-recipes.json` 维护 node ID 到原稿／native sprite／detail variant 的对应关系；原稿与 prompt 留在 `bin/artwork-originals`，最终运行图进入 `GameResources`。
- `Scripts/prepare-icons.py:35` 做 alpha threshold、crop、nearest resize 和 quantization。保留原版 sprite 色调；共享暖色 palette 对草药等特殊题材可能造成色义错误，需按素材处理。
- `blueprint` 配方生成独立纸张图，同时保留 `nodes/<id>.png` 成品图；不能为了图纸展示覆盖唯一成品资产。等级可以通过材质／结构变化并配合非交互 Text 编号，不必重复生成装饰外框。
- 同时查看实际 32×32、放大预览与游戏内 tooltip；大图辨识度不能替代小图检查。preview 可重建，原稿和 prompt 应保留。

## Artifact Retention

这是根据已发生体积问题提炼的维护建议，不是声称现有脚本已经自动执行的 retention policy。

- 保留最新全绿完整基准、最新完整失败、最新专项、全部历史报告／诊断日志，以及文档实际引用的代表图和失败截图。
- 失败后专项通过不覆盖最后全绿基准，不删除历史失败，不宣称未知根因已修复。
- 仓库历史证据可收敛为原始计数、诊断、FAIL 与 stack trace；保留 raw report 路径和 SHA256。内容 hash 相同不证明两个路径来自同一运行。
- 素材原稿、生成 prompt、配方、存档 fixture 与正式同步 rollback 副本是单独资产；不能把所有 `bin` 当可无脑删除的 cache。
- 高频旧截图、obsolete package 和测试源码副本可移到项目外可恢复归档。归档清单记录原相对路径、size、SHA256；先核对边界和 protected 文件，再移动并复核。
- NewEra 此次整理前 `bin` 约 1276.55 MiB，根目录 1808 张 PNG 约 1005.13 MiB；源码约 0.18 MiB。主要成本来自验收截图积累，不是玩法代码或运行依赖。
- 项目外移动只减少项目目录体积，不释放磁盘空间；忽略目录里的原件不会随 Git push 或 clone 传递。

## Caveats

- NewEra export regex 仅适用于当前已知、无嵌套的开发 conditional block 格式；不能推广成任意 C# preprocessor parser。
- 不为知识整理启动游戏、覆盖用户设置或改写存档。用户正式同步授权与测试实例同步范围要区分。
- “214 个文件逐项一致”只是该版交付证据，不是所有模组应有的固定数量；只初始化通过也不等于完整 gameplay 通过。
- 如 consumer commit 曾由有改动的 working tree 导出，需明确记录，不能标成纯 HEAD 构建。

## Evidence

- NewEra `Source/ModClass.cs:27`, `:34`; `Tests/CultureNodeValidation.cs:97`；对应工程和 PowerShell 入口如上。
- NML snapshot `neomodloader-02266fe8185d`: `NeoModLoader/NeoModLoader.services/ModCompileLoadService.cs:98`; `NeoModLoader/NeoModLoader.ui/ModListWindow.cs:209`, `:234`。
- NewEra 既有台账：Debug / Release 零 warning、零 error；最新玩家目录与指定 OWL 正式目录 214/214 SHA256 一致；历史纯玩家启动传 probe 参数仍不生成报告。
- 当前完整成功、最新完整失败和 focused settings 的具体数字分别见本次三个 companion pattern 的证据段；以 stable IDs 引用，不重复维护报告明细。

## Provenance

来源仓库 `https://github.com/xuanz421/NewEra`，consumer commit 为上述固定版本。2026-10-10 同时记录产物体积审计与可恢复归档方法；既有验收台账位于 consumer `Doc/第一计划/第四阶段验收记录.md`。不把截图、游戏程序集、存档或完整外部源码提交 WBKB。
