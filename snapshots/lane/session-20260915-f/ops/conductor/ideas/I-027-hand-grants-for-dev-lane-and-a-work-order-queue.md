# I-027 — hand grants are the way for dev-lane changes; a work-order queue, later, not in the dev lane

- recorded: 2026-09-12, in session, after the rulebook carve-out landed (PR #152)
- source: owner, verbatim below
- disposition: the first half ratified by the owner's word and written into the lane's rules the same hour (PR #153); the second half open

## In the owner's words
> i move too fast - and i'm not applogizing - and i have ideas - like a work-order queue - but not now and in dev-lane. Right now the goal is to get this dev-lane functioning without a bunch of bullshit bugs - so i can get the testing improved and then i have the plans and concepts for the prod-lane: they're almost hammered out, and i need this system to be able to perform so i can start to make real progress. I'm acutely aware of the classes of issues i'm experiencing - but i can't spend another week fixing the dev-lane - i need good enough while being able to fix issues as I go along - the hand grant is something that I think works for dev-lane changes. And the data that i need isn't more dev-lane data, its prod-lane dev data; we have enough data to know all the big issues re: dev-lane, so i'm trying to consolidate it and get this system functioning.

> from my experience and POV - it feels like either things I've assumed were done, have not been, or have been done half-ass. I move fast - and I have no tolerance for things that get in my way

> when i make a statement like that - i expect it to implimented - i assume that, which is probbaly why we've wasted so much time re-writing things that already exist and lose work. It has to stop

## What was heard

The conductor's reading. Dev-lane changes are done by hand under a grant at the owner's word: one producer, red then green measured, said in the record; the ladder and its second producer are for prod-lane work, where the data the owner needs comes from. A bug met on the way is fixed in the moment and recorded, not queued. A ruling is implemented in the turn it is made; "done" means measured on dev with the commit named; nothing is written as owed unless the owner deferred it. The work-order queue is the owner's idea for later and not for the dev lane.

## Standing facts it must reconcile with

Measured 2026-09-12 against dev `58f3e1b`: `AGENTS.md` §Ground rules says no producer owns two consecutive artifacts and binds every producer; the `dev-lane` skill page says the same in capitals; the defect ledger's header already allows direct hand repair of lane defects. The carve-out for dev-lane changes at the owner's word is the amendment of PR #153.
