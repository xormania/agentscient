"""Review findings against repo/self-hosted-runners' own commits.

Contract: `.dev/records/dispatches/20260828T220750Z-review-claude-4fbe47.json`
`result.envelope.findings`. In scope: the six findings about this
branch's commits (Sandbox excludesFile, pipx --force, sibling unsigned
fixtures, initialise_repo's 'probe' name-gate, a test class after
__main__, ci-minutes.yml assuming gh/python3). The days input,
rounding_share and jobs pagination findings are ruled on repo/ci-burn
and are out of scope.

Written red against
`fce9ad79ce00acee3b1f6effef2e66f53228b14c` before any fix, per
`ops/process/tdd.md`. One test per finding; each is red for that
finding's stated reason, not for another finding's surface.
"""

from __future__ import annotations

import ast
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
import test_gate_binding as gate_binding
import test_operator_git_isolation as isolation
import test_secret_signatures as secret_signatures
import test_slice2_review as slice2_review

git = isolation.git
operator_git_global = isolation.operator_git_global

REPO = support.WF_DIR.parent.parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
DEV_YML = WORKFLOWS / "ci-dev.yml"
APPS_YML = WORKFLOWS / "ci-dev-apps.yml"
MINUTES_YML = WORKFLOWS / "ci-minutes.yml"
TESTS = Path(__file__).resolve().parent

NOTES = "notes.txt"
CANDIDATE = "candidate.txt"
RECOGNISABLE = b"recognisable clean fixture\n"

PYTHON_PROVISION = re.compile(
    r"actions/setup-python|setup-python@|"
    r"pipx install[^\n]*python|"
    r"apt-get install[^\n]*python3|"
    r"dnf install[^\n]*python3|"
    r"brew install[^\n]*python",
    re.IGNORECASE,
)
GH_PROVISION = re.compile(
    r"cli/cli@|cli/setup-gh|setup-gh@|"
    r"pipx install[^\n]*\bgh\b|"
    r"apt-get install[^\n]*\bgh\b|"
    r"dnf install[^\n]*\bgh\b|"
    r"brew install[^\n]*\bgh\b",
    re.IGNORECASE,
)


def _jobs(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    jobs: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        head = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):$", line)
        if head:
            current = head.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def _main_guard_lineno(tree: ast.AST) -> int | None:
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            continue
        if not isinstance(test.ops[0], ast.Eq):
            continue
        left, comparators = test.left, test.comparators
        if len(comparators) != 1:
            continue
        names = (
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(comparators[0], ast.Constant)
            and comparators[0].value == "__main__"
        )
        swapped = (
            isinstance(comparators[0], ast.Name)
            and comparators[0].id == "__name__"
            and isinstance(left, ast.Constant)
            and left.value == "__main__"
        )
        if names or swapped:
            return node.lineno
    return None


class SandboxDoesNotInheritTheOperatorExcludesFile(unittest.TestCase):
    """[high, Claude] The shared Sandbox still inherits the operator's
    global core.excludesFile.

    Sandbox sets identity, commit.gpgsign=false and core.hooksPath, then
    `git add -A` to seed and again in commit_all(). It never sets
    core.excludesFile. A global rule matching a name Sandbox writes
    (notes.txt, *.json, …) silently drops that file, so the assertion
    afterwards answers a question about a different fileset.
    """

    def test_sandbox_keeps_a_file_the_operator_excludes(self):
        with tempfile.TemporaryDirectory(prefix="wf-sb-excludes-") as raw:
            base = Path(raw)
            ignore = base / "ignore"
            ignore.write_text(f"{NOTES}\n")
            self.assertEqual(
                ignore.read_text(encoding="utf-8"),
                f"{NOTES}\n",
                "INVALID fixture: excludesFile did not land intact",
            )

            config_body = f'[core]\n\texcludesFile = "{ignore}"\n'
            with operator_git_global(config_body):
                probe = base / "probe"
                probe.mkdir()
                git(probe, "init", "-q", "-b", "main")
                git(probe, "config", "user.email", "t@x")
                git(probe, "config", "user.name", "T")
                git(probe, "config", "commit.gpgsign", "false")
                (probe / NOTES).write_bytes(RECOGNISABLE)
                self.assertEqual((probe / NOTES).read_bytes(), RECOGNISABLE)
                git(probe, "add", "-A", check=False)
                ignored = git(probe, "check-ignore", "-q", NOTES, check=False)
                self.assertEqual(
                    ignored.returncode, 0,
                    f"INVALID fixture: excludesFile did not match {NOTES}",
                )
                listed = git(
                    probe, "ls-files", "--error-unmatch", NOTES, check=False,
                )
                self.assertNotEqual(
                    listed.returncode, 0,
                    f"INVALID fixture: excludesFile did not drop {NOTES}",
                )

                sb = None
                try:
                    sb = support.Sandbox()
                    written = sb.write(NOTES, RECOGNISABLE.decode())
                    self.assertEqual(
                        written.read_bytes(), RECOGNISABLE,
                        "INVALID fixture: planted notes.txt did not land intact",
                    )
                    ignored = git(sb.dir, "check-ignore", "-q", NOTES, check=False)
                    self.assertNotEqual(
                        ignored.returncode, 0,
                        "Sandbox still honours the operator excludesFile "
                        f"for {NOTES}",
                    )
                    try:
                        sb.commit_all("sandbox: notes")
                    except subprocess.CalledProcessError as err:
                        self.fail(
                            "Sandbox commit_all omitted notes.txt under "
                            f"the operator excludesFile: {err.stderr}"
                        )
                    listed = git(
                        sb.dir, "ls-files", "--error-unmatch", NOTES, check=False,
                    )
                    self.assertEqual(
                        listed.returncode, 0,
                        "Sandbox git add -A dropped notes.txt matching "
                        "the operator excludesFile",
                    )
                finally:
                    if sb is not None:
                        sb.destroy()


class PipxInstallReplacesAPreexistingBinary(unittest.TestCase):
    """[high, Claude] pipx install is a no-op against a pre-existing
    ~/.local/bin/ruff, so the PATH fix can resolve the wrong ruff.

    `pipx install 'ruff>=0.16,<0.17'` without --force exits 0 and does
    not replace an occupied symlink. On a self-hosted runner with a
    persistent HOME the version range never binds.
    """

    def test_every_pipx_ruff_install_forces_or_upgrades_or_uses_the_venv(self):
        paths = (DEV_YML, APPS_YML)
        self.assertEqual(len(paths), 2)
        for path in paths:
            with self.subTest(path.name):
                self.assertTrue(path.is_file(), path)
                jobs = {
                    name: body for name, body in _jobs(path).items()
                    if "pipx install" in body and "ruff" in body
                }
                self.assertTrue(
                    jobs,
                    f"{path.name}: no job runs pipx install ruff",
                )
                for name, body in jobs.items():
                    install_lines = re.findall(r"pipx install[^\n]+", body)
                    ruff_installs = [ln for ln in install_lines if "ruff" in ln]
                    self.assertTrue(
                        ruff_installs,
                        f"{path.name} job {name}: pipx install ruff line missing",
                    )
                    replaces = (
                        any("--force" in ln for ln in ruff_installs)
                        or bool(re.search(
                            r"pipx upgrade --install[^\n]*ruff", body
                        ))
                        or "pipx/venvs/ruff" in body
                    )
                    self.assertTrue(
                        replaces,
                        f"{path.name} job {name}: pipx install ruff is a "
                        "no-op against a pre-existing ~/.local/bin/ruff "
                        "without --force, pipx upgrade --install, or an "
                        f"absolute pipx venv path; lines were {ruff_installs}",
                    )


class SiblingUnsignedFixturesDoNotInheritGlobalSigning(unittest.TestCase):
    """[medium, Claude] The unsigned-fixture defect class is left live
    in sibling fixtures the sweep's wording covers.

    test_gate_binding.seed_commit_trailers and
    test_slice2_review.SeededChecksAreProvenToFire.commit set a git
    identity and commit, but neither sets commit.gpgsign=false.
    --no-verify bypasses hooks, not signing.
    """

    def test_gate_binding_and_slice2_construct_when_operator_requires_signing(self):
        with tempfile.TemporaryDirectory(prefix="wf-sib-sign-") as raw:
            refuse = Path(raw) / "refuse-sign"
            refuse.write_text(
                "#!/bin/sh\necho operator-global-signer >&2\nexit 1\n"
            )
            refuse.chmod(
                refuse.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
            self.assertTrue(
                os.access(refuse, os.X_OK),
                "INVALID fixture: signer is not executable",
            )

            config_body = (
                "[commit]\n"
                "\tgpgsign = true\n"
                "[gpg]\n"
                f'\tprogram = "{refuse}"\n'
            )
            with operator_git_global(config_body):
                probe = Path(raw) / "probe"
                probe.mkdir()
                git(probe, "init", "-q", "-b", "main")
                git(probe, "config", "user.email", "t@x")
                git(probe, "config", "user.name", "T")
                (probe / "f").write_text("probe\n")
                git(probe, "add", "-A")
                declined = git(
                    probe, "commit", "-q", "--no-verify", "-m", "probe",
                    check=False,
                )
                self.assertNotEqual(
                    declined.returncode, 0,
                    "INVALID fixture: commit.gpgsign did not engage",
                )
                self.assertIn("operator-global-signer", declined.stderr)

                with self.subTest("test_gate_binding.seed_commit_trailers"):
                    root = Path(raw) / "gate"
                    root.mkdir()
                    git(root, "init", "-q", "-b", "main")
                    case = gate_binding.RegisteredGateBindings()
                    try:
                        case.seed_commit_trailers(root, faulty=False)
                    except (AssertionError, subprocess.CalledProcessError) as err:
                        self.fail(
                            "test_gate_binding.seed_commit_trailers must not "
                            "inherit commit.gpgsign; fixture construction "
                            f"failed: {err}"
                        )

                with self.subTest("test_slice2_review.SeededChecksAreProvenToFire.commit"):
                    case = slice2_review.SeededChecksAreProvenToFire()
                    case.dir = Path(raw) / "slice2"
                    case.dir.mkdir()
                    git(case.dir, "init", "-q", "-b", "main")
                    (case.dir / "f").write_text("x\n")
                    try:
                        case.commit()
                    except subprocess.CalledProcessError as err:
                        self.fail(
                            "test_slice2_review.SeededChecksAreProvenToFire."
                            "commit must not inherit commit.gpgsign; "
                            "fixture construction failed: "
                            f"{err.stderr or err}"
                        )


class InitialiseRepoDoesNotGateIsolationOnADirectoryName(unittest.TestCase):
    """[medium, Claude] initialise_repo skips its own isolation based on
    a magic directory name.

    `if Path(root).name != "probe"` gates core.excludesFile /dev/null,
    so any future fixture that names its tmpdir 'probe' silently loses
    excludesFile isolation.
    """

    def test_initialise_repo_isolates_excludes_when_the_directory_is_named_probe(self):
        with tempfile.TemporaryDirectory(prefix="wf-probe-name-") as raw:
            base = Path(raw)
            ignore = base / "ignore"
            ignore.write_text(f"{CANDIDATE}\n")
            self.assertEqual(
                ignore.read_text(encoding="utf-8"),
                f"{CANDIDATE}\n",
                "INVALID fixture: excludesFile did not land intact",
            )

            config_body = f'[core]\n\texcludesFile = "{ignore}"\n'
            with operator_git_global(config_body):
                plant = base / "raw"
                plant.mkdir()
                git(plant, "init", "-q", "-b", "main")
                git(plant, "config", "user.email", "t@x")
                git(plant, "config", "user.name", "T")
                (plant / CANDIDATE).write_bytes(RECOGNISABLE)
                self.assertEqual((plant / CANDIDATE).read_bytes(), RECOGNISABLE)
                git(plant, "add", CANDIDATE, check=False)
                ignored = git(plant, "check-ignore", "-q", CANDIDATE, check=False)
                self.assertEqual(
                    ignored.returncode, 0,
                    "INVALID fixture: excludesFile did not match candidate.txt",
                )
                listed = git(
                    plant, "ls-files", "--error-unmatch", CANDIDATE, check=False,
                )
                self.assertNotEqual(
                    listed.returncode, 0,
                    "INVALID fixture: the excludesFile did not drop the add",
                )

                root = base / "probe"
                root.mkdir()
                self.assertEqual(root.name, "probe")
                case = secret_signatures.EverySecretSignatureFires()
                case.initialise_repo(root)
                relative = Path(CANDIDATE)
                candidate = root / relative
                candidate.write_bytes(RECOGNISABLE)
                self.assertEqual(
                    candidate.read_bytes(), RECOGNISABLE,
                    "INVALID fixture: planted candidate did not land intact",
                )
                added = git(root, "add", relative.as_posix(), check=False)
                self.assertEqual(added.returncode, 0, added.stderr)
                case.assert_indexed(root, relative)


class ATestModuleDefinesNoClassAfterItsMainGuard(unittest.TestCase):
    """[low, Claude] The new PATH test class is defined after the
    module's `if __name__ == "__main__"` block.

    `python3 test_ci_shape.py` runs unittest.main() before the class
    statement is reached and reports a green run that never contained
    that test.
    """

    def test_the_path_test_class_is_defined_before_the_main_guard(self):
        path = TESTS / "test_ci_shape.py"
        self.assertTrue(path.is_file(), path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = {
            node.name: node.lineno
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        self.assertIn(
            "AToolInstalledByAJobIsOnThatJobsPath", classes,
            "INVALID: the PATH test class this finding names is gone",
        )
        guard = _main_guard_lineno(tree)
        if guard is None:
            return
        self.assertLess(
            classes["AToolInstalledByAJobIsOnThatJobsPath"], guard,
            "AToolInstalledByAJobIsOnThatJobsPath is defined after "
            f"`if __name__ == \"__main__\"` (class at line "
            f"{classes['AToolInstalledByAJobIsOnThatJobsPath']}, guard at "
            f"{guard}), so `python3 test_ci_shape.py` never collects it",
        )


class CiMinutesDoesNotAssumeTheRunnerPath(unittest.TestCase):
    """[low, Claude] ci-minutes.yml assumes gh and python3 are on the
    self-hosted runner's PATH, which is the assumption the sibling
    commit exists to forbid.

    The tool shells out to `gh`; the workflow invokes `python3`
    directly. Neither is installed by the job, and nothing appends a
    bin directory to $GITHUB_PATH.
    """

    def test_ci_minutes_provisions_gh_and_python3_instead_of_assuming_the_runner(self):
        self.assertTrue(MINUTES_YML.is_file(), MINUTES_YML)
        text = MINUTES_YML.read_text(encoding="utf-8")
        self.assertIn(
            "python3 ops/devlane/workflow/checks/ci_minutes.py", text,
            "INVALID: ci-minutes.yml no longer invokes the tool with python3",
        )
        self.assertRegex(
            text, r"self-hosted|CI_RUNNER",
            "INVALID: ci-minutes.yml is not the self-hosted minutes job",
        )
        with self.subTest("python3"):
            self.assertRegex(
                text, PYTHON_PROVISION,
                "ci-minutes.yml invokes python3 on a self-hosted runner "
                "without provisioning it (setup-python, pipx, or a package "
                "install)",
            )
        with self.subTest("gh"):
            self.assertRegex(
                text, GH_PROVISION,
                "ci-minutes.yml runs ci_minutes.py, which shells out to gh, "
                "without provisioning gh (cli/cli, setup-gh, pipx, or a "
                "package install)",
            )


if __name__ == "__main__":
    unittest.main()
