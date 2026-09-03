# example/leaf — extract form of examples/plan.json

Prose around the tables is not read.

| # | premise | tag | source |
| --- | --- | --- | --- |
| 1 | plans at every level | read | owner 2026-08-29 |

| id | sentence | new | ratified_by | status | premises |
| --- | --- | --- | --- | --- | --- |
| D-leaf-one | The leaf delivers the plan gate as named by the root. | true | pending | standing | [{"source":"owner 2026-08-29","tag":"read","text":"plans at every level"}] |

| # | unit | deliverables | gate | needs |
| --- | --- | --- | --- | --- |

The leaf has no units; the table is present and empty of data rows.

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
      "plan.json"
    ],
    "cost": "cheap",
    "fires_on": "a planted fault",
    "name": "plan-vet-leaf",
    "quiet_on": "the clean leaf"
  }
]
```

```json plan:id
"example/leaf"
```

```json plan:open
[]
```

```json plan:parent
{
  "bound_to": "sidecar",
  "id": "example",
  "sha256": "27af1e2ea72d54bf53118082fd1d88a0f72db510c54e6082ba7f8cb2d637307b",
  "unit": "leaf"
}
```

```json plan:ref
"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

```json plan:refusals
[
  "plan.stale-parent"
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
  },
  {
    "dated": "2026-08-29",
    "id": "D-root-one",
    "ruled_by": "owner",
    "where": "parent decision D-root-one"
  }
]
```
