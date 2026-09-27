# First policy code bucket — structural record evidence

Authorize only the first bounded bucket identified by GPT-6 execution-seam plan 20260906T031249Z-plan-codex-0fa801. This does not adopt its proposed CLI flags or the rest of its integration plan. The existing public APIs are record.build(payload) and record.validate(rec, expected_id=..., expected_snapshot=...). The published lane-policy contract owns brief.policy's binding shape. Structural validation is not permission admission.

The planner measured these existing APIs accepting string, null and empty-object brief.policy at ref 2ecf00e8de4c609b0b5bfd613e82d71ac7c2c9d7. The intended red is an assertion that malformed policy evidence is refused. Use the real current module and the existing _RecordCase._minimum fixture in test_record.py; no missing-module stand-in, echo fallback, skips or import-error red. Test authors must not read record.py or any future implementation. Existing tests/helpers and the contract are the allowed sources.

The independent test producer owns only ops/devlane/dispatch/tests/test_record.py. Test invalid presence (string, null, empty object), required binding fields/types, schema/path and Git-id/digest shapes, template digest equality, syntactic profile id, and the already specified maintenance container/list constraints. Positive neighbors cover a complete valid binding, null maintenance where allowed, a syntactically valid synthetic profile without membership lookup, and legacy records with policy absent. Check build and validate through their existing APIs. Do not test or invent the proposed new CLI/anchor/dependency/result interfaces; incomplete integration interfaces are later work. If a listed structural field is not actually fixed by the owning contract, report that precise gap rather than inventing a schema.

Prove the command red on named intended assertions with zero import/collection errors, while existing tests and positive neighbors pass:

`python3 -B -m unittest discover -s ops/devlane/dispatch/tests -p test_record.py`

Grok authors tests; Claude independently checks them; GPT-6 implements record.py only after the test boundary is accepted. The implementer neither writes nor approves the tests. Root conducts through dispatch.sh with explicit model and branch; the planner's illustrative --worktree commands and Codex test-author assignment are not executable instructions for this cycle. Use the existing read-only inline-review transport for the skeptic while native report-output grants remain unresolved.

Implementation later runs the identical command to green and the required ops/bin/suites.sh gate. Absent-policy legacy records and current record identity/result checks remain unchanged. No active policy selection, new CLI, host/decision store, grant widening, source-dependency checker or full enforcement claim belongs to this bucket. Partial work remains inert until the reviewed minimum complete activation boundary is implemented and admitted.
