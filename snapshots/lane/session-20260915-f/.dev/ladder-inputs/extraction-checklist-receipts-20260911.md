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
| 11 | where receipts live | `.dev/records/receipts/<digest>.json`, the digest being the canonical digest of the receipt itself, so the file name is tamper-evident; tracked like dispatch records | done |
| 12 | verify | re-run argv at cwd against the same head; compare exit code, both output digests and head_sha; match exit 0, mismatch exit 1 with each differing field named, refusal exit 2. Measured: the red receipt (`false`) re-derives exactly; the green receipt over a unittest run differs on `stderr_sha256` because the runner prints timings. verify reports that, as the contract asks; whether a suite receipt binds on exit code alone is a ruling for the frozen-set gate, not taken here | done, finding |
| 13 | red then green by hand | receipts 704eafbc (`false`, exit 1) and 29223cde (the ladder suite, exit 0) at 7d43a81f; both vet against `#Receipt`, the green one against `#AdmissibleReceipt`; a receipt with an extra field is refused by the closed struct (exit 1) | verified |
| 14 | lint and the lane's checks | `ruff check` clean on the lever and the four modules; `laneconf.py closure` exit 0; `literals` exit 0; `cue vet ./ops/devlane/harness/` exit 0 | verified |
| 15 | the term wall over the landed tree | `term_wall.py --root .`: clean, 1381 tracked files | verified |
| 16 | trailers | 79da612 carries `Source: <path>@99334f7` for the verbatim modules; 4aca8c1 carries `Source: original` for the lever; both with the extractor as co-author | verified |
| 17 | no tests by the extractor | tests come from Grok after, the two reviewers after that | rule |
| 18 | one hermetic refusal by hand | `env -u WF_AGENT receipt.py record --claim x -- true`: exit 2, stdout empty, one stderr line `identity: expected …; found absent identity; needed …` | verified |
| 19 | placement | `ops/devlane/harness/receipt/` for the four modules with a README; the lever `ops/devlane/harness/receipt.py` inserts that directory on its path and imports them by name | done |
