from __future__ import annotations
import json
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "gh-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
sys.stdout.write("@@PR_URL@@\n")
raise SystemExit(0)
