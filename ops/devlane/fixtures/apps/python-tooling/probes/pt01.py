from pathlib import Path

from tool.cli import run_helper

marker = Path("pt01-shell-marker")
marker.unlink(missing_ok=True)
try:
    run_helper(f"literal; touch {marker}")
    planted = marker.exists()
finally:
    marker.unlink(missing_ok=True)
raise SystemExit(1 if planted else 0)
