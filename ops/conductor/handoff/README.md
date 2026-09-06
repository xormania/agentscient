# handoff — deterministic hand-over

Context custody across a session boundary is tested, not trusted to
memory (`docs/probes.md`; `../probes-lever.md`). What lives here:

- `HANDOFF-<date>[-topic].md` — a closing session's hand-over: state
  measured at close, the open threads, what only a person can say. The
  measured part shrinks as `onboard` grows; the human part stays.
- `probes/*.jsonl` — the probes corpus: `serve`, `absent`, and
  `nearmiss` rows a runner executes, the answer key that never travels.
  Empty by declaration until the first session closes here; the runner
  (`probes.py`) is contract-only everywhere so far.
- `evidence-<date>/` — a session's evidence, copied beside its hand-off
  so what was asked and what happened are one record.

The after-action reports live one level up as `AAR-<date>[-topic].md`;
the newest one's calibration clause is what `onboard` serves as the
thread. A holding with neither a probe row nor an explicit left-behind
declaration is the hand-over failing, named.

Candidate discovery across tracked files and the retained-ref namespace
`refs/heads/records/` is specified in
[`../discovery-lever.md`](../discovery-lever.md). Publication remains
manual; discovery does not write these records.

## Discovery metadata extension

The corrected [discovery contract](../discovery-lever.md#record-identity-trust-and-selection)
specifies the smallest missing custody metadata: record ID, kind, exact byte
digest, work paths, lineage and explicit supersedes edges. Until a separately
authorized publication step produces this metadata through the existing record
lineage, trusted launch configuration may bind it to existing bytes. No new
store or ref namespace, and no rewrite of older records, is required. A record
cannot authenticate itself by declaring these values in its body, title, date
or branch name. Unbound records remain visible as unknown relevance; incomplete
evidence cannot establish a unique handoff. AARs are reports governed here,
never their own contract or authority. Onboard's existing newest-filename
thread behavior stays unchanged; discovery's selection is a separate read.

The House's hand-over records do not cross. This directory begins with
the substrate work of 2026-09-02, which was this project's own session.
