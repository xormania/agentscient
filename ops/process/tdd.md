# TDD under conductor control

Use the [conductor control](../conductor/conductor-control.md) execution
boundary for conductor work. The owner freezes the task, commands, producer
identities, test paths, dependencies, expiry and total time allowance. The
conductor may select an existing action once. It cannot add a retry or rewrite
the acceptance criteria.

The owner initializes a new state directory outside the worker worktree:

```sh
python3 ops/conductor/tools/control.py init /absolute/plan.json --state /absolute/control-state
```

The owner starts the supported, verified native host through `control.py seat`.
Its mandatory PreToolUse hook allows declared `run` actions and diagnostic
reads. Direct edits, raw launches and reinitialization refuse. Follow the
activation procedure in the conductor control contract before relying on a
host; a settings file alone does not establish active interception.

## The sequence

1. **Tests:** a separate producer writes and tracks the complete test set,
   including helpers and fixtures. The controller seals the actual bytes.
2. **Fixture:** exercise the test setup and relevant existing consumers. A
   successful fixture must establish that later assertions reach the intended
   behavior. The independent reviewer judges this evidence.
3. **RED:** the controller runs `unittest discover` itself. At least one test
   must fail an assertion; import errors, skips, unexpected successes and zero
   tests do not count. The actual result and tracebacks are retained.
4. **Test review:** a producer distinct from both author and implementer reviews
   the tests and fixture/RED evidence. Its approval binds the exact test manifest
   and RED output hash. Exit zero without that attestation does not admit code.
5. **Code:** the controller refuses unless the full prerequisite chain is
   successful and the same test bytes remain intact. The implementer cannot
   modify the sealed tests.
6. **GREEN:** run the same discovery arguments as RED. All tests must pass and
   the sealed bytes must still match. Complete the plan's separate review/check
   actions before proposing integration.

Invoke a declared action with its frozen ID and state directory:

```sh
python3 /absolute/repo/ops/conductor/tools/control.py run tests-1 --state /absolute/control-state
python3 /absolute/repo/ops/conductor/tools/control.py status --state /absolute/control-state
```

A failed, interrupted or already reserved action is consumed. Do not resume it
under a new name. A defective test requires independent correction and review
in a new owner-issued cycle; the conductor cannot grant that cycle to itself.
Expiry and the conductor seat wall stop further work, including repeated reads
or thinking after the finite allowance. Retained status and logs remain readable.

## Evidence and limits

The owner plan identifies producers; this is an attestation boundary, not proof
of who controls an arbitrary process. Reviewers still judge whether fixtures,
assertions and the declared test set are meaningful and complete. The hook
controls tools in a supported native host. Same-UID owner shell access remains
a trust boundary; unhooked hosts are not authorized conductor execution paths.

The former instructions for writing `ops/devlane/workflow/wf.py` receipts are
withdrawn here. Do not use a historical receipt command as evidence that this
execution gate admitted work. Publish measured command results against the
actual tree or commit, and distinguish unavailable evidence from a clean result.
