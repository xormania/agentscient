# Named job-card cap ruling — 2026-09-05

UPHELD: [PR 72 review finding](https://github.com/uscient/agentscient/pull/72#discussion_r3942119410)
against `e7558dea9e10835f3fcfaeebb703199119833b38`. The finder is the GitHub
Codex review; the disputed implementation was produced by GPT-5.6 Sol.
GPT-6 produced neither and rules before the fix under the owner's request.

Section 5 of `ops/conductor/lane-mcp-v2.md` gives the unnamed list and the
named card separate result shapes. The 64-entry limit applies to listing.
A named card returns `jobs: []`; unrelated registry entries must not prevent
that bounded lookup. The existing source-size and complete-query bounds
continue to apply to both forms.

Root reproduced the finding with synthetic registries at the reviewed SHA:
64 entries occupied 6208 bytes and both a named CLI query and its resource
returned ok; 65 entries occupied 6305 bytes and both incorrectly returned
unavailable with reason `registry lists more than 64 jobs`. The unnamed list
correctly returned unavailable at 65 entries. The probe invoked the copied
entrypoint from that commit through CLI and stdio `resources/read` on owned
temporary sources. Existing tests cover the 65-entry list but no named lookup
against that registry (`rg -n '64|65|more than'` on the context test file).

Scope: correct only the application of the listing cap. Add a small independent
regression row covering a known named card through CLI, MCP tool and resource
at 65 entries; keep the list refusal and ordinary missing-name answer. The
contract is unchanged. Preserve all source and response bounds, v1 behavior,
and existing tests. The original pipeline's fix iteration is resumed; no new
feature plan is needed for this already declared behavior.

Tests precede the production fix and remain a different producer. The test
skeptic checks the new row before implementation. Final reviews run in separate
worktrees at the final candidate, and no automatic fix is applied to a CHANGES
finding before its independent ruling. Whole-tree snapshots remain physically
complete; test prompts prohibit implementation reads rather than claiming a
physical firewall.
