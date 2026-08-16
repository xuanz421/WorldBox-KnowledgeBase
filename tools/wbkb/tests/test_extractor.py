"""Extraction orchestration tests (no real decompiler needed)."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wbkb import extractor


FAKE_EXTRACTOR = {
    "name": "ilspycmd",
    "version": "1.0.0-test",
    "mode": "test",
    "install": "test",
    "options": ["-p"],
}

FAKE_EXTRACTOR_V2 = {**FAKE_EXTRACTOR, "version": "2.0.0-test"}


class FakeRunner:
    """subprocess.run stand-in that writes a fake decompiled tree."""

    def __init__(self, valid: bool = True):
        self.valid = valid
        self.calls = []

    def run(self, cmd, cwd, capture_output, text, timeout, **_kw):
        self.calls.append(cmd)
        out_dir = Path(cmd[cmd.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.valid:
            _write_valid_source(out_dir)
        else:
            (out_dir / "garbage.cs").write_text("no type declaration here", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="ilspycmd: fake", stderr="")


def _write_valid_source(out_dir: Path) -> None:
    (out_dir / "Project.csproj").write_text("<Project />", encoding="utf-8")
    for name in ("Actor", "City", "Kingdom"):
        (out_dir / f"{name}.cs").write_text(
            f"public class {name} {{ }}\n", encoding="utf-8"
        )
    for i in range(extractor.MIN_CSHARP_FILES):
        (out_dir / f"Type{i:03d}.cs").write_text(
            f"public class Type{i:03d} {{ }}\n", encoding="utf-8"
        )


class ExtractionTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.repo.mkdir()
        self.assembly = tmp / "Assembly-CSharp.dll"
        self.assembly_bytes = b"FAKE-ASSEMBLY-BYTES"
        self.assembly.write_bytes(self.assembly_bytes)
        self.registry = self._make_registry()

    def tearDown(self):
        self._tmp.cleanup()

    def _make_registry(self, version: str = "9.9.9") -> dict:
        return {
            "sources": {
                "worldbox": {
                    "kind": "game",
                    "game_version": version,
                    "root_path": str(self._tmp.name),
                    "assembly": {
                        "path": str(self.assembly),
                        "sha256": hashlib.sha256(self.assembly_bytes).hexdigest(),
                        "size": len(self.assembly_bytes),
                    },
                }
            }
        }

    def _snap_dir(self, snap_id: str) -> Path:
        return self.repo / extractor.SNAPSHOTS_DIR / snap_id


class SnapshotIdentityTests(ExtractionTestBase):
    def test_snapshot_id_with_version(self):
        self.assertEqual(
            extractor.snapshot_id("0.51.2", "a" * 64), "worldbox-0.51.2-" + "a" * 12
        )

    def test_snapshot_id_without_version(self):
        self.assertEqual(extractor.snapshot_id(None, "a" * 64), "worldbox-" + "a" * 12)

    def test_version_parsing(self):
        text = "ilspycmd: 11.0.0.9375\nICSharpCode.Decompiler: 11.0.0.9375\n"
        self.assertEqual(extractor._parse_ilspy_version(text), "11.0.0.9375")
        self.assertIsNone(extractor._parse_ilspy_version("random output"))


class ExtractionOrchestrationTests(ExtractionTestBase):
    def test_created_then_unchanged(self):
        runner = FakeRunner()
        r1 = extractor.perform_extraction(self.repo, self.registry, runner=runner, extractor_info=FAKE_EXTRACTOR)
        self.assertEqual(r1["status"], "CREATED")
        snap = r1["snapshot"]
        manifest_path = self._snap_dir(snap) / "extraction-manifest.json"
        self.assertTrue(manifest_path.is_file())
        first_mtime = manifest_path.stat().st_mtime_ns

        self.assertEqual(len(runner.calls), 1)
        r2 = extractor.perform_extraction(self.repo, self.registry, runner=runner, extractor_info=FAKE_EXTRACTOR)
        self.assertEqual(r2["status"], "UNCHANGED")
        self.assertEqual(len(runner.calls), 1)  # no second decompile
        self.assertEqual(manifest_path.stat().st_mtime_ns, first_mtime)

    def test_manifest_has_no_absolute_paths(self):
        r = extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        text = (self._snap_dir(r["snapshot"]) / "extraction-manifest.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.repo), text)
        self.assertNotIn(str(self._tmp.name), text)
        self.assertIsNone(re.search(r"[A-Za-z]:\\\\", text))
        manifest = json.loads(text)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["extractor"]["version"], "1.0.0-test")
        self.assertGreaterEqual(manifest["output"]["csharp_files"], extractor.MIN_CSHARP_FILES)
        self.assertEqual(manifest["validation"]["core_types"], {"Actor": True, "City": True, "Kingdom": True})
        self.assertIn("not original source code", manifest["notes"])

    def test_changed_assembly_creates_new_snapshot(self):
        r1 = extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        self.assembly_bytes = b"DIFFERENT-ASSEMBLY"
        self.assembly.write_bytes(self.assembly_bytes)
        registry2 = self._make_registry()
        r2 = extractor.perform_extraction(self.repo, registry2, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        self.assertNotEqual(r1["snapshot"], r2["snapshot"])
        self.assertTrue(self._snap_dir(r1["snapshot"]).is_dir())
        self.assertTrue(self._snap_dir(r2["snapshot"]).is_dir())  # versions coexist

    def test_changed_extractor_version_replaces(self):
        extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        r2 = extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR_V2)
        self.assertEqual(r2["status"], "REPLACED-EXTRACTOR")
        manifest = json.loads(
            (self._snap_dir(r2["snapshot"]) / "extraction-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["extractor"]["version"], "2.0.0-test")

    def test_failed_extraction_keeps_existing_snapshot(self):
        extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        snap = extractor.snapshot_id("9.9.9", hashlib.sha256(self.assembly_bytes).hexdigest())
        manifest_path = self._snap_dir(snap) / "extraction-manifest.json"
        before = manifest_path.read_text(encoding="utf-8")
        before_mtime = manifest_path.stat().st_mtime_ns

        with self.assertRaises(extractor.ExtractionError):
            extractor.perform_extraction(
                self.repo, self.registry, force=True, runner=FakeRunner(valid=False), extractor_info=FAKE_EXTRACTOR
            )
        # existing snapshot untouched, temp cleaned
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)
        self.assertEqual(manifest_path.stat().st_mtime_ns, before_mtime)
        self.assertFalse((self.repo / extractor.TMP_DIR / snap).exists())

    def test_assembly_hash_mismatch_is_rejected(self):
        self.assembly.write_bytes(b"TAMPERED")
        with self.assertRaisesRegex(extractor.ExtractionError, "changed since last discovery"):
            extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)

    def test_no_decompiler_raises(self):
        with self.assertRaisesRegex(extractor.ExtractionError, "no decompiler"):
            extractor.perform_extraction(
                self.repo, self.registry,
                runner=_FailingRunner(), extractor_info=None,
            )

    def test_snapshot_state_transitions(self):
        state = extractor.snapshot_state(self.repo, self.registry)
        self.assertEqual(state["state"], "MISSING")
        extractor.perform_extraction(self.repo, self.registry, runner=FakeRunner(), extractor_info=FAKE_EXTRACTOR)
        state = extractor.snapshot_state(self.repo, self.registry, FAKE_EXTRACTOR)
        self.assertEqual(state["state"], "OK")
        state = extractor.snapshot_state(self.repo, self.registry, FAKE_EXTRACTOR_V2)
        self.assertEqual(state["state"], "OK-EXTRACTOR-CHANGED")
        # a newer game assembly makes the existing snapshot stale
        registry2 = self._make_registry(version="9.9.10")
        state = extractor.snapshot_state(self.repo, registry2, FAKE_EXTRACTOR)
        self.assertEqual(state["state"], "STALE")


class _FailingRunner:
    def run(self, cmd, **_kw):
        raise OSError("dotnet not available")


if __name__ == "__main__":
    unittest.main()
