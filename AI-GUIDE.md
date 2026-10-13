# WBKB — AI 阅读与使用指南

> 当用户提供本仓库链接并要求辅助 WorldBox MOD 开发时，按本指南检索公开知识。**不要求用户安装 WBKB、本地 MCP、SQLite、Python 或 WorldBox 源码。**

## 目标

利用已有的系统知识、已验证的实现模式及参考 MOD 研究，降低开发者重复逆向、重复寻找 API 的成本。WBKB 主要提供**证据化参考资料**，不是直接执行编译、运行游戏或确认当前游戏版本的服务。

## 入口与检索

1. 先查看 [knowledge-index.md](knowledge-index.md)，区分系统（Systems）、模块（Patterns）和模组（Reference Mods）。
2. 从以下目录选择最相关的条目，不要先递归读取整个仓库：
   - [Systems catalog](knowledge/systems/catalog.json)：`systems[].system_id`、`core_types`、`file`；文档位置为 `knowledge/systems/<file>`。
   - [Patterns catalog](knowledge/patterns/catalog.json)：`patterns[].id`、`systems`、`status`、`file`；文档位置为 `knowledge/patterns/<file>`。
   - [Reference Mods catalog](knowledge/reference-mods/catalog.json)：`source_id`、`primary_systems`、`confidence`、`profile`；文档位置为 `knowledge/reference-mods/<profile>`。
3. 优先打开 1–3 篇相关文档；不足时再扩展检索。需要实践示例时优先看 Pattern，需要机制背景时看 System，需要第三方实现证据时看 Reference Mod。
4. 回答时注明具体文档路径（最好附 GitHub 链接）与证据状态，并把源码引用（如 `Actor.cs:123`）标识为**仅供本地源码对照的位置**，不是公开可直接读取的证据全文。
5. 不存在对应条目时回答“WBKB 未收录/当前无法验证”，不要据此断言游戏不存在相应 API。避免自行创造类、字段、方法或补丁入口。

## 版本、可靠性与兼容

- 系统目录目前标识 WorldBox `0.51.2`。不能默认将结论推广到其他版本。
- `Strong Verified`、`Verified` 高于 `Mostly Verified`、`Partial`。 `Inferred`、`Planned` 不代表实机验证。
- 区分 WorldBox 原版、NeoModLoader API 和第三方模组 API，不能混用。
- 如用户提供目标项目代码，优先以用户当前代码为准，再用 WBKB 作为参考；注意实际方法签名和调用时机可能随版本变化。
- 对无法联网/无法读取 GitHub 的客户端，清楚说明访问限制，建议用户贴出相关 Markdown 文件，不得假装已经检索仓库。

## 输出建议

回答尽量包含：可确认的机制或实现方式、关键 API/调用路径、适用版本、相关 WBKB 文档以及仍须在实际游戏中验证的部分。不要为了完整而给出未经证实的代码。

## 维护说明

本指南面向只会读取公开 GitHub 内容的 AI。源码提取、SQLite、测试与研究工具是维护者可选工作流；规则在 [AGENTS.md](AGENTS.md)。不要为了普通用户访问而要求配置本地服务。
