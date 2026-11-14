#!/usr/bin/env python3
"""Red-proof: run the suite once per deliberate defect (tests/conftest.py REDPROOF=...) and assert the guard test goes red."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable  # clean clone / CI: current interpreter
EXPECT = {
    "nondet": ["test_determinism.py::test_same_seed_identical_bytes", "test_real_out.py::test_real_regeneration_identical"],
    "span": ["test_spans.py::test_all_spans_verbatim"],
    "digits": ["test_answer_digits.py::test_no_digits_in_any_answer"],
    "overlap": ["test_split.py::test_no_system_in_both_splits"],
    "famsplit": ["test_split.py::test_split_by_family", "test_real_out.py::test_real_regeneration_identical"],
    "leak": ["test_family_leak.py::test_no_family_b_text_in_train", "test_family_leak.py::test_template_families_disjoint"],
    "cap": ["test_caps.py::test_oversize_leaf_raises", "test_caps.py::test_section_over_1500_raises"],
    "vault": ["test_vault.py::test_v1_leaf_at_grok_bot_path_rejected", "test_vault.py::test_v1_generator_refuses_vault_out_root",
              "test_vault.py::test_v2_vault_shaped_id_rejected", "test_vault.py::test_v3_provenance_marker_rejected",
              "test_vault.py::test_v4_md_in_vendored_code_dir_rejected"],
    "unans": ["test_qa.py::test_unanswerable_at_least_15pct"],
    "barestamp": ["test_qa.py::test_stamp_cites_decisions_by_name"],
    "dropin_as0041": ["test_spec_dropin.py::test_as0041_violations_rejected[str]",
                      "test_spec_dropin.py::test_as0041_violations_rejected[section]",
                      "test_spec_dropin.py::test_as0041_violations_rejected[dropped]"],
    "dropin_appfields": ["test_spec_dropin.py::test_app_field_rename_rejected",
                         "test_spec_dropin.py::test_toy_spec_is_not_a_contract_spec_for_the_app"],
    # ---- schema_v1 (GATE 2 path B, spec v1.1 §8) ----
    "nat_fallback": ["test_t0065_national.py::test_missing_national_file_raises",
                     "test_t0065_national.py::test_altered_national_file_raises"],
    "nat_drop": ["test_t0065_national.py::test_national_pins_in_every_exhibit"],
    "nat_window": ["test_t0065_national.py::test_national_pins_in_every_exhibit"],
    "nat_sha": ["test_t0065_national.py::test_manifest_benchmark_source"],
    "nat_cols": ["test_t0065_national.py::test_only_listed_columns_are_read"],
    "band_gt": ["test_t0067_contract_sales.py::test_rule_edges", "test_t0067_contract_sales.py::test_values_recomputed"],
    "floor_ignore_amd": ["test_t0067_contract_sales.py::test_rule_edges"],
    "refuse_leak": ["test_t0068_refusals.py::test_refusal_rows_exact"],
    "status_number": ["test_t0069_status.py::test_status_fields"],
    "nat_invent": ["test_t0069_status.py::test_status_fields"],
    "inv_source": ["test_t0070_provenance.py::test_source_counts_recomputed"],
    "drop_r5": ["test_t0071_coverage.py::test_pool_covers_every_item_level"],
    "exh_skip_one": ["test_t0072_counts.py::test_counts_structural", "test_t0072_counts.py::test_counts_pinned"],
    "nomarker": ["test_t0073_marker.py::test_marker_header_and_footer"],
    "nofooter": ["test_t0073_marker.py::test_marker_header_and_footer"],
    "marker_typo": ["test_t0073_marker.py::test_marker_header_and_footer",
                    "test_t0073_marker.py::test_marker_in_contract_and_proposal_leaves"],
    "noflag": ["test_t0073_marker.py::test_manifest_flag_and_row_flag"],
    "party_rng": ["test_t0074_counterparty.py::test_party_and_brands"],
    "rival_brand": ["test_t0074_counterparty.py::test_party_and_brands"],
    "exh_rng": ["test_t0075_exhibit_determinism.py::test_exhibit_identical_across_seeds"],
}
RUN_TIMEOUT = int(os.environ.get("REDPROOF_TIMEOUT", "300"))  # per pytest run; a hang fails loudly
lines, ok_all = [], True
for name, expect in EXPECT.items():
    env = dict(os.environ, REDPROOF=name)
    print(f"[redproof] REDPROOF={name} ...", flush=True)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "tests"], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=RUN_TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        ok_all = False
        lines.append(f"## REDPROOF={name}: TIMEOUT after {RUN_TIMEOUT}s (counts as FAIL)")
        continue
    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) tests/(\S+?)(?: - |$)", r.stdout, re.M)))
    summary = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
    hit = all(e in failed for e in expect)
    ok_all &= hit
    lines.append(f"## REDPROOF={name}: {'RED as expected' if hit else 'NOT RED (guard is vacuous!)'}")
    lines.append(f"   pytest exit={r.returncode}; {summary}")
    lines.append("   expected red: " + ", ".join(expect))
    lines.append("   all failed:   " + (", ".join(failed) or "(none)"))
print("[redproof] control ...", flush=True)
r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=ROOT, capture_output=True, text=True,
                   timeout=RUN_TIMEOUT, stdin=subprocess.DEVNULL)
lines.append(f"## control (no mutation): exit={r.returncode}; {r.stdout.strip().splitlines()[-1]}")
ok_all &= r.returncode == 0
lines.append(f"REDPROOF OVERALL: {'PASS' if ok_all else 'FAIL'}")
print("\n".join(lines))
sys.exit(0 if ok_all else 1)
