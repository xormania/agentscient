"""Shape and proof-mode pins for `.github/workflows/codeql.yml` (Units A and A-prime).

The live file is the Unit A artifact; this module does not ship it. At HEAD
the live-file tests fail because the file is missing, which is the honest
red. The allowed workflow (one positive fixture) and the skeptic mutant
(one negative fixture, record a14ef3) pin behaviour by executing step
logic and parsing `with:` — not by whole-file substrings.

Proof-mode evaluation is a small script at `.github/codeql/eval_sarif.py`,
unit-tested against real-shaped SARIF fixtures recorded 2026-08-30, as
files and as the directory `analyze` emits.
"""

import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

import support
import test_ci_shape as shape
from test_ci_shape import (
    APPS_YML,
    CONTEXTS_PY,
    DEV_YML,
    HOSTED_BILLING_RUNS_ON,
    JOB_NAME,
    PINNED_CONTEXTS,
    REPO,
    WORKFLOWS,
    _SELF_HOSTED_RUNS_ON_LINE,
    concurrency_group,
    concurrency_problems,
    hosted_billing_runs_on_problems,
    path_filter_problems,
    real_checks_payload,
    run_contexts,
    sandbox_workflows,
    trigger_block,
    workflow_display_name,
    workflow_jobs,
)

CODEQL_YML = WORKFLOWS / "codeql.yml"
EVAL_SARIF = REPO / ".github" / "codeql" / "eval_sarif.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codeql_proof"
PROOF_FIXTURE = FIXTURES / "findable.py.fixture"
CLEAN_SARIF = FIXTURES / "clean.sarif"
FINDING_SARIF = FIXTURES / "finding.sarif"
NOTE_SARIF = FIXTURES / "note.sarif"
LEVELLESS_SARIF = FIXTURES / "levelless.sarif"
WARNING_DEFAULT_SARIF = FIXTURES / "warning-default.sarif"

JOB_NAME_EXACT = "dev: codeql (${{ matrix.language }})"
BUNDLE_PIN = re.compile(r"codeql-bundle-v\d+\.\d+\.\d+")
FORBIDDEN_TOKENS = ("sudo", "apt-get", "pipx", "actions/cache", "setup-python")
WANTED_PERMISSIONS = {
    "security-events": "write",
    "contents": "read",
    "actions": "read",
}
SARIF_FIXTURE_DATE = "2026-08-30"
SARIF_VERSION = "2.1.0"
CHOSEN_SEVERITY = "any result"
INIT_ACTION = "github/codeql-action/init@v3"
ANALYZE_ACTION = "github/codeql-action/analyze@v3"
EVAL_SCRIPT = ".github/codeql/eval_sarif.py"
INIT_WITH_KEYS = frozenset({"languages", "tools", "build-mode"})
ANALYZE_WITH_KEYS = frozenset({"category", "output", "upload"})
WANTED_LANGUAGES = "${{ matrix.language }}"
WANTED_BUILD_MODE = "none"
WANTED_CATEGORY = "/language:${{ matrix.language }}"
WANTED_UPLOAD = "never"
CHECKOUT_ACTION = "actions/checkout@v4"
GUARD_STATE_KEY_DEFAULT = "steps.default-setup.outputs.state"
# Measured PR 90: with Code Security disabled repo-wide, the default-setup
# endpoint answers HTTP 403 "Code Security must be enabled". That body is
# the strongest proof no default setup can compete — not UNREACHABLE.
FEATURE_DISABLED_403_STATUS = "403"
FEATURE_DISABLED_403_MARKER = "Code Security must be enabled"
FEATURE_DISABLED_403_MESSAGE = (
    "Code Security must be enabled for this repository to use code scanning."
)
AUTH_403_MESSAGE = "Resource not accessible by integration"
OTHER_UNREACHABLE_HTTP = (
    (403, AUTH_403_MESSAGE),
    (401, "Requires authentication"),
    (500, "Internal Server Error"),
    (404, "Not Found"),
)

# Positive fixture: the shape the contract allows. Not the implementation.
ALLOWED_WORKFLOW = """\
# CodeQL advanced setup on the self-hosted runners.
# Bills 0 while CI_RUNNER is unset; would bill on CI_RUNNER=ubuntu-latest
# and be refused under the $0 limit. Default setup must be not-configured
# before uploads (D4). Bundle pin lives in init's tools: until pins.env
# exists. No cache action: the action's own tool cache is enough.
name: CodeQL

concurrency:
  group: codeql-${{ github.event_name }}-${{ github.head_ref || github.sha }}
  cancel-in-progress: true

on:
  workflow_dispatch:
    inputs:
      proof:
        description: run proof mode
        type: boolean
        default: false
  pull_request:
    branches: [dev, main]
  push:
    branches: [main]

permissions:
  security-events: write
  contents: read
  actions: read

jobs:
  analyze:
    name: "dev: codeql (${{ matrix.language }})"
    runs-on: ${{ vars.CI_RUNNER || 'self-hosted' }}
    timeout-minutes: 30
    env:
      PROOF: ${{ inputs.proof && '1' || '0' }}
    strategy:
      fail-fast: false
      matrix:
        language: [python, actions]
    steps:
      - uses: actions/checkout@v4

      - id: default-setup
        name: Refuse to run beside default setup
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "code-scanning/default-setup"
          if ! response=$(gh api "repos/${GITHUB_REPOSITORY}/code-scanning/default-setup"); then
            if printf '%s' "$response" | python3 -c "import json,sys; b=json.load(sys.stdin); raise SystemExit(0 if str(b.get('status'))=='403' and 'Code Security must be enabled' in str(b.get('message','')) else 1)"; then
              echo "state=not-configured" >> "$GITHUB_OUTPUT"
              exit 0
            fi
            echo "UNREACHABLE: could not establish default-setup state"
            exit 1
          fi
          state=$(printf '%s' "$response" | python3 -c "import json,sys; print(json.load(sys.stdin)['state'])")
          echo "state=${state}" >> "$GITHUB_OUTPUT"

      - name: Materialise the proof fixture
        if: env.PROOF == '1'
        run: |
          mkdir -p proof-scan
          cp ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture proof-scan/findable.py

      - uses: github/codeql-action/init@v3
        if: env.PROOF == '1' || steps.default-setup.outputs.state == 'not-configured'
        with:
          languages: ${{ matrix.language }}
          tools: https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.20.4/codeql-bundle-linux64.tar.gz
          build-mode: none

      - uses: github/codeql-action/analyze@v3
        if: env.PROOF == '1' || steps.default-setup.outputs.state == 'not-configured'
        with:
          category: /language:${{ matrix.language }}
          upload: never
          output: sarif-results

      - name: Keep SARIF as an artifact
        if: env.PROOF == '1'
        uses: actions/upload-artifact@v4
        with:
          name: codeql-sarif-${{ matrix.language }}
          path: sarif-results

      - name: Evaluate SARIF
        if: env.PROOF == '1'
        run: python3 .github/codeql/eval_sarif.py sarif-results

      - name: Remove the proof fixture
        if: always() && env.PROOF == '1'
        run: rm -f proof-scan/findable.py

      - name: Say why nothing was analysed
        if: env.PROOF != '1' && steps.default-setup.outputs.state != 'not-configured'
        run: |
          echo "codeql: SKIPPED — default setup is still configured." >> "$GITHUB_STEP_SUMMARY"
          echo "gh api -X PATCH repos/uscient/agentscient/code-scanning/default-setup -f state=not-configured"
          exit 1
"""

# Negative fixture: the a14ef3 mutant that passed the substring suite.
MUTANT_WORKFLOW = """\
# CodeQL advanced setup. Bundle codeql-bundle-v2.20.4
# (codeql-bundle-linux64.tar.gz), recorded 2026-08-30.
name: CodeQL

concurrency:
  group: codeql-${{ github.event_name }}-${{ github.head_ref || github.sha }}
  cancel-in-progress: true

on:
  workflow_dispatch:
    inputs:
      proof:
        type: boolean
        default: false
  pull_request:
    branches: [dev, main]
  push:
    branches: [main]

permissions:
  security-events: write
  contents: read
  actions: read

jobs:
  analyze:
    name: "dev: codeql (${{ matrix.language }})"
    runs-on: ${{ vars.CI_RUNNER || 'self-hosted' }}
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        language: [python, actions]
    steps:
      - uses: actions/checkout@v4

      - id: default-setup
        name: Refuse to run beside default setup
        continue-on-error: true
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "UNREACHABLE: could not establish default-setup state"
          echo "code-scanning/default-setup"
          echo "not-configured"
          exit 1

      - uses: github/codeql-action/init@v3
        if: always()
        with:
          languages: ${{ matrix.language }}
          tools: latest
          build-mode: none

      - uses: github/codeql-action/analyze@v3
        if: always()
        with:
          category: /language:${{ matrix.language }}
          upload: never
          output: sarif-results

      - name: Keep SARIF as an artifact
        uses: actions/upload-artifact@v4
        with:
          name: codeql-sarif
          path: uploaded-sarif

      - name: Evaluate SARIF
        run: python3 .github/codeql/eval_sarif.py other-dir || true

      - name: Plant the proof fixture
        run: |
          cp ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture findable.py

      - name: Say why nothing was analysed
        continue-on-error: true
        run: |
          echo "codeql: SKIPPED" >> "$GITHUB_STEP_SUMMARY"
          echo "gh api -X PATCH repos/uscient/agentscient/code-scanning/default-setup -f state=not-configured"
          exit 1
"""


def require_live(test, need):
    """The Unit A file, or an assertion that names the property we cannot pin."""
    test.assertTrue(
        CODEQL_YML.is_file(),
        f".github/workflows/codeql.yml is missing; cannot pin {need}",
    )
    text = CODEQL_YML.read_text(encoding="utf-8")
    test.assertTrue(text.strip(), f"codeql.yml is empty; cannot pin {need}")
    return text


def require_eval(test, need):
    test.assertTrue(
        EVAL_SARIF.is_file(),
        f".github/codeql/eval_sarif.py is missing; cannot pin {need}",
    )
    return EVAL_SARIF


def load_gha(text):
    """YAML load that keeps GitHub's `on:` key as the string `on`."""
    doc = yaml.safe_load(text)
    if isinstance(doc, dict) and True in doc and "on" not in doc:
        doc["on"] = doc.pop(True)
    return doc


def proof_ctx(proof, state="configured", *, state_key=GUARD_STATE_KEY_DEFAULT):
    """Values GitHub would bind for proof-mode and default-setup state.

    ``state_key`` is ``steps.<guard-id>.outputs.state``. Callers that hold a
    workflow must derive it from the guard step's ``id:`` via
    ``proof_ctx_for``; the default is only for evaluator unit tests.
    """
    flag = "1" if proof else "0"
    truth = "true" if proof else "false"
    return {
        state_key: state,
        "inputs.proof": truth,
        "github.event.inputs.proof": truth,
        "env.PROOF": flag,
    }


def proof_dispatch_ctx(proof):
    """Context for the job-level env.PROOF expression.

    A typed workflow_dispatch boolean is a real boolean on ``inputs.proof``.
    ``env.PROOF`` is absent on purpose: that value must come from evaluating
    the job's env expression, not from a bound constant.
    """
    return {
        "inputs.proof": bool(proof),
        "github.event.inputs.proof": "true" if proof else "false",
    }


def eval_gha_expr(expr, ctx):
    """Evaluate a GitHub Actions expression against ``ctx``.

    Missing ``if:`` is GitHub's default: the step runs. Context values
    go in via placeholders so a later leftover pass cannot rewrite
    characters inside already-quoted strings.
    """
    if expr is None:
        return True
    if isinstance(expr, bool):
        return expr
    text = str(expr).strip()
    if text in {"never", "always"}:
        return text
    text = re.sub(r"\$\{\{(.*?)\}\}", r"\1", text, flags=re.DOTALL).strip()
    held = []

    def hold(value):
        token = f"__GHA{len(held)}__"
        held.append(value)
        return token

    text = re.sub(r"\balways\s*\(\s*\)", hold(True), text)
    text = re.sub(r"\bsuccess\s*\(\s*\)", hold(True), text)
    text = re.sub(r"\bfailure\s*\(\s*\)", hold(False), text)
    text = re.sub(r"\bcancelled\s*\(\s*\)", hold(False), text)
    text = re.sub(
        r"fromJSON\s*\(\s*'(true|false)'\s*\)",
        lambda match: hold(match.group(1) == "true"),
        text,
    )
    for key in sorted(ctx, key=len, reverse=True):
        if key in text:
            text = text.replace(key, hold(ctx[key]))
    # GitHub binds a missing step output to the empty string. Hyphenated
    # ids (default-setup) are one token there and several to leftover.
    text = re.sub(
        r"\bsteps\.[A-Za-z0-9_.-]+",
        lambda match: hold(""),
        text,
    )
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"(?<![<>=!])!(?!=)", " not ", text)

    def leftover(match):
        word = match.group(0)
        if word in {"and", "or", "not", "True", "False", "None"}:
            return word
        if word.startswith("__GHA"):
            return word
        return hold("")

    pieces = re.split(r"('(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")", text)
    rebuilt = []
    for index, piece in enumerate(pieces):
        if index % 2 == 1:
            rebuilt.append(piece)
            continue
        rebuilt.append(re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", leftover, piece))
    text = "".join(rebuilt)
    for index, value in enumerate(held):
        text = text.replace(f"__GHA{index}__", " " + repr(value) + " ")
    return _eval_bool_ast(text.strip())


def _eval_bool_ast(text):
    """Evaluate a bool/compare expression with no name lookups."""
    tree = ast.parse(text, mode="eval")
    return _eval_ast(tree.body)


def _eval_ast(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_ast(node.operand)
    if isinstance(node, ast.BoolOp):
        values = [_eval_ast(value) for value in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for value in values:
                result = result and value
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in values:
                result = result or value
            return result
    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left)
        for op, right_node in zip(node.ops, node.comparators, strict=True):
            right = _eval_ast(right_node)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            else:
                raise ValueError(f"disallowed compare {type(op).__name__}")
            if not ok:
                return False
            left = right
        return True
    raise ValueError(f"disallowed expression node {type(node).__name__}")


def github_if(expr, ctx):
    return bool(eval_gha_expr(expr, ctx))


def workflow_on(doc):
    on = doc.get("on", doc.get(True))
    if on is None:
        raise AssertionError("workflow has no on:")
    return on


def analyze_job(doc):
    jobs = doc.get("jobs") or {}
    for job in jobs.values():
        if job.get("name") == JOB_NAME_EXACT:
            return job
    if "analyze" in jobs:
        return jobs["analyze"]
    raise AssertionError("no analyze / dev: codeql job")


def steps_of(doc):
    steps = analyze_job(doc).get("steps") or []
    if not steps:
        raise AssertionError("analyze job has no steps")
    return steps


def step_uses(doc, action):
    found = [step for step in steps_of(doc) if step.get("uses") == action]
    if len(found) != 1:
        raise AssertionError(f"want one step uses {action!r}, got {len(found)}")
    return found[0]


def steps_run_containing(doc, needle):
    return [
        step for step in steps_of(doc)
        if needle in str(step.get("run") or "")
    ]


def step_run_containing(doc, needle):
    found = steps_run_containing(doc, needle)
    if len(found) != 1:
        raise AssertionError(
            f"want one run: containing {needle!r}, got {len(found)}"
        )
    return found[0]


def planting_steps(doc):
    found = steps_run_containing(doc, "findable.py.fixture")
    if not found:
        raise AssertionError("no run: contains 'findable.py.fixture'")
    return found


def copy_step(doc):
    found = planting_steps(doc)
    if len(found) != 1:
        raise AssertionError(
            f"want one plant of findable.py.fixture, got {len(found)}"
        )
    return found[0]


def _is_skip_run(run):
    text = str(run or "")
    return "PATCH" in text or "SKIPPED" in text


def guard_step(doc):
    """The unique step that reads code-scanning/default-setup; must carry id:.

    The skip/refuse-red step quotes the same endpoint in the PATCH command,
    so a URL match alone is not unique — exclude PATCH/SKIPPED runs.
    """
    setup = [
        step for step in steps_of(doc)
        if "code-scanning/default-setup" in str(step.get("run") or "")
        and not _is_skip_run(step.get("run"))
    ]
    if len(setup) != 1:
        raise AssertionError(
            f"want one step reading code-scanning/default-setup, got {len(setup)}"
        )
    if not setup[0].get("id"):
        raise AssertionError("default-setup guard has no id:")
    return setup[0]


def guard_state_key(doc):
    return f"steps.{guard_step(doc)['id']}.outputs.state"


def proof_ctx_for(doc, proof, state="configured"):
    return proof_ctx(proof, state, state_key=guard_state_key(doc))


def skip_step(doc):
    found = [
        step for step in steps_of(doc)
        if "PATCH" in str(step.get("run") or "")
        or "SKIPPED" in str(step.get("run") or "")
    ]
    if len(found) != 1:
        raise AssertionError(f"want one skip/refuse-red step, got {len(found)}")
    return found[0]


def cleanup_steps(doc):
    return [
        step for step in steps_of(doc)
        if re.search(r"\brm\b.*findable\.py", str(step.get("run") or ""))
    ]


def cleanup_step(doc):
    found = cleanup_steps(doc)
    if len(found) != 1:
        raise AssertionError(f"want one cleanup of findable.py, got {len(found)}")
    return found[0]


def continue_on_error_steps(doc):
    named = []
    for index, step in enumerate(steps_of(doc)):
        if step.get("continue-on-error") in (True, "true"):
            named.append(step.get("name") or step.get("uses") or f"step[{index}]")
    return named


def active_lines(text):
    return [
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def workflow_header(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(line)
            continue
        break
    return "\n".join(lines)


def permissions_map(text):
    match = re.search(r"(?m)^permissions:\n((?:[ \t].*\n)*)", text)
    if not match:
        return None
    entries = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        entries[key.strip()] = value.strip()
    return entries


def permissions_problems(text):
    got = permissions_map(text)
    if got is None:
        return ["no permissions: block"]
    problems = []
    if got != WANTED_PERMISSIONS:
        problems.append(f"permissions {got!r} want {WANTED_PERMISSIONS!r}")
    for key, value in got.items():
        if value == "write" and key != "security-events":
            problems.append(f"{key}: write is not allowed")
    return problems


def matrix_languages(text):
    doc = load_gha(text)
    language = analyze_job(doc).get("strategy", {}).get("matrix", {}).get(
        "language"
    )
    if language is not None:
        return list(language)
    match = re.search(r"language:\s*\[([^\]]*)\]", text)
    if match:
        return [part.strip() for part in match.group(1).split(",") if part.strip()]
    return None


def bundle_pin_problems(text):
    """Pin ``tools:`` by the init step's ``with:`` block, never the header."""
    try:
        init = step_uses(load_gha(text), INIT_ACTION)
    except AssertionError as err:
        return [str(err)]
    tools = (init.get("with") or {}).get("tools")
    if tools is None:
        return ["init has no tools: pin"]
    tools = str(tools)
    problems = []
    if BUNDLE_PIN.search(tools) is None:
        problems.append("tools: is not pinned to codeql-bundle-v<semver>")
    if "codeql-bundle-linux64.tar.gz" not in tools:
        problems.append("tools: does not name the linux64 bundle")
    if tools.strip() == "latest":
        problems.append("tools: is the action's moving default")
    return problems


def init_with_problems(text):
    """Pin init's whole ``with:`` and analyze's, each key its own check.

    Plan §3 unit A: languages is the matrix language, build-mode is none,
    tools is present (form is ``bundle_pin_problems``), analyze category is
    ``/language:${{ matrix.language }}``. Extra init inputs (config,
    config-file, paths-ignore) can hide the plant; keys must be exactly
    languages, tools, build-mode. Analyze is bounded the same way to
    ``ANALYZE_WITH_KEYS``.
    """
    try:
        init = step_uses(load_gha(text), INIT_ACTION)
    except AssertionError as err:
        return [str(err)]
    with_block = init.get("with")
    if not isinstance(with_block, dict):
        return ["init has no with: block"]
    problems = []
    languages = with_block.get("languages")
    if languages != WANTED_LANGUAGES:
        problems.append(
            f"init languages: {languages!r}, want {WANTED_LANGUAGES}"
        )
    build_mode = with_block.get("build-mode")
    if build_mode != WANTED_BUILD_MODE:
        problems.append(
            f"init build-mode: {build_mode!r}, want {WANTED_BUILD_MODE!r}"
        )
    if "tools" not in with_block:
        problems.append("init with: missing tools:")
    extra = sorted(set(with_block) - INIT_WITH_KEYS)
    missing = sorted(INIT_WITH_KEYS - set(with_block))
    if extra:
        problems.append(
            f"init with: extra keys {extra} "
            "(config/paths-ignore would hide the plant)"
        )
    if missing:
        problems.append(f"init with: missing keys {missing}")
    problems.extend(analyze_with_problems(text))
    return problems


def analyze_with_problems(text):
    """Bound analyze's ``with:`` the way init's is bounded.

    Extra analyze inputs (skip-queries, config, queries, upload-database,
    wait-for-processing) can skip the plant, filter it, or swallow an
    upload failure so the proof run is green having found nothing.
    """
    try:
        analyze = step_uses(load_gha(text), ANALYZE_ACTION)
    except AssertionError as err:
        return [str(err)]
    with_block = analyze.get("with")
    if not isinstance(with_block, dict):
        return ["analyze has no with: block"]
    problems = []
    extra = sorted(set(with_block) - ANALYZE_WITH_KEYS)
    missing = sorted(ANALYZE_WITH_KEYS - set(with_block))
    if extra:
        problems.append(
            f"analyze with: extra keys {extra} "
            "(skip-queries/config/queries/upload-database would hide "
            "the plant or swallow an upload failure)"
        )
    if missing:
        problems.append(f"analyze with: missing keys {missing}")
    category = with_block.get("category")
    if category != WANTED_CATEGORY:
        problems.append(
            f"analyze category: {category!r}, want {WANTED_CATEGORY}"
        )
    upload = with_block.get("upload")
    if upload != WANTED_UPLOAD:
        problems.append(
            f"analyze upload: {upload!r}, want {WANTED_UPLOAD!r} unconditionally"
        )
    return problems


def checkout_and_fail_fast_problems(text):
    try:
        doc = load_gha(text)
        job = analyze_job(doc)
    except AssertionError as err:
        return [str(err)]
    problems = []
    found = [step for step in steps_of(doc) if step.get("uses") == CHECKOUT_ACTION]
    if len(found) != 1:
        problems.append(f"want one {CHECKOUT_ACTION}, got {len(found)}")
    fail_fast = (job.get("strategy") or {}).get("fail-fast")
    if fail_fast is not False:
        problems.append(f"strategy.fail-fast is {fail_fast!r}, want false")
    return problems


def forbidden_problems(text, token):
    return [
        f"active line contains {token!r}: {line.strip()}"
        for line in active_lines(text)
        if token in line
    ]


def header_metered_problems(text):
    header = workflow_header(text)
    if not header.strip():
        return ["codeql.yml has no header comment"]
    problems = []
    lower = header.lower()
    if "CI_RUNNER" not in header:
        problems.append("header does not name CI_RUNNER")
    if "ubuntu-latest" not in header:
        problems.append("header does not name ubuntu-latest")
    if "$0" not in header:
        problems.append("header does not name the $0 spend limit")
    if "bill" not in lower:
        problems.append("header does not state what it bills")
    return problems


def proof_input_problems(text):
    try:
        doc = load_gha(text)
        on = workflow_on(doc)
    except AssertionError as err:
        return [str(err)]
    if not isinstance(on, dict) or "workflow_dispatch" not in on:
        return ["no workflow_dispatch input for PROOF"]
    dispatch = on.get("workflow_dispatch") or {}
    inputs = dispatch.get("inputs") or {}
    names = {str(key).lower() for key in inputs}
    if "proof" not in names:
        return ["workflow_dispatch has no proof input"]
    try:
        expr = (analyze_job(doc).get("env") or {}).get("PROOF")
    except AssertionError as err:
        return [str(err)]
    if expr is None:
        return ["analyze job has no env.PROOF"]
    problems = []
    on_val = eval_gha_expr(expr, proof_dispatch_ctx(True))
    off_val = eval_gha_expr(expr, proof_dispatch_ctx(False))
    if on_val != "1":
        problems.append(
            f"env.PROOF evaluates to {on_val!r} when proof is dispatched, want '1'"
        )
    if off_val != "0":
        problems.append(
            f"env.PROOF evaluates to {off_val!r} when proof is off, want '0'"
        )
    return problems


def guard_endpoint_is_this_repository(run):
    text = str(run or "")
    return (
        "${GITHUB_REPOSITORY}" in text
        or "$GITHUB_REPOSITORY" in text
        or "${{ github.repository }}" in text
    )


def writes_github_output_state(step):
    """True when the step's run: writes ``state=`` to ``$GITHUB_OUTPUT``."""
    run = str(step.get("run") or "")
    return "GITHUB_OUTPUT" in run and re.search(r"\bstate=", run) is not None


def github_output_state_writers(doc):
    return [step for step in steps_of(doc) if writes_github_output_state(step)]


def guard_condition_problems(test, text):
    """D4: init/analyze stay off when configured unless proof is on.

    The configured / not-configured labels are the values the guard step
    actually wrote when the endpoint returned each. The context key is
    derived from that step's ``id:``, not bound by hand, and init /
    analyze / skip ``if:`` must name that key. The endpoint is this
    repository (``${GITHUB_REPOSITORY}``). Only the guard writes
    ``state=`` to ``$GITHUB_OUTPUT``; every other ``if:`` that reads a
    state output must use that derived key. The guard itself must run
    in the proof=False worlds it feeds, and it must precede init.
    """
    try:
        doc = load_gha(text)
        init = step_uses(doc, INIT_ACTION)
        analyze = step_uses(doc, ANALYZE_ACTION)
        skip = skip_step(doc)
        setup = guard_step(doc)
        key = guard_state_key(doc)
    except AssertionError as err:
        return [str(err)]
    problems = []
    if not guard_endpoint_is_this_repository(setup.get("run")):
        problems.append(
            "default-setup endpoint is not pinned to this repository "
            "via ${GITHUB_REPOSITORY}"
        )
    writers = github_output_state_writers(doc)
    if setup not in writers:
        problems.append(
            "default-setup guard does not write state= to $GITHUB_OUTPUT"
        )
    others = [step for step in writers if step is not setup]
    if others:
        names = [
            step.get("name") or step.get("id") or "unnamed" for step in others
        ]
        problems.append(
            "steps other than the guard write state= to $GITHUB_OUTPUT: "
            f"{names}"
        )
    steps = steps_of(doc)
    if steps.index(setup) >= steps.index(init):
        problems.append("default-setup guard does not precede init")
    off_proof_configured = proof_ctx(False, "configured", state_key=key)
    off_proof_ready = proof_ctx(False, "not-configured", state_key=key)
    if not github_if(setup.get("if"), off_proof_configured):
        problems.append(
            "default-setup guard does not run when proof is off and "
            "default setup is configured"
        )
    if not github_if(setup.get("if"), off_proof_ready):
        problems.append(
            "default-setup guard does not run when proof is off and "
            "default setup is not-configured"
        )
    for name, step in (("init", init), ("analyze", analyze), ("skip", skip)):
        if_text = str(step.get("if") or "")
        if key not in if_text:
            problems.append(f"{name} if: does not reference {key}")
    for index, step in enumerate(steps):
        if_text = str(step.get("if") or "")
        if ".outputs.state" in if_text and key not in if_text:
            label = step.get("name") or step.get("uses") or f"step[{index}]"
            problems.append(
                f"{label} if: reads a state output that is not {key}"
            )
    observed_problems, observed = observe_guard_states(test, text)
    problems.extend(observed_problems)
    off_configured = proof_ctx(False, observed["configured"], state_key=key)
    on_configured = proof_ctx(True, observed["configured"], state_key=key)
    off_ready = proof_ctx(False, observed["not-configured"], state_key=key)
    if github_if(init.get("if"), off_configured):
        problems.append(
            "init runs when default setup is configured and proof is off"
        )
    if not github_if(init.get("if"), off_ready):
        problems.append("init does not run when default setup is not-configured")
    if not github_if(init.get("if"), on_configured):
        problems.append(
            "init does not run in proof mode while default setup is configured"
        )
    if github_if(analyze.get("if"), off_configured):
        problems.append(
            "analyze runs when default setup is configured and proof is off"
        )
    if not github_if(analyze.get("if"), off_ready):
        problems.append(
            "analyze does not run when default setup is not-configured"
        )
    if not github_if(analyze.get("if"), on_configured):
        problems.append(
            "analyze does not run in proof mode while default setup is configured"
        )
    if not github_if(skip.get("if"), off_configured):
        problems.append("skip does not run when configured and proof is off")
    if github_if(skip.get("if"), on_configured):
        problems.append("skip still runs in proof mode")
    if github_if(skip.get("if"), off_ready):
        problems.append("skip runs when default setup is not-configured")
    leaking = continue_on_error_steps(doc)
    if leaking:
        problems.append(f"continue-on-error on {leaking}")
    return problems


def fixture_exclusion_problems(text):
    try:
        doc = load_gha(text)
        plants = planting_steps(doc)
        init = step_uses(doc, INIT_ACTION)
        analyze = step_uses(doc, ANALYZE_ACTION)
        state_key = guard_state_key(doc)
    except AssertionError as err:
        return [str(err)]
    problems = []
    for step in plants:
        for proof in (False, True):
            for state in ("configured", "not-configured"):
                runs = github_if(
                    step.get("if"),
                    proof_ctx(proof, state, state_key=state_key),
                )
                if proof and not runs:
                    suffix = (
                        ""
                        if state == "configured"
                        else f" and default setup is {state}"
                    )
                    problems.append(
                        f"copy step does not run when proof is on{suffix}"
                    )
                if (not proof) and runs:
                    if state == "not-configured":
                        problems.append(
                            "plant runs on a real scan once default setup is off"
                        )
                    else:
                        problems.append("copy step runs when proof is off")
    cleanups = cleanup_steps(doc)
    if not cleanups:
        problems.append("no cleanup removes findable.py")
    else:
        on_proof = proof_ctx(True, state_key=state_key)
        for cleanup in cleanups:
            if not github_if(cleanup.get("if"), on_proof):
                problems.append("cleanup does not run when proof is on")
    steps = steps_of(doc)
    init_at = steps.index(init)
    analyze_at = steps.index(analyze)
    for step in plants:
        if steps.index(step) >= init_at:
            problems.append("copy does not precede init")
    if init_at >= analyze_at:
        problems.append("init does not precede analyze")
    for cleanup in cleanups:
        if steps.index(cleanup) <= analyze_at:
            problems.append("cleanup does not follow analyze")
    return problems


def eval_argument(run):
    for line in str(run).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "eval_sarif.py" not in stripped:
            continue
        left = stripped.split("||")[0]
        parts = shlex.split(left)
        index = next(
            i for i, part in enumerate(parts) if part.endswith("eval_sarif.py")
        )
        if index + 1 >= len(parts):
            return None
        return parts[index + 1]
    return None


def proof_path_problems(text):
    try:
        doc = load_gha(text)
        analyze = step_uses(doc, ANALYZE_ACTION)
        eval_step = step_run_containing(doc, "eval_sarif.py")
        state_key = guard_state_key(doc)
    except AssertionError as err:
        return [str(err)]
    output = (analyze.get("with") or {}).get("output")
    if not output:
        return ["analyze has no output: for the SARIF"]
    artifacts = [
        step for step in steps_of(doc)
        if "upload-artifact" in str(step.get("uses") or "")
    ]
    if len(artifacts) != 1:
        return [f"want one upload-artifact step, got {len(artifacts)}"]
    artifact = (artifacts[0].get("with") or {}).get("path")
    if not artifact:
        return ["SARIF is not kept as an artifact"]
    argument = eval_argument(eval_step.get("run") or "")
    problems = []
    on_proof = proof_ctx(True, state_key=state_key)
    off_proof = proof_ctx(False, state_key=state_key)
    off_ready = proof_ctx(False, "not-configured", state_key=state_key)
    if argument != output:
        problems.append(
            f"eval argument {argument!r} != analyze output {output!r}"
        )
    if artifact != output:
        problems.append(
            f"artifact path {artifact!r} != analyze output {output!r}"
        )
    upload = (analyze.get("with") or {}).get("upload")
    if upload is None:
        problems.append("analyze has no upload:")
    else:
        if upload != WANTED_UPLOAD:
            problems.append(
                f"analyze upload is {upload!r}, want {WANTED_UPLOAD} unconditionally"
            )
        for label, ctx in (
            ("in proof mode", on_proof),
            ("when not proving", off_ready),
        ):
            value = eval_gha_expr(upload, ctx)
            if value != "never" and str(value) != "never":
                problems.append(
                    f"analyze upload {label} is {value!r}, want never"
                )
    if not github_if(eval_step.get("if"), on_proof):
        problems.append("eval step does not run when proof is on")
    if github_if(eval_step.get("if"), off_proof):
        problems.append("eval step runs when proof is off")
    try:
        eval_at = steps_of(doc).index(eval_step)
        analyze_at = steps_of(doc).index(analyze)
    except ValueError:
        return problems
    if eval_at <= analyze_at:
        problems.append("eval step does not follow analyze")
    return problems


def bash_eval_run(run, script, argument, output_token):
    rewritten = run.replace(EVAL_SCRIPT, str(script))
    if output_token:
        rewritten = rewritten.replace(str(output_token), str(argument))
    return subprocess.run(
        ["bash", "-e", "-c", rewritten],
        capture_output=True,
        text=True,
        check=False,
    )


def failing_eval_stub(test):
    raw = tempfile.mkdtemp(prefix="ci-codeql-stub-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    stub = Path(raw) / "eval_sarif.py"
    stub.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    dummy = Path(raw) / "sarif-results"
    dummy.mkdir()
    return stub, dummy


def eval_step_propagates_failure(test, text):
    """True when a failing evaluation fails the shell step (no ``|| true``)."""
    doc = load_gha(text)
    eval_step = step_run_containing(doc, "eval_sarif.py")
    if eval_step.get("continue-on-error") in (True, "true"):
        return False
    analyze = step_uses(doc, ANALYZE_ACTION)
    output = (analyze.get("with") or {}).get("output") or "sarif-results"
    stub, dummy = failing_eval_stub(test)
    proc = bash_eval_run(eval_step.get("run") or "", stub, dummy, output)
    return proc.returncode != 0


def execute_run(run, cwd, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-e", "-c", run],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def named_findable_fixture(run):
    match = re.search(r"(\S*findable\.py\.fixture)", str(run or ""))
    if match is None:
        return None
    return match.group(1).strip("'\"")


def plant_source_problems(run):
    """The plant's source must be the repository's reviewed proof fixture."""
    source = named_findable_fixture(run)
    if source is None:
        return ["copy run does not name findable.py.fixture"]
    repo_source = (REPO / source).resolve()
    if repo_source != PROOF_FIXTURE.resolve():
        relative = PROOF_FIXTURE.relative_to(REPO)
        return [
            f"plant source {source!r} is not the reviewed proof fixture {relative}"
        ]
    if not repo_source.is_file():
        return [f"plant source {source} is not a file in the repository"]
    return []


def execute_copy(test, step, cwd=None):
    """Run the plant step, copying FROM the repository fixture.

    The named source is resolved against REPO and must be PROOF_FIXTURE.
    The sandbox is laid out from that repository path; the harness never
    invents the source bytes.
    """
    if cwd is None:
        raw = tempfile.mkdtemp(prefix="ci-codeql-copy-")
        test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
        cwd = Path(raw)
    run = step.get("run") or ""
    source = named_findable_fixture(run)
    test.assertIsNotNone(source, "copy run does not name findable.py.fixture")
    repo_source = (REPO / source).resolve()
    test.assertEqual(
        repo_source,
        PROOF_FIXTURE.resolve(),
        f"plant source {source!r} is not the reviewed proof fixture",
    )
    test.assertTrue(
        repo_source.is_file(),
        f"plant source {source} is not a file in the repository",
    )
    sandbox_source = cwd / source
    sandbox_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_source, sandbox_source)
    proc = execute_run(run, cwd)
    return cwd, proc


def copy_materialises(test, text, *, proof):
    doc = load_gha(text)
    plants = planting_steps(doc)
    try:
        ctx = proof_ctx_for(doc, proof)
    except AssertionError:
        ctx = proof_ctx(proof)
    raw = tempfile.mkdtemp(prefix="ci-codeql-copy-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    cwd = Path(raw)
    ran = False
    for step in plants:
        if not github_if(step.get("if"), ctx):
            continue
        ran = True
        _cwd, proc = execute_copy(test, step, cwd=cwd)
        test.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
    return ran, list(cwd.rglob("findable.py")), cwd


def workspace_relative_findable(cwd):
    """findable.py paths under ``cwd``, as relative paths; escapes listed apart."""
    relative = []
    escaped = []
    root = cwd.resolve()
    for path in cwd.rglob("findable.py"):
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            escaped.append(path)
            continue
        relative.append(rel)
    return relative, escaped


def plant_execution_problems(test, text):
    """Execute every plant in proof mode; the fixture must land in-tree.

    Each named source is the repository's reviewed proof fixture, not a
    path the harness invented. A findable.py must appear at a path
    relative to the workspace, and every cleanup in the same cwd must
    remove it. Catalogue 2: an arm that never ran is not a pin.
    """
    try:
        doc = load_gha(text)
        plants = planting_steps(doc)
    except AssertionError as err:
        return [str(err)]
    problems = []
    try:
        ctx = proof_ctx_for(doc, True)
    except AssertionError as err:
        problems.append(str(err))
        ctx = proof_ctx(True)

    source_ok = True
    for step in plants:
        src_probs = plant_source_problems(step.get("run") or "")
        if src_probs:
            problems.extend(src_probs)
            source_ok = False
    if not source_ok:
        return problems

    raw = tempfile.mkdtemp(prefix="ci-codeql-copy-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    cwd = Path(raw)
    any_ran = False
    last_proc = None
    for step in plants:
        if not github_if(step.get("if"), ctx):
            problems.append("plant step does not run in proof mode")
            continue
        any_ran = True
        _cwd, last_proc = execute_copy(test, step, cwd=cwd)
        if last_proc.returncode != 0:
            problems.append(
                "plant step exited nonzero in proof mode; findable.py did not land"
            )
    relative, escaped = workspace_relative_findable(cwd)
    for path in escaped:
        problems.append(f"plant landed outside the workspace: {path}")
    if any_ran and last_proc is not None and last_proc.returncode == 0:
        if not relative:
            problems.append(
                "proof copy produced no findable.py inside the workspace"
            )
        else:
            for rel in relative:
                if rel.is_absolute():
                    problems.append(f"plant path is not relative: {rel}")
    cleanups = cleanup_steps(doc)
    if not cleanups:
        problems.append("no cleanup removes findable.py")
        return problems
    if relative:
        for cleanup in cleanups:
            proc_rm = execute_run(cleanup.get("run") or "", cwd)
            if proc_rm.returncode != 0:
                problems.append("cleanup exited nonzero")
        remaining = [path for path in cwd.rglob("findable.py") if path.is_file()]
        if remaining:
            problems.append("cleanup left the planted findable.py in place")
    return problems


def execute_skip(test, text):
    doc = load_gha(text)
    skip = skip_step(doc)
    raw = tempfile.mkdtemp(prefix="ci-codeql-skip-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    cwd = Path(raw)
    summary = cwd / "summary.md"
    output = cwd / "output.txt"
    proc = execute_run(
        skip.get("run") or "",
        cwd,
        {
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_OUTPUT": str(output),
        },
    )
    written = summary.read_text(encoding="utf-8") if summary.is_file() else ""
    return proc, written


def _default_setup_step(test, text):
    try:
        return guard_step(load_gha(text))
    except AssertionError as err:
        test.fail(str(err))
        return None  # test.fail always raises; keep a return for linters


def execute_guard(test, text, *, stub_script, probe):
    """Run the default-setup step with gh and curl replaced by ``stub_script``.

    ``probe`` is called with the stub directory and must prove the arm
    will actually run: the stubs are the commands this env would invoke,
    and they behave as this case needs. An arm that never ran is INVALID.
    """
    step = _default_setup_step(test, text)
    raw = tempfile.mkdtemp(prefix="ci-codeql-guard-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    cwd = Path(raw)
    bin_dir = cwd / "bin"
    bin_dir.mkdir()
    for name in ("gh", "curl"):
        path = bin_dir / name
        path.write_text(stub_script, encoding="utf-8")
        path.chmod(0o755)
    extra = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GH_TOKEN": "invalid",
        "GITHUB_TOKEN": "invalid",
        "GITHUB_REPOSITORY": "uscient/agentscient",
        "GITHUB_STEP_SUMMARY": str(cwd / "summary.md"),
        "GITHUB_OUTPUT": str(cwd / "output.txt"),
    }
    which = subprocess.run(
        ["bash", "-c", "command -v gh && command -v curl"],
        env={**os.environ, **extra},
        capture_output=True,
        text=True,
        check=False,
    )
    test.assertEqual(which.returncode, 0, which.stderr or which.stdout)
    resolved = [Path(line).resolve() for line in which.stdout.splitlines() if line]
    test.assertEqual(
        resolved,
        [(bin_dir / "gh").resolve(), (bin_dir / "curl").resolve()],
        "http stubs were not the commands this env would invoke",
    )
    probe(test, bin_dir)
    proc = execute_run(step.get("run") or "", cwd, extra)
    summary = Path(extra["GITHUB_STEP_SUMMARY"])
    output = Path(extra["GITHUB_OUTPUT"])
    written = summary.read_text(encoding="utf-8") if summary.is_file() else ""
    emitted = output.read_text(encoding="utf-8") if output.is_file() else ""
    combined = (proc.stdout or "") + (proc.stderr or "") + written + emitted
    return proc, combined, emitted


def execute_guard_unreachable(test, text):
    """Run the default-setup step with gh and curl stubbed to fail.

    Plan §2: an unreadable endpoint prints UNREACHABLE and exits 1.
    """
    stub = '#!/bin/sh\necho "$0: unreachable stub" >&2\nexit 1\n'

    def probe(test, bin_dir):
        proc = subprocess.run(
            [str(bin_dir / "gh"), "api", "x"],
            capture_output=True,
            text=True,
            check=False,
        )
        test.assertNotEqual(
            proc.returncode, 0, "gh stub did not fail; the arm never ran"
        )

    proc, combined, _emitted = execute_guard(
        test, text, stub_script=stub, probe=probe
    )
    return proc, combined


def execute_guard_success(test, text, state):
    """Run the default-setup step with gh stubbed to return ``state``.

    Plan §2: the step records the endpoint's state in $GITHUB_OUTPUT.
    The stub prints JSON ``{"state": ...}`` and exits 0 — the same
    body ``gh api`` emits on a reachable endpoint.
    """
    if state not in ("configured", "not-configured"):
        raise AssertionError(f"unexpected default-setup state {state!r}")
    body = json.dumps({"state": state})
    stub = f"#!/bin/sh\necho '{body}'\nexit 0\n"

    def probe(test, bin_dir):
        proc = subprocess.run(
            [str(bin_dir / "gh"), "api", "x"],
            capture_output=True,
            text=True,
            check=False,
        )
        test.assertEqual(
            proc.returncode, 0, "gh stub did not succeed; the arm never ran"
        )
        test.assertIn(state, proc.stdout, "gh stub did not print the planted state")

    proc, _combined, emitted = execute_guard(
        test, text, stub_script=stub, probe=probe
    )
    return proc, emitted


def github_output_state(emitted):
    """Last ``state=`` value in a GITHUB_OUTPUT blob, or None if absent."""
    found = None
    for line in str(emitted).splitlines():
        if line.startswith("state="):
            found = line.split("=", 1)[1]
    return found


def observe_guard_states(test, text):
    """Run the guard against each endpoint body; return problems and observed states."""
    problems = []
    observed = {}
    for expected in ("configured", "not-configured"):
        proc, emitted = execute_guard_success(test, text, expected)
        got = github_output_state(emitted)
        observed[expected] = got
        if proc.returncode != 0:
            problems.append(
                "default-setup step exits nonzero when endpoint returns "
                f"{expected}"
            )
        if got != expected:
            problems.append(
                f"default-setup wrote state={got!r} when endpoint returned "
                f"{expected}"
            )
    return problems, observed


def guard_output_problems(test, text):
    problems, _observed = observe_guard_states(test, text)
    return problems


def guard_read_failure_problems(test, text):
    """Behaviour pin for plan §2: unreadability is UNREACHABLE, not a default."""
    proc, combined = execute_guard_unreachable(test, text)
    problems = []
    if proc.returncode == 0:
        problems.append(
            "default-setup step exits 0 when the endpoint is unreadable"
        )
    if "UNREACHABLE" not in combined:
        problems.append(
            "default-setup step does not print UNREACHABLE on read failure"
        )
    return problems


def execute_guard_http_error(test, text, *, http_status, message):
    """Run the default-setup step against a failed HTTP ``gh api`` body.

    Real ``gh api`` prints the JSON body on stdout, ``gh: <message> (HTTP N)``
    on stderr, and exits 1. The probe proves that is what this env invokes.
    """
    body = json.dumps(
        {
            "message": message,
            "documentation_url": "https://docs.github.com/rest",
            "status": str(http_status),
        }
    )
    stub = (
        "#!/bin/sh\n"
        f"echo '{body}'\n"
        f'echo "gh: {message} (HTTP {http_status})" >&2\n'
        "exit 1\n"
    )

    def probe(test, bin_dir):
        proc = subprocess.run(
            [str(bin_dir / "gh"), "api", "x"],
            capture_output=True,
            text=True,
            check=False,
        )
        test.assertNotEqual(
            proc.returncode, 0, "gh stub did not fail; the arm never ran"
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        test.assertIn(
            str(http_status),
            combined,
            "gh stub did not print the planted HTTP status",
        )
        test.assertIn(
            message,
            combined,
            "gh stub did not print the planted error message",
        )

    return execute_guard(test, text, stub_script=stub, probe=probe)


def execute_guard_feature_disabled(test, text):
    """The PR 90 body: HTTP 403 whose message is Code Security disabled."""
    return execute_guard_http_error(
        test,
        text,
        http_status=int(FEATURE_DISABLED_403_STATUS),
        message=FEATURE_DISABLED_403_MESSAGE,
    )


def guard_feature_disabled_problems(test, text):
    """403 'Code Security must be enabled' records not-configured, as today."""
    today_proc, today_emitted = execute_guard_success(test, text, "not-configured")
    proc, combined, emitted = execute_guard_feature_disabled(test, text)
    problems = []
    if today_proc.returncode != 0:
        problems.append(
            "not-configured success path exits nonzero; cannot compare "
            "feature-disabled 403 recording to today"
        )
    today_state = github_output_state(today_emitted)
    if today_state != "not-configured":
        problems.append(
            f"not-configured success path wrote state={today_state!r}; "
            "cannot compare feature-disabled 403 recording to today"
        )
    if proc.returncode != today_proc.returncode:
        problems.append(
            "feature-disabled 403 exit "
            f"{proc.returncode} does not match today's not-configured "
            f"exit {today_proc.returncode}"
        )
    got = github_output_state(emitted)
    if got != today_state:
        problems.append(
            f"feature-disabled 403 wrote state={got!r} to GITHUB_OUTPUT; "
            f"today's not-configured wrote {today_state!r}"
        )
    if "UNREACHABLE" in combined:
        problems.append(
            "feature-disabled 403 printed UNREACHABLE; that response is "
            "the strongest proof no default setup can compete"
        )
    return problems


def guard_http_error_stays_unreachable_problems(test, text, http_status, message):
    """Auth and other HTTP errors stay UNREACHABLE exit 1, with no state=."""
    proc, combined, emitted = execute_guard_http_error(
        test, text, http_status=http_status, message=message
    )
    problems = []
    if proc.returncode == 0:
        problems.append(
            f"default-setup step exits 0 on HTTP {http_status} {message!r}"
        )
    if "UNREACHABLE" not in combined:
        problems.append(
            f"HTTP {http_status} {message!r} did not print UNREACHABLE"
        )
    got = github_output_state(emitted)
    if got is not None:
        problems.append(
            f"HTTP {http_status} {message!r} wrote state={got!r}; "
            "unreachability must not look like a configured state"
        )
    return problems


def guard_other_http_errors_problems(test, text):
    problems = []
    for http_status, message in OTHER_UNREACHABLE_HTTP:
        problems.extend(
            guard_http_error_stays_unreachable_problems(
                test, text, http_status, message
            )
        )
    return problems


def expect_for(before, after):
    if len(after) == len(before):
        return "edit"
    if len(after) < len(before):
        return "shrink"
    return "grow"


def planted_copy(test, mutate, *, recognisable, need):
    """Copy the live file, plant a fault, prove it landed, return the copy."""
    original = require_live(test, need).encode("utf-8")
    proposed = mutate(original)
    test.assertNotEqual(proposed, original, f"plant mutate was a no-op ({need})")
    raw = tempfile.mkdtemp(prefix="ci-codeql-")
    test.addCleanup(shutil.rmtree, raw, ignore_errors=True)
    dest = Path(raw) / "codeql.yml"
    dest.write_bytes(original)
    before = support.plant_bytes(
        dest,
        mutate,
        expect=expect_for(original, proposed),
        recognisable=recognisable,
    )
    after = dest.read_bytes()
    test.assertNotEqual(after, before)
    test.assertGreater(len(after), 64)
    test.assertEqual(after, proposed)
    return dest, before, after


def still_the_workflow(blob):
    return b"jobs:" in blob and (b"CodeQL" in blob or b"codeql" in blob)


def one_fault(text, old, new):
    """In-memory one-fault variant. Prove it landed and is still a workflow."""
    if old not in text:
        raise AssertionError(f"one-fault anchor missing: {old!r}")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"one-fault anchor not unique ({count}): {old!r}")
    out = text.replace(old, new, 1)
    if out == text:
        raise AssertionError("one-fault was a no-op")
    if "jobs:" not in out or "CodeQL" not in out:
        raise AssertionError("one-fault left the workflow unrecognisable")
    return out


class GithubIfEvaluator(unittest.TestCase):
    def test_missing_if_runs_the_step(self):
        self.assertTrue(github_if(None, {}))

    def test_always_is_true_even_when_configured(self):
        self.assertTrue(github_if("always()", proof_ctx(False, "configured")))

    def test_not_configured_or_proof_gate(self):
        expr = (
            "env.PROOF == '1' || "
            "steps.default-setup.outputs.state == 'not-configured'"
        )
        self.assertFalse(github_if(expr, proof_ctx(False, "configured")))
        self.assertTrue(github_if(expr, proof_ctx(False, "not-configured")))
        self.assertTrue(github_if(expr, proof_ctx(True, "configured")))


class AllowedWorkflowIsThePositiveFixture(unittest.TestCase):
    """The shape the contract allows — one positive fixture."""

    def test_bundle_pin_is_the_init_with_value(self):
        self.assertEqual(bundle_pin_problems(ALLOWED_WORKFLOW), [])

    def test_init_with_is_languages_tools_and_build_mode(self):
        self.assertEqual(init_with_problems(ALLOWED_WORKFLOW), [])
        self.assertEqual(checkout_and_fail_fast_problems(ALLOWED_WORKFLOW), [])

    def test_header_states_metered_ci(self):
        self.assertEqual(header_metered_problems(ALLOWED_WORKFLOW), [])

    def test_proof_input_is_named_proof(self):
        self.assertEqual(proof_input_problems(ALLOWED_WORKFLOW), [])

    def test_guard_condition_keeps_init_off_when_configured(self):
        self.assertEqual(guard_condition_problems(self, ALLOWED_WORKFLOW), [])

    def test_skip_exits_nonzero_and_names_the_patch(self):
        proc, summary = execute_skip(self, ALLOWED_WORKFLOW)
        self.assertNotEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("PATCH", (proc.stdout or "") + summary)

    def test_unreadable_endpoint_is_unreachable(self):
        self.assertEqual(
            guard_read_failure_problems(self, ALLOWED_WORKFLOW),
            [],
        )

    def test_feature_disabled_403_is_not_configured(self):
        self.assertEqual(
            guard_feature_disabled_problems(self, ALLOWED_WORKFLOW),
            [],
        )

    def test_auth_403_is_unreachable(self):
        self.assertEqual(
            guard_http_error_stays_unreachable_problems(
                self, ALLOWED_WORKFLOW, 403, AUTH_403_MESSAGE
            ),
            [],
        )

    def test_other_http_errors_are_unreachable(self):
        self.assertEqual(
            guard_other_http_errors_problems(self, ALLOWED_WORKFLOW),
            [],
        )

    def test_guard_writes_the_endpoint_state(self):
        for state in ("configured", "not-configured"):
            with self.subTest(state=state):
                proc, emitted = execute_guard_success(self, ALLOWED_WORKFLOW, state)
                self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
                self.assertEqual(
                    github_output_state(emitted),
                    state,
                    emitted,
                )

    def test_copy_stays_off_without_proof(self):
        ran, files, _cwd = copy_materialises(self, ALLOWED_WORKFLOW, proof=False)
        self.assertFalse(ran)
        self.assertEqual(files, [])

    def test_copy_materialises_findable_py_only_in_proof_mode(self):
        ran, files, cwd = copy_materialises(self, ALLOWED_WORKFLOW, proof=True)
        self.assertTrue(ran)
        self.assertTrue(files, "proof copy produced no findable.py")
        for path in files:
            rel = path.resolve().relative_to(cwd.resolve())
            self.assertFalse(rel.is_absolute(), rel)

    def test_cleanup_removes_the_materialised_fixture(self):
        ran, files, cwd = copy_materialises(self, ALLOWED_WORKFLOW, proof=True)
        self.assertTrue(ran)
        doc = load_gha(ALLOWED_WORKFLOW)
        cleanup = cleanup_step(doc)
        proc = execute_run(cleanup.get("run") or "", cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertFalse(files[0].is_file())

    def test_proof_mode_plant_lands_inside_the_workspace_and_cleanup_removes_it(self):
        self.assertEqual(plant_execution_problems(self, ALLOWED_WORKFLOW), [])

    def test_fixture_exclusion_and_order(self):
        self.assertEqual(fixture_exclusion_problems(ALLOWED_WORKFLOW), [])

    def test_analyze_upload_is_never_unconditionally(self):
        analyze = step_uses(load_gha(ALLOWED_WORKFLOW), ANALYZE_ACTION)
        upload = (analyze.get("with") or {}).get("upload")
        self.assertEqual(upload, WANTED_UPLOAD)
        self.assertNotIn("${{", str(upload))
        self.assertEqual(analyze_with_problems(ALLOWED_WORKFLOW), [])
        self.assertEqual(proof_path_problems(ALLOWED_WORKFLOW), [])

    def test_eval_paths_match_and_eval_follows_analyze(self):
        self.assertEqual(proof_path_problems(ALLOWED_WORKFLOW), [])

    def test_eval_step_propagates_failure(self):
        self.assertTrue(eval_step_propagates_failure(self, ALLOWED_WORKFLOW))

    def test_no_continue_on_error(self):
        self.assertEqual(continue_on_error_steps(load_gha(ALLOWED_WORKFLOW)), [])


class SkepticMutantIsTheNegativeFixture(unittest.TestCase):
    """Record a14ef3: one adversarial workflow the substring suite missed."""

    def test_tools_latest_is_unpinned_despite_the_header(self):
        problems = bundle_pin_problems(MUTANT_WORKFLOW)
        self.assertTrue(problems, "tools: latest with a header pin was quiet")
        self.assertTrue(
            any("semver" in item or "moving default" in item for item in problems),
            problems,
        )

    def test_always_if_runs_init_when_configured(self):
        problems = guard_condition_problems(self, MUTANT_WORKFLOW)
        self.assertTrue(problems, "if: always() + continue-on-error was quiet")
        joined = " ".join(problems)
        self.assertIn("configured", joined)

    def test_copy_runs_without_proof(self):
        problems = fixture_exclusion_problems(MUTANT_WORKFLOW)
        self.assertTrue(problems, "unconditional copy was quiet")
        ran, files, _cwd = copy_materialises(self, MUTANT_WORKFLOW, proof=False)
        self.assertTrue(ran)
        self.assertTrue(files, "mutant copy did not land findable.py")

    def test_eval_or_true_cannot_fail_the_job(self):
        self.assertFalse(eval_step_propagates_failure(self, MUTANT_WORKFLOW))
        problems = proof_path_problems(MUTANT_WORKFLOW)
        self.assertTrue(problems, "mismatched eval/output/artifact paths were quiet")


class Pass3MutantsFire(unittest.TestCase):
    """Skeptic 17f1d5 + 08704d: one-fault workflows the behaviour suite missed."""

    def test_inverted_eval_if_does_not_run_in_proof_mode(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - name: Evaluate SARIF\n        if: env.PROOF == '1'\n",
            "      - name: Evaluate SARIF\n        if: env.PROOF != '1'\n",
        )
        self.assertIn("if: env.PROOF != '1'", mutant)
        problems = proof_path_problems(mutant)
        self.assertTrue(
            problems,
            "inverted eval if: was quiet; proof-mode evaluation would be skipped",
        )

    def test_eval_step_without_if_runs_when_proof_is_off(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - name: Evaluate SARIF\n        if: env.PROOF == '1'\n        run:",
            "      - name: Evaluate SARIF\n        run:",
        )
        eval_step = step_run_containing(load_gha(mutant), "eval_sarif.py")
        self.assertIsNone(eval_step.get("if"))
        problems = proof_path_problems(mutant)
        self.assertTrue(
            problems,
            "eval step with no if: was quiet; evaluation would run on every PR",
        )

    def test_cleanup_before_analyze_is_a_problem(self):
        cleanup = (
            "      - name: Remove the proof fixture\n"
            "        if: always() && env.PROOF == '1'\n"
            "        run: rm -f proof-scan/findable.py\n"
        )
        copy_end = (
            "          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            "findable.py.fixture proof-scan/findable.py\n\n"
        )
        without = one_fault(ALLOWED_WORKFLOW, "\n" + cleanup, "\n")
        mutant = one_fault(without, copy_end, copy_end + cleanup)
        doc = load_gha(mutant)
        steps = steps_of(doc)
        copy_at = steps.index(copy_step(doc))
        cleanup_at = steps.index(cleanup_step(doc))
        analyze_at = steps.index(step_uses(doc, ANALYZE_ACTION))
        self.assertGreater(cleanup_at, copy_at)
        self.assertLess(cleanup_at, analyze_at)
        problems = fixture_exclusion_problems(mutant)
        self.assertTrue(
            problems,
            "cleanup before analyze was quiet; the plant would be gone before the scan",
        )

    def test_proof_env_from_boolean_input_not_the_boolean_itself(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "PROOF: ${{ inputs.proof && '1' || '0' }}",
            "PROOF: ${{ inputs.proof }}",
        )
        self.assertIn("PROOF: ${{ inputs.proof }}", mutant)
        self.assertNotIn("&& '1' || '0'", mutant)
        problems = proof_input_problems(mutant)
        self.assertTrue(
            problems,
            "env.PROOF bound to inputs.proof was quiet; the string 'true' never equals '1'",
        )

    def test_proof_conditional_upload_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "upload: never",
            "upload: ${{ env.PROOF == '1' && 'never' || 'always' }}",
        )
        self.assertIn("env.PROOF == '1' && 'never' || 'always'", mutant)
        analyze = step_uses(load_gha(mutant), ANALYZE_ACTION)
        upload = (analyze.get("with") or {}).get("upload")
        self.assertNotEqual(upload, WANTED_UPLOAD)
        self.assertIn("${{", str(upload))
        problems = analyze_with_problems(mutant)
        path_problems = proof_path_problems(mutant)
        self.assertTrue(
            problems,
            "PROOF-conditional upload was quiet; analyze would upload "
            "on the real scan and 403 with Code Security off",
        )
        self.assertTrue(
            path_problems,
            "PROOF-conditional upload was quiet on the proof-path pin; "
            "off-proof would upload: always",
        )

    def test_unreachable_then_exit_zero_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "          if ! response=$(gh api "
            '"repos/${GITHUB_REPOSITORY}/code-scanning/default-setup"); then\n'
            "            if printf '%s' \"$response\" | python3 -c "
            '"import json,sys; b=json.load(sys.stdin); raise SystemExit(0 if '
            "str(b.get('status'))=='403' and 'Code Security must be enabled' "
            "in str(b.get('message','')) else 1)\"; then\n"
            '              echo "state=not-configured" >> "$GITHUB_OUTPUT"\n'
            "              exit 0\n"
            "            fi\n"
            '            echo "UNREACHABLE: could not establish default-setup state"\n'
            "            exit 1\n"
            "          fi\n"
            '          state=$(printf \'%s\' "$response" | python3 -c '
            '"import json,sys; print(json.load(sys.stdin)[\'state\'])")\n'
            '          echo "state=${state}" >> "$GITHUB_OUTPUT"\n',
            '          echo "UNREACHABLE: could not establish default-setup state"\n',
        )
        self.assertIn("UNREACHABLE", mutant)
        self.assertNotIn("exit 1", mutant.split("Say why nothing was analysed")[0])
        problems = guard_read_failure_problems(self, mutant)
        self.assertTrue(
            problems,
            "UNREACHABLE then exit 0 was quiet; unreadability would look like not-configured",
        )

    def test_feature_disabled_403_treated_as_unreachable_is_a_problem(self):
        inner = (
            "            if printf '%s' \"$response\" | python3 -c "
            '"import json,sys; b=json.load(sys.stdin); raise SystemExit(0 if '
            "str(b.get('status'))=='403' and 'Code Security must be enabled' "
            "in str(b.get('message','')) else 1)\"; then\n"
            '              echo "state=not-configured" >> "$GITHUB_OUTPUT"\n'
            "              exit 0\n"
            "            fi\n"
        )
        mutant = one_fault(ALLOWED_WORKFLOW, inner, "")
        guard_run = mutant.split("Say why nothing was analysed")[0]
        self.assertNotIn(FEATURE_DISABLED_403_MARKER, guard_run)
        self.assertIn("UNREACHABLE", guard_run)
        problems = guard_feature_disabled_problems(self, mutant)
        self.assertTrue(
            problems,
            "feature-disabled 403 falling through to UNREACHABLE was quiet; "
            "Code Security disabled is the strongest proof no default setup "
            "can compete",
        )

    def test_any_403_as_not_configured_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "str(b.get('status'))=='403' and 'Code Security must be enabled' "
            "in str(b.get('message',''))",
            "str(b.get('status'))=='403'",
        )
        guard_run = mutant.split("Say why nothing was analysed")[0]
        self.assertNotIn(FEATURE_DISABLED_403_MARKER, guard_run)
        self.assertIn("=='403'", guard_run)
        self.assertEqual(
            guard_feature_disabled_problems(self, mutant),
            [],
            "a too-broad 403 handler must still accept the feature-disabled case",
        )
        problems = guard_http_error_stays_unreachable_problems(
            self, mutant, 403, AUTH_403_MESSAGE
        )
        self.assertTrue(
            problems,
            "any HTTP 403 mapped to not-configured was quiet; an auth 403 "
            "would look like default setup is off",
        )

    def test_feature_disabled_403_without_github_output_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            '              echo "state=not-configured" >> "$GITHUB_OUTPUT"\n'
            "              exit 0\n",
            "              exit 0\n",
        )
        guard_run = mutant.split("Say why nothing was analysed")[0]
        self.assertIn("exit 0", guard_run)
        self.assertNotIn(
            'echo "state=not-configured" >> "$GITHUB_OUTPUT"',
            guard_run,
        )
        problems = guard_feature_disabled_problems(self, mutant)
        self.assertTrue(
            problems,
            "feature-disabled 403 that exits 0 without writing GITHUB_OUTPUT "
            "was quiet; init would read an empty state",
        )

    def test_plant_runs_on_a_real_scan_once_default_setup_is_off(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - name: Materialise the proof fixture\n"
            "        if: env.PROOF == '1'\n",
            "      - name: Materialise the proof fixture\n"
            "        if: env.PROOF == '1' || "
            "steps.default-setup.outputs.state == 'not-configured'\n",
        )
        step = copy_step(load_gha(mutant))
        self.assertTrue(
            github_if(step.get("if"), proof_ctx(False, "not-configured")),
            "mutant plant if: must run on a real scan once default setup is off",
        )
        self.assertFalse(
            github_if(step.get("if"), proof_ctx(False, "configured")),
        )
        problems = fixture_exclusion_problems(mutant)
        self.assertTrue(
            problems,
            "plant if: also true when not-configured was quiet; "
            "the fixture would upload into the Security tab after the swap",
        )
        self.assertTrue(
            any("real scan" in item or "not-configured" in item for item in problems),
            problems,
        )

    def test_plant_outside_the_workspace_is_a_problem(self):
        outside = Path(tempfile.mkdtemp(prefix="ci-codeql-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        self.assertTrue(outside.is_absolute())
        copy_run = (
            "          mkdir -p proof-scan\n"
            "          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            "findable.py.fixture proof-scan/findable.py\n"
        )
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            copy_run,
            f"          mkdir -p {outside}\n"
            f"          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            f"findable.py.fixture {outside}/findable.py\n",
        )
        self.assertIn(str(outside), mutant)
        problems = plant_execution_problems(self, mutant)
        self.assertTrue(
            (outside / "findable.py").is_file(),
            "outside plant did not land; the assertion would answer nothing",
        )
        self.assertTrue(
            problems,
            "cp to an absolute path outside the checkout was quiet; "
            "proof mode would scan a tree with no plant",
        )

    def test_plant_to_runner_temp_is_a_problem(self):
        copy_run = (
            "          mkdir -p proof-scan\n"
            "          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            "findable.py.fixture proof-scan/findable.py\n"
        )
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            copy_run,
            "          mkdir -p ${{ runner.temp }}\n"
            "          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            "findable.py.fixture ${{ runner.temp }}/findable.py\n",
        )
        self.assertIn("${{ runner.temp }}", mutant)
        problems = plant_execution_problems(self, mutant)
        self.assertTrue(
            problems,
            "cp to ${{ runner.temp }} was quiet; proof mode would "
            "materialise nothing inside $GITHUB_WORKSPACE",
        )

    def test_cleanup_of_the_wrong_path_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "        run: rm -f proof-scan/findable.py\n",
            "        run: rm -f findable.py\n",
        )
        self.assertIn("rm -f findable.py", mutant)
        self.assertNotIn("rm -f proof-scan/findable.py", mutant)
        problems = plant_execution_problems(self, mutant)
        self.assertTrue(
            problems,
            "cleanup rm -f findable.py against a plant in proof-scan/ was quiet",
        )

    def test_guard_that_ignores_the_endpoint_state_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            '          state=$(printf \'%s\' "$response" | python3 -c '
            '"import json,sys; print(json.load(sys.stdin)[\'state\'])")\n'
            '          echo "state=${state}" >> "$GITHUB_OUTPUT"\n',
            '          echo "state=not-configured" >> "$GITHUB_OUTPUT"\n',
        )
        self.assertIn('echo "state=not-configured"', mutant)
        guard_run = mutant.split("Say why nothing was analysed")[0]
        self.assertNotIn("json.load(sys.stdin)['state']", guard_run)
        self.assertNotIn("state=$(printf", guard_run)
        output_problems = guard_output_problems(self, mutant)
        self.assertTrue(
            output_problems,
            "guard that writes not-configured regardless of the endpoint was quiet",
        )
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "observed not-configured-for-configured was not fed into the if: checks",
        )

    def test_hardcoded_init_languages_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "languages: ${{ matrix.language }}",
            "languages: actions",
        )
        self.assertIn("languages: actions", mutant)
        self.assertNotIn("languages: ${{ matrix.language }}", mutant)
        problems = init_with_problems(mutant)
        self.assertTrue(
            problems,
            "languages: actions was quiet; both matrix legs would build an "
            "actions database and the python proof would find nothing",
        )
        self.assertTrue(
            any("languages" in item for item in problems),
            problems,
        )

    def test_init_config_paths_ignore_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "          build-mode: none\n",
            "          build-mode: none\n"
            "          config: |\n"
            "            paths-ignore:\n"
            "              - proof-scan\n",
        )
        self.assertIn("paths-ignore:", mutant)
        self.assertIn("proof-scan", mutant.split("init@v3", 1)[1].split("analyze@v3", 1)[0])
        problems = init_with_problems(mutant)
        self.assertTrue(
            problems,
            "init config: paths-ignore was quiet; the plant would be excluded "
            "from the database and the proof run would be green having found nothing",
        )
        self.assertTrue(
            any("config" in item or "extra" in item for item in problems),
            problems,
        )

    def test_plant_source_that_is_not_the_proof_fixture_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture",
            ".dev/ci/findable.py.fixture",
        )
        self.assertIn(".dev/ci/findable.py.fixture", mutant)
        self.assertFalse(
            (REPO / ".dev/ci/findable.py.fixture").exists(),
            "the named source must not exist in the repository; a harness that "
            "manufactures it would hide this",
        )
        problems = plant_execution_problems(self, mutant)
        self.assertTrue(
            problems,
            "plant source .dev/ci/findable.py.fixture was quiet; the harness "
            "would manufacture the reviewed fixture at a path that is not in the repo",
        )

    def test_plant_source_that_is_not_in_the_repository_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture",
            "ops/devlane/workflow/fixtures/codeql_proof/findable.py.fixture",
        )
        self.assertIn(
            "ops/devlane/workflow/fixtures/codeql_proof/findable.py.fixture",
            mutant,
        )
        self.assertFalse(
            (REPO / "ops/devlane/workflow/fixtures/codeql_proof/findable.py.fixture").exists()
        )
        problems = plant_execution_problems(self, mutant)
        self.assertTrue(
            problems,
            "plant source one directory off the reviewed fixture was quiet",
        )

    def test_guard_id_that_does_not_match_the_if_key_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - id: default-setup\n",
            "      - id: setup-state\n",
        )
        self.assertIn("id: setup-state", mutant)
        self.assertNotIn("id: default-setup", mutant)
        doc = load_gha(mutant)
        self.assertEqual(guard_step(doc).get("id"), "setup-state")
        init = step_uses(doc, INIT_ACTION)
        self.assertIn("steps.default-setup.outputs.state", init.get("if"))
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "id: setup-state with if: steps.default-setup.outputs.state was quiet; "
            "GitHub would bind the empty string and every real PR would take the skip arm",
        )

    def test_guard_endpoint_that_is_not_this_repository_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            'repos/${GITHUB_REPOSITORY}/code-scanning/default-setup',
            "repos/github/codeql-action/code-scanning/default-setup",
        )
        self.assertIn("repos/github/codeql-action", mutant)
        guard = guard_step(load_gha(mutant))
        self.assertNotIn("GITHUB_REPOSITORY", guard.get("run") or "")
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "guard reading github/codeql-action's default-setup was quiet",
        )

    def test_second_unguarded_plant_is_a_problem(self):
        extra = (
            "      - name: Seed the sample tree\n"
            "        run: |\n"
            "          mkdir -p sample\n"
            "          cp ops/devlane/workflow/tests/fixtures/codeql_proof/"
            "findable.py.fixture sample/findable.py\n\n"
        )
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - uses: github/codeql-action/init@v3\n",
            extra + "      - uses: github/codeql-action/init@v3\n",
        )
        doc = load_gha(mutant)
        plants = planting_steps(doc)
        self.assertEqual(len(plants), 2, "the second plant must have landed")
        self.assertEqual(plants[0].get("if"), "env.PROOF == '1'")
        self.assertIsNone(plants[1].get("if"), "the second plant is unguarded")
        problems = fixture_exclusion_problems(mutant)
        self.assertTrue(
            problems,
            "a second unguarded plant was quiet; after the swap the fixture "
            "would land on every real scan",
        )

    def test_analyze_skip_queries_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "          output: sarif-results\n",
            "          output: sarif-results\n          skip-queries: true\n",
        )
        analyze = step_uses(load_gha(mutant), ANALYZE_ACTION)
        self.assertEqual((analyze.get("with") or {}).get("skip-queries"), True)
        problems = init_with_problems(mutant)
        self.assertTrue(
            problems,
            "analyze skip-queries: true was quiet; the database would be "
            "built, no query would run, and the proof run would be green "
            "having found nothing",
        )
        self.assertTrue(
            any("skip-queries" in item or "extra" in item for item in problems),
            problems,
        )

    def test_analyze_upload_database_false_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "          output: sarif-results\n",
            "          output: sarif-results\n          upload-database: false\n",
        )
        analyze = step_uses(load_gha(mutant), ANALYZE_ACTION)
        self.assertIs((analyze.get("with") or {}).get("upload-database"), False)
        problems = init_with_problems(mutant)
        self.assertTrue(
            problems,
            "analyze upload-database: false was quiet; the with: block is "
            "unread for any key other than category/output/upload",
        )
        self.assertTrue(
            any("upload-database" in item or "extra" in item for item in problems),
            problems,
        )

    def test_a_second_github_output_state_writer_is_a_problem(self):
        extra = (
            "      - name: Force default-setup ready\n"
            '        run: echo "state=not-configured" >> "$GITHUB_OUTPUT"\n\n'
        )
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - uses: github/codeql-action/init@v3\n",
            extra + "      - uses: github/codeql-action/init@v3\n",
        )
        writers = [
            step
            for step in steps_of(load_gha(mutant))
            if "GITHUB_OUTPUT" in str(step.get("run") or "")
            and re.search(r"\bstate=", str(step.get("run") or ""))
        ]
        self.assertGreaterEqual(len(writers), 2, "the second writer must have landed")
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "a second step writing state= to $GITHUB_OUTPUT was quiet; "
            "consumers would not know which write they read",
        )

    def test_a_consumer_reading_a_literal_other_state_key_is_a_problem(self):
        extra = (
            "      - name: Echo another step's state\n"
            "        if: steps.other.outputs.state == 'configured'\n"
            "        run: echo leftover\n\n"
        )
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - uses: github/codeql-action/init@v3\n",
            extra + "      - uses: github/codeql-action/init@v3\n",
        )
        doc = load_gha(mutant)
        found = [
            step
            for step in steps_of(doc)
            if "steps.other.outputs.state" in str(step.get("if") or "")
        ]
        self.assertEqual(len(found), 1, "the literal-key consumer must have landed")
        self.assertNotIn(guard_state_key(doc), found[0].get("if"))
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "if: steps.other.outputs.state was quiet; a consumer reading a "
            "literal key that is not the guard's derived output is unread",
        )

    def test_guard_only_in_proof_is_a_problem(self):
        mutant = one_fault(
            ALLOWED_WORKFLOW,
            "      - id: default-setup\n"
            "        name: Refuse to run beside default setup\n",
            "      - id: default-setup\n"
            "        name: Refuse to run beside default setup\n"
            "        if: env.PROOF == '1'\n",
        )
        setup = guard_step(load_gha(mutant))
        self.assertEqual(setup.get("if"), "env.PROOF == '1'")
        self.assertFalse(
            github_if(setup.get("if"), proof_ctx(False, "configured")),
            "mutant guard if: must stay off when proof is off",
        )
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "guard if: env.PROOF == '1' was quiet; on every real PR the "
            "step that writes state= would not run, init/analyze would "
            "read the empty string, and the skip arm would fire forever",
        )

    def test_guard_after_analyze_is_a_problem(self):
        guard = (
            "      - id: default-setup\n"
            "        name: Refuse to run beside default setup\n"
            "        env:\n"
            "          GH_TOKEN: ${{ github.token }}\n"
            "        run: |\n"
            '          echo "code-scanning/default-setup"\n'
            "          if ! response=$(gh api "
            '"repos/${GITHUB_REPOSITORY}/code-scanning/default-setup"); then\n'
            "            if printf '%s' \"$response\" | python3 -c "
            '"import json,sys; b=json.load(sys.stdin); raise SystemExit(0 if '
            "str(b.get('status'))=='403' and 'Code Security must be enabled' "
            "in str(b.get('message','')) else 1)\"; then\n"
            '              echo "state=not-configured" >> "$GITHUB_OUTPUT"\n'
            "              exit 0\n"
            "            fi\n"
            '            echo "UNREACHABLE: could not establish default-setup state"\n'
            "            exit 1\n"
            "          fi\n"
            "          state=$(printf '%s' \"$response\" | python3 -c "
            '"import json,sys; print(json.load(sys.stdin)[\'state\'])")\n'
            '          echo "state=${state}" >> "$GITHUB_OUTPUT"\n\n'
        )
        analyze_end = (
            "          output: sarif-results\n\n"
            "      - name: Keep SARIF as an artifact\n"
        )
        without = one_fault(ALLOWED_WORKFLOW, "\n" + guard, "\n")
        mutant = one_fault(
            without,
            analyze_end,
            "          output: sarif-results\n\n"
            + guard
            + "      - name: Keep SARIF as an artifact\n",
        )
        doc = load_gha(mutant)
        steps = steps_of(doc)
        setup_at = steps.index(guard_step(doc))
        init_at = steps.index(step_uses(doc, INIT_ACTION))
        analyze_at = steps.index(step_uses(doc, ANALYZE_ACTION))
        self.assertGreater(setup_at, analyze_at)
        self.assertGreater(setup_at, init_at)
        problems = guard_condition_problems(self, mutant)
        self.assertTrue(
            problems,
            "guard relocated below analyze was quiet; consumers would "
            "read state= before any step wrote it",
        )


class WorkflowFileExists(unittest.TestCase):
    def test_codeql_yml_exists(self):
        self.assertTrue(
            CODEQL_YML.is_file(),
            ".github/workflows/codeql.yml is missing",
        )


class WorkflowIsNamedCodeQL(unittest.TestCase):
    def test_display_name_is_codeql_not_ci(self):
        text = require_live(self, "workflow name CodeQL")
        self.assertEqual(workflow_display_name(text), "CodeQL")
        self.assertNotEqual(workflow_display_name(text), shape.WORKFLOW_NAME)


class JobNameInterpolatesLanguage(unittest.TestCase):
    def test_job_name_is_the_dev_codeql_matrix_form(self):
        text = require_live(self, "job name dev: codeql (${{ matrix.language }})")
        self.assertEqual(analyze_job(load_gha(text)).get("name"), JOB_NAME_EXACT)
        names = JOB_NAME.findall(text)
        self.assertEqual(names, [JOB_NAME_EXACT])

    def test_the_name_does_not_collide_with_either_ci_file(self):
        text = require_live(self, "job name unique vs CI files")
        mine = set(JOB_NAME.findall(text))
        self.assertTrue(mine)
        verify = set(JOB_NAME.findall(DEV_YML.read_text(encoding="utf-8")))
        apps = set(JOB_NAME.findall(APPS_YML.read_text(encoding="utf-8")))
        self.assertFalse(mine & verify)
        self.assertFalse(mine & apps)


class EveryJobRunsOnTheSelfHostedExpression(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        require_live(self, "runs-on is the self-hosted expression")
        problems = hosted_billing_runs_on_problems([CODEQL_YML])
        self.assertEqual(problems, [])

    def test_planted_ubuntu_latest_fires_naming_codeql(self):
        dest, _, after = planted_copy(
            self,
            lambda blob: _SELF_HOSTED_RUNS_ON_LINE.sub(
                rb"\1" + HOSTED_BILLING_RUNS_ON.encode() + rb"\2",
                blob,
                count=1,
            ),
            recognisable=lambda blob: (
                still_the_workflow(blob)
                and HOSTED_BILLING_RUNS_ON.encode() in blob
            ),
            need="ubuntu-latest is not a runs-on",
        )
        self.assertIn(HOSTED_BILLING_RUNS_ON.encode(), after)
        problems = hosted_billing_runs_on_problems([dest])
        self.assertTrue(problems, "a revert to ubuntu-latest was not seen")
        joined = " ".join(problems)
        self.assertIn("codeql.yml", joined)
        self.assertTrue(
            any(HOSTED_BILLING_RUNS_ON in item for item in problems),
            problems,
        )


class ConcurrencyIsDistinct(unittest.TestCase):
    def test_live_file_stays_quiet_and_the_group_is_not_a_ci_group(self):
        text = require_live(self, "concurrency group codeql-…")
        problems = concurrency_problems([CODEQL_YML])
        self.assertEqual(problems, [])
        ours = concurrency_group(text)
        self.assertIsInstance(ours, str)
        self.assertIn("group: codeql-", ours)
        dev_group = concurrency_group(DEV_YML.read_text(encoding="utf-8"))
        apps_group = concurrency_group(APPS_YML.read_text(encoding="utf-8"))
        self.assertNotEqual(ours, dev_group)
        self.assertNotEqual(ours, apps_group)

    def test_sharing_the_ci_dev_group_fires(self):
        text = require_live(self, "concurrency group distinct from ci-dev")
        ours = concurrency_group(text)
        theirs = concurrency_group(DEV_YML.read_text(encoding="utf-8"))
        self.assertIsInstance(ours, str)
        self.assertIsInstance(theirs, str)
        self.assertNotEqual(ours, theirs)
        dest, _, _ = planted_copy(
            self,
            lambda blob: blob.replace(ours.encode(), theirs.encode(), 1),
            recognisable=lambda blob: (
                b"concurrency:" in blob and theirs.encode() in blob
            ),
            need="concurrency group collision with ci-dev",
        )
        problems = concurrency_problems([DEV_YML, dest])
        self.assertTrue(problems, "shared group was not seen")
        joined = " ".join(problems)
        self.assertIn("codeql.yml", joined)
        self.assertIn("ci-dev.yml", joined)


class PathFiltersStayOff(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        require_live(self, "no paths: filter; both triggers present")
        self.assertEqual(path_filter_problems(CODEQL_YML), [])

    def test_pull_request_targets_dev_and_main(self):
        text = require_live(self, "pull_request branches [dev, main]")
        head = text.split("jobs:", 1)[0]
        block = trigger_block(head, "pull_request")
        self.assertIn("dev", block)
        self.assertIn("main", block)

    def test_push_targets_main_and_not_dev(self):
        text = require_live(self, "push branches [main] only (D11)")
        head = text.split("jobs:", 1)[0]
        block = trigger_block(head, "push")
        self.assertIn("main", block)
        self.assertNotRegex(block, r"(?m)^[ \t]+-[ \t]+dev\s*$")
        self.assertNotRegex(block, r"\[[^\]]*dev[^\]]*\]")

    def test_planted_paths_under_pull_request_fires(self):
        dest, _, after = planted_copy(
            self,
            lambda blob: blob.replace(
                b"  pull_request:\n",
                b"  pull_request:\n    paths:\n      - 'ops/devlane/**'\n",
                1,
            ),
            recognisable=lambda blob: still_the_workflow(blob) and b"paths:" in blob,
            need="paths: under pull_request is refused",
        )
        self.assertIn(b"paths:", after)
        problems = path_filter_problems(dest)
        self.assertTrue(problems, "the planted paths: block was not seen")
        self.assertTrue(any("paths" in item for item in problems), problems)


class EveryJobHasATimeout(unittest.TestCase):
    def test_every_job_declares_timeout_minutes(self):
        text = require_live(self, "timeout-minutes on every job")
        jobs = workflow_jobs(text)
        self.assertTrue(jobs, "codeql.yml has no jobs")
        body = text.split("jobs:", 1)[1]
        self.assertEqual(
            body.count("timeout-minutes:"),
            len(jobs),
            f"{len(jobs)} job(s), {body.count('timeout-minutes:')} timeout(s)",
        )
        self.assertEqual(analyze_job(load_gha(text)).get("timeout-minutes"), 30)


class PermissionsAreExactlyTheThree(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        text = require_live(self, "permissions are the three listed")
        self.assertEqual(permissions_problems(text), [])

    def test_planted_contents_write_fires(self):
        dest, _, after = planted_copy(
            self,
            lambda blob: blob.replace(b"contents: read", b"contents: write", 1),
            recognisable=lambda blob: (
                still_the_workflow(blob) and b"contents: write" in blob
            ),
            need="contents: write is refused",
        )
        self.assertIn(b"contents: write", after)
        problems = permissions_problems(dest.read_text(encoding="utf-8"))
        self.assertTrue(problems, "contents: write was not seen")
        self.assertTrue(
            any("contents" in item and "write" in item for item in problems),
            problems,
        )


class InitAndAnalyzeArePinned(unittest.TestCase):
    def test_init_and_analyze_v3_with_category_and_build_mode_none(self):
        text = require_live(self, "init@v3 / analyze@v3 / category / build-mode")
        self.assertEqual(init_with_problems(text), [])
        self.assertEqual(checkout_and_fail_fast_problems(text), [])
        doc = load_gha(text)
        init = step_uses(doc, INIT_ACTION)
        analyze = step_uses(doc, ANALYZE_ACTION)
        with_block = init.get("with") or {}
        self.assertEqual(with_block.get("languages"), WANTED_LANGUAGES)
        self.assertEqual(with_block.get("build-mode"), WANTED_BUILD_MODE)
        self.assertEqual(set(with_block), set(INIT_WITH_KEYS))
        self.assertEqual(set(analyze.get("with") or {}), set(ANALYZE_WITH_KEYS))
        self.assertEqual(
            (analyze.get("with") or {}).get("category"),
            WANTED_CATEGORY,
        )
        self.assertEqual(
            (analyze.get("with") or {}).get("upload"),
            WANTED_UPLOAD,
        )
        self.assertEqual(
            [
                step.get("uses")
                for step in steps_of(doc)
                if step.get("uses") == CHECKOUT_ACTION
            ],
            [CHECKOUT_ACTION],
        )
        self.assertIs(analyze_job(doc).get("strategy", {}).get("fail-fast"), False)

    def test_analyze_upload_is_never_unconditionally(self):
        text = require_live(self, "analyze upload: never unconditionally")
        analyze = step_uses(load_gha(text), ANALYZE_ACTION)
        upload = (analyze.get("with") or {}).get("upload")
        self.assertEqual(upload, WANTED_UPLOAD)
        self.assertNotIn("${{", str(upload))
        self.assertEqual(analyze_with_problems(text), [])
        self.assertEqual(proof_path_problems(text), [])


class MatrixIsPythonAndActions(unittest.TestCase):
    def test_matrix_is_exactly_python_and_actions(self):
        text = require_live(self, "matrix language: [python, actions]")
        self.assertEqual(matrix_languages(text), ["python", "actions"])


class HeaderStatesMeteredCI(unittest.TestCase):
    def test_live_header_states_what_it_bills(self):
        text = require_live(self, "AGENTS §Metered CI header")
        self.assertEqual(header_metered_problems(text), [])


class DefaultSetupGuardRefusesWhenConfigured(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        text = require_live(self, "D4 default-setup guard")
        self.assertEqual(guard_condition_problems(self, text), [])

    def test_skip_exits_nonzero_and_names_the_patch(self):
        text = require_live(self, "skip step refuses red")
        proc, summary = execute_skip(self, text)
        self.assertNotEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("PATCH", (proc.stdout or "") + summary)

    def test_unreadable_endpoint_is_unreachable(self):
        text = require_live(self, "UNREACHABLE on unreadable default-setup")
        self.assertEqual(guard_read_failure_problems(self, text), [])

    def test_feature_disabled_403_is_not_configured(self):
        text = require_live(
            self, "feature-disabled 403 records not-configured"
        )
        self.assertEqual(guard_feature_disabled_problems(self, text), [])

    def test_auth_403_is_unreachable(self):
        text = require_live(self, "auth 403 stays UNREACHABLE")
        self.assertEqual(
            guard_http_error_stays_unreachable_problems(
                self, text, 403, AUTH_403_MESSAGE
            ),
            [],
        )

    def test_other_http_errors_are_unreachable(self):
        text = require_live(self, "other HTTP errors stay UNREACHABLE")
        self.assertEqual(guard_other_http_errors_problems(self, text), [])


class ForbiddenToolsAreAbsent(unittest.TestCase):
    def test_live_file_has_none_of_the_forbidden_tokens(self):
        text = require_live(self, "no sudo/apt-get/pipx/actions/cache/setup-python")
        for token in FORBIDDEN_TOKENS:
            with self.subTest(token=token):
                self.assertEqual(forbidden_problems(text, token), [])

    def test_planted_sudo_fires(self):
        dest, _, after = planted_copy(
            self,
            lambda blob: blob.replace(
                b"uses: actions/checkout@v4",
                b"run: sudo true\n      - uses: actions/checkout@v4",
                1,
            ),
            recognisable=lambda blob: still_the_workflow(blob) and b"sudo" in blob,
            need="sudo is refused",
        )
        self.assertIn(b"sudo", after)
        problems = forbidden_problems(dest.read_text(encoding="utf-8"), "sudo")
        self.assertTrue(problems, "planted sudo was not seen")


class BundlePinIsExplicit(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        text = require_live(self, "tools: names codeql-bundle-v<semver>")
        self.assertEqual(bundle_pin_problems(text), [])


class CiContextsDoesNotReadCodeql(unittest.TestCase):
    def test_deriver_source_does_not_name_codeql(self):
        source = CONTEXTS_PY.read_text(encoding="utf-8")
        self.assertNotIn("codeql", source.lower())

    def test_a_codeql_yml_beside_the_ci_files_does_not_change_the_19(self):
        root, script = sandbox_workflows()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        extra = root / ".github" / "workflows" / "codeql.yml"
        extra.write_text(
            'name: CodeQL\njobs:\n  analyze:\n    name: "dev: codeql (python)"\n',
            encoding="utf-8",
        )
        self.assertTrue(extra.is_file())
        proc = run_contexts(real_checks_payload(), script=script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(tuple(proc.stdout.splitlines()), PINNED_CONTEXTS)

    def test_live_file_present_still_derives_the_19(self):
        require_live(self, "ci_contexts.py still derives U2-A4 with codeql.yml present")
        proc = run_contexts(real_checks_payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(tuple(proc.stdout.splitlines()), PINNED_CONTEXTS)


class ProofModeUploadNeverAndEvaluatesSarif(unittest.TestCase):
    def test_live_file_stays_quiet(self):
        text = require_live(self, "proof mode: upload never, artifact, eval")
        self.assertEqual(proof_input_problems(text), [])
        self.assertEqual(proof_path_problems(text), [])
        self.assertTrue(eval_step_propagates_failure(self, text))


class ProofFixtureIsExcludedFromTheRealScan(unittest.TestCase):
    def test_the_fixture_exists_and_holds_detectable_sinks(self):
        self.assertTrue(PROOF_FIXTURE.is_file(), PROOF_FIXTURE)
        body = PROOF_FIXTURE.read_text(encoding="utf-8")
        self.assertIn("subprocess", body)
        self.assertIn("shell=True", body)
        self.assertIn("eval(", body)
        self.assertIn("user_input", body)

    def test_the_detectable_file_is_not_a_live_python_module(self):
        live_py = PROOF_FIXTURE.with_suffix("")
        self.assertEqual(live_py.name, "findable.py")
        self.assertFalse(
            live_py.is_file(),
            "findable.py must not sit on the real tree; default setup "
            "would scan it. Copy it only when PROOF=1",
        )

    def test_the_workflow_copies_the_fixture_only_in_proof_mode(self):
        text = require_live(self, "fixture scanned only when PROOF=1")
        self.assertEqual(fixture_exclusion_problems(text), [])
        ran, files, _cwd = copy_materialises(self, text, proof=False)
        self.assertFalse(ran)
        self.assertEqual(files, [])
        self.assertEqual(plant_execution_problems(self, text), [])
        ran, files, cwd = copy_materialises(self, text, proof=True)
        self.assertTrue(ran)
        self.assertTrue(files, "proof copy produced no findable.py")
        for path in files:
            rel = path.resolve().relative_to(cwd.resolve())
            self.assertFalse(rel.is_absolute(), rel)
        cleanup = cleanup_step(load_gha(text))
        proc = execute_run(cleanup.get("run") or "", cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertFalse(files[0].is_file())


class EvalSarifOnFixtures(unittest.TestCase):
    """The evaluation script against real-shaped SARIF (recorded 2026-08-30)."""

    def run_eval(self, path, extra=()):
        script = require_eval(self, f"evaluating {Path(path).name}")
        return subprocess.run(
            [sys.executable, str(script), str(path), *extra],
            capture_output=True,
            text=True,
            check=False,
        )

    def _temp_dir_with(self, source, name):
        raw = tempfile.mkdtemp(prefix="ci-codeql-sarif-")
        self.addCleanup(shutil.rmtree, raw, ignore_errors=True)
        dest = Path(raw) / name
        shutil.copyfile(source, dest)
        return Path(raw)

    def test_fixtures_are_sarif_2_1_0_recorded_2026_08_30(self):
        for path in (
            CLEAN_SARIF,
            FINDING_SARIF,
            NOTE_SARIF,
            LEVELLESS_SARIF,
            WARNING_DEFAULT_SARIF,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), path)
                body = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(body["version"], SARIF_VERSION)
                self.assertIn("runs", body)
                self.assertTrue(body["runs"])
                recorded = body["runs"][0]["properties"]["recorded"]
                self.assertEqual(recorded, SARIF_FIXTURE_DATE)
                self.assertEqual(body["runs"][0]["tool"]["driver"]["name"], "CodeQL")

    def test_clean_sarif_exits_zero(self):
        proc = self.run_eval(CLEAN_SARIF)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_finding_sarif_exits_nonzero(self):
        proc = self.run_eval(FINDING_SARIF)
        self.assertNotEqual(
            proc.returncode, 0,
            "a CodeQL result at error must fail the job",
        )

    def test_a_note_result_still_fails(self):
        proc = self.run_eval(NOTE_SARIF)
        self.assertNotEqual(
            proc.returncode, 0,
            f"chosen severity is {CHOSEN_SEVERITY!r}; a note must fail",
        )

    def _results_of(self, path):
        body = json.loads(path.read_text(encoding="utf-8"))
        results = []
        for run in body["runs"]:
            results.extend(run.get("results") or [])
        return results

    def test_levelless_fixtures_carry_no_result_level(self):
        """The two fixtures that distinguish 'any result' from 'any result with a level'."""
        for path in (LEVELLESS_SARIF, WARNING_DEFAULT_SARIF):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), path)
                body = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(body["version"], SARIF_VERSION)
                results = self._results_of(path)
                self.assertTrue(results, f"{path.name} has no results")
                for result in results:
                    self.assertNotIn(
                        "level",
                        result,
                        f"{path.name} still carries an explicit result level",
                    )
                explicit = [
                    result
                    for result in results
                    if result.get("level") in ("error", "warning", "note")
                ]
                self.assertEqual(
                    explicit,
                    [],
                    "an evaluator that reads result.level only would still "
                    f"see {explicit} in {path.name}",
                )
        levelless = json.loads(LEVELLESS_SARIF.read_text(encoding="utf-8"))
        rule = levelless["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertEqual(
            (rule.get("defaultConfiguration") or {}).get("level"),
            "error",
            "levelless.sarif must take its level from the rule, not the result",
        )
        warning = json.loads(WARNING_DEFAULT_SARIF.read_text(encoding="utf-8"))
        warning_rule = warning["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertNotIn(
            "level",
            warning_rule.get("defaultConfiguration") or {},
            "warning-default.sarif must use the SARIF 2.1.0 default (warning)",
        )

    def test_finding_and_note_still_carry_an_explicit_result_level(self):
        for path in (FINDING_SARIF, NOTE_SARIF):
            with self.subTest(path=path.name):
                results = self._results_of(path)
                self.assertTrue(results, f"{path.name} has no results")
                for result in results:
                    self.assertIn("level", result)

    def test_a_result_with_no_level_still_fails(self):
        proc = self.run_eval(WARNING_DEFAULT_SARIF)
        self.assertNotEqual(
            proc.returncode, 0,
            "SARIF 2.1.0 default level is warning; a result with no level "
            "and no rule defaultConfiguration.level must still fail",
        )

    def test_a_result_whose_level_lives_on_the_rule_still_fails(self):
        proc = self.run_eval(LEVELLESS_SARIF)
        self.assertNotEqual(
            proc.returncode, 0,
            "a result whose level is only on the rule's defaultConfiguration "
            "must still fail; reading result.level only drops it",
        )

    def test_clean_directory_exits_zero(self):
        directory = self._temp_dir_with(CLEAN_SARIF, "python.sarif")
        proc = self.run_eval(directory)
        self.assertEqual(
            proc.returncode, 0,
            "a directory of clean SARIF (what analyze emits) must pass",
        )

    def test_finding_directory_exits_nonzero(self):
        directory = self._temp_dir_with(FINDING_SARIF, "python.sarif")
        proc = self.run_eval(directory)
        self.assertNotEqual(
            proc.returncode, 0,
            "a directory holding a finding (what analyze emits) must fail",
        )

    def test_finding_in_second_run_exits_nonzero(self):
        clean = json.loads(CLEAN_SARIF.read_text(encoding="utf-8"))
        finding = json.loads(FINDING_SARIF.read_text(encoding="utf-8"))
        body = dict(clean)
        body["runs"] = list(clean["runs"]) + list(finding["runs"])
        self.assertGreaterEqual(len(body["runs"]), 2)
        self.assertEqual(body["runs"][0]["results"], [])
        self.assertTrue(body["runs"][1]["results"])
        proc = self.run_eval(self._temp_sarif(body))
        self.assertNotEqual(
            proc.returncode, 0,
            "a finding in runs[1] must fail; inspecting runs[0] only is a miss",
        )

    def test_missing_sarif_is_not_a_clean_scan(self):
        proc = self.run_eval(REPO / "no-such-codeql.sarif")
        self.assertNotEqual(proc.returncode, 0)
        combined = (proc.stderr or "") + (proc.stdout or "")
        self.assertTrue(combined.strip(), "refusal wrote nothing")
        self.assertRegex(combined, r"UNREACHABLE|missing|not found", combined)

    def test_empty_directory_is_not_a_clean_scan(self):
        raw = tempfile.mkdtemp(prefix="ci-codeql-sarif-")
        self.addCleanup(shutil.rmtree, raw, ignore_errors=True)
        proc = self.run_eval(raw)
        self.assertNotEqual(
            proc.returncode, 0,
            "an empty output directory is not a clean scan",
        )

    def _temp_sarif(self, body):
        raw = tempfile.mkdtemp(prefix="ci-codeql-sarif-")
        self.addCleanup(shutil.rmtree, raw, ignore_errors=True)
        path = Path(raw) / "input.sarif"
        if isinstance(body, str):
            path.write_text(body, encoding="utf-8")
        else:
            path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def test_malformed_json_is_not_a_clean_scan(self):
        proc = self.run_eval(self._temp_sarif("{not json"))
        self.assertNotEqual(proc.returncode, 0)

    def test_sarif_without_runs_is_not_a_clean_scan(self):
        proc = self.run_eval(self._temp_sarif({"version": "2.1.0"}))
        self.assertNotEqual(
            proc.returncode, 0,
            "a document with no runs key is UNREACHABLE, not clean",
        )

    def test_run_missing_results_key_is_not_a_clean_scan(self):
        proc = self.run_eval(self._temp_sarif({
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "CodeQL"}}}],
        }))
        self.assertNotEqual(
            proc.returncode, 0,
            "absent results is not an empty results list",
        )


class ExistingCiWorkflowsStayUntouched(unittest.TestCase):
    def test_no_job_name_is_defined_in_both_ci_files(self):
        verify = set(JOB_NAME.findall(DEV_YML.read_text(encoding="utf-8")))
        apps = set(JOB_NAME.findall(APPS_YML.read_text(encoding="utf-8")))
        self.assertTrue(verify)
        self.assertTrue(apps)
        self.assertEqual(verify & apps, set())

    def test_ci_contexts_pin_is_still_19_from_the_two_ci_files(self):
        proc = run_contexts(real_checks_payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(tuple(proc.stdout.splitlines()), PINNED_CONTEXTS)


if __name__ == "__main__":
    unittest.main()
