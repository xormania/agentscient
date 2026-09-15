"""World: hermetic by default, ambient by name, plants proven, children
reaped, watched paths compared (docs/tests.md §The kit, rules 4 and 6)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

from ops.testkit import PlantFailed, World, compare, run


class Environment(unittest.TestCase):
    def test_env_carries_no_operator_home(self):
        with World() as world:
            env = world.env()
            self.assertEqual(env["HOME"], str(world.home))
            self.assertNotEqual(env["HOME"], os.environ.get("HOME"))
            for name in ("XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR"):
                self.assertTrue(env[name].startswith(str(world.root)), name)
            # A leak: the planted fault is an env() that copies os.environ.
            leaked = {k for k in os.environ if k in env and env[k] == os.environ[k]
                      and k != "PATH" and not k.startswith("GIT_")}
            self.assertEqual(leaked, set(), f"host values reached the world: {sorted(leaked)}")
            self.assertTrue(env["PATH"].startswith(str(world.bin) + os.pathsep))

    def test_home_xdg_tmpdir_cwd_are_under_the_root(self):
        with World() as world:
            for path in (world.home, world.xdg_state, world.xdg_config, world.xdg_cache,
                         world.tmp, world.cwd, world.bin):
                self.assertTrue(path.is_dir(), path)
                self.assertEqual(path.resolve().parents[-1], Path("/"))
                self.assertTrue(str(path).startswith(str(world.root)), path)

    def test_ambient_is_explicit_and_named(self):
        os.environ["WORLD_TEST_AMBIENT"] = "from-the-host"
        try:
            with World() as hermetic:
                self.assertNotIn("WORLD_TEST_AMBIENT", hermetic.env())
            with World(ambient=("WORLD_TEST_AMBIENT",)) as world:
                self.assertEqual(world.env()["WORLD_TEST_AMBIENT"], "from-the-host")
                self.assertEqual(world.ambient, ("WORLD_TEST_AMBIENT",))
            with self.assertRaises(PlantFailed):
                World(ambient=("HOME",))
        finally:
            del os.environ["WORLD_TEST_AMBIENT"]

    def test_enter_restores_os_environ(self):
        before = dict(os.environ)
        world = World()
        world.enter()
        try:
            self.assertEqual(os.environ["HOME"], str(world.home))
            self.assertNotEqual(os.environ.get("HOME"), before.get("HOME"))
        finally:
            world.close()
        self.assertEqual(dict(os.environ), before)


class Plants(unittest.TestCase):
    def test_plant_text_refuses_a_plant_that_did_not_land(self):
        with World() as world:
            planted = world.plant_text("a/b.txt", "hello\n", recognisable="hello")
            self.assertEqual(planted.read_text(encoding="utf-8"), "hello\n")
            with self.assertRaises(PlantFailed):
                world.plant_text("a/c.txt", "hello\n", recognisable="absent marker")

    def test_stage_copies_the_subject_and_stands_in_for_an_absent_one(self):
        with World() as world:
            staged = world.stage(support.REFUSER)
            self.assertEqual(staged.read_bytes(), support.REFUSER.read_bytes())
            self.assertNotEqual(staged.resolve(), support.REFUSER.resolve())
            absent = world.stage(world.root / "nowhere.py", "nowhere.py")
            result = run([sys.executable, str(absent), "anything"], cwd=world.cwd, env=world.env())
            self.assertEqual((result.exit, result.stdout, result.stderr), (0, "", ""))

    def test_require_names_an_absent_tool_as_invalid(self):
        with World() as world:
            self.assertTrue(world.require("python3"))
            with self.assertRaises(PlantFailed):
                world.require("no-such-tool-in-this-world")


class Children(unittest.TestCase):
    def test_owned_child_is_reaped_at_close(self):
        world = World()
        child = world.own(subprocess.Popen(support.SLEEPER, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        self.assertIsNone(child.poll())
        world.close()
        self.assertIsNotNone(child.poll(), "the child outlived the world")
        self.assertFalse(world.root.exists())


class Watching(unittest.TestCase):
    def test_watch_reports_a_changed_declared_path_and_ignores_declared_exclusions(self):
        with World() as world:
            store = world.root / "store"
            store.mkdir()
            (store / "kept").write_text("x", encoding="utf-8")
            watch = world.watch(store, ignore=(r"\.tmp\.[a-z]{3}",), tolerate_new=(r"^job-\d+$",))
            (store / ".tmp.abc").write_text("x", encoding="utf-8")
            (store / "job-7").mkdir()
            watch.assert_unchanged(self)
            (store / "intruder").write_text("x", encoding="utf-8")
            with self.assertRaises(AssertionError):
                watch.assert_unchanged(self)
            (store / "intruder").unlink()
            (store / "kept").unlink()
            with self.assertRaises(AssertionError):
                watch.assert_unchanged(self)

    def test_compare_drops_a_removed_original_entry_only_from_expected_never_from_actual(self):
        # The planted fault: a compare that ignores a removed original entry.
        before = {"s": ("dir", ("kept", "job-1"))}
        after = {"s": ("dir", ("job-1", "job-2"))}
        expected, actual = compare(before, after, tolerate_new=(r"^job-\d+$",))
        self.assertEqual(expected, {"s": ("dir", ("kept", "job-1"))})
        self.assertEqual(actual, {"s": ("dir", ("job-1",))})
        self.assertNotEqual(expected, actual)


class Reaching(unittest.TestCase):
    def test_import_from_another_cwd_fails_naming_ops_testkit(self):
        elsewhere = tempfile.mkdtemp(prefix="elsewhere-")
        proc = subprocess.run(
            [sys.executable, "-c", "import ops.testkit"], cwd=elsewhere,
            capture_output=True, text=True, check=False, timeout=60,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": elsewhere},
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ops", proc.stderr)
        here = subprocess.run(
            [sys.executable, "-c", "import ops.testkit"], cwd=str(support.REPO),
            capture_output=True, text=True, check=False, timeout=60,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": elsewhere},
        )
        self.assertEqual(here.returncode, 0, here.stderr)
