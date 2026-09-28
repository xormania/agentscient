# Manual conductor enforcement repair

Scope: finite conductor execution and enforced independent TDD, repaired
manually under the owner's instruction before operating the repaired lane.
The implementation and operating contract are in
[conductor-control.md](../conductor-control.md). The coordination copy is
`/tmp/current-work.md`; raw bootstrap material remains under
`/tmp/ag-manual-repair-20260910`.

## Failure points and resulting behavior

The retained [baseline native probes](evidence-2026-09-10-manual-enforcement/baseline-hook-probes.json)
show malformed and Codex edit payloads returning an empty successful result
from the old Claude matrix, and the unarmed conductor guard allowing a
command that merely mentioned a lane lever. The old test guard operated
after writes; worker timeouts did not bound the whole conductor session.
The former TDD instructions named a workflow writing interface that was not
an implementation admission gate.

The new owner-initialized controller reserves each exact action once, holds
a durable lock and allowance, supervises the entire conductor and each
worker process group, and retains terminal outcomes and bounded logs.
Implementation admission requires independently produced tests, a successful
fixture, actual assertion RED, and a separate review bound to those exact
test bytes and RED output. Code and GREEN cannot alter the sealed test set.
The native gate admits parsed reads and exact declared controller actions;
other model tool actions deny. Permission doctor reports absent or broken
control bindings without depending on the controller's runtime.

## Measured verification

The [source manifest](evidence-2026-09-10-manual-enforcement/source-manifest.json)
names the base SHA, measurement timestamp and final file hashes. Command:
`bash ops/bin/suites.sh`; [retained output](evidence-2026-09-10-manual-enforcement/suites.log)
contains nine passing suites: 2,221 tests run, including seven existing skips.
The [focused output](evidence-2026-09-10-manual-enforcement/focused.log) records
seven passing independently authored controller tests. `ruff check .`,
`laneconf.py closure` and `laneconf.py literals` also completed successfully;
the latter declares its infrastructure-directory exclusion.

Native probes used disposable Git repositories and owner plans capped at
75 seconds. Each requested one native edit, one raw Python write, one read,
and one exact declared action. Receipts preserve actual action results,
sentinel absence, source pins and tool events, rather than accepting a
model's final narrative as proof:

| Host measured | Result | Receipt |
| --- | --- | --- |
| Codex CLI 0.154.0 | Edit and raw write denied; read and declared action passed | [Codex](evidence-2026-09-10-manual-enforcement/codex-receipt.json) |
| Claude Code 2.1.260 | Edit and raw write denied; read and declared action passed | [Claude](evidence-2026-09-10-manual-enforcement/claude-receipt.json) |
| Grok 1.0.13 | Edit and raw write denied; read and declared action passed | [Grok](evidence-2026-09-10-manual-enforcement/grok-receipt.json) |
| agy conductor | Refused with exit 2 before spawning; bounded worker use remains available | [agy](evidence-2026-09-10-manual-enforcement/agy-receipt.json) |

Codex and Claude native receipts precede the narrow Grok alias correction:
matching snake/camel aliases are accepted; conflicting or truncated aliases
deny. The Grok receipt and final focused run include that correction. Original
failed activation attempts are retained in `/tmp/ag-manual-repair-20260910`:
Codex CLI-only hook configuration did not activate interception; a subsequent
profile pin detected Codex adding its own repository trust entry. The final
launcher writes the actual native hook file and trust entry before pinning.

## Bootstrap provenance and review boundary

GPT-5.6 Sol authored the compact tests. Claude Opus 5 returned
[CHANGES](evidence-2026-09-10-manual-enforcement/independent-test-review.md)
because the helper overrode `unittest.TestCase.run`. The original test author
supplied the [exact corrections](evidence-2026-09-10-manual-enforcement/test-author-corrections.jsonl).
Root applied those substitutions and deterministic formatting, then measured
[preimplementation RED](evidence-2026-09-10-manual-enforcement/bootstrap-red.txt):
seven tests, nine assertion failures including subtests, no errors or skips.
Root implemented the controller; it did not author or approve the test oracle.

No subsequent independent APPROVE was obtained. The owner's manual-bootstrap
instruction stopped the expanding author/reviewer loop. This draft preserves
that review gap and the reviewer's untested edge cases; it does not claim a
completed enforced TDD admission for the bootstrap itself. The PR reviewer
must assess test completeness, process cleanup and the native host boundary.

## Activation and recovery

The change is delivered on `repair/manual-enforcement-20260910`, for a draft
PR into `dev`. It does not merge branches, alter other worktrees, or install
global harness settings. Existing raw sessions remain ordinary owner-directed
sessions. To use enforcement, the owner initializes a finite plan outside the
worker worktree and starts a supported conductor through `control.py seat`.
The owner can stop it and perform explicitly directed manual work in a normal
session; a conductor cannot authorize that escape for itself. Full commands
and the owner recovery path are in the operating contract linked above.

This is a native tool and process boundary, not operating-system isolation
against a malicious same-UID owner process. Agy has no verified conductor
interceptor in this repair and is refused in that role. No Symfony runtime
is required. Preserved audit/onboarding branches are not integrated here.

## Worker environment probe, consolidation of 2026-09-10

The parallel candidate in PR #79 was withdrawn in favor of this repair; its
implementation stays retrievable on `repair/audit-enforcement-manual-20260910`.
The one measurement it carried that this handoff lacked is the worker side of
the boundary. [worker-environment-probe.json](evidence-2026-09-10-manual-enforcement/worker-environment-probe.json)
records it against this branch's exact controller bytes: for Codex and Grok a
declared action receives the owner's original home paths, not the conductor's
private hook home, and for Claude the gate rides on flags with no environment
to restore. Stand-in host scripts were used, so this measures the seat's
environment boundary only; native denials remain in the host receipts above.
