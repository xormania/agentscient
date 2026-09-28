# Verified couplings — the code graph's obligations

With contracts defined first, code may be written disjointed —
different producers, different runtimes, different weeks, workers
dying mid-job — and the system still functions, because what joins
the pieces is not shared integration but a verified graph: every
edge between components typed by a contract and checked by a gate.

Coupling is not the enemy; coupling is the thing itself. Real
dependencies are load-bearing. The sin is dark coupling — real
dependencies nobody can check. The graph makes every coupling
first-class: declared, typed, verified, priced.

## The six obligations of every edge

1. **Closure, both directions.** Every real dependency has a
   declared edge; every declared edge has a live counterparty. Dark
   couplings and dangling citations are both findings.
2. **Shape.** Both endpoints conform to the edge's contract —
   schema, wire, fields — checked mechanically.
3. **Behavior.** The counterparty's promises hold, proven by gates
   that fire on planted faults and stay quiet on clean neighbors.
   Contract-verified mocks let either side verify while the other
   does not yet exist — the enabling condition of disjoint work.
4. **Freshness.** Verification is stamped to a version and a date;
   every entry is true of one version on one day. When a
   counterparty moves, the edge's verification is void and
   re-demanded.
5. **Permission.** The edge is allowed: who may depend on what,
   producer firewalls and custody grants expressed as type
   constraints on edges.
6. **Blast radius.** From any change, the graph computes the
   frontier of edges needing re-verification — a change re-verifies
   the frontier, never re-integrates the world.

## Priced coupling

An edge's true cost is its verification cost times its change
frequency. Couplings are not minimized ideologically; they are
bought where they are worth their verification bill.
Tight-and-cheaply-verified beats loose-and-dark.

## External surfaces

Vendor tools and harness features are edges like any other,
consumed through the same triangle: a contract declaring exactly
what is relied on, a probe re-checking the live surface on a
cadence, and a mock implementing the same contract for tests and
staging. No vendor becomes load-bearing; every capability is
exploited while it pays and removable for the cost of a
configuration line.
