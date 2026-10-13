# WorldBox Knowledge Base (WBKB)

**面向 WorldBox MOD 开发者的公开知识库。** 收录 WorldBox 系统机制、经过验证的模组开发模式，以及参考模组的实现研究。

**无需安装 WBKB、下载游戏源码、启动服务或配置 MCP。** 将本仓库链接提供给能够访问 GitHub 内容的 AI，即可让它按需读取知识文档，辅助 MOD 开发。

> AI 使用入口：[AI-GUIDE.md](AI-GUIDE.md) · 知识导航：[knowledge-index.md](knowledge-index.md)

## 给 AI 使用（复制即可）

```text
开发 WorldBox MOD 时，请参考这个知识库：
https://github.com/xuanz421/WorldBox-KnowledgeBase

先阅读 README.md 和 AI-GUIDE.md，再通过 knowledge-index.md 和 knowledge/ 下的三个 catalog.json 定位相关文档。
按需读取文档，优先使用已验证证据；保留真实的 C# API/类型/方法名，并注明知识条目与证据等级。
不要假设仓库包含完整游戏源码或本地数据库；未收录、未验证的内容明确说明，不要编造 API。
```

**使用前提**：AI 必须具备 GitHub 网页读取、仓库文件读取或联网浏览能力。仅在聊天框粘贴链接并不保证所有 AI 都能访问仓库；若客户端无法访问，可手动提供相关 Markdown 文件。

## 查找知识

| 想解决的问题 | 从这里开始 |
| --- | --- |
| WorldBox 系统如何运作、核心类型有哪些 | [系统索引](knowledge/systems/system-index.md) · [系统目录 JSON](knowledge/systems/catalog.json) |
| 某类 MOD 功能如何实现 | [模块索引](knowledge/patterns/module-index.md) · [模式目录 JSON](knowledge/patterns/catalog.json) |
| 其他模组如何实现某功能 | [参考模组索引](knowledge/reference-mods/mod-index.md) · [模组目录 JSON](knowledge/reference-mods/catalog.json) |

阅读顺序：**定位具体问题 → 查对应目录 → 读相关文档 → 检查状态和证据 → 仅在必要时扩大检索**。不要一开始读取整个仓库。

## 版本与证据

系统目录标记 WorldBox **0.51.2**；其他条目以各自文档标注的来源和状态为准。仓库中验证过的模式不保证在其他游戏版本中兼容。

- `Strong Verified` / `Verified`：有较强或直接证据，但仍须留意适用版本。
- `Mostly Verified` / `Partial`：存在尚未完整验证的部分。
- `Inferred` / `Planned`：推断或计划，不应当作已实现的游戏 API。

源码路径和行号属于**证据定位信息**，不表示 GitHub 上公开了完整反编译源码。

## 开发者与维护者（可选）

已有的本地源代码提取、SQLite 索引、CLI 和研究工具仍保留在 [tools/](tools/)；它们用于持续构建与验证知识，**不是普通使用者的前置条件**。

维护规则见 [AGENTS.md](AGENTS.md) 和 [knowledge-organization-rules.md](knowledge-organization-rules.md)。原始 DLL、完整反编译快照与生成数据库不发布到此仓库。
