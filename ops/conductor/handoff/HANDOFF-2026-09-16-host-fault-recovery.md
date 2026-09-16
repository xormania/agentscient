# HANDOFF 2026-09-16 — the host fault, the Lead found, the board as it stood

Written by the recovery session (Claude Fable 5.1, harness session
68f8b671-73af-4ef0-9548-23aca04bf33c, branch `lane/session-20260916-recover`,
grant 285) on 2026-09-16 between 16:16Z and 16:5xZ, from readings taken
then. The owner's words that opened it: "you were the lead agent and the
wsl2 terminal faulted - not a normal onboard - you need to find the
session"; "its a lesson - let's learn"; "you worry about the sessions -
i'll worry the wsl2 cause"; "its may be the cause" (of the Google Drive
mount); "i'll know more soon"; "just don't mount it again for now";
then at 16:5xZ "its not proven - but (i think docker personally) - full
report coming to `~/wsl2-failure.md` - have XO look at it when it
arrives and tell you what its sees". The XO was dead, so the recovery
session read the report when it arrived at 17:01:00Z (7060 bytes, 109
lines) and its reading is below; then at 17:05Z "you are lead".

This session was off the board until 17:05Z. On the owner's word it
bound as PT-9 (worker, through the lever) and wrote `lead` onto its own
row by hand under grant 288 at 17:05:59Z, the lever's `grant` being
unusable with no live lead (LD-91); the row's `probe` column carries
the owner's word. It took T-88. The harness classifier refused the
revokes that would have cleared the dead holders' roles, so the store
shows two leads, PT-2 dead and PT-9, and PT-3 and PT-7 still holding
dispatcher and coordinator with no process behind them. PT-10
(agentscient-c1, Sonnet) was granted dispatcher by PT-9 at 17:07:51Z and PT-11 (agentscient-43,
Opus) coordinator at 17:13:59Z, both times the store's `granted_at`.

## The fault

| time (UTC) | event | read from |
|---|---|---|
| 15:15:22 | `sudo mount -t drvfs G: /mnt/g` succeeded; type 9p, `aname=drvfs`, rw; `/mnt/g/My Drive` present | the Lead's transcript |
| 15:19:13 | the XO wrote `archive/agentscient-20260916.bundle` (12,077,986 bytes, sha256 9691f35b…) and `index.md` to `/mnt/g/My Drive/projects/agentscient/` over that mount and re-read them for the checksum | the XO's transcript |
| 15:21:37 | security audit of #255 ended (record 20260916T151803Z-review-codex-cba3cf) | its `out/last-message.json` |
| 15:24:20 | the Lead's last turn | transcript d5c18547, last timestamp |
| 15:24:33 | the XO's last turn | transcript 7ae721d7, last timestamp |
| 15:25:28 | security audit of #254 ended (record 20260916T151749Z-review-codex-ef6db7) | its `out/last-message.json` |
| 15:28:03 | the last write anyone made: that record's `exit` file | its mtime |
| 15:31 | the last write to the Lead's transcript file | its mtime |
| 15:18:33 | kernel warning in `v9fs_vfs_mkdir_dotl`, `fs/inode.c:474 inc_nlink`, kernel tainted `G W`; the moment the XO made the archive directory on the 9p mount | the owner's report |
| 15:43:59 | `wsl-pro-service` deactivated; runner listeners idle; syslog quiet | the owner's report |
| 16:04:09 | the last indexing cycle of the phpactor language server under `~/.cache/phpactor/index/` | the owner's report |
| 16:04:59.237 | kernel panic, `terminate_walk+0x6b` during `fstatat` of a path component `"index"`, `CR2: ffffa5d6a66b74d5`; the VM halted | the owner's report, from the dump under `%TEMP%\wsl-crashes\` |
| 16:07 to 16:10 | WSL restarted; ext4 journals on `/dev/sde` and `/dev/sdf` recovered; `system.journal` corrupted by the panic and rotated | the owner's report |
| about 16:14:44 | this instance's first claude process, pid 1644 | `ps -o etime` at 16:16:43Z |
| 16:16:43 | `/tmp/claude-1006/…/` holds one session directory, this one; `/run/user/1006/cc-socks/` one socket, 1644; `mount` shows no `/mnt/g` | this session |

The cause is the owner's to investigate and is not proven. The first
version of this record put the fault between 15:28Z and 15:31Z from
the last file writes; the owner's report (`~/wsl2-failure.md`, not
committed: it carries host paths and a user name) puts the kernel
panic at 16:04:59Z. The half hour before it was quiet because every
session was waiting on another, see the board below, not because the
host was dying. What the report says, quoted where it matters:

- The root failure: "a Linux Kernel Panic caused by a fatal page fault
  in the kernel VFS function `terminate_walk` during an `fstatat`
  syscall on an `"index"` path component". The Windows host stayed
  up; no BSOD, no sleep, no OOM.
- Hypothesis A, delayed VFS corruption from the 9p drvfs mount of the
  Google Drive: the `inc_nlink` warning at 15:18:33Z is the XO's
  `mkdir` of `projects/agentscient/archive/` on the mount at 15:19Z by
  the XO's transcript, so the two readings agree to within a minute; the warning's time is
  single-sourced, the report's, because the journal of the failed boot
  ends earlier (below).
- Hypothesis B, an RCU path-walk race in kernel 6.18 under concurrent
  index traffic (phpactor's index, `.git/index`), independent of the
  Drive.
- Docker: the report shows Docker Desktop only observing the reset
  (`WSAECONNRESET`, `Wsl/Service/0x80072746`) at 16:04:59.400Z, and
  its heartbeats proving the host awake; it names Docker as neither
  hypothesis. The owner's own suspicion was Docker ("i think docker
  personally"); the report does not support it as written.
- Its recommendations: no direct drvfs mount of a cloud-synced
  virtual drive, `rclone mount` over FUSE instead, or a drvfs mount
  with explicit metadata options; and, because the WSL2 kernel boots
  with `panic=-1`, work committed to disk and version control often.
  The last one is what LD-92 and LD-93 ask for from the lane's side.

The XO's independent reading (agentscient-43, taken between 17:01:59Z and
17:19:50Z, its two `date -u` stamps; the minute-level times it first
gave were estimates and are withdrawn,
with uname, mount, journalctl, the dump itself, find on mtimes and
stat, before it read the paragraph above): the dump at
`%TEMP%\wsl-crashes\kernel-panic-1789574699-{c8c5d175-…}.txt` (4113
bytes) carries the call trace and CR2 exactly as the report quotes them
but is truncated at the top, no Oops header, no `Comm:`, no taint line,
so it does not name the process that made the call. The one
corroborated pre-panic fact on this host is the mount: `journalctl -b
-1` ends at 15:15:00Z with the `mount -t drvfs G: /mnt/g` line, and
the 15:18:33Z, 15:43:59Z and 16:04:09Z rows above are the report's
alone. Under `~/.cache/phpactor/` no file has an mtime between 15:00Z
and 16:05Z, so hypothesis B's stated premise is unsupported by mtimes,
though a read-only walk writes nothing. No v9fs or 9p frame is in the
trace and nothing shows the walked path was on the mount, so A has no
9p evidence either; CR2 is canonical, not a poison pattern, and lies in
neither the direct map nor the stack region, which is the shape of an
overwritten pointer rather than a plain refcount race. "index"
discriminates nothing (`~/.cache/phpactor/index` is a directory of that
name; `.git/index` is a file last written 14:33:56Z). The report's libc
offset arithmetic does not close (the base it implies is not
page-aligned). Verdict: nothing reachable from this host discriminates
A from B, and the hold on the mount is the right call either way.

Standing instruction, owner 2026-09-16: "just don't mount it again
for now". No session mounts G: or writes under
`/mnt/g` until the owner says otherwise. The Drive copy of the bundle
exists and is unreachable from WSL until then; the staging copy is at
`~/.local/state/agentscient/archive/agentscient-20260916.bundle`, same
checksum by the XO's reading at 15:19Z (not re-taken here).

## The Lead

| | |
|---|---|
| participant | PT-2, roles `worker,lead`, the store's bootstrap |
| model | Claude Fable 5.1 |
| harness session id | `d5c18547-5179-4800-a532-a000c3b56db8` |
| peer name | agentscient-11 |
| branch | `lane/session-20260916-a`, worktree `wt/ag-session-20260916-a` at c4ae0b4c, clean, one commit ahead of origin (the dispatch record commit for 20260916T085626Z-review-claude-30f3eb) |
| lock target | `done lane/session-20260916-a: guidance=on-dev`, met, re-taken by the Lead at 15:14Z |
| transcript | `~/.claude/projects/<project-slug>/d5c18547-5179-4800-a532-a000c3b56db8.jsonl`, 6501 lines, 12,249,215 bytes, last turn 15:24:20Z |

The one command that restores it, from a plain WSL terminal in the
project directory:

    claude --resume d5c18547-5179-4800-a532-a000c3b56db8

A resumed session carries the same harness session id, so the store
reads it as PT-2 again. A fresh session cannot take the seat (LD-91).
Whether the resume itself succeeds is not measured as of this record.

## Every session at the fault

All dead. Names are the peer names the sessions used in messages;
session ids are from `coordination.py participants` where bound.

| name | participant | session id | role | branch, PR | last known state |
|---|---|---|---|---|---|
| agentscient-11 | PT-2 | d5c18547… | lead | lane/session-20260916-a | waiting on the two audit records; then #254's ready note, flip and merge; then the relaunch |
| agentscient-09 | PT-7 | 7ae721d7… | coordinator (XO), T-89 and T-95 taken | lane/session-20260916-09 at 806be732, pushed, seven record commits ahead of dev, no PR | scopes written; audits queued through c8; delete row as two dispatches approved |
| agentscient-c8 | PT-3 | 6748e545… | dispatcher | not measured | "Idle, holding." at 15:18:27Z; the relaunch scope written at 14:43Z (712 bytes), launched nothing after the two audits |
| agentscient-e0 | not bound | not measured | builder, wall grant 283 | lane/session-20260916-ci, #255 | closed on #255 at 9af8a71b; declined the delete row as a non-wall session; H-18 threads T-102 to T-104 |
| db (the builder; its peer name is spelled with a term the tree wall forbids) | not bound | not measured | builder | lane/session-20260916-launcher, #254 | Proof heading and rows in the body; owned the audit dispositions |
| agentscient-72 | not bound | not measured | Sonnet, the Drive read then the delete row | none | silent all afternoon by the XO's reading |
| agentscient-47 | not bound | not measured | the Phase 1 census seat | none | silent all afternoon by the XO's reading |
| agentscient-61 | not bound | not measured | idle, awaiting the relaunch | none | not measured |
| dispatched codex worker | PT-8, bound by PT-3 for A-87 | 30fc4e97… | worker | lane/session-20260916-a87 | exited 0 at 14:3xZ, commit a566d980 in its snapshot; the branch 643f0e18 is unpushed with `ops/conductor/handoff/scopes/scope-a87.txt` untracked |
| verifier | PT-6 | 5015193c… | verifier, T-97 | — | holding the A-87 verification |
| earlier seats | PT-1, PT-4 (agentscient-0d, the first XO), PT-5 | ab281ec6…, a6b096a2…, 6f2c1f5f… | worker | — | ended before the fault |

The transcripts of e0, db, 72, 47 and 61 were not read; their session
ids are not in the store and were not looked for.

## The board at 15:24Z, re-measured at 16:2xZ

**Pull requests.** Both draft, both green, both with a `## Proof`
heading, measured with `gh pr checks` at 16:2xZ:

| PR | branch | head | audit record | verdict | waits on |
|---|---|---|---|---|---|
| #254 Package C slice two: the codex launch registers the acting coordination server | lane/session-20260916-launcher | 6213c35a | 20260916T151749Z-review-codex-ef6db7 | changes: p1 ×2, p2 ×1, p3 0 | the three findings disposed with a citation; a fix commit if the second p1 holds; the ready note; the Lead's flip and merge |
| #255 ci: the conductor family runs as four measured shards | lane/session-20260916-ci | 9af8a71b | 20260916T151803Z-review-codex-cba3cf | approve, no findings | the ready note with the record id; the Lead's flip and merge |

The #254 findings, from the record's `out/last-message.json`, for the
Lead to rule on (this session did not verify them against the tree):

1. p1, launch.py:716 and coordination_mcp.py:361: the privileged MCP
   process loads coordination.py late from the worker's own snapshot,
   which the worker can alter before its first call.
2. p1, coordination_mcp.py:460: `resolve_binding` refuses every
   configured call after validating the participant, so `coord_brief`,
   `coord_claim` and `coord_submit` never reach the core. If this holds,
   the A-87 relaunch would fail at its first tool call, and this is the
   thing the relaunch exists to read.
3. p2, launch.py:777: relocation copies coordination-mcp.json and
   rebases the recorded path and server argv but not the embedded
   worktree.

Local commits not at origin, one per branch, each a dispatch record
commit made by the dispatcher into the requester's worktree: `a`
(c4ae0b4c), `ci` (ce30599b, the #255 audit record), `launcher`
(ec736ffa, the #254 audit record), `s2` (f253bc6d), `s3` (ba2682db);
the `a87` branch entirely (643f0e18). Pushing `ci` or `launcher` moves
a PR head and voids its proof (LD-90), so that is the Lead's call, not
this session's; none were pushed. Dirty worktrees: `i` (three test
files modified), `j` (six coordination files modified, one untracked
test), both on landed or open branches whose sessions ended earlier.

**The Lead's queue, in its order**, from its turns between 14:20Z and
15:24Z:

1. Dispose the #254 audit findings; ready notes for #254 and #255 with
   the record ids; flip and merge, #254 first.
2. Relaunch A-87 through the Dispatcher with `scope-a87-relaunch.txt`
   (coordination only, the three MCP tools by name), the reading being
   whether a codex worker claims through the acting server.
3. The Phase 1 census seat as one dispatch, `scope-branchcensus.txt`,
   after 47 and 72 stayed silent.
4. The delete-refusal row as two dispatches: codex `author-tests` on
   `scope-delete-tests.txt`, then grok `implement` on
   `scope-delete-impl.txt`; each in its own worktree; wall paths, so a
   wall grant (283 was e0's and is still open).
5. Then the Lead itself writes the AGENTS.md retirement rule (a branch
   is retired only after a self-contained bundle is restored and its
   tips proved and its name is in a retirement index; the owner alone
   deletes, in batches against the index) and proposes register row
   D-BRANCH-1 for the owner to ratify.
6. Held for the owner: Phases 2 and 3 of the branch report, which end
   in deleting remote refs; the runner capacity behind the 899 s queue
   wait; whether the archive lives in My Drive or a Shared drive.

The four scopes are committed at
`ops/conductor/handoff/scopes/2026-09-16-recovered/` with their
provenance; they were otherwise lost with `/tmp`.

**The store.** A-87 offered to PT-8, generation 2, revision fecdd37c,
coverage "verification gap"; M-86 outstanding (PT-5 to PT-1, section 6
bound, acknowledged 11:41Z); no open decisions. Threads: T-88 (lead)
open; T-89 and T-95 taken by PT-7; T-90 (dispatcher) open; T-96, T-97,
T-98, T-99, T-100 open. Open grants at 16:2xZ: 254 to 257 and 269, 270
late; 259 to 263, 267, 271, 277 to 281, 283, 284 within ttl; 285 this
session's.

**The cross-session messages.** The last message the Lead received was
the XO's at 15:24:16Z (both delete-row scopes written); the XO's
transcript shows no send after 15:24:15Z and c8's none after 15:18Z.
Looked and found no message in flight between those three; the other
sessions' transcripts were not read.

**A stall before the panic, worth the Lead's eye.** The audits ended
at 15:21:37Z and 15:25:28Z. The Dispatcher's last turn was 15:18:27Z,
"Idle, holding."; the Lead and the XO were both waiting on "c8's
audit records" from 15:24Z on. Nothing read the two finished records
until this session did at 16:2xZ. So the chain stood still for the
forty minutes before the panic with its two blockers already answered
on disk: a detached dispatch ends and nobody is told unless a watch
is armed (the watch skill and the watchdog exist for this and were
not running on those records). Not a new row here; the Lead decides
whether it is one.

## What only the owner can say

- Decided at 17:05Z, owner: "you are lead". The recovery session is
  the Lead, PT-9, by the one-time hand write LD-91 records; the resume
  of d5c18547 is no longer the path.
- The WSL2 cause, between the report's two hypotheses. The lane's
  reading favours A only in that the mount's `mkdir` warning is the
  XO's archive write to the minute; that is a coincidence in time, not
  a proof.
- When, if ever, G: may be mounted again.

## What this session did and did not do

Did: read the store, the lock, the dispatch records, the open PRs, the
worktrees and three transcripts; named `lane/session-20260916-recover`
in the lock with a measure; declared grant 285 on the owner's words;
wrote this record, the four scopes, LD-91 to LD-93, the probe rows in
`probes/probes-2026-09-16-host-fault-recovery.jsonl`, and the
command-structure section "Finding the Lead after a host fault".

Then, from 17:05Z: bound as PT-9, wrote lead onto its row under grant
288, took T-88, granted dispatcher to PT-10.

Did not: push any other session's branch; mount or
touch `/mnt/g`; dispatch; verify the #254 findings; read the transcripts
of e0, db, 72, 47 or 61; write the day's AAR, which is the Lead's.
