# PR-01: observation and explicit measurement

Owner-authorized dev-lane hand work, one producer (GPT-6 Astra Pro);
independent second producer absent. Baseline: `50e675a5304689dc314b8d707d0c9a306c1255b5`.
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

Implementation behavior was measured in a clean Linux sandbox against the
source at `840a974a` (the code/test commit); this report and its custody probe
are additive documentation. Native CI and the required security audit are
separate readiness requirements, recorded on the PR when actually completed.
No independent audit, full native CI pass or operator-host rehearsal is claimed
by the local results below.

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

Commands below use the existing testkit, real tools, bounded subprocesses,
fixture stores, and existing test families. No new test framework was added.
The conductor tests run as `python3 -m unittest discover -s ops/conductor/tests
-p <pattern>`; hook tests use `-s ops/devlane/hooks/tests`.

| Pattern / command | Executed result |
|---|---|
| `test_deliverable.py` before implementation | 17 tests, eight failures: the new observation/measurement behavior was red. |
| `test_storage.py` before implementation | 10 tests; 13 failed subcases and 26 errors, including the absent writer-mode API. |
| `test_deliverable.py` after implementation | 18 tests passed; same discover command as red. |
| `test_storage.py` after implementation | 11 tests passed; same discover command as red. |
| `test_hand.py` | 31 tests passed. |
| `test_skills.py` | 23 tests passed. |
| `test_findings*.py` initial run | 61 tests, two export-fixture failures caused by their old automatic-initialization assumption; the other 59 passed. |
| `test_findings_export_write.py` after explicit fixture initialization | Three tests passed; no claim of a second complete 61-test local run. |
| `test_instrument*.py` | 87 tests passed. |
| `test_engine.py` (hooks) | 33 tests passed, including a real marker-producing target never measured by Stop. |
| `test_onboard_lever.py -k TheLockLine` | Seven tests passed in the isolated rerun. An earlier concurrent run timed out in unrelated one-second fake register/ledger calls; no production timeout was widened. |

The storage family exercises 54 read/fault combinations: missing, corrupt,
locked, incompatible, unreadable and populated stores across the hand,
findings and skills read APIs. Before/after snapshots compare domain file
bytes, modification times and directory entries. Identity acquisition during
reads is a planted failure. A live WAL fixture checks that committed recent
rows remain readable; no immutable-database workaround hides them. A legacy
findings store is rejected unchanged on read, then explicitly migrated while
preserving dispositions. CLI missing-store refusals are also exercised.

Deliverable fixtures cover successful and failed explicit measurements, absent
and invalid lock data, retargeting, stale metadata, marker nonexecution through
show/onboard/Stop, and a target changed during measurement without overwriting
the concurrent update.

Executed mutation calibration at `840a974a`:

```sh
python3 ops/testkit/cases.py calibrate \
  --subject ops/conductor/tools/deliverable.py \
  --mutants ops/conductor/tests/deliverable_faults.py \
  --command 'python3 -m unittest discover -s ops/conductor/tests -p test_deliverable.py -k show_unmeasured'
```

Clean: green. All three planted faults caught; zero quiet faults:
`M-unmeasured-measures`, `M-any-option-admitted`, and
`M-done-does-not-measure`. The full deliverable family above covers the other
behaviors; this narrow calibration does not replace it.

### Same-host latency

Sequential matched-fixture runs used Python 3.13.5 on Linux 6.18.44 in this
sandbox, not xor's workstation. Each fixture had three targets, each with a
fake measurement that sleeps 50 ms. Each sample starts a new CLI process.
"First" is process-cold, not a cold disk/cache claim; OS caches were not dropped.
"Repeated" is the median of the next two invocations. Startup overhead on this
sandbox dominates the post-change result. These are observations, not an SLA.

| Operation | Baseline first / repeated | Candidate first / repeated | Measurement invocations across three reads, before / after |
|---|---|---|---|
| `show` | 2.908 s / 2.975 s | 0.711 s / 0.710 s | 9 / 0 |
| `show --unmeasured` | 0.672 s / 0.684 s | 0.719 s / 0.722 s | 0 / 0 |

The compatibility alias was already non-measuring. The meaningful change is
that ordinary display now has that property too. No arbitrary latency gate
was introduced; operator-host latency and native long-lived sessions remain
unmeasured here.

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
The scoped hand declarations and fixtures used separate sandbox state.
