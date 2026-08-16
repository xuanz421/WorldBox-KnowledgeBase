"""Multi-source symbol resolver over the declaration tables (Z4/Z5).

Loads lightweight symbol tables from the indexed declarations of every source
(worldbox, neomodloader, ...) and resolves type names, members and method
calls with an inheritance-aware, precision-first strategy. Lookup order for a
non-worldbox source: current source first, then worldbox — never a blind
same-name bind. Ambiguous stays ambiguous, unknowns stay unresolved/external.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field as dc_field

RESOLVER_VERSION = "2.0.0"

# Namespaces that are definitely not part of any indexed source.
EXTERNAL_ROOTS = {
    "System", "UnityEngine", "Unity", "Microsoft", "Newtonsoft", "Mono",
    "DG", "FMOD", "Facepunch", "Google", "Firebase", "Apple", "Steamworks",
    "ICSharpCode", "NUnit", "C5", "Best", "TMPro", "Sirenix", "AOT",
    "HarmonyLib", "Harmony", "Gameloop", "YamlDotNet", "Humanizer",
}

_GENERIC_RE = re.compile(r"<[^<>]*>")

TypeKey = tuple  # (source_id: str, full_name: str)


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
    source: str | None = None       # source_id of the resolved declaration
    type_full: str | None = None
    type_id: int | None = None
    method_id: int | None = None
    field_id: int | None = None
    prop_id: int | None = None
    signature: str | None = None
    return_type: str | None = None
    target_kind: str | None = None  # method / field / property / constructor / type
    candidates: list = dc_field(default_factory=list)
    declaring_hint: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "resolved"

    @property
    def type_key(self) -> TypeKey | None:
        if self.type_full is None:
            return None
        return (self.source, self.type_full)

    def logical_key(self, name_hint: str) -> str:
        kind = self.target_kind or "unknown"
        if self.ok and self.type_full:
            if kind in ("method", "constructor"):
                return f"method:{self.source}:{self.type_full}.{self.signature}"
            return f"{kind}:{self.source}:{self.type_full}.{name_hint}"
        prefix = {"method": "method?", "constructor": "method?", "field": "field?", "property": "prop?"}.get(kind, "?")
        return f"{prefix}{name_hint}"


class Resolver:
    """Symbol tables + lookup over all indexed sources in one database."""

    def __init__(self, conn: sqlite3.Connection):
        self.types: dict[TypeKey, dict] = {}
        self.types_by_name: dict[str, list[TypeKey]] = {}
        self.methods: dict[TypeKey, dict[str, list[dict]]] = {}
        self.fields: dict[TypeKey, dict[str, dict]] = {}
        self.props: dict[TypeKey, dict[str, dict]] = {}
        self.bases: dict[TypeKey, list[tuple[str, TypeKey | None]]] = {}
        self.known_sources: set[str] = set()
        self._load(conn)

    def _load(self, conn: sqlite3.Connection) -> None:
        source_names = {row[0]: row[1] for row in conn.execute("SELECT id, source_id FROM sources")}
        for row in conn.execute(
            """SELECT t.id, s.source_id, t.full_name, t.name, t.kind, t.namespace
               FROM types t JOIN sources s ON s.id = t.source_id"""
        ):
            key = (row[1], row[2])
            self.types[key] = {"id": row[0], "name": row[3], "kind": row[4], "namespace": row[5], "source": row[1]}
            self.types_by_name.setdefault(row[3], []).append(key)
            self.known_sources.add(row[1])
        self._source_names = source_names
        for row in conn.execute(
            """SELECT s.source_id, t.full_name, m.id, m.name, m.signature, m.return_type
               FROM methods m JOIN types t ON t.id = m.type_id JOIN sources s ON s.id = t.source_id"""
        ):
            self.methods.setdefault((row[0], row[1]), {}).setdefault(row[3], []).append(
                {"id": row[2], "signature": row[4], "return_type": row[5]}
            )
        for row in conn.execute(
            """SELECT s.source_id, t.full_name, f.id, f.name, f.field_type
               FROM fields f JOIN types t ON t.id = f.type_id JOIN sources s ON s.id = f.source_id"""
        ):
            self.fields.setdefault((row[0], row[1]), {})[row[3]] = {"id": row[2], "type": row[4]}
        for row in conn.execute(
            """SELECT s.source_id, t.full_name, p.id, p.name, p.property_type
               FROM properties p JOIN types t ON t.id = p.type_id JOIN sources s ON s.id = p.source_id"""
        ):
            self.props.setdefault((row[0], row[1]), {})[row[3]] = {"id": row[2], "type": row[4]}
        for row in conn.execute(
            """SELECT s.source_id, t.full_name, i.target_name, s2.source_id, t2.full_name
               FROM inheritance i
               JOIN types t ON t.id = i.type_id JOIN sources s ON s.id = t.source_id
               LEFT JOIN types t2 ON t2.id = i.target_type_id
               LEFT JOIN sources s2 ON s2.id = t2.source_id"""
        ):
            resolved = (row[3], row[4]) if row[3] and row[4] else None
            self.bases.setdefault((row[0], row[1]), []).append((row[2], resolved))

    # --- type chain ---------------------------------------------------------

    def type_chain(self, key: TypeKey) -> list[TypeKey]:
        """Declaring type first, then resolved base chain (cross-source, cycle-safe)."""
        chain = [key]
        seen = {key}
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

    def _resolve_base_textual(self, textual: str, declaring: TypeKey) -> TypeKey | None:
        base = strip_generics(textual).split(".")[-1]
        info = self.types.get(declaring)
        ns = info["namespace"] if info else None
        candidates = []
        if ns:
            candidates.append((declaring[0], f"{ns}.{base}"))
        candidates.append((declaring[0], base))
        for candidate in candidates:
            if candidate in self.types:
                return candidate
        # cross-source fallback: worldbox types are the game API surface
        if declaring[0] != "worldbox":
            if ("worldbox", base) in self.types:
                return ("worldbox", base)
        return None

    def chain_is_external(self, key: TypeKey) -> bool:
        for textual, resolved in self.bases.get(key, []):
            if resolved:
                continue
            if is_external_name(textual):
                return True
        return False

    # --- type resolution ----------------------------------------------------

    def _candidate_keys(self, base: str, namespace: str | None, using_ns, current_type: TypeKey | None, source: str, search_source: str) -> list[TypeKey]:
        """Candidate keys to try, built for `search_source`.

        Nested-type candidates follow the current type chain (which may cross
        sources through inheritance); namespace/using/bare candidates are
        generated for the searched source.
        """
        candidates: list[TypeKey] = []
        if current_type is not None:
            for chain_type in self.type_chain(current_type):
                nested = (chain_type[0], f"{chain_type[1]}.{base}")
                candidates.append(nested)
        if namespace:
            candidates.append((search_source, f"{namespace}.{base}"))
        for ns in using_ns:
            candidates.append((search_source, f"{ns}.{base}"))
        candidates.append((search_source, base))
        return candidates

    def resolve_type(
        self,
        name: str,
        namespace: str | None = None,
        using_ns: tuple[str, ...] = (),
        current_type: TypeKey | None = None,
        source: str = "worldbox",
    ) -> Resolution:
        base = strip_generics(name).strip()
        if not base:
            return Resolution("unresolved")

        if "." in base:
            for candidate_source in ([source] + (["worldbox"] if source != "worldbox" else [])):
                key = (candidate_source, base)
                if key in self.types:
                    return Resolution("resolved", source=candidate_source, type_full=base, type_id=self.types[key]["id"], target_kind="type")
            if is_external_name(base):
                return Resolution("external", declaring_hint=base)
            return Resolution("unresolved", declaring_hint=base)

        # current source first — a same-name type in worldbox never shadows it
        search_sources = [source]
        if source != "worldbox" and "worldbox" in self.known_sources:
            search_sources.append("worldbox")

        unique: list[TypeKey] = []
        seen: set[TypeKey] = set()
        for candidate_source in search_sources:
            for key in self._candidate_keys(base, namespace, using_ns, current_type, source, candidate_source):
                if key in self.types and key not in seen:
                    seen.add(key)
                    unique.append(key)
            if unique:
                break  # current source wins over cross-source candidates

        if len(unique) == 1:
            key = unique[0]
            return Resolution("resolved", source=key[0], type_full=key[1], type_id=self.types[key]["id"], target_kind="type")
        if len(unique) > 1:
            return Resolution("ambiguous", candidates=[f"{k[0]}:{k[1]}" for k in unique], declaring_hint=base)
        if is_external_name(base):
            return Resolution("external", declaring_hint=base)
        return Resolution("unresolved", declaring_hint=base)

    # --- member resolution ----------------------------------------------------

    def resolve_member(self, receiver: TypeKey | None, member: str) -> Resolution:
        """Resolve a field/property on a receiver type (inheritance-aware)."""
        if receiver is None:
            return Resolution("unresolved", declaring_hint=member)
        if receiver not in self.types:
            return Resolution("external" if is_external_name(receiver[1]) else "unresolved", declaring_hint=receiver[1])

        # nearest declaration wins (C# shadowing)
        for chain_type in self.type_chain(receiver):
            field_hit = self.fields.get(chain_type, {}).get(member)
            prop_hit = self.props.get(chain_type, {}).get(member)
            if field_hit and prop_hit:
                return Resolution("ambiguous", candidates=[chain_type[1]], declaring_hint=f"{receiver[1]}.{member}")
            if field_hit:
                return Resolution("resolved", source=chain_type[0], type_full=chain_type[1], field_id=field_hit["id"], target_kind="field")
            if prop_hit:
                return Resolution("resolved", source=chain_type[0], type_full=chain_type[1], prop_id=prop_hit["id"], target_kind="property")

        if self.chain_is_external(receiver):
            return Resolution("external", declaring_hint=f"{receiver[1]}.{member}")
        return Resolution("unresolved", declaring_hint=f"{receiver[1]}.{member}")

    def resolve_method(self, receiver: TypeKey | None, name: str, arg_count: int | None = None, constructor: bool = False) -> Resolution:
        """Resolve a method call on a receiver type (inheritance + arity aware)."""
        method_name = ".ctor" if constructor else name
        if receiver is None:
            return Resolution("unresolved", declaring_hint=name)
        if receiver not in self.types:
            status = "external" if is_external_name(receiver[1]) else "unresolved"
            return Resolution(status, declaring_hint=f"{receiver[1]}.{name}")

        candidates: list[tuple[TypeKey, dict]] = []
        for chain_type in self.type_chain(receiver):
            for method in self.methods.get(chain_type, {}).get(method_name, []):
                candidates.append((chain_type, method))
        if not candidates:
            if self.chain_is_external(receiver):
                return Resolution("external", declaring_hint=f"{receiver[1]}.{name}")
            return Resolution("unresolved", declaring_hint=f"{receiver[1]}.{name}")

        if arg_count is not None and len(candidates) > 1:
            by_arity = [c for c in candidates if self._arity(c[1]["signature"]) == arg_count]
            if by_arity:
                candidates = by_arity

        if len(candidates) == 1:
            owner, method = candidates[0]
            return Resolution(
                "resolved",
                source=owner[0],
                type_full=owner[1],
                method_id=method["id"],
                signature=method["signature"],
                return_type=method["return_type"],
                target_kind="constructor" if constructor else "method",
            )
        return Resolution(
            "ambiguous",
            candidates=[f"{owner[0]}:{owner[1]}.{method['signature']}" for owner, method in candidates],
            declaring_hint=f"{receiver[1]}.{name}",
        )

    @staticmethod
    def _arity(signature: str) -> int:
        inner = signature[signature.find("(") + 1 : signature.rfind(")")]
        return len(inner) // 2 if inner else 0

    def member_type(self, receiver: TypeKey, member: str) -> str | None:
        for chain_type in self.type_chain(receiver):
            if member in self.fields.get(chain_type, {}):
                return self._normalize_type_text(self.fields[chain_type][member]["type"], chain_type)
            if member in self.props.get(chain_type, {}):
                return self._normalize_type_text(self.props[chain_type][member]["type"], chain_type)
        return None

    def method_return_type(self, resolution: Resolution) -> str | None:
        if resolution.ok and resolution.return_type and resolution.type_key:
            return self._normalize_type_text(resolution.return_type, resolution.type_key)
        return None

    def _normalize_type_text(self, declared: str | None, context: TypeKey | None):
        """Map a declared member/method type text to an indexed TypeKey.

        Returns a TypeKey tuple for indexed types, a plain string for external
        type text, or None when unknown.
        """
        if not declared:
            return None
        base = strip_generics(declared)
        if base.split("<")[0].split(".")[0] in EXTERNAL_ROOTS:
            return base
        candidates = []
        if context:
            info = self.types.get(context)
            ns = info["namespace"] if info else None
            if ns:
                candidates.append((context[0], f"{ns}.{base}"))
            candidates.append((context[0], base))
            if context[0] != "worldbox":
                candidates.append(("worldbox", base))
        for candidate in candidates:
            if candidate in self.types:
                return candidate
        return None

    def key_for(self, source: str, full_name: str) -> TypeKey | None:
        key = (source, full_name)
        return key if key in self.types else None
