"""Shared constants, chunk schema and vector-index state for the RAG layer.

The state file (data/generated/vector/state.json, never committed) records
the rebuild identity: embedding backend + model + dimension, chunker
version, index version and per-file hashes. A mismatch on any identity
field forces a full rebuild so stale vectors are never silently reused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from ..registry import save_json_if_changed

RAG_INDEX_VERSION = 1
CHUNKER_VERSION = "1.0.0"

EMBEDDING_BACKEND = "bge-m3"
EMBEDDING_MODEL = "BAAI/bge-m3"

VECTOR_DIR_REL = Path("data/generated/vector")
QDRANT_DIR_REL = VECTOR_DIR_REL / "qdrant"
STATE_REL = VECTOR_DIR_REL / "state.json"

DOC_ROOTS = ("knowledge", "docs")
COLLECTION_NAME = "wbkb_md_chunks"

_STATE_VOLATILE = ("built_at",)


class RagError(RuntimeError):
    pass


@dataclass
class Chunk:
    chunk_id: str        # deterministic: hash of (chunker version, path, section, seq)
    document_type: str   # root dir name: "knowledge" | "docs"
    source_path: str     # repo-relative posix path
    title: str           # document title (first H1, else filename stem)
    section: str         # heading path joined with " > ", "" for preamble
    text: str            # chunk body (no heading line, fences intact)
    content_hash: str    # sha256(text)

    def payload(self) -> dict:
        """Qdrant payload — chunk fields only, no SQLite data duplicated."""
        return {
            "chunk_id": self.chunk_id,
            "document_type": self.document_type,
            "source_path": self.source_path,
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "content_hash": self.content_hash,
        }

    def embedding_input(self) -> str:
        """Heading context + body improves recall over body-only embeddings."""
        parts = [p for p in (self.title, self.section, self.text) if p]
        return "\n".join(parts)


def vector_dir(repo_root: Path) -> Path:
    return Path(repo_root) / VECTOR_DIR_REL


def qdrant_dir(repo_root: Path) -> Path:
    return Path(repo_root) / QDRANT_DIR_REL


def state_path(repo_root: Path) -> Path:
    return Path(repo_root) / STATE_REL


def load_state(repo_root: Path) -> dict | None:
    path = state_path(repo_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and "chunks" in data else None


def save_state(repo_root: Path, state: dict) -> bool:
    return save_json_if_changed(state_path(repo_root), state, volatile_keys=_STATE_VOLATILE)


def state_identity(state: dict | None) -> tuple:
    """Identity fields — any change invalidates every stored vector."""
    if not state:
        return ()
    return (
        state.get("rag_index_version"),
        state.get("chunker_version"),
        state.get("embedding_backend"),
        state.get("embedding_model"),
        state.get("embedding_dimension"),
    )


def current_identity(dimension: int, backend: str = EMBEDDING_BACKEND, model: str = EMBEDDING_MODEL) -> tuple:
    return (RAG_INDEX_VERSION, CHUNKER_VERSION, backend, model, dimension)


def chunk_to_state_entry(chunk: Chunk) -> dict:
    return {"content_hash": chunk.content_hash, "source_path": chunk.source_path}


def chunks_to_state(chunks: list[Chunk]) -> dict:
    return {c.chunk_id: chunk_to_state_entry(c) for c in chunks}
