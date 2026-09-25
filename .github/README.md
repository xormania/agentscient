# CI

`dev` is the integration branch for both lanes. Changed files select CI;
the branch name does not select a lane.

| Change | Checks |
|---|---|
| Symfony application, packages, dependencies, configuration or tests | Prod-lane |
| `ops/`, harness configuration or Python tooling | Dev-lane |
| Both lanes, shared CI or an unclassified file | Both |
| Markdown only | Neither runtime suite |

`.github/ci_scope.py` contains the path mapping. It compares the actual event
checkout with the PR base, merge-group base or previous push revision. Renames
include both paths; unreadable revisions fail selection. Every automatic run
reports `lane`, which succeeds only when selection and all selected jobs succeed.
Skipped work is shown as skipped. There are no prose-content acceptance checks
in prod-lane CI.

`ci-prod-lane.yml` runs Composer validation and locked installation, PHP lint,
Symfony configuration/container checks and PHPUnit. It is also available through
manual workflow dispatch. Logs and the uploaded artifact identify the tested
revision; PHPUnit writes JUnit results. The initial app has no test cases yet,
so an empty PHPUnit run is not evidence of application behavior coverage.

Dev-lane keeps its existing test profiles and execution receipts. Both workflows
respect `CI_RUNNER_MODE`: `local` uses the registered self-hosted runner; `hosted`
or an empty value uses Ubuntu. Runner choice does not change prod-lane coverage.
If Composer is absent, prod-lane verifies the official installer checksum and
downloads Composer into the job's temporary directory.
