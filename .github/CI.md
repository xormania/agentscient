# Continuous integration

[ci.yml](workflows/ci.yml) runs on pull requests into `dev`, `master` and
`work-order/*`, pushes to `dev` and `master`, merge groups, and manual invocation.
Its `lane` check aggregates three jobs:

| Job | Checks |
| --- | --- |
| `live-mcp` | Ruff and the Python service, stdio MCP, native protocol, Git and GitHub fixture tests. |
| `symfony / php` | Locked Composer metadata/platform, PHP/YAML/container lint, PHPUnit, and real Maker/Mate integration through normal MCP. Uses [ci-prod-lane.yml](workflows/ci-prod-lane.yml). |
| `serena` | Build the pinned provider image and exercise real REPL persistence, PHPactor navigation, edits, protected paths, pause/resume, checkpointing and provider shutdown after release. |
| `lane` | Succeeds only when all three preceding jobs succeed. This is the aggregate result for branch protection. |

The Symfony job uploads its tested revision, dependency observations, PHPUnit
results and development-tool output as a CI artifact. The Serena job records its
build and integration results in the workflow logs.

## Runner selection

The repository variable `CI_RUNNER_MODE` selects execution:

| Value | Runner |
| --- | --- |
| `hosted` or unset | GitHub-hosted Ubuntu 24.04 |
| `local` | Registered self-hosted runner |

Any other value fails runner selection. The same jobs run in either mode.
The self-hosted PHP setup requires Linux/X64. Runners need Python, Git, Docker and
the download/archive tools used by [php-runtime](actions/php-runtime/action.yml).
That action supplies temporary pinned PHP and installs Composer when absent,
without replacing global PHP. Select runner mode as an operator choice.

## Local verification

From the repository root, use the relevant checks:

```sh
python3 -m unittest discover -s devtools/tests -v
uv tool run --from ruff==0.16.8 ruff check devtools
```

The Ruff command uses `uv`; an installed Ruff matching the workflow pin also works.
The integration scripts require the installed application dependencies or the
built Serena image described in [setup](../docs/local-agent-readiness.md):

```sh
python3 devtools/integration/symfony.py
python3 devtools/integration/serena.py
```

They use disposable repositories/worktrees. The Python suite uses native protocol
and GitHub HTTP fixtures; the integrations execute real Symfony and Serena code.
Neither proves authenticated model behavior. Record that separately through the
[local acceptance run](../docs/local-agent-readiness.md#authenticated-local-acceptance).

## GitHub settings

Configure these as the repository owner in **Settings → Rules → Rulesets**:

| Target | Rules |
| --- | --- |
| `dev` | Require a pull request and successful `lane` from GitHub Actions; block force pushes and deletion. |
| Include `work-order/*`, exclude `work-order/*-job-*` | Require a pull request and successful `lane` from GitHub Actions; block force pushes. Allow branch creation and deletion. |

In the active **work-order** ruleset's **Target branches**, include `work-order/*`
and add an **Exclude by pattern** entry for `work-order/*-job-*`. Both generated
names have one slash: `work-order/<wo>` is protected, while
`work-order/<wo>-job-<job>` accepts normal, non-forced pushes of review fixes.
For example, `work-order/123-job-7` opens its PR into `work-order/123`, and that
work-order branch opens its final PR into `dev`. The exclusion is necessary:
without it, the broad include would require a PR just to update a job branch.
Ensure other active rulesets or classic protections do not independently require
PRs on job branches; an exclusion applies only to the ruleset containing it.
Leave **Restrict creations** and
**Restrict updates** off. For the work-order status check, select **Do not require
status checks on creation**, so a new branch can start at the tested development
revision. Keep the required aggregate named `lane`; remove obsolete required
contexts only after checking they are no longer produced by current CI.

The workflow tests each job PR against its work-order base and the final work-order
PR against development. Pushing a review fix to the same job branch triggers
`pull_request.synchronize`, reruns CI on the updated PR and leaves the merge into
the work order blocked until its required `lane` check passes. The MCP merge
service rechecks both CI and GitHub's merge eligibility before requesting a merge;
it does not use credential bypass authority to ignore reported requirements.
**Require branches to be up to date before merging** is
optional additional strictness: it can require refreshing jobs and an integration
job before final delivery when development advances. No service bypass is needed.
The runtime honors GitHub's merge eligibility and never configures these rules.

Under **Settings → General → Pull Requests**, leave at least one supported merge
method enabled. Merge commits preserve the relationship between sibling jobs;
squash and rebase remain supported, with merge evidence retained separately.
Optional **Automatically delete head branches** removes remote job branches after
their PRs merge and the work-order branch after its final merge. Local cleanup is
independent. This PR does not change release/master or archive protections.

Required approving reviews are an owner choice. The runtime's audit comments are
not approvals from another GitHub identity. Do not grant the automation an owner
bypass merely to satisfy a review count.

References: [creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository),
[available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets),
[required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
