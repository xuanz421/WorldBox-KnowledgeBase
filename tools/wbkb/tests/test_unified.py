"""Unified multi-source index tests (Z5)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from wbkb import indexer, query

SCHEMA = (Path(__file__).resolve().parents[3] / "schemas" / "schema-v2.sql").read_text(encoding="utf-8")

WORLDBOX_SRC = b"""
namespace Sim {
  public class Actor {
    public ActorData data;
    public bool Alive { get; set; }
    public void killHimself() { }
    public int hit(int amount) { return amount; }
    public int hit(string reason) { return 0; }
  }
  public class ActorData { public float health; }
  public class BasePlugin { public virtual void onLoad() { } }
  // same-name type that also exists in NML
  public class Foo { public int wb_only; }
}
"""

NML_SRC = b"""
using System.Collections.Generic;
namespace NeoModLoader {
  public class ModEntry : Sim.BasePlugin {
    public override void onLoad() {
      Sim.Actor actor = new Sim.Actor();
      actor.killHimself();
      actor.data.health = 1f;
      actor.hit(5);
    }
  }
  public class Loader {
    public Sim.ActorData cache;
    public void tick(Sim.Actor a) { a.killHimself(); }
  }
  // NML's own Foo: bare references inside NML bind to this one
  public class Foo { public string nml_only; }
  public class UsesFoo {
    public void make() { Foo f = new Foo(); f.nml_only = "x"; }
    public void cross() { Sim.Foo wf = new Sim.Foo(); wf.wb_only = 1; }
  }
}
"""

META_WB = {"worldbox_version": "1.0", "assembly_sha256": "a" * 64,
           "extractor_name": "t", "extractor_version": "1", "source_snapshot_id": "wb-snap"}
META_NML = {"commit": "c" * 40, "source_mode": "decompiled", "extractor_version": "1"}


class UnifiedFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        (self.repo / "schemas").mkdir(parents=True)
        (self.repo / "schemas" / "schema-v2.sql").write_text(SCHEMA, encoding="utf-8")
        wb_dir = tmp / "wb" / "source"
        nml_dir = tmp / "nml" / "source"
        wb_dir.mkdir(parents=True)
        nml_dir.mkdir(parents=True)
        (wb_dir / "Sim.cs").write_bytes(WORLDBOX_SRC)
        (nml_dir / "Nml.cs").write_bytes(NML_SRC)
        self.db = indexer.db_path(self.repo)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_unified_index(
            [
                {"source_id": "worldbox", "kind": "game", "version": "1.0",
                 "snapshot_id": "wb-snap", "source_dir": wb_dir, "meta": META_WB},
                {"source_id": "neomodloader", "kind": "mod-loader", "version": "cccccccccccc",
                 "snapshot_id": "nml-snap", "source_dir": nml_dir, "meta": META_NML},
            ],
            self.db, SCHEMA, require_core_types=False,
        )
        self._old_root = os.environ.pop("WBKB_ROOT", None)
        os.environ["WBKB_ROOT"] = str(self.repo)

    def tearDown(self):
        if self._old_root is None:
            os.environ.pop("WBKB_ROOT", None)
        else:
            os.environ["WBKB_ROOT"] = self._old_root
        self._tmp.cleanup()


class CrossSourceResolutionTests(UnifiedFixture):
    def test_sources_registered(self):
        conn = sqlite3.connect(self.db)
        try:
            rows = dict(conn.execute("SELECT source_id, id FROM sources").fetchall())
        finally:
            conn.close()
        self.assertEqual(set(rows), {"worldbox", "neomodloader"})

    def test_cross_source_type_references(self):
        conn = sqlite3.connect(self.db)
        try:
            count = conn.execute(
                """SELECT COUNT(*) FROM type_references tr
                   JOIN types tgt ON tgt.id=tr.target_type_id JOIN sources sto ON sto.id=tgt.source_id
                   JOIN files ff ON ff.id=tr.from_file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(count, 0, "NML parameter/local types must resolve to worldbox")

    def test_cross_source_method_calls(self):
        conn = sqlite3.connect(self.db)
        try:
            rows = conn.execute(
                """SELECT mc.callee_name FROM method_calls mc
                   JOIN methods m ON m.id=mc.callee_method_id
                   JOIN types ct ON ct.id=m.type_id JOIN sources sto ON sto.id=ct.source_id
                   JOIN files ff ON ff.id=mc.file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'"""
            ).fetchall()
        finally:
            conn.close()
        names = {r[0] for r in rows}
        self.assertIn("killHimself", names)
        self.assertIn("hit", names)
        # note: implicit parameterless ctors have no method row and stay unresolved

    def test_cross_source_field_write(self):
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN fields f ON f.id=sr.target_id
                   JOIN types ft ON ft.id=f.type_id JOIN sources sto ON sto.id=ft.source_id
                   JOIN files ff ON ff.id=sr.from_file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND ft.full_name='Sim.ActorData' AND f.name='health' AND sr.reference_kind='write'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(row, 0, "actor.data.health = 1f in NML must be a cross-source write")

    def test_cross_source_inheritance(self):
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                """SELECT i.target_type_id FROM inheritance i
                   JOIN types t ON t.id=i.type_id JOIN sources s ON s.id=t.source_id
                   JOIN types tt ON tt.id=i.target_type_id JOIN sources st ON st.id=tt.source_id
                   WHERE s.source_id='neomodloader' AND t.full_name='NeoModLoader.ModEntry'
                     AND st.source_id='worldbox'"""
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "ModEntry : Sim.BasePlugin must resolve cross-source")

    def test_same_name_current_source_wins(self):
        conn = sqlite3.connect(self.db)
        try:
            # f.nml_only inside NML UsesFoo.make: Foo must be NML's own
            nml_foo = conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN fields f ON f.id=sr.target_id
                   JOIN types ft ON ft.id=f.type_id JOIN sources sto ON sto.id=ft.source_id
                   JOIN files ff ON ff.id=sr.from_file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='neomodloader'
                     AND f.name='nml_only'"""
            ).fetchone()[0]
            wrong = conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN fields f ON f.id=sr.target_id
                   JOIN types ft ON ft.id=f.type_id JOIN sources sto ON sto.id=ft.source_id
                   JOIN files ff ON ff.id=sr.from_file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND f.name='nml_only'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(nml_foo, 0, "bare Foo in NML binds to NML Foo")
        self.assertEqual(wrong, 0, "bare Foo in NML must never bind to worldbox Foo")

    def test_qualified_worldbox_reference_binds(self):
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                """SELECT COUNT(*) FROM symbol_references sr
                   JOIN fields f ON f.id=sr.target_id
                   JOIN types ft ON ft.id=f.type_id JOIN sources sto ON sto.id=ft.source_id
                   JOIN files ff ON ff.id=sr.from_file_id JOIN sources sfrom ON sfrom.id=ff.source_id
                   WHERE sfrom.source_id='neomodloader' AND sto.source_id='worldbox'
                     AND f.name='wb_only'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(row, 0, "explicit Sim.Foo in NML binds to worldbox Foo")


class QuerySourceTests(UnifiedFixture):
    def test_search_source_filter(self):
        all_hits = query.search(self.repo, "Foo")
        sources_found = {t["source_id"] for t in all_hits["types"]}
        self.assertEqual(sources_found, {"worldbox", "neomodloader"})
        nml_hits = query.search(self.repo, "Foo", source="neomodloader")
        self.assertTrue(nml_hits["types"])
        self.assertTrue(all(t["source_id"] == "neomodloader" for t in nml_hits["types"]))

    def test_qualified_symbol_lookup(self):
        result = query.symbol(self.repo, "Foo")
        self.assertTrue(result["ambiguous"])
        self.assertEqual(len(result["candidates"]), 2)
        wb = query.symbol(self.repo, "worldbox::Foo")
        self.assertTrue(wb["found"] and not wb["ambiguous"])
        self.assertEqual(wb["type"]["full_name"], "Sim.Foo")
        nml = query.symbol(self.repo, "neomodloader::Foo")
        self.assertEqual(nml["type"]["full_name"], "NeoModLoader.Foo")

    def test_refs_from_source_filter(self):
        result = query.refs(self.repo, "Actor.killHimself")
        self.assertTrue(result["references"])
        nml_only = query.refs(self.repo, "Actor.killHimself", from_source="neomodloader")
        self.assertTrue(nml_only["references"])
        self.assertTrue(all(r["from_source"] == "neomodloader" for r in nml_only["references"]))

    def test_callers_source_prefix(self):
        result = query.callers(self.repo, "Actor.killHimself")
        self.assertTrue(any(c["caller"].startswith("[neomodloader]") for c in result["callers"]))

    def test_derived_cross_source(self):
        result = query.derived(self.repo, "BasePlugin")
        self.assertIn("[neomodloader] NeoModLoader.ModEntry", result["derived"])
        wb_only = query.derived(self.repo, "BasePlugin", source="worldbox")
        self.assertEqual(wb_only["derived"], [])

    def test_cross_source_stats(self):
        stats = query.source_stats(self.repo)
        self.assertEqual(set(stats["sources"]), {"worldbox", "neomodloader"})
        cross = stats["cross"]
        self.assertGreater(cross["nml_to_worldbox_type_refs"], 0)
        self.assertGreater(cross["nml_to_worldbox_method_calls"], 0)
        self.assertGreater(cross["nml_to_worldbox_symbol_refs"], 0)


class UnifiedOrchestrationTests(UnifiedFixture):
    def test_meta_records_both_snapshots(self):
        meta = indexer.read_meta(self.db)
        self.assertEqual(meta.get("snapshot:worldbox"), "wb-snap")
        self.assertEqual(meta.get("snapshot:neomodloader"), "nml-snap")
        self.assertEqual(meta.get("sources_count"), "2")

    def test_deterministic_rebuild(self):
        db2 = self.db.with_name("wbkb2.db")
        indexer.build_unified_index(
            [
                {"source_id": "worldbox", "kind": "game", "version": "1.0",
                 "snapshot_id": "wb-snap", "source_dir": self._wb_dir(), "meta": META_WB},
                {"source_id": "neomodloader", "kind": "mod-loader", "version": "cccccccccccc",
                 "snapshot_id": "nml-snap", "source_dir": self._nml_dir(), "meta": META_NML},
            ],
            db2, SCHEMA, require_core_types=False,
        )

        def dump(path):
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                meta = dict(conn.execute("SELECT key, value FROM meta WHERE key != 'built_at'").fetchall())
                data = {}
                for table in ("sources", "files", "types", "methods", "fields", "properties",
                              "inheritance", "symbol_references", "method_calls", "type_references"):
                    data[table] = conn.execute(f"SELECT * FROM {table}").fetchall()
            finally:
                conn.close()
            return meta, data

        meta1, data1 = dump(self.db)
        meta2, data2 = dump(db2)
        self.assertEqual(meta1, meta2)
        self.assertEqual(data1, data2)

    def _wb_dir(self):
        return Path(self._tmp.name) / "wb" / "source"

    def _nml_dir(self):
        return Path(self._tmp.name) / "nml" / "source"


if __name__ == "__main__":
    unittest.main()
