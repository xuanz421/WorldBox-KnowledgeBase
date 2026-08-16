"""Symbol resolver over the declaration tables (Z4).

Loads lightweight symbol tables from the indexed declarations and resolves
type names, members and method calls with an inheritance-aware, best-effort
strategy. High precision beats fake recall: ambiguous stays ambiguous,
unknowns stay unresolved/external — never guessed.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field as dc_field

RESOLVER_VERSION = "1.0.0"

# Namespaces that are definitely not part of the indexed game code.
EXTERNAL_ROOTS = {
    "System", "UnityEngine", "Unity", "Microsoft", "Newtonsoft", "Mono",
    "DG", "FMOD", "Facepunch", "Google", "Firebase", "Apple", "Steamworks",
    "ICSharpCode", "NUnit", "C5", "Best", "TMPro", "Sirenix", "AOT",
}

_GENERIC_RE = re.compile(r"<[^<>]*>")


def strip_generics(name: str) -> str:
    """Remove generic argument lists: List<int> -> List (handles nesting)."""
    prev = None
    while prev != name:
        prev = name
        name = _GENERIC_RE.sub("", name)
    return name.strip()


def is_external_name(name: str) -> bool:
    first = strip_generics(name).split(".")[0].strip()
    return first in EXTERNAL_ROOTS


@dataclass
class Resolution:
    status: str  # resolved / ambiguous / unresolved / external
    type_full: str | None = None
    type_id: int | None = None
    method_id: int | None = None
    field_id: int | None = None
    prop_id: int | None = None
    signature: str | None = None
    return_type: str | None = None
    target_kind: str | None = None  # method / field / property / constructor
    candidates: list = dc_field(default_factory=list)
    declaring_hint: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "resolved"

    def logical_key(self, name_hint: str) -> str:
        kind = self.target_kind or "unknown"
        if self.ok and self.type_full:
            if kind in ("method", "constructor"):
                return f"method:{self.type_full}.{self.signature}"
            return f"{kind}:{self.type_full}.{name_hint}"
        prefix = {"method": "method?", "constructor": "method?", "field": "field?", "property": "prop?"}.get(kind, "?")
        return f"{prefix}{name_hint}"


class Resolver:
    """Symbol tables + lookup over one indexed source (worldbox)."""

    def __init__(self, conn: sqlite3.Connection):
        self.types: dict[str, dict] = {}
        self.types_by_name: dict[str, list[str]] = {}
        self.methods: dict[str, dict[str, list[dict]]] = {}
        self.fields: dict[str, dict[str, dict]] = {}
        self.props: dict[str, dict[str, dict]] = {}
        self.bases: dict[str, list[tuple[str, str | None]]] = {}  # full -> [(textual, resolved_full)]
        self._load(conn)

    def _load(self, conn: sqlite3.Connection) -> None:
        for row in conn.execute("SELECT id, full_name, name, kind, namespace FROM types"):
            full = row[1]
            self.types[full] = {"id": row[0], "name": row[2], "kind": row[3], "namespace": row[4]}
            self.types_by_name.setdefault(row[2], []).append(full)
        for row in conn.execute(
            "SELECT t.full_name, m.id, m.name, m.signature, m.return_type FROM methods m JOIN types t ON t.id = m.type_id"
        ):
            self.methods.setdefault(row[0], {}).setdefault(row[2], []).append(
                {"id": row[1], "signature": row[3], "return_type": row[4]}
            )
        for row in conn.execute(
            "SELECT t.full_name, f.id, f.name, f.field_type FROM fields f JOIN types t ON t.id = f.type_id"
        ):
            self.fields.setdefault(row[0], {})[row[2]] = {"id": row[1], "type": row[3]}
        for row in conn.execute(
            "SELECT t.full_name, p.id, p.name, p.property_type FROM properties p JOIN types t ON t.id = p.type_id"
        ):
            self.props.setdefault(row[0], {})[row[2]] = {"id": row[1], "type": row[3]}
        for row in conn.execute(
            """SELECT t.full_name, i.target_name, t2.full_name FROM inheritance i
               JOIN types t ON t.id = i.type_id LEFT JOIN types t2 ON t2.id = i.target_type_id"""
        ):
            self.bases.setdefault(row[0], []).append((row[1], row[2]))

    # --- type chain ---------------------------------------------------------

    def type_chain(self, full_name: str) -> list[str]:
        """Declaring type first, then resolved base chain (cycle-safe)."""
        chain = [full_name]
        seen = {full_name}
        index = 0
        while index < len(chain):
            current = chain[index]
            index += 1
            for textual, resolved in self.bases.get(current, []):
                target = resolved or self._resolve_base_textual(textual, current)
                if target and target not in seen and target in self.types:
                    seen.add(target)
                    chain.append(target)
        return chain

    def _resolve_base_textual(self, textual: str, declaring_full: str) -> str | None:
        base = strip_generics(textual).split(".")[-1]
        info = self.types.get(declaring_full)
        ns = info["namespace"] if info else None
        for candidate in ([f"{ns}.{base}"] if ns else []) + [base]:
            if candidate in self.types:
                return candidate
        return None

    def chain_is_external(self, full_name: str) -> bool:
        """True if the unresolved tail of a chain points at external types."""
        for textual, resolved in self.bases.get(full_name, []):
            if resolved:
                continue
            if is_external_name(textual):
                return True
        return False

    # --- type resolution ----------------------------------------------------

    def resolve_type(self, name: str, namespace: str | None = None, using_ns: tuple[str, ...] = (), current_type: str | None = None) -> Resolution:
        base = strip_generics(name).strip()
        if not base:
            return Resolution("unresolved")

        if "." in base:
            if base in self.types:
                return Resolution("resolved", type_full=base, type_id=self.types[base]["id"])
            # namespace-qualified name: resolve the last segment within that namespace
            prefix, last = base.rsplit(".", 1)
            qualified = f"{prefix}.{last}"
            if qualified in self.types:
                return Resolution("resolved", type_full=qualified, type_id=self.types[qualified]["id"])
            if is_external_name(base):
                return Resolution("external", declaring_hint=base)
            return Resolution("unresolved", declaring_hint=base)

        candidates: list[str] = []
        if current_type:
            # nested types of the enclosing chain first
            for chain_type in self.type_chain(current_type):
                nested = f"{chain_type}.{base}"
                if nested in self.types:
                    candidates.append(nested)
        if namespace:
            candidates.append(f"{namespace}.{base}")
        for ns in using_ns:
            candidates.append(f"{ns}.{base}")
        candidates.append(base)

        seen: set[str] = set()
        unique: list[str] = []
        for candidate in candidates:
            if candidate in self.types and candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        if len(unique) == 1:
            return Resolution("resolved", type_full=unique[0], type_id=self.types[unique[0]]["id"])
        if len(unique) > 1:
            return Resolution("ambiguous", candidates=unique, declaring_hint=base)
        if is_external_name(base):
            return Resolution("external", declaring_hint=base)
        return Resolution("unresolved", declaring_hint=base)

    # --- member resolution ----------------------------------------------------

    def resolve_member(self, receiver_full: str | None, member: str, kind_hint: str | None = None) -> Resolution:
        """Resolve a field/property on a receiver type (inheritance-aware)."""
        if receiver_full is None:
            return Resolution("unresolved", declaring_hint=member)
        if receiver_full not in self.types:
            return Resolution("external" if is_external_name(receiver_full) else "unresolved", declaring_hint=receiver_full)

        # nearest declaration wins (C# shadowing): only the first chain level
        # that declares the member is considered; field+property conflict at
        # that level is genuinely ambiguous from syntax alone
        for chain_type in self.type_chain(receiver_full):
            field_hit = self.fields.get(chain_type, {}).get(member)
            prop_hit = self.props.get(chain_type, {}).get(member)
            if field_hit and prop_hit:
                return Resolution("ambiguous", candidates=[chain_type], declaring_hint=f"{receiver_full}.{member}")
            if field_hit:
                return Resolution("resolved", type_full=chain_type, field_id=field_hit["id"], target_kind="field")
            if prop_hit:
                return Resolution("resolved", type_full=chain_type, prop_id=prop_hit["id"], target_kind="property")

        if self.chain_is_external(receiver_full):
            return Resolution("external", declaring_hint=f"{receiver_full}.{member}")
        return Resolution("unresolved", declaring_hint=f"{receiver_full}.{member}")

    def resolve_method(self, receiver_full: str | None, name: str, arg_count: int | None = None, constructor: bool = False) -> Resolution:
        """Resolve a method call on a receiver type (inheritance-aware, arity-aware)."""
        method_name = ".ctor" if constructor else name
        if receiver_full is None:
            return Resolution("unresolved", declaring_hint=name)
        if receiver_full not in self.types:
            status = "external" if is_external_name(receiver_full) else "unresolved"
            return Resolution(status, declaring_hint=f"{receiver_full}.{name}")

        candidates: list[tuple[str, dict]] = []
        for chain_type in self.type_chain(receiver_full):
            for method in self.methods.get(chain_type, {}).get(method_name, []):
                candidates.append((chain_type, method))
        if not candidates:
            if self.chain_is_external(receiver_full):
                return Resolution("external", declaring_hint=f"{receiver_full}.{name}")
            return Resolution("unresolved", declaring_hint=f"{receiver_full}.{name}")

        if arg_count is not None and len(candidates) > 1:
            by_arity = [c for c in candidates if self._arity(c[1]["signature"]) == arg_count]
            if len(by_arity) == 1:
                candidates = by_arity
            elif len(by_arity) > 1:
                candidates = by_arity  # still ambiguous below

        if len(candidates) == 1:
            owner, method = candidates[0]
            return Resolution(
                "resolved",
                type_full=owner,
                method_id=method["id"],
                signature=method["signature"],
                return_type=method["return_type"],
                target_kind="constructor" if constructor else "method",
            )
        return Resolution(
            "ambiguous",
            candidates=[f"{owner}.{method['signature']}" for owner, method in candidates],
            declaring_hint=f"{receiver_full}.{name}",
        )

    @staticmethod
    def _arity(signature: str) -> int:
        inner = signature[signature.find("(") + 1 : signature.rfind(")")]
        return len(inner) // 2 if inner else 0

    # member type lookup for chained access (field/property type as receiver)
    def member_type(self, receiver_full: str, member: str) -> str | None:
        for chain_type in self.type_chain(receiver_full):
            if member in self.fields.get(chain_type, {}):
                declared = self.fields[chain_type][member]["type"]
                return self._normalize_type_text(declared, chain_type)
            if member in self.props.get(chain_type, {}):
                declared = self.props[chain_type][member]["type"]
                return self._normalize_type_text(declared, chain_type)
        return None

    def method_return_type(self, method_resolution: Resolution) -> str | None:
        if method_resolution.ok and method_resolution.return_type:
            owner = method_resolution.type_full
            return self._normalize_type_text(method_resolution.return_type, owner)
        return None

    def _normalize_type_text(self, declared: str | None, context_type: str | None) -> str | None:
        """Map a declared member/method type text to a known indexed full name."""
        if not declared:
            return None
        base = strip_generics(declared)
        if base in self.types:
            return base
        info = self.types.get(context_type) if context_type else None
        ns = info["namespace"] if info else None
        for candidate in ([f"{ns}.{base}"] if ns else []) + [base]:
            if candidate in self.types:
                return candidate
        if base.split("<")[0].split(".")[0] in EXTERNAL_ROOTS:
            return base  # external type text — usable as external hint
        return None
