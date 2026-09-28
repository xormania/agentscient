# Slice write-path-produce (S)

Ledger 50, finding `20260904T180026Z-review-codex-23ee3d#3` only. Do not edit ladder.py (51 owns it).

## Contract

A write verb plus a path-shaped token is a write path. The recogniser is not a closed verb list. `Produce REVIEW in the repository`, `Generate REVIEW in the repository`, `Create REVIEW on disk`, `Dump REVIEW in the repository` are writes. Existing 21 guard tests stay green.

Files: `ops/devlane/task/write_path.py`. Tests: `ops/devlane/task/tests/test_check_tests_json.py` method already named for the produce/generate/create/dump plants.

Improvisation: do not touch ladder.py or jobs.json catalogue of other jobs.

slice	write-path-produce	S
bucket	write-path-produce	S	ops/devlane/task/write_path.py
