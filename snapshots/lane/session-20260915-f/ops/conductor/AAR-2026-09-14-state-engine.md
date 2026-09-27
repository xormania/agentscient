# AAR — 2026-09-14, the state engine and the handoff manager

Session record by Claude Fable 5.1 on `lane/session-20260913-m`, cut
from dev `8acab9aa`. Measured at write time: PR #203 merged into dev at
`50a3c19c` (2026-09-14T01:48:53Z); no open grant (220 settled against
`f95e885b`, verified); the lock names this branch and `-n` (session -n
lifts its own); worktree `../wt/ag-session-20260913-m` at `420affd9`,
0 uncommitted, 0 unpushed; `handoff.py held --branch
lane/session-20260913-m` reads `none held`, exit 0. The handoff is not
a file: it is H-2 in the state engine's store (`handoff.py show H-2`),
threads T-7 (closed at `50a3c19c`), T-8, T-9, T-10, read at onboard
under `== handoffs`. This is the last AAR written as a file for its own
PR; from here an AAR rides the work PR or dissolves into the pitfalls
and defects ledgers (close skill, step 6b, `f95e885b`).

## Request and outcome

The owner asked, in order: "work on handoff and aar process - i think a
new branch/PR per session handoff is excessive - thoughts?"; "we need a
way to handoff and onboard consistently between sessions in a
multi-agent env ... maybe handoff states - so if a session onboards a
handoff - it marks it as taken?"; "why can't we have an SQlite backed
session handoff manager?"; "I don't like using files - i like something
more deterministic and that manages states - and it can be improved
over time - maybe allow for selection of session handoffs?"; "i'm not
happy that we aren't SQLite more - this got lost somewhere - but i
don't files as state"; "hand grant ok'd - build the engine and the
handoff manager - and consider hooks that guard against this, with
skills returned on failure to guide?"; "i need to prevent future
default to files when SQLite is better option"; "AAR and handoff".

| PR | merge | what |
|---|---|---|
| #203 | `50a3c19c` | machine.py, handoff.py, the `== handoffs` section, the state declaration in 25 placement files with test_state_placement.py, conventions §State, machine-lever.md, handoff-lever.md, the state skill, the close and onboard steps, the README sentence, seven corpus rows, pitfalls 36 and 37 |

No dispatch ran; one producer by hand under grant 220, the second
producer absent by the owner's word (`e780db97`).

## What was decided and why

- **Rows, not files, for anything another session must see now**: a
  file on a branch is invisible until it merges, a file in the state
  directory is a lost update waiting (the lock needed one on #198).
  Measured at `8acab9aa` before the change: nine tools on SQLite,
  twelve on JSON or text. The rule is conventions §State; the gate
  pins the four file-backed tools (control, deliverable, ladder,
  ledger) so a new one cannot default to files.
- **One engine, machines as data** (docs/workflow.md): the handoff is
  the first instance; the lock and the grants are thread T-6 for a
  later session.
- **Onboard shows, `take` claims**: onboard is a read by contract, and
  a session onboarding to look must not claim; a take names the
  branch and refuses unless the lock names it (`handoff-lever.md`).
- **The declared failure class fires only at the transition's target**
  (a second take reads `taken`, a take of a closed thread reads
  `place`), found by test_handoff.py's 33rd case and written into
  machine-lever.md at `e780db97`.
- **Hooks against files as state**: the gate is the CI wall; the
  in-session hook row is thread T-5 for a wall session, since the hook
  paths are written only under a wall grant in isolation. The miss
  mechanism already logs a skill per refusal; the state skill maps
  each gate line to its remedy.

## What went wrong

- **The claim-unmeasured row scans a heredoc to a code path**: three
  writes of one file refused in a row on `HOLDS`, "works" and the
  transition name. Pitfall 36: stage in the scratchpad, scan with
  matrix.unmeasured_claim, then copy (`f95e885b`).
- **A setUp that raised skipped tearDown** and left XDG_STATE_HOME and
  LANE_CONF on the process: the first whole conductor run read
  failures=7 errors=27 in skills, watchdog and the tracked corpus; the
  rerun with addCleanup read Ran 1177 tests, OK. Pitfall 37.
- **Two sessions minted pitfall 35**: ledger.py mints from origin/dev;
  session -n held 35 unpushed. Renumbered by hand to 36 and 37 after a
  message exchange (`f95e885b`); thread T-10 names the window.
- **The main checkout's hooks ran at 3014cb22** while dev was at
  cccc810b, until the owner fast-forwarded it by hand (session -n's
  LD-38); the trunk-commit row refused the fast-forward to agents.
- **A push after ready was rejected**: the owner had updated the
  branch from GitHub (`420affd9`); the local merge `acc18b17` had the
  same tree (`7b5b64d4`), so the local branch was aligned to the
  remote and the readings re-posted against `420affd9`.
- **`done` on my own open thread refused `place`**: a thread is closed
  from taken, not from open, so the closing session takes T-7 first;
  read at the close (`50a3c19c`).

## Calibration

- `worth.py waste --since 2026-09-14T00:20:00Z` at write time: this
  session 17.3M cached tokens, 191,349 out, mean context about 235k
  over 53 turns, 0 refusals counted by the meter (the hook refusals of
  this session are in pitfalls 36 and 37, not the meter).
- Corpus: 189 pass, 0 fail, 0 unreachable at `acc18b17`, the tree of
  `420affd9`; exit read from the process.
- Suites: exit 0 at that tree; conductor Ran 1180 tests, OK.
