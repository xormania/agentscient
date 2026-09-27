# I-031 — the cheap session is the dispatcher; the master session sets scope and reads findings

- recorded: 2026-09-16, session agentscient-11 (Fable, lane/session-20260915-e), the evening of the token-efficiency deliverable
- source: owner, verbatim below
- disposition: open

## In the owner's words

> `The Grok 4.6 investigation is dispatched through Sonnet,` I LOVE THAT - GOOD JOB!!!!!

> Note in ideas about using Sonnet as dispatcher - that's brilliant!!!!

## What arrived with it

The owner asked for a Grok 4.6 investigation of WF_AGENT (its history and
the side effects of changing it). The master session (Fable) wrote the
scope in one message and sent it to the Sonnet support session
(agentscient-4c), which read ops/README.md and the dev-lane skill, cut
lane/session-20260915-i from origin/dev at f9e48c35, chose the sweep job
by its contract, trimmed the scope to 1,009 bytes under the 1,024-byte
scope cap, and ran ops/bin/dispatch.sh. The first launch refused exit 3,
class isolation, on a grok credential 28.4 hours old (the LD-18 class);
Sonnet classified it through the dead-dispatch skill and surfaced the
device-code login to the owner rather than relaunch. Everything after
the scope, the job choice, the record, the pid file, the triage, comes
back to the master as a bounded reply.

Why it pays, as measured this evening: the lane law a dispatcher reads is
ops/README.md, 12,253 bytes by `wc -c` at bbdcc651, plus the dev-lane
skill, and a session re-reads what it holds into every later turn. The
master session's context read 186.8k of 1M by `/context` at about
02:55Z, 154.7k of it messages, with none of that law in it; how much the
dispatch would have added to the master is not measured. The standing
rule is T-69 (Fable decides and delegates); this idea names the dispatch
itself as a delegated mechanic, with the cheapest session as its owner.

## What a ruling would have to settle

- the dispatching session owns the dispatch record, the pid file and the
  triage, and reports the record id to the master the moment it exists;
- the scope is the master's words, supplied verbatim as the job's scope
  input (docs/concerns.md: the artifact is supplied verbatim), within
  the scope cap;
- the master reads findings, never envelopes or transcripts; a bounded
  reply with the report path and its first lines is the interface;
- the dispatching session's branch carries the dispatch records, and the
  lock names it beside the master's.

Hardens through the register as a D- row when the owner rules.
