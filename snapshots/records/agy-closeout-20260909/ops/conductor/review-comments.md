# External PR review comments — the resolution procedure

Owner, 2026-08-31: "one thing you have to manage: resolving codex PR review
comments. It has to be documented." This is that document. It applies to
every inline finding an external reviewer posts on a GitHub PR — the Codex
connector, a human, any harness with an account — and treats each as a
finding in the CONTRIB review-protocol sense, managed to closure.

1. **Verify first.** The finding is checked against the live tree (command
   + sha) before any action — CONTRIB's rule, unchanged by the medium.
2. **Route through the pipeline.** A finding against a contract forces an
   amendment (conductor); anything else becomes a fix dispatch. The finding
   text travels verbatim in the brief.
3. **Reply on the thread when its state changes**, carrying: the verdict
   (confirmed / refuted), the fix commit sha and dispatch record id — or
   the refuting command — and where the fix lands (branch, PR).
4. **Resolve only when the fix is reachable from the PR's head.** For a
   dev→main PR that means after the carrying PR has merged to dev. "Fixed
   on a side branch" is a reply, not a resolution.
5. **Refutation is closure.** A refuted finding is resolved with the
   refuting command in the reply.
6. **Replies are evidence.** Every claim in a reply is produced by a
   command at write time and stamped with the sha it was measured against —
   the PR-body rule, applied to threads.

## Open under this procedure, 2026-08-31

- PR #81, `launch.py:627` and `:522` — both confirmed; fixes implemented on
  `harness-fixes/dev` (D-ENV-4, D-DIFF-1; residual findings in the U10b fix
  cycle in flight). Replies + resolution due after #83 merges to dev
  (rule 4).
- PR #81, `launch.py:324` — replied and resolved 2026-08-30 while the fix
  sat on the side branch; early under rule 4. Noted, not re-litigated: the
  fix (D-ENV-2) is verified present on `harness-fixes/dev`.
