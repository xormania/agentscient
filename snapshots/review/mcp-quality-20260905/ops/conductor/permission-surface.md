# The permission surface — contract for /co-doc

The conductor acts through a stack of things that may refuse it: hooks,
permission rules, levers, the launcher, identity. Each layer below declares
its probe (an oracle that executes), its tier, and its remedy shape. The
doctor (`tools/co_doc.py`) is this contract's instrument: it runs every
probe read-only and reports findings with remedies. It is not the fixer.

**Lockout invariants** (owner + conductor, 2026-08-31):

1. Reads are never gated. Any layer able to refuse a read is itself a
   finding, per se.
2. Every refusal names its remedy; layers under this contract also name
   the doctor.
3. The doctor depends on nothing it diagnoses: stdlib Python, filesystem
   reads, and at most a `--help` subprocess. No launcher, no wrapper, no
   database writes. If everything else is wedged, it still runs.
4. The bypass is the owner, formalized: the doctor proposes; application
   of a remedy happens only with the owner present, one decision at a
   time. (The pre-ratified remedies table that would let it fix
   unattended is **ratification-pending** — until the owner ratifies it,
   v1 applies nothing.)

## Probes

| id | layer | asserts | tier |
|---|---|---|---|
| P-SET-1 | settings | every present settings file (`.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json`) parses as a JSON object; an absent file is reported absent, never as clean-by-silence | 2 |
| P-PERM-1 | permissions | every `permissions.allow` rule naming an absolute path resolves to an existing file — an allow whose target does not exist is an **inert grant**, the lockout that looks like permission | 2 |
| P-PERM-2 | permissions | no deny rule textually shadows an allow's target (heuristic, stated as such in output) | 3 |
| P-HOOK-1 | hooks | every configured hook's command file exists and is executable | 2 |
| P-HOOK-2 | hooks | every hook matcher names the tools it judges — a `.*` or absent matcher is a finding (the tool-guard lesson, agent-lab rule) | 2 |
| P-LEV-1 | levers | `dispatch.conf` parses; an explicit `LAUNCHER_PIN` or the sibling-default launcher, `dispatch.sh`, and `gate.sh` are each reported live or inert with the path examined | 2 |
| P-ID-1 | identity | `WF_AGENT`, when set, is `Name <address>`; unset is a note with the export line as remedy (reads need no identity) | 2 |
| P-WF-1 | record | `wf.py` exists and `--help` exits 0 | 2 |
| P-DB-1 | ledgers | `handwork.db` and `skills.db` open; open grants past TTL counted and named | 2 |

## Output contract

One line per finding: `[CLASS] probe-id: what was expected / what was found
— remedy: <one sentence>`. CLASS is the four-class taxonomy: Rejection,
Denial, Abort, Finding. A probe that cannot examine its layer reports
INVALID for that probe — an unperformed scan is never a clean result.
Exit 0: every probe ran, no findings. Exit 1: findings present. Exit 2:
one or more probes INVALID.

`--list-probes` prints every probe id above, one per line — the drift
check between this contract and the instrument.

## Remedies (proposed by the doctor; application ratification-pending)

| finding | proposed remedy |
|---|---|
| inert grant | repoint the rule at the resolving path, or complete the step that makes it resolve (e.g. the main checkout's move to dev); never widen |
| broad/absent hook matcher | scope the matcher to named tools; move general policy into `permissions` |
| missing hook file | remove the entry or restore the file — a hook that cannot run is config lying about enforcement |
| malformed settings | restore from the timestamped backup beside it, or fix the JSON; the doctor names the parse error |
| stale lever pin | repoint at the measured current target; record the measurement |
| stuck grants | settle or expire them with reason; a stuck grant is unfinished evidence |

A remedy that would **widen** any permission is never proposed for
unattended application, under any future ratification.

## Registration duty

Any new gate that can refuse the conductor registers here with a probe id
and a remedy shape before it arms, or it is an unproven gate. This table
and `co_doc.py --list-probes` must agree; their drift is itself a finding.

Source: owner doctrine 2026-08-31 (lockout fear, skill bypass, CDD) +
conductor design, this session. Ratified-by: pending owner for the
remedies-application clause; the diagnostic contract is design (conductor).
