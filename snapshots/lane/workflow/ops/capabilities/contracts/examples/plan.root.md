# example — extract form of examples/plan.root.json

Prose around the tables is not read.

| # | premise | tag | source |
| --- | --- | --- | --- |
| 1 | plans at every level | read | owner 2026-08-29 |

| id | sentence | new | ratified_by | status | premises |
| --- | --- | --- | --- | --- | --- |
| D-root-one | The root names one leaf unit that delivers the plan gate. | true | owner | standing | [{"source":"owner 2026-08-29","tag":"read","text":"plans at every level"}] |

| # | unit | deliverables | gate | needs |
| --- | --- | --- | --- | --- |
| 1 | leaf | [{"interface":{"declared_at":"example \u00a71","name":"#Plan"},"path":"contracts/plan.cue"}] | plan | [] |

```json plan:deliverables
[
  {
    "interface": {
      "declared_at": "example \u00a71",
      "name": "#Plan"
    },
    "path": "contracts/plan.cue"
  }
]
```

```json plan:denied
[
  "reading outside the snapshot"
]
```

```json plan:discharge
{
  "decisions_to": "docs/DECISIONS.md",
  "design_to": "contracts/plan.md",
  "lessons_to": "docs/lessons.md"
}
```

```json plan:economics
{
  "write": {
    "minutes": 1,
    "tag": "assumed"
  }
}
```

```json plan:gates
[
  {
    "argv": [
      "python3",
      "checks/plan_vet.py",
      "vet",
      "example.plan.json"
    ],
    "cost": "cheap",
    "fires_on": "a planted fault",
    "name": "plan-vet-root",
    "quiet_on": "the clean root"
  }
]
```

```json plan:id
"example"
```

```json plan:open
[
  {
    "delegated_to": "leaf",
    "what": "The leaf delivers the plan gate as named by the root."
  }
]
```

```json plan:parent
{
  "declared_absent": "this is the root"
}
```

```json plan:ref
"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

```json plan:refusals
[
  "plan.absent-key",
  "plan.bound-prose",
  "plan.decision-multiline",
  "plan.decision-not-new",
  "plan.decision-unratified",
  "plan.definition",
  "plan.deliverables-mismatch",
  "plan.derived-key",
  "plan.drift",
  "plan.gate-cost",
  "plan.gate-half",
  "plan.leaf-open",
  "plan.premise-empty",
  "plan.premise-tag",
  "plan.ratified_by",
  "plan.reopened",
  "plan.root-parent",
  "plan.scope-drift",
  "plan.scope-oversize",
  "plan.settled-dropped",
  "plan.stage-blocked",
  "plan.stale-parent",
  "plan.status",
  "plan.undelegated"
]
```

```json plan:scope
{
  "dated": "2026-08-29",
  "owner_words": "framework first",
  "source": "owner 2026-08-29"
}
```

```json plan:settled
[
  {
    "dated": "2026-08-29",
    "id": "framework-before-surface",
    "ruled_by": "owner",
    "where": "owner 2026-08-29"
  }
]
```
