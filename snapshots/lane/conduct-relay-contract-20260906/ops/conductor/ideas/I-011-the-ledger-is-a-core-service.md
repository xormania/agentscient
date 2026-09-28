# The ledger is a core service

The lane now keeps four append-only evidence stores as separate SQLite
files with tracked exports: the handwork ledger (`hand.py`), the
register (`decisions.py`), the skills registry (`skills.py`) and the
findings ledger (`findings.py`). They share one shape: a row is a fact
with who set it and when, rows are never edited, the store is local and
the export is tracked.

Owner, 2026-09-04, in session: "ledger feels like a core Agenscient
symfony service". Proposed: one Ledger service in the Symfony project,
four projections (Console, TUI, MCP read-only, API), of which the four
Python stores are the functional specification; each retires when the
twin passes its conformance row (AGENTS.md §The lane). Not ruled;
recorded for the plan of the first package.
