### Verb
`python3 ops/conductor/tools/laneconf.py defaults [--paths FILE…] [--strict]`
- Scan the same source set `literals()` uses (`ops/` and `.claude/`, suffixes `.py` `.sh`, skip `tests` `fixtures` `archive` `infra`), unless `--paths` names files; `--paths` still skips those four directory names if a named file sits under them.
- Do **not** read `DEFERRED_LITERAL_PATHS`. That list is why today's identity fallbacks are invisible to `literals()`.
- Hits, two families:
  1. Hardcoded lane value: a literal equal to a `lane.conf` value, or a compare/assign of `dev` / `master` / `agentscient` / `uscient/agentscient` / `../wt` / a `MODEL_*` / `EFFORT_*` / `ADDRESS_*` / `LANE_AUTHOR` / `WALL_DEFAULT` / `SCOPE_CAP` value, outside `lane.conf` itself and outside `laneconf.py`'s own token table. `NAME_KEYS` expands to every identity key including `WORKTREE_ROOT` and the address/model/effort/author/wall/scope keys. The `len >= 4` filter goes. Short `dev` is a token as `'"dev"'` and `"'dev'"` 