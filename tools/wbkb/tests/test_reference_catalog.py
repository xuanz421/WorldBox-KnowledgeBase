"""Regression coverage for retaining manually curated reference-mod intakes."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


class ReferenceCatalogTests(unittest.TestCase):
    def test_regeneration_preserves_later_intakes_and_is_idempotent(self):
        script = Path(__file__).resolve().parents[2] / "gen_reference_mod_catalog.py"
        spec = importlib.util.spec_from_file_location("reference_catalog_generator", script)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)

        with tempfile.TemporaryDirectory() as tmp:
            generator.OUT = Path(tmp)
            # A profile added after the original inline harvest must survive.
            retained = {"source_id": "ref:later-intake", "name": "Later intake",
                        "profile": "mods/later-intake.md", "primary_systems": ["City"],
                        "confidence": "Mostly Verified", "custom_evidence": "Code/Main.cs:12",
                        "tier": "A", "harmony": True, "ui": False, "assets": True,
                        "persistence": True}
            (generator.OUT / "catalog.json").write_text(json.dumps([retained]), encoding="utf-8")
            matrix = ["ref:later-intake", "City", "primary", "7", "Mostly Verified"]
            with open(generator.OUT / "system-matrix.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["mod_id", "system", "role", "evidence_count", "confidence"])
                writer.writerow(matrix)
            candidate = {"mod_id": "ref:later-intake", "pattern_id": "candidate:later",
                         "goal": "Preserve curated evidence", "confidence": "inferred"}
            (generator.OUT / "pattern-candidates.jsonl").write_text(
                json.dumps(candidate) + "\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            catalog = json.loads((generator.OUT / "catalog.json").read_text(encoding="utf-8"))
            self.assertIn(retained, catalog)
            ids = [entry["source_id"] for entry in catalog]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertIn("ref:civilization-trait-expansion", ids)
            with open(generator.OUT / "system-matrix.csv", encoding="utf-8", newline="") as f:
                self.assertIn(matrix, list(csv.reader(f)))
            patterns = [json.loads(line) for line in
                        (generator.OUT / "pattern-candidates.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertIn(candidate, patterns)
            csv_path = generator.OUT / "catalog.csv"
            with open(csv_path, encoding="utf-8", newline="") as f:
                self.assertIn("ref:later-intake", {row["mod_id"] for row in csv.DictReader(f)})

            before = {p.name: p.read_bytes() for p in generator.OUT.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            self.assertEqual(before, {p.name: p.read_bytes() for p in generator.OUT.iterdir()})
