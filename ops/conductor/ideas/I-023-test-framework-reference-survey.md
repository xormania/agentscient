# I-023 — the test framework reference survey: ten projects, a vocabulary, and a research plan

- recorded: 2026-09-11, in session, after I-022 landed (PR #140, dev `be090e5`)
- source: owner, verbatim below; the document beside this record was supplied by the owner under `.xor/in/ci-and-tests/` and is copied verbatim, its author not verified
- disposition: open

## In the owner's words
> i have a third incoming - that you HAVE to look at first - standby

> `.xor/in/ci-and-tests/agentscient_test_framework_reference_survey_2026-09-11.md`

## The document

`I-023-test-framework-reference-survey-2026-09-11.md`, copied byte for byte (`sha256sum` `d506d83ea0bb1e47…` under both paths). It is the reference survey behind the research document recorded as I-022: the same measurements (2727 tests, 927 in the conductor suite, the six families at 3.25 to one, lane_mcp at 9.25 to one, the six test-system failure classes), then ten external projects ranked for reference value, a shared vocabulary (invariant, case, generator, world, operation, history, checker, evidence, cost), a proposed `ops/testkit` shape, and a five-phase research plan. Its own change authority line: it proposes research directions only and authorizes no source, CI, test, dependency or workflow change.

## What was heard

The conductor's reading, said in session and recorded here.

The survey adds to the two earlier documents in three places. First, the vocabulary: an operation history retained as evidence and a checker separate from the scenario that produced it, which is the probes contract's corpus-and-runner shape and the concerns contract's reviewer-behind-a-shell applied to tests. Second, the matcher rule: assert only what the contract owns, exact values only where the contract is exact, which is the LD-21 lesson stated as a general rule and the one most worth adopting first. Third, the ranking, which names five projects at priority one; four of them are dependencies (Hypothesis, mutmut, Infection, Foundry) and one is an architecture (Jepsen).

Where it must reconcile with the lane. The dev lane is standard library only: `ops/bin/suites.sh` says so in its header and the workflow installs nothing; the founding rule is that no vendor becomes load-bearing and every external capability is consumed through a contract, a probe and a mock. So the survey's Phase E question, whether Hypothesis or pytest become dependencies, is answered by the law before it is asked: an internal case model with a stdlib generator comes first, and a dependency is bought only with a measured leverage the survey's own guardrail 11 demands. The survey's Phase C pilot on lane_mcp stays second to the end-to-end fixture for the reason in I-022: on 2026-09-11 the stubbed ladder suite could not see LD-23 or LD-24, and the fixture that runs the real driver against a fake CLI is the world the survey describes. Its Phases A and B, a measured census and a per-project verdict of use, borrow or reject, are work a read job can do without touching code, and are the natural first dispatch once item 31 lands.

The Symfony half (Infection, Foundry) belongs to the prod lane under its own rules and is not this lane's to schedule.

## Standing facts it must reconcile with

Measured 2026-09-11 against dev `be090e5`:

- `grep -c 'Stdlib only' ops/bin/suites.sh` → 1; `grep -c pip .github/workflows/ci.yml` → 0; no `requirements*.txt` or `pyproject.toml` at the root.
- The survey's numbers are the research document's, checked in I-022 against this tree: lane_mcp 152308 over 16462 bytes, 186 test files of which 52 set `HOME` by hand and 14 through a helper, 3 ResourceWarnings in the local suites run.
- The external projects' claims are not checked here; the lane has no network in its jobs and the survey cites their own pages. They stand as the survey's, not this record's.

## Next

Settled with the owner in session, not here.
