# Brief: fix-tests for the receipt lever, from the two review envelopes

The two reviews of the receipt lever at 44995b6 (security audit
20260911T020846Z-review-codex-2beea3, adversarial review
20260911T020855Z-review-grok-0bc987) returned `changes`. Every finding
below is disposed `fix-round` in the findings ledger with the contract
item it cites, from `.dev/ladder-inputs/extraction-checklist-receipts-20260911.md`
(the checklist) or `ops/devlane/harness/evidence.cue` (the contract).
This is the tests half of the one fix round: make the frozen set say what
the contract says, red first. The code half follows and makes it green.
Edit `ops/devlane/harness/tests/test_receipt.py` only. Do not edit the
lever or the modules under `ops/devlane/harness/receipt/`.

## Two assertions rejected (0bc987#6, checklist item 11)

`assert_named_by_digest` hashes the file bytes minus a newline;
`Show.test_prints_the_canonical_json` compares by `json.loads`. Replace
them: the file stem must equal the canonical digest of the parsed body as
`ops/devlane/harness/receipt/canonical.py` computes it, and `show` must
print exactly the canonical serialization. A stub that writes indented
JSON named by the sha256 of its own bytes and pretty-prints must fail both.

## New red cases, one per finding key

- 2beea3#1, checklist item 10: `verify` of a receipt whose `cwd` is
  absolute (`/`) or escapes the root refuses `cwd`; it never runs argv.
- 2beea3#2, checklist item 11: with `.dev/records/receipts` replaced by a
  symlink to a directory outside the repository, `record` refuses (class
  `receipt` or `cwd`, the code half chooses; assert exit 2 and the wire)
  and nothing is written outside the root.
- 2beea3#3 and 0bc987#4, checklist item 11: after a field of a written
  receipt is edited in place, `verify` and `show` of the old digest refuse
  `receipt`.
- 2beea3#4, contract fields `stdout_sha256`/`stderr_sha256`: two commands
  whose outputs differ only in bytes invalid as UTF-8 yield different
  digests; the digest equals sha256 of the raw bytes.
- 2beea3#5, contract field `tree_dirty`: when `git status` fails (a
  repository whose index is unreadable), `record` refuses `repository`
  rather than writing `tree_dirty: false`.
- 2beea3#6, checklist item 5: an argv element containing a newline
  produces a refusal or a receipt whose stderr wire is one line; no
  argv text appears on stderr.
- 2beea3#7 and 0bc987#7, checklist item 5: `record` without `--claim`,
  `verify` without RECEIPT, and bare `show` each refuse `arguments` on the
  wire: one stderr line, exit 2, stdout empty, no usage text.
- 2beea3#8, checklist item 8: `WF_AGENT='<>'`, `WF_AGENT='Name <>'` and
  `WF_AGENT=' <a@b>'` each refuse `identity`.
- 0bc987#1, contract `#Receipt`: `show` of a twelve-key file with
  `tree_dirty: "no"`, `exit_code: "0"`, `duration_ms: -1`, or a 40-hex
  `head_sha` refuses `receipt`.
- 0bc987#2, checklist item 5: `show` of a JSON array refuses `receipt`,
  one line, no traceback.
- 0bc987#3, contract `#Receipt.claim` and `argv`: `record --claim ''` and
  `record --claim x -- true ''` refuse `arguments` before running.
- 0bc987#5, checklist item 11: in a repository that does not track `.dev`,
  a second `record` after the first passes; the untracked receipts
  parent is not dirt.

Each case is red at this ref for its own assertion; report in `note` how
each red was proven. Keep the eighteen existing methods except the two
replaced. Frozen command:
`python3 -m unittest discover -s ops/devlane/harness/tests -p test_receipt.py`
(expected red at this ref; green after the code half).

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; tests build their own git repositories
  under a temp dir — measured: the existing suite does so.
- assumption: `cue` may be absent — refusal: the vet cases already skip
  naming the absence; add none that need it.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
