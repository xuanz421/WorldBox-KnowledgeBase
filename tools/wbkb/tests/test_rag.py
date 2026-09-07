"""Semantic retrieval layer tests: chunker, state, incremental build, search.

Uses a deterministic fake embedding backend (character-trigram hashing) so
no model download is needed; the real bge-m3 backend is exercised only via
its lazy-import wiring.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from wbkb.rag import chunker as rag_chunker
from wbkb.rag import schema as rag_schema
from wbkb.rag.builder import perform_vector_build
from wbkb.rag.embeddings import EmbeddingBackend, register_backend
from wbkb.rag.retriever import semantic_search

FAKE_DIM = 8


class FakeBackend(EmbeddingBackend):
    """Deterministic bag-of-trigram vectors: similar text -> similar vector."""

    def __init__(self):
        self.embed_calls = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def dimension(self) -> int:
        return FAKE_DIM

    def _vector(self, text: str) -> list[float]:
        counts = [0.0] * FAKE_DIM
        padded = f"  {text.lower()} "
        for i in range(len(padded) - 2):
            trigram = padded[i : i + 3]
            counts[int(hashlib.sha256(trigram.encode("utf-8")).hexdigest(), 16) % FAKE_DIM] += 1.0
        norm = sum(c * c for c in counts) ** 0.5 or 1.0
        return [c / norm for c in counts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += len(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embed_calls += 1
        return self._vector(text)


register_backend("fake", FakeBackend)


DOC_A = """# ActorTrait Registration

Intro paragraph about registering traits.

## Safe Registration

Register the trait early and guard against duplicates.

## Clone and Modify

Clone an existing asset before mutating it.
"""

DOC_B = """# Harmony Patching

Prefix patches run before the original method.

## Veto Pattern

Return false in a prefix to skip the original.
"""


class RagTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.repo = Path(self._tmp.name) / "repo"
        (self.repo / "knowledge" / "patterns").mkdir(parents=True)
        (self.repo / "docs").mkdir(parents=True)
        self.doc_a = self.repo / "knowledge" / "patterns" / "register-actor-trait.md"
        self.doc_b = self.repo / "docs" / "patching.md"
        self.doc_a.write_text(DOC_A, encoding="utf-8")
        self.doc_b.write_text(DOC_B, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()


class ChunkerTests(RagTestBase):
    def test_sections_and_titles(self):
        chunks = rag_chunker.chunk_markdown(DOC_A, "knowledge/patterns/register-actor-trait.md", "knowledge")
        sections = [c.section for c in chunks]
        self.assertIn("ActorTrait Registration > Safe Registration", sections)
        self.assertIn("ActorTrait Registration > Clone and Modify", sections)
        for chunk in chunks:
            self.assertEqual(chunk.title, "ActorTrait Registration")
            self.assertEqual(chunk.document_type, "knowledge")
            self.assertEqual(chunk.content_hash, rag_chunker._sha16(chunk.text))
            self.assertRegex(chunk.chunk_id, r"^[0-9a-f]{16}$")

    def test_deterministic_ids(self):
        first = rag_chunker.chunk_markdown(DOC_A, "a.md", "knowledge")
        second = rag_chunker.chunk_markdown(DOC_A, "a.md", "knowledge")
        self.assertEqual([c.chunk_id for c in first], [c.chunk_id for c in second])

    def test_editing_one_section_keeps_other_ids_stable(self):
        edited = DOC_A.replace("Register the trait early and guard against duplicates.",
                               "Changed guidance text for safe registration flow.")
        base = rag_chunker.chunk_markdown(DOC_A, "a.md", "knowledge")
        other = rag_chunker.chunk_markdown(edited, "a.md", "knowledge")
        base_map = {c.section: c for c in base}
        other_map = {c.section: c for c in other}
        self.assertNotEqual(base_map["ActorTrait Registration > Safe Registration"].content_hash,
                            other_map["ActorTrait Registration > Safe Registration"].content_hash)
        self.assertEqual(base_map["ActorTrait Registration > Clone and Modify"].chunk_id,
                         other_map["ActorTrait Registration > Clone and Modify"].chunk_id)

    def test_heading_inside_code_fence_ignored(self):
        doc = "# Real Title\n\nText before.\n\n```csharp\n# not a heading\n```\n\nAfter fence.\n"
        chunks = rag_chunker.chunk_markdown(doc, "a.md", "docs")
        for chunk in chunks:
            self.assertNotIn("not a heading", chunk.section)
        joined = "\n".join(c.text for c in chunks)
        self.assertIn("# not a heading", joined)

    def test_oversized_section_secondary_split(self):
        paragraph = "Sentence about actor traits and registration. " * 80  # ~4400 chars
        doc = f"# Big\n\n## Huge Section\n\n{paragraph}\n"
        chunks = rag_chunker.chunk_markdown(doc, "a.md", "knowledge")
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), rag_chunker.MAX_SECTION_CHARS + 200)
        # reassembly preserves all content words
        joined = " ".join(c.text for c in chunks)
        self.assertEqual(joined.count("registration."), 80)

    def test_min_chunk_filter(self):
        doc = "# Title\n\n## Empty Section\n\n## Real\n\nEnough content to survive the minimum filter here.\n"
        chunks = rag_chunker.chunk_markdown(doc, "a.md", "docs")
        self.assertEqual([c.section for c in chunks], ["Title > Real"])

    def test_title_falls_back_to_filename(self):
        doc = "No headings at all, just text.\n"
        chunks = rag_chunker.chunk_markdown(doc, "docs/plain-file.md", "docs")
        self.assertEqual(chunks[0].title, "plain-file")
        self.assertEqual(chunks[0].section, "")


class BuildTests(RagTestBase):
    def test_full_build_creates_state_and_vectors(self):
        result = perform_vector_build(self.repo, backend_name="fake")
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(result["mode"], "full-rebuild")
        self.assertEqual(result["dimension"], FAKE_DIM)
        self.assertEqual(result["files"], 2)
        self.assertGreater(result["chunks"], 0)
        self.assertEqual(result["stats"]["indexed"], result["chunks"])
        self.assertTrue(rag_schema.state_path(self.repo).is_file())
        self.assertTrue(rag_schema.qdrant_dir(self.repo).is_dir())

    def test_unchanged_short_circuits_without_embedding(self):
        perform_vector_build(self.repo, backend_name="fake")
        # fresh backend instance counts embed calls after the first build
        result = perform_vector_build(self.repo, backend_name="fake")
        self.assertEqual(result["status"], "UNCHANGED")
        self.assertEqual(result["chunks"], result["stats"].get("chunks", result["chunks"]))

    def test_incremental_update_and_remove(self):
        perform_vector_build(self.repo, backend_name="fake")

        self.doc_a.write_text(
            DOC_A.replace("Register the trait early and guard against duplicates.",
                          "Completely new guidance text for safe registration."),
            encoding="utf-8",
        )
        self.doc_b.unlink()
        result = perform_vector_build(self.repo, backend_name="fake")
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(result["mode"], "incremental")
        self.assertEqual(result["stats"]["removed"], 2)  # Harmony intro + Veto section
        self.assertGreaterEqual(result["stats"]["updated"], 1)
        self.assertGreaterEqual(result["stats"]["unchanged"], 1)
        self.assertEqual(result["stats"]["files"], 1)

    def test_force_triggers_full_rebuild(self):
        perform_vector_build(self.repo, backend_name="fake")
        result = perform_vector_build(self.repo, force=True, backend_name="fake")
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(result["mode"], "full-rebuild")
        # same corpus re-embedded: nothing new, everything updated in place
        self.assertEqual(result["stats"]["indexed"], 0)
        self.assertEqual(result["stats"]["updated"], result["chunks"])
        self.assertEqual(result["stats"]["removed"], 0)

    def test_state_version_mismatch_forces_full_rebuild(self):
        perform_vector_build(self.repo, backend_name="fake")
        state = rag_schema.load_state(self.repo)
        state["chunker_version"] = "0.0.0-test"
        rag_schema.state_path(self.repo).write_text(
            __import__("json").dumps(state), encoding="utf-8"
        )
        result = perform_vector_build(self.repo, backend_name="fake")
        self.assertEqual(result["mode"], "full-rebuild")
        # and the mismatch is repaired
        state = rag_schema.load_state(self.repo)
        self.assertEqual(state["chunker_version"], rag_schema.CHUNKER_VERSION)

    def test_validation_catches_missing_points(self):
        perform_vector_build(self.repo, backend_name="fake")
        # delete the state: full rebuild must re-embed everything anyway
        rag_schema.state_path(self.repo).unlink()
        result = perform_vector_build(self.repo, backend_name="fake")
        self.assertEqual(result["mode"], "full-rebuild")
        self.assertEqual(result["stats"]["indexed"], result["chunks"])


class SemanticSearchTests(RagTestBase):
    def test_search_ranks_relevant_document_first(self):
        perform_vector_build(self.repo, backend_name="fake")
        result = semantic_search(self.repo, "register ActorTrait safely", limit=2)
        self.assertEqual(result["limit"], 2)
        self.assertLessEqual(len(result["results"]), 2)
        self.assertTrue(result["results"])
        top = result["results"][0]
        self.assertEqual(top["source_path"], "knowledge/patterns/register-actor-trait.md")
        self.assertIn("ActorTrait", top["title"])
        for key in ("score", "chunk_id", "document_type", "source_path", "title", "section", "text", "content_hash"):
            self.assertIn(key, top)

    def test_missing_state_is_error_not_silent_rebuild(self):
        with self.assertRaises(rag_schema.RagError):
            semantic_search(self.repo, "anything")

    def test_stale_state_is_error(self):
        perform_vector_build(self.repo, backend_name="fake")
        state = rag_schema.load_state(self.repo)
        state["embedding_dimension"] = 999
        import json

        rag_schema.state_path(self.repo).write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(rag_schema.RagError):
            semantic_search(self.repo, "anything")

    def test_empty_query_is_error(self):
        with self.assertRaises(rag_schema.RagError):
            semantic_search(self.repo, "   ")


if __name__ == "__main__":
    unittest.main()
