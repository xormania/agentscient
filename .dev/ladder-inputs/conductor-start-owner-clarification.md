# Conductor startup — owner clarification, 2026-09-05

The owner clarified the scope after the initial plan and boundary-review
dispatches were launched:

> The point of the conductor is to keep session context clean of imlimentation details

> pre-tool should prvent you from doing anything other then delgating

The existing Claude Code settings and their pre-tool enforcement are the
behavioral starting point. The desired launcher selects Claude, Codex, or
Grok as conductor, forwards CLI arguments, and preserves that role across
the system. Worker investigation and implementation go through lane dispatch;
the root session scopes, delegates, reads reports, rules, and coordinates.

The initial broad host-isolation proposal is research evidence, not an
accepted implementation plan. Separate role enforcement from any additional
host-containment work when discussing the findings.

The owner then explicitly limited the current work:

> look into it - but before implimenting - i want to discuss.

Finish the settings and harness-compatibility investigation and discuss the
proposed behavior before tests, implementation, or active configuration changes.
The three current dispatches produce research/design evidence only:

- `20260905T234530Z-plan-claude-56d481`
- `20260905T234559Z-review-codex-a079d6`
- `20260905T234846Z-review-grok-8e1450`
