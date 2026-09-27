# Research report — agent delegation queues, and where our law fits

- commissioned: owner, 2026-09-01, verbatim: "i need this idea added
  to our idea system - and then i need a real research report into it
  (this is something to be tagged and saved - it is part of what
  project needs to do)"
- classification (the Project charter's axes, hand-run):
  subject: framework · horizon: now · authority: owner-policy for
  adoption, conductor-design for the analysis
- state: classified — feeds the framework scoping talks and the
  commissioned pilot; intake pointers: the Linear idea record and the
  independent-excavation record in `ops/conductor/ideas/`
- provenance: two web research passes and one vendor-doc fetch on
  2026-09-01, sources dated inline; repo-internal claims cite the
  session's own record

## The question

The owner holds the Linear-side integration of OpenAI's coding agent
and recognized the shape as their own ("this sounds VERY fimiliar -
my higher roles?"). What is the product landscape, how does it map
onto the architecture already recorded here, and what should the
framework buy, borrow, or build?

## The mechanics, per vendor documentation

**OpenAI Codex via Linear** (learn.chatgpt.com/docs/third-party/
linear.md, fetched 2026-09-01): a Linear issue is assigned to Codex
like a teammate, or `@Codex` is mentioned in a comment. A cloud
agent wakes in a pre-configured "environment" bound to a GitHub
repository, reads the full issue as its brief, selects the
environment by issue context (pinnable by comment), and works
against the default branch of the environment's first mapped
repository. Progress and a completion summary post back into the
issue's activity; a session link lets a human review and create the
GitHub PR. Paid ChatGPT plan required; a Linear MCP server exists
for local use.

**GitHub Copilot coding agent** (github.blog and docs.github.com,
2026-09-01): the GitHub-native version of the same shape — assign a
GitHub Issue to Copilot and an agent spins up an Actions-powered
environment, pushes commits to a draft PR as it works, leaves
session logs, runs tests, self-reviews, security-scans, and tags the
assigner for review. Queue and forge are the same product here;
Linear is not involved.

**Linear as a multi-agent queue** (linear.app/integrations/agents,
fetched 2026-09-01): the sharpest finding. Linear positions agents
as assignable "AI teammates" and lists twenty-plus — Codex, Cursor,
GitHub Copilot, Devin, Factory, Sentry among the featured — behind
one assignment model, and publishes an API and developer framework
inviting third-party agents into the directory. Linear is not an
OpenAI surface; it is a vendor-neutral queue with pluggable
consumers.

**xAI** (searched 2026-09-01, owner's question): in the race on both
ends. Grok Build (May 2026) is a terminal coding agent whose
architectural bet is parallelism — up to eight concurrent sub-agents,
each in its own git worktree on its own branch, which is this repo's
worktree-per-line doctrine productized as a flag. Grok Bot (beta,
August 2026) is the always-on cloud-worker product: each assigned
task gets a persistent cloud computer that keeps working after the
device closes. Linear does not feature Grok as a first-party agent,
but Grok Build consumes MCP servers — by the vendor's own claim,
anything wired for Claude Code works with zero reconfiguration.
Consequence for the lane: the planned conductor MCP server would
feed this harness and Grok Build alike — the cross-harness
context-plane thesis confirmed from a vendor's side.

## The convergence

The triangle — queue surface, assignable agents, cloud workers,
results back to queue and forge — is the architecture already in
this repo's record: the Project charter's push queue ("Project
pushes by EMITTING"), the officer layer, async workers on the
horizon, and the owner's higher roles with narrow charges. The
charter has a name for an outside artifact matching the design:
independent excavation of the same shape. Two major vendors
excavating it independently de-risks the architecture and marks the
queue-and-worker layer as commodity in progress.

## Where our law does not fit their products

Measured against this repo's standing rules, three gaps — none
fatal, all naming the boundary of what can be delegated:

1. **Branch and forge law.** The Codex environment works against a
   default branch and its PRs follow suit; our law is branch from
   dev, PR to dev, never touch main. Instructions in the issue text
   can order compliance; whether an agent obeys is measurable, and
   the commissioned pilot's first axis.
2. **Attribution and evidence law.** No product emits our Source
   and Co-Authored-By trailers, write-time evidence, or wire-format
   review stamps. Outputs need the harvest-and-credit treatment the
   dispatch lane already gives its own workers — or they trip the
   gates, exactly as the GitHub reviewer's own largest finding class
   (attribution enforcement, 166-finding corpus mined 2026-09-01)
   predicts.
3. **Custody.** No staged snapshots, no withholding proved, no
   record store, no refusal wire, no firewall over who may produce
   what, no calibration of the stochastic parts. Their agent works
   on trust; ours work inside measured trust. This is the layer no
   vendor ships.

## The split this implies

Buy or borrow the queue plumbing; build the trust layer — under the
owner's standing constraint, stated while this report was written:
"harness or vendor tie in is not acceptable - but we can use the
shit of their capabilities when possible." Every vendor surface
below is therefore an adapter, never a dependency: the queue of
record, the records, and the law stay ours; a vendor's removal
costs a config line, not a redesign.

- **Borrow**: Linear as the owner-facing queue surface is cheap to
  try (the owner already holds it), and its open agent API means the
  house's own dispatched workers could eventually appear as
  assignable teammates in the same queue — the officer corps wearing
  a product UI. GitHub-native Copilot assignment is the same
  experiment one vendor over, with the forge and queue unified.
- **Build**: custody, law, calibration, the gauntlet — the
  framework's differentiated layer, unshipped by anyone, and the
  reason a delegated task here ends as a governed landing rather
  than a trusted merge.
- **Boundary**: delegation to outside agents stays at well-defined,
  low-custody tasks; pipeline producer stages remain behind the
  firewall.

## The commissioned pilot

One chore issue with the law written into its text (branch target,
trailers, invent-nothing), scored on seven axes: PR base branch,
trailers, correctness against spec, scope discipline, the repo's CI
gates, one dispatched adversarial review, and issue-to-PR latency.
Status at writing: issue text delivered to the owner; awaiting the
owner's Linear-side steps. The verdict amends this report.

## Sources

- learn.chatgpt.com/docs/third-party/linear.md (fetched 2026-09-01)
- linear.app/integrations/codex and /integrations/agents (2026-09-01)
- linear.app/changelog/2025-12-04-openai-codex-agent
- github.blog: "GitHub Copilot: meet the new coding agent";
  "Assigning and completing issues with coding agent"
- docs.github.com: "About GitHub Copilot cloud agent"
- This repo's record: the Project charter (scratch), the stack
  document, the 2026-09-01 session's idea files and reviewer-corpus
  mining
