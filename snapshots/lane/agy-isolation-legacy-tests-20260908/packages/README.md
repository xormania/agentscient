# packages — where Agentscient's packages gestate

Each package lives here package-shaped from its first commit: its own
`composer.json` (type `symfony-bundle`, vendor `agentscient`), its own
tests under `tests/`, its own README. Siblings are reached only through
Composer — the project's path repository covers `packages/*` — never by
relative import, so graduation is a subtree split plus a Flex recipe and
never a refactor. The project composes them; the project's PHPUnit runs
every package's suite (`packages/*/tests`).

A package graduates to its own repository when its boundary is proven.
Ruling: `AGENTS.md` §Standing rulings.

Empty by declaration: no package has landed yet. The first is the wire
(`docs/wire.md`; `docs/mapping.md` §What this settles).
