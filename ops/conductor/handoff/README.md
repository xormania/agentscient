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

The House's hand-over records do not cross. This directory begins with
the substrate work of 2026-09-02, which was this project's own session.
