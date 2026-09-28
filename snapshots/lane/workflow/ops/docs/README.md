# The shelf — owner docs for the dev lane

One doc per topic, created here by you or for you. Every doc opens
with frontmatter (`name`, `description`, optionally `covers:` naming
the paths it describes), and every doc is listed below — a test holds
both directions: nothing unindexed anywhere on the shelf
(subdirectories included, `scratch/` excepted), no links to missing
files.

`covers:` is read on every run by the `doc-covers` check, and it is
read strictly: each entry is a list item naming a repo-relative path,
with no `..` segment and nothing absolute, resolving inside the
repository. Anything else — a path that is not there, a route rather
than a name, a value that is not a list — is refused by name. What
the check proves is that the paths are real, not that the prose about
them is current: no staleness check has been built.

To add a doc: write it, add its line here. To have one written: ask
any harness; the writer follows this file's rules.

Beside the reference docs: [TODO.md](TODO.md) tracks the lane's open
items informally (checkboxes, no frontmatter), and `scratch/` is the
rule-free working space — both deliberately outside the index
discipline below.

The shelf's operating rule: prior output and memory may suggest what to
inspect; only current evidence decides what is true. [tomorrow.md](tomorrow.md)
is the cold-start resume point written in that spirit — intent plus the
commands that re-verify it, never prose as proof.

[STATUS.md](STATUS.md) is the check-in page — untracked, generated
on demand by `python3 ops/docs/refresh.py`, never edited by hand. A
committed copy would rot; absence just means nobody has asked yet.

## Index

- [decisions](DECISIONS.md) — the owner's ratified dev-lane decisions,
  readable by every harness.

- [telemetry](telemetry.md) — the usage/pulse/breaker family: what
  each answers, the grok accounting rule, and what the cost ticks are.

- [tool-audit](tool-audit.md) — which externally-named tools are real,
  which are refuted, and the generator that re-derives every figure
  rather than trusting prose.

- [rust-agent-tooling](rust-agent-tooling.md) — verified landscape of
  Rust CI/diagnostic tools for the lane: adopt now, adopt with the
  workspace, avoid — and where each plugs into the gate registry.

- [cue-sys](cue-sys.md) — what CUE turned out to be for in agent work:
  bounding and proving an agent's context, not validating its data.
  Each lesson carries the incident behind it.

- [cue-aar-equality](cue-aar-equality.md) — four CUE constructs that
  read as constraints and enforced nothing, each passing its negative
  test while doing so. The companion to cue-sys.

- [mini-app-lessons](mini-app-lessons.md) — what building the dev-lane
  mini apps taught, kept so the prod-lane versions can be written
  better. A running document; add while the measurement is on screen.
