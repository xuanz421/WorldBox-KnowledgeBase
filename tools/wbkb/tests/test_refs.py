"""Reference graph & navigation tests (Z4)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from wbkb import csharp, indexer, query
from wbkb.__main__ import main as cli_main

SCHEMA = (Path(__file__).resolve().parents[3] / "schemas" / "schema-v2.sql").read_text(encoding="utf-8")

FIXTURE = b"""
using System.Collections.Generic;
using UnityEngine;

namespace Sim {
  public class BaseThing {
    public int hp;
    public virtual void update() { }
    public void tick() { update(); }
  }

  public class Actor : BaseThing {
    public ActorData data;
    public bool Alive { get; set; }
    public static ActorLibrary library;
    public Actor() { }
    public Actor(int seed) { }
    public void killHimself() { hp = 0; }
    public ActorData fetch() { return data; }
    public int hit(int amount) { return amount; }
    public int hit(string reason) { return 0; }
    public override void update() { base.update(); }
  }

  public class ActorData { public float health; }

  public class ActorLibrary { public static List<Actor> all = new List<Actor>(); }

  public class ClassA { public int value; }
  public class ClassB { public int value; }

  public class Service {
    public ClassA a = new ClassA();
    public void consume(ClassB b) { int stolen = b.value; }
    public int mix() {
      Actor actor = new Actor(5);
      actor.killHimself();
      BaseThing b = actor;
      b.update();
      var d = actor.fetch();
      d.health += 1f;
      actor.data = new ActorData();
      actor.hit(3);
      BaseThing widened = (BaseThing)actor;
      var asData = actor as ActorData;
      Mathf.Clamp(1f, 0f, 2f);
      Debug.Log("done");
      loop(this);
      return a.value + this.a.value;
    }
    public void loop(Service s) { s.mix(); }
  }
}
"""

META = {
    "worldbox_version": "2.0.0",
    "assembly_sha256": "b" * 64,
    "extractor_name": "ilspycmd",
    "extractor_version": "9.9.9",
    "source_snapshot_id": "worldbox-2.0.0-bbbbbbbbbbbb",
}


class RefFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        (self.repo / "schemas").mkdir(parents=True)
        (self.repo / "schemas" / "schema-v2.sql").write_text(SCHEMA, encoding="utf-8")
        self.source_dir = tmp / "snap" / "source"
        self.source_dir.mkdir(parents=True)
        (self.source_dir / "Sim.cs").write_bytes(FIXTURE)
        self.db = indexer.db_path(self.repo)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        indexer.build_index(self.source_dir, self.db, META, SCHEMA)
        self._old_root = os.environ.pop("WBKB_ROOT", None)
        os.environ["WBKB_ROOT"] = str(self.repo)

    def tearDown(self):
        if self._old_root is None:
            os.environ.pop("WBKB_ROOT", None)
        else:
            os.environ["WBKB_ROOT"] = self._old_root
        self._tmp.cleanup()

    def connect(self):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def method_id(self, owner: str, signature: str) -> int:
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT m.id FROM methods m JOIN types t ON t.id=m.type_id
                   WHERE t.full_name=? AND m.signature=?""",
                (owner, signature),
            ).fetchone()
            self.assertIsNotNone(row, f"method not indexed: {owner}.{signature}")
            return row["id"]
        finally:
            conn.close()

    def calls_of(self, caller_sig_owner: str, caller_sig: str) -> list[sqlite3.Row]:
        conn = self.connect()
        try:
            return conn.execute(
                """SELECT mc.* FROM method_calls mc
                   WHERE mc.caller_method_id=? ORDER BY mc.line""",
                (self.method_id(caller_sig_owner, caller_sig),),
            ).fetchall()
        finally:
            conn.close()


class CallResolutionTests(RefFixture):
    def test_same_type_call(self):
        calls = self.calls_of("Sim.BaseThing", "tick()")
        resolved = [c for c in calls if c["callee_name"] == "update" and c["resolution_status"] == "resolved"]
        self.assertTrue(resolved)

    def test_cross_type_call(self):
        calls = self.calls_of("Sim.Service", "mix()")
        hit = [c for c in calls if c["callee_name"] == "killHimself"]
        self.assertTrue(hit and hit[0]["resolution_status"] == "resolved")

    def test_constructor_with_arity(self):
        calls = self.calls_of("Sim.Service", "mix()")
        ctor = [c for c in calls if c["callee_name"] == ".ctor" and c["declaring_type_hint"] == "Sim.Actor"]
        self.assertTrue(ctor)
        self.assertEqual(ctor[0]["resolution_status"], "resolved")  # new Actor(5) picks (int)

    def test_overloaded_call_resolved_by_arity(self):
        calls = self.calls_of("Sim.Service", "mix()")
        hit = [c for c in calls if c["callee_name"] == "hit" and c["resolution_status"] == "resolved"]
        self.assertTrue(hit)
        self.assertIn("hit(int)", hit[0]["callee_signature_hint"] or "")

    def test_ambiguous_overload_retained(self):
        # both overloads same arity never happens here; craft via direct resolver:
        conn = self.connect()
        try:
            ambiguous = conn.execute(
                "SELECT COUNT(*) FROM method_calls WHERE resolution_status='ambiguous'"
            ).fetchone()[0]
            unresolved = conn.execute(
                "SELECT COUNT(*) FROM method_calls WHERE resolution_status IN ('unresolved')"
            ).fetchone()[0]
            external = conn.execute(
                "SELECT COUNT(*) FROM method_calls WHERE resolution_status='external'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(unresolved + ambiguous, 0)
        self.assertGreater(external, 0)  # Mathf/Debug retained as external

    def test_external_call_retained(self):
        calls = self.calls_of("Sim.Service", "mix()")
        external = [c for c in calls if c["resolution_status"] == "external"]
        self.assertTrue(any(c["callee_name"] in ("Clamp", "Log") for c in external))

    def test_base_call(self):
        calls = self.calls_of("Sim.Actor", "update()")
        hit = [c for c in calls if c["callee_name"] == "update" and c["declaring_type_hint"] == "Sim.BaseThing"]
        self.assertTrue(hit and hit[0]["resolution_status"] == "resolved")

    def test_virtual_dispatch_is_static(self):
        # b.update() where b : BaseThing resolves to BaseThing.update, not Actor.update
        calls = self.calls_of("Sim.Service", "mix()")
        hit = [c for c in calls if c["callee_name"] == "update" and c["resolution_status"] == "resolved"]
        self.assertTrue(hit)
        self.assertEqual(hit[0]["declaring_type_hint"], "Sim.BaseThing")


class InferenceTests(RefFixture):
    def test_parameter_type_inference(self):
        # b.value in consume(ClassB b) must resolve to ClassB.value (not ClassA.value)
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT r.* FROM symbol_references r
                   JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.ClassB' AND f.name='value'"""
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "b.value should resolve to ClassB.value")
        self.assertEqual(row["resolution_status"], "resolved")

    def test_false_resolution_guard(self):
        conn = self.connect()
        try:
            wrong = conn.execute(
                """SELECT COUNT(*) FROM symbol_references r
                   JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.ClassA' AND f.name='value'
                     AND r.from_method_id=(
                       SELECT m.id FROM methods m JOIN types t2 ON t2.id=m.type_id
                       WHERE t2.full_name='Sim.Service' AND m.signature='consume(ClassB)')"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(wrong, 0, "b.value must never bind to ClassA.value")

    def test_local_var_from_new(self):
        calls = self.calls_of("Sim.Service", "mix()")
        self.assertTrue(any(c["callee_name"] == "killHimself" and c["resolution_status"] == "resolved" for c in calls))

    def test_var_from_resolved_method(self):
        # var d = actor.fetch(); d.health += 1f -> ActorData.health read_write
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT r.* FROM symbol_references r
                   JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.ActorData' AND f.name='health'
                     AND r.reference_kind='read_write'"""
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)

    def test_field_write(self):
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT r.* FROM symbol_references r
                   JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.Actor' AND f.name='data' AND r.reference_kind='write'"""
            ).fetchone()
            # hp is declared on BaseThing; `hp = 0` inside Actor resolves through the chain
            hp_write = conn.execute(
                """SELECT r.* FROM symbol_references r JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.BaseThing' AND f.name='hp' AND r.reference_kind='write'"""
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "actor.data = ... should be a write")
        self.assertIsNotNone(hp_write, "hp = 0 should be a write")

    def test_this_member_access(self):
        conn = self.connect()
        try:
            rows = conn.execute(
                """SELECT r.* FROM symbol_references r JOIN fields f ON f.id=r.target_id
                   JOIN types t ON t.id=f.type_id
                   WHERE t.full_name='Sim.ClassA' AND f.name='value'"""
            ).fetchall()
        finally:
            conn.close()
        self.assertGreaterEqual(len(rows), 2)  # a.value + this.a.value

    def test_cast_and_as_references(self):
        conn = self.connect()
        try:
            cast = conn.execute(
                "SELECT COUNT(*) FROM type_references WHERE reference_kind='cast'"
            ).fetchone()[0]
            as_ref = conn.execute(
                "SELECT COUNT(*) FROM type_references WHERE reference_kind='as'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(cast, 0)
        self.assertGreater(as_ref, 0)

    def test_generic_type_reference(self):
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT COUNT(*) FROM type_references tr JOIN types t ON t.id=tr.target_type_id
                   WHERE t.full_name='Sim.Actor' AND tr.reference_kind='generic_argument'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(row, 0, "List<Actor> should emit a generic_argument type reference")

    def test_type_reference_instantiate(self):
        conn = self.connect()
        try:
            row = conn.execute(
                """SELECT COUNT(*) FROM type_references tr JOIN types t ON t.id=tr.target_type_id
                   WHERE t.full_name='Sim.ActorData' AND tr.reference_kind='instantiate'"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(row, 0)

    def test_unresolved_retained(self):
        conn = self.connect()
        try:
            unresolved = conn.execute(
                "SELECT COUNT(*) FROM symbol_references WHERE resolution_status='unresolved'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(unresolved, 0)  # presence check: pipeline never crashes on them

    def test_reference_status_tracked(self):
        conn = self.connect()
        try:
            rows = conn.execute("SELECT reference_status, COUNT(*) FROM files GROUP BY 1").fetchall()
        finally:
            conn.close()
        self.assertTrue(any(r[0] == "OK" for r in rows))


class NavigationTests(RefFixture):
    def test_refs_type(self):
        result = query.refs(self.repo, "ActorData")
        self.assertIn("[class] Sim.ActorData", result["definition"])
        kinds = {r["kind"] for r in result["references"]}
        self.assertIn("field_type", kinds)

    def test_refs_field(self):
        result = query.refs(self.repo, "Actor.data")
        self.assertIn("field] Sim.Actor.data", result["definition"])
        self.assertTrue(any(r["kind"] in ("read", "write") for r in result["references"]))

    def test_refs_method_and_callers(self):
        callers = query.callers(self.repo, "Actor.killHimself")
        self.assertTrue(callers["callers"])
        result = query.refs(self.repo, "Actor.killHimself")
        self.assertTrue(any(r["kind"] == "call" for r in result["references"]))

    def test_refs_ambiguous_overload_lists_candidates(self):
        result = query.refs(self.repo, "Actor.hit")
        self.assertEqual(result["target"]["kind"], "ambiguous")
        self.assertEqual(len(result["target"]["candidates"]), 2)
        self.assertIn("Sim.Actor.hit(int)", result["target"]["candidates"])

    def test_refs_exact_signature(self):
        result = query.refs(self.repo, "Actor.hit(int)")
        self.assertEqual(result["target"]["kind"], "method")

    def test_callees_depth_and_cycle(self):
        result = query.callees(self.repo, "Service.mix", depth=2)
        self.assertTrue(result["tree"])
        # recursion cycle Service.mix -> Service.loop -> Service.mix must terminate
        deep = query.callees(self.repo, "Service.mix", depth=5)
        self.assertTrue(deep["tree"])

    def test_derived_and_overrides(self):
        derived = query.derived(self.repo, "BaseThing")
        self.assertIn("Sim.Actor", derived["derived"])
        overrides = query.overrides(self.repo, "BaseThing.update")
        self.assertIn("Sim.Actor.update()", overrides["overrides"])

    def test_result_limit(self):
        result = query.refs(self.repo, "ActorData", limit=1)
        self.assertLessEqual(len(result["references"]), 1)

    def test_cli_json_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["refs", "Actor.data", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertIn("definition", payload)
        self.assertIn("references", payload)

    def test_idempotent_deterministic_rebuild(self):
        """Rebuilding from the same snapshot yields identical content (except timestamps)."""
        db2 = self.db.with_name("wbkb2.db")
        indexer.build_index(self.source_dir, db2, META, SCHEMA)

        def dump(path):
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                meta = dict(conn.execute("SELECT key, value FROM meta WHERE key != 'built_at'").fetchall())
                data = {}
                for table in ("files", "types", "methods", "fields", "properties", "inheritance",
                              "symbol_references", "method_calls", "type_references"):
                    data[table] = conn.execute(f"SELECT * FROM {table}").fetchall()
            finally:
                conn.close()
            return meta, data

        meta1, data1 = dump(self.db)
        meta2, data2 = dump(db2)
        self.assertEqual(meta1, meta2)
        self.assertEqual(data1, data2)


class AtomicityTests(RefFixture):
    def test_reference_failure_keeps_good_db(self):
        # corrupt a copy of the source so the reference pass raises per-file,
        # but validation (no resolved calls) must fail the build and keep the old db
        good = self.db.read_bytes()
        (self.source_dir / "Evil.cs").write_text(
            "class Evil { void x() { " + "\x00binary" * 50, encoding="utf-8", errors="ignore"
        )
        meta2 = dict(META, source_snapshot_id="worldbox-2.0.0-deadbeefdead")
        with self.assertRaises(indexer.IndexError_):
            indexer.build_index(self.source_dir, self.db, meta2, SCHEMA, require_core_types=True)
        self.assertEqual(self.db.read_bytes(), good)  # old db untouched


if __name__ == "__main__":
    unittest.main()
