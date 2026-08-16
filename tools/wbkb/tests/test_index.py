"""Structured index tests: parsing, schema, queries, safety (Z3)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from wbkb import csharp, indexer, query

SCHEMA = (Path(__file__).resolve().parents[3] / "schemas" / "schema-v1.sql").read_text(encoding="utf-8")

SAMPLE = b"""
using System;

namespace Game.Sim {
  public abstract class Actor : BaseThing, ITick {
    private const int A = 1, B = 2;
    public static readonly string Tag = "actor_tag";
    public int Health { get; private set; }
    public bool Alive => Health > 0;
    public void Hit(int damage) { string log = "hit me"; }
    public void Hit(string reason) { string log = "hit me"; }
    public Actor() { }
    static Actor() { }
    public class InnerState { public enum Kind { X, Y } }
  }
  public class BaseThing { }
  public interface ITick { }
  public struct Point { public int X; }
  public delegate void Handler(int code);
  public record Vec(double X);
}

class MonoBehaviour { }
"""

META = {
    "worldbox_version": "1.2.3",
    "assembly_sha256": "a" * 64,
    "extractor_name": "ilspycmd",
    "extractor_version": "1.0.0-test",
    "source_snapshot_id": "worldbox-1.2.3-aaaaaaaaaaaa",
}


class IndexTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.source_dir = Path(self._tmp.name) / "snap" / "source"
        self.source_dir.mkdir(parents=True)
        (self.source_dir / "Actor.cs").write_bytes(SAMPLE)
        (self.source_dir / "Extra.cs").write_text(
            "public class Extra { public string Path = \"data/units.xml\"; }\n", encoding="utf-8"
        )
        self.db = Path(self._tmp.name) / "wbkb.db"
        # store schema where indexer expects it inside the fake repo
        schema_dst = self.repo / "schemas"
        schema_dst.mkdir(parents=True)
        (schema_dst / "schema-v1.sql").write_text(SCHEMA, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def build(self, require_core_types: bool = False, meta=META, max_failed_ratio=1.0):
        return indexer.build_index(
            self.source_dir, self.db, meta, SCHEMA,
            require_core_types=require_core_types, max_failed_ratio=max_failed_ratio,
        )

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn


class SchemaAndFileTests(IndexTestBase):
    def test_schema_tables_created(self):
        self.build()
        conn = self.connect()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for table in ("meta", "sources", "files", "types", "methods", "fields", "properties", "strings", "inheritance"):
            self.assertIn(table, tables)

    def test_file_rows(self):
        self.build()
        conn = self.connect()
        rows = {r["relative_path"]: r for r in conn.execute("SELECT * FROM files")}
        conn.close()
        self.assertEqual(set(rows), {"Actor.cs", "Extra.cs"})
        actor = rows["Actor.cs"]
        self.assertEqual(actor["parse_status"], "OK")
        self.assertEqual(actor["sha256"], hashlib.sha256(SAMPLE).hexdigest())
        self.assertGreater(actor["line_count"], 10)


class TypeAndMemberTests(IndexTestBase):
    def test_type_indexing(self):
        self.build()
        conn = self.connect()
        actor = conn.execute("SELECT * FROM types WHERE name='Actor'").fetchone()
        self.assertEqual(actor["namespace"], "Game.Sim")
        self.assertEqual(actor["full_name"], "Game.Sim.Actor")
        self.assertEqual(actor["kind"], "class")
        self.assertEqual(actor["visibility"], "public")
        self.assertEqual(actor["is_abstract"], 1)
        point = conn.execute("SELECT kind FROM types WHERE name='Point'").fetchone()
        self.assertEqual(point["kind"], "struct")
        delegate = conn.execute("SELECT kind FROM types WHERE name='Handler'").fetchone()
        self.assertEqual(delegate["kind"], "delegate")
        record = conn.execute("SELECT kind FROM types WHERE name='Vec'").fetchone()
        self.assertEqual(record["kind"], "record")
        conn.close()

    def test_nested_type_full_name_and_parent(self):
        self.build()
        conn = self.connect()
        inner = conn.execute("SELECT * FROM types WHERE name='InnerState'").fetchone()
        self.assertEqual(inner["full_name"], "Game.Sim.Actor.InnerState")
        parent = conn.execute("SELECT full_name FROM types WHERE id=?", (inner["parent_type_id"],)).fetchone()
        self.assertEqual(parent["full_name"], "Game.Sim.Actor")
        enum = conn.execute("SELECT full_name FROM types WHERE name='Kind'").fetchone()
        self.assertEqual(enum["full_name"], "Game.Sim.Actor.InnerState.Kind")
        conn.close()

    def test_overloaded_methods_distinct(self):
        self.build()
        conn = self.connect()
        actor = conn.execute("SELECT id FROM types WHERE name='Actor'").fetchone()
        hits = conn.execute("SELECT signature FROM methods WHERE type_id=? ORDER BY signature", (actor["id"],)).fetchall()
        signatures = [h["signature"] for h in hits]
        self.assertIn("Hit(int)", signatures)
        self.assertIn("Hit(string)", signatures)
        self.assertIn(".ctor()", signatures)
        self.assertIn(".cctor()", signatures)
        conn.close()

    def test_fields_multi_declarator_and_flags(self):
        self.build()
        conn = self.connect()
        actor = conn.execute("SELECT id FROM types WHERE name='Actor'").fetchone()
        fields = {r["name"]: r for r in conn.execute("SELECT * FROM fields WHERE type_id=?", (actor["id"],))}
        self.assertEqual(fields["A"]["is_const"], 1)
        self.assertEqual(fields["B"]["is_const"], 1)
        self.assertEqual(fields["A"]["field_type"], "int")
        self.assertEqual(fields["Tag"]["is_static"], 1)
        self.assertEqual(fields["Tag"]["is_readonly"], 1)
        conn.close()

    def test_properties(self):
        self.build()
        conn = self.connect()
        props = {r["name"]: r for r in conn.execute(
            "SELECT * FROM properties WHERE type_id=(SELECT id FROM types WHERE name='Actor')")}
        self.assertEqual(props["Health"]["has_getter"], 1)
        self.assertEqual(props["Health"]["has_setter"], 1)
        self.assertEqual(props["Alive"]["has_getter"], 1)
        self.assertEqual(props["Alive"]["has_setter"], 0)
        conn.close()


class InheritanceTests(IndexTestBase):
    def test_inheritance_internal_and_external(self):
        self.build()
        conn = self.connect()
        actor = conn.execute("SELECT id FROM types WHERE name='Actor'").fetchone()
        edges = conn.execute("SELECT * FROM inheritance WHERE type_id=?", (actor["id"],)).fetchall()
        by_target = {e["target_name"]: e for e in edges}
        self.assertEqual(by_target["BaseThing"]["relation"], "base")
        self.assertIsNotNone(by_target["BaseThing"]["target_type_id"])  # internal resolution
        self.assertEqual(by_target["ITick"]["relation"], "interface")
        self.assertIsNotNone(by_target["ITick"]["target_type_id"])
        # external targets in a file compiled without Unity refs stay unresolved
        extra = conn.execute("SELECT * FROM types WHERE name='Extra'").fetchone()
        extra_edges = conn.execute("SELECT * FROM inheritance WHERE type_id=?", (extra["id"],)).fetchall()
        self.assertEqual(extra_edges, [])


class StringTests(IndexTestBase):
    def test_duplicate_string_occurrences_kept(self):
        self.build()
        conn = self.connect()
        rows = conn.execute("SELECT * FROM strings WHERE value='hit me'").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["start_line"] for r in rows}, {10, 11})  # both occurrences recorded

    def test_field_initializer_string(self):
        self.build()
        conn = self.connect()
        tag = conn.execute("SELECT * FROM strings WHERE value='actor_tag'").fetchone()
        self.assertIsNotNone(tag)
        self.assertIsNone(tag["method_id"])
        self.assertIsNotNone(tag["type_id"])
        conn.close()

    def test_escaped_and_verbatim_strings(self):
        result = csharp.parse_source(
            b'class C { void M() { string a = "tab\\there"; string b = @"C:\\path\\n"; string c = $"v={a}"; } }'
        )
        values = [s["value"] for s in result["strings"]]
        self.assertIn("tab\there", values)
        self.assertIn("C:\\path\\n", values)
        self.assertTrue(any(v.startswith("v=") for v in values))  # interpolated raw text kept

    def test_classification(self):
        self.assertEqual(csharp.classify_string("data/units.xml"), "path_like")
        self.assertEqual(csharp.classify_string("Welcome to the world"), "localization_like")
        self.assertEqual(csharp.classify_string("citizen_job"), "possible_identifier")
        self.assertEqual(csharp.classify_string("units.orc"), "possible_asset_id")
        self.assertEqual(csharp.classify_string("!!"), "other")


class RobustnessTests(IndexTestBase):
    def test_failed_file_does_not_kill_index(self):
        (self.source_dir / "Broken.cs").write_text("class {{{ not valid C# at all ]]]", encoding="utf-8")
        self.build(max_failed_ratio=0.5)
        conn = self.connect()
        broken = conn.execute("SELECT * FROM files WHERE relative_path='Broken.cs'").fetchone()
        self.assertIn(broken["parse_status"], ("FAILED", "PARTIAL"))
        self.assertIsNotNone(broken["parse_error"])
        total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        self.assertEqual(total, 3)  # all files still present
        conn.close()

    def test_compiler_generated_flag(self):
        result = csharp.parse_source(b"class Outer { private class <>c { void <m>b__0_0() {} } }")
        gen = [t for t in result["types"] if t["is_compiler_generated"]]
        self.assertTrue(gen)
        # the invalid `<m>` prefix is recovered as an ERROR node; the plain identifier remains
        self.assertIn("b__0_0", [m["name"] for m in result["methods"]])


class OrchestrationTests(IndexTestBase):
    def _registry(self, version="1.2.3", sha=None):
        return {
            "sources": {
                "worldbox": {
                    "kind": "game",
                    "game_version": version,
                    "assembly": {
                        "path": str(self.source_dir / ".." / ".." / "Assembly-CSharp.dll"),
                        "sha256": sha or META["assembly_sha256"],
                        "size": 1,
                    },
                }
            }
        }

    def test_validation_failure_keeps_good_db(self):
        self.build()
        good_mtime = self.db.stat().st_mtime_ns
        # rebuild requiring core types that the fixture lacks -> must fail and keep old db
        with self.assertRaises(indexer.IndexError_):
            indexer.build_index(self.source_dir, self.db, META, SCHEMA, require_core_types=True)
        self.assertTrue(self.db.is_file())
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0], 2)  # old content intact
        conn.close()
        self.assertEqual(self.db.stat().st_mtime_ns, good_mtime)  # untouched, no half-rebuild

    def test_tmp_build_leaves_final_alone_on_failure(self):
        self.build()
        final = self.db
        tmp = final.with_name("wbkb.tmp.db")
        meta_bad = dict(META, source_snapshot_id="other")
        with self.assertRaises(indexer.IndexError_):
            indexer.build_index(self.source_dir, tmp, meta_bad, SCHEMA, require_core_types=True)
        self.assertFalse(tmp.exists())  # cleaned up
        self.assertTrue(final.is_file())  # untouched

    def test_index_state_transitions(self):
        repo = self.repo
        self.assertEqual(indexer.index_state(repo, self._registry())["state"], "MISSING")
        # fake a built database at the standard location
        std_db = indexer.db_path(repo)
        std_db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, std_db, META, SCHEMA)
        state = indexer.index_state(repo, self._registry())
        self.assertEqual(state["state"], "OK")
        # changed assembly => STALE
        stale_registry = self._registry(sha="b" * 64)
        self.assertEqual(indexer.index_state(repo, stale_registry)["state"], "STALE")
        # broken db
        std_db.write_bytes(b"not a database")
        self.assertEqual(indexer.index_state(repo, self._registry())["state"], "BROKEN")

    def test_search_limit(self):
        # build db at repo standard location for query layer
        std_db = indexer.db_path(self.repo)
        std_db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, std_db, META, SCHEMA)
        result = query.search(self.repo, "e", limit=2)
        for category in ("types", "methods", "fields", "properties", "strings", "files"):
            self.assertLessEqual(len(result[category]), 2, msg=category)
        # exact search
        exact = query.search(self.repo, "Actor", exact=True)
        self.assertTrue(any(t["full_name"] == "Game.Sim.Actor" for t in exact["types"]))

    def test_symbol_lookup(self):
        std_db = indexer.db_path(self.repo)
        std_db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, std_db, META, SCHEMA)
        result = query.symbol(self.repo, "Actor")
        self.assertTrue(result["found"])
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["type"]["full_name"], "Game.Sim.Actor")
        bases = {b["relation"]: b["target_name"] for b in result["bases"]}
        self.assertEqual(bases["base"], "BaseThing")
        base_result = query.symbol(self.repo, "BaseThing")
        self.assertEqual(base_result["derived"], ["Game.Sim.Actor"])
        not_found = query.symbol(self.repo, "NoSuchType")
        self.assertFalse(not_found["found"])

    def test_show_and_path_traversal(self):
        std_db = indexer.db_path(self.repo)
        std_db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, std_db, META, SCHEMA)
        # db meta carries the snapshot id; point snapshot dir at fixture source
        snap_dir = self.repo / indexer.extractor.SNAPSHOTS_DIR / META["source_snapshot_id"] / "source"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for cs in self.source_dir.iterdir():
            (snap_dir / cs.name).write_bytes(cs.read_bytes())

        result = query.show(self.repo, "Actor.cs:12", context=2)
        self.assertEqual(result["line"], 12)
        self.assertEqual(len(result["lines"]), 5)
        with self.assertRaises(query.QueryError):
            query.show(self.repo, "../schemas/schema-v1.sql")
        with self.assertRaises(query.QueryError):
            query.show(self.repo, "..\\..\\secret.txt:1")
        with self.assertRaises(query.QueryError):
            query.show(self.repo, "C:\\Windows\\win.ini:1")

    def test_string_command_query(self):
        std_db = indexer.db_path(self.repo)
        std_db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, std_db, META, SCHEMA)
        rows = query.string_search(self.repo, "hit me", exact=True)
        self.assertEqual(len(rows), 2)
        rows = query.string_search(self.repo, "actor", exact=False)
        self.assertTrue(any(r["value"] == "actor_tag" for r in rows))


if __name__ == "__main__":
    unittest.main()
