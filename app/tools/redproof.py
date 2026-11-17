#!/usr/bin/env python3
"""Red-proof: one deliberate defect per run (tests/conftest.py REDPROOF=...), running the guard's own test file(s);
each must go red. Then the full suite with no mutation must be green (control). Every run passes pytest-timeout's
per-test cap (v0.2-h1, PR 14 review N2), so a hang fails in minutes, not at the CI step limit."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable  # clean clone / CI: current interpreter
TIMEOUT = ["--timeout", os.environ.get("REDPROOF_TEST_TIMEOUT", "180")]  # pytest-timeout (requirements.txt)
EXPECT = {  # mutation: (files to run, tests that must fail)
    "reconcile": (["test_t0001_reconcile.py"], ["test_reconcile_synthetic_file", "test_returns_netted_and_reported"]),
    "ratio": (["test_t0002_ratio.py"], ["test_rule", "test_fixture_cases"]),
    "switch": (["test_t0003_switching.py"], ["test_noise_does_not_flag", "test_flag_rate_synthetic_under_half"]),
    "validator": (["test_t0004_validator.py"], ["test_t0004_trips", "test_t0013_trips"]),
    "fallback": (["test_t0005_fallback.py"], ["test_unreachable_falls_back", "test_timeout_falls_back",
                                               "test_rejected_twice_falls_back"]),
    "onepage": (["test_t0006_onepage.py"], ["test_all_180_one_page", "test_pdfinfo_agrees"]),
    "label": (["test_t0008_label.py"], ["test_benchmark_facts_labelled", "test_footer_shows_synthetic",
                                        "test_footer_shows_national"]),
    "name": (["test_t0035_name.py"], ["test_constant", "test_page_title_and_header", "test_pdf_header"]),
    "isolation": (["test_t0036_contracts.py"], ["test_free_text_isolated"]),  # example-question path is also doc_id-pinned (F-0011)
    "expired": (["test_t0038_expired.py"], ["test_flag_on_lookup", "test_rule_edges", "test_qa_citation_flagged",
                                            "test_pdf_snapshot_marked_and_one_page"]),
    "expired_le": (["test_t0038_expired.py"], ["test_file_count_exactly_19_and_edge_systems_live", "test_rule_edges"]),
    "noautorenew": (["test_t0039_autorenew.py", "test_t0040_brief_contracts.py"], ["test_rule_unit_cases", "test_rule_ignores_clause_wording",
                                                 "test_split_10_9_schema_v1", "test_status_column_and_citations_use_marker",
                                                 "test_brief_tab_markers"]),
    "nosamesection": (["test_t0039_autorenew.py"], ["test_rule_unit_cases"]),
    "schema_autorenew": (["test_t0041_autorenew_schema.py"], ["test_auto_renew_present_on_every_msa",
                                                              "test_auto_renew_is_bool_in_term_section"]),
    "briefmarker": (["test_t0040_brief_contracts.py"], ["test_brief_tab_markers"]),
    "bench": (["test_t0037_benchmark.py"], ["test_national_mode", "test_missing_national_falls_back"]),
    "trainguard": (["test_t0066_train_guard.py"], ["test_accepts_national_only_by_recorded_sha",
                                                    "test_still_refuses_visits_and_other_files",
                                                    "test_refuses_non_synthetic_record", "test_scan_flags_planted_reference"]),
    "guard_open": (["test_t0066_train_guard.py"], ["test_accepts_national_only_by_recorded_sha",
                                                    "test_still_refuses_visits_and_other_files"]),
    # v0.2-a client metrics
    "kr_abcwy": (["test_t0042_client_formulas.py"], ["test_ratios_hand_computed", "test_national_file_pins",
                                                     "test_syncp000025_pins"]),
    "kr_swap": (["test_t0042_client_formulas.py"], ["test_ratios_hand_computed", "test_national_file_pins",
                                                    "test_syncp000025_pins"]),
    "invent": (["test_t0043_availability.py"], ["test_not_available_never_a_number"]),  # NOT AVAILABLE -> a number
    "ratio_neg": (["test_t0044_ratio_guards.py"], ["test_rule_unit_cases", "test_fixture_edges", "test_real_file_guards"]),
    "a1_excl": (["test_t0042_client_formulas.py", "test_t0044_ratio_guards.py"], ["test_attributes_hand_computed",
                                                                               "test_a1_state_share_bounded"]),
    "tok_wide": (["test_t0053_validator_tokens.py"], ["test_rejects_f0_f15_and_above"]),
    "tp_digit": (["test_t0045_talking_points.py"], ["test_every_point_passes_guardrails"]),
    "tp_inject": (["test_t0045_talking_points.py"], ["test_numbers_trace_to_facts"]),
    "tp_select": (["test_t0045_talking_points.py"], ["test_select_rule_unit_cases"]),
    "tp_na": (["test_t0045_talking_points.py"], ["test_status_and_not_available_tokens_rejected"]),
    "payload_fields": (["test_t0045_talking_points.py"], ["test_payload_fields"]),
    "tabs": (["test_t0052_ui_tabs.py"], ["test_tabs_table_and_talking_points_render"]),
    "r4_def": (["test_t0055_r4_hepb_ped.py"], ["test_fixture_hand_value", "test_national_pin"]),
    "r6_proxy": (["test_t0056_r6_full_rsv.py"], ["test_fixture_counts_every_rsv_product", "test_national_pin_and_registry"]),
    "obgyn_spec": (["test_t0057_obgyn_tdap.py"], ["test_fixture_hand_values", "test_national_pins"]),
    "babies_swap": (["test_t0058_babies_ratio.py"], ["test_fixture_hand_values", "test_national_pin_and_levels"]),
    # v0.2-d visit store + FAKE Salesforce payload record (no send)
    "pay_drop": (["test_t0047_payload.py"], ["test_payload_validates_against_schema"]),
    "pay_nofake": (["test_t0047_payload.py"], ["test_payload_carries_fake_marker"]),
    "schema_lax": (["test_t0047_payload.py"], ["test_bad_payload_rejected"]),
    "pay_none_str": (["test_t0047_payload.py"], ["test_provider_values_numbers_and_null"]),
    "hint": (["test_t0047_payload.py"], ["test_mentioned_hint"]),
    "store_nopayload": (["test_t0048_visit_store.py"], ["test_save_writes_payload_row"]),
    "store_overwrite": (["test_t0048_visit_store.py"], ["test_resave_versions_not_overwrites"]),
    "store_prefix": (["test_t0048_visit_store.py"], ["test_lookup_exact_key_only"]),
    "store_listall": (["test_t0048_visit_store.py"], ["test_no_list_all_exposed"]),
    "load_lax": (["test_t0048_visit_store.py"], ["test_load_rejects_invalid_file"]),
    "backup_empty": (["test_t0048_visit_store.py"], ["test_backup_subcommand"]),
    "net": (["test_t0049_no_egress.py"], ["test_no_network_imports", "test_round_trip_with_sockets_blocked"]),
    "trainguard_visits": (["test_t0051_visits_not_training.py"], ["test_refuses_visit_records",
                                                                  "test_gen_clean_and_planted_flagged"]),
    "ui_lookup": (["test_t0059_visit_record_ui.py"], ["test_save_then_lookup_round_trip"]),
    "ui_banner": (["test_t0059_visit_record_ui.py"], ["test_banner_and_no_send_action"]),
    "ui_send": (["test_t0059_visit_record_ui.py"], ["test_banner_and_no_send_action"]),
    "ro_save": (["test_t0060_visit_store_unwritable.py"], ["test_typed_save_not_writable"]),
    "ro_save_loaded": (["test_t0060_visit_store_unwritable.py"], ["test_loaded_save_not_writable"]),
    "ro_store_errors": (["test_t0060_visit_store_unwritable.py"], ["test_typed_save_not_writable",
                                                                  "test_loaded_save_not_writable",
                                                                  "test_lookup_store_unreadable"]),
    # GATE 2 path B (schema_v1, spec v1.1 §8)
    "exh_window": (["test_t0064_parity.py"], ["test_exhibit_figures_equal_app_facts", "test_committed_out_equals_inprocess"]),
    "exh_peer_incl": (["test_t0064_parity.py"], ["test_exhibit_figures_equal_app_facts",
                                                 "test_committed_out_equals_inprocess"]),
    "nat_profile_r1": (["test_t0065_national_app.py"], ["test_exhibit_national_ratios_equal_app_profile"]),
    "refusal_text": (["test_t0068_refusals_app.py"], ["test_refusal_rows_use_app_string"]),
    "footer_eats_body": (["test_t0076_footer_marker.py"], ["test_hand_built_order_and_no_body_dropped",
                                                            "test_every_gen_out_doc_keeps_its_body"]),
    "marker_hidden": (["test_t0076_footer_marker.py"], ["test_marker_reaches_qa_answer_and_reports",
                                                         "test_marker_on_qa_and_brief_tabs"]),
    # v0.2-c voice notes (T-0046)
    "stt_nofallback": (["test_t0046_stt.py"], ["test_transcribe_bytes_falls_back"]),
    "stt_none": (["test_t0046_stt.py"], ["test_get_transcriber_config"]),
    "stt_decode": (["test_t0046_stt.py"], ["test_decode_rejects_bad"]),
    "stt_offline": (["test_t0046_stt.py"], ["test_faster_whisper_offline_args"]),
    "stt_persist": (["test_t0046_stt_ui.py"], ["test_no_audio_on_disk_or_in_store"]),
    "stt_prefill": (["test_t0046_stt_ui.py"], ["test_stub_prefills_notes_and_saves", "test_no_audio_on_disk_or_in_store"]),
    "stt_dedupe": (["test_t0046_stt_ui.py"], ["test_one_transcription_per_recording"]),
    "stt_cap": (["test_t0046_stt_ui.py"], ["test_transcript_cut_to_notes_limit"]),
    # PR 6-hot: lookup Company follows the sidebar (T-0061, F-0025); upload limits equal (T-0062, F-0026)
    "lookup_fixed_key": (["test_t0061_lookup_company_follows_sidebar.py"], ["test_lookup_company_follows_sidebar"]),
    "upload_si": (["test_t0062_upload_limit_check.py"], ["test_caddy_sizes_in_bytes", "test_equal_limits_pass"]),
    # v0.2-f Salesforce dry run (D-0045): re-root on Visit__c, setup non-secret only, preview never sends
    "root_event": (["test_t0047_payload.py"], ["test_payload_validates_against_schema", "test_outcomes_only_under_visit"]),
    "net_call": (["test_t0079_sf_no_egress.py"], ["test_no_network_imports", "test_setup_and_preview_with_network_blocked"]),
    "secret_ok": (["test_t0077_sf_config.py"], ["test_secret_values_refused"]),
    "secret_col": (["test_t0077_sf_config.py"], ["test_no_secret_fields_or_columns"]),
    "body_drift": (["test_t0078_sf_preview.py"], ["test_body_is_the_stored_payload"]),  # 6c: on the Composite body
    "send_label": (["test_t0080_sf_dryrun_ui.py"], ["test_preview_after_save_and_lookup_and_no_send"]),
    "url_lax": (["test_t0077_sf_config.py"], ["test_instance_url_pattern", "test_export_import_round_trip"]),
    # 6c one Composite request, allOrNone (D-0046, T-0081; closes F-0033)
    "allornone_off": (["test_t0081_sf_composite.py"], ["test_all_or_none_and_order", "test_check_composite_refuses_each_broken_shape"]),
    "ref_break": (["test_t0081_sf_composite.py"], ["test_every_reference_points_at_the_visit", "test_check_composite_refuses_each_broken_shape"]),
    "over_25": (["test_t0081_sf_composite.py"], ["test_at_most_25_subrequests", "test_check_composite_refuses_each_broken_shape"]),
    "visit_not_first": (["test_t0081_sf_composite.py"], ["test_all_or_none_and_order", "test_check_composite_refuses_each_broken_shape"]),
    "placeholder_linked": (["test_t0082_placeholder_not_linked.py"], ["test_instance_url_in_backticks"]),  # F-0034
    "link_live": (["test_t0082_placeholder_not_linked.py"], ["test_integration_tab_no_salesforce_anchor"]),  # F-0034
    # v0.2-g missed talking-point follow-up (D-0047; T-0083..T-0087)
    "reason_optional": (["test_t0085_gap_gate.py", "test_t0087_schema_04.py"],
                        ["test_save_blocked_and_warning_names_keys", "test_save_visit_refuses_unresolved",
                         "test_schema_04_rejects"]),
    "gap_panel_off": (["test_t0084_narratives.py", "test_t0085_gap_gate.py"],
                      ["test_uncovered_equals_planted", "test_apptest_panel_lists_planted",
                       "test_all_resolved_enables_save_and_stores_reasons"]),
    "second_pass_rescans_covered": (["test_t0086_second_pass.py"], ["test_spy_only_uncovered_keys_and_raised_unchanged",
                                                                    "test_status_never_goes_down",
                                                                    "test_04_round_one_then_round_two"]),
    "partial_dropped": (["test_t0083_hint_status.py", "test_t0084_narratives.py"],
                        ["test_rule_unit_cases", "test_deterministic_and_mentioned_hint_compatible",
                         "test_uncovered_equals_planted", "test_apptest_panel_lists_planted"]),
    "schema_03_mutated": (["test_t0087_schema_04.py"], ["test_v03_schema_bytes_pinned", "test_v03_builder_frozen"]),
    "a1_stopworded": (["test_t0083_hint_status.py", "test_t0084_narratives.py"],
                      ["test_rule_unit_cases", "test_size_point_has_no_keywords_and_uses_anchors",
                       "test_uncovered_equals_planted", "test_apptest_panel_lists_planted"]),
    # v0.2-h1 rule-based auto-fill (D-0048; T-0089..T-0093) and the PR 14 follow-ups N4, N5 (T-0085 amended)
    "quote_paraphrased": (["test_t0089_autofill_evidence.py", "test_t0092_autofill_narratives.py"],
                          ["test_quote_is_verbatim_substring", "test_narrative_matches_fixture"]),
    "share_reaches_status": (["test_t0089_autofill_evidence.py"], ["test_rank_cues_never_affect_status"]),
    "followup_without_cue": (["test_t0090_autofill_followup.py", "test_t0092_autofill_narratives.py"],
                             ["test_no_cue_gives_blank", "test_only_the_evidence_sentence_and_the_next",
                              "test_narrative_matches_fixture"]),
    "edit_overwritten": (["test_t0091_autofill_edits.py"], ["test_edit_survives_reruns_and_provenance_after_save"]),
    "autofill_on_not_raised": (["test_t0093_autofill_scope.py", "test_t0092_autofill_narratives.py"],
                               ["test_not_raised_gets_nothing", "test_narrative_matches_fixture"]),
    "score_autofilled": (["test_t0093_autofill_scope.py"], ["test_writes_only_evidence_and_follow_up_keys",
                                                            "test_apptest_defaults_kept_caption_and_labels"]),
    "response_autofilled": (["test_t0093_autofill_scope.py"], ["test_writes_only_evidence_and_follow_up_keys",
                                                               "test_apptest_defaults_kept_caption_and_labels"]),
    "savevisit_gate_off": (["test_t0085_gap_gate.py"], ["test_save_visit_gate_is_its_own_refusal"]),
    "loaded_gate_off": (["test_t0085_gap_gate.py"], ["test_apptest_save_loaded_gate"]),
    # v0.2-h1b (PR 15 review M-1, M-2, L-3)
    "downgrade_keeps_auto": (["test_t0093_autofill_scope.py"], ["test_apptest_not_raised_pick_withdraws_auto"]),
    "save_keeps_auto_marks": (["test_t0091_autofill_edits.py"], ["test_apptest_second_visit_gets_fresh_suggestions"]),
    "n7_clear_off": (["test_t0086_second_pass.py"], ["test_save_clears_gap_state_n7"]),
    # v0.2-h1c (PR 16 review L-3)
    "not_raised_blanks_edits": (["test_t0093_autofill_scope.py"], ["test_apptest_edit_survives_not_raised_pick"]),
    # v0.2-h2 Gate 1 Bluebird Customer response, flag default OFF (D-0049; T-0094..T-0096)
    "bb_default_on": (["test_t0094_bluebird_flag_off.py"], ["test_flag_values", "test_apptest_flag_off_is_todays_tab"]),
    "bb_label_lax": (["test_t0095_bluebird_client.py"], ["test_parse_label_refuses_anything_else",
                                                         "test_bad_answer_is_unavailable"]),
    "bb_url_lax": (["test_t0095_bluebird_client.py"], ["test_url_refused"]),
    "bb_fills_not_raised": (["test_t0096_bluebird_ui.py"], ["test_click_fills_customer_response_only"]),
    "bb_overwrites_edit": (["test_t0096_bluebird_ui.py"], ["test_edits_win"]),
    "bb_down_neutral": (["test_t0096_bluebird_ui.py"], ["test_model_down_never_saves_neutral"]),
    "bb_unpicked_saves": (["test_t0096_bluebird_ui.py"], ["test_nothing_prepicked_and_save_blocked"]),
    "bb_stale_kept": (["test_t0096_bluebird_ui.py"], ["test_notes_change_withdraws_stale_suggestions"]),
    # v0.2-h4 bug fixes (D-0051; T-0099, T-0100)
    "hint_negation_off": (["test_t0099_hint_not_discussed.py"], ["test_not_discussed_is_not_raised"]),
    "hint_ratio_off": (["test_t0099_hint_not_discussed.py"], ["test_ratio_needs_both_sides"]),
    "bb_not_raised_unpicked": (["test_t0100_bluebird_not_raised.py"],
                               ["test_not_raised_default_needs_no_pick_and_saves_neutral"]),
    "bb_button_silent": (["test_t0100_bluebird_not_raised.py"],
                         ["test_button_with_no_notes_says_why", "test_button_with_nothing_covered_says_why"]),
    "clear_keeps_points": (["test_t0102_clear_form.py"],
                           ["test_clear_empties_the_form", "test_clear_drops_bluebird_suggestions"]),
    "clear_resets_saves": (["test_t0102_clear_form.py"], ["test_saved_visit_survives_and_save_count_kept"]),
    "talk_llm_off_label": (["test_t0101_talking_labels.py"],
                           ["test_talking_point_labels_do_not_say_llm_off", "test_pdf_heading_does_not_say_llm_off"]),
    # v0.2-h3 Bluebird Contract Q&A, same flag (D-0050; T-0097, T-0098)
    "qa_span_unchecked": (["test_t0097_bluebird_qa_client.py", "test_t0098_bluebird_qa_ui.py"],
                          ["test_span_not_in_contract_rejected", "test_rejected_answer_is_not_shown"]),
    "qa_digits_lax": (["test_t0097_bluebird_qa_client.py"],
                      ["test_numbers_outside_slots_rejected_d0023"]),
    "qa_other_system": (["test_t0097_bluebird_qa_client.py"], ["test_units_one_system_and_budget"]),
    "qa_advice_sent": (["test_t0097_bluebird_qa_client.py", "test_t0098_bluebird_qa_ui.py"],
                       ["test_advice_question_never_sent", "test_advice_question_refused_without_the_model"]),
    "qa_down_hidden": (["test_t0097_bluebird_qa_client.py", "test_t0098_bluebird_qa_ui.py"],
                       ["test_failures_are_statuses_never_exceptions", "test_model_down_warns_and_termset_still_works"]),
}
lines, ok_all = [], True
for name, (files, expect) in EXPECT.items():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider"] + TIMEOUT +
                       [f"tests/{f}" for f in files],
                       cwd=ROOT, env=dict(os.environ, REDPROOF=name), capture_output=True, text=True)
    failed = sorted(set(re.findall(r"^FAILED tests/\S+?::(\w+)", r.stdout, re.M)))
    hit = all(e in failed for e in expect)
    ok_all &= hit
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
    lines += [f"## REDPROOF={name}: {'RED as expected' if hit else 'NOT RED (guard is vacuous!)'}",
              f"   files: {', '.join(files)}; pytest exit={r.returncode}; {last}",
              f"   expected red: {', '.join(expect)}", f"   all failed:   {', '.join(failed) or '(none)'}"]
r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + TIMEOUT + ["tests"], cwd=ROOT, capture_output=True,
                   text=True)
lines.append(f"## control (no mutation, full suite): exit={r.returncode}; {r.stdout.strip().splitlines()[-1]}")
ok_all &= r.returncode == 0
lines.append(f"REDPROOF OVERALL: {'PASS' if ok_all else 'FAIL'}")
print("\n".join(lines))
sys.exit(0 if ok_all else 1)
