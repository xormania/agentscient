"""Independent tests for the inert lane-policy library.

Contracts (only): `ops/conductor/lane-policy.md` (including adoption
unit 1a's public functions and P1-P5, N1-N10, R1-R5, I1),
`ops/conductor/permission-surface.md` (Request/Decision),
`ops/devlane/task/CONTRACT.md` §Unit1a declaration transport,
`ops/devlane/dispatch/CONTRACT.md` §Unit1a attempt/result transport,
`ops/conductor/conductor-start-plan.md` (LaunchSelection),
`ops/conductor/decisions-register.md` (`show` row/events),
`docs/wire.md` (expected/found/needed), `docs/verified-couplings.md`.

Subject, not read: `ops/conductor/tools/lane_policy.py`. Public
functions: `bind_launch(trusted_context, declarations)`,
`check_transition(binding, candidate_evidence, transition)`,
`evaluate_tool(bound_role, normalized_request)`. In-process library,
no CLI.

A missing library file is one red (`test_the_library_file_is_present`).
Every other case loads the file when present, or a no-op stand-in that
returns None, so a missing file is not an import/collection error.
This run does not claim a later green.

Terminal pass evidence uses a registered OutputAttempt and declared
file receipts. A launch pass may use the null-attempt preflight
value; that value cannot substitute at settle/collect/land/ladder.
Request.binding_sha256 is the canonical ConductorBinding digest, not
grants_sha256. Decision is closed and must repeat Request id/digest.
checked_at is UTC YYYY-MM-DDTHH:MM:SSZ. Environment restores in
finally; the live-store guard follows pinned ops/lane.conf.

Verified synthetic providers only: planted policy bytes, planted
`decisions.py show` stdout, planted LaunchDeclarations, planted
ArtifactManifest/DependencyEvidence/OutputAttempt. No live register,
host settings, credentials, network or vendor launch. Isolated worker
HOME is never authority; the custody host HOME is a temp directory.

Faulty controls prove the plant landed and is still the fixture.
Digests are SHA-256 of the exact planted bytes, measured in the test.

Untestable here without inventing a coupling (reported, not faked):

- Exact Python key names of `trusted_context` and `bound_role` are
  named by contents in the contract, not a closed JSON schema. This
  fixture uses the contract's own nouns as keys.
- Exit 2 vs Abort 3 serialization, job-directory claim, land/ladder
  cherry-pick and record mutation are dispatch/land/ladder owned.
  This library is asserted to return an owning refusal or a refused
  PolicyResult without mutating those surfaces.
- A prose classifier for I1 is forbidden by the contract ("No word
  ban or prose classifier can prove architectural independence").
  I1 is pinned as dependency/authority promotion refusals plus
  unchanged historical record bytes.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIBRARY = REPO / "ops" / "conductor" / "tools" / "lane_policy.py"
TRACKED_POLICY = REPO / "ops" / "lane-policy.json"
PINNED_LANE_CONF = REPO / "ops" / "lane.conf"


def _lane_name(conf: Path) -> str:
    text = conf.read_text(encoding="utf-8")
    match = re.search(r"(?m)^LANE_NAME='([^']+)'$", text)
    if match is None:
        raise AssertionError(f"pinned lane.conf has no LANE_NAME: {conf}")
    name = match.group(1).strip()
    if not name:
        raise AssertionError(f"pinned LANE_NAME is empty: {conf}")
    return name


def _store_path(home: Path, lane: str) -> Path:
    return Path(home) / ".local" / "state" / lane / "decisions.db"


PINNED_LANE_NAME = _lane_name(PINNED_LANE_CONF)
LIVE_STORE = _store_path(Path.home(), PINNED_LANE_NAME)

SCHEMA = "agentscient.lane-policy/v1"
POLICY_PATH = "ops/lane-policy.json"
OWNER = "xormania <127287135+xormania@users.noreply.github.com>"
RECORDER = "Grok 4.6 <noreply@x.ai>"
BRANCH = "lane/conduct-policy-tests-20260906"
JOB = "author-tests"
STAGE = "tests"
DISPATCH = "20260906T120000Z-tests-grok-lp0001"
DISPATCH_B = "20260906T120000Z-tests-grok-lp0002"
CONDUCT_ID = "20260906T120000Z-conduct-grok-lp0003"
ADMISSION = "D-POLICY-1"
STANDING = "D-POLICY-2"
PER_JOB = "D-POLICY-3"
REPLACEMENT = "D-POLICY-4"
CHECKED_AT = "2026-09-06T12:00:00Z"
TEMPLATE_REL = "ops/devlane/task/jobs.json"
CONDUCTOR_TEMPLATE_REL = "ops/conductor/onboard-lever.md"
OWNER_WORDS = "Admit this synthetic fixture policy for independent tests."

REFUSAL_LINE = re.compile(
    r"^(lane-profile|lane-policy|lane-write|lane-dependency|"
    r"lane-artifact|lane-resume): expected .+; found .+; needed .+$"
)
CHECKED_AT_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REASON_CODES = (
    "direct-edit",
    "git-mutation",
    "shell-escape",
    "raw-vendor",
    "in-session-agent",
    "unknown-tool",
    "malformed-request",
    "binding-mismatch",
)
TRANSITIONS = (
    "launch",
    "settle",
    "resume",
    "collect-before",
    "collect-after",
    "land",
    "ladder",
)
GATE_PATHS = (
    "ops/bin/dispatch.sh",
    "ops/conductor/tools/dispatch.sh",
    "ops/bin/go.sh",
    "ops/bin/ladder.sh",
    "ops/bin/suites.sh",
    "ops/conductor/tools/laneconf.py",
    "ops/conductor/tools/ladder.py",
)
POLICY_BINDING_KEYS = (
    "schema",
    "path",
    "ref",
    "sha256",
    "admission",
    "profile",
    "template_sha256",
    "grants_sha256",
    "maintenance",
)
CONDUCTOR_BINDING_KEYS = (
    "policy",
    "selection",
    "dispatch",
    "stage",
    "job",
    "lineage",
    "snapshot_ref",
    "template",
    "declarations_sha256",
    "custody_sha256",
)
POLICY_RESULT_KEYS = (
    "binding",
    "snapshot_ref",
    "head",
    "artifacts",
    "dependencies",
    "outputs",
    "checked_at",
    "outcome",
    "refusal",
)
DECISION_KEYS = (
    "schema",
    "id",
    "binding_sha256",
    "outcome",
    "refusal",
)
FILE_RECEIPT_KEYS = (
    "artifact",
    "path",
    "sha256",
    "bytes",
    "production",
    "reuse",
    "evidence",
)
GRANT_KEYS = ("scope", "job", "role", "adapter", "outputs", "maintenance")
LANE_ENV = (
    "LANE_CONF",
    "LANE_NAME",
    "LANE_POLICY_PATH",
    "LANE_POLICY",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONSAFEPATH",
    "PYTHONNOUSERSITE",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return text.encode("utf-8")


def _path_b64(path: str) -> str:
    return base64.b64encode(path.encode("utf-8")).decode("ascii")


def _grant(repository: list[str] | tuple[str, ...], outputs: list[str] | None = None):
    return {
        "repository": sorted(set(repository)),
        "outputs": sorted(set([] if outputs is None else outputs)),
    }


def _live_snapshot_at(path: Path) -> tuple[str, bytes | None]:
    if path.is_file():
        return ("file", path.read_bytes())
    if path.exists():
        return ("other", None)
    return ("absent", None)


def _live_snapshot() -> tuple[str, bytes | None]:
    return _live_snapshot_at(LIVE_STORE)


def _as_object(value: object) -> dict | None:
    if isinstance(value, dict):
        return value
    if value is None or isinstance(value, (str, bytes, BaseException)):
        return None
    mapping = getattr(value, "__dict__", None)
    if isinstance(mapping, dict) and mapping:
        return mapping
    out = {}
    for key in (
        *POLICY_RESULT_KEYS,
        *POLICY_BINDING_KEYS,
        *CONDUCTOR_BINDING_KEYS,
        *DECISION_KEYS,
    ):
        if hasattr(value, key):
            out[key] = getattr(value, key)
    return out or None


def _refusal_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseException):
        text = str(value).strip()
        if text:
            return text.splitlines()[0]
        return ""
    if isinstance(value, str):
        return value.strip().splitlines()[0] if value.strip() else ""
    mapping = _as_object(value)
    if mapping is None:
        return ""
    refusal = mapping.get("refusal")
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip().splitlines()[0]
    if isinstance(refusal, dict):
        class_name = refusal.get("class")
        expected = refusal.get("expected")
        found = refusal.get("found")
        needed = refusal.get("needed")
        if class_name and expected and found and needed:
            return f"{class_name}: expected {expected}; found {found}; needed {needed}"
    if mapping.get("outcome") == "refused":
        return ""
    return ""


class _AbsentLibrary:
    """Stand-in so missing implementation fails assertions, not imports."""

    def bind_launch(self, trusted_context, declarations):
        return None

    def check_transition(self, binding, candidate_evidence, transition):
        return None

    def evaluate_tool(self, bound_role, normalized_request):
        return None


def _missing(name: str):
    def _call(*args, **kwargs):
        return None

    _call.__name__ = name
    return _call


def load_library():
    if not LIBRARY.is_file():
        return _AbsentLibrary()
    spec = importlib.util.spec_from_file_location("lane_policy_under_test", LIBRARY)
    if spec is None or spec.loader is None:
        return _AbsentLibrary()
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return _AbsentLibrary()
    for name in ("bind_launch", "check_transition", "evaluate_tool"):
        if not callable(getattr(module, name, None)):
            setattr(module, name, _missing(name))
    return module


class _LanePolicyCase(unittest.TestCase):
    """Isolated synthetic authority, declarations and evidence."""

    def setUp(self):
        self._live_before = _live_snapshot()
        self._env_before = {key: os.environ.get(key) for key in LANE_ENV}
        for key in LANE_ENV:
            os.environ.pop(key, None)
        self._tmp = tempfile.TemporaryDirectory(prefix="lane-policy-")
        root = Path(self._tmp.name)
        self.worker_home = root / "worker-home"
        self.host_home = root / "host-home"
        self.canonical_repo = root / "canonical-repo"
        self.reader_checkout = root / "reader-checkout"
        self.job_root = root / "job-root"
        self.candidate_tree = root / "candidate-tree"
        for path in (
            self.worker_home,
            self.host_home,
            self.canonical_repo,
            self.reader_checkout,
            self.job_root,
            self.candidate_tree,
        ):
            path.mkdir(parents=True)
        self.library = load_library()
        self.admitted_python = sys.executable
        self.policy_bytes = TRACKED_POLICY.read_bytes()
        self.assertTrue(self.policy_bytes, "tracked policy fixture is empty")
        self.assertIn(b"agentscient.lane-policy/v1", self.policy_bytes)
        self.policy_digest = _sha256(self.policy_bytes)
        self.template_bytes = b'{"author-tests":{"adapter":"harness"}}\n'
        self.template_digest = _sha256(self.template_bytes)
        self.conductor_template_bytes = b"startup-template-fixture\n"
        self.conductor_template_digest = _sha256(self.conductor_template_bytes)
        self.example_sh = b"#!/bin/sh\nexit 0\n"
        self.example_php = b"<?php\nclass Example {}\n"
        self.hook_py = b"# ordinary unprotected hook tooling\n"
        self._write_tree(
            self.canonical_repo,
            {
                POLICY_PATH: self.policy_bytes,
                TEMPLATE_REL: self.template_bytes,
                CONDUCTOR_TEMPLATE_REL: self.conductor_template_bytes,
                "ops/bin/example.sh": self.example_sh,
                "ops/devlane/hooks/claude/example.py": self.hook_py,
                "docs/wire.md": b"# wire fixture\n",
                "src/Example.php": self.example_php,
                "composer.json": b"{}\n",
                "unittest/example.txt": b"fixture-only\n",
                "ops/README.md": b"# ops fixture\n",
            },
        )
        self.snapshot_ref = self._git_init(self.canonical_repo)
        self.consumer_ref = self.snapshot_ref
        self.reader_ref = self._install_reader()
        self.reader_lane_name = _lane_name(self.reader_checkout / "ops" / "lane.conf")
        self.assertEqual(self.reader_lane_name, "agentscient-fixture")
        self.assertNotEqual(self.reader_lane_name, PINNED_LANE_NAME)
        self.host_store = _store_path(self.host_home, self.reader_lane_name)
        self._host_store_before = _live_snapshot_at(self.host_store)
        self.runtime_manifest = self._runtime_manifest()
        self.runtime_sha256 = _sha256(_canonical(self.runtime_manifest))
        self.admission_id = ADMISSION
        self.dispatch_id = DISPATCH
        self.standing_rows: list[dict] = []
        self.per_job_rows: list[dict] = []
        self.admission_stdout, self.admission_digest = self._install_show(
            ADMISSION,
            kind="lane-policy-admission/v1",
            extra={
                "reader": {
                    "ref": self.reader_ref,
                    "runtime_sha256": self.runtime_sha256,
                },
                "standing_grants": [],
            },
        )

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                f"live store mutated: {LIVE_STORE}",
            )
            if self._live_before[0] == "absent":
                self.assertFalse(LIVE_STORE.exists(), "tests created the live store")
            host_store = getattr(self, "host_store", None)
            if host_store is not None:
                self.assertEqual(
                    _live_snapshot_at(host_store),
                    self._host_store_before,
                    f"pinned-lane store mutated: {host_store}",
                )
        finally:
            for key, value in self._env_before.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            self._tmp.cleanup()

    def plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _write_tree(self, root: Path, files: dict[str, bytes]) -> None:
        for rel, data in files.items():
            self.plant_bytes(root / rel, data)

    def _git_env(self, home: Path) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(home),
            "LC_ALL": "C",
            "LANG": "C",
            "GIT_AUTHOR_NAME": "policy-fixture",
            "GIT_AUTHOR_EMAIL": "policy-fixture@example.test",
            "GIT_COMMITTER_NAME": "policy-fixture",
            "GIT_COMMITTER_EMAIL": "policy-fixture@example.test",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def _git(self, repo: Path, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *argv],
            cwd=str(repo),
            env=self._git_env(self.host_home),
            capture_output=True,
            text=True,
            check=False,
        )

    def _git_init(self, repo: Path) -> str:
        init = self._git(repo, "init")
        self.assertEqual(init.returncode, 0, init.stderr)
        self._git(repo, "config", "user.name", "policy-fixture")
        self._git(repo, "config", "user.email", "policy-fixture@example.test")
        add = self._git(repo, "add", "-A")
        self.assertEqual(add.returncode, 0, add.stderr)
        commit = self._git(repo, "commit", "-m", "fixture")
        self.assertEqual(commit.returncode, 0, commit.stderr)
        sha = self._git(repo, "rev-parse", "HEAD")
        self.assertEqual(sha.returncode, 0, sha.stderr)
        ref = sha.stdout.strip()
        self.assertEqual(len(ref), 40, ref)
        self.assertRegex(ref, r"^[0-9a-f]{40}$")
        return ref

    def _install_reader(self) -> str:
        conf = (
            "LANE_NAME='agentscient-fixture'\n"
            "TRUNK_BRANCH='dev'\n"
            "RELEASE_BRANCH='master'\n"
        )
        self.plant_bytes(self.reader_checkout / "ops" / "lane.conf", conf.encode())
        self.plant_bytes(
            self.reader_checkout / "ops" / "conductor" / "tools" / "laneconf.py",
            b'"""Pinned reader laneconf stand-in."""\nLANE = "fixture"\n',
        )
        show_map = (
            self.reader_checkout / "ops" / "conductor" / "tools" / "show-map.json"
        )
        self.plant_bytes(show_map, b"{}\n")
        provider = (
            "import json, pathlib, sys\n"
            "root = pathlib.Path(__file__).resolve().parent\n"
            "table = json.loads((root / 'show-map.json').read_text())\n"
            "if len(sys.argv) >= 3 and sys.argv[1] == 'show':\n"
            "    body = table.get(sys.argv[2])\n"
            "    if body is None:\n"
            "        sys.stderr.write('unknown: expected planted id; found '\n"
            "                         + sys.argv[2] + '; needed a planted show')\n"
            "        sys.exit(2)\n"
            "    sys.stdout.write(body)\n"
            "    sys.exit(0)\n"
            "sys.stderr.write('arguments: expected show ID; found '\n"
            "                 + ' '.join(sys.argv[1:]) + '; needed show')\n"
            "sys.exit(2)\n"
        )
        self.plant_bytes(
            self.reader_checkout / "ops" / "conductor" / "tools" / "decisions.py",
            provider.encode("utf-8"),
        )
        self.assertFalse((self.reader_checkout / "ops" / "lane.local.conf").exists())
        return self._git_init(self.reader_checkout)

    def _runtime_manifest(self) -> dict[str, str]:
        files = [
            Path(self.admitted_python).resolve(),
            (self.reader_checkout / "ops" / "lane.conf").resolve(),
            (
                self.reader_checkout / "ops" / "conductor" / "tools" / "decisions.py"
            ).resolve(),
            (
                self.reader_checkout / "ops" / "conductor" / "tools" / "laneconf.py"
            ).resolve(),
        ]
        mapping = {}
        for path in files:
            self.assertTrue(path.is_file(), f"runtime file missing: {path}")
            mapping[str(path)] = _sha256(path.read_bytes())
        return mapping

    def _evidence_payload(self, kind: str, extra: dict) -> str:
        payload = {
            "kind": kind,
            "owner_words": OWNER_WORDS,
            "policy": {"ref": self.snapshot_ref, "sha256": self.policy_digest},
        }
        payload.update(extra)
        return f"{OWNER}: {json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)}"

    def _show_bytes(
        self,
        record_id: str,
        *,
        kind: str,
        extra: dict,
        standing: str = "ratified",
        superseded_by: str | None = None,
        note: str | None = None,
        decided_by: str = OWNER,
    ) -> bytes:
        evidence = self._evidence_payload(kind, extra)
        row = {
            "id": record_id,
            "question": "Should this synthetic policy admission stand as recorded",
            "home": POLICY_PATH,
            "standing": standing,
            "blocked_on": None,
            "decided_by": decided_by,
            "decided_at": CHECKED_AT,
            "evidence": evidence,
            "recorded_by": RECORDER,
            "supersedes": None,
            "superseded_by": superseded_by,
            "created_at": CHECKED_AT,
            "created_by": RECORDER,
        }
        events = [
            {
                "id": record_id,
                "timestamp": CHECKED_AT,
                "agent": RECORDER,
                "kind": "ratified",
                "detail": evidence,
            }
        ]
        if note is not None:
            events.append(
                {
                    "id": record_id,
                    "timestamp": "2026-09-06T12:30:00Z",
                    "agent": RECORDER,
                    "kind": "note",
                    "detail": note,
                }
            )
        body = json.dumps(
            {"decision": row, "events": events},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        data = (body + "\n").encode("utf-8")
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(data.count(b"\n"), 1)
        return data

    def _write_show_map(self, mapping: dict[str, str]) -> None:
        path = self.reader_checkout / "ops" / "conductor" / "tools" / "show-map.json"
        payload = json.dumps(mapping, sort_keys=True, indent=2).encode("utf-8")
        self.plant_bytes(path, payload)

    def _install_show(self, record_id: str, *, kind: str, extra: dict, **kwargs):
        stdout = self._show_bytes(record_id, kind=kind, extra=extra, **kwargs)
        digest = _sha256(stdout)
        table = {record_id: stdout.decode("utf-8")}
        for row in self.standing_rows + self.per_job_rows:
            table[row["record"]] = row["stdout"]
        table[record_id] = stdout.decode("utf-8")
        self._write_show_map(table)
        return stdout, digest

    def refresh_admission(self, standing_ids: list[str] | None = None, **kwargs):
        extra = {
            "reader": {
                "ref": self.reader_ref,
                "runtime_sha256": self.runtime_sha256,
            },
            "standing_grants": list([] if standing_ids is None else standing_ids),
        }
        self.admission_stdout, self.admission_digest = self._install_show(
            self.admission_id,
            kind="lane-policy-admission/v1",
            extra=extra,
            **kwargs,
        )
        return self.admission_digest

    def add_standing(self, paths: list[str], record_id: str = STANDING):
        extra = {
            "paths": sorted(paths),
            "purpose": "standing maintenance coverage for the named paths",
        }
        stdout = self._show_bytes(
            record_id, kind="lane-policy-standing/v1", extra=extra
        )
        row = {
            "record": record_id,
            "stdout": stdout.decode("utf-8"),
            "sha256": _sha256(stdout),
            "paths": sorted(paths),
        }
        self.standing_rows = [
            item for item in self.standing_rows if item["record"] != record_id
        ]
        self.standing_rows.append(row)
        self.standing_rows.sort(key=lambda item: item["record"])
        self.refresh_admission([item["record"] for item in self.standing_rows])
        return row

    def add_per_job(
        self,
        paths: list[str],
        record_id: str = PER_JOB,
        *,
        job: str = JOB,
        dispatch: str = DISPATCH,
        lineage: dict | None = None,
    ):
        extra = {
            "paths": sorted(paths),
            "purpose": "per-job coverage for uncovered protected paths",
            "job": job,
            "dispatch": dispatch,
            "lineage": lineage or {"branch": BRANCH, "base_sha": self.snapshot_ref},
        }
        stdout = self._show_bytes(record_id, kind="lane-policy-job/v1", extra=extra)
        row = {
            "record": record_id,
            "stdout": stdout.decode("utf-8"),
            "sha256": _sha256(stdout),
            "paths": sorted(paths),
        }
        self.per_job_rows = [
            item for item in self.per_job_rows if item["record"] != record_id
        ]
        self.per_job_rows.append(row)
        self.per_job_rows.sort(key=lambda item: item["record"])
        table = {self.admission_id: self.admission_stdout.decode("utf-8")}
        for item in self.standing_rows + self.per_job_rows:
            table[item["record"]] = item["stdout"]
        self._write_show_map(table)
        return row

    def commit_policy(self, data: bytes) -> str:
        original = self.policy_bytes
        self.plant_bytes(self.canonical_repo / POLICY_PATH, data)
        landed = (self.canonical_repo / POLICY_PATH).read_bytes()
        self.assertEqual(landed, data)
        self.assertIn(b"agentscient.lane-policy/v1", landed)
        if data != original:
            self.assertNotEqual(landed, original)
        add = self._git(self.canonical_repo, "add", POLICY_PATH)
        self.assertEqual(add.returncode, 0, add.stderr)
        commit = self._git(self.canonical_repo, "commit", "-m", "policy-update")
        self.assertEqual(commit.returncode, 0, commit.stderr)
        sha = self._git(self.canonical_repo, "rev-parse", "HEAD")
        self.snapshot_ref = sha.stdout.strip()
        self.policy_bytes = data
        self.policy_digest = _sha256(data)
        return self.snapshot_ref

    def sources(self, declarations: dict) -> list[dict]:
        rows = []
        mapping = {
            "selection": declarations["selection"],
            "scope": declarations["requested_scope"],
            "job": declarations["job_grants"],
            "role": declarations["role_grants"],
            "adapter": declarations["adapter_grants"],
            "outputs": declarations["outputs"],
            "reservations": declarations["reservations"],
        }
        conductor = declarations["selection"].get("role") == "conductor"
        for component, value in mapping.items():
            if conductor and component in ("outputs", "job"):
                rows.append(
                    {
                        "component": component,
                        "kind": "absent",
                        "path": None,
                        "ref": None,
                        "sha256": None,
                    }
                )
                continue
            raw = _canonical(value)
            rows.append(
                {
                    "component": component,
                    "kind": "invocation",
                    "path": component,
                    "ref": None,
                    "sha256": _sha256(raw),
                }
            )
        rows.sort(
            key=lambda item: (
                item["component"],
                item["kind"],
                item["path"] is None,
                item["path"] or "",
                item["ref"] is None,
                item["ref"] or "",
            )
        )
        return rows

    def declarations(
        self,
        *,
        profile: str | None = "dev",
        role: str = "worker",
        job_role: str | None = "write",
        repository: list[str] | tuple[str, ...] = ("ops/",),
        outputs: list[dict] | None = None,
        output_paths: list[str] | None = None,
        job: list[str] | None = None,
        adapter: list[str] | None = None,
        role_paths: list[str] | None = None,
        missing_key: str | None = None,
    ) -> dict:
        c2 = [] if outputs is None else list(outputs)
        out_paths = output_paths
        if out_paths is None:
            out_paths = [entry["path"] for entry in c2]
        repo = list(repository)
        payload = {
            "selection": {
                "harness": "grok",
                "model": "fixture-model",
                "effort": None,
                "role": role,
                "job_role": job_role,
                "profile": profile,
            },
            "requested_scope": _grant(repo, out_paths),
            "job_grants": _grant(repo if job is None else job, out_paths),
            "role_grants": _grant(
                (
                    []
                    if job_role == "read"
                    else (repo if role_paths is None else role_paths)
                ),
                out_paths,
            ),
            "adapter_grants": _grant(repo if adapter is None else adapter, out_paths),
            "outputs": c2,
            "reservations": ["COMMIT_MSG", "last-message.json"],
        }
        payload["sources"] = self.sources(payload)
        if missing_key is not None:
            payload.pop(missing_key, None)
        return payload

    def conductor_declarations(self, profile: str = "dev") -> dict:
        return self.declarations(
            profile=profile,
            role="conductor",
            job_role=None,
            repository=(),
            outputs=[],
            job=[],
            adapter=[],
            role_paths=[],
        )

    def maintenance_binding(self) -> dict | None:
        if not self.standing_rows and not self.per_job_rows:
            return None
        return {
            "standing": [
                {"record": row["record"], "sha256": row["sha256"]}
                for row in self.standing_rows
            ],
            "per_job": [
                {"record": row["record"], "sha256": row["sha256"]}
                for row in self.per_job_rows
            ],
        }

    def grants_object(self, declarations: dict, maintenance: dict | None) -> dict:
        outputs = sorted({entry["path"] for entry in declarations["outputs"]})
        if maintenance is None:
            paths: list[str] = []
        else:
            paths = []
            for row in self.standing_rows + self.per_job_rows:
                paths.extend(row["paths"])
            paths = sorted(set(paths))
        return {
            "adapter": declarations["adapter_grants"],
            "job": declarations["job_grants"],
            "maintenance": paths,
            "outputs": {"outputs": outputs, "repository": []},
            "role": declarations["role_grants"],
            "scope": declarations["requested_scope"],
        }

    def grants_digest(self, declarations: dict, maintenance: dict | None) -> str:
        payload = self.grants_object(declarations, maintenance)
        raw = _canonical(payload)
        self.assertFalse(raw.endswith(b"\n"))
        return _sha256(raw)

    def trusted_context(
        self,
        *,
        profile: str | None = "dev",
        selection: bool = True,
        job: str | None = JOB,
        stage: str = STAGE,
        dispatch_id: str | None = None,
        parent_binding: object | None = None,
        default_profile: str | None = None,
        declaration_profile: str | None = None,
    ) -> dict:
        chosen = None
        if selection:
            chosen = {"profile": profile, "provenance": "explicit"}
        return {
            "custody_anchor": {
                "owner": OWNER,
                "host_home": str(self.host_home),
                "repository": str(self.canonical_repo),
                "admission_id": self.admission_id,
                "consumer_revision": self.consumer_ref,
                "reader": {
                    "ref": self.reader_ref,
                    "runtime_sha256": self.runtime_sha256,
                },
            },
            "reader": {
                "ref": self.reader_ref,
                "runtime_sha256": self.runtime_sha256,
                "checkout": str(self.reader_checkout),
                "python": self.admitted_python,
                "runtime_manifest": self.runtime_manifest,
            },
            "register_evidence": {
                "admission": {
                    "record": self.admission_id,
                    "stdout": self.admission_stdout.decode("utf-8"),
                    "sha256": self.admission_digest,
                },
                "standing": [
                    {
                        "record": row["record"],
                        "stdout": row["stdout"],
                        "sha256": row["sha256"],
                    }
                    for row in self.standing_rows
                ],
                "per_job": [
                    {
                        "record": row["record"],
                        "stdout": row["stdout"],
                        "sha256": row["sha256"],
                    }
                    for row in self.per_job_rows
                ],
            },
            "repository": str(self.canonical_repo),
            "job_root": str(self.job_root),
            "dispatch_id": dispatch_id or self.dispatch_id,
            "job": job,
            "stage": stage,
            "snapshot_ref": self.snapshot_ref,
            "lineage": {"branch": BRANCH, "base_sha": self.snapshot_ref},
            "selection": chosen,
            "parent_binding": parent_binding,
            "default_profile": default_profile,
            "declaration_profile": declaration_profile,
            "template": {
                "path": CONDUCTOR_TEMPLATE_REL if stage == "conduct" else TEMPLATE_REL,
                "sha256": (
                    self.conductor_template_digest
                    if stage == "conduct"
                    else self.template_digest
                ),
            },
        }

    def bind(self, context, declarations):
        before = _tree_listing(self.job_root)
        fn = getattr(self.library, "bind_launch", None)
        if not callable(fn):
            return None
        try:
            result = fn(context, declarations)
        except Exception as exc:
            result = exc
        after = _tree_listing(self.job_root)
        self._bind_tree_before = before
        self._bind_tree_after = after
        return result

    def check(self, binding, evidence, transition):
        fn = getattr(self.library, "check_transition", None)
        if not callable(fn):
            return None
        try:
            return fn(binding, evidence, transition)
        except Exception as exc:
            return exc

    def evaluate(self, bound_role, request):
        fn = getattr(self.library, "evaluate_tool", None)
        if not callable(fn):
            return None
        try:
            return fn(bound_role, request)
        except Exception as exc:
            return exc

    def assert_refusal(self, result, class_name: str) -> str:
        text = _refusal_text(result)
        self.assertTrue(
            text,
            f"expected {class_name} refusal, got {result!r}",
        )
        self.assertRegex(text, REFUSAL_LINE)
        self.assertTrue(
            text.startswith(class_name + ":"),
            f"expected class {class_name!r} in {text!r}",
        )
        self.assertIn("expected ", text)
        self.assertIn("; found ", text)
        self.assertIn("; needed ", text)
        return text

    def assert_not_refusal(self, result) -> None:
        text = _refusal_text(result)
        self.assertFalse(
            text and REFUSAL_LINE.match(text),
            f"unexpected refusal {text!r} from {result!r}",
        )
        self.assertIsNotNone(result)
        self.assertFalse(isinstance(result, BaseException), result)

    def extract_policy(self, result) -> dict:
        mapping = _as_object(result)
        self.assertIsInstance(mapping, dict, result)
        if set(POLICY_BINDING_KEYS) <= set(mapping):
            return {key: mapping[key] for key in POLICY_BINDING_KEYS}
        if "policy" in mapping and isinstance(mapping["policy"], dict):
            return mapping["policy"]
        brief = mapping.get("brief")
        if isinstance(brief, dict) and isinstance(brief.get("policy"), dict):
            return brief["policy"]
        handle = mapping.get("binding")
        if isinstance(handle, dict) and set(POLICY_BINDING_KEYS) <= set(handle):
            return {key: handle[key] for key in POLICY_BINDING_KEYS}
        self.fail(f"bound context has no policy binding: {result!r}")

    def assert_worker_binding(
        self, result, *, profile: str, declarations: dict
    ) -> dict:
        self.assert_not_refusal(result)
        policy = self.extract_policy(result)
        self.assertEqual(sorted(policy), sorted(POLICY_BINDING_KEYS))
        self.assertEqual(policy["schema"], SCHEMA)
        self.assertEqual(policy["path"], POLICY_PATH)
        self.assertEqual(policy["ref"], self.snapshot_ref)
        self.assertEqual(policy["sha256"], self.policy_digest)
        self.assertEqual(
            policy["admission"],
            {"record": self.admission_id, "sha256": self.admission_digest},
        )
        self.assertEqual(policy["profile"], profile)
        self.assertEqual(policy["template_sha256"], self.template_digest)
        maintenance = self.maintenance_binding()
        self.assertEqual(policy["maintenance"], maintenance)
        expected = self.grants_digest(declarations, maintenance)
        self.assertEqual(policy["grants_sha256"], expected)
        self.assertEqual(len(policy["grants_sha256"]), 64)
        self.assertRegex(policy["grants_sha256"], r"^[0-9a-f]{64}$")
        return policy

    def conductor_binding_digest(self, binding: dict) -> str:
        closed = {key: binding[key] for key in CONDUCTOR_BINDING_KEYS}
        raw = _canonical(closed)
        self.assertFalse(raw.endswith(b"\n"))
        digest = _sha256(raw)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        return digest

    def assert_conductor_binding(
        self,
        result,
        *,
        declarations: dict,
        dispatch_id: str,
    ) -> tuple[dict, str]:
        self.assert_not_refusal(result)
        mapping = _as_object(result)
        self.assertIsInstance(mapping, dict, result)
        self.assertEqual(sorted(mapping), sorted(CONDUCTOR_BINDING_KEYS), mapping)
        policy = mapping["policy"]
        self.assertIsInstance(policy, dict, policy)
        self.assertEqual(sorted(policy), sorted(POLICY_BINDING_KEYS), policy)
        self.assertIsNone(mapping["job"])
        self.assertEqual(mapping["stage"], "conduct")
        self.assertEqual(mapping["dispatch"], dispatch_id)
        selection = mapping["selection"]
        self.assertIsInstance(selection, dict, selection)
        self.assertEqual(
            sorted(selection),
            ["effort", "harness", "job_role", "model", "profile", "role"],
        )
        self.assertEqual(selection["role"], "conductor")
        self.assertIsNone(selection["job_role"])
        self.assertEqual(selection["profile"], declarations["selection"]["profile"])
        self.assertEqual(mapping["snapshot_ref"], self.snapshot_ref)
        self.assertEqual(
            mapping["lineage"],
            {"branch": BRANCH, "base_sha": self.snapshot_ref},
        )
        self.assertEqual(
            mapping["template"],
            {
                "path": CONDUCTOR_TEMPLATE_REL,
                "sha256": self.conductor_template_digest,
            },
        )
        self.assertEqual(policy["template_sha256"], mapping["template"]["sha256"])
        self.assertEqual(
            mapping["declarations_sha256"],
            _sha256(_canonical(declarations)),
        )
        self.assertIsInstance(mapping["custody_sha256"], str)
        self.assertEqual(len(mapping["custody_sha256"]), 64)
        self.assertRegex(mapping["custody_sha256"], r"^[0-9a-f]{64}$")
        digest = self.conductor_binding_digest(mapping)
        self.assertNotEqual(digest, policy["grants_sha256"])
        self.assertNotEqual(digest, mapping["declarations_sha256"])
        self.assertNotEqual(digest, mapping["custody_sha256"])
        self.assertNotEqual(digest, policy["sha256"])
        return mapping, digest

    def assert_policy_result(self, result, *, outcome: str) -> dict:
        mapping = _as_object(result)
        self.assertIsInstance(mapping, dict, result)
        self.assertEqual(sorted(mapping), sorted(POLICY_RESULT_KEYS), mapping)
        self.assertEqual(mapping["outcome"], outcome)
        self.assertIsInstance(mapping["checked_at"], str, mapping)
        self.assertRegex(mapping["checked_at"], CHECKED_AT_UTC)
        self.assertTrue(mapping["checked_at"].endswith("Z"))
        self.assertNotIn("+", mapping["checked_at"][:-1])
        self.assertNotIn(".", mapping["checked_at"])
        if outcome == "pass":
            self.assertIsNone(mapping["refusal"])
            for key in ("artifacts", "dependencies", "outputs"):
                self.assertIsInstance(mapping[key], dict, key)
                self.assertEqual(sorted(mapping[key]), ["path", "sha256"], mapping[key])
                self.assertRegex(mapping[key]["sha256"], r"^[0-9a-f]{64}$")
            self.assertIsNotNone(mapping["head"])
        else:
            self.assertIsInstance(mapping["refusal"], str)
            self.assertRegex(mapping["refusal"], REFUSAL_LINE)
        self.assertEqual(mapping["snapshot_ref"], self.snapshot_ref)
        return mapping

    def artifact_entry(
        self,
        path: str,
        content: bytes,
        *,
        layer: str = "worktree",
        status: str = "A",
        mode: str = "100644",
        before_path: str | None = None,
    ) -> dict:
        after = {
            "path_b64": _path_b64(path),
            "mode": mode,
            "sha256": _sha256(content),
        }
        before = None
        if status in ("M", "T", "R", "C", "D"):
            before = {
                "path_b64": _path_b64(before_path or path),
                "mode": mode,
                "sha256": _sha256(content),
            }
        if status == "D":
            after = None
        if status in ("A", "?", "!"):
            before = None
        return {
            "layer": layer,
            "status": status,
            "before": before,
            "after": after,
        }

    def manifest(self, entries: list[dict], head: str | None = None) -> dict:
        return {
            "snapshot_ref": self.snapshot_ref,
            "head": self.snapshot_ref if head is None else head,
            "entries": entries,
        }

    def dependencies(
        self,
        manifest: dict,
        *,
        coverage: list[str],
        edges: list[dict] | None = None,
        unresolved: list[dict] | None = None,
        unavailable: str | None = None,
    ) -> dict:
        return {
            "snapshot_ref": manifest["snapshot_ref"],
            "head": manifest["head"],
            "artifacts_sha256": _sha256(_canonical(manifest)),
            "producer": {
                "component": "dependencies",
                "kind": "invocation",
                "path": "dependencies",
                "ref": None,
                "sha256": _sha256(b"fixture-analyzer"),
            },
            "coverage": sorted(set(coverage)),
            "edges": list([] if edges is None else edges),
            "unresolved": list([] if unresolved is None else unresolved),
            "unavailable": unavailable,
        }

    def output_attempt(
        self,
        *,
        attempt: int | None = None,
        files: list | None = None,
        dispatch: str | None = None,
    ) -> dict:
        return {
            "dispatch": self.dispatch_id if dispatch is None else dispatch,
            "attempt": attempt,
            "files": list([] if files is None else files),
        }

    def retained_handle(self, rel: str, content: bytes) -> dict:
        self.plant_bytes(self.job_root / rel, content)
        return {"path": rel, "sha256": _sha256(content)}

    def file_receipt(
        self,
        content: bytes,
        *,
        artifact: str,
        path: str,
        production: str = "fresh",
        reuse: dict | None = None,
        evidence: list | None = None,
    ) -> dict:
        digest = _sha256(content)
        handles = (
            list(evidence)
            if evidence is not None
            else [self.retained_handle(f"evidence/{path}", content)]
        )
        receipt = {
            "artifact": artifact,
            "path": path,
            "sha256": digest,
            "bytes": len(content),
            "production": production,
            "reuse": reuse,
            "evidence": handles,
        }
        self.assertEqual(sorted(receipt), sorted(FILE_RECEIPT_KEYS), receipt)
        self.assertGreater(receipt["bytes"], 0)
        self.assertRegex(receipt["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(receipt["evidence"], "file receipt evidence must be nonempty")
        if production == "fresh":
            self.assertIsNone(receipt["reuse"])
        else:
            self.assertEqual(production, "reuse")
            self.assertIsInstance(receipt["reuse"], dict)
            self.assertEqual(sorted(receipt["reuse"]), ["attempt", "receipt"])
        return receipt

    def evidence(
        self,
        *,
        entries: list[dict] | None = None,
        coverage: list[str] | None = None,
        edges: list[dict] | None = None,
        unresolved: list[dict] | None = None,
        unavailable: str | None = None,
        outputs: dict | None = None,
        head: str | None = None,
        artifacts=None,
        dependencies=None,
        allow_null: bool = False,
        completed: bool = True,
        files: list | None = None,
        attempt: int | None = None,
        dispatch: str | None = None,
    ) -> dict:
        if allow_null:
            return {
                "snapshot_ref": self.snapshot_ref,
                "head": head,
                "artifacts": artifacts,
                "dependencies": dependencies,
                "outputs": outputs,
            }
        manifest = self.manifest([] if entries is None else entries, head=head)
        required = coverage
        if required is None:
            required = sorted(
                {
                    self._decode_path(entry.get("after") or entry.get("before") or {})
                    for entry in manifest["entries"]
                }
            )
        deps = self.dependencies(
            manifest,
            coverage=required,
            edges=edges,
            unresolved=unresolved,
            unavailable=unavailable,
        )
        if outputs is None:
            if completed:
                outputs = self.output_attempt(
                    attempt=1 if attempt is None else attempt,
                    files=[] if files is None else files,
                    dispatch=dispatch,
                )
            else:
                outputs = self.output_attempt(
                    attempt=None,
                    files=[],
                    dispatch=dispatch,
                )
        return {
            "snapshot_ref": self.snapshot_ref,
            "head": manifest["head"],
            "artifacts": manifest,
            "dependencies": deps,
            "outputs": outputs,
        }

    def _decode_path(self, endpoint: dict) -> str:
        raw = endpoint.get("path_b64") or ""
        if not raw:
            return ""
        return base64.b64decode(raw.encode("ascii")).decode("utf-8")

    def bind_ok(self, *, profile="dev", **kwargs):
        decls = kwargs.pop("declarations", None) or self.declarations(
            profile=profile, **kwargs
        )
        context = self.trusted_context(profile=profile)
        result = self.bind(context, decls)
        policy = self.assert_worker_binding(result, profile=profile, declarations=decls)
        return result, decls, policy

    def check_writes(self, binding, paths_and_bytes, **kwargs):
        entries = [
            self.artifact_entry(path, content, **kwargs)
            for path, content in paths_and_bytes
        ]
        coverage = [path for path, _content in paths_and_bytes]
        return self.check(
            binding, self.evidence(entries=entries, coverage=coverage), "settle"
        )


def _tree_listing(root: Path) -> tuple[str, ...]:
    names = []
    for path in root.rglob("*"):
        if path.is_file() or path.is_symlink():
            names.append(str(path.relative_to(root)))
    return tuple(sorted(names))


class ToolPresence(_LanePolicyCase):
    def test_the_library_file_is_present(self):
        self.assertTrue(LIBRARY.is_file(), f"RED: library is absent: {LIBRARY}")

    def test_public_functions_are_callable(self):
        self.assertFalse(
            isinstance(self.library, _AbsentLibrary),
            "RED: loaded the absent stand-in, not ops/conductor/tools/lane_policy.py",
        )
        for name in ("bind_launch", "check_transition", "evaluate_tool"):
            self.assertTrue(
                callable(getattr(self.library, name, None)),
                f"RED: {name} is not a public callable",
            )


class CasesP1(_LanePolicyCase):
    def test_p1_dev_writes_ordinary_tooling_without_maintenance(self):
        binding, _decls, policy = self.bind_ok(profile="dev")
        self.assertIsNone(policy["maintenance"])
        result = self.check_writes(
            binding,
            [
                ("ops/bin/example.sh", self.example_sh),
                ("ops/devlane/hooks/claude/example.py", self.hook_py),
            ],
        )
        mapping = self.assert_policy_result(result, outcome="pass")
        self.assertEqual(mapping["binding"], policy)

    def test_p1_dev_reads_docs_and_application_source(self):
        decls = self.declarations(profile="dev", job_role="read", repository=())
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        self.assert_worker_binding(binding, profile="dev", declarations=decls)
        evidence = self.evidence(
            entries=[],
            coverage=["docs/wire.md", "src/Example.php"],
            completed=False,
        )
        mapping = self.assert_policy_result(
            self.check(binding, evidence, "launch"),
            outcome="pass",
        )
        self.assertEqual(mapping["head"], self.snapshot_ref)

    def test_p1_operable_with_application_and_vendor_absent(self):
        for rel in ("src/Example.php", "composer.json"):
            (self.canonical_repo / rel).unlink()
        self.assertFalse((self.canonical_repo / "vendor").exists())
        self.assertFalse((self.canonical_repo / "src" / "Example.php").exists())
        binding, _decls, _policy = self.bind_ok(profile="dev")
        result = self.check_writes(binding, [("ops/bin/example.sh", self.example_sh)])
        self.assert_policy_result(result, outcome="pass")


class CasesP2(_LanePolicyCase):
    def test_p2_prod_writes_application_and_composer(self):
        binding, _decls, _policy = self.bind_ok(
            profile="prod",
            repository=("src/", "composer.json"),
        )
        result = self.check_writes(
            binding,
            [
                ("src/Example.php", self.example_php),
                ("composer.json", b"{}\n"),
            ],
        )
        self.assert_policy_result(result, outcome="pass")

    def test_p2_dev_refuses_application_and_composer(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        for path, content in (
            ("src/Example.php", self.example_php),
            ("composer.json", b"{}\n"),
        ):
            with self.subTest(path=path):
                result = self.check_writes(binding, [(path, content)])
                mapping = self.assert_policy_result(result, outcome="refused")
                self.assert_refusal(mapping, "lane-write")
                self.assertIn(path, mapping["refusal"])

    def test_p2_prod_refuses_ops_write(self):
        binding, _decls, _policy = self.bind_ok(
            profile="prod",
            repository=("src/", "ops/"),
        )
        result = self.check_writes(binding, [("ops/bin/example.sh", self.example_sh)])
        mapping = self.assert_policy_result(result, outcome="refused")
        self.assert_refusal(mapping, "lane-write")
        self.assertIn("ops/bin/example.sh", mapping["refusal"])


class CasesP3(_LanePolicyCase):
    def test_p3_fixture_only_profile_under_admitted_fixture_policy(self):
        tracked_before = TRACKED_POLICY.read_bytes()
        policy = json.loads(self.policy_bytes)
        policy["profiles"]["fixture-only"] = {
            "write_roots": ["unittest/"],
            "forbidden_dependency_roots": ["vendor/"],
            "authority_maintenance": False,
            "allow_declared_outputs": False,
        }
        data = (json.dumps(policy, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.plant_bytes(self.canonical_repo / POLICY_PATH, data)
        self.assertIn(b'"fixture-only"', data)
        self.assertNotEqual(data, tracked_before)
        self.commit_policy(data)
        self.refresh_admission([])
        binding, _decls, _policy = self.bind_ok(
            profile="fixture-only",
            repository=("unittest/",),
        )
        ok = self.check_writes(binding, [("unittest/example.txt", b"fixture-only\n")])
        self.assert_policy_result(ok, outcome="pass")
        src = self.check_writes(binding, [("src/Example.php", self.example_php)])
        self.assert_refusal(
            self.assert_policy_result(src, outcome="refused"), "lane-write"
        )
        out_decls = self.declarations(
            profile="fixture-only",
            repository=("unittest/",),
            outputs=[{"kind": "file", "path": "OUT.md", "artifact": "out"}],
        )
        out_binding = self.bind(self.trusted_context(profile="fixture-only"), out_decls)
        self.assert_worker_binding(
            out_binding, profile="fixture-only", declarations=out_decls
        )
        out_entries = [
            self.artifact_entry(
                "OUT.md",
                b"external\n",
                layer="output",
            )
        ]
        refused = self.check(
            out_binding,
            self.evidence(entries=out_entries, coverage=["OUT.md"]),
            "settle",
        )
        mapping = self.assert_policy_result(refused, outcome="refused")
        self.assert_refusal(mapping, "lane-write")
        self.assertEqual(TRACKED_POLICY.read_bytes(), tracked_before)
        tracked = json.loads(tracked_before)
        self.assertNotIn("fixture-only", tracked["profiles"])


class CasesP4(_LanePolicyCase):
    def test_p4_standing_grant_covers_two_jobs_without_fresh_owner_act(self):
        standing = self.add_standing(["docs/", "ops/lane-policy.json"])
        first_digest = standing["sha256"]
        binding_a, _decls_a, policy_a = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertEqual(policy_a["maintenance"]["standing"][0]["record"], STANDING)
        self.assertEqual(policy_a["maintenance"]["standing"][0]["sha256"], first_digest)
        result_a = self.check_writes(
            binding_a,
            [
                ("ops/lane-policy.json", self.policy_bytes),
                ("docs/wire.md", b"# wire fixture\n"),
            ],
        )
        self.assert_policy_result(result_a, outcome="pass")
        decls_b = self.declarations(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        context_b = self.trusted_context(
            profile="authority-maintenance",
            job="implement",
            dispatch_id=DISPATCH_B,
        )
        binding_b = self.bind(context_b, decls_b)
        policy_b = self.assert_worker_binding(
            binding_b,
            profile="authority-maintenance",
            declarations=decls_b,
        )
        self.assertEqual(policy_b["admission"]["record"], ADMISSION)
        self.assertEqual(policy_b["maintenance"]["standing"][0]["sha256"], first_digest)
        result_b = self.check_writes(
            binding_b,
            [("docs/wire.md", b"# wire fixture\n")],
        )
        self.assert_policy_result(result_b, outcome="pass")
        self.assertEqual(self.standing_rows[0]["sha256"], first_digest)

    def test_p4_uncovered_path_refuses_without_per_job_and_passes_with_exact_row(self):
        self.add_standing(["docs/", "ops/lane-policy.json"])
        binding, _decls, policy = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertEqual(policy["maintenance"]["per_job"], [])
        refused = self.check_writes(binding, [("ops/README.md", b"# ops fixture\n")])
        self.assert_refusal(
            self.assert_policy_result(refused, outcome="refused"),
            "lane-write",
        )
        self.add_per_job(["ops/README.md"])
        covered, _decls, policy2 = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertEqual(policy2["maintenance"]["per_job"][0]["record"], PER_JOB)
        mixed = self.check_writes(
            covered,
            [
                ("ops/lane-policy.json", self.policy_bytes),
                ("ops/README.md", b"# ops fixture\n"),
            ],
        )
        self.assert_policy_result(mixed, outcome="pass")

    def test_p4_identical_edits_without_grants_refuse(self):
        binding, _decls, policy = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertIsNone(policy["maintenance"])
        result = self.check_writes(
            binding,
            [
                ("ops/lane-policy.json", self.policy_bytes),
                ("docs/wire.md", b"# wire fixture\n"),
            ],
        )
        self.assert_refusal(
            self.assert_policy_result(result, outcome="refused"),
            "lane-write",
        )


class CasesP5(_LanePolicyCase):
    def test_p5_candidate_reader_edits_pass_as_artifacts_but_are_not_authority(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        candidate = b'"""candidate decisions.py must not be the reader"""\n'
        seed = b'{"rows":[]}\n'
        result = self.check_writes(
            binding,
            [
                ("ops/conductor/tools/decisions.py", candidate),
                ("ops/conductor/decisions.seed.json", seed),
            ],
        )
        self.assert_policy_result(result, outcome="pass")
        self.plant_bytes(
            self.candidate_tree / "ops" / "conductor" / "tools" / "decisions.py",
            candidate,
        )
        forged_home = self.worker_home / ".local" / "state" / self.reader_lane_name
        forged_home.mkdir(parents=True)
        self.plant_bytes(forged_home / "decisions.db", b"forged-store")
        admitted = (
            self.reader_checkout / "ops" / "conductor" / "tools" / "decisions.py"
        ).read_bytes()
        self.assertNotEqual(admitted, candidate)
        self.assertIn(b"show-map.json", admitted)
        self.assertEqual(
            (forged_home / "decisions.db").read_bytes(),
            b"forged-store",
        )
        context = self.trusted_context(profile="dev")
        context["repository"] = str(self.candidate_tree)
        rebound = self.bind(context, self.declarations(profile="dev"))
        self.assert_refusal(rebound, "lane-policy")


class CasesN1(_LanePolicyCase):
    def test_n1_absent_selection_without_default_refuses_lane_profile(self):
        decls = self.declarations(profile=None)
        result = self.bind(self.trusted_context(selection=False, profile=None), decls)
        self.assert_refusal(result, "lane-profile")
        self.assertEqual(self._bind_tree_after, self._bind_tree_before)
        self.assertEqual(self._bind_tree_after, ())

    def test_n1_unknown_empty_and_conflict_refuse_and_do_not_fall_back(self):
        cases = (
            ("unknown", self.declarations(profile="no-such"), True, "no-such"),
            ("empty", self.declarations(profile=""), True, ""),
            (
                "conflict",
                self.declarations(profile="prod"),
                True,
                "dev",
            ),
        )
        for label, decls, present, profile in cases:
            with self.subTest(label=label):
                context = self.trusted_context(profile=profile, selection=present)
                result = self.bind(context, decls)
                self.assert_refusal(result, "lane-profile")
        default_policy = json.loads(self.policy_bytes)
        default_policy["default_profile"] = "dev"
        data = (json.dumps(default_policy, indent=2, sort_keys=True) + "\n").encode()
        self.commit_policy(data)
        self.refresh_admission([])
        valid = self.bind(
            self.trusted_context(selection=False, default_profile="dev"),
            self.declarations(profile=None),
        )
        self.assert_worker_binding(
            valid,
            profile="dev",
            declarations=self.declarations(profile=None),
        )
        invalid = self.bind(
            self.trusted_context(profile="no-such", default_profile="dev"),
            self.declarations(profile="no-such"),
        )
        self.assert_refusal(invalid, "lane-profile")


class CasesN2(_LanePolicyCase):
    def test_n2_environment_laneconf_and_scope_text_cannot_move_authority(self):
        other = json.loads(self.policy_bytes)
        other["profiles"]["dev"]["write_roots"] = ["src/"]
        planted = (json.dumps(other, indent=2) + "\n").encode()
        env_path = self.worker_home / "moved-policy.json"
        self.plant_bytes(env_path, planted)
        self.assertNotEqual(planted, self.policy_bytes)
        os.environ["LANE_POLICY_PATH"] = str(env_path)
        os.environ["LANE_CONF"] = str(self.worker_home / "lane.conf")
        os.environ["LANE_NAME"] = "moved"
        decls = self.declarations(profile="dev")
        decls["requested_scope"] = _grant(["src/"])
        context = self.trusted_context(profile="dev")
        binding = self.bind(context, decls)
        policy = self.assert_worker_binding(binding, profile="dev", declarations=decls)
        self.assertEqual(policy["path"], POLICY_PATH)
        self.assertEqual(policy["sha256"], self.policy_digest)
        widened = self.check_writes(binding, [("src/Example.php", self.example_php)])
        self.assert_refusal(
            self.assert_policy_result(widened, outcome="refused"),
            "lane-write",
        )

    def test_n2_candidate_policy_widening_cannot_permit_its_own_product_write(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        widened = json.loads(self.policy_bytes)
        widened["profiles"]["dev"]["write_roots"] = ["ops/", "src/"]
        candidate = (json.dumps(widened, indent=2) + "\n").encode()
        result = self.check_writes(
            binding,
            [
                (POLICY_PATH, candidate),
                ("src/Example.php", self.example_php),
            ],
        )
        mapping = self.assert_policy_result(result, outcome="refused")
        self.assert_refusal(mapping, "lane-write")


class CasesN3(_LanePolicyCase):
    def test_n3_runtime_vendor_app_service_and_console_refuse(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        manifest = self.manifest(
            [self.artifact_entry("ops/bin/example.sh", self.example_sh)]
        )
        edges = (
            {
                "source_b64": _path_b64("ops/conductor/tools/example.py"),
                "kind": "import",
                "target_space": "repository",
                "target_root": "vendor/",
            },
            {
                "source_b64": _path_b64("ops/conductor/tools/example.py"),
                "kind": "service",
                "target_space": "repository",
                "target_root": "src/",
            },
            {
                "source_b64": _path_b64("ops/conductor/tools/example.py"),
                "kind": "subprocess",
                "target_space": "repository",
                "target_root": "bin/",
            },
        )
        for edge in edges:
            with self.subTest(kind=edge["kind"]):
                deps = self.dependencies(
                    manifest,
                    coverage=["ops/bin/example.sh", "ops/conductor/tools/example.py"],
                    edges=[edge],
                )
                evidence = {
                    "snapshot_ref": self.snapshot_ref,
                    "head": self.snapshot_ref,
                    "artifacts": manifest,
                    "dependencies": deps,
                    "outputs": self.output_attempt(attempt=1, files=[]),
                }
                mapping = self.assert_policy_result(
                    self.check(binding, evidence, "settle"),
                    outcome="refused",
                )
                self.assert_refusal(mapping, "lane-dependency")

    def test_n3_textual_inspection_of_vendor_citation_passes(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        citation = b"See vendor/autoload.php as a citation, not a runtime edge.\n"
        result = self.check_writes(
            binding,
            [("ops/conductor/notes/citation.md", citation)],
        )
        self.assert_policy_result(result, outcome="pass")

    def test_n3_unresolved_unavailable_and_incomplete_coverage_refuse(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        manifest = self.manifest(
            [self.artifact_entry("ops/bin/example.sh", self.example_sh)]
        )
        unresolved = self.dependencies(
            manifest,
            coverage=["ops/bin/example.sh"],
            unresolved=[
                {
                    "source_b64": _path_b64("ops/bin/example.sh"),
                    "kind": "import",
                    "reason": "parser could not resolve the import",
                }
            ],
        )
        mapping = self.assert_policy_result(
            self.check(
                binding,
                {
                    "snapshot_ref": self.snapshot_ref,
                    "head": self.snapshot_ref,
                    "artifacts": manifest,
                    "dependencies": unresolved,
                    "outputs": self.output_attempt(attempt=1, files=[]),
                },
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-dependency")
        unavailable = self.dependencies(
            manifest,
            coverage=["ops/bin/example.sh"],
            unavailable="analyzer was not admitted for this candidate",
        )
        mapping = self.assert_policy_result(
            self.check(
                binding,
                {
                    "snapshot_ref": self.snapshot_ref,
                    "head": self.snapshot_ref,
                    "artifacts": manifest,
                    "dependencies": unavailable,
                    "outputs": self.output_attempt(attempt=1, files=[]),
                },
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-dependency")
        empty_incomplete = self.dependencies(
            manifest,
            coverage=[],
            edges=[],
            unresolved=[],
            unavailable=None,
        )
        mapping = self.assert_policy_result(
            self.check(
                binding,
                {
                    "snapshot_ref": self.snapshot_ref,
                    "head": self.snapshot_ref,
                    "artifacts": manifest,
                    "dependencies": empty_incomplete,
                    "outputs": self.output_attempt(attempt=1, files=[]),
                },
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-dependency")


class CasesN4(_LanePolicyCase):
    def test_n4_committed_untracked_ignored_rename_symlink_and_cache_refuse(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        cases = (
            (
                "committed",
                self.artifact_entry(
                    "src/Example.php", self.example_php, layer="committed"
                ),
            ),
            (
                "untracked",
                self.artifact_entry("src/sneak.php", self.example_php, status="?"),
            ),
            (
                "ignored",
                self.artifact_entry("src/ignored.php", self.example_php, status="!"),
            ),
            (
                "rename",
                self.artifact_entry(
                    "src/Renamed.php",
                    self.example_php,
                    status="R",
                    before_path="ops/bin/example.sh",
                ),
            ),
            (
                "symlink",
                self.artifact_entry(
                    "ops/escape",
                    b"src/Example.php",
                    mode="120000",
                ),
            ),
            (
                "cache-source",
                self.artifact_entry(
                    "ops/devlane/dispatch/.cache/Example.php",
                    self.example_php,
                ),
            ),
        )
        for label, entry in cases:
            with self.subTest(label=label):
                mapping = self.assert_policy_result(
                    self.check(
                        binding,
                        self.evidence(entries=[entry], coverage=["src/Example.php"]),
                        "settle",
                    ),
                    outcome="refused",
                )
                self.assert_refusal(mapping, "lane-write")


class CasesN5(_LanePolicyCase):
    def test_n5_ok_approve_exit_zero_and_collected_cannot_override_missing_policy(self):
        old_record = {
            "id": "20260901T000000Z-tests-grok-legacy1",
            "status": "ok",
            "verdict": "approve",
            "exit": 0,
            "collected": True,
        }
        record_path = self.job_root / "legacy.json"
        payload = json.dumps(old_record).encode()
        self.plant_bytes(record_path, payload)
        for transition in ("land", "ladder", "collect-after"):
            with self.subTest(transition=transition):
                mapping = self.assert_policy_result(
                    self.check(
                        None,
                        self.evidence(
                            allow_null=True,
                            artifacts=None,
                            dependencies=None,
                            outputs=None,
                            head=None,
                        ),
                        transition,
                    ),
                    outcome="refused",
                )
                self.assertTrue(
                    mapping["refusal"].startswith("lane-policy:")
                    or mapping["refusal"].startswith("lane-artifact:")
                    or mapping["refusal"].startswith("lane-resume:"),
                    mapping["refusal"],
                )
                self.assertIsNone(mapping["artifacts"])
                self.assertIsNone(mapping["dependencies"])
        self.assertEqual(record_path.read_bytes(), payload)


class CasesN6(_LanePolicyCase):
    def test_n6_missing_output_declaration_gives_no_output_grant(self):
        decls = self.declarations(profile="dev", outputs=[])
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        policy = self.assert_worker_binding(binding, profile="dev", declarations=decls)
        self.assertEqual(
            json.loads(self._grants_json(decls, None))["outputs"]["outputs"], []
        )
        self.assertIsNone(policy["maintenance"])
        result = self.check(
            binding,
            self.evidence(
                entries=[self.artifact_entry("SKEPTIC.md", b"nope\n", layer="output")],
                coverage=["SKEPTIC.md"],
            ),
            "settle",
        )
        self.assert_refusal(
            self.assert_policy_result(result, outcome="refused"),
            "lane-write",
        )

    def _grants_json(self, declarations, maintenance):
        return _canonical(self.grants_object(declarations, maintenance)).decode()

    def test_n6_read_snapshot_stays_immutable_with_declared_out(self):
        decls = self.declarations(
            profile="dev",
            job_role="read",
            repository=(),
            outputs=[{"kind": "file", "path": "NOTE.md", "artifact": "note"}],
        )
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        self.assert_worker_binding(binding, profile="dev", declarations=decls)
        mutated = self.check(
            binding,
            self.evidence(
                entries=[self.artifact_entry("ops/bin/example.sh", b"changed\n")],
                coverage=["ops/bin/example.sh"],
            ),
            "settle",
        )
        self.assert_refusal(
            self.assert_policy_result(mutated, outcome="refused"),
            "lane-write",
        )

    def test_n6_missing_job_or_adapter_scope_never_widens(self):
        decls = self.declarations(profile="dev", job=[], adapter=[])
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        self.assert_worker_binding(binding, profile="dev", declarations=decls)
        result = self.check_writes(binding, [("ops/bin/example.sh", self.example_sh)])
        self.assert_refusal(
            self.assert_policy_result(result, outcome="refused"),
            "lane-write",
        )


class CasesN7(_LanePolicyCase):
    def test_n7_dev_refuses_each_exact_gate_path(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        for path in GATE_PATHS:
            with self.subTest(path=path):
                mapping = self.assert_policy_result(
                    self.check_writes(binding, [(path, b"#!/bin/sh\n")]),
                    outcome="refused",
                )
                self.assert_refusal(mapping, "lane-write")
                self.assertIn(path, mapping["refusal"])

    def test_n7_dev_plus_maintenance_record_still_refuses_ops_readme(self):
        self.add_standing(["ops/README.md"])
        binding, _decls, policy = self.bind_ok(profile="dev", repository=("ops/",))
        self.assertEqual(policy["maintenance"]["standing"][0]["record"], STANDING)
        mapping = self.assert_policy_result(
            self.check_writes(binding, [("ops/README.md", b"# ops fixture\n")]),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-write")

    def test_n7_true_maintenance_without_coverage_refuses_and_ordinary_tooling_passes(
        self,
    ):
        binding, _decls, policy = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertIsNone(policy["maintenance"])
        mapping = self.assert_policy_result(
            self.check_writes(binding, [("ops/lane-policy.json", self.policy_bytes)]),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-write")
        ordinary, _decls, _policy = self.bind_ok(profile="dev")
        self.assert_policy_result(
            self.check_writes(ordinary, [("ops/bin/example.sh", self.example_sh)]),
            outcome="pass",
        )


class CasesN8(_LanePolicyCase):
    def test_n8_standing_active_duplicate_keys_wrong_types_malformed_paths(self):
        original = self.policy_bytes
        active = original.replace(b'"proposal"', b'"active"', 1)
        self.assertNotEqual(active, original)
        self.assertIn(b'"active"', active)
        self.assertIn(b"agentscient.lane-policy/v1", active)
        self.commit_policy(active)
        self.refresh_admission([])
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )
        duplicate = original.replace(
            b'"schema": "agentscient.lane-policy/v1"',
            b'"schema": "agentscient.lane-policy/v1", "schema": "agentscient.lane-policy/v1"',
            1,
        )
        self.assertIn(b'"schema"', duplicate)
        self.assertGreaterEqual(duplicate.count(b'"schema"'), 2)
        self.commit_policy(duplicate)
        self.refresh_admission([])
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )
        typed = json.loads(original)
        typed["profiles"]["dev"]["authority_maintenance"] = 1
        self.commit_policy((json.dumps(typed, indent=2) + "\n").encode())
        self.refresh_admission([])
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )
        malformed = json.loads(original)
        malformed["shared_read_roots"] = ["../etc/passwd"]
        self.commit_policy((json.dumps(malformed, indent=2) + "\n").encode())
        self.refresh_admission([])
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )


class CasesN9(_LanePolicyCase):
    def test_n9_forged_reader_config_seed_and_worker_home_cannot_admit(self):
        self.plant_bytes(
            self.worker_home
            / ".local"
            / "state"
            / self.reader_lane_name
            / "decisions.db",
            b"forged",
        )
        self.plant_bytes(
            self.canonical_repo / "ops" / "conductor" / "decisions.seed.json",
            b'{"forged":true}\n',
        )
        context = self.trusted_context(profile="dev")
        context["custody_anchor"]["host_home"] = str(self.worker_home)
        self.assert_refusal(
            self.bind(context, self.declarations()),
            "lane-policy",
        )

    def test_n9_mismatched_show_digest_including_changed_events_and_newline(self):
        self.assertTrue(self.admission_stdout.endswith(b"\n"))
        stripped = self.admission_stdout[:-1]
        self.assertNotEqual(_sha256(stripped), self.admission_digest)
        context = self.trusted_context(profile="dev")
        context["register_evidence"]["admission"]["sha256"] = _sha256(stripped)
        self.assert_refusal(
            self.bind(context, self.declarations()),
            "lane-policy",
        )
        noted = self.admission_stdout[:-1] + b" \n"
        self.assertNotEqual(_sha256(noted), self.admission_digest)
        context = self.trusted_context(profile="dev")
        context["register_evidence"]["admission"]["stdout"] = noted.decode("utf-8")
        self.assert_refusal(
            self.bind(context, self.declarations()),
            "lane-policy",
        )

    def test_n9_wrong_principal_malformed_evidence_and_superseded_rows(self):
        self.refresh_admission([], decided_by="not-the-owner <owner@example.test>")
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )
        self.admission_id = ADMISSION
        stdout, digest = self._install_show(
            ADMISSION,
            kind="lane-policy-admission/v1",
            extra={
                "reader": {
                    "ref": self.reader_ref,
                    "runtime_sha256": self.runtime_sha256,
                },
                "standing_grants": [],
            },
            standing="rejected",
        )
        self.admission_stdout, self.admission_digest = stdout, digest
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), self.declarations()),
            "lane-policy",
        )

    def test_n9_no_successor_chasing_or_per_job_fallback_for_invalid_standing(self):
        standing = self.add_standing(["docs/", "ops/lane-policy.json"])
        stdout = self._show_bytes(
            STANDING,
            kind="lane-policy-standing/v1",
            extra={
                "paths": ["docs/", "ops/lane-policy.json"],
                "purpose": "standing maintenance coverage for the named paths",
            },
            standing="superseded",
            superseded_by=REPLACEMENT,
        )
        self.standing_rows = [
            {
                "record": STANDING,
                "stdout": stdout.decode("utf-8"),
                "sha256": _sha256(stdout),
                "paths": standing["paths"],
            }
        ]
        self.refresh_admission([STANDING, REPLACEMENT])
        self.add_per_job(["ops/lane-policy.json"])
        self.assert_refusal(
            self.bind(
                self.trusted_context(profile="authority-maintenance"),
                self.declarations(
                    profile="authority-maintenance",
                    repository=("ops/", "docs/"),
                ),
            ),
            "lane-policy",
        )


class CasesN10(_LanePolicyCase):
    def test_n10_per_job_reused_for_other_dispatch_or_inside_union_refuses(self):
        self.add_standing(["docs/", "ops/lane-policy.json"])
        self.add_per_job(["ops/README.md"], dispatch=DISPATCH)
        foreign = self.trusted_context(
            profile="authority-maintenance",
            dispatch_id=DISPATCH_B,
            job="implement",
        )
        self.assert_refusal(
            self.bind(
                foreign,
                self.declarations(
                    profile="authority-maintenance",
                    repository=("ops/", "docs/"),
                ),
            ),
            "lane-policy",
        )
        self.per_job_rows = []
        self.add_per_job(["ops/lane-policy.json"])
        self.assert_refusal(
            self.bind(
                self.trusted_context(profile="authority-maintenance"),
                self.declarations(
                    profile="authority-maintenance",
                    repository=("ops/", "docs/"),
                ),
            ),
            "lane-policy",
        )

    def test_n10_absent_per_job_outside_union_is_lane_write(self):
        self.add_standing(["docs/", "ops/lane-policy.json"])
        binding, _decls, _policy = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        mapping = self.assert_policy_result(
            self.check_writes(binding, [("ops/README.md", b"# ops fixture\n")]),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-write")

    def test_n10_read_permission_cannot_bypass_custody(self):
        secret = self.host_home / ".secrets" / "token"
        self.plant_bytes(secret, b"credential-must-not-be-read\n")
        decls = self.declarations(profile="dev", job_role="read", repository=())
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        self.assert_worker_binding(binding, profile="dev", declarations=decls)
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[
                        self.artifact_entry(
                            str(secret), b"credential-must-not-be-read\n"
                        )
                    ],
                    coverage=[str(secret)],
                ),
                "settle",
            ),
            outcome="refused",
        )
        self.assertTrue(
            mapping["refusal"].startswith("lane-write:")
            or mapping["refusal"].startswith("lane-policy:")
            or mapping["refusal"].startswith("lane-artifact:"),
            mapping["refusal"],
        )
        self.assertNotIn("credential-must-not-be-read", mapping["refusal"])


class CasesR1(_LanePolicyCase):
    def test_r1_stationary_binding_revalidates_on_every_transition(self):
        binding, _decls, policy = self.bind_ok(profile="dev")
        evidence = self.evidence(
            entries=[self.artifact_entry("ops/bin/example.sh", self.example_sh)],
            coverage=["ops/bin/example.sh"],
            completed=True,
        )
        self.assertEqual(evidence["outputs"]["attempt"], 1)
        self.assertEqual(evidence["outputs"]["files"], [])
        for transition in TRANSITIONS:
            with self.subTest(transition=transition):
                if transition == "launch":
                    payload = self.evidence(
                        entries=[],
                        coverage=["ops/bin/example.sh"],
                        completed=False,
                    )
                    self.assertIsNone(payload["outputs"]["attempt"])
                    self.assertEqual(payload["outputs"]["files"], [])
                else:
                    payload = evidence
                mapping = self.assert_policy_result(
                    self.check(binding, payload, transition),
                    outcome="pass",
                )
                self.assertEqual(mapping["binding"], policy)
                self.assertEqual(mapping["snapshot_ref"], self.snapshot_ref)


class CasesR2(_LanePolicyCase):
    def test_r2_changed_policy_profile_template_or_declarations_refuse_before_mutation(
        self,
    ):
        binding, _decls, policy = self.bind_ok(profile="dev")
        listing = _tree_listing(self.job_root)
        changed = dict(policy)
        changed["profile"] = "prod"
        mapping = self.assert_policy_result(
            self.check(changed, self.evidence(entries=[], coverage=[]), "resume"),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-resume")
        self.assertEqual(_tree_listing(self.job_root), listing)
        changed = dict(policy)
        changed["template_sha256"] = "a" * 64
        mapping = self.assert_policy_result(
            self.check(changed, self.evidence(entries=[], coverage=[]), "settle"),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-policy")
        collect = self.check(
            binding,
            self.evidence(
                entries=[self.artifact_entry("src/Example.php", self.example_php)],
                coverage=["src/Example.php"],
            ),
            "collect-after",
        )
        self.assert_refusal(
            self.assert_policy_result(collect, outcome="refused"),
            "lane-write",
        )

    def test_r2_legacy_unbound_write_resume_refuses(self):
        mapping = self.assert_policy_result(
            self.check(
                None,
                self.evidence(
                    allow_null=True,
                    artifacts=None,
                    dependencies=None,
                    outputs=None,
                    head=self.snapshot_ref,
                ),
                "resume",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-resume")
        self.assertEqual(_tree_listing(self.job_root), ())


class CasesR3(_LanePolicyCase):
    def test_r3_legacy_records_remain_readable_but_cannot_land_or_advance(self):
        old = {
            "id": "20260901T000000Z-tests-grok-legacy2",
            "brief": {"template": {"sha256": self.template_digest}},
        }
        path = self.job_root / "old-record.json"
        payload = json.dumps(old, sort_keys=True).encode()
        self.plant_bytes(path, payload)
        for transition in ("land", "ladder", "collect-before"):
            with self.subTest(transition=transition):
                mapping = self.assert_policy_result(
                    self.check(
                        None,
                        self.evidence(
                            allow_null=True,
                            artifacts=None,
                            dependencies=None,
                            outputs=None,
                            head=self.snapshot_ref,
                        ),
                        transition,
                    ),
                    outcome="refused",
                )
                self.assertIsNotNone(mapping["refusal"])
        self.assertEqual(path.read_bytes(), payload)
        _binding, _decls, policy = self.bind_ok(profile="dev")
        self.assertEqual(policy["admission"]["record"], ADMISSION)
        self.assertIn("20260901T000000Z-tests-grok-legacy2", path.read_text())

    def test_r3_candidate_evaluator_cannot_accept_itself(self):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        candidate = b'"""candidate evaluator"""\ndef bind_launch(a, b):\n    return {"outcome": "pass"}\n'
        mapping = self.assert_policy_result(
            self.check_writes(
                binding,
                [("ops/conductor/tools/lane_policy.py", candidate)],
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-write")


class CasesR4(_LanePolicyCase):
    def test_r4_superseded_standing_refuses_until_replacement_admission_and_anchor(
        self,
    ):
        self.add_standing(["docs/", "ops/lane-policy.json"])
        self.add_per_job(["ops/README.md"])
        superseded = self._show_bytes(
            STANDING,
            kind="lane-policy-standing/v1",
            extra={
                "paths": ["docs/", "ops/lane-policy.json"],
                "purpose": "standing maintenance coverage for the named paths",
            },
            standing="superseded",
            superseded_by=REPLACEMENT,
        )
        self.standing_rows = [
            {
                "record": STANDING,
                "stdout": superseded.decode("utf-8"),
                "sha256": _sha256(superseded),
                "paths": ["docs/", "ops/lane-policy.json"],
            }
        ]
        self.refresh_admission([STANDING])
        self.assert_refusal(
            self.bind(
                self.trusted_context(profile="authority-maintenance"),
                self.declarations(
                    profile="authority-maintenance",
                    repository=("ops/", "docs/"),
                ),
            ),
            "lane-policy",
        )
        replacement = self.add_standing(
            ["docs/", "ops/lane-policy.json"],
            record_id=REPLACEMENT,
        )
        context = self.trusted_context(profile="authority-maintenance")
        context["custody_anchor"]["admission_id"] = ADMISSION
        # replacement listed but anchor still names stale reader tuple after map rewrite
        self.assertIsNotNone(replacement)
        fresh_ids = [REPLACEMENT]
        self.standing_rows = [
            row for row in self.standing_rows if row["record"] == REPLACEMENT
        ]
        self.refresh_admission(fresh_ids)
        old_anchor = dict(context["custody_anchor"])
        old_anchor["reader"] = {
            "ref": "0" * 40,
            "runtime_sha256": "b" * 64,
        }
        context["custody_anchor"] = old_anchor
        self.assert_refusal(
            self.bind(
                context,
                self.declarations(
                    profile="authority-maintenance",
                    repository=("ops/", "docs/"),
                ),
            ),
            "lane-policy",
        )
        good, decls, policy = self.bind_ok(
            profile="authority-maintenance",
            repository=("ops/", "docs/"),
        )
        self.assertEqual(policy["admission"]["record"], ADMISSION)
        self.assertEqual(policy["maintenance"]["standing"][0]["record"], REPLACEMENT)
        self.assert_policy_result(
            self.check_writes(good, [("docs/wire.md", b"# wire fixture\n")]),
            outcome="pass",
        )
        second = self.bind(
            self.trusted_context(
                profile="authority-maintenance",
                job="implement",
                dispatch_id=DISPATCH_B,
            ),
            decls,
        )
        self.assert_worker_binding(
            second, profile="authority-maintenance", declarations=decls
        )


class CasesR5(_LanePolicyCase):
    def test_r5_note_changes_show_digest_existing_dispatch_refuses_fresh_binds(self):
        binding, _decls, policy = self.bind_ok(profile="dev")
        old_digest = self.admission_digest
        old_stdout = self.admission_stdout
        noted_stdout = self._show_bytes(
            ADMISSION,
            kind="lane-policy-admission/v1",
            extra={
                "reader": {
                    "ref": self.reader_ref,
                    "runtime_sha256": self.runtime_sha256,
                },
                "standing_grants": [],
            },
            note="bound note must change exact show bytes",
        )
        new_digest = _sha256(noted_stdout)
        self.assertNotEqual(new_digest, old_digest)
        self.assertNotEqual(noted_stdout, old_stdout)
        self.admission_stdout = noted_stdout
        self.admission_digest = new_digest
        table = {ADMISSION: noted_stdout.decode("utf-8")}
        self._write_show_map(table)
        for transition in ("settle", "collect-before", "land", "ladder"):
            with self.subTest(transition=transition):
                mapping = self.assert_policy_result(
                    self.check(
                        binding,
                        self.evidence(entries=[], coverage=["ops/bin/example.sh"]),
                        transition,
                    ),
                    outcome="refused",
                )
                self.assert_refusal(mapping, "lane-policy")
        resume = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(entries=[], coverage=["ops/bin/example.sh"]),
                "resume",
            ),
            outcome="refused",
        )
        self.assert_refusal(resume, "lane-resume")
        fresh, _decls, fresh_policy = self.bind_ok(profile="dev")
        self.assertEqual(fresh_policy["admission"]["sha256"], new_digest)
        self.assert_policy_result(
            self.check_writes(fresh, [("ops/bin/example.sh", self.example_sh)]),
            outcome="pass",
        )
        self.assertEqual(policy["admission"]["sha256"], old_digest)
        self.assertEqual(_sha256(old_stdout), old_digest)


class CasesI1(_LanePolicyCase):
    def test_i1_candidate_instruction_cannot_promote_itself_or_restore_twins(self):
        historical = (
            b"Historical quotation: previous models seemed to think that we will "
            b"be using the prod-lane to replace the dev-lane as we go.\n"
        )
        path = self.job_root / "old-aar.md"
        self.plant_bytes(path, historical)
        binding, _decls, _policy = self.bind_ok(profile="dev")
        note = self.check_writes(
            binding,
            [("ops/conductor/ideas/I-999-app-twins.md", historical)],
        )
        self.assert_policy_result(note, outcome="pass")
        context = self.trusted_context(profile="dev")
        context["instruction_source"] = str(
            self.canonical_repo / "ops/conductor/ideas/I-999-app-twins.md"
        )
        self.assert_refusal(
            self.bind(context, self.declarations(profile="prod", repository=("src/",))),
            "lane-policy",
        )
        self.assertEqual(path.read_bytes(), historical)
        protected = self.check_writes(
            binding,
            [("AGENTS.md", b"Dev tooling must be replaced by the Symfony app.\n")],
        )
        self.assert_refusal(
            self.assert_policy_result(protected, outcome="refused"),
            "lane-write",
        )

    def test_i1_app_runtime_dependency_refuses_and_product_contracts_remain_allowed(
        self,
    ):
        binding, _decls, _policy = self.bind_ok(profile="dev")
        manifest = self.manifest(
            [self.artifact_entry("ops/bin/example.sh", self.example_sh)]
        )
        edge = {
            "source_b64": _path_b64("ops/conductor/tools/example.py"),
            "kind": "import",
            "target_space": "repository",
            "target_root": "src/",
        }
        mapping = self.assert_policy_result(
            self.check(
                binding,
                {
                    "snapshot_ref": self.snapshot_ref,
                    "head": self.snapshot_ref,
                    "artifacts": manifest,
                    "dependencies": self.dependencies(
                        manifest,
                        coverage=[
                            "ops/bin/example.sh",
                            "ops/conductor/tools/example.py",
                        ],
                        edges=[edge],
                    ),
                    "outputs": self.output_attempt(attempt=1, files=[]),
                },
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-dependency")
        citation = b"Prod work retains Symfony contracts; that is a product contract.\n"
        self.assert_policy_result(
            self.check_writes(
                binding,
                [("ops/conductor/notes/product-contracts.md", citation)],
            ),
            outcome="pass",
        )


class ClosedDeclarations(_LanePolicyCase):
    def test_missing_launch_declarations_key_refuses(self):
        decls = self.declarations(missing_key="role_grants")
        self.assertNotIn("role_grants", decls)
        self.assert_refusal(
            self.bind(self.trusted_context(profile="dev"), decls),
            "lane-policy",
        )

    def test_absent_grant_terms_are_empty_not_profile_ceilings(self):
        decls = self.declarations(profile="dev", repository=())
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        policy = self.assert_worker_binding(binding, profile="dev", declarations=decls)
        grants = json.loads(_canonical(self.grants_object(decls, None)).decode())
        self.assertEqual(grants["scope"]["repository"], [])
        self.assertEqual(policy["grants_sha256"], _sha256(_canonical(grants)))
        mapping = self.assert_policy_result(
            self.check_writes(binding, [("ops/bin/example.sh", self.example_sh)]),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-write")

    def test_check_tests_walkthrough_grants_digest_and_brief_policy_keys(self):
        decls = self.declarations(
            profile="dev",
            outputs=[
                {"kind": "file", "path": "SKEPTIC.md", "artifact": "skeptic"},
                {"kind": "scratch", "path": "tmp"},
            ],
        )
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        policy = self.assert_worker_binding(binding, profile="dev", declarations=decls)
        grants = self.grants_object(decls, None)
        self.assertEqual(
            grants["outputs"], {"outputs": ["SKEPTIC.md", "tmp"], "repository": []}
        )
        self.assertEqual(grants["maintenance"], [])
        self.assertEqual(policy["grants_sha256"], _sha256(_canonical(grants)))
        self.assertEqual(sorted(policy), sorted(POLICY_BINDING_KEYS))

    def test_conductor_binding_has_null_job_empty_grants_and_null_maintenance(self):
        decls = self.conductor_declarations("dev")
        result = self.bind(
            self.trusted_context(
                profile="dev",
                job=None,
                stage="conduct",
                dispatch_id=CONDUCT_ID,
            ),
            decls,
        )
        closed, digest = self.assert_conductor_binding(
            result,
            declarations=decls,
            dispatch_id=CONDUCT_ID,
        )
        policy = closed["policy"]
        self.assertIsNone(policy["maintenance"])
        grants = self.grants_object(decls, None)
        self.assertEqual(grants["job"]["repository"], [])
        self.assertEqual(grants["role"]["repository"], [])
        self.assertEqual(grants["outputs"]["outputs"], [])
        self.assertEqual(policy["grants_sha256"], _sha256(_canonical(grants)))
        self.assertEqual(policy["template_sha256"], self.conductor_template_digest)
        self.assertEqual(closed["declarations_sha256"], _sha256(_canonical(decls)))
        self.assertRegex(closed["custody_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(digest, self.conductor_binding_digest(closed))
        self.assertNotEqual(digest, policy["grants_sha256"])


class PreEffectAndLate(_LanePolicyCase):
    def test_pre_effect_bind_launch_refusal_does_not_mutate_job_root(self):
        marker = self.job_root / "must-not-appear"
        result = self.bind(
            self.trusted_context(profile="no-such"),
            self.declarations(profile="no-such"),
        )
        self.assert_refusal(result, "lane-profile")
        self.assertEqual(_tree_listing(self.job_root), ())
        self.assertFalse(marker.exists())
        self.assertFalse(
            isinstance(_as_object(result), dict)
            and _as_object(result)
            and _as_object(result).get("outcome") == "pass"
        )

    def test_late_missing_evidence_is_null_not_empty_success(self):
        binding, _decls, policy = self.bind_ok(profile="dev")
        claimed = self.job_root / "claimed"
        self.plant_bytes(claimed, b"directory-claim\n")
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    allow_null=True,
                    artifacts=None,
                    dependencies=None,
                    outputs=None,
                    head=None,
                ),
                "settle",
            ),
            outcome="refused",
        )
        self.assertIsNone(mapping["head"])
        self.assertIsNone(mapping["artifacts"])
        self.assertIsNone(mapping["dependencies"])
        self.assertIsNone(mapping["outputs"])
        self.assertEqual(mapping["binding"], policy)
        self.assertEqual(mapping["snapshot_ref"], self.snapshot_ref)
        self.assertEqual(claimed.read_bytes(), b"directory-claim\n")
        empty_pass = _as_object(
            self.check(
                binding,
                self.evidence(
                    allow_null=True,
                    artifacts={
                        "snapshot_ref": self.snapshot_ref,
                        "head": self.snapshot_ref,
                        "entries": [],
                    },
                    dependencies=None,
                    outputs={
                        "dispatch": self.dispatch_id,
                        "attempt": None,
                        "files": [],
                    },
                    head=self.snapshot_ref,
                ),
                "settle",
            )
        )
        self.assertIsInstance(empty_pass, dict)
        self.assertNotEqual(empty_pass.get("outcome"), "pass")


class ConductorTools(_LanePolicyCase):
    def _role_and_request(self, kind, target, arguments, reason=None):
        decls = self.conductor_declarations("dev")
        bound = self.bind(
            self.trusted_context(
                profile="dev",
                job=None,
                stage="conduct",
                dispatch_id=CONDUCT_ID,
            ),
            decls,
        )
        mapping = _as_object(bound)
        if mapping is not None:
            closed, digest = self.assert_conductor_binding(
                bound,
                declarations=decls,
                dispatch_id=CONDUCT_ID,
            )
            role_binding = closed
        else:
            digest = "0" * 64
            role_binding = bound
        request = {
            "schema": "conductor-tool/1",
            "id": f"req-{kind}-1",
            "binding_sha256": digest,
            "kind": kind,
            "target": target,
            "arguments": arguments if reason is None else {"reason": reason},
        }
        role = {
            "binding": role_binding,
            "tools": {
                "delegate": ["dispatch", "go", "ladder"],
                "read": ["git-status", "inspect"],
                "coordinate": ["board", "handwork-read"],
                "mcp-read": ["lane_start"],
            },
        }
        return role, request

    def _decision(self, result, request) -> dict:
        mapping = _as_object(result)
        self.assertIsInstance(mapping, dict, result)
        self.assertEqual(sorted(mapping), sorted(DECISION_KEYS), mapping)
        self.assertEqual(mapping["schema"], "conductor-decision/1")
        self.assertEqual(mapping["id"], request["id"])
        self.assertEqual(mapping["binding_sha256"], request["binding_sha256"])
        self.assertRegex(mapping["binding_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(mapping["outcome"], ("allow", "refuse"))
        if mapping["outcome"] == "allow":
            self.assertIsNone(mapping["refusal"])
        else:
            refusal = mapping["refusal"]
            self.assertIsInstance(refusal, dict, refusal)
            self.assertEqual(sorted(refusal), ["class", "expected", "found", "needed"])
            self.assertEqual(refusal["class"], "conductor-tool")
            self.assertIn(refusal["found"], REASON_CODES)
            for field in ("expected", "found", "needed"):
                self.assertIsInstance(refusal[field], str)
                self.assertTrue(refusal[field])
                self.assertNotIn(";", refusal[field])
        return mapping

    def test_evaluate_tool_allows_canonical_delegation_and_coordination_reads(self):
        role, request = self._role_and_request(
            "delegate",
            "dispatch",
            {"frontend": "ops/bin/dispatch.sh", "job": JOB},
        )
        allowed = self._decision(self.evaluate(role, request), request)
        self.assertEqual(allowed["outcome"], "allow")
        self.assertIsNone(allowed["refusal"])
        role, request = self._role_and_request(
            "read",
            "inspect",
            {"path": "docs/wire.md"},
        )
        allowed = self._decision(self.evaluate(role, request), request)
        self.assertEqual(allowed["outcome"], "allow")
        role, request = self._role_and_request(
            "read",
            "git-status",
            {"argv": ["git", "status", "--short"]},
        )
        allowed = self._decision(self.evaluate(role, request), request)
        self.assertEqual(allowed["outcome"], "allow")

    def test_evaluate_tool_refuses_handwork_before_effects(self):
        cases = (
            ("direct-edit", "forbidden", "implementation", "direct-edit"),
            ("git-mutation", "forbidden", "implementation", "git-mutation"),
            ("shell-escape", "forbidden", "implementation", "shell-escape"),
            ("raw-vendor", "forbidden", "implementation", "raw-vendor"),
            ("in-session-agent", "forbidden", "implementation", "in-session-agent"),
        )
        listing = _tree_listing(self.canonical_repo)
        for label, kind, target, reason in cases:
            with self.subTest(label=label):
                role, request = self._role_and_request(kind, target, {}, reason=reason)
                decision = self._decision(self.evaluate(role, request), request)
                self.assertEqual(decision["outcome"], "refuse")
                self.assertEqual(decision["refusal"]["found"], reason)
        self.assertEqual(_tree_listing(self.canonical_repo), listing)
        self.assertEqual(
            sorted(REASON_CODES),
            sorted(
                (
                    "binding-mismatch",
                    "direct-edit",
                    "git-mutation",
                    "in-session-agent",
                    "malformed-request",
                    "raw-vendor",
                    "shell-escape",
                    "unknown-tool",
                )
            ),
        )

    def test_evaluate_tool_substring_naming_a_lever_is_malformed_coordinate(self):
        role, request = self._role_and_request(
            "coordinate",
            "board",
            {"command": "python3 -c 'import os; os.system(\"ops/bin/dispatch.sh\")'"},
        )
        decision = self._decision(self.evaluate(role, request), request)
        self.assertEqual(decision["outcome"], "refuse")
        self.assertEqual(decision["refusal"]["found"], "malformed-request")
        self.assertNotEqual(decision["refusal"]["found"], "shell-escape")

    def test_evaluate_tool_normalized_shell_escape_is_not_a_coordinate(self):
        role, request = self._role_and_request(
            "forbidden",
            "implementation",
            {},
            reason="shell-escape",
        )
        decision = self._decision(self.evaluate(role, request), request)
        self.assertEqual(decision["outcome"], "refuse")
        self.assertEqual(decision["refusal"]["found"], "shell-escape")
        self.assertNotEqual(decision["refusal"]["found"], "malformed-request")

    def test_evaluate_tool_unknown_tool_refuses(self):
        role, request = self._role_and_request(
            "mcp-read",
            "not-a-declared-tool",
            {"uri": "lane://undeclared"},
        )
        decision = self._decision(self.evaluate(role, request), request)
        self.assertEqual(decision["outcome"], "refuse")
        self.assertEqual(decision["refusal"]["found"], "unknown-tool")

    def test_evaluate_tool_binding_mismatch_refuses(self):
        role, request = self._role_and_request(
            "read",
            "inspect",
            {"path": "docs/wire.md"},
        )
        held = request["binding_sha256"]
        request["binding_sha256"] = "a" * 64
        self.assertNotEqual(request["binding_sha256"], held)
        decision = self._decision(self.evaluate(role, request), request)
        self.assertEqual(decision["outcome"], "refuse")
        self.assertEqual(decision["refusal"]["found"], "binding-mismatch")
        self.assertEqual(decision["id"], request["id"])
        self.assertEqual(decision["binding_sha256"], request["binding_sha256"])

    def test_evaluate_tool_read_containing_apply_is_not_a_mutation(self):
        role, request = self._role_and_request(
            "read",
            "inspect",
            {"query": "how does git apply work in this contract"},
        )
        decision = self._decision(self.evaluate(role, request), request)
        self.assertEqual(decision["outcome"], "allow")
        self.assertIsNone(decision["refusal"])


class ExactShowDigest(_LanePolicyCase):
    def test_show_digest_is_exact_stdout_bytes_including_newline_and_events(self):
        canonical = self.admission_stdout
        self.assertTrue(canonical.endswith(b"\n"))
        parsed = json.loads(canonical)
        self.assertEqual(sorted(parsed), ["decision", "events"])
        self.assertEqual(parsed["decision"]["id"], ADMISSION)
        self.assertEqual(parsed["decision"]["home"], POLICY_PATH)
        self.assertEqual(parsed["decision"]["standing"], "ratified")
        self.assertIsNone(parsed["decision"]["superseded_by"])
        self.assertEqual(parsed["decision"]["decided_by"], OWNER)
        self.assertNotEqual(
            parsed["decision"]["recorded_by"], parsed["decision"]["decided_by"]
        )
        self.assertTrue(parsed["events"])
        compact = json.dumps(
            parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        shuffled = {"events": parsed["events"], "decision": parsed["decision"]}
        planted = (json.dumps(shuffled, indent=2, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
        self.assertTrue(planted.endswith(b"\n"))
        self.assertGreater(planted.count(b"\n"), 1)
        self.assertNotEqual(planted, canonical)
        self.assertEqual(json.loads(planted), parsed)
        reserialized = json.dumps(
            json.loads(planted),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        self.assertEqual(reserialized, compact)
        self.assertNotEqual(reserialized, planted[:-1])
        self.assertNotEqual(planted, planted.rstrip(b"\n"))
        self.assertNotEqual(_sha256(planted), _sha256(reserialized))
        self.assertNotEqual(_sha256(planted), _sha256(planted.rstrip(b"\n")))
        self.assertNotEqual(_sha256(reserialized), _sha256(planted.rstrip(b"\n")))
        self.admission_stdout = planted
        self.admission_digest = _sha256(planted)
        self._write_show_map({ADMISSION: planted.decode("utf-8")})
        reread = (
            self.reader_checkout / "ops" / "conductor" / "tools" / "show-map.json"
        ).read_bytes()
        self.assertIn(b'"D-POLICY-1"', reread)
        _binding, _decls, policy = self.bind_ok(profile="dev")
        self.assertEqual(policy["admission"]["sha256"], _sha256(planted))
        self.assertNotEqual(policy["admission"]["sha256"], _sha256(reserialized))
        self.assertNotEqual(
            policy["admission"]["sha256"],
            _sha256(planted.rstrip(b"\n")),
        )


class OutputAttemptReceipts(_LanePolicyCase):
    def _declared_note(self):
        content = b"declared note bytes\n"
        decls = self.declarations(
            profile="dev",
            outputs=[
                {"kind": "file", "path": "NOTE.md", "artifact": "note"},
                {"kind": "scratch", "path": "tmp"},
            ],
        )
        self.assertEqual(decls["outputs"][0]["artifact"], "note")
        self.assertEqual(decls["outputs"][1]["kind"], "scratch")
        return decls, content

    def _bind_declared(self):
        decls, content = self._declared_note()
        binding = self.bind(self.trusted_context(profile="dev"), decls)
        policy = self.assert_worker_binding(binding, profile="dev", declarations=decls)
        return binding, decls, policy, content

    def test_launch_preflight_with_null_attempt_passes(self):
        binding, _decls, policy, _content = self._bind_declared()
        payload = self.evidence(
            entries=[],
            coverage=["ops/bin/example.sh"],
            completed=False,
        )
        self.assertIsNone(payload["outputs"]["attempt"])
        self.assertEqual(payload["outputs"]["files"], [])
        mapping = self.assert_policy_result(
            self.check(binding, payload, "launch"),
            outcome="pass",
        )
        self.assertEqual(mapping["binding"], policy)

    def test_null_preflight_cannot_substitute_for_terminal_pass(self):
        binding, _decls, _policy, content = self._bind_declared()
        payload = self.evidence(
            entries=[self.artifact_entry("NOTE.md", content, layer="output")],
            coverage=["NOTE.md"],
            completed=False,
        )
        self.assertIsNone(payload["outputs"]["attempt"])
        self.assertEqual(payload["outputs"]["files"], [])
        for transition in (
            "settle",
            "collect-before",
            "collect-after",
            "land",
            "ladder",
        ):
            with self.subTest(transition=transition):
                mapping = self.assert_policy_result(
                    self.check(binding, payload, transition),
                    outcome="refused",
                )
                self.assert_refusal(mapping, "lane-artifact")

    def test_fresh_production_receipt_passes_settlement(self):
        binding, _decls, policy, content = self._bind_declared()
        handle = self.retained_handle("evidence/NOTE.md", content)
        receipt = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="fresh",
            evidence=[handle],
        )
        self.assertIsNone(receipt["reuse"])
        self.plant_bytes(self.job_root / "out" / "NOTE.md", content)
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[self.artifact_entry("NOTE.md", content, layer="output")],
                    coverage=["NOTE.md"],
                    completed=True,
                    attempt=1,
                    files=[receipt],
                ),
                "settle",
            ),
            outcome="pass",
        )
        self.assertEqual(mapping["binding"], policy)

    def test_verified_reuse_from_earlier_attempt_passes(self):
        binding, _decls, policy, content = self._bind_declared()
        first = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="fresh",
        )
        prior_bytes = _canonical(
            {
                "dispatch": self.dispatch_id,
                "attempt": 1,
                "files": [first],
            }
        )
        prior_handle = self.retained_handle("receipts/attempt-1.json", prior_bytes)
        reuse = {"attempt": 1, "receipt": prior_handle}
        second = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="reuse",
            reuse=reuse,
            evidence=[prior_handle],
        )
        self.assertEqual(second["reuse"]["attempt"], 1)
        self.assertLess(second["reuse"]["attempt"], 2)
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[self.artifact_entry("NOTE.md", content, layer="output")],
                    coverage=["NOTE.md"],
                    completed=True,
                    attempt=2,
                    files=[second],
                ),
                "settle",
            ),
            outcome="pass",
        )
        self.assertEqual(mapping["binding"], policy)

    def test_reuse_naming_foreign_dispatch_refuses(self):
        binding, _decls, _policy, content = self._bind_declared()
        first = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="fresh",
        )
        foreign_bytes = _canonical(
            {
                "dispatch": DISPATCH_B,
                "attempt": 1,
                "files": [first],
            }
        )
        self.assertIn(DISPATCH_B.encode("utf-8"), foreign_bytes)
        self.assertNotEqual(DISPATCH_B, self.dispatch_id)
        prior_handle = self.retained_handle("receipts/foreign.json", foreign_bytes)
        second = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="reuse",
            reuse={"attempt": 1, "receipt": prior_handle},
            evidence=[prior_handle],
        )
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[self.artifact_entry("NOTE.md", content, layer="output")],
                    coverage=["NOTE.md"],
                    completed=True,
                    attempt=2,
                    files=[second],
                ),
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-artifact")

    def test_reuse_future_attempt_refuses(self):
        binding, _decls, _policy, content = self._bind_declared()
        first = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="fresh",
        )
        prior_handle = self.retained_handle(
            "receipts/attempt-1.json",
            _canonical(
                {
                    "dispatch": self.dispatch_id,
                    "attempt": 1,
                    "files": [first],
                }
            ),
        )
        second = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="reuse",
            reuse={"attempt": 3, "receipt": prior_handle},
            evidence=[prior_handle],
        )
        self.assertGreaterEqual(second["reuse"]["attempt"], 2)
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[self.artifact_entry("NOTE.md", content, layer="output")],
                    coverage=["NOTE.md"],
                    completed=True,
                    attempt=2,
                    files=[second],
                ),
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-artifact")

    def test_reuse_stale_digest_refuses(self):
        binding, _decls, _policy, content = self._bind_declared()
        stale = b"stale leftover note\n"
        self.assertNotEqual(stale, content)
        self.assertIn(b"note", stale)
        first = self.file_receipt(
            stale,
            artifact="note",
            path="NOTE.md",
            production="fresh",
        )
        self.assertEqual(first["sha256"], _sha256(stale))
        self.assertNotEqual(first["sha256"], _sha256(content))
        prior_handle = self.retained_handle(
            "receipts/attempt-1.json",
            _canonical(
                {
                    "dispatch": self.dispatch_id,
                    "attempt": 1,
                    "files": [first],
                }
            ),
        )
        current = self.file_receipt(
            content,
            artifact="note",
            path="NOTE.md",
            production="reuse",
            reuse={"attempt": 1, "receipt": prior_handle},
            evidence=[prior_handle],
        )
        self.assertNotEqual(current["sha256"], first["sha256"])
        mapping = self.assert_policy_result(
            self.check(
                binding,
                self.evidence(
                    entries=[self.artifact_entry("NOTE.md", content, layer="output")],
                    coverage=["NOTE.md"],
                    completed=True,
                    attempt=2,
                    files=[current],
                ),
                "settle",
            ),
            outcome="refused",
        )
        self.assert_refusal(mapping, "lane-artifact")


if __name__ == "__main__":
    unittest.main()
