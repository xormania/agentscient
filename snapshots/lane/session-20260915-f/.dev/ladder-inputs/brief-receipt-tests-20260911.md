# Brief: tests for the receipt lever, from the contract and the checklist

The receipt lever `ops/devlane/harness/receipt.py` and the four verbatim
modules under `ops/devlane/harness/receipt/` were extracted from the
previous repository's workflow engine under an owner-authorized hand
grant (2026-09-11). The extractor wrote no tests. Write them from the
contract `ops/devlane/harness/evidence.cue`, the lever's docstring, and
the extraction checklist
`.dev/ladder-inputs/extraction-checklist-receipts-20260911.md`. Do not
edit the lever or the modules; a finding against them is a finding, not
a fix.

## What the lever promises

- `record --claim TEXT [--cwd REL] [--allow-dirty] -- ARGV...` runs ARGV
  at CWD under the repository root and writes a `#Receipt` (the closed
  twelve-field struct of `evidence.cue`) to
  `.dev/records/receipts/<digest>.json`, the digest being the canonical
  digest of the receipt itself. Exit 0 when the command passed, 1 when
  it failed, the receipt written either way. `tree_dirty` is true only
  with `--allow-dirty`; a dirty tree without it refuses `dirty`.
- `head_sha` is the sha256 hex of the commit id's hex characters
  (checklist item 6). `actor` is `WF_AGENT`, refused `identity` when
  absent or not `Name <address>`. `cwd` is repository-relative; an
  absolute path refuses `cwd`. `at` is UTC with a trailing Z.
- `verify RECEIPT` (path or digest): refuses `state` when HEAD is not
  the recorded head; re-runs and compares exit code and both output
  digests; exit 0 on agreement, 1 naming each differing field.
- `show RECEIPT` prints the canonical JSON. A file that is not a
  twelve-field receipt refuses `receipt`; no verb refuses `arguments`.
- Every refusal: one stderr line `class: expected …; found …; needed …`,
  exit 2, stdout empty.

## Tests to write

`ops/devlane/harness/tests/test_receipt.py`, one class per verb, each
case in its own temporary git repository with one commit and a scratch
HOME, `WF_AGENT` set explicitly per case. Cover, at least:

- identity absent, and identity without `<address>`, each refuse
  `identity` on the wire;
- a passing command yields exit 0 and a receipt file whose name is its
  canonical digest and whose twelve fields, and no others, are present;
  `cue vet ./ops/devlane/harness/ <receipt> -d '#AdmissibleReceipt'`
  passes when `cue` is on PATH, and the case is skipped with the reason
  named when it is not;
- a failing command yields exit 1 and a receipt with that exit code;
- `head_sha` equals `sha256(hex of git rev-parse HEAD)`;
- a dirty tree refuses `dirty`; with `--allow-dirty` the receipt has
  `tree_dirty: true` and fails `#AdmissibleReceipt` while passing
  `#Receipt`;
- an absolute `--cwd` refuses `cwd`; a `--cwd` outside the root refuses
  `cwd`;
- `verify` of a deterministic command agrees, exit 0; after a new commit
  it refuses `state`; a command whose output changes between runs
  reports the differing field, exit 1;
- `show` of an unknown digest refuses `receipt`; a JSON file with an
  extra field refuses `receipt`; a bare `receipt.py` refuses
  `arguments`.

Prove each test red for its own assertion before green: the lever is
present at this ref, so red is proven by pointing the test at a stub
lever or by asserting the exact wire text first and watching the
mismatch. Report in `note` how each red was proven.

Frozen command:
`python3 -m unittest discover -s ops/devlane/harness/tests -p test_receipt.py`

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; tests build their own git repositories
  under a temp dir — measured: the harness suite already does so.
- assumption: `cue` may be absent in the worker's sandbox — refusal:
  skip the vet cases naming the absence, never fake a pass.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
