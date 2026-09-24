# Historical handwork ledger

Hand grants were retired by owner direction on 2026-09-24. Ordinary work needs
no declaration, grant ID, expiry, scope exception, or settlement. Current working
guidance lives in `AGENTS.md`; CI owns acceptance.

`python3 ops/conductor/tools/hand.py report` and `open` read retained historical
records. They do not create or modify the store. Existing rows are evidence of
past workflow friction, not current permission or outstanding obligations.
No recovery operation consults this ledger.
