"""Tree-sitter based C# source parser for the WBKB indexer.

Best-effort extraction: a parse error marks the file PARTIAL/FAILED but
non-error declarations are still extracted. Deterministic, no LLM.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import tree_sitter_c_sharp as _tscs
    from tree_sitter import Language, Parser

    _LANGUAGE = Language(_tscs.language())

    def _make_parser() -> Parser:
        try:
            return Parser(_LANGUAGE)
        except TypeError:  # older binding API
            parser = Parser()
            parser.set_language(_LANGUAGE)
            return parser

    _PARSER = _make_parser()
    TREE_SITTER_AVAILABLE = True
except ImportError:  # pragma: no cover - environment without deps
    _PARSER = None
    TREE_SITTER_AVAILABLE = False

TYPE_KINDS = {
    "class_declaration": "class",
    "struct_declaration": "struct",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "delegate_declaration": "delegate",
    "record_declaration": "record",
    "record_struct_declaration": "record",
}

MODIFIER_KEYWORDS = {
    "public": "public",
    "private": "private",
    "protected": "protected",
    "internal": "internal",
    "static": "static",
    "abstract": "abstract",
    "sealed": "sealed",
    "virtual": "virtual",
    "override": "override",
    "const": "const",
    "readonly": "readonly",
    "partial": "partial",
    "extern": "extern",
    "unsafe": "unsafe",
    "async": "async",
    "new": "new",
}

VISIBILITY_ORDER = ("public", "protected", "internal", "private")
_COMPILER_GENERATED_RE = re.compile(r"[<>]")

_MAX_PARSE_ERROR_TEXT = 200


def _text(node) -> str:
    return node.text.decode("utf-8", "replace")


def _row(node) -> int:
    point = node.start_point
    return point[0] if isinstance(point, (tuple, list)) else point.row


def _start_col(node) -> int:
    point = node.start_point
    return point[1] if isinstance(point, (tuple, list)) else point.column


def _end_row(node) -> int:
    point = node.end_point
    return point[0] if isinstance(point, (tuple, list)) else point.row


def _end_col(node) -> int:
    point = node.end_point
    return point[1] if isinstance(point, (tuple, list)) else point.column


def _child_by_field(node, name):
    child = node.child_by_field_name(name)
    return child


def _collect_modifiers(node) -> set[str]:
    found = set()
    for child in node.children:
        t = child.type
        if t == "modifier":
            found.add(_text(child).strip())
        elif t in MODIFIER_KEYWORDS and t not in ("new",):  # bare keyword child
            found.add(t)
    return found


def _visibility(modifiers: set[str]) -> str:
    for vis in VISIBILITY_ORDER:
        if vis in modifiers:
            return vis
    return "internal"  # C# default


def _declared_name(node) -> str | None:
    name_node = _child_by_field(node, "name")
    if name_node is None:
        return None
    return _text(name_node).strip()


def _parameter_signature(parameter_list) -> str:
    if parameter_list is None:
        return ""
    parts = []
    for child in parameter_list.children:
        if child.type != "parameter":
            continue
        type_node = _child_by_field(child, "type")
        if type_node is not None:
            type_text = _text(type_node)
        else:  # params like `in float f` may wrap the type differently
            type_text = _text(child).strip()
            for keyword in ("ref ", "in ", "out ", "params ", "this "):
                type_text = type_text.replace(keyword, "")
            type_text = type_text.split()[0] if type_text.split() else "?"
        parts.append(re.sub(r"\s+", "", type_text))
    return ",".join(parts)


def _clean_string_value(node) -> str | None:
    raw = _text(node)
    if node.type == "verbatim_string_literal":
        inner = raw[2:-1] if raw.startswith('@"') else raw
        return inner.replace('""', '"')
    if node.type == "interpolated_string_expression":
        value = raw
        for prefix in ('$@"', '@$"', '$"'):
            if value.startswith(prefix):
                value = value[len(prefix):]
                break
        return value[:-1] if value.endswith('"') else value
    if node.type == "string_literal":
        if len(raw) < 2 or not raw.startswith('"'):
            return None
        inner = raw[1:-1]
        return (
            inner.replace(r"\\", "\x00")
            .replace(r"\"", '"')
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
            .replace(r"\r", "\r")
            .replace(r"\0", "\x00")
            .replace("\x00", "\\")
        )
    return None


_CLASSIFICATION_PATH_RE = re.compile(r"[/\\]")
_CLASSIFICATION_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CLASSIFICATION_ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")


def classify_string(value: str) -> str:
    """Conservative, deterministic string classification."""
    if not value:
        return "other"
    if _CLASSIFICATION_PATH_RE.search(value):
        return "path_like"
    if any(ch.isspace() for ch in value):
        return "localization_like"
    if _CLASSIFICATION_IDENT_RE.fullmatch(value):
        return "possible_identifier"
    if _CLASSIFICATION_ASSET_RE.fullmatch(value) and ("_" in value or "." in value):
        return "possible_asset_id"
    return "other"


def _accessor_keywords(accessors) -> tuple[int, int]:
    """Return (has_getter, has_setter); accessors may carry modifiers (private set)."""
    has_getter = has_setter = 0
    if accessors is None:
        return 0, 0
    for child in accessors.children:
        if child.type != "accessor_declaration":
            continue
        for sub in child.children:
            if sub.type == "get":
                has_getter = 1
            elif sub.type == "set":
                has_setter = 1
            elif sub.type == "add":
                has_getter = 1
            elif sub.type == "remove":
                has_setter = 1
    return has_getter, has_setter


def _is_compiler_generated(node) -> bool:
    """Detect compiler-generated names like `<>c` / `<Method>d__12`.

    tree-sitter recovers the invalid identifier as an ERROR node right before
    the plain identifier, so check both the name text and its previous sibling.
    """
    name_node = _child_by_field(node, "name")
    if name_node is not None and _COMPILER_GENERATED_RE.search(_text(name_node)):
        return True
    if name_node is not None:
        prev = name_node.prev_sibling
        if prev is not None and (prev.type == "ERROR" or "<" in _text(prev)):
            return True
    return False


def _first_error_text(root) -> str | None:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            text = _text(node).strip() or node.type
            return text[:_MAX_PARSE_ERROR_TEXT]
        stack.extend(reversed(node.children))
    return None


class _FileCollector:
    def __init__(self):
        self.types: list[dict] = []
        self.methods: list[dict] = []
        self.fields: list[dict] = []
        self.properties: list[dict] = []
        self.strings: list[dict] = []
        self.inheritance: list[dict] = []

    def add_string(self, node, file_id_placeholder, type_id, method_id):
        value = _clean_string_value(node)
        if value is None:
            return
        self.strings.append(
            {
                "type_id": type_id,
                "method_id": method_id,
                "value": value,
                "classification": classify_string(value),
                "start_line": _row(node) + 1,
            }
        )


def get_parser():
    """Shared tree-sitter C# parser (raises if deps are missing)."""
    if not TREE_SITTER_AVAILABLE:
        raise RuntimeError(
            "tree-sitter packages missing; run: pip install -r tools/wbkb/requirements.txt"
        )
    return _PARSER


def parse_source(code: bytes) -> dict:
    """Parse one C# file and extract indexable declarations (best-effort)."""
    tree = get_parser().parse(code)
    root = tree.root_node
    collector = _FileCollector()
    type_counter = 0
    method_counter = 0

    def visit(node, namespace: str, parent_type: dict | None, method_local_id: int | None = None):
        nonlocal type_counter, method_counter
        t = node.type

        if t == "ERROR":
            return

        if t == "namespace_declaration":
            name_node = _child_by_field(node, "name")
            ns = _text(name_node).strip() if name_node is not None else ""
            merged = f"{namespace}.{ns}" if namespace and ns else (ns or namespace)
            for child in node.children:
                visit(child, merged, parent_type)
            return

        if t in TYPE_KINDS:
            name = _declared_name(node)
            if not name:
                return
            modifiers = _collect_modifiers(node)
            kind = TYPE_KINDS[t]
            local_id = type_counter
            type_counter += 1
            if parent_type:
                full_name = f"{parent_type['name_chain']}.{name}"  # name_chain already carries namespace
            elif namespace:
                full_name = f"{namespace}.{name}"
            else:
                full_name = name
            record = {
                "local_id": local_id,
                "parent_local_id": parent_type["local_id"] if parent_type else None,
                "namespace": namespace,
                "name": name,
                "full_name": full_name,
                "name_chain": full_name,
                "kind": kind,
                "visibility": _visibility(modifiers),
                "is_abstract": int("abstract" in modifiers),
                "is_static": int("static" in modifiers),
                "is_sealed": int("sealed" in modifiers),
                "is_compiler_generated": int(_is_compiler_generated(node)),
                "start_line": _row(node) + 1,
                "end_line": _end_row(node) + 1,
            }
            collector.types.append(record)

            # inheritance: first base_list entry = base, rest = interfaces
            base_list = next((c for c in node.children if c.type == "base_list"), None)
            if base_list is not None:
                target_names = [
                    re.sub(r"\s+", "", _text(c))
                    for c in base_list.children
                    if c.type in ("identifier", "qualified_name", "generic_name", "predefined_type")
                ]
                for index, target in enumerate(target_names):
                    collector.inheritance.append(
                        {
                            "type_local_id": local_id,
                            "relation": "base" if index == 0 else "interface",
                            "target_name": target,
                        }
                    )
            for child in node.children:
                visit(child, namespace, record)
            return

        current_type = parent_type

        if t in ("method_declaration", "constructor_declaration", "destructor_declaration"):
            if t == "constructor_declaration":
                modifiers = _collect_modifiers(node)
                name = ".cctor" if "static" in modifiers else ".ctor"
            else:
                name = _declared_name(node) or "?"
                modifiers = _collect_modifiers(node)
            params = _child_by_field(node, "parameters")
            signature = f"{name}({_parameter_signature(params)})"
            returns = _child_by_field(node, "returns")
            method_local_id = method_counter
            method_counter += 1
            collector.methods.append(
                {
                    "local_id": method_local_id,
                    "type_local_id": current_type["local_id"] if current_type else None,
                    "name": name,
                    "signature": signature,
                    "return_type": re.sub(r"\s+", " ", _text(returns)).strip() if returns is not None else ("void" if t == "method_declaration" else None),
                    "visibility": _visibility(modifiers),
                    "is_static": int("static" in modifiers),
                    "is_virtual": int("virtual" in modifiers),
                    "is_override": int("override" in modifiers),
                    "is_abstract": int("abstract" in modifiers),
                    "start_line": _row(node) + 1,
                    "end_line": _end_row(node) + 1,
                }
            )
            for child in node.children:
                visit(child, namespace, current_type, method_local_id)
            return

        if t == "field_declaration":
            modifiers = _collect_modifiers(node)
            var_decl = next((c for c in node.children if c.type == "variable_declaration"), None)
            if var_decl is not None:
                type_node = var_decl.children[0] if var_decl.children else None
                field_type = re.sub(r"\s+", "", _text(type_node)) if type_node is not None else None
                for child in var_decl.children:
                    if child.type == "variable_declarator":
                        name_node = _child_by_field(child, "name")
                        if name_node is None:
                            first = child.children[0] if child.children else None
                            name = _text(first) if first is not None and first.type == "identifier" else None
                        else:
                            name = _text(name_node)
                        if not name:
                            continue
                        collector.fields.append(
                            {
                                "type_local_id": current_type["local_id"] if current_type else None,
                                "name": name,
                                "field_type": field_type,
                                "visibility": _visibility(modifiers),
                                "is_static": int("static" in modifiers),
                                "is_readonly": int("readonly" in modifiers),
                                "is_const": int("const" in modifiers),
                                "start_line": _row(child) + 1,
                            }
                        )
            # walk initializers so string literals in `= "x"` are recorded
            for child in node.children:
                visit(child, namespace, current_type)
            return

        if t == "property_declaration":
            modifiers = _collect_modifiers(node)
            name = _declared_name(node)
            type_node = _child_by_field(node, "type")
            has_getter, has_setter = _accessor_keywords(_child_by_field(node, "accessors"))
            if _child_by_field(node, "value") is not None:  # expression-bodied => getter
                has_getter = 1
            if name:
                collector.properties.append(
                    {
                        "type_local_id": current_type["local_id"] if current_type else None,
                        "name": name,
                        "property_type": re.sub(r"\s+", "", _text(type_node)) if type_node is not None else None,
                        "visibility": _visibility(modifiers),
                        "has_getter": has_getter,
                        "has_setter": has_setter,
                        "is_static": int("static" in modifiers),
                        "start_line": _row(node) + 1,
                        "end_line": _end_row(node) + 1,
                    }
                )
            # walk accessors/bodies for string literals
            for child in node.children:
                visit(child, namespace, current_type)
            return

        if t == "indexer_declaration":
            modifiers = _collect_modifiers(node)
            type_node = _child_by_field(node, "type")
            has_getter, has_setter = _accessor_keywords(_child_by_field(node, "accessors"))
            collector.properties.append(
                {
                    "type_local_id": current_type["local_id"] if current_type else None,
                    "name": "this[]",
                    "property_type": re.sub(r"\s+", "", _text(type_node)) if type_node is not None else None,
                    "visibility": _visibility(modifiers),
                    "has_getter": has_getter,
                    "has_setter": has_setter,
                    "is_static": int("static" in modifiers),
                    "start_line": _row(node) + 1,
                    "end_line": _end_row(node) + 1,
                }
            )
            return

        if t in ("string_literal", "verbatim_string_literal", "interpolated_string_expression"):
            collector.add_string(node, None, current_type["local_id"] if current_type else None, method_local_id)
            return

        for child in node.children:
            visit(child, namespace, parent_type, method_local_id)

    visit(root, "", None)

    error_text = _first_error_text(root)
    if error_text is not None:
        status = "PARTIAL" if collector.types else "FAILED"
    else:
        status = "OK"
    return {
        "types": collector.types,
        "methods": collector.methods,
        "fields": collector.fields,
        "properties": collector.properties,
        "strings": collector.strings,
        "inheritance": collector.inheritance,
        "parse_status": status,
        "parse_error": error_text,
    }


def parse_file(path: Path) -> dict:
    return parse_source(Path(path).read_bytes())
