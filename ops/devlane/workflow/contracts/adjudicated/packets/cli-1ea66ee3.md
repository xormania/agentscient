# packet cli-1ea66ee3

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `1ea66ee3`

## the disagreement

error path: `facts.commands`

```
facts.commands: incompatible list lengths (16 and 17):
    ./cue/cli.cue:603:13
```

## what the extractor observed

```json
[
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--reason"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--to"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "advance",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "agents",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--allow-dirty"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--kind"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--verify-only"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": "*",
        "positional": "target",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "check",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--note"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--ttl"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "claim",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--message"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": "?",
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "commit",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "export",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--allow-dirty"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "green",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--rebuild"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "init",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--all"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--attempts"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--full"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--recorded-by"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--since"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--type"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "-n",
          "--number"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "log",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--note"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": [
          "open",
          "close"
        ],
        "nargs": null,
        "positional": "action",
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "id",
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "marker",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": "?",
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "next",
    "next_json_keys": [
      "advances",
      "advances_complete",
      "claim",
      "frozen",
      "head",
      "kind",
      "last_commit",
      "missing",
      "note",
      "objective",
      "open_markers",
      "outcomes",
      "requires_agent",
      "satisfied",
      "seq",
      "stage",
      "status",
      "wo"
    ]
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--kind"
        ],
        "nargs": null,
        "required": true
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--objective"
        ],
        "nargs": null,
        "required": true
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": "?",
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "open",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--by"
        ],
        "nargs": null,
        "required": true
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--note"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "value",
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "outcome",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--allow-dirty"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "red",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": null,
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "release",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--checks"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "nargs": "?",
        "positional": "wo",
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "status",
    "next_json_keys": "n/a"
  },
  {
    "arguments": [
      {
        "action": null,
        "choices": null,
        "flags": [
          "--agent"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--deep"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--json"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "store_true",
        "choices": null,
        "flags": [
          "--no-commit"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": null,
        "choices": null,
        "flags": [
          "--root"
        ],
        "nargs": null,
        "required": null
      },
      {
        "action": "append",
        "choices": null,
        "flags": [
          "--source"
        ],
        "nargs": null,
        "required": null
      }
    ],
    "helpers_applied": [
      "common_options"
    ],
    "name": "verify",
    "next_json_keys": "n/a"
  }
]
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:603`

```
  601 | 	global_arguments!: [] | [#GlobalJsonArgument]
  602 | 	// PLAN.md SS4 lines 238-259 -- CLI-S01 (stated)
  603 | 	commands!: [
  604 | 		// PLAN.md SS4 lines 253-253 -- CLI-S01 (stated)
  605 | 		#Command & {name: "advance"},
```

## verdict required

Write `verdicts/cli-1ea66ee3.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

