"""Bind CI registry entries to the checkers and faults they promise to detect."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

REPO = support.WF_DIR.parent.parent.parent
GATE_KINDS = support.WF_DIR / "gate-kinds"

# ci_required False for diagnostics: its argv wraps `cargo check`,
# and the registry's documented state (wf-tests.yml, PLAN section 7)
# keeps cargo-dependent checks out of the matrix until a Cargo
# workspace exists at the repo root. The script binding is still
# pinned; the flag flips WITH the workspace, deliberately.
# diagnostics' ci requirement is the Cargo-workspace state itself:
# out of the matrix while no workspace exists (a permanently red
# WF:gates guards nothing), REQUIRED in it the day one lands —
# two-sided, so it cannot linger unflagged (Grok, PR #32 review).
_CARGO_WORKSPACE = (
    Path(__file__).resolve().parents[3] / "Cargo.toml").is_file()
REQUIRED_BINDINGS = {
    ("artifact", "secret-scan"): ("secret_scan.py", True),
    ("artifact", "vocabulary-wall"): ("vocabulary_wall.py", True),
    ("tdd", "secret-scan"): ("secret_scan.py", True),
    ("tdd", "diagnostics"): ("diagnostics.py", _CARGO_WORKSPACE),
    ("tdd", "lint"): ("lint.py", True),
}


class RegisteredGateBindings(unittest.TestCase):
    def registry_entries(self):
        entries = []
        for name in ("artifact.json", "tdd.json"):
            path = GATE_KINDS / name
            self.assertTrue(path.is_file(), path)
            spec = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(spec.get("checks"), list, path)
            for check in spec["checks"]:
                entries.append((spec["kind"], check))
        self.assertGreater(len(entries), 0, "both registries must contain checks")
        return entries

    def check_script(self, kind, check):
        argv = check.get("argv")
        self.assertIsInstance(argv, list, f"{kind}/{check.get('name')}: argv")
        scripts = [
            arg for arg in argv
            if isinstance(arg, str)
            and arg.startswith("ops/devlane/workflow/checks/")
            and arg.endswith(".py")
        ]
        self.assertEqual(
            len(scripts), 1,
            f"{kind}/{check.get('name')} must invoke exactly one workflow checker",
        )
        expected = f"{check['name'].replace('-', '_')}.py"
        self.assertEqual(Path(scripts[0]).name, expected)
        return scripts[0]

    def initialise_repo(self, root):
        proc = subprocess.run(
            ["git", "init", "-q", "-b", "main"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def assert_indexed(self, root, path):
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), path.as_posix())

    def seed_secret_scan(self, root, faulty):
        candidate = root / "config.txt"
        candidate.write_bytes(b"mode=clean\n")
        if faulty:
            secret = b"AKIA" + b"ABCDEFGHIJKLMNOP"
            support.plant_bytes(
                candidate,
                lambda raw: raw + b"key=" + secret + b"\n",
                expect="grow",
                recognisable=lambda raw: secret in raw and b"mode=clean" in raw,
            )
            self.assertIn(secret, candidate.read_bytes())
        proc = subprocess.run(
            ["git", "add", candidate.name],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_indexed(root, Path(candidate.name))

    def seed_vocabulary_wall(self, root, faulty):
        artifact = root / "design" / "artifact.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"Scientific observation remains reproducible.\n")
        if faulty:
            support.plant_bytes(
                artifact,
                lambda raw: raw + b"Each write produces a receipt.\n",
                expect="grow",
                recognisable=lambda raw: (
                    b"Scientific observation" in raw and b"receipt" in raw
                ),
            )
            self.assertIn(b"receipt", artifact.read_bytes())

    def seed_doc_commands(self, root, faulty):
        """A document that tells a reader to run something.

        Clean: the script named in the fence is beside the document.
        Faulty: the script is removed and the instruction is left, which
        is exactly what shipped on 2026-08-25 -- the doc rendered, the
        docs-index suite passed, the ghost-link check passed because it
        reads only markdown links, and CI was green.
        """
        doc = root / "docs" / "aar.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(
            "# aar\n\nOutput of `lessons.sh`:\n\n"
            "```sh\n./lessons.sh\n```\n")
        script = doc.parent / "lessons.sh"
        script.write_text("#!/bin/sh\necho measured\n")
        if faulty:
            script.unlink()
            self.assertFalse(script.exists())
            self.assertIn("./lessons.sh", doc.read_text())

    def seed_diagnostics(self, root, faulty):
        manifest = root / "Cargo.toml"
        manifest.write_text(
            '[package]\n'
            'name = "diagnostics-binding"\n'
            'version = "0.1.0"\n'
            'edition = "2021"\n',
            encoding="utf-8",
        )
        source = root / "src" / "lib.rs"
        source.parent.mkdir()
        source.write_bytes(b"pub fn answer() -> u32 { 42 }\n")
        if faulty:
            support.plant_bytes(
                source,
                lambda raw: raw.replace(b"42", b'"broken"'),
                expect="grow",
                recognisable=lambda raw: (
                    b"pub fn answer()" in raw and b'"broken"' in raw
                ),
            )
            self.assertIn(b'"broken"', source.read_bytes())

    def seed_lint(self, root, faulty):
        # The checker refuses without the pinned contract, so the
        # fixture carries the real one — the planted fault is then
        # judged by the rules the repo actually enforces.
        contract = REPO / "ruff.toml"
        self.assertTrue(contract.is_file(), contract)
        shutil.copy2(contract, root / "ruff.toml")
        self.assertEqual((root / "ruff.toml").read_bytes(),
                         contract.read_bytes())
        module = root / "module.py"
        module.write_bytes(b"def answer():\n    return 42\n")
        if faulty:
            support.plant_bytes(
                module,
                lambda raw: b"import os\n" + raw,
                expect="grow",
                recognisable=lambda raw: (
                    b"import os" in raw and b"def answer()" in raw
                ),
            )
            self.assertIn(b"import os", module.read_bytes())

    def seed_commit_trailers(self, root, faulty):
        """A history, not a file: this checker reads commit messages.

        The plant is one blank line. It is asserted to differ from the
        control before it is used, and the resulting commit is asserted
        to actually present the condition -- Source unparsed when
        faulty, parsed when clean -- because a fixture whose plant
        silently failed would let the faulty case pass for the wrong
        reason and the clean case pass for no reason.
        """
        def git(*args):
            proc = subprocess.run(["git", *args], cwd=root,
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc

        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "fixture")
        git("config", "commit.gpgsign", "false")
        (root / "base.txt").write_bytes(b"base\n")
        git("add", "base.txt")
        git("commit", "-q", "--no-verify", "-m", "base")
        # the check measures from origin/dev; the fixture supplies one
        git("update-ref", "refs/remotes/origin/dev", git("rev-parse", "HEAD").stdout.strip())

        control = ("subject\n\nbody paragraph.\n\n"
                   "Source: original\nCo-Authored-By: A <a@x>\n")
        planted = control.replace("\nCo-Authored-By", "\n\nCo-Authored-By")
        self.assertNotEqual(planted, control, "INVALID: the plant is a no-op")

        message = planted if faulty else control
        msg_file = root / "fixture.msg"
        msg_file.write_text(message, encoding="utf-8")
        self.assertEqual(msg_file.read_text(encoding="utf-8"), message,
                         "INVALID: the message did not land")
        (root / "work.txt").write_bytes(b"work\n")
        git("add", "work.txt")
        git("commit", "-q", "--no-verify", "-F", str(msg_file))
        msg_file.unlink()

        parsed = git("log", "-1",
                     "--format=%(trailers:key=Source,valueonly)").stdout.strip()
        if faulty:
            self.assertEqual(parsed, "",
                             "INVALID: the plant did not break the parse")
        else:
            self.assertEqual(parsed, "original",
                             "INVALID: the control does not parse")

    def seed_doc_covers(self, root, faulty):
        """A shelf doc whose covers: names a path in this repository.

        Clean: the named path exists at the fixture root.
        Faulty: the named path is rewritten to something that does not
        exist, which is the finding the check is registered to catch.
        """
        shelf = root / "ops" / "docs"
        shelf.mkdir(parents=True)
        target = root / "README.md"
        target.write_text("fixture\n")
        doc = shelf / "note.md"
        clean = (
            "---\nname: note\ndescription: a fixture\n"
            "covers:\n  - README.md\n---\nbody\n"
        )
        doc.write_text(clean)
        self.assertEqual(doc.read_text(), clean)
        self.assertTrue(target.is_file())
        if faulty:
            support.plant_bytes(
                doc,
                lambda raw: raw.replace(b"README.md", b"no/such/path.py"),
                expect="grow",
                recognisable=lambda raw: (
                    b"name: note" in raw and b"no/such/path.py" in raw
                ),
            )
            self.assertIn("no/such/path.py", doc.read_text())
            self.assertFalse((root / "no/such/path.py").exists())

    def seed_fixture(self, root, check_name, faulty):
        seeders = {
            "secret-scan": self.seed_secret_scan,
            "vocabulary-wall": self.seed_vocabulary_wall,
            "diagnostics": self.seed_diagnostics,
            "lint": self.seed_lint,
            "commit-trailers": self.seed_commit_trailers,
            "doc-commands": self.seed_doc_commands,
            "doc-covers": self.seed_doc_covers,
        }
        self.assertIn(
            check_name, seeders,
            f"CI checker {check_name!r} needs an explicit planted-fault fixture",
        )
        seeders[check_name](root, faulty)

    def run_registered(self, kind, check, script_arg, faulty):
        with tempfile.TemporaryDirectory(prefix="wf-gate-binding-") as raw:
            root = Path(raw)
            self.initialise_repo(root)

            source = REPO / script_arg
            self.assertTrue(
                source.is_file(),
                f"{kind}/{check['name']} registers missing script {script_arg}",
            )
            target = root / script_arg
            target.parent.mkdir(parents=True)
            shutil.copy2(source, target)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertGreater(len(target.read_bytes()), 0)

            self.seed_fixture(root, check["name"], faulty)
            proc = subprocess.run(
                list(check["argv"]),
                cwd=root,
                capture_output=True,
                text=True, check=False,
            )
            message = (
                f"{kind}/{check['name']} argv={check['argv']!r}\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
            if faulty:
                self.assertNotEqual(proc.returncode, 0, message)
            else:
                self.assertEqual(proc.returncode, 0, message)

    def test_every_registered_ci_checker_is_bound_to_clean_and_faulty_repos(self):
        entries = self.registry_entries()
        by_key = {}
        for kind, check in entries:
            key = (kind, check.get("name"))
            by_key.setdefault(key, []).append(check)

        cargo_workspace = (REPO / "Cargo.toml").is_file()
        for key, (expected_script, ci_required) in REQUIRED_BINDINGS.items():
            self.assertIn(key, by_key, f"required registered check missing: {key}")
            self.assertEqual(len(by_key[key]), 1, f"duplicate check registration: {key}")
            check = by_key[key][0]
            if ci_required:
                self.assertIs(
                    check.get("ci"), True,
                    f"{key} must remain present in the derived CI matrix",
                )
            elif not cargo_workspace:
                # a cargo-dependent check in the matrix with no
                # workspace turns WF:gates permanently red
                self.assertIsNot(
                    check.get("ci"), True,
                    f"{key} cannot join the matrix before a Cargo"
                    " workspace exists",
                )
            self.assertEqual(
                Path(self.check_script(key[0], check)).name,
                expected_script,
            )

        bound = []
        cargo = shutil.which("cargo") is not None
        for kind, check in entries:
            runnable = (check.get("ci") is True
                        or (check.get("name") == "diagnostics" and cargo))
            if not runnable:
                continue
            argv = check.get("argv")
            if not isinstance(argv, list):
                continue
            if not any(
                isinstance(arg, str)
                and arg.startswith("ops/devlane/workflow/checks/")
                and arg.endswith(".py")
                for arg in argv
            ):
                continue
            script_arg = self.check_script(kind, check)
            bound.append((kind, check["name"]))
            with self.subTest(kind=kind, check=check["name"], fixture="clean"):
                self.run_registered(kind, check, script_arg, faulty=False)
            with self.subTest(kind=kind, check=check["name"], fixture="fault"):
                self.run_registered(kind, check, script_arg, faulty=True)

        ci_required_count = sum(
            1 for _, ci_required in REQUIRED_BINDINGS.values()
            if ci_required)
        self.assertGreaterEqual(
            len(bound), ci_required_count,
            "the registry-to-checker loop must not be vacuous",
        )


if __name__ == "__main__":
    unittest.main()
