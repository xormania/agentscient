# Brief: correction after the security re-audit of PR 101

The security re-audit 20260911T030332Z-review-codex-5711a3 at 4017366
confirmed thirteen of the fifteen fix-round findings fixed and refuted
full closure of one; it found two more places where a checklist item
does not hold and one false sentence. Each finding below is disposed
`fix-round` in the findings ledger with the contract item it cites
(`.dev/ladder-inputs/extraction-checklist-receipts-20260911.md`, the
checklist; `ops/devlane/harness/evidence.cue`, the contract). This is a
correction after the one fix round, as clause item 6 allows when a
numbered item is not holding; it names its finding keys and items here.

Edit `ops/devlane/harness/receipt.py` and
`ops/devlane/harness/receipt/README.md` only. Do not edit the tests, the
modules, the contract, or the checklist. The frozen set (thirty tests)
must stay green; the auditor's reproduce commands below must stop
reproducing.

1. 5711a3#1, checklist item 11 (2beea3#3 and 0bc987#4 incompletely
   fixed). `load_receipt` accepts an existing path anywhere and checks the
   stem only when it is digest-shaped or resolves under the receipt
   directory, so an external, non-digest-named file can change without
   renaming and `verify` still runs its argv. Bind every accepted receipt
   to its digest: a RECEIPT argument is a digest or a path whose resolved
   location is under `.dev/records/receipts/` and whose stem equals the
   canonical digest of the parsed body; anything else refuses `receipt`.
   Reproduce: a receipt body written to `/proc/self/fd/<memfd>` named
   `not-a-digest`, then `verify` on that path: today it runs argv; after,
   it refuses `receipt` before running anything.
2. 5711a3#3, contract field `tree_dirty` and checklist item 11. The
   ancestor exclusion added in the fix classifies `?? .dev/` (git's
   collapse of an entirely untracked subtree) as clean, hiding unrelated
   untracked files under `.dev/`. Exclude only paths at or under
   `.dev/records/receipts/`; when git reports a collapsed ancestor such as
   `?? .dev/` or `?? .dev/records/`, resolve it by listing the untracked
   files beneath it (`git status --porcelain -z --untracked-files=all`,
   or an equivalent second query limited to that path) and treat any file
   outside the receipts directory as dirt. Reproduce: `dirty_paths` on
   status output `?? .dev/\0` must not return `[]` while a file such as
   `.dev/unrelated` exists.
3. 5711a3#4, checklist item 10. `load_receipt` accepts any non-empty
   `cwd`; `show` presents a digest-named receipt with `cwd: "/"` as
   conforming. Validate `cwd` in `load_receipt` the way `verify` does:
   relative, normalized, inside the root; otherwise refuse `receipt`.
4. 5711a3#6, checklist item 1. The receipt README says all four modules
   are byte-for-byte copies and nothing is edited; `receipts.py` was
   adapted at 64de462. Replace that sentence with the truth: three
   modules verbatim from the previous repository at 99334f7 with their
   blob ids; `receipts.py` adapted at 64de462 to hash raw output bytes,
   with the reason.

Deferred, not here: 5711a3#2 (whether `verify` refuses `state` on a
dirty worktree; owner ruling with checklist item 12) and 5711a3#5 (argv
credential representation; same as 2beea3#9).

Keep: `head_sha` as sha256 of the commit hex (item 6); suite receipts
differing on `stderr_sha256` (item 12). `ruff check` clean; `cue vet
./ops/devlane/harness/` exit 0; the hermetic registry invocation still
refuses `identity`.

Frozen command, must pass:
`python3 -m unittest discover -s ops/devlane/harness/tests -p test_receipt.py`

Commit with trailers per AGENTS.md, `Source: original`.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; the tests build their own repositories
  under a temp dir — measured by the fix round's runs.
- assumption: `cue` may be absent — refusal: say so in `note`; the vet
  cases skip naming the absence.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
