# Manual conductor repair verification

The command-produced measurements in `verification.json` bind this repair to
the exact controller, hook, independent test and dispatch-isolation bytes.
`native-roles.json` retains six native CLI results from 2026-09-10. The installed
clients used local deterministic protocol fixtures with synthetic credentials;
no paid model produced these responses. This is execution evidence, not a
Grok, Claude or Codex review verdict.

| Host | Conductor | Worker through dispatch isolation |
| --- | --- | --- |
| Codex 0.154.0 | Read and declared action allowed; raw write and patch denied | Raw write and patch succeeded |
| Claude Code 2.1.260 | Read and declared action allowed; raw write and Write denied | Raw write and Write succeeded |
| Grok 1.0.13 | Read and declared action allowed; raw write and search_replace denied | Raw write and search_replace succeeded |

Workers were launched from a declared controller action with the conductor's
private environment as the incoming context. The action restored the owner's
original paths before invoking the repository's real `isolation.isolated`
adapter. Each worker used its normal isolation flags or home and observed no
conductor-hook denial. This verifies the native role boundary; it does not
claim a full dispatcher job lifecycle was exercised by these six probes.
The complete existing dispatch and harness suites also passed in `suites.log`.

`native-probe.py.txt` is the exact manual probe script retained as evidence.
Its absolute paths identify the measured checkout and disposable fixture
location. The worker transport setup supplies only the local fixture provider;
the conductor paths use the implemented `seat --host` wiring. The private
homes do not change persistent user or project hook settings.

The seven focused tests came from GPT-5.6 Sol with the author's exact helper
name and timeout corrections; their bytes and provenance are recorded in
`producer-correction.json`. Claude Opus 5 rejected the earlier candidate. No
subsequent independent approval of the corrected tests or this implementation
is claimed. The owner instructed immediate manual repair and stopped further
model review loops; this PR remains a draft for review.

Native interface references: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude hooks](https://code.claude.com/docs/en/hooks), and
[Grok hooks](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md).
