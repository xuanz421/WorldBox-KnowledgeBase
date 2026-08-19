# Pattern Library Gaps

实际调查后仍缺少的高价值 Modding Pattern——未来任务队列，现在不解决。

| 领域 | 缺口 | 现状证据 |
|---|---|---|
| **Custom Job / Profession** | 无法回答"如何添加自定义职业/工作"——21 mods 无一实现，仅 powerbox/sandbox 调用 setProfession | 无 |
| **Resource / Economy** | 注册资源、修改资源循环（采集/运输/存储）零覆盖 | 无 primary 例子 |
| **Custom Item / Crafting** | 注册物品仅有 xuanjian 法宝（单一样本、反编译代码质量低）；合成系统零覆盖 | ref:xuanjian-xianzu（弱） |
| **City 深度行为** | 修改城市建造逻辑/存储访问——仅 xavii LandTypes 挂了生命周期钩子 | ref:xavii-nation-types（部分） |
| **Boats / Transport** | 完全空白 | 无 |
| **Books / Knowledge 系统** | 完全空白 | 无 |
| **Harmony Transpiler 教程级 pattern** | 三 mod 有实现但高风险，未提炼（见 DEFERRED） | chinesename/xuanmen/guigu |
| **模组间依赖/通信** | 仅玄鉴仙族未声明硬依赖 VideoCopilot（反面教材）；无正面模式 | 无 |
| **NML API 面权威清单** | 多处 Unverified 标注的根因（见 reference-mods/unresolved.jsonl）——Z6 API mining 待做 | 无 |
| **性能工程** | 仅 optime + 各大 mod 私有实践，无统一 pattern | 分散 |

这些缺口与 `knowledge/reference-mods/CROSS_MOD_SUMMARY.md` 的 Knowledge Gaps 一致，作为 Z7+/Z8 的输入。
