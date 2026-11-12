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
    "briefmarker": (["test_t0040_brief_contracts.py"], ["test_brief_tab_markers"]),
    "bench": (["test_t0037_benchmark.py"], ["test_national_mode", "test_missing_national_falls_back"]),
    "trainguard": (["test_t0025_train_guard.py"], ["test_refuses_national_path", "test_refuses_outside_train_dirs_and_copies",
                                                    "test_refuses_non_synthetic_record", "test_scan_flags_planted_reference"]),
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
