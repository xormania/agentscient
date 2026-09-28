# I-003 — this is a Symfony project, not a constitutional repository; MinSpec deferred

- recorded: 2026-09-03, on the question of skipping the substrate
- source: owner, verbatim below
- disposition: ratified — `AGENTS.md` §Standing rulings, third bullet; register row D-REPO-1, superseded by D-REPO-2 — the reading "MinSpec deferred" below was the conductor's softening and is corrected by I-006: MinSpec is not used

## In the owner's words

> i think we'll skip MinSpec for now - we can we organize what we write here into a package/flex recipe later. Thoughts?

> i don't know where the constitutional came from - probably bad assumptions from the other model. This is a Symfony project

## What was heard

The genesis framing of this repository as law-only was an assumption,
withdrawn. Code lives here: packages gestate under `packages/<name>/`,
package-shaped from the first commit, reaching siblings only through
Composer, and graduate to their own repositories with Flex recipes when
their boundaries are proven. MinSpec is deferred with its pins kept, not
dropped. The estates ruling's open question — gestate here or found
separate — is answered: here.

## Standing facts it must reconcile with

- The substrate's own constitution lists "creates packages before boundaries are proven" among things to avoid and defines a deferred repository as one held back until its boundary is proven (`minspec/.github` GOVERNANCE and TERMINOLOGY at dev `64cc8e7`, read 2026-09-02).
- The shell materialized from `symfony/skeleton` at the substrate's pins verifies: validate strict exit 0, kernel v8.1.6, PHPUnit exit 0 on the empty package set — measured 2026-09-03.
