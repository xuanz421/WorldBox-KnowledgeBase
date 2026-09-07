"""Semantic retrieval layer (v0.10): markdown chunks -> embeddings -> Qdrant.

Scope: knowledge/**/*.md + docs/**/*.md only. This layer never becomes a
source of truth — SQLite stays the ground truth for code facts; vectors
only answer "which document section is relevant".
"""

from __future__ import annotations

from .schema import RagError
from .chunker import Chunk, chunk_markdown, CHUNKER_VERSION
from .embeddings import get_backend, register_backend

__all__ = [
    "RagError",
    "Chunk",
    "chunk_markdown",
    "CHUNKER_VERSION",
    "get_backend",
    "register_backend",
]
