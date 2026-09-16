"""The session id the launcher mints must reach the worker that runs under it.

Package C slice two, the launcher half. The acting coordination MCP server
resolves who is calling from the session id in its own environment and
refuses class `session` when there is none. A dispatched worker therefore
holds a participant only if the id the launcher minted for it is in its
environment, under the key `instrument.session()` reads.

Measured before this was written, read-only off the live store at
/home/scientdb/.local/state/agentscient/state.db on 2026-09-16: five
participants, and every one of them has a null `bound_for` and a null
`bound_by`. No row in that store was ever written by `bind-for`. The
launcher already mints a uuid per dispatch (launch.py, `uuid.uuid4()`) and
already hands it to a claude child as `--session-id`, so the id exists and
reaches the argv; what it does not do is put it in the child's environment,
where a worker of any harness could read it.

  L1  the minted session id is in the worker's environment
  L2  it is the same id the record and the argv carry, not a second one
  L3  the witness would see the key if it were set — the guard that keeps
      L1 from passing because the fixture is blind to it rather than
      because the launcher set anything
"""

from __future__ import annotations

import launch_support as ls

from ops.testkit import World  # noqa: F401 - _TempLaunch owns the world

SESSION_KEY = "CLAUDE_SESSION_ID"


class TheWorkerLearnsTheSessionIdItWasMintedFor(ls._TempLaunch):
    """L1 L2 L3."""

    def test_the_fixture_can_see_the_key_at_all(self):
        """L3, and it runs first for a reason.

        The witness records an allowlist of environment keys, not the whole
        environment. If SESSION_KEY is not in that list, the assertion in
        the next case reads an absent value whether the launcher set one or
        not, and a green there would mean nothing. This case fails loudly
        instead.

        Planted fault: remove SESSION_KEY from `env_keys` in
        launch_support's fake CLI and this fails while the other two still
        pass, which is exactly the blindness it exists to catch.
        """
        source = ls._FAKE_CLI
        self.assertIn("env_keys", source,
                      "the fake CLI no longer builds an env allowlist")
        head, _, tail = source.partition("env_keys")
        window, _, _ = tail.partition("]")
        self.assertIn(
            SESSION_KEY, window,
            f"the witness allowlist does not carry {SESSION_KEY}, so an "
            f"assertion about the worker's environment cannot fail for the "
            f"right reason")

    def test_the_minted_session_id_reaches_the_worker_s_environment(self):
        """L1."""
        rec, witness, _out, _err = self.launch_ok(harness="claude")
        minted = (rec.get("session") or {}).get("id")
        self.assertTrue(minted, "the record carries no minted session id")
        env = witness.get("env") or {}
        self.assertEqual(
            env.get(SESSION_KEY), minted,
            f"the worker ran without {SESSION_KEY} in its environment, so "
            f"it could hold no participant and every mutation it made would "
            f"refuse class session; the record minted {minted!r} and the "
            f"child saw {env.get(SESSION_KEY)!r}")

    def test_the_environment_and_the_argv_name_one_session(self):
        """L2.

        Two ids would be worse than none: the worker would act under one and
        be recorded under the other, and the store's provenance would point
        at a session that never ran.
        """
        rec, witness, _out, _err = self.launch_ok(harness="claude")
        minted = (rec.get("session") or {}).get("id")
        argv = [str(a) for a in witness.get("argv") or []]
        self.assertIn("--session-id", argv,
                      "a claude child is launched without --session-id")
        on_argv = argv[argv.index("--session-id") + 1]
        env = witness.get("env") or {}
        self.assertEqual(
            on_argv, minted,
            "the argv names a session the record does not")
        self.assertEqual(
            env.get(SESSION_KEY), on_argv,
            f"the child was told one session on its argv ({on_argv!r}) and "
            f"another in its environment ({env.get(SESSION_KEY)!r})")
