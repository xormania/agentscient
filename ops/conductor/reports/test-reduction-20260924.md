# Test consolidation: owner-selected items 1–3

Measured 2026-09-23T21:05:10.252208+00:00 against dev `a91284eccdc532e63ef8c9de84ee19776e64bf51`. Owner requested items 1–3 in one PR and runtime consolidation separately. Hand grant 1; one producer (Codex), no independent test author or external reviewer was available. Exact model identifier is not exposed in this session.

## Count and scope

| Module | Before | After |
|---|---:|---:|
| `ops/devlane/dispatch/tests/test_record.py` | 96 | 65 |
| `ops/devlane/fixtures/tests/test_python_service_app.py` | 35 | 19 |
| `ops/devlane/fixtures/tests/test_python_tooling_app.py` | 23 | 9 |
| `ops/devlane/fixtures/tests/test_rust_crate_app.py` | 41 | 25 |
| `ops/devlane/fixtures/tests/test_symfony_app_app.py` | 33 | 21 |
| `ops/devlane/telemetry/tests/test_wiring.py` | 82 | 3 |
| Total | 310 | 142 |

168 fewer collected tests; the required-suite baseline of 3,729 becomes 3,561 if unchanged families retain their counts (4.5% overall). This is a focused reduction, not the earlier exploratory 30–40% opportunity estimate. No CI family or gate is removed. No production implementation changes in this PR.

## What remains

- Documentation: three tests execute the actual launch and battery shell blocks, verify the reviewer PID, literal prompt file, stream selection, caps and real breaker CLI, and bounded discovery after reviewer death. Runtime wire behavior stays in breaker tests. Exact explanatory prose, Markdown placement and tests of the old documentation parser are intentionally retired, not claimed as runtime coverage. The two dispatch-directory assertions already live in `test_worth_dispatches.DispatchMeterTests`.
- Fixture apps: shared manifest, copying, proof aggregation and grading suites own generic behavior. All fixture-specific planted-fault probes, clean-neighbour executions, complete ID/kind/severity mappings, copy/suite/dispatch portability, and unavailable-toolchain cases remain. No list of fault executions was shortened.
- Policy: shared match/receipt mechanics are exercised once, and a wrapping spy checks that every actual field/receipt value reaches the expected grammar and qualified field name. Policy shape, required fields, template equality, sorting/uniqueness for both collections, legacy omission and accepted bindings remain integration checks. A 64-character Git-id acceptance case is added. Pattern identity is an explicit coupling assertion; changing a grammar requires updating its binding contract test.

## Verification

- `python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_record.py`: baseline 96 pass; reduced 65 pass.
- `python3 -m unittest discover -s ops/devlane/telemetry/tests -p test_wiring.py`: baseline 82 pass; replacement 3 pass.
- `python3 -m unittest discover -s ops/devlane/telemetry/tests`: 174 pass.
- `PATH="$HOME/.local/bin:$PATH" python3 -m unittest discover -s ops/devlane/fixtures/tests`: 163 tests, pass, 5 skipped for missing Rust/PHP tooling. Shared fixture subset: 71 pass before and after.
- `python3 -m ruff check .`: pass (ruff 0.16.8).
- Full gate remains a CI requirement. This host lacks Rust, PHP, CUE and tmux; local checks are explicitly partial.

## Paired planted faults

For each row, change only the named runtime/doc expression, run the same unittest discovery command above against the old and new suite, then restore the source. All 18 faults are detected before and after; healthy executions pass. These calibration runs are not added to the collected suite.

| Mutation | Before | After |
|---|---|---|
| match accepts non-string | detected | detected |
| match accepts substring | detected | detected |
| weaken digest grammar | detected | detected |
| omit grants validation | detected | detected |
| omit admission validation | detected | detected |
| skip per-job receipts | detected | detected |
| drop receipt sorting | detected | detected |
| drop receipt uniqueness | detected | detected |
| drop template equality | detected | detected |
| drop required-field refusal | detected | detected |
| wrong stream pattern | detected | detected |
| oldest stream selected | detected | detected |
| disabled output cap | detected | detected |
| termination removed | detected | detected |
| invalid battery flag | detected | detected |
| wrong reviewer PID | detected | detected |
| discovery ignores dead reviewer | detected | detected |
| launch binds wrapper PID | detected | detected |

## Fixture retirement map

| Removed case | Retained responsibility |
|---|---|
| `test_python_service_app.PythonServiceExists.test_faults_json_exists` | Shared manifest sweep and retained fixture execution |
| `test_python_service_app.PythonServiceLayout.test_layout_paths_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_service_app.PythonServiceLayout.test_readme_itself_declares_apparatus` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_service_app.PythonServiceLayout.test_readme_names_the_service_and_the_check_command` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_service_app.PythonServiceLayout.test_readme_names_the_install_command` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_service_app.PythonServiceManifest.test_apparatus_paths_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_service_app.PythonServiceManifest.test_manifest_has_six_to_eight_rows_over_six_or_more_kinds` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_service_app.PythonServiceManifest.test_manifest_cites_k1_k2_k4_k5_k6_k7_k9` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_python_service_app.PythonServiceManifest.test_manifest_ids_are_ps_01_to_ps_07` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_python_service_app.PythonServiceManifest.test_readme_carries_one_declaration_per_fault` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_service_app.PythonServiceManifest.test_manifest_sweep_accepts_faults_json` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_service_app.PythonServiceMakeProve.test_make_python_service_into_a_temp_directory_succeeds` | Retained made_app callers exercise this fixture; test_fixture_lever.MakeCopies owns generic copying/trailers |
| `test_python_service_app.PythonServiceMakeProve.test_prove_reports_every_planted_fault_red` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_python_service_app.PythonServiceMakeProve.test_prove_fixed_reports_every_probe_green` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_python_service_app.PythonServiceGrade.test_grade_scores_a_planted_review` | Generic fixture grade classifications |
| `test_python_service_app.PythonServiceGrade.test_grade_scores_independently_found_neighbours_as_false_positives` | Generic fixture grade classifications |
| `test_python_tooling_app.PythonToolingExists.test_faults_json_exists` | Shared manifest sweep and retained fixture execution |
| `test_python_tooling_app.PythonToolingLayout.test_layout_paths_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_tooling_app.PythonToolingLayout.test_readme_itself_declares_apparatus` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_tooling_app.PythonToolingLayout.test_readme_names_the_check_command` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_tooling_app.PythonToolingLayout.test_readme_carries_one_declaration_per_fault` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_python_tooling_app.PythonToolingManifest.test_manifest_has_six_to_eight_rows_over_six_or_more_kinds` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_tooling_app.PythonToolingManifest.test_manifest_cites_k1_k2_k3_k4_k5_k6_k8` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_python_tooling_app.PythonToolingManifest.test_manifest_ids_are_pt_01_to_pt_07` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_python_tooling_app.PythonToolingManifest.test_manifest_sweep_accepts_faults_json` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_python_tooling_app.PythonToolingMakeProve.test_make_python_tooling_into_a_temp_directory_succeeds` | Retained made_app callers exercise this fixture; test_fixture_lever.MakeCopies owns generic copying/trailers |
| `test_python_tooling_app.PythonToolingMakeProve.test_prove_reports_every_planted_fault_red` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_python_tooling_app.PythonToolingMakeProve.test_prove_fixed_reports_every_probe_green` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_python_tooling_app.PythonToolingGrade.test_grade_scores_a_planted_review` | Generic fixture grade classifications |
| `test_python_tooling_app.PythonToolingGrade.test_grade_scores_independently_found_neighbours_as_false_positives` | Generic fixture grade classifications |
| `test_rust_crate_app.RustCrateExists.test_faults_json_exists` | Shared manifest sweep and retained fixture execution |
| `test_rust_crate_app.RustCrateLayout.test_layout_paths_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_rust_crate_app.RustCrateLayout.test_probes_and_fixes_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_rust_crate_app.RustCrateLayout.test_readme_itself_declares_apparatus` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_rust_crate_app.RustCrateLayout.test_readme_names_check_cargo_fetch_and_offline` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_rust_crate_app.RustCrateLayout.test_readme_carries_one_declaration_per_fault` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_rust_crate_app.RustCrateManifest.test_manifest_name_is_rust_crate` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_rust_crate_app.RustCrateManifest.test_manifest_has_seven_rows_over_seven_kinds` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_rust_crate_app.RustCrateManifest.test_manifest_cites_k1_to_k6_and_k9` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_rust_crate_app.RustCrateManifest.test_manifest_ids_are_rc_01_to_rc_07` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_rust_crate_app.RustCrateManifest.test_manifest_sweep_accepts_faults_json` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_rust_crate_app.RustCrateMakeProve.test_make_rust_crate_into_a_temp_directory_succeeds` | Retained made_app callers exercise this fixture; test_fixture_lever.MakeCopies owns generic copying/trailers |
| `test_rust_crate_app.RustCrateMakeProve.test_prove_reports_every_planted_fault_red_when_cargo_is_ready` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_rust_crate_app.RustCrateMakeProve.test_prove_fixed_reports_every_probe_green_when_cargo_is_ready` | The same module: each_planted_fault_is_proved_by_its_own_probe; test_fixture_lever.ProveColours owns aggregate reporting |
| `test_rust_crate_app.RustCrateGrade.test_grade_scores_a_planted_review` | Generic fixture grade classifications |
| `test_rust_crate_app.RustCrateGrade.test_grade_scores_a_false_positive_on_a_neighbour` | Generic fixture grade classifications |
| `test_symfony_app_app.SymfonyAppExists.test_faults_json_exists` | Shared manifest sweep and retained fixture execution |
| `test_symfony_app_app.SymfonyAppLayout.test_layout_paths_exist` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_symfony_app_app.SymfonyAppLayout.test_readme_itself_declares_apparatus` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_symfony_app_app.SymfonyAppLayout.test_readme_names_check_install_and_absent_fix` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_symfony_app_app.SymfonyAppLayout.test_readme_carries_one_declaration_per_fault` | Shared manifest sweep verifies declared quotation spans; command behavior is exercised by retained fixture tests. Exact prose is intentionally retired. |
| `test_symfony_app_app.SymfonyAppManifest.test_manifest_has_six_to_eight_rows_over_six_or_more_kinds` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_symfony_app_app.SymfonyAppManifest.test_manifest_cites_k1_to_k6_and_k8` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_symfony_app_app.SymfonyAppManifest.test_manifest_ids_are_sa_01_to_sa_07` | The same module: complete per-ID kind/visibility/severity mapping and retained independent fault probes |
| `test_symfony_app_app.SymfonyAppManifest.test_manifest_sweep_accepts_faults_json` | test_fixture_manifests.ManifestSweep.test_every_found_manifest_validates plus retained make/probe/check cases |
| `test_symfony_app_app.SymfonyAppMakeProve.test_make_symfony_app_into_a_temp_directory_succeeds` | Retained made_app callers exercise this fixture; test_fixture_lever.MakeCopies owns generic copying/trailers |
| `test_symfony_app_app.SymfonyAppGrade.test_grade_scores_a_planted_review` | Generic fixture grade classifications |
| `test_symfony_app_app.SymfonyAppGrade.test_grade_scores_independently_found_neighbours_as_false_positives` | Generic fixture grade classifications |

## Policy retirement map

The following old cases are superseded by `PolicyPrimitives` and `BriefPolicyBindingShape.test_all_policy_fields_use_the_shared_contracts`, or duplicate a retained composition case. They were deleted rather than hidden in a parametrized execution of the same full-record matrix.

- `BriefPolicyBindingShape.test_a_complete_valid_binding_validates`
- `BriefPolicyBindingShape.test_a_list_policy_is_refused`
- `BriefPolicyBindingShape.test_a_syntactically_valid_synthetic_profile_validates_without_membership`
- `BriefPolicyBindingShape.test_abbreviated_ref_is_refused`
- `BriefPolicyBindingShape.test_admission_missing_record_is_refused`
- `BriefPolicyBindingShape.test_admission_missing_sha256_is_refused`
- `BriefPolicyBindingShape.test_admission_record_missing_the_D_prefix_is_refused`
- `BriefPolicyBindingShape.test_admission_record_outside_the_decision_id_pattern_is_refused`
- `BriefPolicyBindingShape.test_admission_sha256_uppercase_is_refused`
- `BriefPolicyBindingShape.test_admission_that_is_not_an_object_is_refused`
- `BriefPolicyBindingShape.test_an_empty_object_policy_is_refused`
- `BriefPolicyBindingShape.test_empty_admission_record_is_refused`
- `BriefPolicyBindingShape.test_empty_ref_is_refused`
- `BriefPolicyBindingShape.test_maintenance_empty_object_is_refused`
- `BriefPolicyBindingShape.test_non_hex_ref_is_refused`
- `BriefPolicyBindingShape.test_non_string_admission_record_is_refused`
- `BriefPolicyBindingShape.test_non_string_grants_sha256_is_refused`
- `BriefPolicyBindingShape.test_non_string_path_is_refused`
- `BriefPolicyBindingShape.test_non_string_policy_sha256_is_refused`
- `BriefPolicyBindingShape.test_non_string_profile_is_refused`
- `BriefPolicyBindingShape.test_non_string_ref_is_refused`
- `BriefPolicyBindingShape.test_non_string_schema_is_refused`
- `BriefPolicyBindingShape.test_null_maintenance_validates_when_no_protected_writes_are_requested`
- `BriefPolicyBindingShape.test_per_job_decision_id_outside_the_pattern_is_refused`
- `BriefPolicyBindingShape.test_per_job_item_missing_record_is_refused`
- `BriefPolicyBindingShape.test_per_job_item_missing_sha256_is_refused`
- `BriefPolicyBindingShape.test_per_job_item_uppercase_digest_is_refused`
- `BriefPolicyBindingShape.test_profile_outside_the_specified_syntax_is_refused`
- `BriefPolicyBindingShape.test_short_grants_sha256_is_refused`
- `BriefPolicyBindingShape.test_short_policy_sha256_is_refused`
- `BriefPolicyBindingShape.test_short_template_sha256_is_refused`
- `BriefPolicyBindingShape.test_standing_decision_id_outside_the_pattern_is_refused`
- `BriefPolicyBindingShape.test_standing_item_missing_record_is_refused`
- `BriefPolicyBindingShape.test_standing_item_missing_sha256_is_refused`
- `BriefPolicyBindingShape.test_standing_item_uppercase_digest_is_refused`
- `BriefPolicyBindingShape.test_uppercase_grants_sha256_is_refused`
- `BriefPolicyBindingShape.test_uppercase_policy_sha256_is_refused`
- `BriefPolicyBindingShape.test_uppercase_ref_is_refused`
- `BriefPolicyBindingShape.test_uppercase_template_sha256_is_refused`
