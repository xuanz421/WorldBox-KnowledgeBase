"""Reference extraction pass (Z4): walks the AST with local scopes and emits
symbol_references / method_calls / type_references records via the Resolver.

Single-dispatch model: every node is visited exactly once — statements
recursively, expressions through resolve_expression (which owns its children).
Unknown receivers stay unresolved; nothing is ever guessed.
"""

from __future__ import annotations

from .csharp import (
    TYPE_KINDS,
    _child_by_field,
    _collect_modifiers,
    _end_col,
    _end_row,
    _parameter_signature,
    _row,
    _start_col,
    _text,
)
from .resolver import Resolution, is_external_name, strip_generics

COMPOUND_OPS = {"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "??=", "<<=", ">>=", ">>>="}
ASSIGNMENT_OP_TOKENS = COMPOUND_OPS | {"="}
INCDEC_OPS = ("++", "--")

_TYPE_NODE_KINDS = {
    "identifier", "qualified_name", "generic_name", "predefined_type",
    "alias_qualified_name", "array_type", "nullable_type", "pointer_type",
}


class ReferenceContext:
    """What the extractor needs to know about the file being processed."""

    def __init__(self, resolver, file_id: int, source: str, type_ids: dict, method_ids: dict):
        self.resolver = resolver
        self.file_id = file_id
        self.source = source          # source_id of the file being processed
        self.type_ids = type_ids      # (source, full_name) -> db id
        self.method_ids = method_ids  # ((source, owner_full), signature) -> db id


def extract_references(code: bytes, ctx: ReferenceContext) -> dict:
    from .csharp import get_parser

    root = get_parser().parse(code).root_node
    symbol_references: list[dict] = []
    method_calls: list[dict] = []
    type_references: list[dict] = []

    state = {"namespace": "", "using": [], "type_chain": [], "current_method_id": None, "scope": {}}

    def current_type():
        return state["type_chain"][-1] if state["type_chain"] else None

    def _is_type_key(value) -> bool:
        """TypeKey tuples are indexed types; plain strings are external pseudo-types."""
        return isinstance(value, tuple) and len(value) == 2 and value in ctx.resolver.types

    # ---- emitters ----

    def emit_symbol_ref(res: Resolution, name: str, kind: str, node):
        target_id = None
        if res.ok:
            target_id = res.field_id or res.prop_id or res.method_id or res.type_id
        symbol_references.append(
            {
                "from_file_id": ctx.file_id,
                "from_type_id": ctx.type_ids.get(current_type()),
                "from_method_id": state["current_method_id"],
                "target_kind": res.target_kind or "unknown",
                "target_name": res.declaring_hint or name,
                "target_logical_key": res.logical_key(name),
                "target_id": target_id,
                "reference_kind": kind,
                "start_line": _row(node) + 1,
                "start_column": _start_col(node),
                "end_line": _end_row(node) + 1,
                "end_column": _end_col(node),
                "resolution_status": res.status,
                "resolution_confidence": 1.0 if res.ok else (0.5 if res.status == "external" else 0.0),
            }
        )

    def emit_type_ref(res: Resolution, node, kind: str):
        type_references.append(
            {
                "from_file_id": ctx.file_id,
                "from_type_id": ctx.type_ids.get(current_type()),
                "from_method_id": state["current_method_id"],
                "target_type_id": res.type_id if res.ok else None,
                "target_name": res.type_full if res.ok else (res.declaring_hint or "?"),
                "reference_kind": kind,
                "line": _row(node) + 1,
                "resolution_status": res.status,
            }
        )

    def emit_method_call(res: Resolution, name: str, arg_count: int, node, receiver_hint: str | None):
        method_calls.append(
            {
                "caller_method_id": state["current_method_id"],
                "callee_method_id": res.method_id if res.ok else None,
                "callee_name": name,
                "callee_signature_hint": res.signature if res.ok else "(" + ", ".join("?" * arg_count) + ")",
                "declaring_type_hint": res.type_full if res.ok else receiver_hint,
                "file_id": ctx.file_id,
                "line": _row(node) + 1,
                "column": _start_col(node),
                "resolution_status": res.status,
            }
        )

    # ---- type helpers ----

    def resolve_type_name(name_text: str):
        return ctx.resolver.resolve_type(
            name_text, state["namespace"], tuple(state["using"]), current_type(), ctx.source
        )

    def emit_type_node_refs(node, kind: str):
        if node.type == "predefined_type":
            # int/void/bool/... are language-predefined; skip as type refs
            return
        res = resolve_type_name(_text(node))
        emit_type_ref(res, node, kind)
        _emit_generic_args(node)

    def _emit_generic_args(node):
        stack = list(node.children)
        while stack:
            child = stack.pop()
            if child.type == "type_argument_list":
                for sub in child.children:
                    if sub.type in ("identifier", "predefined_type", "qualified_name"):
                        arg_res = resolve_type_name(_text(sub))
                        if arg_res.ok or arg_res.status == "external":
                            emit_type_ref(arg_res, sub, "generic_argument")
            else:
                stack.extend(child.children)

    # ---- expressions: return the static type full name (or None) ----

    def resolve_expression(node, mode: str) -> str | None:
        if node is None:
            return None
        t = node.type

        if t == "identifier":
            name = _text(node).strip()
            if name in state["scope"]:
                return state["scope"][name]
            res = resolve_type_name(name)
            if res.ok:
                emit_type_ref(res, node, "type_use")
                return res.type_key
            # implicit this: bare member access on the enclosing type
            if current_type() and res.status == "unresolved":
                member_res = ctx.resolver.resolve_member(current_type(), name)
                if member_res.ok:
                    emit_symbol_ref(member_res, name, _member_kind_for_mode(mode), node)
                    return ctx.resolver.member_type(current_type(), name)
            if res.status == "external":
                return name
            # unresolvable name imported via a using directive is almost
            # certainly an external library type (Mathf, Debug, ...)
            if any(is_external_name(ns) for ns in state["using"]):
                return name
            return None

        if t == "member_access_expression":
            return resolve_member_access(node, mode)

        if t == "invocation_expression":
            return resolve_invocation(node)

        if t == "object_creation_expression":
            return resolve_creation(node)

        if t in ("this", "this_expression"):
            return current_type()

        if t in ("base", "base_expression"):
            chain = ctx.resolver.type_chain(current_type()) if current_type() else []
            return chain[1] if len(chain) > 1 else None
        if t == "cast_expression":
            type_node = _child_by_field(node, "type")
            value = _child_by_field(node, "value")
            if value is None:
                value = _child_by_field(node, "expression")
            resolve_expression(value, "read")
            if type_node is not None:
                emit_type_node_refs(type_node, "cast")
                res = resolve_type_name(_text(type_node))
                return res.type_key if res.ok else None
            return None

        if t == "as_expression":
            resolve_expression(_child_by_field(node, "left"), "read")
            right = _child_by_field(node, "right")
            if right is not None:
                emit_type_node_refs(right, "as")
                res = resolve_type_name(_text(right))
                if res.ok:
                    return res.type_key
                if res.status == "external":
                    return strip_generics(_text(right).strip())
            return None

        if t == "typeof_expression":
            type_node = _child_by_field(node, "type")
            if type_node is not None:
                emit_type_node_refs(type_node, "typeof")
            return "System.Type"

        if t == "assignment_expression":
            walk_assignment(node)
            return None

        if t in ("postfix_unary_expression", "prefix_unary_expression"):
            operand = node.children[1] if t == "postfix_unary_expression" else node.children[0]
            op_text = _text(node)
            mode_rw = any(op in op_text for op in INCDEC_OPS)
            resolve_expression(operand, "read_write" if mode_rw else "read")
            return None

        if t == "element_access_expression":
            resolve_expression(_child_by_field(node, "expression"), "read")
            for child in node.children:
                if child.type == "bracketed_argument_list":
                    walk_argument_list(child)
            return None

        if t in ("parenthesized_expression", "checked_expression", "unchecked_expression"):
            inner = node.children[1] if t == "parenthesized_expression" else (node.children[-1] if node.children else None)
            return resolve_expression(inner, mode)

        if t == "conditional_access_expression":
            resolve_expression(_child_by_field(node, "expression"), "read")
            resolve_expression(_child_by_field(node, "when_not_null"), "read")
            return None

        # generic fallback: visit children once
        for child in node.children:
            resolve_expression(child, "read")
        return None

    def resolve_member_access(node, mode: str) -> str | tuple | None:
        expr = _child_by_field(node, "expression")
        name_node = _child_by_field(node, "name")
        member = _member_name(name_node)
        receiver = resolve_expression(expr, "read")
        kind = _member_kind_for_mode(mode)

        if receiver is None:
            emit_symbol_ref(Resolution("unresolved", declaring_hint=member), member, kind, node)
            return None

        if not _is_type_key(receiver):
            hint = f"{receiver}.{member}" if isinstance(receiver, str) else member
            emit_symbol_ref(Resolution("external", declaring_hint=hint), member, kind, node)
            return None

        res = ctx.resolver.resolve_member(receiver, member)
        emit_symbol_ref(res, member, kind, node)
        if res.ok:
            return ctx.resolver.member_type(receiver, member)
        return None

    def resolve_invocation(node) -> str | None:
        function = _child_by_field(node, "function")
        args = _child_by_field(node, "arguments")
        arg_count = _count_arguments(args)

        if function is None:
            walk_argument_list(args)
            return None

        if function.type == "identifier":
            name = _text(function).strip()
            receiver = current_type()
            res = ctx.resolver.resolve_method(receiver, name, arg_count)
            emit_method_call(res, name, arg_count, node, receiver[1] if receiver else None)
            walk_argument_list(args)
            return ctx.resolver.method_return_type(res) if res.ok else None

        if function.type == "member_access_expression":
            expr = _child_by_field(function, "expression")
            name = _member_name(_child_by_field(function, "name"))
            receiver_hint = _text(expr).strip()[:80] if expr is not None else None
            receiver = resolve_expression(expr, "read")

            if _is_type_key(receiver):
                res = ctx.resolver.resolve_method(receiver, name, arg_count)
            elif receiver is None:
                hint = f"{receiver_hint}.{name}" if receiver_hint else name
                res = Resolution("unresolved", declaring_hint=hint)
            else:
                res = Resolution("external", declaring_hint=f"{receiver}.{name}")
            emit_method_call(res, name, arg_count, node, receiver if isinstance(receiver, str) else receiver_hint)
            walk_argument_list(args)
            if res.ok:
                return ctx.resolver.method_return_type(res)
            return None

        walk_argument_list(args)
        return None

    def resolve_creation(node) -> str | None:
        type_node = _child_by_field(node, "type")
        args = _child_by_field(node, "arguments")
        arg_count = _count_arguments(args)
        if type_node is None:
            walk_argument_list(args)
            return None
        emit_type_node_refs(type_node, "instantiate")
        res = resolve_type_name(_text(type_node))
        walk_argument_list(args)
        if res.ok:
            ctor = ctx.resolver.resolve_method(res.type_key, ".ctor", arg_count, constructor=True)
            emit_method_call(ctor, ".ctor", arg_count, node, res.type_full)
            return res.type_key
        return None

    def walk_assignment(node):
        # the operator is a child whose node type IS the operator token
        op = next((c for c in node.children if c.type in ASSIGNMENT_OP_TOKENS), None)
        op_text = op.type if op is not None else "="
        mode = "read_write" if op_text in COMPOUND_OPS else "write"
        resolve_expression(_child_by_field(node, "left"), mode)
        resolve_expression(_child_by_field(node, "right"), "read")

    def walk_argument_list(args) -> list:
        types = []
        if args is None:
            return types
        for child in args.children:
            if child.type == "argument":
                value = _child_by_field(child, "expression")
                if value is None and child.children:
                    value = child.children[-1]
                types.append(resolve_expression(value, "read"))
        return types

    def _member_name(name_node) -> str:
        if name_node is None:
            return "?"
        if name_node.type == "generic_name":
            inner = _child_by_field(name_node, "name")
            return _text(inner).strip() if inner is not None else _text(name_node).split("<")[0]
        return _text(name_node).strip()

    def _count_arguments(args) -> int:
        if args is None:
            return 0
        return sum(1 for c in args.children if c.type == "argument")

    def _member_kind_for_mode(mode: str) -> str:
        return {"write": "write", "read_write": "read_write"}.get(mode, "read")

    # ---- statements & declarations ----

    def walk_body(node):
        """Statements recurse; expression children are resolved exactly once."""
        if node is None:
            return
        t = node.type
        if t == "local_declaration_statement":
            walk_local_declaration(node)
            return
        if t == "for_each_statement":
            walk_foreach(node)
            return
        if t == "catch_declaration":
            walk_catch(node)
            return
        for child in node.children:
            if _is_expression(child):
                resolve_expression(child, "read")
            else:
                walk_body(child)

    def _is_expression(node) -> bool:
        return node.type.endswith("_expression")

    def walk_local_declaration(node):
        var_decl = next((c for c in node.children if c.type == "variable_declaration"), None)
        if var_decl is None:
            return
        type_node = var_decl.children[0] if var_decl.children else None
        declared_type = None
        is_var = False
        if type_node is not None:
            type_text = _text(type_node).strip()
            is_var = type_text == "var"
            if not is_var:
                emit_type_node_refs(type_node, "type_use")
                res = resolve_type_name(type_text)
                declared_type = res.type_key if res.ok else None
                if declared_type is None and res.status == "external":
                    declared_type = strip_generics(type_text)
        for child in var_decl.children:
            if child.type != "variable_declarator":
                continue
            name_node = _child_by_field(child, "name")
            vname = _text(name_node).strip() if name_node is not None else None
            # the initializer is an unnamed child after the '=' token
            init_value = None
            if len(child.children) >= 3:
                init_value = child.children[-1]
            init_type = resolve_expression(init_value, "read") if init_value is not None else None
            if vname:
                state["scope"][vname] = declared_type if not is_var else init_type

    def walk_foreach(node):
        type_node = None
        var_name = None
        for child in node.children:
            if child.type in _TYPE_NODE_KINDS and type_node is None:
                type_node = child
            elif child.type == "identifier" and var_name is None:
                var_name = _text(child).strip()
        elem_type = None
        if type_node is not None:
            type_text = _text(type_node).strip()
            emit_type_node_refs(type_node, "type_use")
            if type_text != "var":
                res = resolve_type_name(type_text)
                elem_type = res.type_key if res.ok else (strip_generics(type_text) if res.status == "external" else None)
        if var_name:
            state["scope"][var_name] = elem_type
        for child in node.children:
            if child is type_node:
                continue
            if _is_expression(child):
                resolve_expression(child, "read")
            else:
                walk_body(child)

    def walk_catch(node):
        type_node = None
        var_name = None
        for child in node.children:
            if child.type in _TYPE_NODE_KINDS:
                type_node = child
            elif child.type == "identifier":
                var_name = _text(child).strip()
        caught = None
        if type_node is not None:
            emit_type_node_refs(type_node, "type_use")
            res = resolve_type_name(_text(type_node))
            caught = res.type_key if res.ok else None
        if var_name:
            state["scope"][var_name] = caught
        for child in node.children:
            if child is not type_node:
                walk_body(child)

    def walk_declaration(node, namespace: str):
        """File-level walk: using directives, namespaces, type declarations."""
        t = node.type
        if t == "using_directive":
            text = _text(node).strip()
            name = text.replace("using", "").replace("static", "").strip().rstrip(";").split("=")[0].strip()
            if name:
                state["using"].append(name)
            return
        if t == "namespace_declaration":
            name_node = _child_by_field(node, "name")
            ns = _text(name_node).strip() if name_node is not None else ""
            merged = f"{namespace}.{ns}" if namespace and ns else (ns or namespace)
            previous = state["namespace"]
            state["namespace"] = merged
            for child in node.children:
                walk_declaration(child, merged)
            state["namespace"] = previous
            return
        if t == "file_scoped_namespace_declaration":
            return  # applied globally by the entry pre-scan
        if t in TYPE_KINDS:
            walk_type_declaration(node, namespace)
            return
        for child in node.children:
            walk_declaration(child, namespace)

    def walk_type_declaration(node, namespace: str):
        name_node = _child_by_field(node, "name")
        name = _text(name_node).strip() if name_node is not None else "?"
        parent = current_type()
        full = f"{parent[1]}.{name}" if parent else (f"{namespace}.{name}" if namespace else name)
        state["type_chain"].append((ctx.source, full))

        base_list = next((c for c in node.children if c.type == "base_list"), None)
        if base_list is not None:
            type_children = [c for c in base_list.children if c.type in _TYPE_NODE_KINDS]
            for index, child in enumerate(type_children):
                emit_type_node_refs(child, "inherit" if index == 0 else "interface")

        for child in node.children:
            visit_member(child)
        state["type_chain"].pop()

    def visit_member(node):
        t = node.type
        if t in ("method_declaration", "constructor_declaration", "destructor_declaration"):
            returns = _child_by_field(node, "returns")
            if returns is not None:
                emit_type_node_refs(returns, "return_type")
            scope = {}
            params = _child_by_field(node, "parameters")
            if params is not None:
                for child in params.children:
                    if child.type != "parameter":
                        continue
                    type_node = _child_by_field(child, "type")
                    name_node = _child_by_field(child, "name")
                    ptype = None
                    if type_node is not None:
                        emit_type_node_refs(type_node, "parameter_type")
                        res = resolve_type_name(_text(type_node))
                        if res.ok:
                            ptype = res.type_key
                        elif res.status == "external":
                            ptype = strip_generics(_text(type_node).strip())
                    pname = _text(name_node).strip() if name_node is not None else None
                    if pname:
                        scope[pname] = ptype
            state["scope"] = scope
            state["current_method_id"] = ctx.method_ids.get((current_type(), _signature_of(node)))
            body = _child_by_field(node, "body")
            if body is None:
                arrow = _child_by_field(node, "value")
                body = arrow
            walk_body(body)
            state["current_method_id"] = None
            state["scope"] = {}
            return
        if t == "field_declaration":
            var_decl = next((c for c in node.children if c.type == "variable_declaration"), None)
            if var_decl is not None and var_decl.children:
                emit_type_node_refs(var_decl.children[0], "field_type")
            state["current_method_id"] = None
            state["scope"] = {}
            for child in node.children:
                walk_body(child)
            return
        if t == "property_declaration":
            type_node = _child_by_field(node, "type")
            if type_node is not None:
                emit_type_node_refs(type_node, "property_type")
            state["current_method_id"] = None
            state["scope"] = {}
            for child in node.children:
                walk_body(child)
            return
        if t == "attribute_list":
            for child in node.children:
                if child.type == "attribute":
                    attr_name = _child_by_field(child, "name")
                    if attr_name is not None:
                        res = resolve_type_name(_text(attr_name))
                        if res.ok or res.status == "external":
                            emit_type_ref(res, attr_name, "attribute")
            return
        if t in TYPE_KINDS:
            walk_type_declaration(node, state["namespace"])
            return
        for child in node.children:
            visit_member(child)

    def _signature_of(node) -> str:
        if node.type == "constructor_declaration":
            name = ".cctor" if "static" in _collect_modifiers(node) else ".ctor"
        else:
            name_node = _child_by_field(node, "name")
            name = _text(name_node).strip() if name_node is not None else "?"
        return f"{name}({_parameter_signature(_child_by_field(node, 'parameters'))})"

    # entry: using directives + declarations (file-scoped namespace applies to all siblings)
    file_namespace = ""
    for child in root.children:
        if child.type == "file_scoped_namespace_declaration":
            name_node = _child_by_field(child, "name")
            file_namespace = _text(name_node).strip() if name_node is not None else ""
            break
    if file_namespace:
        state["namespace"] = file_namespace
    for child in root.children:
        if child.type == "file_scoped_namespace_declaration":
            continue
        walk_declaration(child, file_namespace)

    return {
        "symbol_references": symbol_references,
        "method_calls": method_calls,
        "type_references": type_references,
    }
