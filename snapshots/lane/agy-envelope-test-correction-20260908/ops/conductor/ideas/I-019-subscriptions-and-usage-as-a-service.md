# Subscriptions and usage as a service

Owner, 2026-09-04, in session, after reading the organisation's GitHub
billing page to settle whether a merge queue was available (GitHub
Team, two seats, a metered line for Actions the self-hosted runners
keep at zero), and after saying why the runners are self-hosted: "our
ci costs nothing becasue i ran my credits out - and learned". Then:
"re: github billing - i was thinking that there are many subscriptions
and usage to track - sounds like a service for Agenscient Symfony App
- thoughts?"

What the lane measures today, as the instance. The meter (`worth.py`)
reads dispatch records and reports tokens and ticks per harness and
per run; the Grok tick scale was settled against list prices the same
day; the bucket calibration table carries minutes per stage. None of
it knows what is paid for: the GitHub seats, the model subscriptions
and their included allowances, the metered products, the harness
CLIs' own plans. The one lesson on the billing page (credits run out,
runners moved home) lives in the owner's memory.

The idea: a service in the Symfony app that holds every subscription
and every meter the project runs on, and turns them into thresholds.
Three tables and a cadence. Subscriptions: what is paid, to whom, per
period, seats, what is included (the GitHub Team plan and its Actions
minutes; each model vendor's plan; anything else with a renewal
date). Meters: usage per product per period, read from the vendors'
billing surfaces where one exists (the forge's organisation billing
API; the model vendors' usage and cost endpoints) and from the lane's
own records where the vendor has none (the meter's ticks, the harness
usage reports such as the Grok report the session monitors). Budgets:
a threshold per meter and per period, and the lever that makes it
bite: a dispatch that would spend past a threshold is refused before
it starts, on the wire, the way the wall refuses a run past its
minutes; a CI run on a hosted runner is refused past the included
minutes rather than billed. Reports on cadence and on events (I-015):
what was spent, against what, what renews when, what the next batch
will cost at the measured rates, with the numbers beside the words.

How it sits. Every vendor billing surface is an edge (contract,
probe, mock; docs/verified-couplings.md), so no vendor's API becomes
load-bearing and a vendor without one is a declared gap fed from the
lane's records. The couplings contract already prices a coupling by
its verification cost; this service prices it in money, so "what does
this edge cost" has a measured answer. Symfony: Scheduler for the
cadence pulls, HttpClient behind each bridge, Doctrine for the three
tables (never pruned; every reading a row), Messenger for the pulls in
the background, and the four projections (Console, TUI, MCP resource
read-only, API). It is a sibling of the CI-tracking service (I-014):
that one watches time and rates, this one watches money and
allowances, and both feed the watcher (I-017) and the calibration
table, where a bucket gains a cost column beside its minutes.

Not ruled, not scoped; recorded with the instance beside it. The
reading is the conductor's.
