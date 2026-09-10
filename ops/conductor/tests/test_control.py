import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("CONTROL_REPO", Path(__file__).resolve().parents[3]))
CONTROL = ROOT / "ops/conductor/tools/control.py"
HOOK = ROOT / "ops/devlane/hooks/conductor-control.py"
AUTHOR = "Test Author <author@example.test>"
REVIEWER = "Test Reviewer <reviewer@example.test>"
CODER = "Code Producer <coder@example.test>"

TEST_SOURCE = """from impl import foo
import unittest
class T(unittest.TestCase):
 def test_foo(self): self.assertEqual(foo(), 42)
if __name__ == '__main__': unittest.main()
"""
MAKE_TEST = (
    "from pathlib import Path;import subprocess;Path('t.py').write_text("
    + repr(TEST_SOURCE)
    + ");subprocess.run(['git','add','t.py'],check=True)"
)
FIXTURE = "import impl;assert impl.foo() is None"
REVIEW = """import hashlib,json,os,subprocess,sys
s=json.loads(subprocess.check_output([sys.executable,%r,'status','--state',os.environ['CONTROL_STATE']],text=True))
r=s['actions_state']['red']; rows=r['tests']
d=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
print(json.dumps({'verdict':'approve','tests_sha256':d,'red_sha256':r['stdout_sha256']},separators=(',',':')))
""" % str(CONTROL)
CODE = (
    "from pathlib import Path;Path('impl.py').write_text('def foo():\\n return 42\\n')"
)
RED = ["unittest", "discover", "-p", "t.py"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def action(id, kind, argv, requires=(), tests=(), producer=AUTHOR, timeout=5):
    return {
        "id": id,
        "kind": kind,
        "argv": argv,
        "timeout": timeout,
        "requires": list(requires),
        "tests": list(tests),
        "producer": producer,
    }


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo, self.state = base / "repo", base / "state"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Fixture"], cwd=self.repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture@example.test"],
            cwd=self.repo,
            check=True,
        )
        (self.repo / "SCOPE.md").write_text("Make foo return 42.\n")
        (self.repo / "impl.py").write_text("def foo():\n return None\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.plan_path = base / "plan.json"

    def tearDown(self):
        self.tmp.cleanup()

    def cp(self, *args, agent=AUTHOR, timeout=12, input=None):
        env = os.environ.copy()
        if agent is None:
            env.pop("WF_AGENT", None)
        else:
            env["WF_AGENT"] = agent
        try:
            return subprocess.run(
                [sys.executable, str(CONTROL), *args],
                cwd=self.repo,
                env=env,
                input=input,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            self.fail("missing control CLI: %s" % e)

    def plan(self, actions, max_seconds=20):
        scope = (self.repo / "SCOPE.md").read_bytes()
        return {
            "version": 1,
            "repo": str(self.repo.resolve()),
            "branch": "main",
            "scope": "SCOPE.md",
            "scope_sha256": sha(scope),
            "expires_at": "2099-01-01T00:00:00Z",
            "max_seconds": max_seconds,
            "actions": actions,
        }

    def init(self, actions, max_seconds=20):
        self.plan_path.write_text(
            json.dumps(self.plan(actions, max_seconds), separators=(",", ":"))
        )
        r = self.cp("init", str(self.plan_path), "--state", str(self.state))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def run_action(self, id, agent=AUTHOR, timeout=12):
        return self.cp(
            "run", id, "--state", str(self.state), agent=agent, timeout=timeout
        )

    def status(self):
        r = self.cp("status", "--state", str(self.state), agent=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def assert_refusal(self, r):
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertEqual(r.stdout, "")
        self.assertRegex(r.stderr, r"^[a-z]+: expected .+; found .+; needed .+\n$")

    def tdd(self, review=REVIEW, producers=(AUTHOR, REVIEWER, CODER)):
        a, rv, c = producers
        return [
            action(
                "tests",
                "tests",
                [sys.executable, "-c", MAKE_TEST],
                tests=["t.py"],
                producer=a,
            ),
            action(
                "fixture",
                "fixture",
                [sys.executable, "-c", FIXTURE],
                ["tests"],
                ["t.py"],
                a,
            ),
            action("red", "red", RED, ["fixture"], ["t.py"], a),
            action(
                "review",
                "test-review",
                [sys.executable, "-c", review],
                ["red"],
                ["t.py"],
                rv,
            ),
            action(
                "code", "code", [sys.executable, "-c", CODE], ["review"], ["t.py"], c
            ),
            action("green", "green", RED, ["code"], ["t.py"], c),
        ]

    def test_full_tdd_path_records_real_red_then_green(self):
        self.init(self.tdd())
        for id, who in [
            ("tests", AUTHOR),
            ("fixture", AUTHOR),
            ("red", AUTHOR),
            ("review", REVIEWER),
            ("code", CODER),
            ("green", CODER),
        ]:
            r = self.run_action(id, who)
            self.assertEqual(r.returncode, 0, (id, r.stdout, r.stderr))
        s = self.status()["actions_state"]
        red = json.loads(Path(s["red"]["stdout_path"]).read_text())
        self.assertGreater(red["testsRun"], 0)
        self.assertGreater(red["failures"], 0)
        self.assertEqual(red["errors"], 0)
        self.assertEqual(s["green"]["status"], "completed")
        self.assertEqual(
            __import__("subprocess")
            .check_output(
                [sys.executable, "-c", "import impl;print(impl.foo())"],
                cwd=self.repo,
                text=True,
            )
            .strip(),
            "42",
        )

    def test_import_error_red_fails_and_blocks_code(self):
        bad = "from missing_impl import nope\n"
        mk = (
            "from pathlib import Path;import subprocess;Path('t.py').write_text(%r);subprocess.run(['git','add','t.py'],check=True)"
            % bad
        )
        acts = self.tdd()
        acts[0]["argv"] = [sys.executable, "-c", mk]
        acts[1]["argv"] = [sys.executable, "-c", "pass"]
        self.init(acts)
        self.assertEqual(self.run_action("tests").returncode, 0)
        self.assertEqual(self.run_action("fixture").returncode, 0)
        self.assertEqual(self.run_action("red").returncode, 1)
        red = json.loads(
            Path(self.status()["actions_state"]["red"]["stdout_path"]).read_text()
        )
        self.assertGreater(red["errors"], 0)
        self.assert_refusal(self.run_action("code", CODER))
        self.assertIn("return None", (self.repo / "impl.py").read_text())

    def test_code_refuses_missing_prerequisites_without_effect(self):
        self.init(self.tdd())
        self.assert_refusal(self.run_action("code", CODER))
        self.assertIn("return None", (self.repo / "impl.py").read_text())

    def test_identity_stale_review_and_test_drift_block_code(self):
        cases = ["same", "stale", "drift"]
        for case in cases:
            with self.subTest(case=case):
                self.tearDown()
                self.setUp()
                review = REVIEW
                producers = (AUTHOR, REVIEWER, CODER)
                if case == "same":
                    producers = (AUTHOR, AUTHOR, CODER)
                if case == "stale":
                    review = REVIEW.replace("r['stdout_sha256']", "'0'*64")
                self.init(self.tdd(review, producers))
                for id, who in [
                    ("tests", AUTHOR),
                    ("fixture", AUTHOR),
                    ("red", AUTHOR),
                ]:
                    self.assertEqual(self.run_action(id, who).returncode, 0)
                rr = self.run_action("review", producers[1])
                if case == "drift":
                    self.assertEqual(rr.returncode, 0)
                    (self.repo / "t.py").write_text(TEST_SOURCE + "# drift\n")
                else:
                    self.assertIn(rr.returncode, (1, 2))
                self.assert_refusal(self.run_action("code", CODER))

    def test_actions_are_durable_once_only_concurrent_and_failed(self):
        slow = action(
            "once", "check", [sys.executable, "-c", "import time;time.sleep(.4)"]
        )
        fail = action("fail", "check", [sys.executable, "-c", "raise SystemExit(7)"])
        self.init([slow, fail])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            rs = list(ex.map(lambda _: self.run_action("once"), range(2)))
        self.assertEqual(sorted(r.returncode for r in rs), [0, 2])
        self.assert_refusal(self.run_action("once"))
        self.assertEqual(self.run_action("fail").returncode, 1)
        self.assert_refusal(self.run_action("fail"))

    def test_real_timeout_survives_closed_streams_and_exhausts_budget(self):
        src = "import os,time;os.close(1);os.close(2);time.sleep(10)"
        self.init(
            [
                action("hang", "check", [sys.executable, "-c", src], timeout=1),
                action(
                    "later",
                    "check",
                    [sys.executable, "-c", "pass"],
                    ["hang"],
                    timeout=1,
                ),
            ],
            max_seconds=1,
        )
        start = time.monotonic()
        r = self.run_action("hang", timeout=5)
        self.assertEqual(r.returncode, 3)
        self.assertLess(time.monotonic() - start, 4)
        self.assertEqual(self.status()["actions_state"]["hang"]["status"], "aborted")
        self.assert_refusal(self.run_action("later"))

    def test_single_seat_and_native_boundary(self):
        self.init([action("ok", "check", [sys.executable, "-c", "pass"])])
        env = dict(os.environ, WF_AGENT=AUTHOR)
        p = subprocess.Popen(
            [
                sys.executable,
                str(CONTROL),
                "seat",
                "--state",
                str(self.state),
                "--",
                sys.executable,
                "-c",
                "import time;time.sleep(.5)",
            ],
            cwd=self.repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            time.sleep(0.1)
            self.assert_refusal(
                self.cp(
                    "seat",
                    "--state",
                    str(self.state),
                    "--",
                    sys.executable,
                    "-c",
                    "pass",
                )
            )
        finally:
            try:
                p.terminate()
                p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
        self.assert_refusal(
            self.cp(
                "seat", "--state", str(self.state), "--", sys.executable, "-c", "pass"
            )
        )

        def hook(tool, inp):
            payload = json.dumps(
                {"tool_name": tool, "tool_input": inp, "cwd": str(self.repo)}
            )
            return subprocess.run(
                [sys.executable, str(HOOK), "--state", str(self.state)],
                input=payload,
                text=True,
                capture_output=True,
                cwd=self.repo,
                timeout=5,
            )

        for tool, inp in [
            ("Read", {"file_path": str(self.repo / "SCOPE.md")}),
            ("Bash", {"command": "git status"}),
        ]:
            h = hook(tool, inp)
            self.assertEqual(h.returncode, 0)
            self.assertNotIn('"deny"', h.stdout)
        allowed = f"{sys.executable} {CONTROL} run ok --state {self.state}"
        h = hook("Bash", {"command": allowed})
        self.assertEqual(h.returncode, 0)
        self.assertNotIn('"deny"', h.stdout)
        denied = [
            (
                "Edit",
                {
                    "file_path": str(self.repo / "impl.py"),
                    "old_string": "None",
                    "new_string": "42",
                },
            ),
            (
                "Bash",
                {"command": 'python -c \'open(\\"impl.py\\",\\"w\\").write(\\"x\\")\''},
            ),
            ("Bash", {"command": allowed + "; git status"}),
            ("Mystery", {}),
            ("Bash", {"command": "apply_patch"}),
            (
                "Bash",
                {"command": f"{sys.executable} {CONTROL} init x --state {self.state}"},
            ),
            (
                "Bash",
                {
                    "command": f"{sys.executable} {CONTROL} seat --state {self.state} -- pwd"
                },
            ),
        ]
        before = (self.repo / "impl.py").read_bytes()
        for tool, inp in denied:
            h = hook(tool, inp)
            self.assertEqual(h.returncode, 0)
            out = json.loads(h.stdout)
            spec = out["hookSpecificOutput"]
            self.assertEqual(spec["hookEventName"], "PreToolUse")
            self.assertEqual(spec["permissionDecision"], "deny")
        self.assertEqual((self.repo / "impl.py").read_bytes(), before)
        self.assertEqual(hook("Bash", "malformed").returncode, 0)


if __name__ == "__main__":
    unittest.main()
