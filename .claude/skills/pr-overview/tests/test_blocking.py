"""The overview must compare reported names with every expected CI context.

``ci_contexts.py`` owns the check-name derivation.  These tests ask that
module for the expected set; they do not maintain a second workflow reader.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[4]
OVERVIEW = ROOT / ".claude" / "skills" / "pr-overview" / "pr_overview.py"
WORKFLOWS = ROOT / ".github" / "workflows"
WF = ROOT / "ops" / "devlane" / "workflow" / "wf.py"
CI_CONTEXTS = ROOT / "ops" / "devlane" / "workflow" / "checks" / "ci_contexts.py"


def load_overview(root: Path, name: str):
    path = root / OVERVIEW.relative_to(ROOT)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ci_contexts(root: Path, name: str):
    path = root / CI_CONTEXTS.relative_to(ROOT)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_registry(root: Path) -> dict:
    wf = root / WF.relative_to(ROOT)
    proc = subprocess.run(
        [sys.executable, str(wf), "--json", "status", "--checks"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def expected_check_names(root: Path, registry: dict | None = None) -> set[str]:
    """Ask the tree's canonical derivation; do not duplicate it here."""
    contexts = load_ci_contexts(root, "canonical_ci_contexts_for_test")
    payload = check_registry(root) if registry is None else registry
    return set(contexts.derive(payload, root=root))


def one_matrix_check(expected: set[str], registry: dict) -> str:
    """Select, without constructing, one canonical matrix context."""
    suffixes = tuple(f"({name})" for name in registry["ci_matrix"])
    matches = sorted(name for name in expected if name.endswith(suffixes))
    if len(matches) != len(registry["ci_matrix"]):
        raise AssertionError(
            "the canonical set does not contain exactly one context per CI check"
        )
    return matches[0]


def otherwise_ready(check_names: set[str]) -> dict:
    return {
        "checks": {"pass": len(check_names), "names": sorted(check_names)},
        "unresolved": 0,
        "review": "current",
        "merge_state": "CLEAN",
    }


def assert_not_ready_due_to_skipping(testcase, verdict):
    """No-runs skipping: not ready, not 'not reported', mentions skip.

    Without per-name buckets the skipped name cannot be required, and
    ``cannot tell`` is an allowed sentence.
    """
    testcase.assertFalse(verdict.startswith("ready to merge"), verdict)
    testcase.assertNotIn("not reported", verdict)
    testcase.assertRegex(verdict, r"(?i)skip")


def assert_skipped_expected(testcase, verdict, skipped):
    """A named expected skip has reported; it is not ready, incomplete, or unknown."""
    skipped = set(skipped)
    testcase.assertTrue(skipped, "skipped set must be non-empty")
    testcase.assertFalse(verdict.startswith("ready to merge"), verdict)
    testcase.assertFalse(
        verdict.startswith("cannot tell"),
        f"a named expected skip is not an unknown set: {verdict}",
    )
    testcase.assertNotIn("not reported", verdict)
    testcase.assertRegex(verdict, r"(?i)skip")
    absent = [name for name in sorted(skipped) if name not in verdict]
    testcase.assertEqual(
        absent,
        [],
        f"skipped name(s) {absent} missing from verdict: {verdict}",
    )


class BlockingWaitsForTheExpectedCheckSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overview = load_overview(ROOT, "pr_overview_under_test")

    def assert_ready(self, observed: set[str], expected: set[str], root=ROOT):
        verdict = self.overview.blocking(otherwise_ready(observed), root=root)
        self.assertEqual(
            verdict,
            f"ready to merge — all {len(expected)} expected check(s) passed",
        )

    def assert_missing(
        self,
        observed: set[str],
        expected: set[str],
        missing: set[str],
        root=ROOT,
    ):
        verdict = self.overview.blocking(otherwise_ready(observed), root=root)
        self.assertEqual(
            verdict,
            f"checks incomplete — {len(missing)} of {len(expected)} "
            f"expected not reported: {', '.join(sorted(missing))} "
            f"(still registering, or never ran)",
        )

    def test_a_missing_derived_matrix_check_is_not_ready(self):
        registry = check_registry(ROOT)
        expected = expected_check_names(ROOT, registry)
        missing = one_matrix_check(expected, registry)

        self.assert_ready(expected, expected)
        self.assert_missing(expected - {missing}, expected, {missing})

    def test_an_unrelated_pass_cannot_replace_an_expected_check(self):
        registry = check_registry(ROOT)
        expected = expected_check_names(ROOT, registry)
        replaced = one_matrix_check(expected, registry)
        observed = (expected - {replaced}) | {"unrelated-check"}
        self.assertEqual(len(observed), len(expected), "the plant must preserve the count")
        self.assertNotEqual(observed, expected, "the plant must change the names")

        self.assert_ready(expected, expected)
        self.assert_missing(observed, expected, {replaced})

    def test_check_collection_retains_the_names_blocking_must_compare(self):
        expected = expected_check_names(ROOT)
        rows = [{"bucket": "pass", "name": name} for name in sorted(expected)]
        requested_fields = []

        def fake_run(argv, **_kwargs):
            json_arg = argv.index("--json") + 1
            requested_fields.extend(argv[json_arg].split(","))
            returned = [
                {key: value for key, value in row.items() if key in requested_fields}
                for row in rows
            ]
            return subprocess.CompletedProcess(
                argv,
                returncode=0,
                stdout=json.dumps(returned),
                stderr="",
            )

        with mock.patch.object(self.overview.subprocess, "run", side_effect=fake_run):
            checks = self.overview.buckets(17, "owner/repo")

        self.assertIn(
            "name",
            requested_fields,
            "the live gh query must request names instead of only bucket counts",
        )
        self.assertIn(
            "bucket",
            requested_fields,
            "per-name skip attribution needs the bucket of each check-run",
        )
        self.assertEqual(
            checks.get("names"),
            sorted(expected),
            "blocking cannot compare names the collector discarded",
        )
        self.assertEqual(
            [(run["name"], run["bucket"]) for run in checks.get("runs") or ()],
            [(name, "pass") for name in sorted(expected)],
            "blocking cannot attribute skips if the collector discarded per-name buckets",
        )
        row = otherwise_ready(expected)
        row["checks"] = checks
        verdict = self.overview.blocking(row, root=ROOT)
        self.assertEqual(
            verdict,
            f"ready to merge — all {len(expected)} expected check(s) passed",
        )

    def test_a_new_registry_check_is_expected_without_a_hardcoded_update(self):
        with tempfile.TemporaryDirectory(prefix="pr-overview-registry-") as tmp:
            copied_root = Path(tmp) / "repo"
            copied_root.mkdir()
            shutil.copytree(
                WORKFLOWS,
                copied_root / WORKFLOWS.relative_to(ROOT),
            )
            workflow_app = WF.parent
            copied_workflow_app = copied_root / workflow_app.relative_to(ROOT)
            copied_workflow_app.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                workflow_app,
                copied_workflow_app,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "wf.db"),
            )
            before = check_registry(copied_root)
            before_expected = expected_check_names(copied_root, before)
            planted_name = "late-added"
            self.assertNotIn(planted_name, before["ci_matrix"])

            gate_kind = (
                copied_root / "ops" / "devlane" / "workflow" / "gate-kinds"
                / "artifact.json"
            )
            payload = json.loads(gate_kind.read_text(encoding="utf-8"))
            payload["checks"].append(
                {
                    "name": planted_name,
                    "class": "policy",
                    "argv": ["python3", "-c", "raise SystemExit(0)"],
                    "ci": True,
                }
            )
            gate_kind.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            after = check_registry(copied_root)
            self.assertEqual(
                set(after["ci_matrix"]),
                set(before["ci_matrix"]) | {planted_name},
                "the planted registry check must land in the derived matrix",
            )
            after_expected = expected_check_names(copied_root, after)
            added = after_expected - before_expected
            self.assertEqual(
                len(added),
                1,
                "the canonical expected set must grow by exactly one context",
            )
            added_name = next(iter(added))
            self.assertIn(
                planted_name,
                added_name,
                "the new canonical context must be the planted registry entry",
            )

            self.assert_missing(
                before_expected,
                after_expected,
                {added_name},
                root=copied_root,
            )
            self.assert_ready(after_expected, after_expected, root=copied_root)


# gh pr checks buckets: pass, fail, pending, skipping, cancel.
# fail / pending / cancel already leave before the ready sentence; skipping
# must not fall through it. The three names are a fixture, not the live tree.
SKIP_FIXTURE = ("gates (a)", "gates (b)", "verify")
SKIPPED_EXPECTED = "gates (b)"


def _row(*, pass_n, skipping_n, names, extra_bucket=None):
    checks = {
        "pass": pass_n,
        "skipping": skipping_n,
        "names": list(names),
    }
    if extra_bucket:
        checks.update(extra_bucket)
    return {
        "checks": checks,
        "unresolved": 0,
        "review": "current",
        "merge_state": "CLEAN",
    }


def _named_skip_row(expected, skip_name, extra=None):
    """One skipped name, with per-name buckets so attribution is possible."""
    names = sorted(expected)
    buckets = {name: "pass" for name in expected}
    if extra is not None:
        names = names + [extra]
        buckets[extra] = "pass"
    buckets[skip_name] = "skipping"
    pass_n = sum(1 for name in names if buckets[name] == "pass")
    skip_n = sum(1 for name in names if buckets[name] == "skipping")
    row = _row(pass_n=pass_n, skipping_n=skip_n, names=names)
    row["checks"]["runs"] = [
        {"name": name, "bucket": buckets[name]} for name in names
    ]
    planted = [run["name"] for run in row["checks"]["runs"] if run["bucket"] == "skipping"]
    if planted != [skip_name]:
        raise AssertionError(f"skip plant did not land: {planted}")
    return row


class BlockingDoesNotTreatASkippedCheckAsPassed(unittest.TestCase):
    """A skipped expected check has reported; it has not passed."""

    @classmethod
    def setUpClass(cls):
        cls.overview = load_overview(ROOT, "pr_overview_skipping_under_test")
        cls.live_expected = expected_check_names(ROOT)
        cls.live_registry = check_registry(ROOT)
        if "dev: verify" not in cls.live_expected:
            raise AssertionError("live expected set is missing the verify job")

    def _verdict(self, row, expected=None):
        expected = set(SKIP_FIXTURE) if expected is None else expected
        return self.overview.blocking(row, expected=expected)

    def test_a_skipped_expected_check_is_not_ready(self):
        self.assertIn(SKIPPED_EXPECTED, SKIP_FIXTURE)
        row = _row(pass_n=2, skipping_n=1, names=SKIP_FIXTURE)
        self.assertEqual(len(row["checks"]["names"]), 3)
        self.assertEqual(row["checks"]["pass"] + row["checks"]["skipping"], 3)
        self.assertNotIn("runs", row["checks"])

        verdict = self._verdict(row)

        assert_not_ready_due_to_skipping(self, verdict)

    def test_every_expected_check_skipping_is_not_ready(self):
        row = _row(pass_n=0, skipping_n=3, names=SKIP_FIXTURE)
        self.assertEqual(len(row["checks"]["names"]), 3)
        self.assertEqual(row["checks"]["skipping"], 3)
        self.assertNotIn("runs", row["checks"])

        verdict = self._verdict(row)

        assert_not_ready_due_to_skipping(self, verdict)

    def test_an_unrelated_pass_cannot_stand_in_for_a_skipped_expected_check(self):
        """Same counts as 'extra skipped, all expected passed'; the skipped
        name is the expected one. Distinguishing those needs per-name buckets.
        """
        unrelated = "unrelated-check"
        names = list(SKIP_FIXTURE) + [unrelated]
        row = _row(pass_n=3, skipping_n=1, names=names)
        row["checks"]["runs"] = [
            {
                "name": SKIP_FIXTURE[0],
                "bucket": "pass",
            },
            {"name": SKIPPED_EXPECTED, "bucket": "skipping"},
            {"name": SKIP_FIXTURE[2], "bucket": "pass"},
            {"name": unrelated, "bucket": "pass"},
        ]
        self.assertEqual(len(row["checks"]["names"]), 4)
        self.assertEqual(row["checks"]["pass"], len(SKIP_FIXTURE))
        self.assertIn(SKIPPED_EXPECTED, row["checks"]["names"])
        self.assertIn(unrelated, row["checks"]["names"])
        planted = [
            run["name"] for run in row["checks"]["runs"] if run["bucket"] == "skipping"
        ]
        self.assertEqual(planted, [SKIPPED_EXPECTED])

        verdict = self._verdict(row)

        assert_skipped_expected(self, verdict, {SKIPPED_EXPECTED})

    def test_skipping_a_named_expected_check_is_not_ready_for_each_kind(self):
        """Planted-name skip handling is not enough: a workflow job, a
        matrix job, and an extra name must each be classified by *that*
        name's bucket.
        """
        expected = self.live_expected
        matrix = one_matrix_check(expected, self.live_registry)
        workflow = "dev: verify"
        extra = "unrelated-extra"
        self.assertIn(workflow, expected)
        self.assertIn(matrix, expected)
        self.assertNotEqual(matrix, "dev: gates (lint)")
        self.assertNotEqual(matrix, "gates (b)")
        self.assertNotIn(extra, expected)

        cases = (
            ("workflow-job", workflow, None, False),
            ("matrix-job", matrix, None, False),
            ("extra-name", extra, extra, True),
        )
        for label, skip_name, extra_name, ready in cases:
            with self.subTest(kind=label, skip_name=skip_name):
                row = _named_skip_row(expected, skip_name, extra=extra_name)
                verdict = self._verdict(row, expected=expected)
                if ready:
                    self.assertEqual(
                        verdict,
                        f"ready to merge — all {len(expected)} expected check(s) passed",
                        verdict,
                    )
                else:
                    assert_skipped_expected(self, verdict, {skip_name})


if __name__ == "__main__":
    unittest.main()
