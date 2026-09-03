# I-004 — copy first: the dev lane whole, a clean slate, then write Agentscient with it

- recorded: 2026-09-03, after the full-scope inventory of the House lane
- source: owner, verbatim below
- disposition: ratified — register row D-PORT-1; the extraction order in `docs/mapping.md` §What this settles and the conductor's freights

## In the owner's words

> and i realize a potential larger issue - you may not realize what the full scope of extracting […]'s dev-lane systems

> copy first- i want what has been created (its kinda working nice), with a clean slate for Agentscient development. Then we use it to write agentscient. This about getting all value out of the dev-lane and having a framework to impliment it (Symfony) - we can move fast once we have it defined. And this is about moving fast - this is private repo, can't get bogged down on permissions

## What was heard

Bring the whole lane over, de-instanced, so the conductor's circuit
works here end to end within days; then strangle each part by the
mapping with the copied Python as the oracle. What never crosses is the
House's memory: its ideas, handoffs, after-action reports, session
records. The order the circuit needs: the conductor lane, the workflow
engine with its contracts and tests, the framework seed, the docs shelf
and infra tests, the root law. Merges into `dev` are the session's; the
release into `master` is the owner's. Permission friction is a defect
to remove, not a ceremony to keep.

## Standing facts it must reconcile with

- The House lane at dev `99334f7`: 1,741 files, 301,887 lines, 147 test files, 489 files naming the House — measured 2026-09-03T02:41Z; 222 files and 47,573 lines had crossed before this idea.
- The session cannot loosen its own permissions: the classifier refused both permission files from the session on 2026-09-03; the owner's hand applied them.
