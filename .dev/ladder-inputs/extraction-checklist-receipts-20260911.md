# Extraction checklist: receipts from the previous repository

Owner, 2026-09-11: "i'd rather extract as much from work i've already
done"; "hand grant ok'd for the extraction - make sure to adapt it where
needed - create a checklist first of things to look for and verify them."
Grant 89. Every item below is verified by a command before the work it
gates; the status column is updated as the extraction proceeds.

Source: the previous repository at `~/projects/uscient/<its name>/.dev/app/workflow/`,
commit 99334f7, cited in commit trailers as `<path>@99334f7`.

| # | look for | verify by | status |
|---|---|---|---|
| 1 | the four files are committed and clean at the cited commit | `git status --short -- <4 files>` empty; blob ids recorded (receipts ff2afe19, canonical dbc04433, gitio d27994fe, errors 8c8b7540; last commits 7158a2f, 7158a2f, 7158a2f, 471ce0f) | verified |
| 2 | no walled name or private path in the copied bytes | term-wall pattern over each file: 0 hits; `.dev/app` references: 0 | verified |
| 3 | import graph closed: stdlib plus the three siblings only | grep of import lines in all four: `re subprocess time pathlib datetime hashlib json` plus `canonical gitio errors` | verified |
| 4 | no dependency on the engine's store or chain | receipts.py: none; gitio.py carries `chain_bytes`, `attempts_bytes`, `export*`, `commit_message` that take an engine store as an argument: dead here, kept verbatim for fidelity, never called by the lever | verified, noted |
| 5 | refusal wire | source `Refusal` exits 1 as `refused: <precondition> — expected … — actual … — needed …`; this lane's wire is one stderr line `class: expected …; found …; needed …`, exit 2, stdout empty (docs/wire.md). The lever maps `Refusal` to the wire; the module is not edited | adapt |
| 6 | `head_sha` shape | the contract wants `#Digest`, 64 hex; git here and there gives 40-hex SHA-1 (both repositories, measured `rev-parse HEAD` length 40, no sha256 object format). The lever records `head_sha` as sha256 of the commit id's 40 hex characters and says so in the receipt README; verify recomputes the same way. Alternative, widening the contract to admit a git id, is the owner's call and not taken here | adapt, flagged |
| 7 | closed receipt shape | `#Receipt` is `close({...})` with twelve fields; the engine's `receipt_event` added stage, check, manifest, scope and toolchain fields. The lever writes the twelve fields only. The manifest and toolchain functions stay in the module for the later frozen-set gate | adapt |
| 8 | `actor` | the lane's identity rule for writing verbs: `WF_AGENT` in `Name <address>` form, refused `identity` when absent, as graft.py does | adapt |
| 9 | `at` | `canonical.now()`, UTC with a trailing Z, the module's own rule | as is |
| 10 | `cwd` | relative to the repository root, never absolute (the contract's comment) | adapt |
| 11 | where receipts live | `.dev/records/receipts/<digest>.json`, the digest being the canonical digest of the receipt itself, so the file name is tamper-evident; tracked like dispatch records | decide, adapt |
| 12 | verify | re-run argv at cwd against the same head; compare exit code, both output digests and head_sha; match exit 0, mismatch exit 1 with each differing field named, refusal exit 2 | adapt |
| 13 | red then green by hand | one receipt for a failing command and one for a passing command, each `cue vet`-ed against `#Receipt`; the passing one against `#AdmissibleReceipt` (clean tree) | pending |
| 14 | lint and the lane's checks | `ruff check` on every file; `laneconf.py closure` and `literals` clean; `cue vet ./ops/devlane/harness/` still clean | pending |
| 15 | the term wall over the landed tree | `term_wall.py --root .` clean | pending |
| 16 | trailers | verbatim modules: `Source: <path>@99334f7`; the lever: `Source: original`; the extractor as co-author | pending |
| 17 | no tests by the extractor | tests come from Grok after, the two reviewers after that | rule |
| 18 | one hermetic refusal by hand | the lever refuses `identity` with `WF_AGENT` unset, one line, exit 2, stdout empty | pending |
| 19 | placement | a directory `ops/devlane/harness/receipt/` for the four modules, loaded by path by the lever `ops/devlane/harness/receipt.py`, the way graft.py loads laneconf; no package machinery | decide |
