# Scope — fixture apps: a project the lane runs on, with planted faults it must find

Formed in chat with the owner, 2026-09-04. The owner's words are verbatim.
Measured on dev at `e566c33`. Nothing here says how.

## What the owner said

> What are your thoughts on setting up a fixture repo based on a symfony app?

> can you place the repo fixture in this repo (for ease)? And while you
> mentioned it - can we setup the fixture so its easy to prove red?

> place the fixture somewhere we can load it from - somewhere in dev
> machinery dirs? … yes - and i'm not against more fixtures if needed

> python, php Symfony, and rust - for now as fixtures. Just make them good
> - so they can be useful - think about it

> and python needs two, i think, one for dev and one for prod - right?

> but now php/symfony until i'm comfortable with the dev machinery

> but the rust is not a dev fixture - is it? Its potential end-use project
> - and it shouldn't be the only one

## What is there today

`ops/devlane/fixtures/` holds the deterministic store builders the lane's
tests plant (`stores.py`, the envelopes); nothing in the lane is a whole
project the loop can run on. Every run of the loop so far has been on
this repository's own lane, so the lane has never been proved portable
(scope-lane-conf.md), never graded against a known fault (docs/concerns.md
§Calibration: "a concern without fixtures is a declared gap"), and never
run on PHP.

## What the owner wants

- Fixture apps live under `ops/devlane/fixtures/apps/<name>/`, apparatus
  of the lane, never product code: a README that says so, a minimal
  project skeleton at the project's own pins for the first one
  (`symfony-app`: Symfony 8.1.*, PHP >= 8.4, composer manifest and lock,
  a few services and one test suite), and room for more: one fixture
  app per toolchain profile the lane must handle. A fixture app is
  apparatus and never a product: the Rust one is a minimal crate with
  planted faults that proves the Rust profile, never a real project.
  Target projects (Rust projects, Agentscient itself in PHP by
  dogfooding, others as they come; no named first target — owner,
  2026-09-04: another project "i never intended for it to be part of
  the conversation other than it another project that ma be useful")
  are end use, live in their own repositories, and are several; a
  fixture app rehearses the install into that kind of project.
- A manifest per app, `FAULTS.json`: one row per planted fault with an
  id, a kind (security, defect, test gap), the location, the finding a
  reviewer should make as a quotation pair (the declared words and the
  practiced evidence), a severity, and a clean neighbour that must not be
  flagged (a similar-looking place with no fault).
- A probe per fault: a command that exits non-zero while the fault is
  planted and zero once it is fixed, so a fault's presence is proved
  mechanically. "Easy to prove red" is the acceptance: every probe red on
  the fresh fixture, every probe green after the planted fix.
- One lever, `ops/bin/fixture.sh`: `make <app>` copies the app and the
  lane (the same files the lane conf's copy rule names) into a scratch
  directory, initialises a repository there and commits, so every run
  starts from a known state and the lane is proved portable each time;
  `prove <dir>` runs every probe and expects red; `prove --fixed <dir>`
  expects green; `grade <record> <app>` reads a review record's envelope
  against the manifest and prints caught, missed and false positives per
  reviewer — the measured rates the concerns contract asks for, written
  to the findings ledger with the app and fault ids.
- The first fault set per app: six to eight from the shared kinds, each
  with its clean neighbour (the section below).
- Four apps for now (owner: "python, php Symfony, and rust - for now";
  "python needs two, i think, one for dev and one for prod"), one S
  slice each, Python tooling first. The fixture is where PHP work through
  the loop happens first. Nothing PHP lands in the product from this
  scope.

## What makes them good (the owner: "make them good - so they can be useful")

- Real shape, small size. Each app has its toolchain's standard layout, a
  real dependency manifest with a lock, lint and format configuration, a
  test suite green on the clean tree, one "is it green" command, and a
  README; enough structure for a planted fault to have a believable
  neighbour: a CLI entry, a service, a data model, one I/O boundary.
  - `python-tooling`: the dev dialect, the lane's own Python in
    miniature: stdlib only, no packaging, levers that speak the refusal
    wire, unittest, ruff. First, because it needs nothing installed and
    the lane proves this dialect every day.
  - `python-service`: the production dialect: a packaged application
    with a pyproject, pinned dependencies and a lock, a service or CLI
    product with an I/O boundary, its own runner. Its faults are a
    target's faults: an injection at the boundary, an unpinned
    dependency, a secret in a log.
  - `symfony-app`: a Symfony skeleton at the product's pins (8.1.*, PHP
    >= 8.4) with one console command, one service, one controller,
    PHPUnit, and the standards draft's `composer check` and `composer
    fix` (the seat session's Part A).
  - `rust-crate`: a crate with a lib and a bin, cargo test, clippy, fmt,
    a lock.
- One fault taxonomy, three idioms. The kinds come from the findings
  ledger: an untrusted string reaching a shell or argv; a path escaping
  its root; a loose comparison (false as zero); a secret in the
  environment or a log; an error swallowed; a boundary off by one
  (half-open intervals); a test proving against a stub; an oracle taken
  from the code under test; an unpinned or drifted dependency. Each app
  plants the same kinds in its own idiom, so a reviewer's rates compare
  across languages. Six to eight per app to start; some carry a failing
  test, some are visible only to an audit. `ops/devlane/fixtures/apps/FAULT-KINDS.md`
  is the shared list; each manifest cites a kind by id.
- Prove red mechanically: every fault has a probe, red while planted,
  green after the planted fix; the manifest is data and a new fault is
  a new row.
- Hermetic and pinned: no network at make time (locked or vendored
  dependencies, cached on the runner host), versions pinned, probes free
  of time and locale, the term and vocabulary walls clean, each app a few
  hundred lines besides its dependencies.
- Useful four ways beyond calibration: the app is the toolchain
  profile's specification by example (what installing Agentscient into a
  target of that kind expects to find); the two-minute proof a new
  session runs to know the lane works (`fixture.sh make python-app` then
  the suites); the exemplar the implement prompt points workers at for
  the profile's conventions; and the toolchain smoke test for the
  runners, one cheap matrix job per profile when CI splits.
- Not the lane's tests: the lane's suites test `fixture.sh` and the
  grading, never run an app's own suite except through `prove`.

## Boundaries the owner set

- Apparatus under the lane's fixture home, loadable by the lane; not a
  separate repository (owner: "place the repo fixture in this repo (for
  ease)").
- No PHP or Symfony work in the product until the owner is comfortable
  with the machinery; the fixture is the proving ground.
- The lane is bounded: one lever, data files, a skeleton; no new kernel
  responsibility.
- The product's CI steps at the root never run on a fixture app.

## Acceptance, measurable

- `fixture.sh make python-tooling` (and each of the other three) produces a scratch repository where
  `bash ops/bin/suites.sh` is green and a `dispatch.sh --dry-run` resolves
  the branch's launcher, models and efforts from the lane conf.
- `fixture.sh prove` on the fresh scratch repository: every probe red;
  after applying the planted fixes: every probe green.
- One security audit and one adversarial audit run through the ladder
  driver over the fresh fixture; `fixture.sh grade` prints each
  reviewer's caught, missed and false-positive counts against the
  manifest, and the findings ledger holds the rows.
- The product's `composer validate`, lint, `phpunit` and mate steps are
  unchanged and do not read the fixture.
- Every lane suite green; `ruff check .` clean; term wall clean.
