# The wire — refusals and the four outcome classes

Every component speaks one wire, so outcomes aggregate across any
mix of languages, vendors, and runtimes. A candidate in any language
that speaks this wire is admissible.

## The four classes

| exit | class | meaning |
|---|---|---|
| 0 | — | the verb did what it says |
| 1 | Finding | ran to completion; the result carries findings |
| 2 | Rejection | refused before acting; the refusal wire says why |
| 3 | Abort | stopped mid-act by wall, kill, or conflict — printing its last reading first, leaving durable partials, never residue |

## The refusal wire

One line per refusal, on stderr, exit 2, stdout empty:

    class: expected <what>; found <what>; needed <remedy>

The class is a lower-case token from the component's refusal table.
Expected, found, and needed are each present, in that order. A
refusal that only says "invalid" makes the next actor guess, and
guessing is what the refusal existed to prevent.

## Identity

Writing verbs require an agent identity in full `Name <address>`
form and refuse class `identity` without it. Reads never require
identity — a layer able to refuse a read is itself a finding.

## Absence discipline

Distinguish "looked and found nothing" from "could not look." An
empty list, a zero, and a null are answers — used only when one is
held. The second case is an explicit marker (`UNREACHABLE`, a
refusal, an `unresolved` reason), never a default that reads as a
confident answer. A list that may be empty declares its emptiness on
purpose; an absent key is refused, because silence is not a
declaration.

## Conformance

A registry holds every component that declares this contract, each
with one hermetic refusal-provoking invocation, and a gate asserts
the wire on all of them: exit 2, a single non-empty stderr line, the
class token, expected–found–needed, empty stdout. A component joins
the registry in the change that lands it.
