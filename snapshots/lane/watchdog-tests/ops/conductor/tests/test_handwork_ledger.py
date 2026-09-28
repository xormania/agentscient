"""Handwork-ledger acceptance tests, written from the contract.

Contract: `ops/conductor/handwork-ledger.md`. The tool
`ops/conductor/tools/hand.py` is the subject and is not read here.
Tests invoke it as a subprocess with HOME pointed at a temp dir.

The live store (`~/.local/state/agentscient/handwork.db` at import-time
HOME) must stay untouched — asserted in tearDown.

The implementation lands in parallel. A missing tool file is one red
(`test_the_tool_file_is_present`). Every other case stages a
copy-tool-bytes stand-in so a missing file is not every test's failure:
when the tool exists its bytes are copied and run; when it does not, a
no-op stub (exit 0, no output) is planted so each assertion goes red on
the contract promise rather than Python's missing-file exit 2.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "hand.py"
# Captured at import, before any test mutates a subprocess HOME.
LIVE_STORE = Path.home() / ".local" / "state" / "agentscient" / "handwork.db"

DISPATCH_PROBE = REPO / "ops" / "devlane" / "dispatch" / "launch.py"
LAND_PROBE = REPO / "ops" / "conductor" / "tools" / "land.py"

AGENT = "Grok 4.6 <noreply@x.ai>"
MALFORMED_AGENT = "JustAName"
SESSION = "handwork-session-test-1"

ACTION = "retry the land"
WHY = "the land lever is not built yet"
FOUR_WHY = "cannot wait for lever"
SHORT_WHY = "cannot wait"
UNKNOWN_CLASS = "teleport"
UNPROBED = "other"

KNOWN_CLASSES = (
    "dispatch",
    "gate-run",
    "land",
    "verify-record",
    "pr-open",
    "bulk-push",
    "amend",
    "worktree",
    "log-tooling",
    "other",
)

RECURRENCE = "a recurring absence is a lever demanding to be built."

# Contract's surviving CREATE TABLE, adopted verbatim.
SURVIVING_DDL = (
    "CREATE TABLE handwork(\n"
    "    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,\n"
    "    agent TEXT NOT NULL, action TEXT NOT NULL, why_by_hand TEXT NOT NULL,\n"
    "    missing_lever TEXT, evidence TEXT, lever_class TEXT, scope TEXT,\n"
    "    ttl_s INTEGER, status TEXT DEFAULT 'settled', settled_ts TEXT,\n"
    "    verified INTEGER, late INTEGER DEFAULT 0, settle_note TEXT)"
)

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

DEFAULT_TTL_S = 30 * 60


def _live_snapshot() -> tuple[str, bytes | None]:
    if LIVE_STORE.is_file():
        return ("file", LIVE_STORE.read_bytes())
    if LIVE_STORE.exists():
        return ("other", None)
    return ("absent", None)


class _LedgerFixture(unittest.TestCase):
    """Isolated HOME, staged tool copy, live store frozen."""

    def setUp(self):
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="handwork-ledger-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.home.mkdir()
        self.scratch.mkdir()
        self.store = self.home / ".local" / "state" / "agentscient" / "handwork.db"
        self.assertFalse(
            self.store.exists(),
            "plant: isolated store must start absent",
        )
        self.staged = self.scratch / "hand.py"
        self._stage_tool_bytes()

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                f"live store mutated: {LIVE_STORE}",
            )
            if self._live_before[0] == "absent":
                self.assertFalse(
                    LIVE_STORE.exists(),
                    "tests created the live store",
                )
        finally:
            self._tmp.cleanup()

    def _stage_tool_bytes(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self.staged.write_bytes(data)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
            self.assertEqual(len(landed), len(data))
            self.assertNotEqual(landed, ABSENT_STUB)
        else:
            self.staged.write_bytes(ABSENT_STUB)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, ABSENT_STUB, "stub plant did not land intact")
            self.assertEqual(len(landed), len(ABSENT_STUB))
        self.assertTrue(self.staged.is_file())

    def env(
        self,
        agent: str | None = None,
        session: str | None = None,
    ) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        if session is not None:
            env["CLAUDE_SESSION_ID"] = session
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = None,
        session: str | None = None,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ):
        env = self.env(agent=agent, session=session)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(cwd or REPO),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def declare(
        self,
        action: str = ACTION,
        why: str = WHY,
        lever_class: str = "pr-open",
        *,
        agent: str | None = AGENT,
        session: str | None = None,
        extra: list[str] | None = None,
    ):
        argv = ["declare", action, why, lever_class]
        if extra:
            argv.extend(extra)
        return self.invoke(argv, agent=agent, session=session)

    def settle(
        self,
        grant_id: str | int,
        evidence: str,
        *,
        agent: str | None = AGENT,
        cwd: Path | None = None,
        extra: list[str] | None = None,
    ):
        argv = ["settle", str(grant_id), "--evidence", evidence]
        if extra:
            argv.extend(extra)
        return self.invoke(argv, agent=agent, cwd=cwd)

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def assert_refusal(self, proc, class_name: str) -> None:
        err = proc.stderr or ""
        compact = err.lower().replace("_", "-")
        token = class_name.lower().replace("_", "-")
        spaced = token.replace("-", " ")
        self.assertTrue(
            token in compact or spaced in err.lower(),
            f"refusal class {class_name!r} not named in stderr: {err!r}",
        )
        self.assertEqual(proc.returncode, 2, err)
        self.assertTrue(err.strip(), "refusal was silent")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = err.lower()
        self.assertIn("expected", lower)
        self.assertIn("found", lower)
        self.assertIn("needed", lower)
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )

    def parse_grant_id(self, proc) -> int | None:
        text = proc.stdout or ""
        stripped = text.strip()
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            for key in ("id", "grant", "grant_id"):
                if key in obj:
                    try:
                        return int(obj[key])
                    except (TypeError, ValueError):
                        pass
        match = re.search(r"\b(\d+)\b", text)
        if match:
            return int(match.group(1))
        row = self.latest_row()
        if row is not None:
            return int(row["id"])
        return None

    def grant_id(self, proc) -> str:
        parsed = self.parse_grant_id(proc)
        return str(parsed if parsed is not None else 1)

    def latest_row(self) -> dict | None:
        if not self.store.is_file():
            return None
        conn = sqlite3.connect(self.store)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM handwork ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def stored(self, grant_id: str | int) -> dict | None:
        if not self.store.is_file():
            return None
        conn = sqlite3.connect(self.store)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM handwork WHERE id=?",
                (int(grant_id),),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def table_columns(self) -> list[tuple[str, str]]:
        conn = sqlite3.connect(self.store)
        try:
            rows = conn.execute("PRAGMA table_info(handwork)").fetchall()
            return [(r[1], (r[2] or "").upper()) for r in rows]
        finally:
            conn.close()

    def user_tables(self) -> list[str]:
        conn = sqlite3.connect(self.store)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    def plant_file(self) -> Path:
        path = self.scratch / "evidence.txt"
        data = b"handwork-evidence-v1\n"
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, "evidence file plant did not land intact")
        self.assertEqual(len(landed), len(data))
        self.assertTrue(path.is_file())
        return path

    def plant_dispatch_dir(self) -> Path:
        path = (
            self.home
            / ".local"
            / "state"
            / "agentscient"
            / "dispatch"
            / "hw-record-1"
        )
        path.mkdir(parents=True)
        self.assertTrue(path.is_dir(), "INVALID: dispatch dir plant did not land")
        root = self.home / ".local" / "state" / "agentscient" / "dispatch"
        self.assertEqual(path.parent, root)
        self.assertTrue(path.is_dir())
        return path

    def scratch_git(self) -> tuple[Path, str]:
        repo = self.scratch / "evidence-repo"
        repo.mkdir()
        (repo / "marker.txt").write_text("handwork-git-evidence\n", encoding="utf-8")
        git_env = self.env()
        git_env.update(
            {
                "GIT_AUTHOR_NAME": "Handwork Test",
                "GIT_AUTHOR_EMAIL": "handwork@example.invalid",
                "GIT_COMMITTER_NAME": "Handwork Test",
                "GIT_COMMITTER_EMAIL": "handwork@example.invalid",
            }
        )
        git = [
            "git",
            "-c",
            "user.name=Handwork Test",
            "-c",
            "user.email=handwork@example.invalid",
            "-c",
            "commit.gpgsign=false",
        ]
        init = subprocess.run(
            [*git, "init"],
            cwd=str(repo),
            env=git_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(init.returncode, 0, init.stderr)
        add = subprocess.run(
            [*git, "add", "marker.txt"],
            cwd=str(repo),
            env=git_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        commit = subprocess.run(
            [*git, "commit", "-m", "scratch evidence"],
            cwd=str(repo),
            env=git_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(commit.returncode, 0, commit.stderr)
        sha = subprocess.check_output(
            [*git, "rev-parse", "HEAD"],
            cwd=str(repo),
            env=git_env,
            text=True,
        ).strip()
        self.assertRegex(sha, r"^[0-9a-f]{40}$")
        probe = subprocess.run(
            [*git, "cat-file", "-e", sha],
            cwd=str(repo),
            env=git_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            probe.returncode,
            0,
            "INVALID: scratch sha is not in the scratch repo",
        )
        return repo, sha

    def backdate_open_grant(self, grant_id: str | int) -> None:
        conn = sqlite3.connect(self.store)
        try:
            before = conn.execute(
                "SELECT ts, status FROM handwork WHERE id=?",
                (int(grant_id),),
            ).fetchone()
            self.assertIsNotNone(before, "INVALID: grant missing before backdate")
            conn.execute(
                "UPDATE handwork SET ts=? WHERE id=?",
                ("2000-01-01T00:00:00Z", int(grant_id)),
            )
            conn.commit()
            after = conn.execute(
                "SELECT ts, status FROM handwork WHERE id=?",
                (int(grant_id),),
            ).fetchone()
            self.assertEqual(
                after[0],
                "2000-01-01T00:00:00Z",
                "INVALID: backdate did not land",
            )
            self.assertNotEqual(after[0], before[0], "INVALID: backdate changed nothing")
            self.assertEqual(after[1], before[1], "INVALID: backdate clobbered status")
            self.assertEqual(after[1], "open", "INVALID: grant was not open")
        finally:
            conn.close()

    def plant_historical_db(self) -> None:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.store)
        try:
            conn.execute(SURVIVING_DDL)
            conn.execute(
                "INSERT INTO handwork("
                "ts, session, agent, action, why_by_hand, missing_lever, "
                "evidence, lever_class, scope, ttl_s, status, settled_ts, "
                "verified, late, settle_note"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "2026-08-30T12:00:00Z",
                    "historical-session",
                    "Session Scratch <scratch@example.invalid>",
                    "logged a by-hand act in a scratchpad",
                    "the ledger instrument was not a repo citizen",
                    None,
                    "session-scratchpad",
                    None,
                    None,
                    DEFAULT_TTL_S,
                    "settled",
                    "2026-08-30T12:05:00Z",
                    1,
                    0,
                    None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        landed = self.stored(1)
        self.assertIsNotNone(landed, "INVALID: historical row did not land")
        self.assertIsNone(
            landed["lever_class"],
            "INVALID: plant lost NULL lever_class",
        )
        self.assertEqual(landed["status"], "settled")
        self.assertEqual(self.user_tables(), ["handwork"])

    def assert_verified(self, proc, grant_id: str | int, expected: int, msg: str):
        row = self.stored(grant_id)
        if row is not None and row.get("verified") is not None:
            self.assertEqual(int(row["verified"]), expected, msg)
            return
        self.fail(msg)


class ToolPresence(_LedgerFixture):
    """Missing tool file counts once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class DeclareOpen(_LedgerFixture):
    """1. declare → open round-trip; ttl, agent, session."""

    def test_declare_open_round_trip_prints_id_reminder_and_status_open(self):
        proc = self.declare()
        out = proc.stdout or ""
        self.assertRegex(
            out,
            r"\b\d+\b",
            "declare must print the grant id with the standing reminder",
        )
        reminder = re.sub(r"\b\d+\b", "", out).strip()
        self.assertTrue(
            reminder,
            "declare must print the standing reminder with the grant id",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        opened = self.invoke(["open"], agent=None)
        text = opened.stdout or ""
        # Adjudicated at reconciliation: the contract promises the open
        # grants with age against ttl, not a literal status token — every
        # listed row is open by definition; the row's stored status is
        # asserted below.
        self.assertRegex(
            text,
            r"age=\d+",
            "open must show age against ttl",
        )
        self.assertRegex(
            text,
            r"ttl",
            "open must show age against ttl",
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)
        row = self.latest_row()
        if row is not None:
            self.assertEqual(row["status"], "open")

    def test_open_lists_oldest_first(self):
        first = self.declare(action="first-hand-act")
        second = self.declare(action="second-hand-act")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        opened = self.invoke(["open"], agent=None)
        text = opened.stdout or ""
        pos_first = text.find("first-hand-act")
        pos_second = text.find("second-hand-act")
        self.assertNotEqual(pos_first, -1, "open omitted the older grant")
        self.assertNotEqual(pos_second, -1, "open omitted the newer grant")
        self.assertLess(
            pos_first,
            pos_second,
            "open must list oldest first",
        )

    def test_ttl_defaults_to_30_minutes(self):
        self.declare()
        row = self.latest_row()
        opened = self.invoke(["open"], agent=None)
        text = opened.stdout or ""
        if row is not None and row.get("ttl_s") is not None:
            self.assertEqual(
                int(row["ttl_s"]),
                DEFAULT_TTL_S,
                "ttl must default to 30 minutes (1800s)",
            )
            return
        self.assertTrue(
            re.search(r"\b30\b", text),
            "ttl must default to 30 minutes",
        )

    def test_ttl_flag_is_minutes_not_seconds(self):
        self.declare(extra=["--ttl", "5"])
        row = self.latest_row()
        if row is not None and row.get("ttl_s") is not None:
            ttl = int(row["ttl_s"])
            self.assertEqual(
                ttl,
                5 * 60,
                f"--ttl 5 is minutes (300s), not 5 seconds; got {ttl}",
            )
            self.assertNotEqual(ttl, 5)
            return
        self.fail("--ttl 5 did not persist a grant whose ttl_s is minutes")

    def test_agent_is_stamped_from_wf_agent(self):
        self.declare(agent=AGENT)
        row = self.latest_row()
        if row is not None:
            self.assertEqual(
                row["agent"],
                AGENT,
                "agent must be stamped from WF_AGENT",
            )
            return
        self.fail("agent was not stamped from WF_AGENT")

    def test_session_comes_from_claude_session_id(self):
        self.declare(session=SESSION)
        row = self.latest_row()
        if row is not None:
            self.assertEqual(
                row["session"],
                SESSION,
                "session must come from CLAUDE_SESSION_ID",
            )
            return
        self.fail("session was not stamped from CLAUDE_SESSION_ID")

    def test_session_is_unknown_when_claude_session_id_is_unset(self):
        self.declare(session=None)
        row = self.latest_row()
        if row is not None:
            self.assertEqual(
                row["session"],
                "unknown",
                "session must be unknown when CLAUDE_SESSION_ID is unset",
            )
            return
        self.fail("session was not unknown when CLAUDE_SESSION_ID was unset")


class Identity(_LedgerFixture):
    """2. Writing verbs need WF_AGENT; open and report need none."""

    def test_declare_without_wf_agent_refuses_identity(self):
        proc = self.declare(agent=None)
        self.assertTrue(
            "identity" in (proc.stderr or "").lower(),
            "declare with WF_AGENT unset must refuse identity",
        )
        self.assert_refusal(proc, "identity")

    def test_malformed_wf_agent_refuses_identity(self):
        proc = self.declare(agent=MALFORMED_AGENT)
        self.assertTrue(
            "identity" in (proc.stderr or "").lower(),
            "declare with malformed WF_AGENT must refuse identity",
        )
        self.assert_refusal(proc, "identity")
        self.assertIn(MALFORMED_AGENT, proc.stderr or "")

    def test_settle_without_wf_agent_refuses_identity(self):
        granted = self.declare(agent=AGENT)
        gid = self.grant_id(granted)
        evidence = str(self.plant_file())
        proc = self.settle(gid, evidence, agent=None)
        self.assertTrue(
            "identity" in (proc.stderr or "").lower(),
            "settle with WF_AGENT unset must refuse identity",
        )
        self.assert_refusal(proc, "identity")

    def test_open_and_report_need_no_identity(self):
        self.declare(agent=AGENT)
        for verb in ("open", "report"):
            with self.subTest(verb=verb):
                proc = self.invoke([verb], agent=None)
                err = (proc.stderr or "").lower()
                self.assertNotIn("identity", err)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(
                    (proc.stdout or "").strip(),
                    f"{verb} produced no result",
                )


class WhyShort(_LedgerFixture):
    """3. WHY under four words refuses."""

    def test_why_under_four_words_refuses(self):
        proc = self.declare(why=SHORT_WHY)
        self.assertTrue(
            "why-short" in (proc.stderr or "").lower().replace("_", "-")
            or "why short" in (proc.stderr or "").lower(),
            "WHY under four words must refuse why-short",
        )
        self.assert_refusal(proc, "why-short")

    def test_four_word_why_is_accepted(self):
        proc = self.declare(why=FOUR_WHY)
        self.assertTrue(
            (proc.stdout or "").strip(),
            "four-word WHY must grant",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("why-short", (proc.stderr or "").lower())


class UnknownClass(_LedgerFixture):
    """4. Unknown lever class refuses and names the known classes."""

    def test_unknown_lever_class_refuses_naming_known_classes(self):
        proc = self.declare(lever_class=UNKNOWN_CLASS)
        err = proc.stderr or ""
        self.assertTrue(
            re.search(r"\bclass\b", err.lower()),
            "unknown lever class must refuse class",
        )
        self.assert_refusal(proc, "class")
        self.assertIn(UNKNOWN_CLASS, err)
        for name in KNOWN_CLASSES:
            self.assertIn(name, err)


class LeverExists(_LedgerFixture):
    """5. Built probe refuses; absent probe grants."""

    def test_declaring_dispatch_refuses_naming_the_built_probe(self):
        self.assertTrue(
            DISPATCH_PROBE.is_file(),
            f"INVALID: dispatch probe missing: {DISPATCH_PROBE}",
        )
        proc = self.declare(lever_class="dispatch")
        err = proc.stderr or ""
        self.assertTrue(
            "lever-exists" in err.lower().replace("_", "-")
            or "lever exists" in err.lower(),
            "declaring dispatch must refuse lever-exists",
        )
        self.assert_refusal(proc, "lever-exists")
        self.assertTrue(
            "launch.py" in err or str(DISPATCH_PROBE) in err,
            f"refusal must name the built probe; got {err!r}",
        )

    def test_declaring_land_refuses_now_that_the_lever_is_built(self):
        # Adjudicated at reconciliation: this PR builds the land lever, and
        # the ledger contract flips the class from grantable to refused in
        # the same PR. The grantable example moves to pr-open below.
        self.assertTrue(
            LAND_PROBE.exists(),
            f"INVALID: land probe absent: {LAND_PROBE}",
        )
        proc = self.declare(lever_class="land", extra=None)
        err = (proc.stderr or "").lower()
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("lever-exists", err)

    def test_declaring_pr_open_grants_because_the_probe_is_absent(self):
        proc = self.declare(lever_class="pr-open")
        self.assertTrue(
            (proc.stdout or "").strip(),
            "declaring land must grant because land.sh is absent",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        compact = (proc.stderr or "").lower().replace("_", "-")
        self.assertNotIn("lever-exists", compact)


class SettleEvidence(_LedgerFixture):
    """6. Evidence is verified by shape."""

    def test_existing_file_evidence_verifies(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        path = self.plant_file()
        proc = self.settle(gid, str(path))
        self.assert_verified(
            proc,
            gid,
            1,
            "existing file path must verify (verified 1)",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dispatch_directory_evidence_verifies_as_a_record(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        path = self.plant_dispatch_dir()
        proc = self.settle(gid, str(path))
        self.assert_verified(
            proc,
            gid,
            1,
            "dispatch directory must verify as a record (verified 1)",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_real_git_sha_evidence_verifies(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        repo, sha = self.scratch_git()
        self.assertGreaterEqual(len(sha), 7)
        self.assertLessEqual(len(sha), 40)
        proc = self.settle(gid, sha, cwd=repo)
        self.assert_verified(
            proc,
            gid,
            1,
            "real scratch commit sha must verify (verified 1)",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_bogus_hex_stores_as_claimed_unverified(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        repo, sha = self.scratch_git()
        bogus = "deadbee"
        self.assertRegex(bogus, r"^[0-9a-f]{7,40}$")
        self.assertNotEqual(bogus, sha[: len(bogus)])
        git_env = self.env()
        probe = subprocess.run(
            ["git", "cat-file", "-e", bogus],
            cwd=str(repo),
            env=git_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(
            probe.returncode,
            0,
            "INVALID: bogus hex resolved in the scratch repo",
        )
        proc = self.settle(gid, bogus, cwd=repo)
        self.assert_verified(
            proc,
            gid,
            0,
            "bogus hex stores as claimed with verified 0",
        )
        text = self.combined(proc).lower()
        self.assertTrue(
            any(word in text for word in ("claim", "verified 0", "unverified")),
            "bogus hex output must say it stored as claimed with verified 0",
        )

    def test_unverifiable_shape_stores_as_claimed_unverified(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        evidence = "plain-claim-not-a-path"
        proc = self.settle(gid, evidence)
        self.assert_verified(
            proc,
            gid,
            0,
            "unverifiable shape stores with verified 0",
        )
        text = self.combined(proc).lower()
        self.assertTrue(
            any(word in text for word in ("claim", "verified 0", "unverified")),
            "unverifiable shape must say it stored as claimed with verified 0",
        )


class LateSettle(_LedgerFixture):
    """7. Settling past the ttl sets late 1 and says so."""

    def test_settling_past_ttl_sets_late_and_says_so(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        if self.store.is_file() and self.stored(gid) is not None:
            self.backdate_open_grant(gid)
        path = self.plant_file()
        proc = self.settle(gid, str(path))
        text = self.combined(proc).lower()
        self.assertRegex(
            text,
            r"\blate\b",
            "settling past the ttl must say so",
        )
        row = self.stored(gid)
        if row is not None and row.get("late") is not None:
            self.assertEqual(int(row["late"]), 1)


class ResettleAndUnknown(_LedgerFixture):
    """8. Resettle and unknown id refuse."""

    def test_settling_a_settled_grant_refuses_resettle(self):
        granted = self.declare()
        gid = self.grant_id(granted)
        path = self.plant_file()
        first = self.settle(gid, str(path))
        self.assertEqual(first.returncode, 0, first.stderr)
        again = self.settle(gid, str(path))
        err = again.stderr or ""
        self.assertTrue(
            "resettle" in err.lower(),
            "settling a settled grant must refuse resettle",
        )
        self.assert_refusal(again, "resettle")

    def test_settle_on_unknown_id_refuses(self):
        missing = "404"
        proc = self.settle(missing, str(self.plant_file()))
        err = proc.stderr or ""
        self.assertTrue(
            "unknown" in err.lower(),
            "settle on an id not in the store must refuse unknown",
        )
        self.assert_refusal(proc, "unknown")
        self.assertIn(missing, err)


class Recurrence(_LedgerFixture):
    """9. Third declaration of an unprobed class prints the note."""

    def test_third_declaration_of_an_unprobed_class_prints_recurrence(self):
        first = self.declare(action="first other act", lever_class=UNPROBED)
        second = self.declare(action="second other act", lever_class=UNPROBED)
        self.assertNotIn(RECURRENCE, self.combined(first))
        self.assertNotIn(RECURRENCE, self.combined(second))
        third = self.declare(action="third other act", lever_class=UNPROBED)
        self.assertIn(
            RECURRENCE,
            self.combined(third),
            "third declaration of an unprobed class must print the recurrence note",
        )


class SchemaAdoption(_LedgerFixture):
    """10. Surviving schema with NULL lever_class is readable, no migration."""

    def test_preexisting_schema_is_readable_without_migration(self):
        self.plant_historical_db()
        columns_before = self.table_columns()
        opened = self.invoke(["open"], agent=None)
        reported = self.invoke(["report"], agent=None)
        text = f"{reported.stdout or ''}{reported.stderr or ''}".lower()
        self.assertIn(
            "settled",
            text,
            "report must read the historical settled row without error",
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)
        self.assertEqual(reported.returncode, 0, reported.stderr)
        self.assertNotIn("identity", (opened.stderr or "").lower())
        self.assertNotIn("identity", (reported.stderr or "").lower())
        self.assertEqual(self.table_columns(), columns_before)
        self.assertEqual(self.user_tables(), ["handwork"])
        row = self.stored(1)
        self.assertIsNotNone(row)
        self.assertIsNone(row["lever_class"])
        self.assertEqual(row["status"], "settled")
        self.assertEqual(row["session"], "historical-session")


if __name__ == "__main__":
    unittest.main()
