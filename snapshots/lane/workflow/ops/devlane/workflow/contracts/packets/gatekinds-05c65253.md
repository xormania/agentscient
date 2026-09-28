# packet gatekinds-05c65253

observation: `gatekinds`  definition: `#GateKinds`
id: `<name>-<sha256(error path)[:8]>` = `gatekinds` + `05c65253`

## the disagreement

error path: `facts.kinds.0.spec.stages.2.advance_to`

```
facts.kinds.0.spec.stages.2.advance_to: field not allowed:
    ./obs/gatekinds.json:28:16
```

## what the extractor observed

```json
"review"
```

## provenance for that fact

### `kinds[gate-kinds/artifact.json]`

- file: `gate-kinds/artifact.json`
- lines: `1-45`
- rule: 5.3 kinds: gate-kinds/*.json, sorted by file

```
{
  "kind": "artifact",
  "version": 1,
  "stages": [
    {
      "name": "draft",
      "leave_requires": []
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "ratify",
        "finding": "fix",
        "rejected": "fix",
        "denied": "terminal",
        "aborted": "terminal"
      }
    },
    {
      "name": "fix",
      "leave_requires": [],
      "advance_to": "review",
      "blocked_by_open_markers": true
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [],
  "harness_scope": [],
  "checks": [
    {"name": "vocabulary-wall", "class": "policy",
     "argv": ["python3", "ops/devlane/workflow/checks/vocabulary_wall.py"], "ci": true},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true}
  ]
}

```

### `kinds[gate-kinds/artifact.json].sha256_canonical`

- file: `gate-kinds/artifact.json`
- lines: `1-45`
- rule: 5.3 sha256_canonical: sha256 over json.dumps(obj, sort_keys=True, separators=(',',':'))

```
{
  "kind": "artifact",
  "version": 1,
  "stages": [
    {
      "name": "draft",
      "leave_requires": []
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "ratify",
        "finding": "fix",
        "rejected": "fix",
        "denied": "terminal",
        "aborted": "terminal"
      }
    },
    {
      "name": "fix",
      "leave_requires": [],
      "advance_to": "review",
      "blocked_by_open_markers": true
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [],
  "harness_scope": [],
  "checks": [
    {"name": "vocabulary-wall", "class": "policy",
     "argv": ["python3", "ops/devlane/workflow/checks/vocabulary_wall.py"], "ci": true},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true}
  ]
}

```

### `kinds[gate-kinds/artifact.json].sha256_raw`

- file: `gate-kinds/artifact.json`
- lines: `1-45`
- rule: 5.3 sha256_raw: sha256 over the file bytes on disk

```
{
  "kind": "artifact",
  "version": 1,
  "stages": [
    {
      "name": "draft",
      "leave_requires": []
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "ratify",
        "finding": "fix",
        "rejected": "fix",
        "denied": "terminal",
        "aborted": "terminal"
      }
    },
    {
      "name": "fix",
      "leave_requires": [],
      "advance_to": "review",
      "blocked_by_open_markers": true
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [],
  "harness_scope": [],
  "checks": [
    {"name": "vocabulary-wall", "class": "policy",
     "argv": ["python3", "ops/devlane/workflow/checks/vocabulary_wall.py"], "ci": true},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true}
  ]
}

```

### `kinds[gate-kinds/tdd.json]`

- file: `gate-kinds/tdd.json`
- lines: `1-61`
- rule: 5.3 kinds: gate-kinds/*.json, sorted by file

```
{
  "kind": "tdd",
  "version": 1,
  "stages": [
    {
      "name": "spec",
      "leave_requires": []
    },
    {
      "name": "red",
      "leave_requires": ["receipt.red"]
    },
    {
      "name": "impl",
      "leave_requires": ["receipt.green"],
      "seals_frozen_set": true
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "advance",
        "finding": "impl",
        "denied": "terminal"
      }
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [
    "crates/*/tests/**",
    "crates/*/src/**/*_test.rs",
    "ops/design/features/**"
  ],
  "harness_scope": [
    "Cargo.toml",
    "Cargo.lock",
    ".cargo/**",
    "rust-toolchain*",
    "crates/*/build.rs"
  ],
  "checks": [
    {"name": "cargo-test", "class": "build",
     "argv": ["cargo", "test", "--workspace"]},
    {"name": "audit", "class": "security",
     "argv": ["cargo", "audit"]},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true},
    {"name": "diagnostics", "class": "diagnostics",
     "argv": ["python3", "ops/devlane/workflow/checks/diagnostics.py",
              "--", "cargo", "check", "--message-format=json"]}
  ]
}

```

### `kinds[gate-kinds/tdd.json].sha256_canonical`

- file: `gate-kinds/tdd.json`
- lines: `1-61`
- rule: 5.3 sha256_canonical: sha256 over json.dumps(obj, sort_keys=True, separators=(',',':'))

```
{
  "kind": "tdd",
  "version": 1,
  "stages": [
    {
      "name": "spec",
      "leave_requires": []
    },
    {
      "name": "red",
      "leave_requires": ["receipt.red"]
    },
    {
      "name": "impl",
      "leave_requires": ["receipt.green"],
      "seals_frozen_set": true
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "advance",
        "finding": "impl",
        "denied": "terminal"
      }
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [
    "crates/*/tests/**",
    "crates/*/src/**/*_test.rs",
    "ops/design/features/**"
  ],
  "harness_scope": [
    "Cargo.toml",
    "Cargo.lock",
    ".cargo/**",
    "rust-toolchain*",
    "crates/*/build.rs"
  ],
  "checks": [
    {"name": "cargo-test", "class": "build",
     "argv": ["cargo", "test", "--workspace"]},
    {"name": "audit", "class": "security",
     "argv": ["cargo", "audit"]},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true},
    {"name": "diagnostics", "class": "diagnostics",
     "argv": ["python3", "ops/devlane/workflow/checks/diagnostics.py",
              "--", "cargo", "check", "--message-format=json"]}
  ]
}

```

### `kinds[gate-kinds/tdd.json].sha256_raw`

- file: `gate-kinds/tdd.json`
- lines: `1-61`
- rule: 5.3 sha256_raw: sha256 over the file bytes on disk

```
{
  "kind": "tdd",
  "version": 1,
  "stages": [
    {
      "name": "spec",
      "leave_requires": []
    },
    {
      "name": "red",
      "leave_requires": ["receipt.red"]
    },
    {
      "name": "impl",
      "leave_requires": ["receipt.green"],
      "seals_frozen_set": true
    },
    {
      "name": "review",
      "leave_requires": [],
      "outcomes": {
        "accepted": "advance",
        "finding": "impl",
        "denied": "terminal"
      }
    },
    {
      "name": "ratify",
      "actor": "owner",
      "leave_requires": [],
      "outcomes": {
        "ratified": "terminal",
        "denied": "terminal",
        "aborted": "terminal"
      }
    }
  ],
  "test_scope": [
    "crates/*/tests/**",
    "crates/*/src/**/*_test.rs",
    "ops/design/features/**"
  ],
  "harness_scope": [
    "Cargo.toml",
    "Cargo.lock",
    ".cargo/**",
    "rust-toolchain*",
    "crates/*/build.rs"
  ],
  "checks": [
    {"name": "cargo-test", "class": "build",
     "argv": ["cargo", "test", "--workspace"]},
    {"name": "audit", "class": "security",
     "argv": ["cargo", "audit"]},
    {"name": "secret-scan", "class": "security",
     "argv": ["python3", "ops/devlane/workflow/checks/secret_scan.py"], "ci": true},
    {"name": "diagnostics", "class": "diagnostics",
     "argv": ["python3", "ops/devlane/workflow/checks/diagnostics.py",
              "--", "cargo", "check", "--message-format=json"]}
  ]
}

```

## the contract text cited above

### `./obs/gatekinds.json:28`

```
   26 |               "name": "fix",
   27 |               "leave_requires": [],
   28 |               "advance_to": "review",
   29 |               "blocked_by_open_markers": true
   30 |             },
```

## verdict required

Write `verdicts/gatekinds-05c65253.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

