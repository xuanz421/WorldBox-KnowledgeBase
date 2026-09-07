"""Qdrant local persistent vector store (data/generated/vector/qdrant/).

Thin, replaceable wrapper: deterministic point ids from chunk ids, upsert /
delete / search plus collection lifecycle. Never a source of truth — the
payload mirrors chunk fields only.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .schema import COLLECTION_NAME, RagError

_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL


def point_id(chunk_id: str) -> str:
    """Deterministic UUIDv5 so the same chunk always maps to the same point."""
    return str(uuid.uuid5(_NAMESPACE, f"wbkb:{chunk_id}"))


class VectorStore:
    """Owns one local Qdrant client; must be closed (Windows file locks)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient  # lazy import

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(self.path))
        return self._client

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # --- collection lifecycle -------------------------------------------------

    def collection_exists(self) -> bool:
        client = self._ensure_client()
        return any(c.name == COLLECTION_NAME for c in client.get_collections().collections)

    def collection_dimension(self) -> int | None:
        if not self.collection_exists():
            return None
        client = self._ensure_client()
        info = client.get_collection(COLLECTION_NAME)
        vectors = info.config.params.vectors
        size = getattr(vectors, "size", None)
        return int(size) if size is not None else None

    def ensure_collection(self, dimension: int) -> str:
        """Create the collection if absent; recreate when dimensions mismatch.

        Returns "kept", "created" or "recreated".
        """
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        current = self.collection_dimension()
        if current == dimension:
            return "kept"
        if current is not None:
            client.delete_collection(COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        return "recreated" if current is not None else "created"

    def reset_collection(self, dimension: int) -> str:
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        if self.collection_exists():
            client.delete_collection(COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        return "created"

    # --- data operations --------------------------------------------------------

    def upsert_chunks(self, chunks: list, vectors: list[list[float]]) -> None:
        from qdrant_client.models import PointStruct

        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise RagError("chunk/vector length mismatch")
        client = self._ensure_client()
        points = [
            PointStruct(id=point_id(chunk.chunk_id), vector=vector, payload=chunk.payload())
            for chunk, vector in zip(chunks, vectors)
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

    def delete_chunk_ids(self, chunk_ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        if not chunk_ids:
            return
        client = self._ensure_client()
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=PointIdsList(points=[point_id(cid) for cid in chunk_ids]),
            wait=True,
        )

    def count(self) -> int:
        if not self.collection_exists():
            return 0
        client = self._ensure_client()
        return int(client.count(COLLECTION_NAME, exact=True).count)

    def search(self, vector: list[float], limit: int) -> list[dict]:
        client = self._ensure_client()
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        results = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                {
                    "score": float(point.score),
                    "chunk_id": payload.get("chunk_id", ""),
                    "document_type": payload.get("document_type", ""),
                    "source_path": payload.get("source_path", ""),
                    "title": payload.get("title", ""),
                    "section": payload.get("section", ""),
                    "text": payload.get("text", ""),
                    "content_hash": payload.get("content_hash", ""),
                }
            )
        return results
