"""Vector index builder: markdown docs -> chunks -> embeddings -> Qdrant.

Rebuild identity = chunker version + embedding backend/model + dimension +
rag index version (per-chunk drift handled by content_hash comparison). The
embedding model is loaded only when at least one chunk actually needs
embedding; a fully unchanged corpus short-circuits before any model load.

Incremental (identity matches): only new/changed chunks are embedded and
deleted chunks removed. Any identity change, missing/reset collection or
--force escalates to a full rebuild with a fresh collection so stale
vectors can never survive.
"""

from __future__ import annotations

from pathlib import Path

from .. import util
from . import schema
from .chunker import chunk_markdown
from .embeddings import get_backend
from .vector_store import VectorStore


def _collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in schema.DOC_ROOTS:
        root_dir = Path(repo_root) / root_name
        if not root_dir.is_dir():
            continue
        files.extend(root_dir.rglob("*.md"))
    return sorted(files, key=lambda p: p.relative_to(repo_root).as_posix())


def _chunk_corpus(repo_root: Path, files: list[Path]) -> list:
    chunks = []
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        document_type = rel.split("/", 1)[0]
        chunks.extend(chunk_markdown(text, rel, document_type))
    return chunks


def _model_name(backend) -> str:
    return getattr(backend, "model_name", backend.name)


def _fast_path_state(repo_root: Path, state: dict, file_hashes: dict, backend_name: str) -> dict | None:
    """UNCHANGED result when identity + corpus are unchanged, without loading the model."""
    expected_model = schema.EMBEDDING_MODEL if backend_name == schema.EMBEDDING_BACKEND else backend_name
    if schema.state_identity(state) != schema.current_identity(
        state.get("embedding_dimension") or 0, backend=backend_name, model=expected_model
    ):
        return None
    if state.get("files") != file_hashes:
        return None
    with VectorStore(schema.qdrant_dir(repo_root)) as store:
        if (
            store.collection_exists()
            and store.collection_dimension() == state.get("embedding_dimension")
            and store.count() > 0
        ):
            return {
                "status": "UNCHANGED",
                "mode": "",
                "roots": list(schema.DOC_ROOTS),
                "backend": state.get("embedding_backend"),
                "model": state.get("embedding_model"),
                "dimension": state.get("embedding_dimension"),
                "files": len(file_hashes),
                "chunks": len(state.get("chunks", {})),
                "stats": state.get("last_stats", {}),
            }
    return None


def perform_vector_build(repo_root: Path, force: bool = False, backend_name: str | None = None) -> dict:
    repo_root = Path(repo_root)
    backend_name = backend_name or schema.EMBEDDING_BACKEND

    files = _collect_files(repo_root)
    if not files:
        raise schema.RagError(f"no markdown files found under {', '.join(schema.DOC_ROOTS)}")
    file_hashes = {p.relative_to(repo_root).as_posix(): util.sha256_file(p) for p in files}
    state = schema.load_state(repo_root)

    if not force and state is not None:
        unchanged = _fast_path_state(repo_root, state, file_hashes, backend_name)
        if unchanged is not None:
            return unchanged

    chunks = _chunk_corpus(repo_root, files)
    new_entries = schema.chunks_to_state(chunks)
    old_entries = state.get("chunks", {}) if state else {}

    backend = get_backend(backend_name)
    dimension = backend.dimension
    actual_identity = schema.current_identity(dimension, backend=backend.name, model=_model_name(backend))
    identity_ok = state is not None and schema.state_identity(state) == actual_identity

    with VectorStore(schema.qdrant_dir(repo_root)) as store:
        incremental = identity_ok and not force and store.ensure_collection(dimension) == "kept"
        if not incremental:
            store.reset_collection(dimension)

        if incremental:
            to_embed = [
                c for c in chunks
                if old_entries.get(c.chunk_id, {}).get("content_hash") != c.content_hash
            ]
        else:
            to_embed = list(chunks)
        to_embed_ids = {c.chunk_id for c in to_embed}
        removed_ids = [cid for cid in old_entries if cid not in new_entries]

        if to_embed:
            vectors = backend.embed_documents([c.embedding_input() for c in to_embed])
            store.upsert_chunks(to_embed, vectors)
        if incremental and removed_ids:
            store.delete_chunk_ids(removed_ids)

        stored = store.count()
        if stored != len(new_entries):
            raise schema.RagError(
                f"vector index validation failed: {stored} points stored vs {len(new_entries)} chunks"
            )

        stats = {
            "files": len(files),
            "chunks": len(chunks),
            "indexed": sum(1 for c in to_embed if c.chunk_id not in old_entries),
            "updated": sum(1 for c in to_embed if c.chunk_id in old_entries),
            "unchanged": sum(1 for c in chunks if c.chunk_id not in to_embed_ids),
            "removed": len(removed_ids),
        }
        schema.save_state(
            repo_root,
            {
                "rag_index_version": schema.RAG_INDEX_VERSION,
                "chunker_version": schema.CHUNKER_VERSION,
                "embedding_backend": backend.name,
                "embedding_model": _model_name(backend),
                "embedding_dimension": dimension,
                "built_at": util.now_iso(),
                "files": file_hashes,
                "chunks": new_entries,
                "last_stats": stats,
            },
        )

    return {
        "status": "CREATED",
        "mode": "incremental" if incremental else "full-rebuild",
        "roots": list(schema.DOC_ROOTS),
        "backend": backend.name,
        "model": _model_name(backend),
        "dimension": dimension,
        "files": len(files),
        "chunks": len(chunks),
        "stats": stats,
    }
