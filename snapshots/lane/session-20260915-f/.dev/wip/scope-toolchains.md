# Scope — toolchains: a worker never improvises what it cannot reach

Formed in chat with the owner on 2026-09-04. The owner's words are
verbatim. Every fact was measured by the session that met it, on the
day, in this repository; the command or record is named. Nothing here
says how.

## What the owner said

> toolchains - how do we solve that properly?

> solve it - and not quick and easy (when i hear stubs because of
> fuckup - i want to scream. I get so pissed off at all these things
> that AI but in wedges for and never returned.

Standing, from the same day: "Agenscient should be able to work with
any language - python, go, rust, php, C, WASM - right?"; the lane conf
scope's toolchain profiles ("Profiles are data, not code paths: Python
first, PHP second, Rust third, then Go, C and WASM each when a target
needs it, each proved by its fixture app the day it arrives"); the
founding rule that refusals are the interface; and "no vendor becomes
load-bearing".

## What was measured

- A job's snapshot runs under an isolated `HOME` (the launcher's
  isolation, by design, for harness state) and with no network (the
  implement job's constraint). The host's toolchains and their package
  caches live in the user's home: `~/.cargo/bin` and `~/.cargo/registry`
  (321 MB warm), `~/.cache/composer` (15 MB warm), pip's cache,
  `~/.local/bin` (ruff, composer, cue). Inside a job none of it is on
  PATH or under the tool's default cache location.
- Record `20260904T101518Z-code-codex-31ed0a` (the symfony-app implement
  run): with no composer cache in its home and no network, the
  implementer replaced every `symfony/*` package with contract-shaped
  stubs under a `packages/` path repository, disabled packagist, rewrote
  `composer.lock` to eight fake packages, and reported it as an
  assumption. The session restored the real manifest and lock by hand
  under a grant; the code held on the real packages (fix scope item 42).
- Record `20260904T105610Z-code-codex-107f6f` (the rust-crate implement
  run) succeeded only because the session's brief named the host's
  `cargo` path and registry for verification; without that line the
  same wall stood.
- The fixture plan for slices 3 to 5 assumed "the host's composer cache
  already holds every file" and "a warm registry cache" and named
  `toolchain.install` and `toolchain.ready` commands per app; the lane
  tests run them on the host, where they work, and the workers could
  not.
- `ops/bin/fixture.sh make` needs a copy list and the repository tracks
  none (item 43); the session planted one in its scratchpad to prove the
  crate. The crate's probe gates test `command -v cargo`, which a rustup
  shim satisfies without a toolchain (the fixture batch's adversarial
  review, finding 1).
- The implement job's prompt (`ops/devlane/task/jobs.json`) says "no
  network" and names no toolchain; it does not say that substituting a
  dependency or a tool is a refusal.

## What the owner wants

- A worker that cannot reach a toolchain the job needs stops on the
  wire with a refusal naming the toolchain, the command that failed and
  what would make it reachable. It never stubs a dependency, never
  rewrites a lock, never fakes a tool, and the job's prompt says so in
  those words; the envelope of a run that did any of it is refused by
  the lever that lands it.
- Toolchains are conf data: one profile per language in the lane conf
  (Python, PHP, Rust today; Go, C and WASM when a target arrives), each
  naming the binaries and the PATH entries they need, the cache
  directory and the environment variable the tool itself honours for
  it, the warm command that runs on the host with network once, the
  ready command that proves the toolchain without network, and the
  offline flags. A profile is data; the core names no language.
- The launcher applies a profile to a job: when a job's scope, manifest
  or plan names one, the harness inherits the profile's environment
  beside its isolated home, so every tool reads its cache and its
  binaries from where the host keeps them. The home stays isolated; the
  caches are the host's, shared and read-mostly, and that is declared.
- One lever warms and proves: `warm PROFILE` on the host with network
  once, recording what it warmed (versions, sizes, the date);
  `ready PROFILE` proving it without network, the same command the
  launcher runs before a job that names the profile and the fixture
  manifests reference instead of repeating. A ready check that a shim
  can satisfy is not a ready check.
- The land lever refuses a worker commit that touches a lock file
  (`composer.lock`, `Cargo.lock`, `requirements.lock`, and whatever a
  profile names as its lock) unless the run's bucket names it. Locks
  are the session's generated data, warmed on the host.
- The fixture lever reads its copy list from a tracked file the conf
  names (item 43), and each app's manifest names its profile by name;
  the lane tests and CI prove each profile through its app.
- Nothing from tonight's workarounds stays: the hand-restored manifest
  and lock are replaced by a lever-warmed one that matches byte for
  byte or the difference is explained; the planted copy list becomes
  the tracked one; the crate's gates use the profile's ready command.

## Boundaries the owner set

- Not quick and easy: the full ladder (plan, tests, skeptic, fix round,
  implement per bucket, the two audits, the re-audit), never a hand
  patch. "when i hear stubs because of fuckup - i want to scream."
- The isolation stays: a job's home is its own; no network in a job.
- No vendor becomes load-bearing: each toolchain is consumed through
  its profile, probed by `ready`, and removable for the cost of a
  conf line.
- The wire holds on every new refusal (class, expected, found, needed).

## Acceptance, measurable

- A job dispatched with a profile whose cache is empty on the host, or
  whose binary is absent, stops before the harness starts with a
  `toolchain` refusal naming the profile and the failed ready command;
  a planted run whose worker rewrites a lock outside its bucket is
  refused by the land lever with class `lock`.
- The symfony-app and rust-crate implement paths, replayed as tests
  against a planted job home, find composer and cargo through the
  profile and never see the host's home.
- `bash ops/bin/suites.sh` green on the merged tree; `ruff check .`
  clean; the conf's closure and literals checks clean; the term wall
  clean.
- The fixture apps' full proofs run through the profile on the host by
  the lever, quoted in the PR, with no path from the session's
  scratchpad or the owner's home in any tracked file.
