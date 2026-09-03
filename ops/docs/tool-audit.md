---
name: tool-audit
description: Which externally-named tools are real, which are refuted, and the generator that re-derives every figure instead of trusting prose.
covers:
  - ops/docs/tool-audit.py
  - ops/devlane/workflow/gate-kinds/
---

# Tools we were told about, and what is actually there

Three research reports arrived naming roughly sixty external tools
between them. Some are load-bearing projects with millions of
downloads. Some do not exist. Nothing in a report distinguishes the
two, because a report is prose and prose runs nothing.

This page holds the durable half of that audit — the verdicts, and
why. The numbers are not written down anywhere, on purpose. Ask for
them:

```sh
python3 ops/docs/tool-audit.py
```

`rust-agent-tooling.md` states the problem this closes, in its own
words: *"tool freshness rots and `covers:` cannot watch external
projects; only the repo-facing claims are mechanically checkable."*
A version number written into a document is a measurement that
outlived what it measured. So no figure appears on this page at all,
and none is committed anywhere else either.

## The rule

**A tool does not enter a gate kind until it has been through the
audit.** A registered check naming something nobody installed reports
nothing, and a check that reports nothing is indistinguishable from a
check that passed — which is the failure the whole lane is built to
refuse.

The generator refuses in three ways, for the same reason:

- a name the registry does not have prints **ABSENT**, which is a
  finding about the name rather than an error in the run;
- a name that could not be reached prints **UNREACHABLE**, and is
  never rendered as though it were healthy;
- if nothing at all was reachable, nothing is printed and the exit is
  non-zero, because a report of `UNREACHABLE` rows still reads as an
  audit at a glance.

## Refuted — named in a report, not fit to register

- **rustyspec** — no crate. A single-author CLI, sourced from one
  Medium post, presented as a spec-to-failing-test bridge.
- **ax-rust-agent-observability** — not a Rust tool at all. It is a
  `SKILL.md` entry in Tessl's registry, describing another crate's
  hooks. The lane's own telemetry already does this job.
- **mcp-framework** — no crate; the repository is a dormant hobby
  project.
- **cue-rust** — sold as a Rust-native CUE implementation you could
  embed instead of shelling out to Go. Run the generator and judge
  that claim against what is actually behind it. Shell out to the Go
  `cue` binary.
- **cargo-pmcp** — genuinely active, but built on a **third-party**
  MCP SDK rather than the official one. Its SARIF output is a good
  idea worth copying; the dependency is not.
- **agent-harness** — a unified event vocabulary across Claude Code,
  Codex and local models. Interesting, because
  `ops/devlane/telemetry/usage.py` already holds three harness
  accountings. Read it; do not depend on it.
- **cargo-mcp** — presented as *the* cargo MCP server. Check its
  release age before believing that.

### One name collision, which is worse than an absence

A report cites **Anda** (`ldclabs/anda`) as a Rust agent framework.
The crate published under the name `anda` is an unrelated Linux
packaging toolchain from a different organisation. The framework
publishes as `anda_core` and `anda_engine`. Following the citation
installs the wrong software, silently — an absent name fails loudly,
a collided one does not.

## Two figures that had already rotted

Two version numbers in one of the reports did not match the registries
when they were checked on 2026-08-22: **`rmcp`** and **Anodized**, both
understated. What the registries say today is a question for the
generator, and this page deliberately does not answer it — an earlier
draft of this section named the versions, which made it an instance of
the exact failure it describes (Codex and Grok, PR review of 5387cd2).

Neither error was careless. They are what happens to any number that
is written down once and then read later, which is the argument for
the generator rather than an argument against the reports.

## Where the verdicts came from, and what they rest on

Every **figure** was checked against the crates.io API and the GitHub
API directly, not against blog posts or the reports themselves.

The **verdicts are not purely mechanical**, and the distinction
matters. "This name has no crate" is a registry fact. "This is the
official SDK", "this is a dormant hobby project", "this is bound to a
third-party SDK" are judgements resting on the registries *plus* the
three research documents the owner supplied *plus* reading the
projects. Where a `why` line asserts something an API cannot show, it
points at the figures the generator prints rather than asserting a
conclusion the reader cannot check.

One ambiguity the generator cannot resolve: an unauthenticated GitHub
404 is also what an existing **private** repository returns. A repo
row reading ABSENT means GitHub said not-found to an anonymous caller,
which is not quite the same as "it does not exist".

For what to do with the tools that *did* survive — where each plugs
into the gate registry, and in what order — see
[rust-agent-tooling](rust-agent-tooling.md), which this page is the
mechanical backing for.
