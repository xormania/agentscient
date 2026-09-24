# PR-01: observation and explicit measurement

Original implementation came from the preceding chat. This follow-up reviews
and finishes PR #296 directly in chat at xor's request, 2026-09-24. The broken
dev-lane dispatcher is not a prerequisite for this repair. Independent second
reviewer absent. Baseline: `50e675a5304689dc314b8d707d0c9a306c1255b5`.
Delivery destination: `dev`, through a reviewed draft PR and passing CI.

## Contract

1. `deliverable show` and its compatibility `--unmeasured` option read only
   recorded state. Onboard and the routine Stop lookup never run measurements.
2. `done BRANCH` runs the declared command once and records its result in the
   existing target, with time, source checkout, candidate reference and actor.
   Failed measurements remain failures. Retargeting discards the old projection.
   A target that changes during measurement must not be overwritten.
3. A command string does not declare all verification inputs. Its recorded
   result is historical: applicability is unknown and status remains unmeasured
   until the structured evidence work supplies a trustworthy input binding.
   A recorded success, missing evidence, or stale candidate never authorizes work.
4. Hand, findings and skills readers use `instrument.connect_store` read-only.
   Only explicit domain writers initialize or migrate their schemas. Reads
   preserve files, directories, rows and schema; SQLite read infrastructure is
   not an application lifecycle mutation.
5. Missing, unreadable, corrupt, locked and incompatible stores stay distinct
   on the existing refusal wire. A store error cannot become a nominal empty
   registry, open grant, accepted finding or successful measurement.
6. Plain findings exports, including calibration, write only stdout. Exporting
   to a file is explicit `--write [PATH]` and requires writer identity; it does
   not initialize the source database. Existing explicit removal verification
   stays in `deliverable remove`; completion-policy consolidation is PR-07.

## Validation record

The follow-up started from GitHub head
`cf85d31fd45a9a0d85ccf7adacdd44583aba1132`. An authenticated source bundle
provided the baseline; applying the PR patch reproduced all 2,465 source blobs
from that head, verified against the GitHub tree. Follow-up changes explicitly
initialize the skills fixture before asserting an unknown row and update six
existing corpus expectations to the PR-01 observation contract. Production
implementation files remain unchanged.

The original full CI run [35945700010](https://github.com/uscient/agentscient/actions/runs/35945700010)
finished all 19 lane checks with six failing/unreachable corpus rows and one
failing test:
`test_skills.Refusals.test_an_unknown_skill_refuses_skill`. It expected a
`skill` refusal from an absent store, which correctly returned a `store`
refusal under PR-01. The same failure reproduced in this chat. The fixture
now creates a known row through `add` before looking up `nosuch`; missing
stores continue to refuse without initialization in the storage fault cases.
The app job passed in that original run. The first follow-up missed the six
corpus failures when isolating the fixture failure; they were already present
in the original run, not introduced by the follow-up report.

Follow-up run [35947283283](https://github.com/uscient/agentscient/actions/runs/35947283283)
at `7b553789dbd6b95633ded9e67f8b9e0e13e6de3e` passed every test family and
the app job, but correctly remained red on those six corpus rows. They still
expected the previous status/measurement wording in the changed deliverable
and refusal pages. The six failures reproduced directly with the existing
probe runner. Their questions and IDs remain; the expectations now distinguish
recorded status, explicit measurement, an absent lock and a removed branch.
The `/goal` near-miss still checks that the judge runs nothing.

After correction, all 14 rows across the three affected existing corpus files
and the new PR-01 corpus file passed through `probes.load_corpus`, `run_row`
and `report`: zero failures, zero unreachable. These are retrieval checks;
the behavior evidence remains the test families below. No corpus row or
required check was removed or skipped.

Direct validation below ran in this chat's Linux sandbox. The local
verification snapshot is `d1a6808d`; it contains the original implementation
and the four-line fixture correction. Corpus checks above ran against the
working tree with the subsequent expectation corrections. Required final CI
results are linked on PR #296 after the follow-up commit is published; these
focused checks do not replace that gate.

### Previous dispatcher audit: invalid, excluded

Workflow [35945681015](https://github.com/uscient/agentscient/actions/runs/35945681015)
was green and its shell exit file said zero, but artifact
`pr01-native-security-audit`, record `20260924T020432Z-review-codex-d5243a`,
contains `status: invalid`, `verdict: null`, and no findings. Its hooks blocked
`lane_brief`, repository reads and even its suggested diagnostic. No source
review occurred. This is a failed review attempt, not a clean audit.

Xor's current direction is to finish this repair here because the dev-lane
machinery is broken. This follow-up therefore reviews the changed source and
runs its deterministic checks directly. It does not rerun the dispatcher or
represent the invalid result as security evidence. No independent native
security-audit pass is claimed.

### Read-call map

| Entry point | Existing owner and behavior after this change |
|---|---|
| `deliverable show`, `show --unmeasured`, `target_line` | `load_lock` reads JSON and renders recorded metadata; no command, identity, flock or write. |
| `onboard.lock_lines` | Retains its existing `show --unmeasured` call, now receiving the richer recorded status. |
| Stop `engine._lock_reading` | Explicit compatibility `show --unmeasured`, bounded at five seconds even against an older installed lever. |
| `deliverable done` | Deliberate measurement: executes once, records success or failure additively in the existing target, and rechecks target equality before writing. |
| `deliverable remove` | Existing deliberate live verification retained; lifting work is a mutation, not an observation. |
| Hand `open`, `report` | `hand.connect()` uses the shared read-only primitive; `declare`/`settle` use its explicit writer mode. |
| Findings `summary`, `cited`, `export` | `findings.connect()` uses read-only access; calibration export is stdout unless `--write` is explicit. |
| Findings imports, dispositions, calibration updates | Same domain owner with explicit writer access; legacy migrations happen only there. |
| Skills `list`, `show`, `report` | `skills.con_()` uses read-only access; sync/add/note/retire/event writers initialize explicitly. |
| Shared `instrument.connect_store` | Optional required-column validation, no second connection helper; other callers retain native exception behavior. `store_failure` maps reader errors to the existing refusal wire. |

Reviewed source callers with repository-wide searches for `deliverable.py`,
`reading`, `target_line`, `connect`, `con_`, and imports of the three instruments.
Updated current deliverable/refusal skills and instrument/findings documentation;
historical reports remain historical. Completion-prose parsing, refusal caps,
coordination authority and PR acceptance remain their existing owners (PR-07).

### Focused behavior and faults

The existing testkit, fixture stores and test families were used directly.
Commands are `python3 -m unittest discover -s ops/conductor/tests -p PATTERN`,
except the hook tests, which use `-s ops/devlane/hooks/tests`.

| Pattern / command | Executed result in this follow-up |
|---|---|
| `test_skills.py`, original PR head | 12 tests; one failure, matching CI. |
| `test_skills.py`, after fixture correction | 12 passed with the same command. |
| `test_skills_registry.py` | 23 passed. |
| `test_deliverable.py` | 18 passed. |
| `test_storage.py` | 11 passed. |
| `test_handwork_ledger.py` | 31 passed. |
| `test_findings*.py` | All 61 passed. |
| `test_instrument*.py` | 87 passed. |
| `test_engine.py` (hooks) | 33 passed. |
| `test_onboard_lever.py -k TheLockLine` | Seven passed. |

Total: 283 passing focused tests, no skips. The earlier report mislabeled the
23-test skills-registry run as `test_skills.py` and the handwork run as
`test_hand.py`. Discovery with `test_hand.py` collected zero tests and was not
counted as a pass; the correct command and its actual result are above.

The storage family exercises 54 read/fault combinations: missing, corrupt,
locked, incompatible, unreadable and populated stores across hand, findings
and skills. Snapshots compare domain bytes, modification times and directory
entries; read-time identity acquisition is a planted failure. A real WAL
fixture checks committed rows remain visible. Legacy findings reads refuse
without migration; explicit writers preserve existing dispositions while
migrating. CLI missing-store refusals and read-only write rejection also pass.

Deliverable fixtures cover failed and successful explicit measurements,
absent and invalid locks, marker nonexecution through show/onboard/Stop,
historical metadata, retargeting and concurrent target replacement. Review
of the source confirmed that read adapters use the shared read-only opener;
measurement retains bounded argv execution; publication rechecks the held
target; explicit file exports require identity. Recorded results do not
become a current applicability decision.

Mutation calibration on the local verification snapshot:

```sh
python3 ops/testkit/cases.py calibrate \
  --subject ops/conductor/tools/deliverable.py \
  --mutants ops/conductor/tests/deliverable_faults.py \
  --command 'python3 -m unittest discover -s ops/conductor/tests -p test_deliverable.py -k show_unmeasured'
```

Clean: green. All three planted faults caught; zero quiet faults:
`M-unmeasured-measures`, `M-any-option-admitted`, and
`M-done-does-not-measure`. This calibration supplements the full deliverable
family rather than replacing it.

### Same-host latency, repeated in this follow-up

Python 3.12.14 on Linux x86_64, in the same chat sandbox for baseline and
candidate. Existing `World`, fake tools and `run` supplied three targets,
each with a measurement that sleeps 50 ms. Each sample starts a new CLI
process. First means process-cold, not a cold filesystem cache; repeated is
the median of the next two reads. These observations do not predict the
operator host's latency.

| Operation | Baseline first / repeated | Candidate first / repeated | Measurement starts across three reads, before / after |
|---|---|---|---|
| `show` | 0.267 s / 0.264 s | 0.046 s / 0.050 s | 9 / 0 |
| `show --unmeasured` | 0.048 s / 0.047 s | 0.045 s / 0.047 s | 0 / 0 |

The compatibility alias already avoided measurement. Ordinary display now
shares that property. No arbitrary response-time gate was added.

### Migration, rollback and remaining boundaries

No archive conversion, new database or destructive schema cleanup is required.
Old targets remain unmeasured until explicitly measured; recorded command
results still report unknown applicability until structured evidence binds
all verification inputs. `candidate` is the checkout HEAD observed before the
command, not an assertion that the working tree was clean or all external
inputs were captured. Status therefore cannot turn that metadata into a pass.

Read access never imports data. Existing explicit writer operations retain
schema creation/migration. File export is an intentional write and now needs
`--write`; callers requiring a saved calibration export must select it.
A rollback must retain non-measuring onboard/Stop callers and must not
reintroduce automatic initialization into status paths.

Changed zones are conductor instruments, their shared storage primitive and
the Stop observation boundary. Their regression floor includes the full
native lane plan and both configured `lane`/`app` checks on the PR merge tree.
Local focused checks do not replace that floor. No Symfony application or CI
routing configuration is changed. The temporary authenticated source/publish
transport is removed from the final tree before readiness.

The actual user's worktrees, runtime databases and active sessions were not
accessible from this sandbox. None were cleaned, pruned, replaced or claimed.
Follow-up fixtures used separate sandbox state; no live dispatch, grant or
operator-state workflow was used to perform this repair.
