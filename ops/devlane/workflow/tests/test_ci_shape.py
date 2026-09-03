"""The CI workflows' shape, asserted rather than eyeballed (PLAN §7).

Two things here are easy to get wrong silently: a required check that a path
filter skips never reports and blocks the pull request forever, and a matrix
that is hand-listed while a `--checks` command sits unused beside it.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# isort: off
# support must import FIRST: it wires sys.path so canonical (a
# workflow module) resolves at all. Both live inside the guard so a
# sorter cannot hoist canonical out again — that exact fix broke
# direct collection once already.
import support
import canonical
# isort: on

_CHECKS = str(support.WF_DIR / "checks")
if _CHECKS not in sys.path:
    sys.path.insert(0, _CHECKS)
import ci_contexts  # noqa: E402

REPO = support.WF_DIR.parent.parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
# 2026-08-25: wf-verify.yml -> ci-dev.yml (unfiltered verifier,
# discovery, and gates); wf-tests.yml -> ci-dev-apps.yml (unfiltered
# workflow shards and per-app jobs). Job names are `{lane}: {subject}`;
# both workflow files are named `CI`. The merge box shows reviewers
# `CI / {job} ({event})`, but that is presentation, not the ruleset
# context: a required-check rule would list the job check-run name,
# with matrix values in parentheses. A bare WF: was read as "the
# workflow app" while covering every mini app (PR #52).
DEV_YML = WORKFLOWS / "ci-dev.yml"
APPS_YML = WORKFLOWS / "ci-dev-apps.yml"
WORKFLOW_FILES = (DEV_YML, APPS_YML)

# One job per mini app, in the include-matrix order. Dropping a name
# here is how that app silently leaves CI.
APP_JOBS = (
    "telemetry",
    "task",
    "dispatch",
    "hooks",
    "fixtures",
    "contracts",
    "conductor",
    "capabilities",
    "symfony",
    "harness",
)

# YAML job `name:` values. GitHub then composes
# `{workflow} / {job} ({event})`. Pinning only the job name stays
# green through a workflow rename that changes every required-check
# context; pinning only the composed string hides a job rename that
# did not move the workflow title. Both halves are load-bearing.
WORKFLOW_NAME = "CI"
EVENTS = ("pull_request", "push")
JOB_VERIFY = "dev: verify"
JOB_DISCOVER = "dev: discover"
JOB_GATES = "dev: gates"
JOB_WORKFLOW = "dev: workflow"
JOB_APP = "dev: ${{ matrix.app }}"

# Observed check-run names on 12fb1d3 (CI-OBSERVED.md), sorted, plus
# `dev: gates (doc-covers)` registered in stage 2 and `dev: dispatch`
# added with the app in PR #61 (the §Dispatch launcher split out of
# task). U2-A4: `dev: gates (anatomy)` and `dev: gates (registry-vet)`
# join through the registry; the pin learns them. This project adds
# three app rows — conductor, capabilities, symfony — the day the lane
# crossed (2026-09-03). The derived list
# below is what the branch ruleset WOULD require; additions are
# assertions until a GitHub run reports them.
# These are observed, not derived, so a derivation bug cannot rewrite
# the pin. Bare `dev: gates` and `dev: workflow` are not in the list.
PINNED_CONTEXTS = (
    "dev: capabilities",
    "dev: conductor",
    "dev: contracts",
    "dev: discover",
    "dev: dispatch",
    "dev: fixtures",
    "dev: gates (anatomy)",
    "dev: gates (commit-trailers)",
    "dev: gates (doc-commands)",
    "dev: gates (doc-covers)",
    "dev: gates (imports)",
    "dev: gates (lint)",
    "dev: gates (registry-vet)",
    "dev: gates (secret-scan)",
    "dev: gates (vocabulary-wall)",
    "dev: harness",
    "dev: hooks",
    "dev: symfony",
    "dev: task",
    "dev: telemetry",
    "dev: verify",
    "dev: workflow (0)",
    "dev: workflow (1)",
    "dev: workflow (2)",
)

CONTEXTS_PY = support.WF_DIR / "checks" / "ci_contexts.py"
JOB_NAME = ci_contexts.JOB_NAME
app_matrix_entries = ci_contexts.app_matrix_entries

DISCOVERY_PROBE = r"""
import json
import sys
import unittest


class RecordingLoader(unittest.TestLoader):
    def __init__(self):
        super().__init__()
        self.modules = []

    def loadTestsFromModule(self, module, *args, **kwargs):
        self.modules.append(module.__name__)
        return super().loadTestsFromModule(module, *args, **kwargs)


loader = RecordingLoader()
start = sys.argv[1]
loader.discover(start_dir=start, pattern="test*.py", top_level_dir=start)
if loader.errors:
    print("\n\n".join(loader.errors), file=sys.stderr)
    raise SystemExit(1)
print("WF_DISCOVERED=" + json.dumps(sorted(set(loader.modules))))
"""


def section(text, job):
    """The block of a workflow file belonging to one job name."""
    start = text.index(f'name: "{job}"')
    rest = text[start:]
    nxt = re.search(r"\n  [a-z-]+:\n", rest)
    return rest[: nxt.start()] if nxt else rest


_RUN_KEY = re.compile(r"^([ \t]+)(?:-\s+)?run:\s*(.*)$")
_BLOCK_SCALAR = re.compile(r"^([|>][+-]?)(?:[ \t].*)?$")
_PIP_INSTALL = re.compile(r"\b(pipx|pip) install\b")
_PIP_PIN = re.compile(r"[<>=]=?\d")
_FETCH = re.compile(r"\b(curl|wget)\b")
_FETCH_PIN = re.compile(r"v\d+\.\d+|\d+\.\d+\.\d+")
_SHA256_HEX = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])"
)
_SHA256SUM = re.compile(r"\bsha256sum\b")


def gates_run_bodies(gates_text):
    """Unfold every `run:` step body from a job section.

    A `run: |` marker is not the command. The current pipx-only loop
    matched that marker and never saw the fetch it wrapped — U2-A4
    is the second form, so the body has to be the unit of judgment.
    """
    lines = gates_text.splitlines()
    bodies = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        if raw.lstrip().startswith("#"):
            i += 1
            continue
        match = _RUN_KEY.match(raw)
        if not match:
            i += 1
            continue
        indent, rest = match.group(1), match.group(2).rstrip()
        block = _BLOCK_SCALAR.match(rest)
        if block is None:
            bodies.append(rest)
            i += 1
            continue
        collected = []
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if nxt.strip() == "":
                collected.append("")
                i += 1
                continue
            if nxt.lstrip().startswith("#"):
                i += 1
                continue
            nxt_indent = len(nxt) - len(nxt.lstrip(" \t"))
            if nxt_indent > len(indent):
                collected.append(nxt.strip())
                i += 1
                continue
            break
        bodies.append("\n".join(collected))
    return bodies


def gates_install_problems(gates_text):
    """Refusals against the two sanctioned gates-job install forms.

    Form 1: pipx|pip install, version-pinned.
    Form 2: a release fetch that is version-pinned AND sha256-verified
    (a 64-hex digest checked with sha256sum). The wf.py evaluating
    step is not an install. Nothing else may share the job.
    """
    bodies = gates_run_bodies(gates_text)
    problems = []
    if not bodies:
        problems.append("gates job has no run: steps")
        return problems
    for body in bodies:
        compact = " ".join(body.split())
        if "wf.py" in body:
            continue
        if _PIP_INSTALL.search(body):
            if not _PIP_PIN.search(body):
                problems.append(f"unpinned pip/pipx install: {compact}")
            continue
        if _FETCH.search(body):
            if not _FETCH_PIN.search(body):
                problems.append(f"unpinned fetch: {compact}")
            verified = (
                _SHA256_HEX.search(body) is not None
                and _SHA256SUM.search(body) is not None
            )
            if not verified:
                problems.append(
                    f"unverified fetch (no sha256 digest): {compact}"
                )
            continue
        problems.append(
            f"non-install step may not share this job: {compact}"
        )
    return problems


def _pipx_and_wf_gates():
    return (
        '    name: "dev: gates"\n'
        "    steps:\n"
        "      - run: pipx install 'ruff>=0.14,<0.15'\n"
        "      - run: python3 ops/devlane/workflow/wf.py check\n"
    )


def _with_run_step(gates, run_body, *, multiline=False):
    """Insert a run step ahead of the evaluating wf.py call."""
    needle = "      - run: python3 ops/devlane/workflow/wf.py check\n"
    if needle not in gates:
        raise AssertionError("wf.py run step missing from fixture")
    if multiline:
        extra = "      - run: |\n"
        for line in run_body.splitlines():
            extra += f"          {line}\n"
    else:
        extra = f"      - run: {run_body}\n"
    return gates.replace(needle, extra + needle, 1)


_SANCTIONED_DIGEST = "0123456789abcdef" * 4
_SANCTIONED_FETCH = (
    "curl -fsSL https://example.invalid/cue/v0.14.1/cue.tar.gz "
    "-o cue.tgz\n"
    f"echo '{_SANCTIONED_DIGEST}  cue.tgz' | sha256sum -c -\n"
    "tar -xzf cue.tgz"
)


def workflow_display_name(text):
    """The top-level workflow `name:` GitHub uses as the left half."""
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("name:"):
            value = line.split(":", 1)[1].strip()
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                return value[1:-1]
            return value
        if line.startswith("jobs:"):
            break
    raise ValueError("workflow file has no top-level name:")


def workflow_events(text):
    """Trigger events that produce a check run (`on:` keys before jobs:)."""
    head = text.split("jobs:", 1)[0]
    return tuple(
        event
        for event in EVENTS
        if re.search(rf"(?m)^  {event}:", head)
    )


PATH_FILTER_KEY = re.compile(r"(?m)^[ \t]+paths(?:-ignore)?:")
RETIRED_CHECK_NAME = re.compile(r"WF:(verify|tests|gates)|CI:dev:")


def trigger_block(head, trigger):
    marker = f"  {trigger}:"
    start = head.index(marker)
    rest = head[start + len(marker):]
    nxt = re.search(r"\n  \w+:", rest)
    return rest[: nxt.start()] if nxt else rest


def trigger_active(head, trigger):
    block = trigger_block(head, trigger)
    return "\n".join(
        line for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def path_filter_problems(path):
    """None if `path` has no paths:/paths-ignore: in either trigger."""
    text = Path(path).read_text(encoding="utf-8")
    head = text.split("jobs:", 1)[0]
    problems = []
    if "pull_request:" not in head:
        problems.append(f"{Path(path).name}: missing pull_request:")
    if "push:" not in head:
        problems.append(f"{Path(path).name}: missing push:")
    for trigger in ("pull_request", "push"):
        if f"  {trigger}:" not in head:
            continue
        active = trigger_active(head, trigger)
        keys = PATH_FILTER_KEY.findall(active)
        if keys:
            problems.append(
                f"{Path(path).name} {trigger} has {keys}"
            )
    return problems


def concurrency_group(text):
    match = re.search(r"(?m)^concurrency:\n((?:[ \t].*\n)+)", text)
    if not match:
        return None
    block = match.group(1)
    groups = [
        line.strip() for line in block.splitlines()
        if line.strip().startswith("group:")
    ]
    if len(groups) != 1:
        return groups
    return groups[0]


def concurrency_problems(paths):
    """Problems in the per-file concurrency keys. Names both files."""
    problems = []
    groups = []
    names = []
    for path in paths:
        path = Path(path)
        names.append(path.name)
        text = path.read_text(encoding="utf-8")
        if "concurrency:" not in text:
            problems.append(f"{path.name} has no concurrency:")
            continue
        if "cancel-in-progress: true" not in text:
            problems.append(f"{path.name} has no cancel-in-progress: true")
        group = concurrency_group(text)
        if not isinstance(group, str):
            problems.append(
                f"{path.name} wants exactly one group: under concurrency:, "
                f"found {group!r}"
            )
            continue
        if "${{ github.workflow }}" in group:
            problems.append(
                f"{path.name} group still contains ${{{{ github.workflow }}}}"
            )
        if f"group: {path.stem}-" not in group:
            problems.append(
                f"{path.name} group is not prefixed with {path.stem}-: {group}"
            )
        if "${{ github.event_name }}" not in group:
            problems.append(f"{path.name} group dropped github.event_name")
        if "${{ github.head_ref || github.sha }}" not in group:
            problems.append(
                f"{path.name} group dropped github.head_ref || github.sha"
            )
        groups.append(group)
    if len(groups) == 2 and groups[0] == groups[1]:
        problems.append(
            f"{names[0]} and {names[1]} share a concurrency group: {groups[0]}"
        )
    return problems


def mini_apps_with_tests(app_root):
    return sorted(
        child.name
        for child in Path(app_root).iterdir()
        if child.is_dir() and (child / "tests").is_dir()
    )


def undeclared_mini_apps(app_root, matrix_apps):
    named = set(matrix_apps)
    return [
        name for name in mini_apps_with_tests(app_root)
        if name != "workflow" and name not in named
    ]


def retired_hits(root, rels):
    hits = []
    for rel in rels:
        path = Path(root) / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if RETIRED_CHECK_NAME.search(line):
                hits.append(f"{rel}:{lineno}:{line}")
    return hits


def run_contexts(payload, script=CONTEXTS_PY, extra=()):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False
    ) as handle:
        json.dump(payload, handle)
        path = handle.name
    proc = subprocess.run(
        [sys.executable, str(script), path, *extra],
        capture_output=True, text=True, check=False,
    )
    Path(path).unlink(missing_ok=True)
    return proc


def sandbox_workflows(mut_dev=None, mut_apps=None):
    raw = tempfile.mkdtemp(prefix="ci-shape-ctx-")
    root = Path(raw)
    checks = root / "ops" / "devlane" / "workflow" / "checks"
    workflows = root / ".github" / "workflows"
    checks.mkdir(parents=True)
    workflows.mkdir(parents=True)
    shutil.copy(CONTEXTS_PY, checks / "ci_contexts.py")
    dev = DEV_YML.read_text(encoding="utf-8")
    apps = APPS_YML.read_text(encoding="utf-8")
    if mut_dev is not None:
        dev = mut_dev(dev)
    if mut_apps is not None:
        apps = mut_apps(apps)
    (workflows / "ci-dev.yml").write_text(dev)
    (workflows / "ci-dev-apps.yml").write_text(apps)
    return root, checks / "ci_contexts.py"


def real_checks_payload():
    return json.loads(
        subprocess.run(
            [sys.executable, str(support.WF_PY), "--json", "status", "--checks"],
            capture_output=True, text=True, check=True,
        ).stdout
    )


class PathFilters(unittest.TestCase):
    def test_no_workflow_is_path_filtered(self):
        # A required check skipped by a path filter never reports, so
        # the pull request waits on it forever. Both files, both
        # triggers, paths: and paths-ignore:.
        for path in WORKFLOW_FILES:
            problems = path_filter_problems(path)
            self.assertFalse(problems, problems)

    def test_a_paths_block_under_pull_request_fails_the_check(self):
        with tempfile.TemporaryDirectory(prefix="ci-paths-") as raw:
            copy = Path(raw) / "ci-dev-apps.yml"
            text = APPS_YML.read_text(encoding="utf-8")
            before = text.encode()
            needle = "  pull_request:\n"
            self.assertIn(needle, text)
            planted = text.replace(
                needle, needle + "    paths:\n      - 'ops/devlane/**'\n", 1
            )
            copy.write_text(planted)
            after = copy.read_bytes()
            self.assertNotEqual(after, before)
            self.assertGreater(len(after), 64)
            self.assertIn(b"name: CI", after)
            problems = path_filter_problems(copy)
            self.assertTrue(problems, "the planted paths: block was not seen")
            self.assertTrue(
                any("paths" in item for item in problems), problems
            )

    def test_the_lane_prefixed_check_names_still_exist(self):
        # Job names are `{lane}: {subject}`. The CI:<lane>:<subject>
        # scheme was retired with this rename; WF: was retired earlier
        # (PR #52). These YAML names are the job half of the composed
        # check; they are not themselves what a ruleset would list —
        # that surface is pinned next door.
        # Pinning the old CI:dev: strings would freeze the scheme this
        # change replaced.
        dev = DEV_YML.read_text()
        apps = APPS_YML.read_text()
        both = dev + apps
        for job in (JOB_VERIFY, JOB_GATES, JOB_WORKFLOW):
            self.assertIn(f'name: "{job}"', both, job)
        self.assertIn(f'name: "{JOB_DISCOVER}"', dev)
        self.assertIn(f'name: "{JOB_APP}"', apps)
        self.assertNotRegex(
            both, r'(?m)^    name: "WF:',
            "a leftover WF: job name is the prefix this rename retired",
        )
        self.assertNotRegex(
            both, r'(?m)^    name: "CI:',
            "a leftover CI:<lane>:<subject> job name is the scheme "
            "this rename retired",
        )

    def test_composed_check_names_are_the_ruleset_surface(self):
        # The ruleset surface is the check-run name (E5), not the
        # merge-box rendering. ci_contexts.py derives it; the pin is
        # the 17 names GitHub reported on 12fb1d3, plus doc-covers and
        # `dev: dispatch` (PR #61), plus anatomy and registry-vet
        # (U2-A4 — registered through the matrix, learned here).
        self.assertEqual(len(PINNED_CONTEXTS), 21)
        self.assertEqual(tuple(PINNED_CONTEXTS), tuple(sorted(PINNED_CONTEXTS)))
        self.assertNotIn("dev: gates", PINNED_CONTEXTS)
        self.assertNotIn("dev: workflow", PINNED_CONTEXTS)
        payload = real_checks_payload()
        proc = run_contexts(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(tuple(proc.stdout.splitlines()), PINNED_CONTEXTS)
        dumped = run_contexts(payload, extra=("--json",))
        self.assertEqual(dumped.returncode, 0, dumped.stderr)
        self.assertEqual(json.loads(dumped.stdout), list(PINNED_CONTEXTS))
        for path in WORKFLOW_FILES:
            text = path.read_text()
            self.assertEqual(
                workflow_display_name(text), WORKFLOW_NAME, path.name,
            )
            self.assertEqual(workflow_events(text), EVENTS, path.name)

    def test_no_job_name_is_defined_in_both_files(self):
        verify = set(JOB_NAME.findall(DEV_YML.read_text()))
        apps = set(JOB_NAME.findall(APPS_YML.read_text()))
        self.assertTrue(verify, "ci-dev.yml has no quoted job names")
        self.assertTrue(apps, "ci-dev-apps.yml has no quoted job names")
        self.assertEqual(
            verify & apps, set(),
            "a duplicated job name makes the composed check ambiguous "
            "(both workflows are named CI)",
        )

    def test_the_dev_lane_ci_is_exactly_these_files(self):
        # A leftover wf-tests.yml / wf-verify.yml would run alongside
        # the renamed files, so both the old and new jobs report.
        # ci-minutes.yml (2026-08-28) is the scheduled billing guard: it
        # runs on no pull request, adds no context, and ci_contexts.py
        # does not read it -- test_ci_minutes.py pins that shape.
        # codeql.yml is pinned by test_ci_codeql.py, not read by
        # ci_contexts.py.
        names = sorted(
            path.name for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
        self.assertEqual(
            names,
            ["ci-dev-apps.yml", "ci-dev.yml", "ci-minutes.yml", "codeql.yml"],
        )

    def _scheme_header(self):
        source = Path(__file__).read_text(encoding="utf-8")
        marker = "# 2026-08-25:"
        start = source.index(marker)
        collected = []
        seen_non_comment = False
        for line in source[start:].splitlines(keepends=True):
            stripped = line.lstrip()
            collected.append(line)
            if stripped and not stripped.startswith("#"):
                seen_non_comment = True
                break
        header = "".join(collected)
        self.assertTrue(header.startswith(marker), header[:80])
        self.assertTrue(
            seen_non_comment,
            "header never reached a non-comment line after the marker",
        )
        self.assertIn("ci-dev.yml", header)
        self.assertIn("ci-dev-apps.yml", header)
        return header

    def test_the_scheme_header_does_not_claim_path_filtered_apps(self):
        # A comment is not a check. ci-dev-apps.yml is unfiltered;
        # PathFilters above asserts that. The header still says
        # "path-filtered per-app jobs".
        header = self._scheme_header()
        self.assertFalse(path_filter_problems(APPS_YML), APPS_YML)
        self.assertNotIn(
            "path-filtered per-app jobs",
            header,
            "the header describes ci-dev-apps.yml as path-filtered; "
            "the live file and PathFilters both say it is not",
        )

    # Retired 2026-08-26 (Claude Fable 5, on the header ruling; owner
    # ratifies): Grok's
    # test_the_scheme_header_does_not_name_merge_box_rendering_as_the_pin
    # stood here. It was named and messaged for one property -- the
    # header must not call the merge-box rendering the ruleset surface
    # -- and asserted a different one: the literal `CI / {job} ({event})`
    # never appears in the header. Those diverge on exactly the header
    # above, which names the rendering in order to deny it is the
    # ruleset context (the wording ops/guide/dev-lane.md also uses),
    # while a paraphrase of the false claim would have passed. No
    # truthful header can turn it green, and a permanently red
    # `dev: workflow (1)` guards nothing. The property it stood for is
    # asserted executably by
    # test_composed_check_names_are_the_ruleset_surface above:
    # PINNED_CONTEXTS equals the derived check-run list, 21 bare job
    # names, none of them `CI / ...`. Its sibling
    # test_the_scheme_header_does_not_claim_path_filtered_apps is left
    # as found: a truthful edit discharged it, and it was not ruled on.


class ExpectedContexts(unittest.TestCase):
    """1.3 plants: each mutation is on a copy; the live files are untouched."""

    def sandbox(self, mut_dev=None, mut_apps=None):
        root, script = sandbox_workflows(mut_dev=mut_dev, mut_apps=mut_apps)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root, script

    def prove_landed(self, path, before, marker):
        after = path.read_bytes()
        self.assertNotEqual(after, before)
        self.assertGreater(len(after), 64, path)
        self.assertIn(marker, after)

    def test_a_new_include_app_adds_only_that_context(self):
        before = APPS_YML.read_bytes()

        def mut(text):
            needle = "          - app: telemetry\n"
            self.assertIn(needle, text)
            extra = (
                "          - app: newapp\n"
                "            cmd: python3 -m unittest discover "
                "ops/devlane/newapp/tests -v\n"
            )
            return text.replace(needle, extra + needle, 1)

        root, script = self.sandbox(mut_apps=mut)
        planted = root / ".github" / "workflows" / "ci-dev-apps.yml"
        self.prove_landed(planted, before, b"- app: newapp")
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = proc.stdout.splitlines()
        self.assertIn("dev: newapp", got)
        self.assertEqual(
            sorted(c for c in got if c != "dev: newapp"),
            list(PINNED_CONTEXTS),
        )

    def test_dropping_a_shard_drops_that_context(self):
        before = APPS_YML.read_bytes()

        def mut(text):
            needle = "shard: [0, 1, 2]"
            self.assertIn(needle, text)
            return text.replace(needle, "shard: [0, 1]", 1)

        root, script = self.sandbox(mut_apps=mut)
        planted = root / ".github" / "workflows" / "ci-dev-apps.yml"
        self.prove_landed(planted, before, b"shard: [0, 1]")
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = proc.stdout.splitlines()
        self.assertNotIn("dev: workflow (2)", got)
        self.assertIn("dev: workflow (0)", got)
        self.assertIn("dev: workflow (1)", got)

    def test_a_registry_without_lint_drops_that_gate_context(self):
        payload = real_checks_payload()
        self.assertIn("lint", payload["ci_matrix"])
        payload["ci_matrix"] = [
            name for name in payload["ci_matrix"] if name != "lint"
        ]
        proc = run_contexts(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = proc.stdout.splitlines()
        self.assertNotIn("dev: gates (lint)", got)
        self.assertIn("dev: gates (imports)", got)

    def test_removing_the_verify_name_refuses_with_empty_stdout(self):
        before = DEV_YML.read_bytes()

        def mut(text):
            needle = '    name: "dev: verify"\n'
            self.assertIn(needle, text)
            return text.replace(needle, "", 1)

        root, script = self.sandbox(mut_dev=mut)
        planted = root / ".github" / "workflows" / "ci-dev.yml"
        self.prove_landed(planted, before, b"  verify:\n")
        self.assertNotIn(b'name: "dev: verify"', planted.read_bytes())
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("ci-dev.yml", proc.stderr)
        self.assertIn("verify", proc.stderr)

    def test_removing_the_gates_name_refuses_with_empty_stdout(self):
        before = DEV_YML.read_bytes()

        def mut(text):
            needle = '    name: "dev: gates"\n'
            self.assertIn(needle, text)
            return text.replace(needle, "", 1)

        root, script = self.sandbox(mut_dev=mut)
        planted = root / ".github" / "workflows" / "ci-dev.yml"
        self.prove_landed(planted, before, b"  gates:\n")
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("ci-dev.yml", proc.stderr)
        self.assertIn("gates", proc.stderr)

    def test_an_app_name_without_the_expression_refuses(self):
        before = APPS_YML.read_bytes()

        def mut(text):
            needle = '    name: "dev: ${{ matrix.app }}"\n'
            self.assertIn(needle, text)
            return text.replace(needle, '    name: "dev: apps"\n', 1)

        root, script = self.sandbox(mut_apps=mut)
        planted = root / ".github" / "workflows" / "ci-dev-apps.yml"
        self.prove_landed(planted, before, b'name: "dev: apps"')
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("app", proc.stderr)

    def test_a_sixth_job_refuses_naming_the_unknown_id(self):
        before = DEV_YML.read_bytes()

        def mut(text):
            self.assertIn("\njobs:\n", text)
            return text.replace(
                "\njobs:\n",
                '\njobs:\n  extra:\n    name: "dev: extra"\n',
                1,
            )

        root, script = self.sandbox(mut_dev=mut)
        planted = root / ".github" / "workflows" / "ci-dev.yml"
        self.prove_landed(planted, before, b"  extra:\n")
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("extra", proc.stderr)

    def test_an_empty_ci_matrix_refuses(self):
        proc = run_contexts({"ci_matrix": []})
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("ci_matrix", proc.stderr)


class DerivedMatrix(unittest.TestCase):
    def test_the_matrix_is_derived_and_not_hand_listed(self):
        gates = section(DEV_YML.read_text(), JOB_GATES)
        self.assertIn("fromJSON(needs.discover.outputs.matrix)", gates)
        self.assertNotRegex(
            gates, r"check: \[[a-z]",
            "a hand-listed matrix means the --checks command is decoration",
        )

    def test_the_gates_job_evaluates_only_through_the_cli(self):
        # The invariant is that CI never renders a verdict itself: the
        # only step that EVALUATES anything is the wf call, so a gate
        # cannot be satisfied by work done CI-side. Provisioning the
        # tool a registered command needs is not evaluating — ruff is
        # absent from the runner image, and the lint check refuses
        # rather than reporting clean without it — so an install step
        # is allowed. Two sanctioned forms (U2-A4): pipx|pip with a
        # version pin, or a version-pinned release fetch that is
        # sha256-verified. A bare pipe-to-tar is not the second form.
        gates = section(DEV_YML.read_text(), JOB_GATES)
        bodies = gates_run_bodies(gates)
        self.assertTrue(bodies, "gates job has no run: steps")
        evaluating = [body for body in bodies if "wf.py" in body]
        self.assertEqual(len(evaluating), 1, bodies)
        self.assertEqual(
            bodies[-1], evaluating[0],
            "the wf call must be the last step",
        )
        problems = gates_install_problems(gates)
        self.assertFalse(problems, problems)

    def test_an_empty_matrix_is_guarded(self):
        # An empty matrix is a hard error in Actions, not a skip.
        gates = section(DEV_YML.read_text(), JOB_GATES)
        self.assertIn("needs.discover.outputs.any == 'yes'", gates)

    def test_every_ci_flagged_check_is_registered_and_runnable(self):
        body = json.loads(subprocess.run(
            [sys.executable, str(support.WF_PY), "--json", "status", "--checks"],
            capture_output=True, text=True, check=True,
        ).stdout)
        names = {c["name"] for c in body["checks"]}
        for name in body["ci_matrix"]:
            self.assertIn(name, names)
        self.assertEqual(body["ci_matrix"], sorted(set(body["ci_matrix"])))

    def test_checks_needs_no_database(self):
        # CI runs this before init --rebuild, in a fresh checkout.
        sb = support.Sandbox()
        self.addCleanup(sb.destroy)
        self.assertFalse(sb.db.exists())
        proc = sb.wf("--json", "status", "--checks", check=0)
        self.assertFalse(sb.db.exists(), "a registry projection must open no store")
        body = json.loads(proc.stdout)
        self.assertEqual(proc.stdout.strip(), canonical.dumps(body))

    def test_a_new_ci_check_reaches_the_matrix_with_no_code_change(self):
        sb = support.Sandbox()
        self.addCleanup(sb.destroy)
        raw = canonical.loads(
            (sb.root / "gate-kinds" / "artifact.json").read_bytes())
        raw["checks"].append({
            "name": "brand-new", "class": "policy",
            "argv": ["python3", "-c", "raise SystemExit(0)"], "ci": True,
        })
        (sb.root / "gate-kinds" / "artifact.json").write_bytes(canonical.dumpb(raw))
        body = json.loads(sb.wf("--json", "status", "--checks", check=0).stdout)
        self.assertIn("brand-new", body["ci_matrix"])

    def test_a_check_without_the_flag_stays_out_and_stays_visible(self):
        body = json.loads(subprocess.run(
            [sys.executable, str(support.WF_PY), "--json", "status", "--checks"],
            capture_output=True, text=True, check=True,
        ).stdout)
        excluded = [c["name"] for c in body["checks"] if not c["ci"]]
        self.assertIn("cargo-test", excluded, "no workspace exists to test yet")
        self.assertIn("audit", excluded, "cargo-audit is not installed")
        for name in excluded:
            self.assertNotIn(name, body["ci_matrix"])
        # Excluded, but listed — an omission nobody can see is the failure
        # mode this command exists to prevent.
        self.assertIn("cargo-test", {c["name"] for c in body["checks"]})


class GatesInstallGrammar(unittest.TestCase):
    """U2-A4: two sanctioned install forms; everything else is a refusal.

    The live gates job is pinned by DerivedMatrix and is expected red
    until the code stage adds the digest. These cases are plants on a
    clean pipx+wf fixture so a live unverified fetch cannot satisfy
    them, and so they stay discriminating after that digest lands.
    """

    def _prove_plant(self, base, planted, marker):
        self.assertNotEqual(planted, base)
        self.assertGreater(len(planted), 64)
        self.assertIn(marker, planted)
        return planted

    def test_pipx_with_a_pin_is_the_first_sanctioned_form(self):
        base = _pipx_and_wf_gates()
        self.assertFalse(gates_install_problems(base), base)

    def test_a_pinned_and_sha256_verified_fetch_is_the_second_form(self):
        base = _pipx_and_wf_gates()
        planted = self._prove_plant(
            base,
            _with_run_step(base, _SANCTIONED_FETCH, multiline=True),
            _SANCTIONED_DIGEST,
        )
        self.assertIn("sha256sum", planted)
        self.assertIn("v0.14.1", planted)
        problems = gates_install_problems(planted)
        self.assertFalse(problems, problems)

    def test_an_unpinned_fetch_is_refused(self):
        base = _pipx_and_wf_gates()
        url = "https://example.invalid/cue/latest/cue.tar.gz"
        planted = self._prove_plant(
            base,
            _with_run_step(
                base,
                f"curl -fsSL {url} | tar -xz",
            ),
            url,
        )
        problems = gates_install_problems(planted)
        self.assertTrue(problems, "unpinned fetch was accepted")
        joined = " ".join(problems)
        self.assertIn("unpinned fetch", joined)
        self.assertIn(url, joined)

    def test_an_unverified_fetch_is_refused(self):
        base = _pipx_and_wf_gates()
        url = "https://example.invalid/cue/v0.14.1/cue.tar.gz"
        planted = self._prove_plant(
            base,
            _with_run_step(
                base,
                f"curl -fsSL {url} | tar -xz",
            ),
            url,
        )
        problems = gates_install_problems(planted)
        self.assertTrue(problems, "unverified fetch was accepted")
        joined = " ".join(problems)
        self.assertIn("unverified fetch", joined)
        self.assertIn("sha256", joined)
        self.assertIn(url, joined)
        self.assertNotIn("unpinned fetch", joined)

    def test_a_non_install_step_is_refused(self):
        base = _pipx_and_wf_gates()
        planted = self._prove_plant(
            base,
            _with_run_step(base, "echo not-an-install"),
            "echo not-an-install",
        )
        problems = gates_install_problems(planted)
        self.assertTrue(problems, "non-install step was accepted")
        joined = " ".join(problems)
        self.assertIn("non-install", joined)
        self.assertIn("echo not-an-install", joined)

    def test_a_fetch_with_sha256sum_but_no_digest_is_still_unverified(self):
        # Naming the tool without pinning a digest is not verification.
        base = _pipx_and_wf_gates()
        url = "https://example.invalid/cue/v0.14.1/cue.tar.gz"
        planted = self._prove_plant(
            base,
            _with_run_step(
                base,
                f"curl -fsSL {url} -o cue.tgz && sha256sum cue.tgz",
            ),
            url,
        )
        problems = gates_install_problems(planted)
        self.assertTrue(problems, "digest-free sha256sum was accepted")
        joined = " ".join(problems)
        self.assertIn("unverified fetch", joined)
        self.assertIn(url, joined)


class MatrixTransform(unittest.TestCase):
    SCRIPT = support.WF_DIR / "checks" / "ci_matrix.py"

    def run_it(self, payload):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            path = fh.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        return subprocess.run([sys.executable, str(self.SCRIPT), path],
                              capture_output=True, text=True, check=False)

    def matrix_from(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = next(
            line for line in proc.stdout.splitlines()
            if line.startswith("matrix=")
        )
        return json.loads(line.split("=", 1)[1])

    def test_emits_actions_outputs(self):
        proc = self.run_it({"ci_matrix": ["b", "a"]})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('matrix=["a", "b"]', proc.stdout)
        self.assertIn("any=yes", proc.stdout)

    def test_an_empty_registry_says_so_rather_than_emitting_an_empty_matrix(self):
        proc = self.run_it({"ci_matrix": []})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("matrix=[]", proc.stdout)
        self.assertIn("any=no", proc.stdout)

    def test_duplicates_collapse(self):
        proc = self.run_it({"ci_matrix": ["a", "a", "b"]})
        self.assertIn('matrix=["a", "b"]', proc.stdout)

    def test_a_malformed_payload_fails_loudly(self):
        proc = self.run_it({"ci_matrix": [1, 2]})
        self.assertNotEqual(proc.returncode, 0)

    def test_no_argument_is_a_usage_error(self):
        proc = subprocess.run([sys.executable, str(self.SCRIPT)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 64)

    def test_the_real_command_feeds_it(self):
        # The two halves must actually fit: run the CLI and pipe it in.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write(subprocess.run(
                [sys.executable, str(support.WF_PY), "--json", "status", "--checks"],
                capture_output=True, text=True, check=True).stdout)
            path = fh.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        proc = subprocess.run([sys.executable, str(self.SCRIPT), path],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("any=yes", proc.stdout)
        matrix = self.matrix_from(proc)
        self.assertIn("secret-scan", matrix)

    def test_the_python_gates_reach_the_transformed_matrix(self):
        # diagnostics wraps `cargo check`: until a Cargo workspace
        # exists at the repo root it must stay OUT of the matrix (a
        # permanently red WF:gates guards nothing), and the day the
        # workspace lands this pin flips WITH it — deliberately.
        body = json.loads(subprocess.run(
            [sys.executable, str(support.WF_PY), "--json", "status", "--checks"],
            capture_output=True, text=True, check=True,
        ).stdout)
        matrix = self.matrix_from(self.run_it(body))
        for name in ("secret-scan", "vocabulary-wall"):
            self.assertIn(
                name, matrix,
                f'removing "ci": true from {name} must not stay green',
            )
        repo_root = support.WF_DIR.parent.parent.parent
        if not (repo_root / "Cargo.toml").is_file():
            self.assertNotIn("diagnostics", matrix)
        else:
            # the flip is TWO-sided: the day the workspace lands,
            # diagnostics must join the matrix, not linger unflagged
            # (Grok, PR #32 review)
            self.assertIn(
                "diagnostics", matrix,
                "a Cargo workspace exists but diagnostics never"
                " joined the matrix — flip its ci flag with the"
                " workspace")

    def test_workspace_binding_refuses_a_gutted_cargo_test_registration(self):
        sb = support.Sandbox()
        self.addCleanup(sb.destroy)

        manifest = sb.dir / "Cargo.toml"
        manifest_text = (
            '[workspace]\n'
            'members = []\n'
            'resolver = "2"\n'
        )
        manifest.write_text(manifest_text, encoding="utf-8")
        self.assertEqual(manifest.read_text(encoding="utf-8"), manifest_text)
        self.assertTrue(manifest.is_file())

        registry = sb.root / "gate-kinds" / "tdd.json"
        spec = canonical.loads(registry.read_bytes())
        cargo_checks = [c for c in spec["checks"] if c["name"] == "cargo-test"]
        self.assertEqual(len(cargo_checks), 1)
        cargo_checks[0]["ci"] = True
        registry.write_bytes(canonical.dumpb(spec))
        seeded = canonical.loads(registry.read_bytes())
        self.assertIs(
            next(c for c in seeded["checks"] if c["name"] == "cargo-test")["ci"],
            True,
        )

        payload_path = sb.dir / "checks.json"
        baseline = json.loads(
            sb.wf("--json", "status", "--checks", check=0).stdout
        )
        self.assertIn("cargo-test", baseline["ci_matrix"])
        payload_path.write_text(json.dumps(baseline), encoding="utf-8")
        clean = subprocess.run(
            [sys.executable, str(sb.root / "checks" / "ci_matrix.py"),
             str(payload_path)],
            cwd=sb.dir, capture_output=True, text=True, check=False,
        )
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertIn("cargo-test", self.matrix_from(clean))

        def remove_ci(raw):
            body = canonical.loads(raw)
            check = next(c for c in body["checks"] if c["name"] == "cargo-test")
            check.pop("ci")
            return canonical.dumpb(body)

        support.plant_bytes(
            registry,
            remove_ci,
            expect="shrink",
            recognisable=lambda raw: (
                "ci" not in next(
                    c for c in canonical.loads(raw)["checks"]
                    if c["name"] == "cargo-test"
                )
            ),
        )
        gutted = canonical.loads(registry.read_bytes())
        self.assertNotIn(
            "ci",
            next(c for c in gutted["checks"] if c["name"] == "cargo-test"),
        )

        missing = json.loads(
            sb.wf("--json", "status", "--checks", check=0).stdout
        )
        self.assertNotIn("cargo-test", missing["ci_matrix"])
        payload_path.write_text(json.dumps(missing), encoding="utf-8")
        refused = subprocess.run(
            [sys.executable, str(sb.root / "checks" / "ci_matrix.py"),
             str(payload_path)],
            cwd=sb.dir, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(
            refused.returncode, 0,
            "require_workspace_tests must be called by the scheduled transform",
        )
        self.assertIn("cargo-test", refused.stdout + refused.stderr)


class TheSuiteIsShardedWithoutGaps(unittest.TestCase):
    """Assert that unittest discovery and the CI shard runner own one set."""

    SHARD = support.WF_DIR / "tests" / "shard.py"
    N = 3

    def modules(self, shard, n, i):
        proc = subprocess.run(
            [sys.executable, str(shard), "--list", str(n), str(i)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.split()

    def discovered_modules(self, tests):
        proc = subprocess.run(
            [sys.executable, "-c", DISCOVERY_PROBE, str(tests)],
            cwd=tests,
            capture_output=True,
            text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        tagged = [
            line for line in proc.stdout.splitlines()
            if line.startswith("WF_DISCOVERED=")
        ]
        self.assertEqual(len(tagged), 1, proc.stdout)
        modules = json.loads(tagged[0].split("=", 1)[1])
        self.assertTrue(modules, "unittest discovery found no modules")
        return modules

    def partition_problem(self, tests, shard):
        expected = sorted(self.discovered_modules(tests))
        shards = [self.modules(shard, self.N, i) for i in range(self.N)]
        listed = [module for one_shard in shards for module in one_shard]
        problems = []
        if sorted(listed) != expected:
            problems.append(
                f"unittest={expected!r}; shard --list union={sorted(listed)!r}"
            )
        duplicates = sorted(
            module for module in set(listed) if listed.count(module) != 1
        )
        if duplicates:
            problems.append(f"modules not owned exactly once: {duplicates!r}")
        return "; ".join(problems) or None

    def test_the_shards_partition_the_unittest_discovery_set(self):
        tests = support.WF_DIR / "tests"
        problem = self.partition_problem(tests, self.SHARD)
        self.assertIsNone(
            problem,
            f"every unittest-discovered module must be in exactly one shard: {problem}",
        )
        for i in range(self.N):
            self.assertTrue(
                self.modules(self.SHARD, self.N, i),
                f"shard {i} of {self.N} is empty",
            )

    def test_the_shard_glob_is_pinned_verbatim(self):
        # the live tree has no module that discriminates test*.py
        # from test_*.py, so a narrowed glob is invisible to the
        # partition comparison; the one-line glob is load-bearing and
        # pinned verbatim — change it and this pin together,
        # deliberately (Grok, PR #32 review)
        source = (support.WF_DIR / "tests" / "shard.py").read_text()
        self.assertEqual(source.count('TESTS.glob("test*.py")'), 1,
                         "the shard glob moved or was respelled")

    def test_a_nested_discovery_gap_makes_the_sandboxed_check_fail(self):
        with tempfile.TemporaryDirectory(prefix="wf-shard-copy-") as raw:
            sandbox = Path(raw) / "repo"
            shutil.copytree(
                REPO,
                sandbox,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "wf.db", "wf.db-*"
                ),
            )
            tests = sandbox / "ops" / "devlane" / "workflow" / "tests"
            nested = tests / "nested"
            nested.mkdir()

            package_text = '"""Planted discovery package."""\n'
            package = nested / "__init__.py"
            package.write_text(package_text, encoding="utf-8")
            self.assertEqual(package.read_text(encoding="utf-8"), package_text)

            planted_text = (
                "import unittest\n\n"
                "class Planted(unittest.TestCase):\n"
                "    def test_planted(self):\n"
                "        self.assertTrue(True)\n"
            )
            planted = nested / "test_planted.py"
            planted.write_text(planted_text, encoding="utf-8")
            self.assertEqual(planted.read_text(encoding="utf-8"), planted_text)
            self.assertTrue(planted.is_file())


            shard = tests / "shard.py"
            problem = self.partition_problem(tests, shard)
            self.assertIsNotNone(
                problem,
                "the planted nested module must expose a flat-glob shard gap",
            )
            self.assertIn("nested.test_planted", problem)

    def test_a_shard_actually_runs_its_tests(self):
        # One small shard end-to-end: the runner must execute unittest, not
        # merely print names. Ran with a high shard count so the subset is
        # tiny and the check stays cheap.
        many = len(self.discovered_modules(support.WF_DIR / "tests"))
        proc = subprocess.run(
            [sys.executable, str(self.SHARD), str(many), "0"],
            capture_output=True, text=True, check=False,
            cwd=REPO,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertIn("OK", proc.stderr + proc.stdout)

    def test_the_workflow_runs_the_shard_matrix(self):
        text = APPS_YML.read_text()
        self.assertIn("shard.py", text, "the job must run the shard runner")
        self.assertIn("matrix", text)
        self.assertIn(f"{self.N} ${{{{ matrix.shard }}}}", text,
                      "the matrix must pass shard count and index")


class MiniAppsRunOnceEach(unittest.TestCase):
    """Until 2026-08-25 the six mini-app suites ran as extra steps inside
    the workflow shard job, so they ran three times each and a telemetry
    failure turned every shard red. They now live in their own matrix
    job, one named check per app, with the command in the matrix."""

    def test_mini_app_suites_do_not_run_inside_the_workflow_shards(self):
        workflow = section(APPS_YML.read_text(), JOB_WORKFLOW)
        self.assertIn("shard.py", workflow)
        self.assertNotIn(
            "unittest discover", workflow,
            "a suite inside the shard job runs once per shard",
        )
        app = section(APPS_YML.read_text(), JOB_APP)
        self.assertIn(
            "unittest discover", app,
            "the app job is where the mini-app suites must run",
        )

    def test_each_mini_app_is_named_in_the_matrix_with_its_command(self):
        entries = app_matrix_entries(APPS_YML.read_text())
        self.assertTrue(entries, "the app include matrix is empty")
        apps = [name for name, _cmd in entries]
        self.assertEqual(
            apps, list(APP_JOBS),
            "dropping an app from the matrix silently leaves CI",
        )
        for name, cmd in entries:
            self.assertIn("unittest discover", cmd, name)
            self.assertIn(name, cmd, f"{name} command does not name its tree")
        app_root = REPO / "ops" / "devlane"
        self.assertEqual(
            undeclared_mini_apps(app_root, APP_JOBS),
            [],
            "a mini app with tests/ must be workflow or in the include matrix",
        )

    def test_a_new_mini_app_directory_without_a_job_fails_the_check(self):
        with tempfile.TemporaryDirectory(prefix="ci-newapp-") as raw:
            root = Path(raw) / "ops" / "devlane"
            live = REPO / "ops" / "devlane"
            for child in live.iterdir():
                if child.is_dir() and (child / "tests").is_dir():
                    (root / child.name / "tests").mkdir(parents=True)
            planted = root / "newapp" / "tests"
            planted.mkdir(parents=True)
            (planted / "test_empty.py").write_text("\n")
            self.assertTrue(planted.is_dir())
            self.assertIn("newapp", mini_apps_with_tests(root))
            self.assertIn(
                "newapp", undeclared_mini_apps(root, APP_JOBS)
            )

    def test_the_app_job_runs_the_matrix_command_not_an_if_branch(self):
        job = section(APPS_YML.read_text(), JOB_APP)
        self.assertIn("run: ${{ matrix.cmd }}", job)
        self.assertNotRegex(
            job, r"if:\s*matrix\.app",
            "a step that picks its command by if: can silently run nothing",
        )


class RunsAreCancelledWhenSuperseded(unittest.TestCase):
    """A 342s suite run on an already-superseded commit is pure waste; a
    hung job burns the 360-minute default. Both workflows therefore declare
    a concurrency group with cancel-in-progress and per-job timeouts."""

    def test_both_workflows_cancel_superseded_runs(self):
        problems = concurrency_problems(WORKFLOW_FILES)
        self.assertFalse(problems, problems)

    def test_copying_one_group_line_onto_the_other_fails_naming_both(self):
        with tempfile.TemporaryDirectory(prefix="ci-conc-") as raw:
            copies = []
            groups = []
            for path in WORKFLOW_FILES:
                dest = Path(raw) / path.name
                dest.write_bytes(path.read_bytes())
                copies.append(dest)
                group = concurrency_group(path.read_text())
                self.assertIsInstance(group, str, path.name)
                groups.append(group)
            self.assertNotEqual(groups[0], groups[1])
            text = copies[1].read_text()
            before = copies[1].read_bytes()
            planted = text.replace(groups[1], groups[0], 1)
            copies[1].write_text(planted)
            after = copies[1].read_bytes()
            self.assertNotEqual(after, before)
            self.assertGreater(len(after), 64)
            self.assertIn(b"concurrency:", after)
            problems = concurrency_problems(copies)
            self.assertTrue(problems, "shared group was not seen")
            joined = " ".join(problems)
            self.assertIn(copies[0].name, joined)
            self.assertIn(copies[1].name, joined)

    def test_every_job_has_a_timeout(self):
        for path in WORKFLOW_FILES:
            text = path.read_text().split("jobs:", 1)[1]
            jobs = re.findall(r"\n  ([a-z-]+):\n", "\n" + text)
            timeouts = text.count("timeout-minutes:")
            self.assertEqual(timeouts, len(jobs),
                             f"{path.name}: {len(jobs)} job(s), "
                             f"{timeouts} timeout(s)")


class RetiredNamesDoNotReachAPerson(unittest.TestCase):
    # Quote-vs-use 2026-08-31: scratch, records, handoffs and conductor
    # are quoting homes. This scan only reaches scratch of those four;
    # sibling scans (vocabulary wall SERVICE_HOMES) already exempt it.
    QUOTE_HOME = "ops/docs/scratch"
    SURFACE = (
        ".dev/guide",
        "ops/docs",
        "ops/devlane/hooks",
        f":(exclude){QUOTE_HOME}",
    )

    def listed(self):
        listed = subprocess.check_output(
            ["git", "ls-files", "--", *self.SURFACE],
            cwd=REPO, text=True,
        )
        rels = [line for line in listed.splitlines() if line]
        self.assertTrue(rels, "the user-facing surface listed no files")
        return rels

    def _under_quote_home(self, rel):
        home = self.QUOTE_HOME
        return rel == home or rel.startswith(home + "/")

    def test_retired_check_names_do_not_reach_a_person(self):
        hits = retired_hits(REPO, self.listed())
        self.assertFalse(hits, "\n".join(hits))

    def test_scratch_quoting_home_is_outside_the_scan(self):
        rels = self.listed()
        scratch = [rel for rel in rels if self._under_quote_home(rel)]
        self.assertFalse(
            scratch,
            "scratch is a quoting home; sibling scans exempt it:\n"
            + "\n".join(scratch),
        )
        docs = [
            rel for rel in rels
            if rel.startswith("ops/docs/") and not self._under_quote_home(rel)
        ]
        self.assertTrue(
            docs, "non-quoting ops/docs dropped from the scan")

    def test_reinserting_a_retired_name_into_a_guide_page_fails(self):
        rels = self.listed()
        guide = next(
            rel for rel in rels if rel.startswith("ops/guide/") and rel.endswith(".md")
        )
        with tempfile.TemporaryDirectory(prefix="ci-retired-") as raw:
            src = REPO / guide
            dest_root = Path(raw)
            dest = dest_root / guide
            dest.parent.mkdir(parents=True)
            before = src.read_bytes()
            dest.write_bytes(before)
            planted = dest.read_text() + "\nWF:gates (commit-trailers)\n"
            dest.write_text(planted)
            after = dest.read_bytes()
            self.assertNotEqual(after, before)
            self.assertGreater(len(after), 64)
            self.assertIn(b"#", after)
            hits = retired_hits(dest_root, [guide])
            self.assertTrue(hits)
            self.assertTrue(any("WF:gates" in hit for hit in hits), hits)


class CachingIsAbsentOnPurpose(unittest.TestCase):
    """The usual cache targets do not exist (stdlib-only, no pip, no build),
    and caching wf.db across runs would put the stale-cache failure class —
    the one classify_cache exists to stop — into CI itself. The decision is
    pinned so a future "add caching" PR has to argue with it."""

    def test_no_cache_action_and_the_reason_is_stated(self):
        for path in WORKFLOW_FILES:
            text = path.read_text()
            self.assertNotIn("actions/cache", text, path.name)
        self.assertIn("cache", DEV_YML.read_text().lower(),
                      "the reason caching is absent belongs in the file")


# Contract: every job's runs-on is this expression. A revert to
# ubuntu-latest restores hosted billing and must not stay green here.
SELF_HOSTED_RUNS_ON = "${{ vars.CI_RUNNER || 'self-hosted' }}"
HOSTED_BILLING_RUNS_ON = "ubuntu-latest"
_RUNS_ON_LINE = re.compile(
    r"^    runs-on:\s*(.+?)\s*$"
)
_SELF_HOSTED_RUNS_ON_LINE = re.compile(
    rb"^([ \t]+runs-on:[ \t]*)\"?"
    + re.escape(SELF_HOSTED_RUNS_ON.encode())
    + rb"\"?([ \t]*)$",
    re.MULTILINE,
)


def workflow_jobs(text):
    """Job id -> body lines, GitHub job-id grammar under the jobs: key.

    Trigger names (`pull_request`, `push`) sit at the same indent as
    job ids, but above `jobs:` — splitting there is what stops them
    counting as jobs with no runs-on.
    """
    marker = "\njobs:\n"
    if marker not in text:
        if text.startswith("jobs:\n"):
            body = text.split("jobs:", 1)[1]
        else:
            return {}
    else:
        body = text.split("jobs:", 1)[1]
    jobs = {}
    current = None
    for line in body.splitlines():
        head = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):$", line)
        if head:
            current = head.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return jobs


def job_runs_on(body_lines):
    """The job-level runs-on value, or None if the job has none."""
    for line in body_lines:
        match = _RUNS_ON_LINE.match(line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            return value
    return None


def hosted_billing_runs_on_problems(paths):
    """Name every job whose runs-on is not the self-hosted expression."""
    problems = []
    for path in paths:
        path = Path(path)
        jobs = workflow_jobs(path.read_text(encoding="utf-8"))
        if not jobs:
            problems.append(f"{path.name}: no jobs")
            continue
        for name, body in jobs.items():
            runs_on = job_runs_on(body)
            if runs_on != SELF_HOSTED_RUNS_ON:
                problems.append(
                    f"{path.name} job {name}: runs-on {runs_on!r} "
                    f"(want {SELF_HOSTED_RUNS_ON!r})"
                )
    return problems


class EveryJobRunsOnTheSelfHostedExpression(unittest.TestCase):
    """A private repo bills a whole hosted minute per job. Both CI
    workflows therefore set every job's runs-on to
    ${{ vars.CI_RUNNER || 'self-hosted' }}. The variable is the escape
    hatch; unset, the default is self-hosted and hosted billing is
    zero. A revert to ubuntu-latest restores that bill, and this pin
    is what makes the revert red in the workflow-shape suite."""

    def test_every_job_runs_on_is_the_self_hosted_expression(self):
        problems = hosted_billing_runs_on_problems(WORKFLOW_FILES)
        self.assertFalse(problems, problems)

        with tempfile.TemporaryDirectory(prefix="ci-runs-on-") as raw:
            copies = []
            for path in WORKFLOW_FILES:
                dest = Path(raw) / path.name
                dest.write_bytes(path.read_bytes())
                copies.append(dest)
            for dest in copies:
                before = support.plant_bytes(
                    dest,
                    lambda blob: _SELF_HOSTED_RUNS_ON_LINE.sub(
                        rb"\1" + HOSTED_BILLING_RUNS_ON.encode() + rb"\2",
                        blob,
                        count=1,
                    ),
                    expect="shrink",
                    recognisable=lambda blob: (
                        b"jobs:" in blob
                        and HOSTED_BILLING_RUNS_ON.encode() in blob
                        and b"name: CI" in blob
                    ),
                )
                after = dest.read_bytes()
                self.assertNotEqual(after, before)
                self.assertGreater(len(after), 64)
                self.assertIn(HOSTED_BILLING_RUNS_ON.encode(), after)
            planted = hosted_billing_runs_on_problems(copies)
            self.assertTrue(
                planted,
                "a revert to ubuntu-latest was not seen",
            )
            joined = " ".join(planted)
            self.assertIn("ci-dev.yml", joined)
            self.assertIn("ci-dev-apps.yml", joined)
            self.assertTrue(
                any(HOSTED_BILLING_RUNS_ON in item for item in planted),
                planted,
            )


class AToolInstalledByAJobIsOnThatJobsPath(unittest.TestCase):
    """A self-hosted runner's PATH is whatever the runner host gave it. On
    agentscient-wsl-1 (run 33150063542, 2026-08-28) `pipx install ruff` ran,
    made no symlink because ~/.local/bin already held a ruff, and
    lint.py then could not find `ruff` at all: ~/.local/bin was not on
    the job's PATH. ubuntu-latest hides this by shipping that directory
    on PATH. A job that installs a tool with pipx therefore appends
    pipx's bin directory to $GITHUB_PATH in the same job, so the
    workflow carries its own PATH assumption instead of the runner's."""

    def _jobs_with_pipx(self, path):
        text = path.read_text(encoding="utf-8")
        jobs = {}
        current = None
        for line in text.splitlines():
            head = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):$", line)
            if head:
                current = head.group(1)
                jobs[current] = []
            elif current is not None:
                jobs[current].append(line)
        return {name: "\n".join(body) for name, body in jobs.items()
                if "pipx install" in "\n".join(body)}

    def test_every_pipx_job_puts_the_bin_dir_on_github_path(self):
        pattern = re.compile(
            r'(?:\$HOME/\.local/bin|\$PIPX_BIN_DIR)[^\n]*>>\s*"?\$GITHUB_PATH"?')
        for path in (DEV_YML, APPS_YML):
            jobs = self._jobs_with_pipx(path)
            self.assertTrue(jobs, f"{path.name}: no job installs with pipx")
            for name, body in jobs.items():
                self.assertRegex(
                    body, pattern,
                    f"{path.name} job {name}: pipx install without its "
                    f"bin dir >> $GITHUB_PATH in the same job",
                )


if __name__ == "__main__":
    unittest.main()
