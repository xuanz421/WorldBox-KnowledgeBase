# WBKB Structured Index Schema v2

v2 = v1 声明层 + 引用层。SQL 定义：`schemas/schema-v2.sql`；v1 文档保留于 `wbkb-schema-v1.md`。数据库由 `python -m wbkb index worldbox` 重建，不进 Git。

## Declaration Layer（同 v1）

`meta / sources / files / types / methods / fields / properties / inheritance / strings`

变化：`files` 增加 `reference_status`（OK/PARTIAL）与 `reference_error`——声明解析与引用提取状态分离。

## Reference Layer（v2 新增）

| table | 内容 |
|---|---|
| `symbol_references` | 成员访问（field/property 读写）。`reference_kind`: read/write/read_write/type_use/…；`target_logical_key` 稳定身份（如 `field:Actor.data`，未解析为 `field?hint`）；`target_id` 仅在 resolved 时填写 |
| `method_calls` | 调用边：caller → callee（含 `.ctor`）。`callee_signature_hint` / `declaring_type_hint` 保留解析线索；`resolution_status`: resolved / ambiguous / unresolved / external |
| `type_references` | 类型使用：instantiate / parameter_type / return_type / field_type / property_type / typeof / cast / as / generic_argument / inherit / interface / attribute / type_use |

## Resolution Status 约定

- **resolved**：receiver 类型 + 成员在声明层唯一确定（继承链查找，最近声明优先；方法按名+参数个数过滤）。
- **ambiguous**：overload 无法唯一确定（如两个同参数个数重载）——保留候选，绝不随机选择。
- **unresolved**：receiver 类型未知（如未推导的 var、接口回调参数）——保留引用行，`target_id=NULL`。
- **external**：目标在外部库（UnityEngine/System 等）——保留名字提示，默认查询可隐藏。

## Logical Identity

- type: `source_id + full_name`（嵌套 `Outer.Inner`）
- method: `source_id + declaring_type + signature`（如 `Actor.hit(int)`）
- field/property: `source_id + declaring_type + name`

引用行的 `target_logical_key` 使用同一约定；数据库重建后内部 row id 可能变化，logical key 稳定。

## 已知边界（best-effort，precision 优先）

- virtual/interface 调用链接到 compile-time 目标；`wbkb overrides` / `wbkb derived` 经 inheritance graph 独立计算。
- 不解析：复杂泛型推断、lambda/LINQ、delegate、dynamic、reflection、字符串→symbol。
- 预定义类型（int/void/…）不产生 type_reference。
