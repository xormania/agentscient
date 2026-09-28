"""The closure gate: every tracked contract names a consumer and a fixture.

Contract, plan §3.1 at tree d0565423: `#ClosureIndex` is
`close({contracts: [...#Row, ...]})` and `#Row` is
`close({path: #NonEmpty, consumer: #NonEmpty | #DeclaredAbsent,
fixture: #NonEmpty | #DeclaredAbsent})`. `closure.py check` walks
`git ls-files '*.cue' 'ops/conductor/*-lever.md'`, diffs against
`ops/devlane/harness/closure.json`, vets the index as `#ClosureIndex`,
and for every closed row subprocess-checks that the fixture path
exists. Cue missing: class `cue-missing`, exit 2. Cue version other
than `#CueVersion`: `cue-version`. CLI stdlib only.

Red at this ref because the three files are absent. A host without
cue makes this file red, never skipped. Missing-tool runs use a
stand-in that exits 99 so each case fails on its contracted
assertion, not on Python's missing-file exit 2.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
SCRIPT = HARNESS / "closure.py"
LAW = HARNESS / "closure.cue"
INDEX = HARNESS / "closure.json"
INDEX_REL = "ops/devlane/harness/closure.json"
CONSUMER_REL = "ops/devlane/harness/consumer.py"
FIXTURE_REL = "ops/devlane/harness/fixture.json"
LS_FILES = ("*.cue", "ops/conductor/*-lever.md")
CLOSURE_CUE_REL = "ops/devlane/harness/closure.cue"
RUN_CAP = 30

# Plan §1 rows with no consumer, pinned so closing one is a
# reviewable diff. Measured at d0565423: 19 cue files, 6 levers.
UNCLOSED_NO_CONSUMER = frozenset(
    {
        "ops/capabilities/contracts/capabilities.cue",
        "ops/capabilities/contracts/capability.cue",
        "ops/capabilities/contracts/outcome.cue",
        "ops/capabilities/contracts/plan.cue",
        "ops/devlane/workflow/contracts/cue/canonical.cue",
        "ops/devlane/workflow/contracts/cue/cli.cue",
        "ops/devlane/workflow/contracts/cue/db.cue",
        "ops/devlane/workflow/contracts/cue/events.cue",
        "ops/devlane/workflow/contracts/cue/exitcodes.cue",
        "ops/devlane/workflow/contracts/cue/gatekinds.cue",
        "ops/devlane/workflow/contracts/cue/layout.cue",
        "ops/devlane/workflow/contracts/cue/mcp.cue",
        "ops/devlane/workflow/contracts/cue/meta.cue",
        "ops/devlane/workflow/contracts/cue/schema.cue",
        "ops/devlane/workflow/contracts/cue/vocab.cue",
        "ops/conductor/probes-lever.md",
    }
)

ABSENT_STUB = (
    b'"""Absent closure.py stand-in. Exit 99, no refusal line."""\n'
    b"import sys\n"
    b"sys.stdout.write('ABSENT-STUB\\n')\n"
    b"raise SystemExit(99)\n"
)

REFUSAL_LINE = re.compile(
    r"^[a-z][a-z0-9_-]*: expected .+; found .+; needed .+$"
)

FAKE_CUE = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "sys.stdout.write('cue version v0.14.1\\n')\n"
    "raise SystemExit(0)\n"
)


def _is_declared_absent(value: object) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("declared_absent"), str)
        and value["declared_absent"] != ""
    )


class ClosureGate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="closure-gate-")
        self.scratch = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        for key in list(env):
            if key.startswith("GIT_"):
                del env[key]
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("WF_AGENT", None)
        if extra:
            env.update(extra)
        return env

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _plant_executable(self, path: Path, body: str) -> None:
        self._plant_bytes(path, body.encode("utf-8"))
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertEqual(path.read_text(encoding="utf-8"), body)
        self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")

    def _git(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo,
            env=self._env(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, f"git {args} failed: {proc.stderr}")
        return proc

    def _tracked(self, repo: Path) -> set[str]:
        proc = subprocess.run(
            ["git", "ls-files", *LS_FILES],
            cwd=repo,
            env=self._env(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        return {line for line in proc.stdout.splitlines() if line}

    def _load_index_file(self, path: Path) -> dict:
        if not path.is_file():
            return {"contracts": []}
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("contracts", data)
        self.assertIsInstance(data["contracts"], list)
        return data

    def _write_index(self, repo: Path, rows: list[dict]) -> None:
        payload = json.dumps({"contracts": rows}, indent=2) + "\n"
        self._plant_bytes(repo / INDEX_REL, payload.encode("utf-8"))

    def _closed(self, path: str) -> dict:
        return {
            "path": path,
            "consumer": CONSUMER_REL,
            "fixture": FIXTURE_REL,
        }

    def _absent(self, path: str, reason: str) -> dict:
        return {
            "path": path,
            "consumer": {"declared_absent": reason},
            "fixture": {"declared_absent": reason},
        }

    def _copy_or_stub(self, dest: Path, src: Path, stub: bytes) -> None:
        if src.is_file():
            data = src.read_bytes()
            self.assertNotEqual(data, stub)
        else:
            data = stub
        self._plant_bytes(dest, data)

    def _mini_closed(self) -> Path:
        root = self.scratch / "mini"
        self.assertFalse(root.exists())
        harness = root / "ops" / "devlane" / "harness"
        harness.mkdir(parents=True)
        (root / "ops" / "conductor").mkdir(parents=True)
        self._copy_or_stub(harness / "closure.py", SCRIPT, ABSENT_STUB)
        self._copy_or_stub(harness / "closure.cue", LAW, b"package harness\n")
        self._plant_bytes(
            harness / "context.cue",
            (HARNESS / "context.cue").read_bytes(),
        )
        self._plant_bytes(
            harness / "evidence.cue",
            (HARNESS / "evidence.cue").read_bytes(),
        )
        self._plant_bytes(root / CONSUMER_REL, b"# closure-gate consumer\n")
        self._plant_bytes(root / FIXTURE_REL, b'{"fired":"closure-gate"}\n')
        self._plant_bytes(harness / "planted.cue", b"package harness\n")
        self._git(root, "init")
        self._git(root, "config", "user.name", "closure-gate-test")
        self._git(root, "config", "user.email", "closure-gate-test@example.test")
        self._git(root, "config", "commit.gpgsign", "false")
        self._write_index(root, [])
        self._git(root, "add", "-A")
        tracked = self._tracked(root)
        self.assertGreaterEqual(len(tracked), 1)
        self._write_index(root, [self._closed(path) for path in sorted(tracked)])
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "mini closed index")
        indexed = {row["path"] for row in self._load_index_file(root / INDEX_REL)["contracts"]}
        self.assertEqual(tracked, indexed)
        self.assertTrue((root / CONSUMER_REL).is_file())
        self.assertTrue((root / FIXTURE_REL).is_file())
        return root

    def _check(
        self,
        repo: Path,
        env: dict[str, str] | None = None,
        tool: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script = tool if tool is not None else repo / "ops" / "devlane" / "harness" / "closure.py"
        return subprocess.run(
            [sys.executable, str(script), "check"],
            cwd=repo,
            env=env or self._env(),
            text=True,
            capture_output=True,
            check=False,
            timeout=RUN_CAP,
        )

    def _live_tool(self) -> Path:
        if SCRIPT.is_file():
            return SCRIPT
        stub = self.scratch / "absent-closure.py"
        self._plant_bytes(stub, ABSENT_STUB)
        return stub

    def _check_live(
        self, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self._check(REPO, env=env, tool=self._live_tool())

    def _assert_refusal(
        self,
        proc: subprocess.CompletedProcess[str],
        class_name: str,
        *,
        named: str | None = None,
    ) -> str:
        lines = [line for line in proc.stderr.splitlines() if line.strip()]
        self.assertTrue(
            any(line.startswith(f"{class_name}:") for line in lines),
            f"expected class {class_name!r} on stderr; "
            f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertEqual(2, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertEqual(1, len(lines), proc.stderr)
        line = lines[0]
        self.assertRegex(line, REFUSAL_LINE)
        self.assertRegex(
            line,
            rf"^{re.escape(class_name)}: expected .+; found .+; needed .+$",
        )
        if named is not None:
            self.assertIn(named, line)
        return line

    def _path_without_cue(self) -> str:
        parts = []
        for item in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep):
            if item and not (Path(item) / "cue").exists():
                parts.append(item)
        path = os.pathsep.join(parts) or "/usr/bin:/bin"
        self.assertIsNone(shutil.which("cue", path=path), "cue still on PATH")
        self.assertIsNotNone(shutil.which("git", path=path), "git must remain on PATH")
        return path

    def test_gate_files_exist(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        self.assertTrue(LAW.is_file(), f"missing {LAW}")
        self.assertTrue(INDEX.is_file(), f"missing {INDEX}")

    def test_live_index_is_complete_versus_git_ls_files(self) -> None:
        tracked = self._tracked(REPO)
        self.assertGreaterEqual(len(tracked), len(UNCLOSED_NO_CONSUMER))
        indexed = {
            row["path"]
            for row in self._load_index_file(INDEX)["contracts"]
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        }
        self.assertEqual(tracked, indexed)

    def test_live_unclosed_set_equals_measured_rows_with_no_consumer(self) -> None:
        tracked = self._tracked(REPO)
        self.assertTrue(tracked >= UNCLOSED_NO_CONSUMER, tracked)
        absent = {
            row["path"]
            for row in self._load_index_file(INDEX)["contracts"]
            if isinstance(row, dict)
            and isinstance(row.get("path"), str)
            and _is_declared_absent(row.get("consumer"))
        }
        self.assertEqual(UNCLOSED_NO_CONSUMER, absent)

    def test_live_check_reports_each_unclosed_path_as_a_finding(self) -> None:
        proc = self._check_live()
        output = proc.stdout + proc.stderr
        for path in sorted(UNCLOSED_NO_CONSUMER):
            self.assertIn(path, output)
        self.assertEqual(1, proc.returncode, output)

    def test_closure_cue_row_is_fully_closed(self) -> None:
        tracked = self._tracked(REPO)
        self.assertIn(CLOSURE_CUE_REL, tracked)
        rows = {
            row["path"]: row
            for row in self._load_index_file(INDEX)["contracts"]
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        }
        self.assertIn(CLOSURE_CUE_REL, rows)
        row = rows[CLOSURE_CUE_REL]
        self.assertIsInstance(row.get("consumer"), str, row)
        self.assertIsInstance(row.get("fixture"), str, row)
        self.assertNotEqual(row["consumer"], "")
        self.assertNotEqual(row["fixture"], "")
        self.assertTrue(
            (REPO / row["consumer"]).is_file(),
            f"consumer path does not exist: {row['consumer']}",
        )
        self.assertTrue(
            (REPO / row["fixture"]).is_file(),
            f"fixture path does not exist: {row['fixture']}",
        )

    def test_planted_extra_cue_refuses_closure_naming_that_path(self) -> None:
        root = self._mini_closed()
        rel = "ops/devlane/harness/unindexed.cue"
        extra = root / rel
        payload = b"package harness\n// unindexed-extra-cue\n"
        self._plant_bytes(extra, payload)
        self.assertIn(b"unindexed-extra-cue", extra.read_bytes())
        self._git(root, "add", rel)
        self._git(root, "commit", "-m", "plant extra cue")
        tracked = self._tracked(root)
        self.assertIn(rel, tracked)
        indexed = {
            row["path"] for row in self._load_index_file(root / INDEX_REL)["contracts"]
        }
        self.assertNotIn(rel, indexed)
        proc = self._check(root)
        self._assert_refusal(proc, "closure", named=rel)

    def test_planted_extra_lever_refuses_closure_naming_that_path(self) -> None:
        root = self._mini_closed()
        rel = "ops/conductor/extra-lever.md"
        extra = root / rel
        payload = b"# extra lever, unindexed\n"
        self._plant_bytes(extra, payload)
        self.assertEqual(extra.read_bytes(), payload)
        self._git(root, "add", rel)
        self._git(root, "commit", "-m", "plant extra lever")
        self.assertIn(rel, self._tracked(root))
        indexed = {
            row["path"] for row in self._load_index_file(root / INDEX_REL)["contracts"]
        }
        self.assertNotIn(rel, indexed)
        proc = self._check(root)
        self._assert_refusal(proc, "closure", named=rel)

    def test_missing_consumer_path_refuses_naming_consumer(self) -> None:
        root = self._mini_closed()
        data = self._load_index_file(root / INDEX_REL)
        before = json.dumps(data, sort_keys=True)
        missing = "ops/devlane/harness/no-such-consumer.py"
        data["contracts"][0]["consumer"] = missing
        self.assertFalse((root / missing).exists())
        self._write_index(root, data["contracts"])
        after = json.dumps(self._load_index_file(root / INDEX_REL), sort_keys=True)
        self.assertNotEqual(before, after)
        self.assertIn(missing, after)
        self.assertTrue((root / FIXTURE_REL).is_file())
        self._git(root, "add", INDEX_REL)
        self._git(root, "commit", "-m", "plant missing consumer")
        proc = self._check(root)
        line = self._assert_refusal(proc, "closure", named="consumer")
        self.assertIn(missing, line)

    def test_missing_fixture_path_refuses_naming_fixture(self) -> None:
        root = self._mini_closed()
        data = self._load_index_file(root / INDEX_REL)
        before = json.dumps(data, sort_keys=True)
        missing = "ops/devlane/harness/no-such-fixture.json"
        data["contracts"][0]["fixture"] = missing
        self.assertFalse((root / missing).exists())
        self._write_index(root, data["contracts"])
        after = json.dumps(self._load_index_file(root / INDEX_REL), sort_keys=True)
        self.assertNotEqual(before, after)
        self.assertIn(missing, after)
        self.assertTrue((root / CONSUMER_REL).is_file())
        self._git(root, "add", INDEX_REL)
        self._git(root, "commit", "-m", "plant missing fixture")
        proc = self._check(root)
        line = self._assert_refusal(proc, "closure", named="fixture")
        self.assertIn(missing, line)

    def test_path_without_cue_exits_2_class_cue_missing(self) -> None:
        root = self._mini_closed()
        env = self._env({"PATH": self._path_without_cue()})
        self.assertIsNone(shutil.which("cue", path=env["PATH"]))
        proc = self._check(root, env=env)
        self._assert_refusal(proc, "cue-missing")

    def test_fake_cue_version_exits_2_class_cue_version(self) -> None:
        root = self._mini_closed()
        bin_dir = self.scratch / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "cue"
        self._plant_executable(fake, FAKE_CUE)
        path = str(bin_dir) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
        which = shutil.which("cue", path=path)
        self.assertIsNotNone(which)
        self.assertEqual(fake.resolve(), Path(which).resolve())
        probe = subprocess.run(
            [str(fake), "version"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, probe.returncode)
        self.assertIn("v0.14.1", probe.stdout)
        proc = self._check(root, env=self._env({"PATH": path}))
        self._assert_refusal(proc, "cue-version")

    def test_fully_closed_mini_repo_exits_0(self) -> None:
        root = self._mini_closed()
        proc = self._check(root)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("", proc.stderr)

    def test_declared_absent_is_finding_not_missing_path_refusal(self) -> None:
        root = self._mini_closed()
        (root / CONSUMER_REL).unlink()
        (root / FIXTURE_REL).unlink()
        self.assertFalse((root / CONSUMER_REL).exists())
        self.assertFalse((root / FIXTURE_REL).exists())
        tracked = self._tracked(root)
        self.assertGreaterEqual(len(tracked), 1)
        self._write_index(
            root,
            [self._absent(path, "no consumer on this tree") for path in sorted(tracked)],
        )
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "declare absent")
        proc = self._check(root)
        output = proc.stdout + proc.stderr
        for path in sorted(tracked):
            self.assertIn(path, output)
        self.assertEqual(1, proc.returncode, output)
        self.assertFalse(
            any(line.startswith("closure:") for line in proc.stderr.splitlines()),
            proc.stderr,
        )

    def test_row_extra_field_does_not_evaluate(self) -> None:
        root = self._mini_closed()
        data = self._load_index_file(root / INDEX_REL)
        before = json.dumps(data, sort_keys=True)
        data["contracts"][0]["notes"] = "not-a-row-field"
        self._write_index(root, data["contracts"])
        after = json.dumps(self._load_index_file(root / INDEX_REL), sort_keys=True)
        self.assertNotEqual(before, after)
        self.assertIn("not-a-row-field", after)
        self._git(root, "add", INDEX_REL)
        self._git(root, "commit", "-m", "plant extra field")
        proc = self._check(root)
        combined = proc.stdout + proc.stderr
        self.assertTrue(
            "field not allowed" in combined or "notes" in combined,
            combined,
        )
        self.assertEqual(2, proc.returncode, proc.stderr)


if __name__ == "__main__":
    unittest.main()
