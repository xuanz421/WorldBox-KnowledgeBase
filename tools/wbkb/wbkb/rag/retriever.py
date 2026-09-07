"""Semantic retrieval: embed a query and return the top markdown chunks.

Read-only over the vector index built by `python -m wbkb vector build`.
A missing or identity-stale state file is an error (never a silent
rebuild): the caller is told to run the build first.
"""

from __future__ import annotations

from pathlib import Path

from . import schema
from .embeddings import get_backend
from .vector_store import VectorStore

DEFAULT_LIMIT = 5


def semantic_search(repo_root: Path, query: str, limit: int = DEFAULT_LIMIT) -> dict:
    repo_root = Path(repo_root)
    query = query.strip()
    if not query:
        raise schema.RagError("empty query")
    limit = max(1, limit)

    state = schema.load_state(repo_root)
    if state is None:
        raise schema.RagError("vector index missing; run: python -m wbkb vector build")
    if schema.state_identity(state) != schema.current_identity(
        state.get("embedding_dimension") or 0,
        backend=state.get("embedding_backend") or "",
        model=state.get("embedding_model") or "",
    ):
        raise schema.RagError(
            "vector index is stale (chunker/embedding/index version changed);"
            " run: python -m wbkb vector build"
        )

    backend = get_backend(state.get("embedding_backend"))
    vector = backend.embed_query(query)

    with VectorStore(schema.qdrant_dir(repo_root)) as store:
        if not store.collection_exists() or store.collection_dimension() != state.get("embedding_dimension"):
            raise schema.RagError(
                "vector index is stale or missing; run: python -m wbkb vector build"
            )
        hits = store.search(vector, limit)

    return {
        "query": query,
        "limit": limit,
        "results": [
            {
                "score": round(hit["score"], 4),
                "chunk_id": hit["chunk_id"],
                "document_type": hit["document_type"],
                "source_path": hit["source_path"],
                "title": hit["title"],
                "section": hit["section"],
                "text": hit["text"],
                "content_hash": hit["content_hash"],
            }
            for hit in hits
        ],
    }
