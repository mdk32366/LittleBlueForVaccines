# Mutation results (as of @0.4: no mutation run at @0.4, since no code or test changed; M28 re-run at @0.3; all other rows carried from the @0.2 run on byte-identical code)

Summary: Kaylee's 46 code mutants **46/46 killed** (@0.0: 17/46); extra port variants where her guard now sits in two places (M39b, M40b, M44b, M46b) **4/4**; her data set **6/6 killed** (@0.0: 1/6); her @0.1-review mutant K-N33b **1/1**; our mutants (N-series incl. @0.2 N45–N60, D07–D09) **63/63 killed**. No survivors.

| id | origin | file | guard | status | killed by (every named failing test) |
|---|---|---|---|---|---|
| M01 | K | evalcore.py | strict: {Sn} slots == span keys | KILLED | test_strict_rejects |
| M02 | K | evalcore.py | strict: refusal has spans {} | KILLED | test_strict_rejects |
| M03 | K | evalcore.py | strict: exactly {answer, spans} | KILLED | test_strict_rejects |
| M04 | K | evalcore.py | strict: span keys S<n> | KILLED | test_strict_rejects |
| M05 | K | evalcore.py | strict: anchor/text are str | KILLED | test_strict_rejects |
| M06 | K | evalcore.py | lenient: fence strip. @0.1 port: the @0.0 fence-strip regex was dead code (equivalent mutant) and was removed; the guard it stood for, recovering JSON after a code fence or prose, now lives in parse_lenient's brace scan, so the mutant disables skipping to the first { | KILLED | test_lenient_recovers_fenced_and_prose |
| M07 | K | evalcore.py | is_refusal: case/space/period tolerant | KILLED | test_is_refusal_tolerance |
| M08 | K | evalcore.py | norm: 1,000 -> 1000 | KILLED | test_norm_and_span_texts |
| M09 | K | evalcore.py | validator: D-0023 slot exemption | KILLED | test_validator_rules |
| M10 | K | evalcore.py | denylist: plural commercial terms | KILLED | test_validator_rules |
| M11 | K | evalcore.py | resolve: whole-leaf DOC#* anchors | KILLED | test_gold_reads; test_resolve_whole_leaf |
| M12 | K | score.py | cf new-value metric | KILLED | test_old_value_on_counterfactual_memorises |
| M13 | K | score.py | verdict MEMORISES rule | KILLED | test_every_review_stub_lands_on_expected_outcome; test_honest_false_alarm_small_sim; test_memorises_needs_old_over_placebo; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises |
| M14 | K | score.py | P-SH bar margin | KILLED | test_at_only_inconclusive_wording; test_each_probe_drop_bar_fails_alone; test_every_review_stub_lands_on_expected_outcome; test_honest_false_alarm_small_sim |
| M15 | K | score.py | P-RN drop bar margin | KILLED | test_each_probe_drop_bar_fails_alone |
| M16 | K | score.py | P-RN-LEAK name-leak bar | KILLED | test_every_review_stub_lands_on_expected_outcome; test_missing_kind_is_fail_not_pass; test_rn_leak_one_row |
| M17 | K | score.py | P-PP-REF over-refusal bar | KILLED | test_pp_extra_refusal_bar |
| M18 | K | score.py | G-F hard gate | KILLED | test_gf_boundary_one_invalid_is_degenerate; test_invalid_is_degenerate |
| M19 | K | score.py | G-F boundary (all vs half), bar and DEGENERATE detector | KILLED | test_every_review_stub_lands_on_expected_outcome; test_gf_boundary_one_invalid_is_degenerate |
| M20 | K | score.py | G-G denylist bar | KILLED | test_gg_one_hit_fails_gate_not_verdict |
| M21 | K | score.py | ar old value returned | KILLED | test_honest_false_alarm_small_sim; test_non_refusal_on_anchor_removal_memorises |
| M22 | K | score.py | old-value evidence (the @0.1 replacement of the P-CF old-value bar) | KILLED | test_every_review_stub_lands_on_expected_outcome; test_honest_false_alarm_small_sim; test_memorises_needs_old_over_placebo; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises |
| M23 | K | eval.py | exit 6 rows/scripts vs manifest | KILLED | test_tampered_inputs_exit_6 |
| M24 | K | eval.py | exit 6 covers eval.py + evalcore.py | KILLED | test_every_review_stub_lands_on_expected_outcome; test_gold_reads; test_invalid_is_degenerate; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises; test_report_written; test_t_vs_s_paired; test_wrong_span; test_eval_sha256_complete_and_verifies; test_run_json_identity_and_content_hash; test_tampered_inputs_exit_6; test_evalcore_change_is_explicit_drift_never_silent; test_report_states_false_alarm_conditions; test_score_py_fix_after_run_scores_with_new_score_pin_and_records_it; test_unrelated_stage_change_after_run_still_scores; test_wrong_run_pin_or_tampered_recorded_manifest_refused_15; test_duplicate_refused; test_garbage_and_foreign_lines_refused; test_missing_probe_kind_refused; test_partial_refused; test_rows_sha_vs_run_json; test_run_json_gates; test_self_check_pin_and_tamper; test_smoke_scoring_never_a_verdict; test_tampered_prediction_refused_by_provenance |
| M25 | K | eval.py | exit 6 covers fewshot.json | KILLED | test_t_vs_s_paired; test_tampered_inputs_exit_6 |
| M26 | K | eval.py | exit 7 config change | KILLED | test_lock_released_on_every_exit_path; test_partial_run_different_config_refused; test_resume_with_changed_adapter_bytes_refused |
| M27 | K | eval.py | resume skips done batches | KILLED | test_mistyped_launch_against_stopped_run_writes_nothing; test_resume_same_config_no_duplicates; test_stale_lock_taken_over_and_recorded; test_torn_last_line_with_newline_repaired_not_fatal; test_torn_tail_and_partial_batch_redone |
| M28 | K | eval.py | exit 7 predictions without run json | KILLED | test_orphan_in_readonly_out_dir_refused_7; test_orphan_with_fresh_torn_lock_refused_at_once; test_orphan_with_stale_lock_same_inode_and_mtime; test_orphan_with_torn_lock_refused_7_lock_bytes_untouched |
| M29 | K | eval.py | EVAL.SHA256 covers predictions | KILLED | test_every_review_stub_lands_on_expected_outcome; test_gold_reads; test_invalid_is_degenerate; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises; test_report_written; test_t_vs_s_paired; test_wrong_span; test_eval_sha256_complete_and_verifies; test_run_json_identity_and_content_hash; test_evalcore_change_is_explicit_drift_never_silent; test_report_states_false_alarm_conditions; test_score_py_fix_after_run_scores_with_new_score_pin_and_records_it; test_unrelated_stage_change_after_run_still_scores; test_wrong_run_pin_or_tampered_recorded_manifest_refused_15; test_duplicate_refused; test_garbage_and_foreign_lines_refused; test_missing_probe_kind_refused; test_partial_refused; test_rows_sha_vs_run_json; test_run_json_gates; test_self_check_pin_and_tamper; test_smoke_scoring_never_a_verdict; test_tampered_prediction_refused_by_provenance |
| M30 | K | eval.py | EVAL.SHA256 written non-empty | KILLED | test_every_review_stub_lands_on_expected_outcome; test_gold_reads; test_invalid_is_degenerate; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises; test_report_written; test_t_vs_s_paired; test_wrong_span; test_bad_pin_exit_6_then_clean_start_and_numbered_aborts; test_eval_sha256_complete_and_verifies; test_run_json_identity_and_content_hash; test_evalcore_change_is_explicit_drift_never_silent; test_report_states_false_alarm_conditions; test_score_py_fix_after_run_scores_with_new_score_pin_and_records_it; test_unrelated_stage_change_after_run_still_scores; test_wrong_run_pin_or_tampered_recorded_manifest_refused_15; test_duplicate_refused; test_garbage_and_foreign_lines_refused; test_missing_probe_kind_refused; test_partial_refused; test_rows_sha_vs_run_json; test_run_json_gates; test_self_check_pin_and_tamper; test_smoke_scoring_never_a_verdict; test_tampered_prediction_refused_by_provenance |
| M31 | K | eval.py | abort writes the ABORT marker content | KILLED | test_bad_invocation_exit_8; test_bad_pin_exit_6_then_clean_start_and_numbered_aborts; test_tampered_inputs_exit_6; test_unhandled_crash_exit_11_with_cause |
| M32b | K | eval.py | greedy decoding overrides (GPU path) | KILLED | test_exit_13_unverified_transformers_unless_pinned; test_all_3569_prompt_ids_match_hf; test_exit_10_low_free_and_configurable_floor; test_exit_10_no_cuda_then_clean_rerun; test_exit_11_unhandled_and_interrupt; test_exit_3_peak_then_resume; test_exit_5_oom_at_load_then_clean_rerun; test_exit_5_oom_in_generate_then_resume; test_fewshot_branch; test_kill_torn_resume_same_batches_same_text; test_ok_greedy_merged_config_recorded; test_preflight_records_merged_config_and_free_memory; test_resume_under_other_library_versions_refused_nothing_written; test_resume_with_different_model_refused_nothing_written; test_smoke_replay_and_smoke_score; test_special_tokens_stay_visible |
| M33 | K | eval.py | exit 3 peak | KILLED | test_exit_3_peak_then_resume |
| M34 | K | eval.py | exit 4 token count | KILLED | test_exit_4_ids_sha_and_count |
| M35 | K | eval.py | exit 9 prompt too long | KILLED | test_exit_9_prompt_too_long |
| M36 | K | eval.py | exit 10 GPU not free | KILLED | test_exit_10_low_free_and_configurable_floor |
| M37b | K | eval.py | resume reads done ids | KILLED | test_corrupt_middle_line_and_duplicates_exit_12; test_mistyped_launch_against_stopped_run_writes_nothing; test_resume_same_config_no_duplicates; test_stale_lock_taken_over_and_recorded; test_torn_last_line_with_newline_repaired_not_fatal; test_torn_tail_and_partial_batch_redone |
| M38 | K | score.py | run json 'complete' flag (consumer side; eval.py sets it only at finish) | KILLED | test_run_json_gates |
| M39 | K | probecheck.py | builder: pp templates 0 shared 4-grams with corpus | KILLED | test_check_functions_negative |
| M39b | K | probecheck.py | rows: pp question 0 shared 4-grams with corpus | KILLED | test_probe_checks_catch_broken_rows |
| M40 | K | build_eval_rows.py | builder: cf new value absent from original prompt | KILLED | test_builder_is_deterministic |
| M40b | K | probecheck.py | rows: cf new value appears exactly once | KILLED | test_probe_checks_catch_broken_rows |
| M41 | K | probecheck.py | builder: 0 system overlap | KILLED | test_builder_refuses_bad_corpus_and_writes_nothing; test_check_functions_negative |
| M42 | K | probecheck.py | builder: test qa sha pin | KILLED | test_builder_refuses_bad_corpus_and_writes_nothing; test_check_functions_negative |
| M43 | K | probecheck.py | rows: rn real name/brands absent | KILLED | test_probe_checks_catch_broken_rows |
| M44 | K | build_eval_rows.py | builder: ar gold text absent after removal | KILLED | test_builder_is_deterministic |
| M44b | K | probecheck.py | rows: ar old value absent | KILLED | test_probe_checks_catch_broken_rows |
| M45 | K | eval.py | ABORT markers numbered, never overwritten (@0.0 M45 'resume clears ABORT.json' no longer exists by design) | KILLED | test_bad_pin_exit_6_then_clean_start_and_numbered_aborts |
| M46 | K | score.py | score refuses missing ids (@0.1 replacement of the INCOMPLETE verdict) | KILLED | test_every_review_stub_lands_on_expected_outcome; test_missing_probe_kind_refused; test_partial_refused; test_smoke_scoring_never_a_verdict |
| M46b | K | score.py | missing probe data is FAIL, not PASS | KILLED | test_missing_kind_is_fail_not_pass |
| N01 | new | score.py | cf placebo hits counted | KILLED | test_every_review_stub_lands_on_expected_outcome; test_honest_false_alarm_small_sim; test_memorises_needs_old_over_placebo |
| N02 | new | score.py | ar placebo hits counted | KILLED | test_every_review_stub_lands_on_expected_outcome; test_honest_false_alarm_small_sim |
| N03 | new | evalstats.py | Wilson z = 1.96 | KILLED | test_wilson_known |
| N04 | new | evalstats.py | exact one-sided McNemar | KILLED | test_honest_false_alarm_small_sim; test_binomial_and_mcnemar_exact |
| N05 | new | evalstats.py | test floor calibrated to alpha | KILLED | test_honest_false_alarm_small_sim; test_floor_kmin_is_calibrated |
| N06 | new | score.py | Bonferroni split of the probe alpha | KILLED | test_honest_false_alarm_small_sim |
| N07 | new | score.py | probe bar needs significance, not just drop | KILLED | test_honest_false_alarm_small_sim |
| N08 | new | score.py | DEGENERATE: always-refuse | KILLED | test_degenerate_detectors |
| N09 | new | score.py | DEGENERATE: format-only (ungrounded spans) | KILLED | test_degenerate_detectors |
| N10 | new | score.py | DEGENERATE: copy-clause | KILLED | test_degenerate_detectors |
| N11 | new | score.py | DEGENERATE: length-gamer | KILLED | test_degenerate_detectors |
| N12 | new | score.py | DEGENERATE: reads nothing | KILLED | test_degenerate_detectors |
| N13 | new | score.py | READS requires every bar | KILLED | test_at_only_inconclusive_wording; test_each_probe_drop_bar_fails_alone; test_every_review_stub_lands_on_expected_outcome; test_floor_boundary_exact; test_honest_45_not_memorises; test_honest_false_alarm_small_sim; test_missing_kind_is_fail_not_pass; test_pp_extra_refusal_bar; test_rn_leak_one_row |
| N14 | new | score.py | score refuses duplicate ids | KILLED | test_every_review_stub_lands_on_expected_outcome; test_duplicate_refused |
| N15 | new | score.py | score refuses foreign ids | KILLED | test_garbage_and_foreign_lines_refused |
| N16 | new | score.py | score: primary carries the expected adapter | KILLED | test_run_json_gates |
| N17 | new | score.py | score verifies EVAL.SHA256 | KILLED | test_tampered_prediction_refused_by_provenance |
| N18 | new | score.py | score verifies content hash | KILLED | test_tampered_prediction_refused_by_provenance |
| N19 | new | score.py | score self-check vs manifest | KILLED | test_self_check_pin_and_tamper |
| N20 | new | score.py | score: run rows sha == --rows | KILLED | test_rows_sha_vs_run_json; test_run_json_gates |
| N21 | new | eval.py | torn last line repaired, not fatal | KILLED | test_torn_last_line_with_newline_repaired_not_fatal |
| N22 | new | eval.py | partial batch redone whole | KILLED | test_torn_last_line_with_newline_repaired_not_fatal; test_torn_tail_and_partial_batch_redone |
| N23 | new | eval.py | exit 12 duplicate id | KILLED | test_corrupt_middle_line_and_duplicates_exit_12 |
| N24 | new | eval.py | exit 7 completed dir, nothing written | KILLED | test_completed_dir_refused_nothing_written; test_lock_released_on_every_exit_path |
| N25 | new | eval.py | exit 7 unknown files | KILLED | test_preds_without_run_json_and_unknown_files_refused |
| N26 | new | eval.py | exit 13 versions | KILLED | test_exit_13_versions_differ_from_train_json |
| N27 | new | eval.py | exit 13 merged config not greedy | KILLED | test_exit_13_merged_config_not_greedy |
| N28 | new | eval.py | L1 special tokens visible | KILLED | test_special_tokens_stay_visible |
| N29 | new | eval.py | abort marks run json aborted | KILLED | test_corrupt_middle_line_and_duplicates_exit_12; test_unhandled_crash_exit_11_with_cause |
| N30 | new | eval.py | KeyboardInterrupt leaves ABORT (exit 11) | KILLED | test_exit_11_unhandled_and_interrupt |
| N31 | new | eval.py | exit 10 default floor | KILLED | test_exit_10_low_free_and_configurable_floor; test_preflight_records_merged_config_and_free_memory |
| N32 | new | eval.py | exit 7 resume with different library versions | KILLED | test_resume_under_other_library_versions_refused_nothing_written |
| N33 | new | eval.py | token check covers every row | KILLED | test_all_3569_prompt_ids_match_hf; test_exit_10_low_free_and_configurable_floor; test_exit_10_no_cuda_then_clean_rerun; test_exit_11_unhandled_and_interrupt; test_exit_13_merged_config_not_greedy; test_exit_13_unverified_transformers_unless_pinned; test_exit_3_peak_then_resume; test_exit_4_ids_sha_and_count; test_exit_4_row_outside_limit_plan; test_exit_5_oom_at_load_then_clean_rerun; test_exit_5_oom_in_generate_then_resume; test_exit_9_prompt_too_long; test_fewshot_branch; test_kill_torn_resume_same_batches_same_text; test_ok_greedy_merged_config_recorded; test_preflight_records_merged_config_and_free_memory; test_resume_under_other_library_versions_refused_nothing_written; test_resume_with_different_model_refused_nothing_written; test_smoke_replay_and_smoke_score; test_special_tokens_stay_visible |
| N33b | K | eval.py | token check covers rows outside the --limit plan (Kaylee K-N33b, review N3) | KILLED | test_exit_4_row_outside_limit_plan |
| N34 | new | evalcore.py | smoke = whole FULL batches | KILLED | test_resume_same_config_no_duplicates; test_smoke_plan_is_whole_full_run_batches; test_torn_last_line_with_newline_repaired_not_fatal; test_torn_tail_and_partial_batch_redone; test_smoke_scoring_never_a_verdict |
| N35 | new | probecheck.py | rows: cf placebo absent from prompt | KILLED | test_probe_checks_catch_broken_rows |
| N36 | new | probecheck.py | rows: rn fake name present | KILLED | test_probe_checks_catch_broken_rows |
| N37 | new | probecheck.py | fake names absent from train corpus | KILLED | test_builder_refuses_bad_corpus_and_writes_nothing; test_check_functions_negative |
| N38 | new | eval.py | replay_b1 smoke only (exit 8) | KILLED | test_bad_invocation_exit_8 |
| N39 | new | score.py | promotable needs READS | KILLED | test_honest_45_not_memorises |
| N40 | new | score.py | smoke scorer refuses a full run | KILLED | test_smoke_scoring_never_a_verdict |
| N41 | new | eval.py | ruling 8: unverified transformers stops unless pinned | KILLED | test_exit_13_unverified_transformers_unless_pinned |
| N42 | new | eval.py | ruling 8: pin must equal the installed transformers | KILLED | test_exit_13_unverified_transformers_unless_pinned |
| N43 | new | eval.py | ruling 8: run stops before model load on unverified transformers | KILLED | test_exit_13_unverified_transformers_unless_pinned |
| N44 | new | eval.py | ruling 8: preflight prints merged config, then exits 13 on unverified transformers | KILLED | test_exit_13_unverified_transformers_unless_pinned |
| N45 | new | score.py | N1: run carries the pinned run manifest | KILLED | test_wrong_run_pin_or_tampered_recorded_manifest_refused_15 |
| N46 | new | score.py | N1: recorded run manifest text hashes to the recorded sha | KILLED | test_wrong_run_pin_or_tampered_recorded_manifest_refused_15 |
| N47 | new | score.py | N1: scorer drift is never silent | KILLED | test_evalcore_change_is_explicit_drift_never_silent |
| N48 | new | score.py | N1: run inputs == the run manifest it recorded | KILLED | test_wrong_run_pin_or_tampered_recorded_manifest_refused_15 |
| N49 | new | score.py | N1: a run without a recorded run manifest is refused | KILLED | test_wrong_run_pin_or_tampered_recorded_manifest_refused_15 |
| N50 | new | eval.py | N1: the run records its run manifest | KILLED | test_every_review_stub_lands_on_expected_outcome; test_gold_reads; test_invalid_is_degenerate; test_non_refusal_on_anchor_removal_memorises; test_old_value_on_counterfactual_memorises; test_report_written; test_t_vs_s_paired; test_wrong_span; test_eval_sha256_complete_and_verifies; test_run_json_identity_and_content_hash; test_evalcore_change_is_explicit_drift_never_silent; test_report_states_false_alarm_conditions; test_score_py_fix_after_run_scores_with_new_score_pin_and_records_it; test_unrelated_stage_change_after_run_still_scores; test_wrong_run_pin_or_tampered_recorded_manifest_refused_15; test_duplicate_refused; test_garbage_and_foreign_lines_refused; test_missing_probe_kind_refused; test_partial_refused; test_rows_sha_vs_run_json; test_run_json_gates; test_self_check_pin_and_tamper; test_smoke_scoring_never_a_verdict; test_tampered_prediction_refused_by_provenance |
| N51 | new | eval.py | N5: single-runner lock taken | KILLED | test_stale_lock_taken_over_and_recorded; test_concurrent_launches_one_runner; test_launch_against_live_run_refused_7_nothing_written |
| N52 | new | eval.py | N5: live lock holder -> 7 | KILLED | test_concurrent_launches_one_runner; test_launch_against_live_run_refused_7_nothing_written |
| N53 | new | eval.py | N5: no invocation/integrity ABORT in a run dir | KILLED | test_mistyped_launch_against_stopped_run_writes_nothing |
| N54 | new | eval.py | N5: running + live last pid (no lock) -> 7 | KILLED | test_launch_against_live_run_refused_7_nothing_written |
| N55 | new | eval.py | N5: stale lock takeover recorded | KILLED | test_stale_lock_taken_over_and_recorded |
| N56 | new | score.py | N6: A-T-only INCONCLUSIVE wording | KILLED | test_at_only_inconclusive_wording |
| N57 | new | score.py | N6: REPORT states the false-alarm conditions | KILLED | test_report_states_false_alarm_conditions |
| N58 | new | build_eval_rows.py | N4: public brand list applied to the rename | KILLED | test_builder_is_deterministic |
| N60 | new | eval.py | N5: refused launch after a stale-lock takeover leaves the dir byte-identical | KILLED | test_resume_under_other_library_versions_refused_nothing_written; test_resume_with_different_model_refused_nothing_written |
| N59 | new | sim/stub_harness.py | N7: suite never writes STUB-OUTCOMES into the stage | KILLED | test_every_review_stub_lands_on_expected_outcome; tearDownModule |
| D01 | K | eval_rows.jsonl | cf old value put back into the clause text | KILLED | test_probe_rows_well_formed |
| D02 | K | eval_rows.jsonl | rn: real supplier name re-inserted in title case | KILLED | test_probe_rows_well_formed; test_rename_no_independent_real_supplier_brands |
| D03 | K | eval_rows.jsonl | sh: units left in original order (no shuffle) | KILLED | test_probe_rows_well_formed |
| D04 | K | eval_rows.jsonl | pp: question = original + trailing space (no paraphrase) | KILLED | test_probe_rows_well_formed |
| D05 | K | eval_rows.jsonl | ar: gold span text re-added under a different unit id | KILLED | test_probe_rows_well_formed |
| D06 | K | eval_rows.jsonl | ar: expect_refusal kept but gold not REFUSAL | KILLED | test_probe_rows_well_formed |
| D07 | new | eval_rows.jsonl | rn: a renamed brand stem put back (new in @0.1) | KILLED | test_probe_rows_well_formed; test_rename_no_independent_real_supplier_brands |
| D09 | new | eval_rows.jsonl | rn: a real-supplier brand outside the MSA catalog left in (TENIVAC; review N4, new in @0.2) | KILLED | test_probe_rows_well_formed; test_rename_no_independent_real_supplier_brands |
| D08 | new | eval_rows.jsonl | cf: placebo value put into the prompt (new in @0.1) | KILLED | test_probe_rows_well_formed |
