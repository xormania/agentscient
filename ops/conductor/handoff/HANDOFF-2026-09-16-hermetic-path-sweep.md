# HANDOFF 2026-09-16 — the hermetic-PATH sweep

The input for the sweep that follows PR #247. LD-72 made a world's PATH
its own bin alone, so every fixture that ran a host tool by bare name now
gets a refusal instead of the operator's copy. This is the list of what
that turned red, measured, not estimated.

Each row's remedy is in the refusal it already gets: name the tool, with
`World(ambient_tools=("git",))` when the case wants the real host tool, or
plant a fake with `world.tools.plant`. `World.git()` needs no declaration;
it carries git for itself. Nothing on this list needs a decision — it
needs the declaration each fixture always owed.

The measurement below was taken on `lane/session-20260916-g` at
`e948141a` with `ops/bin/suites.sh`. Re-measure before working a family:
the numbers move as the sweep lands, and a stale count read as current is
the failure this record exists to prevent.

```
Failing modules by family, ops/bin/suites.sh on lane/session-20260916-g
at e948141a, ten commits over origin/dev 46639344 (which has not moved).
ruff: All checks passed. ops/testkit's own suite: OK, 40 tests.
Total failing rows: 1339 across 95 modules.
Every row is a fixture that runs a host tool the world no longer carries.
The remedy is in the refusal each one now gets: World(ambient_tools=(...))
for a real host tool, or world.tools.plant for a fake. Nothing here needs
a decision; it needs the declaration each fixture always owed.

== conductor  (438 failing rows, 23 modules)
      95  test_dispatch_wrapper
      56  test_ladder_lever
      46  test_onboard_lever
      41  test_branch_census
      37  test_land_lever
      30  test_laneconf
      22  test_ladder_refusals
      16  test_ladder_stage_set
      15  test_ladder_stops
      14  test_ladder_skeptic_envelope
      13  test_ladder_lever_inputs
      13  test_ladder_lever_undisposed
      13  test_ledger
       6  test_gate_runner
       5  test_ladder_skeptic_custody
       3  test_dispatch_wrapper_answers
       3  test_dispatch_wrapper_help
       3  test_probes
       3  test_watchdog_launcher_census
       1  test_dispatch_wrapper_ld16
       1  test_instrument
       1  test_ladder_check_envelope_verb
       1  test_skills_registry

== devlane/dispatch  (437 failing rows, 33 modules)
      44  test_launch_refusals
      34  test_launch_envelope_by_construction
      33  test_launch_codex_read_containment
      33  test_launch_correction_gate
      27  test_launch_watch
      24  test_agy_dispatch
      24  test_launch_collect_committed_recovery
      22  test_launch_isolation
      21  test_launch_envelope_u10_fix
      16  test_launch_record
      16  test_launch_worker_mcp
      15  test_launch_collect
      15  test_launch_job_caps
      15  test_launch_snapshot
      12  test_launch_graft
      10  test_launch_harness_fixes
      10  test_launch_prompt_feed_findings
      10  test_launch_u10b
       8  test_launch_lane_conf
       8  test_launch_verbs
       6  test_launch_read_role_tmp
       6  test_launch_skeptic_write
       4  test_agy_native_transcript
       4  test_launch_record_copy
       3  test_launch_brief_schema
       3  test_launch_credential_age
       3  test_launch_envelope_parse
       2  test_agy_live_step_update_cap
       2  test_launch_claude_readable
       2  test_launch_input_visibility
       2  test_launch_record_identity
       2  test_launch_review_p1_findings
       1  test_launch_grok_head_commit

== devlane/fixtures  (95 failing rows, 6 modules)
      32  test_fixture_lever
      17  test_fixture_grade
      13  test_rust_crate_app
      12  test_python_service_app
      12  test_symfony_app_app
       9  test_python_tooling_app

== devlane/harness  (47 failing rows, 4 modules)
      28  test_graft_query
      15  test_graft_bridge_fake
       2  test_graft_config
       2  test_graft_install

== devlane/hooks  (173 failing rows, 14 modules)
      47  test_hooks
      25  test_engine
      20  test_pr_feedback
      17  test_commit_msg_gate
      12  test_ruff_after_edit
      11  test_context_stream
      10  test_test_guard_hook
       9  test_context_precheck_selected_repo
       9  test_trunk_forward
       6  test_context_precheck_scope
       3  test_bdd_traceability
       2  test_context_precheck
       1  test_conductor_enforce
       1  test_matrix

== devlane/task  (38 failing rows, 3 modules)
      34  test_fileset
       3  test_run
       1  test_verify

Remedied on `lane/session-20260916-sweep`: the three modules request
`World(host_path=False)` (with a compatibility fallback for this branch's
pre-strict kit) and use registry wrappers for `git`, `sh`, and `sleep`, so
every external-tool call is logged. The `run` family also wraps `tee`.
Re-measured from the repository root
after the edit: the three named discover commands ran 34, 45, and 26 tests
respectively and each exited 0. The strict ref `e948141a` was not present in
this snapshot's object database, so its old 34/3/1 split was not re-run here.

== devlane/telemetry  (75 failing rows, 8 modules)
      20  test_worth_dispatches
      14  test_worth_compare
      13  test_worth
       9  test_worth_session_row
       8  test_bdd_worth
       5  test_usage
       5  test_worth_claude_dir
       1  test_wiring

== devlane/workflow  (30 failing rows, 3 modules)
      15  test_term_wall
      13  test_term_wall_archives
       2  test_suites_ruff

== pr-overview  (6 failing rows, 1 modules)
       6  test_collect_rows
```
