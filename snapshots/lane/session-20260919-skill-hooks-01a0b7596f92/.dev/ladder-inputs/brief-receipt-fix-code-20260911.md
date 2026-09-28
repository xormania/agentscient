# Brief: fix-code for the receipt lever, the code half of the one fix round

The tests half landed at 6dc6247 (record 20260911T023330Z-tests-grok-cc9d4d):
thirty tests, twenty-two red, one per finding key of the two reviews
(security audit 20260911T020846Z-review-codex-2beea3, adversarial review
20260911T020855Z-review-grok-0bc987), each disposed `fix-round` in the
findings ledger with its checklist item
(`.dev/ladder-inputs/extraction-checklist-receipts-20260911.md`) or
contract field (`ops/devlane/harness/evidence.cue`). Make the frozen set
green without editing it. The tests are the requirements; the brief for
them, `in/brief-receipt-fix-tests-20260911.md`, says what each asserts and
which finding it answers.

Edit `ops/devlane/harness/receipt.py` and, where a finding lands in a
module under `ops/devlane/harness/receipt/`, that module (they were
extracted verbatim from the previous repository; adapting them is allowed
and the commit message must say which module changed and why). Do not
edit the tests, the contract, or the checklist.

## Findings, by key, with the contract item each cites

- 2beea3#1, checklist item 10: `verify` validates `cwd` as repository-
  relative and inside the root before running; refuses `cwd`.
- 2beea3#2, item 11: `write_receipt` resolves the receipts directory,
  refuses when it or a parent is a symlink or resolves outside the root.
- 2beea3#3 and 0bc987#4, item 11: `load_receipt` recomputes the canonical
  digest of the parsed body and refuses `receipt` when it differs from
  the file stem.
- 2beea3#4, contract fields `stdout_sha256`/`stderr_sha256`: digests are
  sha256 of the raw output bytes; no text decoding before hashing.
- 2beea3#5, contract field `tree_dirty`: a failing `git status` refuses
  `repository`; it is never read as clean.
- 2beea3#6, item 5: refusal text is sanitized to one line; argv never
  appears in a refusal.
- 2beea3#7 and 0bc987#7, item 5: missing required arguments refuse
  `arguments` on the wire; no argparse usage text on stderr.
- 2beea3#8, item 8: identity requires a non-empty name and a non-empty
  address inside the brackets.
- 0bc987#1, contract `#Receipt`: `load_receipt` checks field types
  (`tree_dirty` bool, `exit_code` int, `duration_ms` int >= 0, digests
  64 lowercase hex) and refuses `receipt` otherwise.
- 0bc987#2, item 5: a JSON array or any non-object refuses `receipt`.
- 0bc987#3, contract `#Receipt.claim` and `argv`: an empty claim or an
  empty argv element refuses `arguments` before running.
- 0bc987#5, item 11: the receipts directory's untracked parents are
  excluded from dirty detection as the directory itself is.

Deferred, not in this round: 2beea3#9 (a credential-safe argv
representation; no contract item names one).

Keep: `head_sha` as sha256 of the commit id's hex (checklist item 6) and
receipts differing on `stderr_sha256` for unittest runs (item 12); both
are the owner's decisions, not defects. `ruff check` clean on every
edited file; `cue vet ./ops/devlane/harness/` still exit 0; the one
hermetic registry invocation for `receipt.py` still refuses `identity`.

Frozen command, must pass:
`python3 -m unittest discover -s ops/devlane/harness/tests -p test_receipt.py`

Commit with trailers per AGENTS.md; `Source: original` for the lever,
and for an adapted module `Source: <previous repository path>@99334f7`
as the extraction commits do.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; the tests build their own repositories
  under a temp dir — measured by the tests half's run at 6a59379.
- assumption: `cue` may be absent — refusal: the vet cases skip naming
  the absence; run `cue vet` when present and say so in `note`.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
