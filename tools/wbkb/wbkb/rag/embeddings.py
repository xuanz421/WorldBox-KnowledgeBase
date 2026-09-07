"""Embedding backends behind a small registry.

The default backend wraps BAAI/bge-m3 via sentence-transformers; heavy
libraries are imported lazily so the rest of WBKB never pays for them.
Alternative models (or deterministic fakes in tests) plug in through
register_backend without touching the builder or the retriever.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schema import EMBEDDING_MODEL, RagError

EMBED_BATCH_SIZE = 16


class EmbeddingBackend(ABC):
    """Minimal contract for embedding providers (Hybrid Retrieval can reuse)."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        ...


class BgeM3Backend(EmbeddingBackend):
    """BAAI/bge-m3 through sentence-transformers, L2-normalized (cosine)."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self._model_name = model_name
        self._model = None
        self._dimension: int | None = None

    @property
    def name(self) -> str:
        return "bge-m3"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy: torch et al.

            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            probe = self._load().encode(["dimension probe"], normalize_embeddings=True)
            self._dimension = int(probe.shape[1])
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self._dimension = int(vectors.shape[1])
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        self._dimension = int(vector.shape[0])
        return vector.tolist()


_REGISTRY: dict[str, object] = {}


def register_backend(name: str, factory) -> None:
    """Register a backend factory (name -> callable returning EmbeddingBackend)."""
    _REGISTRY[name] = factory


register_backend("bge-m3", BgeM3Backend)


def get_backend(name: str) -> EmbeddingBackend:
    factory = _REGISTRY.get(name)
    if factory is None:
        raise RagError(
            f"unknown embedding backend: {name} (available: {', '.join(sorted(_REGISTRY))})"
        )
    return factory()
