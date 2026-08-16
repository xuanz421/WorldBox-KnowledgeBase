"""Unit tests for WBKB core logic (no real WorldBox needed)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from wbkb import config, discovery, manifest as manifest_mod, registry as registry_mod, util
from wbkb.__main__ import main as cli_main


class HashTests(unittest.TestCase):
    def test_sha256_file_matches_hashlib(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "blob.bin"
            data = os.urandom(65536)
            p.write_bytes(data)
            self.assertEqual(util.sha256_file(p), hashlib.sha256(data).hexdigest())

    def test_file_record_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.dll"
            p.write_bytes(b"abc")
            rec = util.file_record(p)
            self.assertEqual(rec["filename"], "x.dll")
            self.assertEqual(rec["size"], 3)
            self.assertEqual(rec["sha256"], hashlib.sha256(b"abc").hexdigest())
            self.assertIn("path", rec)
            self.assertIn("mtime", rec)


class NormalizeTests(unittest.TestCase):
    def test_real_mod_names(self):
        cases = {
            "ActorHistory_1.8.0": "actorhistory",
            "BuzzOff_1.1.1": "buzzoff",
            "ChineseName_1.5.0new": "chinesename",
            "CreepMobBoost_1.0.2": "creepmobboost",
            "FamilyTree_0.1.5": "familytree",
            "Guigu_Cultivation_1.0.6.2": "guigu-cultivation",
            "IncensefiredWay_0.0.4.1": "incensefiredway",
            "MapDeal_1.0.5": "mapdeal",
            "NerfFireDamage_1.0.0": "nerffiredamage",
            "Optime_0.3.2-pre": "optime",
            "PowerBox_1.5.1new": "powerbox",
            "SHToolkitmod0.1.4-WorldBox0.51.0+": "shtoolkitmod0.1.4-worldbox",
            "Sandbox_1.0.8": "sandbox",
            "TheFantasyWorld_0.8.6": "thefantasyworld",
            "Unlock all": "unlock-all",
            "WorldResilience_0.4.0": "worldresilience",
            "XaviiNationTypes_1.6.1": "xaviinationtypes",
            "寒海的全解锁_1.2": "寒海的全解锁",
            "玄鉴仙族_0.5.1": "玄鉴仙族",
            "玄门道界_beta1.1.3": "玄门道界",
            "简单汉化_1.0.8": "简单汉化",
        }
        for name, expected in cases.items():
            self.assertEqual(util.normalize_ref_name(name), expected, msg=name)

    def test_never_empty(self):
        self.assertTrue(util.normalize_ref_name("123"))
        self.assertTrue(util.normalize_ref_name("1.2.3"))

    def test_ref_source_id_prefix(self):
        self.assertEqual(util.ref_source_id("Foo_1.0"), "ref:foo")


class JsonPersistenceTests(unittest.TestCase):
    def test_save_json_if_changed_skips_identical_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.json"
            data = {"generated_at": "2026-01-01T00:00:00+00:00", "x": 1}
            self.assertTrue(registry_mod.save_json_if_changed(p, data))
            mtime_first = p.stat().st_mtime_ns
            data2 = {"generated_at": "2027-01-01T00:00:00+00:00", "x": 1}
            self.assertFalse(registry_mod.save_json_if_changed(p, data2))  # only volatile key differs
            self.assertEqual(p.stat().st_mtime_ns, mtime_first)
            data3 = {"generated_at": "2027-01-01T00:00:00+00:00", "x": 2}
            self.assertTrue(registry_mod.save_json_if_changed(p, data3))

    def test_registry_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "reg.json"
            reg = {"schema_version": 1, "generated_at": "t", "sources": {"worldbox": {"kind": "game"}}}
            registry_mod.save_json_if_changed(p, reg)
            loaded = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(loaded, reg)


class DiffTests(unittest.TestCase):
    def _reg(self, sources):
        return {"schema_version": 1, "generated_at": "t", "sources": sources}

    def test_statuses(self):
        game = {"kind": "game", "assembly": {"sha256": "a" * 64}}
        mod = {"kind": "reference-mod", "fingerprint": {"file_count": 2, "total_size": 10, "latest_mtime": "m"}}
        old = self._reg({"worldbox": game, "ref:a": mod})
        new_game = {"kind": "game", "assembly": {"sha256": "b" * 64}}
        new = self._reg({"worldbox": new_game, "ref:a": mod, "ref:b": mod})
        changes = registry_mod.diff_registries(old, new)
        self.assertEqual(changes["worldbox"], "CHANGED")
        self.assertEqual(changes["ref:a"], "UNCHANGED")
        self.assertEqual(changes["ref:b"], "NEW")
        gone = self._reg({"worldbox": game})
        changes2 = registry_mod.diff_registries(old, gone)
        self.assertEqual(changes2["ref:a"], "MISSING")

    def test_first_run_all_new(self):
        changes = registry_mod.diff_registries(None, self._reg({"worldbox": {"kind": "game"}}))
        self.assertEqual(changes, {"worldbox": "NEW"})


class FakeTreeTests(unittest.TestCase):
    """End-to-end against a synthetic WorldBox install (no real game needed)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.wb = tmp / "wb"
        (self.wb / "worldbox_Data" / "Managed").mkdir(parents=True)
        (self.wb / "worldbox_Data" / "StreamingAssets" / "mods" / "NML").mkdir(parents=True)
        (self.wb / "Mods" / "ExampleMod_1.2.3" / "code").mkdir(parents=True)
        (self.wb / "Mods" / "Another Mod").mkdir(parents=True)
        (self.wb / "worldbox.exe").write_bytes(b"MZ")
        self.assembly = self.wb / "worldbox_Data" / "Managed" / "Assembly-CSharp.dll"
        self.assembly.write_bytes(b"ASSEMBLY-BYTES")
        self.publicized = self.wb / "worldbox_Data" / "StreamingAssets" / "mods" / "NML" / "Assembly-CSharp-Publicized.dll"
        self.publicized.write_bytes(b"PUBLICIZED-BYTES")
        (self.wb / "worldbox_Data" / "StreamingAssets" / "mods" / "NML" / "commit").write_text("0" * 40)
        (self.wb / "worldbox_Data" / "StreamingAssets" / "mods" / "NeoModLoader.dll").write_bytes(b"NML")
        (self.wb / "Mods" / "ExampleMod_1.2.3" / "mod.json").write_text(
            json.dumps({"name": "Example Mod"}), encoding="utf-8"
        )
        (self.wb / "Mods" / "ExampleMod_1.2.3" / "code" / "Main.cs").write_text("// code", encoding="utf-8")
        (self.wb / "Mods" / "Another Mod" / "mod.json").write_text("{}", encoding="utf-8")

        self.repo_config_dir = self.repo / "config"
        self.repo_config_dir.mkdir(parents=True)
        (self.repo_config_dir / "wbkb.local.json").write_text(
            json.dumps(
                {
                    "worldbox_root": str(self.wb),
                    "assembly_csharp": str(self.assembly),
                    "assembly_csharp_publicized": str(self.publicized),
                    "neomodloader_root": str(self.wb / "worldbox_Data" / "StreamingAssets" / "mods" / "NML"),
                    "reference_mods_roots": [str(self.wb / "Mods")],
                }
            ),
            encoding="utf-8",
        )
        self._old_root = os.environ.get("WBKB_ROOT")
        os.environ["WBKB_ROOT"] = str(self.repo)

    def tearDown(self):
        if self._old_root is None:
            os.environ.pop("WBKB_ROOT", None)
        else:
            os.environ["WBKB_ROOT"] = self._old_root
        self._tmp.cleanup()

    def test_discover_end_to_end(self):
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "local-config")
        self.assertEqual(scan["worldbox"]["root"], str(self.wb))
        self.assertEqual(scan["worldbox"]["assembly"]["sha256"], hashlib.sha256(b"ASSEMBLY-BYTES").hexdigest())
        self.assertEqual(scan["worldbox"]["publicized"]["sha256"], hashlib.sha256(b"PUBLICIZED-BYTES").hexdigest())
        self.assertEqual(scan["neomodloader"]["commit"], "0" * 40)
        self.assertEqual(len(scan["reference_mods"]), 2)
        by_id = {m["id"]: m for m in scan["reference_mods"]}
        self.assertIn("ref:examplemod", by_id)
        self.assertIn("ref:another-mod", by_id)
        self.assertEqual(by_id["ref:examplemod"]["csharp_file_count"], 1)
        self.assertEqual(by_id["ref:examplemod"]["name"], "Example Mod")

        reg = registry_mod.build_local_registry(scan, "now")
        self.assertTrue(registry_mod.save_json_if_changed(registry_mod.local_registry_path(self.repo), reg))
        man = manifest_mod.build_manifest(scan, "now")
        self.assertTrue(registry_mod.save_json_if_changed(manifest_mod.manifest_path(self.repo), man))

        text = manifest_mod.manifest_path(self.repo).read_text(encoding="utf-8")
        # committed manifest must not leak machine paths
        self.assertNotIn(str(self.wb), text)
        self.assertNotIn(str(self.repo), text)
        self.assertIsNone(re.search(r"[A-Za-z]:\\\\", text))
        loaded = json.loads(text)
        self.assertEqual(loaded["worldbox"]["assembly_sha256"], hashlib.sha256(b"ASSEMBLY-BYTES").hexdigest())
        self.assertEqual([m["id"] for m in loaded["reference_mods"]], ["ref:another-mod", "ref:examplemod"])

        # second run: no changes, nothing rewritten, all UNCHANGED
        scan2 = discovery.discover_sources(self.repo)
        reg2 = registry_mod.build_local_registry(scan2, "later")
        self.assertFalse(registry_mod.save_json_if_changed(registry_mod.local_registry_path(self.repo), reg2))
        changes = registry_mod.diff_registries(reg, reg2)
        self.assertEqual(set(changes.values()), {"UNCHANGED"})

    def test_missing_publicized_is_not_fatal(self):
        cfg_path = self.repo_config_dir / "wbkb.local.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["assembly_csharp_publicized"] = ""
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["discover"])
        self.assertEqual(code, 0)
        text = manifest_mod.manifest_path(self.repo).read_text(encoding="utf-8")
        self.assertIsNone(json.loads(text)["worldbox"]["publicized_sha256"])
        doctor_out = io.StringIO()
        with contextlib.redirect_stdout(doctor_out):
            code = cli_main(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("Publicized      MISSING", doctor_out.getvalue())

    def test_cli_doctor_ok(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["discover"])
        self.assertEqual(code, 0)
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            code = cli_main(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("Reference Mods  2 detected", out2.getvalue())
        self.assertIn("Registry        OK", out2.getvalue())


class ConfigTests(unittest.TestCase):
    def test_repo_root_resolves_to_repository(self):
        # without WBKB_ROOT, repo_root() must be the git repository root
        # (tools/wbkb/wbkb/__main__.py -> parents[3]), not an inner directory
        old = os.environ.pop("WBKB_ROOT", None)
        try:
            from wbkb.__main__ import repo_root

            root = repo_root()
            self.assertTrue((root / "README.md").is_file(), msg=str(root))
            self.assertTrue((root / ".gitignore").is_file(), msg=str(root))
            self.assertFalse((root / "tools" / "config").exists())
        finally:
            if old is not None:
                os.environ["WBKB_ROOT"] = old

    def test_example_config_has_required_keys(self):
        cfg = config.example_config()
        for key in config.REQUIRED_KEYS:
            self.assertIn(key, cfg)

    def test_load_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertIsNone(config.load_local_config(repo))
            (repo / "config").mkdir()
            (repo / "config" / "wbkb.local.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(config.load_local_config(repo))
            (repo / "config" / "wbkb.local.json").write_text(json.dumps({"worldbox_root": "x"}), encoding="utf-8")
            self.assertIsNone(config.load_local_config(repo))  # missing required keys


class ProjectAgnosticDiscoveryTests(unittest.TestCase):
    """WBKB discovery must not inspect or depend on consumer mod projects (Z1.1)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        (self.repo / "config").mkdir(parents=True)
        self.wb = tmp / "wb"
        (self.wb / "worldbox_Data" / "Managed").mkdir(parents=True)
        (self.wb / "worldbox.exe").write_bytes(b"MZ")
        (self.wb / "worldbox_Data" / "Managed" / "Assembly-CSharp.dll").write_bytes(b"ASM")
        # a consumer mod project sibling whose csproj points at the fake WorldBox;
        # WBKB must ignore it completely
        sibling = tmp / "SomeConsumerMod"
        sibling.mkdir()
        (sibling / "SomeConsumerMod.csproj").write_text(
            f"<Project><PropertyGroup><WorldBoxDir>{self.wb}</WorldBoxDir></PropertyGroup></Project>",
            encoding="utf-8",
        )
        self._old_env = os.environ.pop(discovery.WORLDBOX_ROOT_ENV, None)
        self._old_vdf = discovery._VDF_PATH
        discovery._VDF_PATH = tmp / "nonexistent.vdf"  # steam lookup disabled by default

    def tearDown(self):
        discovery._VDF_PATH = self._old_vdf
        if self._old_env is not None:
            os.environ[discovery.WORLDBOX_ROOT_ENV] = self._old_env
        self._tmp.cleanup()

    def _write_config(self, worldbox_root):
        (self.repo / "config" / "wbkb.local.json").write_text(
            json.dumps(
                {
                    "worldbox_root": str(worldbox_root),
                    "assembly_csharp": "",
                    "assembly_csharp_publicized": "",
                    "neomodloader_root": "",
                    "reference_mods_roots": [],
                }
            ),
            encoding="utf-8",
        )

    def test_local_config_takes_priority_over_env(self):
        self._write_config(self.wb)
        os.environ[discovery.WORLDBOX_ROOT_ENV] = str(Path(self._tmp.name) / "elsewhere")
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "local-config")
        self.assertEqual(scan["worldbox"]["root"], str(self.wb.resolve()))

    def test_environment_fallback(self):
        os.environ[discovery.WORLDBOX_ROOT_ENV] = str(self.wb)
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "environment")
        self.assertEqual(scan["worldbox"]["root"], str(self.wb.resolve()))
        self.assertEqual(scan["worldbox"]["assembly"]["sha256"], hashlib.sha256(b"ASM").hexdigest())

    def test_explicit_override(self):
        scan = discovery.discover_sources(self.repo, worldbox_root_override=str(self.wb))
        self.assertEqual(scan["config_origin"], "explicit")
        self.assertEqual(scan["worldbox"]["root"], str(self.wb.resolve()))

    def test_steam_discovery(self):
        lib = Path(self._tmp.name) / "lib"
        (lib / "steamapps" / "common" / "worldbox").mkdir(parents=True)
        vdf = Path(self._tmp.name) / "libraryfolders.vdf"
        escaped = str(lib).replace("\\", "\\\\")
        vdf.write_text(f'"libraryfolders"\n{{\n"1"\n{{\n"path"    "{escaped}"\n}}\n}}\n', encoding="utf-8")
        discovery._VDF_PATH = vdf
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "steam")
        expected = (lib / "steamapps" / "common" / "worldbox").resolve()
        self.assertEqual(scan["config"]["worldbox_root"], str(expected))

    def test_no_csproj_scan_of_parent(self):
        # sibling consumer project with <WorldBoxDir> must be ignored entirely
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "none")
        self.assertIsNone(scan["worldbox"]["root"])

    def test_works_without_any_consumer_project(self):
        shutil.rmtree(Path(self._tmp.name) / "SomeConsumerMod")
        os.environ[discovery.WORLDBOX_ROOT_ENV] = str(self.wb)
        scan = discovery.discover_sources(self.repo)
        self.assertEqual(scan["config_origin"], "environment")
        self.assertEqual(scan["worldbox"]["root"], str(self.wb.resolve()))


if __name__ == "__main__":
    unittest.main()
