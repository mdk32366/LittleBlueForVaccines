#!/usr/bin/env python3
"""Red-proof: one deliberate defect per run (tests/conftest.py REDPROOF=...), running the guard's own test file(s);
each must go red. Then the full suite with no mutation must be green (control)."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable  # clean clone / CI: current interpreter
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
    "expired_le": (["test_t0038_expired.py"], ["test_file_count_exactly_21_and_edge_systems_live", "test_rule_edges"]),
    "noautorenew": (["test_t0039_autorenew.py", "test_t0040_brief_contracts.py"], ["test_rule_unit_cases", "test_rule_ignores_clause_wording",
                                                 "test_pre_regen_split_9_12_stub_data", "test_status_column_and_citations_use_marker",
                                                 "test_brief_tab_markers"]),
    "nosamesection": (["test_t0039_autorenew.py"], ["test_rule_unit_cases"]),
    "schema_autorenew": (["test_t0041_autorenew_schema.py"], ["test_auto_renew_present_on_every_msa",
                                                              "test_auto_renew_is_bool_in_term_section"]),
    "briefmarker": (["test_t0040_brief_contracts.py"], ["test_brief_tab_markers"]),
    "bench": (["test_t0037_benchmark.py"], ["test_national_mode", "test_missing_national_falls_back"]),
    "trainguard": (["test_t0025_train_guard.py"], ["test_refuses_national_path", "test_refuses_outside_train_dirs_and_copies",
                                                    "test_refuses_non_synthetic_record", "test_scan_flags_planted_reference"]),
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
}
lines, ok_all = [], True
for name, (files, expect) in EXPECT.items():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider"] + [f"tests/{f}" for f in files],
                       cwd=ROOT, env=dict(os.environ, REDPROOF=name), capture_output=True, text=True)
    failed = sorted(set(re.findall(r"^FAILED tests/\S+?::(\w+)", r.stdout, re.M)))
    hit = all(e in failed for e in expect)
    ok_all &= hit
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
    lines += [f"## REDPROOF={name}: {'RED as expected' if hit else 'NOT RED (guard is vacuous!)'}",
              f"   files: {', '.join(files)}; pytest exit={r.returncode}; {last}",
              f"   expected red: {', '.join(expect)}", f"   all failed:   {', '.join(failed) or '(none)'}"]
r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=ROOT, capture_output=True, text=True)
lines.append(f"## control (no mutation, full suite): exit={r.returncode}; {r.stdout.strip().splitlines()[-1]}")
ok_all &= r.returncode == 0
lines.append(f"REDPROOF OVERALL: {'PASS' if ok_all else 'FAIL'}")
print("\n".join(lines))
sys.exit(0 if ok_all else 1)
