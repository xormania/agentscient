# Investigation brief — subscriptions and usage, vendor by vendor

Written 2026-09-04 by the session (Fable 5.1) at the owner's request:
"write it up for further investigation - i have to research how to get
subscriptions for every appropriate vendor". A research guide for the
service recorded as idea I-019 (merged, PR #42): what the project pays
or meters today, what each vendor exposes, what to verify, and the
shape of the answer to bring back. Nothing here is scoped or built.
Vendor facts are stated as the session knows them and every one is
marked to be verified at the pin: billing surfaces change more often
than APIs.

## What the owner said

- "our ci costs nothing becasue i ran my credits out - and learned"
- "re: github billing - i was thinking that there are many
  subscriptions and usage to track - sounds like a service for
  Agenscient Symfony App - thoughts?"
- "write it up for further investigation - i have to research how to
  get subscriptions for every appropriate vendor"

## The vendors the project runs on, measured 2026-09-04

| vendor | what the lane uses | measured |
|:--|:--|:--|
| GitHub | the forge, rulesets, Actions on self-hosted runners | organisation on GitHub Team, 2 seats, $96/year; Actions metered line $0.38 this month for this repository; 64 of 3,000 included minutes used; runners self-hosted |
| xAI | the `grok` CLI as a harness (tests, adversarial audit) | `grok 1.0.13`; models named in `ops/lane.conf` (`grok-4.6`, effort xhigh); the CLI reports per-run usage; ticks = USD × 1e9, verified against list prices within 5–9% on 9 of 12 runs (`.dev/wip/note-grok-ticks.md`); a session report at `.xor/tmp/grok-usage.md` |
| OpenAI | the `codex` CLI as a harness (skeptic, implement, security audit) | `codex-cli 0.153.2`; models `gpt-5.6-sol`, `gpt-daybreak-blue-latest`; rollouts under `~/.codex/sessions/` carry per-turn token counts the meter reads |
| Anthropic | Claude Code as the session and as a harness (plan, reads) | `claude 2.1.260`; models `claude-fable-5-1`, `claude-opus-5`; transcripts under `~/.claude/projects/` (98 project directories on the box) carry per-turn usage |
| local | Ollama, when the harness eval seat is built | not installed; free |

Not vendors of this project today: Packagist and Composer (free), the
connectors attached to the session (Hugging Face, Google, Docusign),
and any cloud; AWS is named for later in the owner's overview, and its
Cost Explorer and usage reports join this table when it does.

What the lane captures on its own: every dispatch record carries a
`spend` block per envelope (`harness`, `total`, `out`, `runs`, in the
harness's own units); the meter (`worth.py report --repo .`) sums it
per harness and per run; the bucket calibration table carries minutes
per stage. None of it knows what is paid for or what is included.

## Per vendor: what to find out

For each, the same seven questions. The answers are the seed rows of
the service's subscriptions and meters tables.

1. What exactly is bought: plan name, period, renewal date, seats,
   included allowance, overage price, and whether the harness runs on
   a subscription (a flat plan with rate windows) or on an API key
   (pay per token). The two are metered differently and only the
   second has a cost API.
2. Where usage is visible to a person: the console page, its
   granularity, its latency.
3. Whether usage is exposed to a program: a usage or cost API, an
   export (CSV, a report file), or console only. The endpoint, the
   auth it needs, whether a read-only credential exists.
4. Granularity: per day or hour; per project, key, user or model.
5. Vendor-side budgets or alerts: hard limits, soft alerts, who they
   notify.
6. The mapping from the vendor's unit to money: tokens by model and
   tier, ticks, minutes, seats.
7. What the lane already captures for this vendor, so the service can
   reconcile its own count against the vendor's bill and report the
   gap.

### GitHub

- Bought: GitHub Team for the `uscient` organisation (two seats, per
  year). Actions minutes and storage are metered products with an
  included allowance; the self-hosted runners consume none.
- Program access, to verify at the pin: the organisation billing
  endpoints under the REST API (the enhanced billing platform's usage
  report by product, SKU and repository; the classic Actions, Packages
  and shared-storage summaries), and budgets on the enhanced platform.
  Seats and plan on the organisation object, returned only to an owner
  with the organisation-admin scope; the machine account's token here
  has `read:org` and the plan field came back empty. So: a fine-grained
  token or a GitHub App owned by the organisation with read-only
  billing and administration permissions, held by the service and not
  by the lane's machine account.
- Lane-side: the watchdog and the CI tracking idea (I-014) read runs;
  minutes per run are on each workflow run object.
- To decide: whether hosted runners are ever allowed (a budget of zero
  is a rule the service can enforce), and where the included-minutes
  threshold sits.

### xAI (Grok)

- Bought: to establish. The CLI reports usage in ticks that reconcile
  to list API prices, which reads like a pay-per-token key behind the
  CLI; whether a SuperGrok or team subscription also applies, and
  whether the CLI's plan has rate windows, is the first thing to read
  off the console.
- Program access, to verify: the console's usage and billing pages;
  whether a management or billing API exists for the account (key
  listing, usage by key, spend) and what credential it takes. The
  per-request `usage` object is already in every response the CLI
  logs.
- Lane-side: the strongest source today. The CLI writes a session
  usage report the session monitors, and the tick scale is verified;
  the service can reconcile ticks against the console's bill monthly
  and re-verify the scale (long-context runs already show 1.29–1.49×
  list, which the note records).

### OpenAI (Codex)

- Bought: to establish which of the two modes the `codex` CLI runs in
  here: signed in with a ChatGPT plan (Plus, Pro, Team), in which case
  usage is a rate window with no cost API and the CLI shows the
  windows; or an API key, in which case the organisation's usage and
  cost endpoints apply (bucketed by day, by project, key or model,
  behind an admin key).
- Program access, to verify: the organisation usage and costs
  endpoints and the admin credential they take; for a plan, the
  account page only.
- Lane-side: rollouts carry per-turn token counts; the meter reads
  them; cost per token by model is a table the service holds and
  re-verifies on cadence (the same discipline as the Grok tick note).

### Anthropic (Claude Code)

- Bought: to establish: a Claude plan (Pro or Max, with rate windows)
  or Console API billing (per token, with spend limits and an
  organisation cost report behind an admin key). This session runs on
  one of them.
- Program access, to verify: the organisation usage and cost reports
  for API billing; and, for either mode, Claude Code's own telemetry
  export (metrics for tokens, cost and sessions over OpenTelemetry to
  a collector the owner runs) — if it holds at the pin, it is the
  cleanest feed of all, because it comes from the harness itself
  rather than from a bill.
- Lane-side: transcripts carry per-turn usage including cache reads;
  the meter's Claude rows read them; the compaction summaries are in
  the same files.

### Later: cloud, domains, anything with a renewal

AWS when it arrives (Cost Explorer, the cost and usage report, budgets
with actions); domain and certificate renewals; any SaaS seat. The
service's subscriptions table takes a row with a renewal date even
when there is no meter, so a renewal is a scheduled report, never a
surprise.

## The shape of the answer to bring back

One row per vendor and product, in a form the service seeds from:

    {"vendor": "github", "product": "team-seats", "kind": "subscription", "period": "year", "renews": "YYYY-MM-DD", "seats": 2, "price": 96.00, "currency": "USD", "included": {"actions_minutes": 3000}, "meter": {"source": "api", "endpoint": "...", "auth": "app: billing read", "granularity": "day"}, "lane_source": "workflow runs", "budget": {"actions_minutes": 0}}
    {"vendor": "xai", "product": "grok-cli", "kind": "to-establish", ...}

Plus, per vendor, the credential the service will hold (read-only,
scoped to billing) and where it lives (the per-machine
`ops/lane.local.conf` or the app's secrets vault, never the tracked
conf).

## What the service does with it, for orientation

Subscriptions (what is paid), meters (what is used, from the vendor and
from the lane's records), budgets (thresholds that refuse a dispatch or
a hosted run before it spends), reports on cadence and on events with
the numbers beside the words, every reading a row, never pruned. Each
vendor surface is an edge: a contract naming what is relied on, a
probe on cadence, a mock for tests; a vendor with no surface is a
declared gap fed from the lane's records. Symfony: Scheduler,
HttpClient behind a bridge per vendor, Doctrine, Messenger, the four
projections. Sibling of the CI tracking service (I-014); both feed the
watcher (I-017) and the calibration table, where a bucket gains a cost
column.

## Questions for the owner

- Which mode each harness runs in (plan or key), since it decides
  whether a cost API exists at all.
- Whether a read-only billing credential per vendor may be created
  and held by the app, and where.
- Whether the budget on hosted Actions minutes is zero (the runners
  stay home) or the included allowance.
- Which reconciliation matters first: the Grok ticks against the
  console bill (the scale is already measured), or the Codex and
  Claude token counts against their plans' windows.

## Pointers

`ops/conductor/ideas/I-019-subscriptions-and-usage-as-a-service.md`;
`ops/conductor/ideas/I-014-ci-tracking-with-thresholds.md`;
`.dev/wip/note-grok-ticks.md`; `.xor/tmp/grok-usage.md`;
`ops/devlane/telemetry/worth.py`; `.dev/wip/calibration-buckets.md`;
`docs/verified-couplings.md`.
