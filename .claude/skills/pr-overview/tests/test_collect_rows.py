"""A check-less or unreadable PR is a row, not a board-wide refusal.

Defect 10: gh pr checks exiting non-zero with empty stdout and
"no checks reported" is the real answer (no checks), not Unavailable.
One PR's forge error is a cannot-tell row. The overview refuses only
when it could read none of the open PRs.

The fake gh is a PATH stub in the shape of
ops/devlane/hooks/tests/gh_stub.py and the neighboring
test_pr_head_expected.GH_STUB, with per-PR checks errors injected.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_pr_head_expected import (
    GH_STUB,
    REPO,
    ROOT,
    load_overview,
    non_git_cwd,
    ready_pr,
)

BASE_GH_STUB = GH_STUB

NO_CHECKS_STDERR = "no checks reported on the 'lane/workflow' branch"
AUTH_STDERR = "gh: authentication failed"

CHECKS_OLD = """if "pr" in args and "checks" in args:
    number = None
    after = args[args.index("checks") + 1 :]
    for a in after:
        if a.isdigit():
            number = a
            break
    if number is None:
        sys.stderr.write("pr checks: no number\\n")
        sys.exit(2)
    pr = pr_by_number(number)
    json.dump(
        [{"name": c["name"], "bucket": c["bucket"]} for c in pr["checks"]],
        sys.stdout,
    )
    sys.exit(0)
"""

CHECKS_NEW = """if "pr" in args and "checks" in args:
    number = None
    after = args[args.index("checks") + 1 :]
    for a in after:
        if a.isdigit():
            number = a
            break
    if number is None:
        sys.stderr.write("pr checks: no number\\n")
        sys.exit(2)
    errors = state.get("check_errors") or {}
    if str(number) in errors:
        err = errors[str(number)]
        stderr = err.get("stderr") or ""
        if stderr and not stderr.endswith("\\n"):
            stderr = stderr + "\\n"
        sys.stderr.write(stderr)
        sys.stdout.write(err.get("stdout") or "")
        sys.exit(int(err["rc"]))
    pr = pr_by_number(number)
    json.dump(
        [{"name": c["name"], "bucket": c["bucket"]} for c in pr["checks"]],
        sys.stdout,
    )
    sys.exit(0)
"""

REPO_VIEW = """if "repo" in args and "view" in args:
    repo = state.get("repo") or "uscient/agentscient"
    json.dump({"nameWithOwner": repo}, sys.stdout)
    sys.exit(0)

"""

GRAPHQL_OLD = '''if "api" in args and "graphql" in args:
    number = None
    for i, a in enumerate(args):
        if a.startswith("pr="):
            number = a.split("=", 1)[1]
        if a == "-F" and i + 1 < len(args) and args[i + 1].startswith("pr="):
            number = args[i + 1].split("=", 1)[1]
    if number is None:
        sys.stderr.write("graphql: no pr=\\n")
        sys.exit(2)
    pr = pr_by_number(number)
'''

GRAPHQL_NEW = '''if "api" in args and "graphql" in args:
    number = None
    for i, a in enumerate(args):
        if a.startswith("pr="):
            number = a.split("=", 1)[1]
        if a == "-F" and i + 1 < len(args) and args[i + 1].startswith("pr="):
            number = args[i + 1].split("=", 1)[1]
    if number is None:
        sys.stderr.write("graphql: no pr=\\n")
        sys.exit(2)
    errors = state.get("review_errors") or {}
    if str(number) in errors:
        err = errors[str(number)]
        stderr = err.get("stderr") or ""
        if stderr and not stderr.endswith("\\n"):
            stderr = stderr + "\\n"
        sys.stderr.write(stderr)
        sys.stdout.write(err.get("stdout") or "")
        sys.exit(int(err["rc"]))
    pr = pr_by_number(number)
'''

if CHECKS_OLD not in BASE_GH_STUB:
    raise AssertionError("plant: neighboring GH_STUB checks block moved")
ROW_GH_STUB = BASE_GH_STUB.replace(CHECKS_OLD, CHECKS_NEW, 1)
if ROW_GH_STUB == BASE_GH_STUB:
    raise AssertionError("plant: checks error hook did not land in GH_STUB")
if "check_errors" not in ROW_GH_STUB:
    raise AssertionError("plant: check_errors missing from GH_STUB")
if ROW_GH_STUB.count("if \"pr\" in args and \"checks\" in args:") != 1:
    raise AssertionError("plant: checks handler count drifted")
if GRAPHQL_OLD not in ROW_GH_STUB:
    raise AssertionError("plant: neighboring GH_STUB graphql block moved")
ROW_GH_STUB = ROW_GH_STUB.replace(GRAPHQL_OLD, GRAPHQL_NEW, 1)
if "review_errors" not in ROW_GH_STUB:
    raise AssertionError("plant: review_errors missing from GH_STUB")
MARKER = 'args = sys.argv[1:]\n'
if MARKER not in ROW_GH_STUB:
    raise AssertionError("plant: args assignment missing from GH_STUB")
ROW_GH_STUB = ROW_GH_STUB.replace(MARKER, MARKER + REPO_VIEW, 1)
if "nameWithOwner" not in ROW_GH_STUB:
    raise AssertionError("plant: repo view hook did not land in GH_STUB")


def snapshot_live_derivation() -> dict[str, str]:
    """Files the overview fetches for a PR head, from this tree.

    This snapshot's workflows are not the ci-dev.yml pair the neighboring
    head-tree fixture archives, so those helpers cannot run here.
    """
    out: dict[str, str] = {}
    skip_names = {"__pycache__", "wf.db"}
    for rel in (".github/workflows", "ops/devlane/workflow"):
        root = ROOT / rel
        if not root.exists():
            raise AssertionError(f"live tree missing {rel}")
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_names or part.endswith(".pyc") for part in path.parts):
                continue
            key = str(path.relative_to(ROOT))
            try:
                out[key] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise AssertionError(f"{key} is not utf-8 ({exc})") from exc
    if ".github/workflows/ci.yml" not in out:
        raise AssertionError("live snapshot missing .github/workflows/ci.yml")
    if "ops/devlane/workflow/gate-kinds/artifact.json" not in out:
        raise AssertionError("live snapshot missing artifact.json")
    return out


def no_checks_error() -> dict:
    return {"rc": 1, "stderr": NO_CHECKS_STDERR, "stdout": ""}


def auth_error() -> dict:
    return {"rc": 1, "stderr": AUTH_STDERR, "stdout": ""}


@contextlib.contextmanager
def gh_on_path(
    prs: list[dict],
    trees: dict[str, dict[str, str]],
    check_errors: dict | None = None,
    review_errors: dict | None = None,
):
    tmp = Path(tempfile.mkdtemp(prefix="pr-overview-rows-gh-"))
    state = tmp / "state.json"
    stub = tmp / "gh"
    missing = [pr["headRefOid"] for pr in prs if pr["headRefOid"] not in trees]
    if missing:
        raise AssertionError(f"gh stub has no tree for head(s) {missing}")
    payload = {
        "prs": prs,
        "trees": trees,
        "check_errors": {str(k): v for k, v in (check_errors or {}).items()},
        "review_errors": {str(k): v for k, v in (review_errors or {}).items()},
        "repo": REPO,
    }
    state.write_text(json.dumps(payload), encoding="utf-8")
    landed_state = json.loads(state.read_text(encoding="utf-8"))
    if landed_state["check_errors"] != payload["check_errors"]:
        raise AssertionError("plant: check_errors did not land in stub state")
    if landed_state["review_errors"] != payload["review_errors"]:
        raise AssertionError("plant: review_errors did not land in stub state")
    stub.write_text(ROW_GH_STUB, encoding="utf-8")
    if "check_errors" not in stub.read_text(encoding="utf-8"):
        raise AssertionError("plant: GH_STUB write dropped check_errors")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    old_path = os.environ["PATH"]
    old_state = os.environ.get("GH_STUB_STATE")
    os.environ["PATH"] = str(tmp) + os.pathsep + old_path
    os.environ["GH_STUB_STATE"] = str(state)
    try:
        which = shutil.which("gh")
        if which is None or Path(which).resolve() != stub.resolve():
            raise AssertionError(f"stub gh not first on PATH: {which}")
        yield tmp
    finally:
        os.environ["PATH"] = old_path
        if old_state is None:
            os.environ.pop("GH_STUB_STATE", None)
        else:
            os.environ["GH_STUB_STATE"] = old_state
        shutil.rmtree(tmp, ignore_errors=True)


ROW_HEADER = re.compile(r"^#(\d+)\b")


def row_headers(rendered: str) -> list[int]:
    """Distinct PR row blocks, in render order. A line that merely
    mentions two numbers is not two rows."""
    found = []
    for line in rendered.splitlines():
        match = ROW_HEADER.match(line.lstrip())
        if match:
            found.append(int(match.group(1)))
    return found


def pr_block(rendered: str, number: int) -> list[str]:
    """Lines of the rendered block whose header is this PR number."""
    lines = rendered.splitlines()
    start = None
    for i, line in enumerate(lines):
        match = ROW_HEADER.match(line.lstrip())
        if match and int(match.group(1)) == number:
            start = i
            break
    if start is None:
        raise AssertionError(
            f"no rendered block header is #{number}:\n{rendered}"
        )
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if ROW_HEADER.match(lines[i].lstrip()):
            end = i
            break
    return lines[start:end]


def checks_line_for(rendered: str, number: int) -> str:
    block = pr_block(rendered, number)
    for line in block:
        if "checks:" in line:
            return line
    raise AssertionError(
        f"no checks: line in #{number} block {block!r} of:\n{rendered}"
    )


def blocking_line_for(rendered: str, number: int) -> str:
    block = pr_block(rendered, number)
    for line in block:
        stripped = line.lstrip()
        if stripped.startswith(">>"):
            return stripped
    raise AssertionError(
        f"no >> line for #{number} in:\n{rendered}"
    )


HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
OK_CHECK = "ci"


class CollectRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overview = load_overview(ROOT, "pr_overview_collect_rows")
        files = snapshot_live_derivation()
        if not files:
            raise AssertionError("live derivation snapshot is empty")
        cls.trees = {HEAD_SHA: files}
        if HEAD_SHA not in cls.trees:
            raise AssertionError("plant: trees missing HEAD_SHA")
        if ".github/workflows/ci.yml" not in cls.trees[HEAD_SHA]:
            raise AssertionError("plant: tree dropped ci.yml")

    def pair(self, *, empty_checks: bool = False) -> list[dict]:
        first_names = [] if empty_checks else [OK_CHECK]
        prs = [
            ready_pr(
                10,
                "workflow without checks",
                "lane/workflow",
                HEAD_SHA,
                first_names,
            ),
            ready_pr(
                11,
                "workflow with checks",
                "lane/ok",
                HEAD_SHA,
                [OK_CHECK],
            ),
        ]
        if empty_checks and prs[0]["checks"]:
            raise AssertionError("plant: PR 10 still has checks")
        return prs

    def run_board(self, prs, check_errors, review_errors=None):
        """Invoke main() against the PATH stub. expected_checks is pinned.

        This snapshot's workflows are ci.yml, not the ci-dev.yml pair
        derivation requires, so the live expected_checks path cannot
        succeed here. The defect under test is buckets/collect, not
        derivation.
        """
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ["pr_overview.py", "--repo", REPO]
        code = 0
        with gh_on_path(
            prs, self.trees,
            check_errors=check_errors,
            review_errors=review_errors,
        ), non_git_cwd():
            with mock.patch.object(
                self.overview,
                "expected_checks",
                return_value=frozenset({OK_CHECK}),
            ), mock.patch.object(sys, "argv", argv), mock.patch.object(
                self.overview.sys, "argv", argv
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ):
                try:
                    returned = self.overview.main()
                    code = 0 if returned is None else int(returned)
                except SystemExit as exc:
                    code = 0 if exc.code is None else int(exc.code)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_a_pr_with_no_checks_reported_is_a_row_with_no_checks(self):
        prs = self.pair(empty_checks=True)
        self.assertEqual(len(prs), 2)
        self.assertEqual(prs[0]["checks"], [])
        self.assertTrue(prs[1]["checks"])
        errors = {"10": no_checks_error()}
        self.assertIn("no checks reported", errors["10"]["stderr"])
        self.assertEqual(errors["10"]["stdout"], "")
        self.assertNotEqual(errors["10"]["rc"], 0)
        code, stdout, stderr = self.run_board(prs, errors)
        self.assertEqual(code, 0, stderr or stdout)
        self.assertEqual(row_headers(stdout), [10, 11], stdout)
        self.assertIn("checks: no checks", checks_line_for(stdout, 10))
        block10 = pr_block(stdout, 10)
        self.assertFalse(
            any(ROW_HEADER.match(ln.lstrip()) and ln.lstrip().startswith("#11")
                for ln in block10[1:]),
            f"#10's block must not also be #11: {block10!r}",
        )

    def test_one_unreadable_pr_is_a_cannot_tell_row_not_a_refusal(self):
        prs = self.pair()
        self.assertEqual(len(prs), 2)
        errors = {"10": auth_error()}
        self.assertIn("authentication", errors["10"]["stderr"].lower())
        code, stdout, stderr = self.run_board(prs, errors)
        self.assertEqual(code, 0, stderr or stdout)
        self.assertEqual(row_headers(stdout), [10, 11], stdout)
        blocking = blocking_line_for(stdout, 10)
        self.assertTrue(
            blocking.startswith(">> cannot tell"),
            blocking,
        )
        self.assertIn("checks: unreadable", checks_line_for(stdout, 10))

    def test_every_pr_unreadable_refuses_naming_the_count(self):
        prs = self.pair()
        self.assertEqual(len(prs), 2)
        errors = {"10": auth_error(), "11": auth_error()}
        self.assertEqual(len(errors), 2)
        code, stdout, stderr = self.run_board(prs, errors)
        self.assertEqual(code, 2, stderr or stdout)
        self.assertIn("none of 2", stderr)
        self.assertRegex(
            stderr,
            r"first:.*authentication failed",
            f"refusal names the first underlying error: {stderr!r}",
        )
        self.assertEqual(stdout.strip(), "")

    def test_one_unreadable_review_page_is_a_cannot_tell_row_not_a_refusal(self):
        """Adversarial finding 4: review_pages raising is one PR's
        cannot-tell row, not a board-wide exit 2."""
        prs = self.pair()
        self.assertEqual(len(prs), 2)
        errors = {"10": auth_error()}
        self.assertIn("authentication", errors["10"]["stderr"].lower())
        code, stdout, stderr = self.run_board(
            prs, check_errors=None, review_errors=errors,
        )
        self.assertEqual(code, 0, stderr or stdout)
        self.assertEqual(row_headers(stdout), [10, 11], stdout)
        blocking = blocking_line_for(stdout, 10)
        self.assertTrue(
            blocking.startswith(">> cannot tell"),
            blocking,
        )
        self.assertIn("checks: unreadable", checks_line_for(stdout, 10))


if __name__ == "__main__":
    unittest.main()
