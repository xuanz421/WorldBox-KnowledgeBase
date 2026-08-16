# WBKB Structured Index Schema v1

数据库由 `python -m wbkb index worldbox` 自动重建（`data/generated/index/wbkb.db`），不进 Git。SQL 定义见 `schemas/schema-v1.sql`。

## Tables

| table | 内容 | logical identity |
|---|---|---|
| `meta` | 数据库自描述（schema_version / worldbox_version / assembly_sha256 / extractor / source_snapshot_id / indexer_version） | key |
| `sources` | source identity（当前仅 `worldbox`） | source_id |
| `files` | 反编译源码文件（relative_path 相对 snapshot，sha256，parse_status: OK/PARTIAL/FAILED） | source_id + relative_path |
| `types` | 类型（class/struct/interface/enum/delegate/record；`full_name` 含 namespace 与嵌套链 `Outer.Inner`；`parent_type_id` 指向 declaring type；`is_compiler_generated` 标记 `<>c` 等） | source_id + full_name |
| `methods` | 方法/构造（`.ctor` / `.cctor` 统一命名；`signature` 形如 `foo(int,string)` 区分 overload） | source_id + type + signature |
| `fields` | 字段（一行一个 declarator，`int A, B;` 两条记录） | source_id + type + name |
| `properties` | 属性与 indexer（`this[]`；has_getter/has_setter） | source_id + type + name |
| `inheritance` | 继承边（relation: base/interface；target_name 保留原文含泛型；target_type_id 尽量回链，外部类型为 NULL） | type_id + relation + target_name |
| `strings` | 字符串字面量 occurrence（不去重；classification: path_like/localization_like/possible_identifier/possible_asset_id/other，保守确定性规则） | file + line |

## Relationships

```text
sources 1─n files 1─n types 1─n methods / fields / properties / inheritance
                     └─n strings（type_id / method_id 可 NULL，file+line 必有）
inheritance.target_type_id → types.id（可 NULL = 外部 Unity/.NET 类型）
types.parent_type_id → types.id（嵌套类型）
```

## Conventions

- 所有 location 都是 `relative_path + line`，相对 extraction snapshot，无绝对路径。
- integer PK 只是内部实现；查询/导出依赖 logical identity，rebuild 后依然稳定。
- 默认搜索隐藏 `is_compiler_generated` types（`--all` 显示）。
- attributes 未建表（后续版本可加 `attributes` 表）。
