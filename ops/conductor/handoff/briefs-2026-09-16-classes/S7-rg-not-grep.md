# S7 rg-not-grep: the search shapes on ripgrep, Graft still first

Class 8 of the 2026-09-16 issues (permission decided by matching command text outside the lever), the tool side. Owner, 2026-09-16, relayed by agentscient-11 at 10:06Z: "grep sucks - don't use it to bypass Graft - but ffs use it instead of grep". Two halves: the pages and the lever (this brief), and the wall rows (W4, the wall session).

## Measured 2026-09-16 at dev 46639344

- `rg --version` reads ripgrep 14.1.0. `type grep` in a session shell reads `grep is a function` (the harness wraps the name); `rg` is the binary.
- grep spellings per skill page (`grep -c -F grep .claude/skills/*/SKILL.md`): search 16, terms 5, refused 2, measure 1; `ops/devlane/hooks/claude/evgrep.sh` 6.
- `ops/devlane/hooks/claude/matrix.py` line 145 `SEARCHERS = ("grep", "egrep", "fgrep", "rg", "ugrep", "evgrep.sh")` and line 148 `SEARCH_COUNT_FLAGS` (`-c`, `--count`, `-l`, `--files-with-matches`, `-L`, `--files-without-match`): graft-first already judges `rg` by name as it judges `grep`. `ops/devlane/hooks/claude/unsafe-command.py` line 312 `READS_FILES` names `rg`; its clipped-sweep row (line 343) reads the same statement tokens. Whether the hook tests plant an `rg` fault for either row: not measured.
- `WALL_PATHS` (matrix.py line 196) names matrix.py, engine.py, boundaries.json and `ops/devlane/hooks/tests/`; `evgrep.sh` and `unsafe-command.py` are not wall paths.

## The mechanism

Non-wall, this build:
- `.claude/skills/search/SKILL.md` rewritten on ripgrep: the four questions keep one command each, spelled `rg -c PATTERN FILE`, `rg -l PATTERN DIR`, `rg -n PATTERN FILE` then `sed -n`, and `rg -n PATTERN DIR -g '*.md'` (or any data glob) for data; `-F` for a literal; one pattern per call; `--line-buffered` whenever the output feeds a filter; the count-first rule and the Graft query unchanged. The worked shapes from the refusal log re-spelled on `rg`.
- `evrg.sh` beside `evgrep.sh`, the same contract (the full count first, a bounded view, a loud truncation marker) on `rg -c` and `rg -n`; `evgrep.sh` becomes a two-line shim that refuses on the wire, class `retired`, naming `evrg.sh`, so a page or a habit that still calls it fails loudly.
- Every other skill page spelling a grep shape follows: terms, refused (its graft-first and clipped-sweep rows name `rg`), measure. Pages outside `.claude/skills/` that spell grep (ops/README.md, CONTRIB.md, the handoff records) are counted by the builder (`rg -c -F grep <file>`) and listed in the PR body; records are not rewritten.
- Nothing in this half changes what a row refuses: an `rg` that bypasses Graft refuses exactly as its grep spelling did, and the pages say so where they teach the shape.

Wall, W4 (the wall session, after this half lands): rows in `ops/devlane/hooks/tests/` that plant `rg -n TOKEN ops/` over a code root (graft-first refuses), `rg -E 'a|b|c' FILE | head -8` (clipped-sweep refuses), and the neighbours `rg -c PATTERN FILE` and `rg -l PATTERN DIR` (pass); `evrg.sh`'s own test (count header, bounded view, marker), written there by the wall session, the second producer for the script.

## Planted faults and clean neighbours

Fault: a page that spells `grep -rn` or `rg -n` over a code root as an allowed shape (the page teaches the bypass); on the new search page every such spelling sits inside a "refused" example and nowhere else. Fault: a page still naming `evgrep.sh` as the lever. Neighbour: the count and list shapes read `rg -c` and `rg -l`. Corpus rows for the PR, under `ops/conductor/handoff/probes/probes-2026-09-16-s7.jsonl`: serve `rg -o -F 'ripgrep 14.1.0' .claude/skills/search/SKILL.md` expect `ripgrep 14.1.0`; absent `rg -F 'evgrep.sh PATTERN FILE' .claude/skills/search/SKILL.md`; serve `rg -c -F 'rg -c' .claude/skills/search/SKILL.md` with the count the builder measures.

## Rows

None in this half: the pages are apparatus and the corpus rows above are their test; the lever's tests are W4's. The builder pastes `bash -n ops/devlane/hooks/claude/evrg.sh` and one run of `evrg.sh PATTERN FILE` on a file with more matches than the bounded view shows, marker included, in the PR body.

## Not covered

W4's rows; the origin of the `grep` shell function (the harness); pages outside `.claude/skills/` (counted, not rewritten). The measure for the lock: `sh -c "git fetch -q origin; git show origin/dev:.claude/skills/search/SKILL.md | rg -q 'ripgrep 14.1.0' && echo s7=on-dev || echo s7=short"`, until `s7=on-dev`; the lock runs it with its cwd at the repository root.

## Scope (for the reviews, under 1024 bytes)

adversarial-review of S7 rg-not-grep on lane/session-20260916-<x>: the search skill and the terms, refused and measure pages re-spelled on ripgrep 14.1.0; evrg.sh replacing evgrep.sh, the old name a retired shim. Hunt: a shape that bypasses Graft (an rg -n over a code root taught as allowed); a count or list shape that can truncate; a page still naming evgrep.sh as live; a basic-regex habit carried into rg (a \| alternation, -E where rg needs nothing); a claim without its reading; a grep spelling left on a page the PR says it covered. Quote both halves of every finding.

## The rules every build follows

- Records and apparatus by hand under a grant at the owner's relayed word, one producer, the second producer's absence said in the commit; reviews by Grok `adversarial-review` and Codex `security-audit` at the pushed head, dispatched from the branch's worktree with the grant id as the first token of the call (README, "Dispatching from a session").
- Every commit carries `Source:` and `Co-Authored-By:`; every paragraph that claims carries its reading (the claim skill).
- Draft PR into dev, body per CONTRIB.md, `## Proof` naming the corpus rows; the ready flip waits for a closed `security-audit` record on codex `gpt-daybreak-blue-latest` at the head sha with every finding disposed; a commit after the audit touching any path outside `.dev/records/` voids it, a record landing does not.
- A CHANGES verdict is a stop, ruled on by a harness that produced neither the artifact nor the finding (ops/process/cross-review.md), never by the builder; report the PR to agentscient-11 by message with its number, head, readings and what was not measured.

Builder: agentscient-c8, after S5. Wall half: W4 in the Lead's queue.
