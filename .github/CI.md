# Continuous integration

[ci.yml](workflows/ci.yml) runs on pull requests and pushes to `dev` and `master`,
merge groups, and manual invocation. Its `lane` check aggregates three jobs:

| Job | Checks |
| --- | --- |
| `live-mcp` | Ruff and the Python service, stdio MCP, native protocol, Git and GitHub fixture tests. |
| `symfony / php` | Locked Composer metadata/platform, PHP/YAML/container lint, PHPUnit, and real Maker/Mate integration through normal MCP. Uses [ci-prod-lane.yml](workflows/ci-prod-lane.yml). |
| `serena` | Build the pinned provider image and exercise real REPL persistence, PHPactor navigation, edits, protected paths, pause/resume and checkpointing. |
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
