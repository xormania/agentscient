"""A dispatched codex worker is handed the acting coordination server.

The A-87 trial died on this. The launch wired one MCP server, `lane_mcp.py`,
whose tools are all reads, so the worker had no verb to claim an assignment
with and no verb to submit one with; it fell back to a shell it could not
write from, and the assignment it was dispatched for stayed unclaimed.

The acting server is the projection that carries those verbs. It resolves
who is calling from the session id in its own environment and takes the
participant, the assignment and the record from a config file the launcher
writes. Both halves of that already exist here: the launcher mints the
session id and puts it in the worker's environment, and `bind-for` returns
the participant the core minted for it. What is missing is the registration
and the config.

  C1  the capability list the launcher declares is the server's own
      catalogue, so the two cannot drift apart unseen
  C2  the config the launcher writes is one the real server accepts
  C3  it names the participant `bind-for` returned and the assignment the
      dispatch was for, never an agent string
  C4  the codex argv registers the acting server beside the lane one
  C5  a dispatch that binds no participant declares that and wires nothing
  C6  the brief names the acting tools, so the worker knows it has them
  C7  the harnesses not wired today are named as such, not left silent

One producer by hand under grant 277 at the Lead's assignment relayed by
agentscient-09 (PT-7); the second producer is absent by the owner's word.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import launch_support as ls

from ops.testkit import World  # noqa: F401 - _TempLaunch owns the world

SERVER = "coordination"
LANE_KEY = "agentscient_lane"
ACTING = ls.REPO / "ops" / "conductor" / "tools" / "coordination_mcp.py"
CONFIG_NAME = "coordination-mcp.json"
# The exact key set the acting config declares (coordination_mcp.CONFIG_KEYS).
CONFIG_KEYS = {"version", "participant", "assignment", "branch", "worktree",
               "record", "capabilities", "issued_at"}


def catalogue():
    """The acting server's tool names, read out of its source.

    Read, never imported: the launcher reaches this server as a lever and
    so does this suite, so nothing here puts the core's module state or its
    store inside a case.
    """
    text = ACTING.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'^    Tool\("([\w]+)"', text, re.MULTILINE)))


class _Acting(ls.CoordinationCore, ls._TempLaunch):
    """A snapshot carrying both MCP tools, and a store to bind against."""

    def setUp(self):
        super().setUp()
        self._write("ops/conductor/tools/lane_mcp.py",
                    '"""Lane MCP stub for the fixture."""\n')
        self._write("ops/conductor/tools/coordination_mcp.py",
                    ACTING.read_text(encoding="utf-8"))
        self._write("ops/conductor/tools/instrument.py",
                    (ls.REPO / "ops/conductor/tools/instrument.py")
                    .read_text(encoding="utf-8"))
        self._write("ops/conductor/tools/coordination.py",
                    (ls.REPO / "ops/conductor/tools/coordination.py")
                    .read_text(encoding="utf-8"))
        self.ref = self._commit("plant both MCP tools")

    def dispatched(self, harness="codex", **kwargs):
        """Launch with a real assignment bound, and hand back the record."""
        key = self.dispatcher_session()
        aid = self.assignment(key)
        os.environ[ls.SESSION_KEY] = key
        self.addCleanup(os.environ.pop, ls.SESSION_KEY, None)
        rec, witness, _out, _err = self.launch_ok(
            argv=self.argv_for(harness=harness, job="plan", stage="plan",
                               extra=("--for", aid), **kwargs))
        return rec, witness, aid

    def written(self, rec):
        """The config the launcher wrote, as an object.

        The assertion comes first so a head that writes no config fails on
        this case's own claim rather than raising KeyError, which is a
        fixture defect and not a red.
        """
        meta = self.acting(rec)
        self.assertIn(
            "config", meta,
            f"no acting config was written; the record says {meta!r}")
        return json.loads(
            ls.Path(meta["config"]).read_text(encoding="utf-8"))

    def core_check(self, config):
        """The real acting server's own validation of the config, as a
        lever run with the world's environment — the same way a harness
        would start it, minus the serve loop."""
        env = dict(os.environ)
        env["WF_AGENT"] = ls.FIXTURE_DISPATCHER
        return subprocess.run(
            [sys.executable, str(ACTING), "--config", str(config), "check"],
            capture_output=True, text=True, timeout=60,
            cwd=str(ls.REPO), env=env)

    def acting(self, rec):
        return (rec.get("brief") or {}).get("coordination") or {}


class TheEdgeToTheActingServerIsDeclaredAndChecked(_Acting):
    """C1."""

    def test_the_declared_capabilities_are_the_servers_own_catalogue(self):
        """A capability the server does not carry refuses class `config`
        and kills the launch; one it carries but the launcher omits is a
        verb the worker silently cannot reach. Either way the two lists are
        one edge, and this is the gate on it.

        Planted fault: drop a name from COORD_MCP_TOOLS and this fails.
        """
        launch = ls.require_module(self, "launch")
        declared = sorted(getattr(launch, "COORD_MCP_TOOLS", ()))
        self.assertEqual(
            declared, catalogue(),
            "the launcher's declared capability list and the acting "
            "server's catalogue have drifted apart")


class TheConfigIsOneTheRealServerAccepts(_Acting):
    """C2 C3."""

    def test_the_written_config_checks_clean_against_the_real_server(self):
        rec, _witness, _aid = self.dispatched()
        meta = self.acting(rec)
        self.assertIn(
            "config", meta,
            f"no acting config was written; the record says {meta!r}")
        done = self.core_check(meta["config"])
        self.assertEqual(
            done.returncode, 0,
            f"the real server refused the launcher's config: {done.stderr!r}")

    def test_the_config_carries_exactly_the_keys_the_server_declares(self):
        rec, _witness, _aid = self.dispatched()
        written = self.written(rec)
        self.assertEqual(set(written), CONFIG_KEYS)

    def test_it_names_the_participant_bind_for_returned(self):
        """C3, and the reason the whole binding half came first.

        `participant` is the id the core minted, not an agent string: the
        server refuses class `config` on anything that is not PT-n, and a
        config naming the dispatcher would give the worker the dispatcher's
        authority.
        """
        rec, _witness, aid = self.dispatched()
        written = self.written(rec)
        bound = (rec.get("session") or {}).get("bound") or ""
        self.assertRegex(written["participant"], r"^PT-[1-9][0-9]*$")
        self.assertIn(
            written["participant"], bound,
            f"the config names {written['participant']!r} but bind-for "
            f"returned {bound!r}")
        self.assertEqual(written["assignment"], aid)
        self.assertEqual(written["record"], rec["id"])


class EachHarnessCarriesTheActingServerOrSaysItDoesNot(_Acting):
    """C4 C7."""

    def test_codex_registers_the_acting_server_beside_the_lane_one(self):
        rec, witness, _aid = self.dispatched()
        argv = [str(a) for a in witness["argv"]]
        flags = [argv[i + 1] for i, tok in enumerate(argv) if tok == "-c"]
        self.assertIn(f'mcp_servers.{LANE_KEY}.command="python3"', flags,
                      "the lane server stopped being registered")
        self.assertIn(f'mcp_servers.{SERVER}.command="python3"', flags,
                      f"codex was not handed the acting server; flags {flags!r}")
        args_flag = next(
            f for f in flags if f.startswith(f"mcp_servers.{SERVER}.args="))
        self.assertEqual(json.loads(args_flag.split("=", 1)[1]),
                         self.acting(rec)["server"][1:])

    def test_a_harness_this_does_not_wire_yet_is_named_not_silent(self):
        """C7. Absence is declared, never inferred from silence."""
        rec, witness, _aid = self.dispatched(harness="claude")
        meta = self.acting(rec)
        self.assertIn(
            "unresolved", meta,
            f"claude is not wired for the acting server but the record "
            f"does not say so: {meta!r}")
        self.assertIn("claude", meta["unresolved"])
        argv = " ".join(str(a) for a in witness["argv"])
        self.assertNotIn(f"mcp_servers.{SERVER}", argv)


class ADispatchThatBoundNothingWiresNothing(_Acting):
    """C5."""

    def test_no_assignment_means_a_declared_absence_and_no_registration(self):
        """The acting server cannot be handed a config without a
        participant, and most of this lane's dispatches are reviews that
        name no assignment at all. Those must launch exactly as before.
        """
        rec, witness, _out, _err = self.launch_ok(
            argv=self.argv_for(harness="codex", job="plan", stage="plan"))
        meta = self.acting(rec)
        self.assertIn("unresolved", meta, f"wired without a binding: {meta!r}")
        self.assertIsNone((rec.get("session") or {}).get("bound"))
        argv = " ".join(str(a) for a in witness["argv"])
        self.assertNotIn(f"mcp_servers.{SERVER}", argv)
        self.assertIn(f"mcp_servers.{LANE_KEY}", argv,
                      "the lane server was dropped along with the acting one")


class TheBriefNamesTheActingTools(_Acting):
    """C6."""

    def test_a_wired_worker_is_told_which_verbs_it_holds(self):
        """A registered server the brief never mentions is what the trial
        already proved insufficient: the worker reached for a shell.
        """
        rec, _witness, _aid = self.dispatched()
        text = (ls.Path(rec["snapshot"]["root"]).parent / "prompt.txt").read_text(
            encoding="utf-8")
        self.assertIn(SERVER, text)
        for verb in ("coord_claim", "coord_submit", "coord_brief"):
            self.assertIn(verb, text, f"the brief never names {verb}")
