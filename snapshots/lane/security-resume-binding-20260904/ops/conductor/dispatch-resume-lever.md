# Dispatch resume front door

Inherits the dispatch contract at ops/devlane/dispatch/CONTRACT.md.
This closes the authorized-entrypoint gap in the live resume proof for PR63.
It does not certify a vendor sandbox or add a new harness.

Invocation from the dispatch record's owning lineage worktree:

`ops/bin/dispatch.sh --resume ID [--reason TEXT] [--agent IDENTITY] [--dry-run]`

- Resume selects an existing record, never mints a job or chooses a model.
  The immutable record supplies harness, model, effort, prompt and isolation.
- Only the options shown are accepted in resume mode. Refuse conflicting
  launch-only flags, duplicate resume IDs, missing/option-like/path IDs,
  empty explicit reasons, and --detach before starting a subprocess.
  There is no new prompt, cap, timeout, trust or permission override.
- Existing literal lane configuration, launcher pin precedence and identity
  selection apply. Emit the same dry-run JSON shape, with exact argv
  `[launcher, "resume", ID]` and optional `--reason TEXT`.
  No shell reconstruction or eval. --reason is recorded metadata, not a prompt.
- Dry-run may read configuration and print the planned invocation, but must
  not access a session store, launch a harness or mutate a record.
- Foreground execution preserves the launcher's exit status. Existing fresh
  dispatch behavior is unchanged. The ops/bin shim remains the entrypoint;
  go.sh need not gain a second syntax in this tranche.
- Before resume touches paths, modes, stores or subprocesses, the launcher
  requires valid WF_AGENT and the record's exact non-protected lineage
  checkout (not detached, trunk, release or main). Its existing canonical
  record/ref/isolation checks and post-attempt settlement still apply.
  Refuse before action, using the existing expected/found/needed wire.
- Resuming a live worker is not an admitted use. A currently running attempt
  must be refused before starting a second process. Positive PID existence
  alone is not proof of identity or death; use the launcher-held state and
  available process evidence conservatively, or refuse ambiguous live state.

Verification: independent exact-argv and refusal probes with an owned fake
launcher, unchanged wrapper tests, and the dispatch resume tests. A real
Codex check-tests resume is a separate version-stamped capability probe:
out/TMPDIR writes, ordinary snapshot/input write refusal, same session,
attempt advancement, unchanged snapshot HEAD/residue. Missing arms stay
unmeasured; mode hardening is not strong same-UID immutability.
