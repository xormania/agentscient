# I-005 — our own conductor, and our own runners

- recorded: 2026-09-03, while the conductor lane was being copied
- source: owner, verbatim below
- disposition: ratified — this lane; register row D-CI-1 for the runners

## In the owner's words

> can you make our own copy of conductor? something that won't interfere with […]?

> also - […] has github runners locally - try to mimic that for this repo -

> we found we could run 12 at once easily

## What was heard

The conductor lane crosses whole into `ops/conductor/` with its own
state directory under `~/.local/state/agentscient/`, its own records,
its own register — nothing shared with the House's lane or stores. CI
runs on this repository's own self-hosted runners, twelve of them,
registered from the same runner package and unit template the House
uses, labelled `agentscient-wsl`; the House's twelve stay the House's.

## Standing facts it must reconcile with

- The House's twelve runners are repo-level, labelled `self-hosted,Linux,X64` plus a House label, four as user services and the rest from `run.sh` — `gh api repos/<house>/actions/runners`, `systemctl --user`, measured 2026-09-03.
- This repository's twelve: `agentscient-wsl-1..12`, all online — `gh api repos/uscient/agentscient/actions/runners`, 2026-09-03.
