export HAND_GRANT=43
export PYTHONFAULTHANDLER=1 LAUNCHER_PIN=/home/scientdb/projects/uscient/wt/ag-check-tests-json/ops/devlane/dispatch/launch.py DISPATCH_TIMEOUT=3600 WF_AGENT="Claude Fable 5.1 <noreply@anthropic.com>"
cd /home/scientdb/projects/uscient/wt/ag-check-tests-json
bash ops/bin/dispatch.sh --job security-audit --harness codex --worktree /home/scientdb/projects/uscient/wt/ag-check-tests-json --scope-file /tmp/claude-1006/-home-scientdb-projects-uscient-agentscient/c1b9ce7c-856f-4586-b441-b2f10e66d5d4/scratchpad/scope-check-tests-json-2-audit.md --input /tmp/claude-1006/-home-scientdb-projects-uscient-agentscient/c1b9ce7c-856f-4586-b441-b2f10e66d5d4/scratchpad/PLAN-check-tests-json-2.md --input /tmp/claude-1006/-home-scientdb-projects-uscient-agentscient/c1b9ce7c-856f-4586-b441-b2f10e66d5d4/scratchpad/input-check-tests-json-2-plan.md --stage review --unit lane/check-tests-json
echo "DISPATCH EXIT $?"
