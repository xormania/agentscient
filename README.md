# deprecated-work — the standing branch for retired material

Owner, 2026-09-11: "maybe a branch off of deprecated-work branch - to
isolate"; "feels like something we'll use from time to time".

This branch is an orphan: it shares no history and no tree with `dev` or
`master`, so nothing on it or its children can be merged into the trunk
by accident, and a child branch shows only the retired files. It is never
merged anywhere; it exists for the data.

## How it is used

- Each retirement is one branch cut from this one, named
  `deprecated/<what>-<date>`, holding only the retired files at their
  original paths and one commit whose message says where the files came
  from, why they are retired, and where their ideas went.
- `Source:` names the origin (`owner <date>`, or `repo@sha` for content
  taken from a tracked ref). `Co-Authored-By:` names the committer.
- A retired file's ideas are extracted into a scope or a record before it
  lands here; the commit message names that record so the branch is a
  pointer back into the lane, not a second home for the idea.
- Branches are never deleted (AGENTS.md); a retirement is never undone by
  deletion, only by a new commit on the trunk that re-adopts the content
  with a `Source:` trailer naming this branch and commit.

## Children

- `deprecated/session-watch-20260904`: the owner's session watch script
  and calibration bucket note, untracked in the main checkout from
  2026-09-04 to 2026-09-11.
