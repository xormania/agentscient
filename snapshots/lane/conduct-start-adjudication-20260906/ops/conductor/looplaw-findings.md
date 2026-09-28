# What to take from looplaw — read 2026-08-30

Read: `README.md`, `schema/trinity.cue`, `schema/gap.cue`,
`internal/gate/ratification.go`, `internal/outcome/outcome.go`, and the tree of
`internal/`, `cmd/`, `dev/`. **Not read:** `internal/gate/trinity.go` (45KB),
`submission.go`, `store/`, `diff/`, `conformance/`, `provenance/`, and every
test file. Everything below is doctrine visible in what was read; no claim is
made about the implementation's completeness.

Owner: "looplaw is in its infancy" and "do i finish looplaw or do we move into a
framework? I tend to think framework."

## 1. The failure taxonomy — the single most useful thing in the repository

`internal/outcome/outcome.go`, verbatim:

> every non-advancing result is one of four classes, and **none of them is a
> generic "error"**.
>
> - **Rejection**: a malformed submission or breached client precondition.
>   Nothing commits; the gate keeps operating.
> - **Denial**: a well-formed submission the deciding authority declines. **A
>   successful execution — recorded, never routed through error handling.**
> - **Abort**: an infrastructure failure. Nothing commits, no partial records.
> - **Finding**: on verification paths (which commit nothing), an item the
>   checks cannot process — **first-class, never skipped.**

**This repository conflates all four.** A dispatch that ends badly is `invalid`,
or exit 2, or exit 3, with the distinctions carried in prose. Concretely:

| ours | looplaw's class |
|---|---|
| schema-invalid envelope (A-2, extra keys) | **Rejection** |
| `read-role-head` refusal after a good run (D-ENV-4) | **Denial** |
| a 900s timeout, no residual | **Abort** |
| "GitHub API unreachable, so X is unmeasured" | **Finding** |

A-2 cost three envelopes and their findings today precisely because a
**Rejection** was handled as though the run had produced nothing, discarding
first-class **Findings**. D-ENV-4, ratified tonight ("a refusal annotates the
envelope, it never replaces it"), is a partial rediscovery of the Denial rule —
looplaw states it as one of four with a doctrine behind it.

**Recommendation: adopt the four classes as the envelope's `status` vocabulary**
in the framework, replacing `ok | invalid | tripped`. It is a contract change,
it subsumes D-ENV-4, and it makes "unmeasured" a recorded outcome rather than an
absence.

## 2. A refusal is structured protocol, with a remedy

`outcome.Refusal{Class, Check, Subject, Reason, Remedy}`, and:

> Refusals are protocol, not UX: they are fed back to authoring callers for
> retry, **so the remedy is part of the contract**.

Our launcher already writes good remedies — "satisfy by name a dispatchable
job" — but as prose in a stderr line. As data, a caller can act on them, and a
conductor can be refused *and told what to do* without reading English.

## 3. "An undemonstrated gate is an unproven behavior"

`RatificationChecks` enumerates every check the gate can emit —
`ratify/unbound`, `ratify/authority`, `ratify/target`, `ratify/standing` — and
the comment states the suite **proves a red for each**.

That is exactly the discipline this session had to enforce by hand: the
containment lint's four FAIL plants, the mutation-shaped questions in every
bounded skeptic brief. looplaw makes it structural — the check list *is* the
test manifest, so a gate with no demonstrated refusal is a known gap rather
than an assumption.

## 4. Ratify and amend are different acts, and standing is not self-conferred

- `ratify/standing`: "ratification is a draft's **first** standing; changing law
  that already holds it is a different act" — the remedy names `amend` and,
  honestly, that the binary does not implement it yet.
- `ratify/authority`: "ratification is not delegable, and **a party cannot
  confer standing on its own work**."

**This one lands on the conductor directly.** Tonight ~10 decisions were
recorded `ratified_by: conductor, Claude Fable 5` — the conductor drafting and
conferring standing on its own design. Under looplaw's model those are
*declarations*, and only the accountable authority ratifies.

The difference is real but resolvable: this owner **explicitly delegated** design
ratification ("not me - you have to know how to design a framework"; "policy: my
job is to get you the right policy"). That delegation is the authority binding,
and it should be **recorded as such** rather than assumed by the conductor every
time it signs its own work. The framework should carry the binding as data.

Second consequence: this session amended ratified clauses repeatedly (D-ENV-4,
D-LAW-COV, D-IMG-1/2) using the same word and the same weight as first
ratification. They are different acts with different preconditions.

## 5. `#Gap` — the project-management primitive, and it belongs to the board

`schema/gap.cue`: `#GapKind: absent | added | changed`, `#WorkKind: fill |
split`, `#GapStatus: open | in-work | satisfied | **proven-too-expensive**`,
content hashes on both sides for staleness, and:

> For proven-too-expensive: the recorded amendment-path reference this
> termination initiated (**law is never left standing violated**).

Declining to fix something forces a recorded amendment. Board v1 detects gaps
with four queries and has no gap object, so a detected gap has no status, no
lifecycle, and no honest way to be declined.

## Verdict on the owner's question

**Framework, and mine looplaw for doctrine rather than depending on it.**

Every item above is expressible in Python and CUE inside the framework we are
already building. None of them requires a Go toolchain pinned in CI against an
API in infancy, and the two systems address different domains — looplaw governs
a target system's architecture (parties, acts, contracts between components);
ours governs process obligations (who may amend, what a record carries, when a
refusal fires). Same shape, different subject; sharing a name would be the
conflation `vocab.cue` exists to prevent.

**But the earlier recommendation was too thin.** "Take four schema ideas into
U2" understated it. Items 1, 2 and 3 are framework-wide and belong in the
kernel-equivalent (`container`) and the envelope contract, not only in a
registry schema. Item 4 changes how this repository records its own decisions,
today.

**Still unread and worth reading before U3:** `internal/gate/trinity.go` — the
45KB main gate — to see which obligations are enforced versus declared.
