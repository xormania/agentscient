export HAND_GRANT=43
export PYTHONFAULTHANDLER=1 LAUNCHER_PIN=/home/scientdb/projects/uscient/wt/ag-check-tests-json/ops/devlane/dispatch/launch.py DISPATCH_TIMEOUT=3600 WF_AGENT="Grok 4.6 <noreply@x.ai>"
cd /home/scientdb/projects/uscient/wt/ag-check-tests-json
bash ops/bin/dispatch.sh --job implement --harness codex --worktree /home/scientdb/projects/uscient/wt/ag-check-tests-json --scope-file /home/scientdb/projects/uscient/wt/ag-check-tests-json/.dev/ladder-inputs/fix-round/scope-check-tests-json-impl.md --input /home/scientdb/projects/uscient/wt/ag-check-tests-json/.dev/ladder-inputs/fix-round/input-check-tests-json-2-impl.md --stage code --unit lane/check-tests-json
echo "DISPATCH EXIT $?"
