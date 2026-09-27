# Handoff — 2026-09-09, agy worker custody

Conductor publication update, 2026-09-09: this bundle is now retained on origin
at `records/agy-closeout-20260909`. Independent verification passed all ten
manual custody probes (zero failures or unreachable rows). The [publication
receipt](evidence-2026-09-09-agy/publication.json) supersedes the author-time pending settlement and
publication statements below. Automatic retained-handoff selection remains
unclaimed; the reports retain their original measurement boundaries.

Owner-requested retained report, not authority. Author: GPT-6. Local source
inspection on 2026-09-09 is against
`20f9bcaf2b3ae2152b9cab766637b5a89b71214b`; inherited observations retain the
timestamps and commands in [measurements.json](evidence-2026-09-09-agy/measurements.json),
measured at `2026-09-09T20:02:54.229944+00:00`. The supplied conductor holdings
are attributed recollection. [AAR](../AAR-2026-09-09-agy.md) gives the concise
lessons and accounting. No live store was read in this authoring run.

## Resume with these holdings

1. **Owner intent:** add agy as a worker, not conductor, using owner-selected
   Gemini 3.8 Flash for fast audits/investigations/reviews and eventual
   documentation writing. Dev tooling remains independent of Symfony's prod
   application. Configurable harnesses, separated concerns, canonical dispatch
   only; no native subagents. Supplied owner preferences name GPT-6 for planning
   and extensive implementation, Daybreak for security only, reviews on PR
   comments. These are attributed preferences, not a new routing table. The
   owner initiates AAR/handoff; no routine approval pauses.
2. **Closed integration:** supplied evidence records PR77 MERGED into dev at
   `20f9bcaf2b3ae2152b9cab766637b5a89b71214b`, post-merge CI34398341252 and
   CodeQL34398340949 successful. Earlier ready/unmerged state is superseded.
   `origin/master` was `fc839a5f85f192acbea5efa6cc366efb7a7b5a42` in the supplied
   ref query. No release or report-only PR is requested. The evidence's open-PR
   query and launched-record selection were empty at measurement; neither is
   a new global process/branch audit.
3. **Wire and configuration:** `ops/bin/dispatch.sh` is the canonical worker
   entry. `WORKER_HARNESSES` / `EXECUTABLE_<HARNESS>` resolve through laneconf:
   env > local > tracked > compatibility. Explicit model, no hardcoded agy
   role. Native NDJSON input, `--print=`, stream-json output, explicit
   conversation resume. Cumulative terminal replaces live steps; contradictory
   repeated counters refuse. Installed agy 1.1.27 is inherited measurement.
4. **Capability limit:** read workers only; attributed writes unadmitted.
   Final tracked smoke `20260908T095005Z-review-agy-6be776` reads `ok/approve`,
   24,020 total / 11,136 output, source
   `deea88e7d11ccc25183aecdedd28efb62b433639`, provider unavailable. The owner's
   documentation writing use is not fully enabled. Isolation is policy
   containment, not OS containment. Only combined HOME/XDG/TMPDIR instruction
   discovery is measured, not HOME alone or universal host isolation. No new
   auth installer is needed by these holdings. High model plus separate low
   effort conflicts: omit override or match native selection.
5. **Acceptance lineage:** source `20260908T094800Z-review-grok-1b101d`;
   GPT-6 ruling `20260908T095856Z-adjudicate-codex-b3a76e`; test correction
   `20260908T100151Z-tests-grok-c7d886`; independent acceptance
   `20260908T100343Z-review-claude-944125`. Final test hash and PR comments are
   retained in the AAR. Failed transcript smoke
   `20260908T083944Z-review-agy-e49b81` and invalid effort smoke
   `20260908T094801Z-review-agy-12d55a` remain invalid. Later acceptance never
   rewrites original verdicts. The final correction was the terminal
   `live_output` test assertion, not source.

## Current homes, locally inspected

| Concern | Existing home and bounded observation |
| --- | --- |
| Worker execution/configuration | [dispatch contract](../../devlane/dispatch/CONTRACT.md), [launcher](../../devlane/dispatch/launch.py), [laneconf](../tools/laneconf.py), [dispatch wrapper](../tools/dispatch.sh) |
| Conductor launcher | [conductor-start-plan](../conductor-start-plan.md) owns the conduct interface and startup contract; the canonical launcher above owns execution. `ops/bin/conduct` was not found at this base and `command -v conduct` found no PATH entry. Other host installations were not searched. Do not redesign that home or claim live conductor admission. |
| Lifecycle/publication | [workflow genus](../../../docs/workflow.md), [startup lifecycle section](../conductor-start-plan.md#4-owner-initiated-session-lifecycle), [custody README](README.md). `lane_read.py` describes handoff/AAR action implementation as unbuilt; publication remains manual. No lifecycle publisher is delivered here. |
| Discovery | [discovery contract](../discovery-lever.md), [lane_refs.py](../tools/lane_refs.py), [lane_read.py](../tools/lane_read.py), [MCP projection](../tools/lane_mcp.py). Readers are present; source presence is not host activation or automatic selection evidence. |
| Onboarding | [onboard.py](../tools/onboard.py) `calibration()` sorts the current tree's `AAR-*.md` files and extracts its newest calibration section as untrusted data. It does not select the retained handoff by itself. |
| Probes | [probe law](../../../docs/probes.md), [lever contract](../probes-lever.md), [this corpus](probes/probes-2026-09-09-agy.jsonl). General `ops/conductor/tools/probes.py` was not found. Author checks are not independent grading. |

Reproduce these local observations at the stamped base with `git show
20f9bcaf2b3ae2152b9cab766637b5a89b71214b:<path>` for each linked source;
`git ls-tree -r --name-only 20f9bcaf2b3ae2152b9cab766637b5a89b71214b --
ops/bin/conduct ops/conductor/tools/probes.py ops/devlane/workflow/wf.py`
checks those exact absent paths. The historical
[home map](../reports/conductor-start-home-map-20260905.md) and
[MCP research](../MCP-RESEARCH-2026-09-05.md) remain pointers, not a fresh
audit or authorization to resume their roadmap.

## Stable Git custody and retrieval

Retain this bundle on `refs/heads/records/agy-closeout-20260909`; never delete
the branch, merge these reports to dev/master, or open a report-only PR.
The local retained branch already resolves to the base, but this snapshot is
detached and switching to it was refused because `.git/index.lock` is on a
read-only filesystem. The launcher must commit these four files with the
provided commit message and retain that commit on the named branch. Until
then the local ref contains the base, not this bundle. No origin tracking ref
for this branch was found locally; network publication was not attempted
under the explicit no-network instruction. Remote custody remains unverified.

After launcher settlement, an authorized network-capable publisher can run
this manual publication command (not executed by this author):

```sh
git push origin refs/heads/records/agy-closeout-20260909:refs/heads/records/agy-closeout-20260909
```

From any worktree of the repository with that local ref, use stable Git reads;
no disposable absolute path is needed:

```sh
git show records/agy-closeout-20260909:ops/conductor/handoff/HANDOFF-2026-09-09-agy.md
git show records/agy-closeout-20260909:ops/conductor/AAR-2026-09-09-agy.md
git show records/agy-closeout-20260909:ops/conductor/handoff/probes/probes-2026-09-09-agy.jsonl
git show records/agy-closeout-20260909:ops/conductor/handoff/evidence-2026-09-09-agy/measurements.json
```

A fresh clone must fetch the published branch into the local retained ref
before using those commands (publication is a prerequisite):

```sh
git fetch origin refs/heads/records/agy-closeout-20260909:refs/heads/records/agy-closeout-20260909
git rev-parse records/agy-closeout-20260909
git show records/agy-closeout-20260909:ops/conductor/handoff/HANDOFF-2026-09-09-agy.md
```

Record the retrieved full commit ID for an immutable read using `git show
<commit>:<path>`. Fetch is deliberately not forced; a divergent retained ref
needs custody reconciliation, not an overwritten history.

Publication alone does not make plain onboard discover/select this handoff.
The existing discovery contract requires enabled `refs/heads/records/`
acquisition and trusted bindings of record ID, kind, exact byte digest, work
paths, lineage and explicit supersedes edges. The report's title, date or
branch name cannot authenticate those bindings. They were not supplied or
created for this bundle. Unbound relevance/selection remains unknown; no
automatic onboard selection is claimed. Implementing lifecycle publication
or extending onboarding remains a proposal, not part of this closeout.

## Left behind, and validation limits

Private transcripts, auth data, host configurations and root spend are not
exported. The sanitized supplied evidence is copied verbatim, including its
historical command provenance; it is not a live-store read or a secret search.
SHA-256: `a20667aed9b851bcb0fce66f0b8fb6d78d4139e7bb7b18547bb1bef572119d94`.
Unrelated branches/processes, global settings, current MCP activation and
earlier broad MCP/conduct work were not audited. The supplied watchdog PID
observation is historical and is not proof that it is still running.

The AAR retains scoped native reported spend, root-exclusion and cache limits,
review-loop lessons, shared-host CI attribution and the distinction between
native defects and fixture contradictions. No financial cost claim is made.
Owner next work is not selected; older roadmap directions are historical,
not new task authorization. Future improvements are proposals only.

The ten corpus rows use the existing serve/nearmiss schema and allowlisted
read commands against the retained ref. Explicit left-behind declarations
cover the exclusions; no absence row pretends to have searched private data.
JSON/JSONL and local links are author-checkable. Ref retrieval remains
unreachable until launcher settlement; no independent probe grading or
general runner pass is claimed. No implementation, policy, source/test edits,
network access, full suite or new framework belongs to this report change.
