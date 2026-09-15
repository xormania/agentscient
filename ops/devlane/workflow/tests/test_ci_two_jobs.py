"""CI as two always-on jobs, lane and app.

Contract: fix scope item 34 and ops/conductor/pr66-fixes.md item 4.
The workflow `.github/workflows/ci.yml` is the subject. Tests load it
with a bounded stdlib YAML subset and plant copies under a temporary
directory; they never write the live workflow or the conductor store.
Unsupported YAML is refused rather than silently dropped.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


class WorkflowYamlError(ValueError):
    """YAML syntax outside the workflow surface the oracle is willing to load."""

TRIGGERS = ("pull_request", "merge_group", "push")
JOBS = ("lane", "app")
DEV_BRANCHES = ["dev"]
SELF_HOSTED = ["self-hosted"]

# Distinctive fragments of the contracted step order, matched against
# each step's name and run text. Alternatives in a tuple are one step.
# Matching is positional and unique: a concatenated decoy name is not
# six steps, and equal indexes are not order.
LANE_STEP_NEEDLES = (
    ("actions/checkout",),
    ("GITHUB_PATH", ".local/bin", "user toolchain"),
    ("records branches", "for-each-ref"),
    ("term_wall", "term wall"),
    ("ruff",),
    ("suites.sh",),
    ("ratchet",),
    ("closure",),
    ("literals",),
    ("probes.py run",),
)
APP_STEP_NEEDLES = (
    ("actions/checkout",),
    ("GITHUB_PATH", ".local/bin", "user toolchain"),
    ("host toolchain", "php -v", "composer --version"),
    ("composer validate",),
    ("composer install",),
    ("php -l", "php lint"),
    ("kernel",),
    ("phpunit",),
    ("mate",),
)

TWO_JOB_WORKFLOW = """\
name: ci
"on":
  pull_request:
    branches: [dev]
    types: [opened, synchronize, reopened]
  merge_group:
  push:
    branches: [dev]
jobs:
  lane:
    runs-on: self-hosted
    steps:
      - run: echo lane
  app:
    runs-on: self-hosted
    steps:
      - run: echo app
"""

MASTER_TRIGGER_WORKFLOW = """\
name: ci
"on":
  pull_request:
    branches: [master]
    types: [opened, synchronize, reopened]
  merge_group:
  push:
    branches: [master]
jobs:
  lane:
    runs-on: self-hosted
    steps:
      - run: echo lane
  app:
    runs-on: self-hosted
    steps:
      - run: echo app
"""


def _plant_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    if landed != data:
        raise AssertionError(f"plant did not land intact: {path}")
    if len(landed) != len(data):
        raise AssertionError(f"plant length drifted: {path}")


def load_workflow(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        doc = load_strict_workflow_yaml(text)
    except WorkflowYamlError as exc:
        raise ValueError(f"unsupported workflow YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise AssertionError(f"workflow is not a mapping: {path}")
    return doc


def load_strict_workflow_yaml(text: str) -> object:
    return _WorkflowYamlParser(text).parse_document()


class _WorkflowYamlParser:
    """Bounded loader for the GitHub workflow YAML this oracle actually uses.

    Accepted: block mappings, block sequences, flow sequences of scalars,
    plain/quoted scalars, literal `|` blocks, comments, and `true`/`false`/
    `null` values. Keys stay strings (`on` is the key on, never boolean
    True). Anything outside that surface is refused.
    """

    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.i = 0
        self.started = False

    def parse_document(self) -> object:
        self._skip_noise(allow_doc_start=True)
        if self.i >= len(self.lines):
            raise WorkflowYamlError("empty document")
        indent, body = self._peek()
        if body.startswith("- "):
            value = self._parse_seq(indent - 1)
        else:
            value = self._parse_map(-1)
        self._skip_noise(allow_doc_start=False)
        if self.i < len(self.lines):
            raise WorkflowYamlError(
                f"unsupported trailing content at line {self.i + 1}"
            )
        return value

    def _physical(self, idx: int) -> tuple[int, str]:
        line = self.lines[idx]
        stripped_left = line.lstrip(" ")
        indent = len(line) - len(stripped_left)
        if stripped_left.startswith("\t") or "\t" in line[:indent]:
            raise WorkflowYamlError(
                f"tab indentation is outside the used surface at line {idx + 1}"
            )
        return indent, stripped_left

    def _peek(self) -> tuple[int, str]:
        self._skip_noise(allow_doc_start=False)
        if self.i >= len(self.lines):
            raise WorkflowYamlError("unexpected end of document")
        indent, body = self._physical(self.i)
        return indent, _strip_inline_comment(body)

    def _skip_noise(self, *, allow_doc_start: bool) -> None:
        while self.i < len(self.lines):
            _indent, body = self._physical(self.i)
            content = _strip_inline_comment(body).strip()
            if content == "":
                self.i += 1
                continue
            if content.startswith("%"):
                raise WorkflowYamlError(
                    f"directives are outside the used surface at line {self.i + 1}"
                )
            if content == "...":
                raise WorkflowYamlError(
                    f"document end marker is outside the used surface at line {self.i + 1}"
                )
            if content == "---":
                if self.started and not allow_doc_start:
                    raise WorkflowYamlError(
                        f"multiple documents are outside the used surface at line {self.i + 1}"
                    )
                if self.started:
                    raise WorkflowYamlError(
                        f"multiple documents are outside the used surface at line {self.i + 1}"
                    )
                self.i += 1
                continue
            return

    def _parse_map(self, parent_indent: int) -> dict:
        result: dict = {}
        map_indent = None
        while True:
            if self.i >= len(self.lines):
                break
            self._skip_noise(allow_doc_start=False)
            if self.i >= len(self.lines):
                break
            indent, body = self._physical(self.i)
            content = _strip_inline_comment(body)
            if content.strip() == "":
                self.i += 1
                continue
            if indent <= parent_indent:
                break
            if content.startswith("- "):
                raise WorkflowYamlError(
                    f"sequence item where a mapping is required at line {self.i + 1}"
                )
            if map_indent is None:
                map_indent = indent
            if indent != map_indent:
                if indent > map_indent:
                    raise WorkflowYamlError(
                        f"unexpected nested indent at line {self.i + 1}"
                    )
                break
            self.i += 1
            self.started = True
            key, rest = _split_key(content, self.i)
            if key == "<<":
                raise WorkflowYamlError(
                    f"merge keys are outside the used surface at line {self.i}"
                )
            if key in result:
                raise WorkflowYamlError(f"duplicate key {key!r} at line {self.i}")
            result[key] = self._parse_value(rest, key_indent=indent)
        if map_indent is None:
            raise WorkflowYamlError("expected a mapping")
        return result

    def _parse_seq(self, parent_indent: int) -> list:
        items: list = []
        dash_indent = None
        while True:
            if self.i >= len(self.lines):
                break
            self._skip_noise(allow_doc_start=False)
            if self.i >= len(self.lines):
                break
            indent, body = self._physical(self.i)
            content = _strip_inline_comment(body)
            if content.strip() == "":
                self.i += 1
                continue
            if indent <= parent_indent:
                break
            if not content.startswith("- ") and content != "-":
                break
            if dash_indent is None:
                dash_indent = indent
            if indent != dash_indent:
                break
            self.i += 1
            self.started = True
            rest = content[1:].strip()
            item_indent = dash_indent + 2
            if rest in ("", "-"):
                nxt = self._lookahead()
                if nxt is None or nxt[0] <= dash_indent:
                    items.append(None)
                elif nxt[1].startswith("- "):
                    items.append(self._parse_seq(dash_indent))
                else:
                    items.append(self._parse_map(dash_indent))
            elif _looks_like_key(rest):
                key, valrest = _split_key(rest, self.i)
                mapping = {key: self._parse_value(valrest, key_indent=item_indent)}
                mapping.update(self._parse_map_continuation(item_indent))
                items.append(mapping)
            else:
                items.append(_parse_scalar(rest, self.i))
        return items

    def _parse_map_continuation(self, map_indent: int) -> dict:
        result: dict = {}
        while True:
            if self.i >= len(self.lines):
                break
            self._skip_noise(allow_doc_start=False)
            if self.i >= len(self.lines):
                break
            indent, body = self._physical(self.i)
            content = _strip_inline_comment(body)
            if content.strip() == "":
                self.i += 1
                continue
            if indent != map_indent:
                break
            if content.startswith("- "):
                break
            self.i += 1
            key, rest = _split_key(content, self.i)
            if key == "<<":
                raise WorkflowYamlError(
                    f"merge keys are outside the used surface at line {self.i}"
                )
            if key in result:
                raise WorkflowYamlError(f"duplicate key {key!r} at line {self.i}")
            result[key] = self._parse_value(rest, key_indent=map_indent)
        return result

    def _parse_value(self, rest: str, *, key_indent: int) -> object:
        rest = rest.strip()
        if rest in ("|", "|-", "|+"):
            return self._parse_literal(key_indent)
        if rest in (">", ">-", ">+"):
            raise WorkflowYamlError(
                f"folded scalars are outside the used surface at line {self.i}"
            )
        if rest == "":
            nxt = self._lookahead()
            if nxt is None or nxt[0] <= key_indent:
                return None
            if nxt[1].startswith("- "):
                return self._parse_seq(key_indent)
            return self._parse_map(key_indent)
        return _parse_scalar(rest, self.i)

    def _parse_literal(self, key_indent: int) -> str:
        lines: list[str] = []
        block_indent = None
        while self.i < len(self.lines):
            indent, body = self._physical(self.i)
            if body.strip() == "":
                if block_indent is None:
                    self.i += 1
                    lines.append("")
                    continue
                lines.append("")
                self.i += 1
                continue
            if indent <= key_indent:
                break
            if block_indent is None:
                block_indent = indent
            if indent < block_indent:
                break
            lines.append(" " * (indent - block_indent) + body.rstrip("\n"))
            self.i += 1
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + ("\n" if lines else "")

    def _lookahead(self) -> tuple[int, str] | None:
        j = self.i
        while j < len(self.lines):
            indent, body = self._physical(j)
            content = _strip_inline_comment(body)
            if content.strip() == "":
                j += 1
                continue
            return indent, content
        return None


def _strip_inline_comment(body: str) -> str:
    out: list[str] = []
    dq = False
    sq = False
    i = 0
    while i < len(body):
        ch = body[i]
        if dq:
            out.append(ch)
            if ch == "\\" and i + 1 < len(body):
                out.append(body[i + 1])
                i += 2
                continue
            if ch == '"':
                dq = False
            i += 1
            continue
        if sq:
            out.append(ch)
            if ch == "'" and i + 1 < len(body) and body[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            if ch == "'":
                sq = False
            i += 1
            continue
        if ch == '"':
            dq = True
            out.append(ch)
        elif ch == "'":
            sq = True
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _split_key(content: str, lineno: int) -> tuple[str, str]:
    content = content.rstrip()
    if content.startswith(("&", "*")):
        raise WorkflowYamlError(
            f"anchors and aliases are outside the used surface at line {lineno}"
        )
    if content.startswith("!!"):
        raise WorkflowYamlError(
            f"tags are outside the used surface at line {lineno}"
        )
    if content.startswith('"'):
        end = 1
        while end < len(content):
            if content[end] == "\\" and end + 1 < len(content):
                end += 2
                continue
            if content[end] == '"':
                break
            end += 1
        if end >= len(content) or content[end] != '"':
            raise WorkflowYamlError(f"unterminated quoted key at line {lineno}")
        key = _unescape_double(content[1:end])
        rest = content[end + 1 :].lstrip()
        if not rest.startswith(":"):
            raise WorkflowYamlError(f"quoted key without ':' at line {lineno}")
        return key, rest[1:].lstrip()
    if ":" not in content:
        raise WorkflowYamlError(f"mapping entry missing ':' at line {lineno}")
    key, rest = content.split(":", 1)
    key = key.strip()
    if not key:
        raise WorkflowYamlError(f"empty key at line {lineno}")
    if "&" in key or key.startswith("*"):
        raise WorkflowYamlError(
            f"anchors and aliases are outside the used surface at line {lineno}"
        )
    if key == "<<":
        return key, rest.lstrip()
    return key, rest.lstrip()


def _looks_like_key(content: str) -> bool:
    stripped = content.strip()
    if stripped.startswith(('"', "'")):
        return ":" in stripped
    if stripped.startswith("- "):
        return False
    return ": " in stripped or stripped.endswith(":")


def _unescape_double(value: str) -> str:
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append(escapes.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_flow_seq(raw: str, lineno: int) -> list:
    inner = raw[1:-1].strip()
    if inner == "":
        return []
    if "{" in inner or "}" in inner:
        raise WorkflowYamlError(
            f"flow mappings are outside the used surface at line {lineno}"
        )
    if "[" in inner or "]" in inner:
        raise WorkflowYamlError(
            f"nested flow sequences are outside the used surface at line {lineno}"
        )
    if "&" in inner or "*" in inner or "!!" in inner:
        raise WorkflowYamlError(
            f"anchors, aliases, or tags are outside the used surface at line {lineno}"
        )
    items: list = []
    buf: list[str] = []
    dq = False
    sq = False
    for ch in inner:
        if dq:
            buf.append(ch)
            if ch == '"':
                dq = False
            continue
        if sq:
            buf.append(ch)
            if ch == "'":
                sq = False
            continue
        if ch == '"':
            dq = True
            buf.append(ch)
        elif ch == "'":
            sq = True
            buf.append(ch)
        elif ch == ",":
            token = "".join(buf).strip()
            if token == "":
                raise WorkflowYamlError(f"empty flow-sequence item at line {lineno}")
            items.append(_parse_scalar(token, lineno))
            buf = []
        else:
            buf.append(ch)
    token = "".join(buf).strip()
    if token == "":
        raise WorkflowYamlError(f"trailing comma in flow sequence at line {lineno}")
    items.append(_parse_scalar(token, lineno))
    return items


def _parse_scalar(raw: str, lineno: int) -> object:
    value = raw.strip()
    if value in ("", "~", "null", "Null", "NULL"):
        return None
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value.startswith("!!"):
        raise WorkflowYamlError(
            f"tags are outside the used surface at line {lineno}: {value}"
        )
    if value.startswith("&") or value.startswith("*"):
        raise WorkflowYamlError(
            f"anchors and aliases are outside the used surface at line {lineno}: {value}"
        )
    if value.startswith("{"):
        raise WorkflowYamlError(
            f"flow mappings are outside the used surface at line {lineno}"
        )
    if value.startswith("[") and value.endswith("]"):
        return _parse_flow_seq(value, lineno)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return _unescape_double(value[1:-1])
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if ":" in value and (
        value.split(":", 1)[1][:1] in ("", " ") or value.endswith(":")
    ):
        raise WorkflowYamlError(
            f"inline mappings are outside the used surface at line {lineno}: {value}"
        )
    return value


def trigger_map(doc: dict) -> dict:
    if "on" in doc:
        on = doc["on"]
    elif True in doc:
        # PyYAML 1.1 treats the unquoted key `on` as the boolean True.
        on = doc[True]
    else:
        raise AssertionError("workflow has no on: triggers")
    if isinstance(on, dict):
        return on
    if isinstance(on, list):
        return {name: {} for name in on}
    if isinstance(on, str):
        return {on: {}}
    raise AssertionError(f"workflow on: is not a trigger map: {on!r}")


def trigger_branches(spec: object) -> list[str] | None:
    """Branch filter of one event. None means no branches: key, i.e. all."""
    if spec is None or spec is True:
        return None
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, list):
        return [str(item) for item in spec]
    if isinstance(spec, dict):
        if "branches" not in spec:
            return None
        raw = spec["branches"]
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(item) for item in raw]
        raise AssertionError(f"branches is not a name or list: {raw!r}")
    raise AssertionError(f"trigger spec is not a filter: {spec!r}")


def paths_locations(obj, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if key == "paths":
                found.append(here)
            found.extend(paths_locations(value, here))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            found.extend(paths_locations(value, f"{path}[{index}]"))
    return found


def job_ifs(jobs: dict) -> list[str]:
    found: list[str] = []
    for name, job in jobs.items():
        if isinstance(job, dict) and "if" in job:
            found.append(str(name))
    return found


def runs_on(job: dict) -> list[str]:
    raw = job.get("runs-on")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def step_blob(step: object) -> str:
    if not isinstance(step, dict):
        return str(step)
    parts = []
    for key in ("name", "run", "uses"):
        value = step.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def step_blobs(job: dict) -> list[str]:
    steps = job.get("steps") or []
    if not isinstance(steps, list):
        raise AssertionError(f"job steps is not a list: {steps!r}")
    return [step_blob(step) for step in steps]


def blob_hits(blob: str, needles: tuple[str, ...]) -> bool:
    lowered = blob.lower()
    return any(needle.lower() in lowered for needle in needles)


def step_order_indexes(
    blobs: list[str],
    groups: tuple[tuple[str, ...], ...],
) -> list[int]:
    """One distinct step per contracted group, in that order.

    Length must match. Each group must hit exactly one blob, and the
    hit indexes must be 0..n-1. A concatenated decoy that satisfies
    every substring at one index is therefore not order.
    """
    if len(blobs) != len(groups):
        raise AssertionError(
            f"step count {len(blobs)} != contracted {len(groups)}: {blobs!r}"
        )
    indexes: list[int] = []
    for needles in groups:
        hits = [i for i, blob in enumerate(blobs) if blob_hits(blob, needles)]
        if len(hits) != 1:
            raise AssertionError(
                f"step {needles!r} hits {hits} in {blobs!r}"
            )
        indexes.append(hits[0])
    expected = list(range(len(groups)))
    if indexes != expected:
        raise AssertionError(
            f"step order {indexes} is not contracted order {expected}"
        )
    return indexes


class CiTwoJobs(unittest.TestCase):
    def load(self) -> dict:
        self.assertTrue(WORKFLOW.is_file(), f"RED: workflow is absent: {WORKFLOW}")
        return load_workflow(WORKFLOW)

    def jobs(self) -> dict:
        jobs = self.load().get("jobs")
        self.assertIsInstance(jobs, dict, f"jobs is not a mapping: {jobs!r}")
        self.assertTrue(jobs, "workflow declares no jobs")
        return jobs

    def test_jobs_are_exactly_lane_and_app(self):
        names = set(self.jobs())
        self.assertEqual(names, set(JOBS), names)
        self.assertEqual(len(names), 2, names)

    def test_both_jobs_run_on_self_hosted_runners(self):
        jobs = self.jobs()
        names = set(jobs)
        for name in JOBS:
            with self.subTest(job=name):
                self.assertIn(name, names)
                labels = runs_on(jobs[name])
                self.assertEqual(
                    labels,
                    SELF_HOSTED,
                    f"{name} runs-on={labels!r}",
                )

    def test_not_self_hosted_is_not_the_self_hosted_label(self):
        self.assertEqual(runs_on({"runs-on": "self-hosted"}), SELF_HOSTED)
        self.assertNotEqual(
            runs_on({"runs-on": "not-self-hosted"}),
            SELF_HOSTED,
        )
        self.assertNotEqual(
            runs_on({"runs-on": ["not-self-hosted"]}),
            SELF_HOSTED,
        )
        self.assertIn("self-hosted", "not-self-hosted")

    def test_triggers_are_pull_request_merge_group_and_push(self):
        on = trigger_map(self.load())
        self.assertEqual(set(on), set(TRIGGERS), set(on))
        self.assertEqual(
            trigger_branches(on["pull_request"]),
            DEV_BRANCHES,
            on["pull_request"],
        )
        self.assertEqual(
            trigger_branches(on["push"]),
            DEV_BRANCHES,
            on["push"],
        )
        merge_branches = trigger_branches(on["merge_group"])
        if merge_branches is not None:
            self.assertEqual(merge_branches, DEV_BRANCHES, on["merge_group"])

    def test_triggers_targeting_master_are_not_the_dev_set(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-master-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, MASTER_TRIGGER_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, MASTER_TRIGGER_WORKFLOW)
            on = trigger_map(load_workflow(path))
            self.assertEqual(set(on), set(TRIGGERS), set(on))
            self.assertEqual(trigger_branches(on["pull_request"]), ["master"])
            self.assertEqual(trigger_branches(on["push"]), ["master"])
            self.assertNotEqual(trigger_branches(on["pull_request"]), DEV_BRANCHES)
            self.assertNotEqual(trigger_branches(on["push"]), DEV_BRANCHES)

    def test_workflow_has_no_paths_filter(self):
        doc = self.load()
        found = paths_locations(doc)
        self.assertEqual(found, [], f"paths: filter present at {found}")

    def test_neither_job_has_a_job_level_if(self):
        found = job_ifs(self.jobs())
        self.assertEqual(found, [], f"job-level if: on {found}")

    def test_lane_steps_are_the_named_steps_in_order(self):
        jobs = self.jobs()
        self.assertIn("lane", set(jobs))
        blobs = step_blobs(jobs["lane"])
        self.assertEqual(
            step_order_indexes(blobs, LANE_STEP_NEEDLES),
            list(range(len(LANE_STEP_NEEDLES))),
            blobs,
        )

    def test_app_steps_are_the_named_steps_in_order(self):
        jobs = self.jobs()
        self.assertIn("app", set(jobs))
        blobs = step_blobs(jobs["app"])
        self.assertEqual(
            step_order_indexes(blobs, APP_STEP_NEEDLES),
            list(range(len(APP_STEP_NEEDLES))),
            blobs,
        )

    def test_a_concatenated_decoy_name_is_not_the_lane_step_order(self):
        decoy = "actions/checkout GITHUB_PATH term_wall ruff suites.sh closure literals"
        job = {
            "steps": [{"name": decoy, "run": "true"}]
            + [{"run": "true"}] * (len(LANE_STEP_NEEDLES) - 1),
        }
        blobs = step_blobs(job)
        self.assertEqual(len(blobs), len(LANE_STEP_NEEDLES))
        self.assertTrue(blob_hits(blobs[0], LANE_STEP_NEEDLES[0]))
        with self.assertRaises(AssertionError):
            step_order_indexes(blobs, LANE_STEP_NEEDLES)

    def test_a_concatenated_decoy_name_is_not_the_app_step_order(self):
        decoy = (
            "actions/checkout GITHUB_PATH host toolchain composer validate composer install "
            "php -l kernel phpunit mate"
        )
        job = {
            "steps": [{"name": decoy, "run": "true"}]
            + [{"run": "true"}] * (len(APP_STEP_NEEDLES) - 1),
        }
        blobs = step_blobs(job)
        self.assertEqual(len(blobs), len(APP_STEP_NEEDLES))
        self.assertTrue(blob_hits(blobs[0], APP_STEP_NEEDLES[0]))
        with self.assertRaises(AssertionError):
            step_order_indexes(blobs, APP_STEP_NEEDLES)

    def test_planted_paths_filter_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-paths-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, TWO_JOB_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, TWO_JOB_WORKFLOW)
            doc = load_workflow(path)
            self.assertEqual(paths_locations(doc), [])
            on = trigger_map(doc)
            self.assertIsInstance(on["pull_request"], dict)
            on["pull_request"]["paths"] = ["ops/**"]
            self.assertIn("paths", on["pull_request"])
            self.assertEqual(
                paths_locations({"on": on}),
                ["on.pull_request.paths"],
            )

    def test_planted_job_level_if_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-if-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, TWO_JOB_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, TWO_JOB_WORKFLOW)
            doc = load_workflow(path)
            jobs = doc["jobs"]
            self.assertEqual(job_ifs(jobs), [])
            jobs["lane"]["if"] = "github.event_name == 'push'"
            self.assertIn("if", jobs["lane"])
            self.assertEqual(job_ifs(jobs), ["lane"])
            self.assertNotIn("if", jobs["app"])

    def test_anchor_syntax_is_refused(self):
        text = TWO_JOB_WORKFLOW + "\nextra: &anchor {run: echo}\n"
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-anchor-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            self.assertIn("&anchor", path.read_text(encoding="utf-8"))
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_alias_syntax_is_refused(self):
        text = (
            "name: ci\n"
            "jobs:\n"
            "  lane: &lane\n"
            "    runs-on: self-hosted\n"
            "  app: *lane\n"
        )
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-alias-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertIn("&lane", landed)
            self.assertIn("*lane", landed)
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_merge_key_is_refused(self):
        text = (
            "name: ci\n"
            "base: &base\n"
            "  runs-on: self-hosted\n"
            "jobs:\n"
            "  lane:\n"
            "    <<: *base\n"
            "    steps:\n"
            "      - run: echo\n"
        )
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-merge-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertIn("<<:", landed)
            self.assertIn("*base", landed)
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_custom_tag_is_refused(self):
        text = TWO_JOB_WORKFLOW.replace(
            "echo lane",
            "!!python/object/apply:os.system ['true']",
        )
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-tag-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            self.assertIn("!!python/object", path.read_text(encoding="utf-8"))
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_second_document_is_refused_not_silently_dropped(self):
        text = TWO_JOB_WORKFLOW + "---\nname: dropped\njobs:\n  secret: {}\n"
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-docs-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertIn("---", landed)
            self.assertIn("secret", landed)
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_flow_mapping_value_is_refused(self):
        text = TWO_JOB_WORKFLOW.replace("echo app", "echo app") + (
            "extra: {runs-on: self-hosted, steps: []}\n"
        )
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-flow-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            self.assertIn("{runs-on:", path.read_text(encoding="utf-8"))
            with self.assertRaises((AssertionError, ValueError)):
                load_workflow(path)

    def test_unquoted_on_key_is_the_string_on_not_boolean_true(self):
        text = (
            "name: ci\n"
            "on:\n"
            "  push:\n"
            "    branches: [dev]\n"
            "jobs:\n"
            "  lane:\n"
            "    runs-on: self-hosted\n"
            "    steps:\n"
            "      - run: echo\n"
        )
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-on-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, text.encode("utf-8"))
            self.assertIn("\non:\n", "\n" + path.read_text(encoding="utf-8"))
            doc = load_workflow(path)
            self.assertIn("on", doc)
            self.assertNotIn(True, doc)
            self.assertIsInstance(doc["on"], dict)


if __name__ == "__main__":
    unittest.main()

