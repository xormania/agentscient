```json
{
  "verdict": "changes",
  "findings": [
    {
      "id": "run-override-kills-suite",
      "severity": "blocker",
      "where": "ControlTests.run (helper), used by every test",
      "detail": "The helper `def run(self, id, agent=AUTHOR, timeout=12)` shadows `unittest.TestCase.run(self, result=None)`. The framework calls `test(result)` -> `self.run(result)`, so `id` binds to the TestResult and `self.state` is touched before setUp ever runs. The measured parent output confirms this: collection-time AttributeError in `run` at line 91, zero tests executed, no honest RED. Rename the helper (e.g. `do_run`/`run_action`) and update all call sites, including the concurrent lambda in test_actions_are_durable_once_only_concurrent_and_failed and the seat/timeout tests."
    },
    {
      "id": "red-is-not-intended-red",
      "severity": "blocker",
      "where": "whole suite / acceptance gate",
      "detail": "Consequence of the above: the current failure is an error inside TestCase.run before setUp, not the intended 'missing implementation' refusal/failure. Contract requires intended RED distinguishable from import/fixture errors; the suite cannot demonstrate that until the shadowing is fixed and the parent command shows real per-test failures against the absent controller."
    }
  ],
  "limits": [
    "hook(\"Bash\", \"malformed\") only asserts exit 0; it does not assert a deny object, so malformed-input denial per the native-boundary section is unverified.",
    "Log-size bound (8 MiB combined), plan-parse strictness (duplicate/unknown keys), scope/plan byte-drift rechecks, and PID+process-start-identity reuse are not exercised.",
    "Seat coverage checks second-seat and post-stop refusal only; it does not assert that an interrupted seat terminates still-owned action groups.",
    "Timeout test asserts abort and budget exhaustion but not retention of stdout/stderr paths for the aborted action."
  ]
}
```
