adversarial audit envelope, record 20260911T020630Z-review-grok-7fdc2e

{
  "artifacts": {},
  "counts": {
    "opinions": 0,
    "p1": 1,
    "p2": 1,
    "p3": 0
  },
  "findings": [
    {
      "claim": "contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md and contract item 4 of .dev/ladder-inputs/scope-gate-20260910.md: `_scope_path` does not identify the work-order Contract file, so a satisfying citation is refused and the needed command does not satisfy. This snapshot has three `.dev/ladder-inputs/scope-*.md` files (`scope-discipline.md`, `scope-gate-20260910.md`, `scope-gate-20260910.scope.md`). An item-1 correction (write job, `--follows` a review record, `--answers` a key) whose evidence is `contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: found-text missing` is refused `disposed fixed without a contract citation (citation does not name the correction scope file)` when no `--input` is given. Needed is `python3 ops/conductor/tools/findings.py disposition '<key>' fixed 'contract item 1 of .dev/ladder-inputs/<scope path>: correction'`; the citation grammar captures path `.dev/ladder-inputs/<scope>`. Running that printed command exits 0; the next check repeats the same refusal. With `--input` of only `scope-gate-20260910.scope.md` (the 1024-byte cap file, no `N. ` line), needed cites item 1 of that file; running it still refuses (`contract item 1 is absent from the cited scope file`). With `--input` of `scope-discipline.md` then the Contract file, needed asks to cite the discipline clause, not the Contract. Item 1 defines a correction from `--follows` / `out/` input alone. The accept path with `--input` of `scope-gate-20260910.md` does pass. Frozen tests hide this by planting a single `scope-*.md`.",
      "reproduce": "python3 -c \"from pathlib import Path; print(sorted(p.name for p in Path('.dev/ladder-inputs').glob('scope-*.md')))\"  # three names at e0dee24. Isolate HOME; copy correction.py and findings.py into a temp repo that contains those three scope files and a planted adversarial-review record; import; disposition KEY fixed 'contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: found-text missing'; python3 ops/conductor/tools/correction.py check --job implement --role write --at 2099-01-01T00:00:00Z --records <records> --jobs-root <jobs> --root <repo> --follows <id> --answers <id>#1  # exit 2, needed contains '<scope path>'. shlex-split and run that needed command (exit 0); repeat check (still exit 2). Repeat check with --input of scope-gate-20260910.scope.md only; run its needed command; repeat check (exit 2, item 1 absent). Repeat with --input of scope-discipline.md first (needed cites that file). Repeat with --input of scope-gate-20260910.md (exit 0).",
      "severity": "p1",
      "where": "ops/conductor/tools/correction.py `_scope_path`"
    },
    {
      "claim": "contract item 4 of .dev/ladder-inputs/scope-gate-20260910.md and contract item 9 of .dev/ladder-inputs/scope-gate-20260910.md: `cited` and the gate do not resolve the same scope file, so the ledger half of item 9 can disagree with mint. The same holding disposition is `cited` exit 0 when the source record's `brief.inputs` has basename `scope-gate-20260910.md`, and `uncited: the finding record names no available scope file` when that record has no `scope-*` brief input (the unique `scope-*.md` fallback fails on this tree). `correction.py check` without that file as `--input` still refuses the key. First `scope-*` basename wins, so a brief that names `scope-discipline.md` makes a Contract citation uncited. Item 9's driver read would therefore stop or continue independently of whether the mint gate would accept.",
      "reproduce": "Same isolated plant as the p1 finding, with findings.py staged at <repo>/ops/conductor/tools/findings.py so ROOT is the temp repo. Record has no brief: python3 ops/conductor/tools/findings.py cited <id>#1  # exit 1, uncited: the finding record names no available scope file. Write brief.inputs path basename scope-gate-20260910.md; cited exits 0. Write brief.inputs basename scope-discipline.md; cited exits 1, citation does not name the correction scope file. Run correction.py check on the same key with no --input: still exit 2 uncited.",
      "severity": "p2",
      "where": "ops/conductor/tools/findings.py `_record_scope` / `do_cited`"
    }
  ],
  "job": "adversarial-review",
  "note": "Frozen tests pass at this ref: python3 -m unittest discover -s ops/conductor/tests -p test_correction.py (36) and test_findings_citation.py (27). They plant one scope-*.md. Registry rows refuse arguments and follows, exit 2, empty stdout. Items 1, 2, 5, 6, 7, 8 and 10 held on the arms those tests plus the hermetic registry invocations cover. launch.py mint wiring is not in this change.",
  "spend": {
    "harness": "grok",
    "out": 51427,
    "runs": 1,
    "total": 1681098
  },
  "stamp": {
    "ended": "2026-09-11T02:20:16Z",
    "ref": "e0dee24a7a979aa822245bb1a4d6eb83b699a4f7",
    "started": null
  },
  "status": "ok",
  "verdict": "changes"
}
