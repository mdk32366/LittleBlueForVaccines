#!/usr/bin/env python3
"""Red-proof: run the suite once per deliberate defect (tests/conftest.py REDPROOF=...) and assert the guard test goes red."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable  # clean clone / CI: current interpreter
EXPECT = {
    "nondet": ["test_determinism.py::test_same_seed_identical_bytes"],
    "span": ["test_spans.py::test_all_spans_verbatim"],
    "digits": ["test_answer_digits.py::test_no_digits_in_any_answer"],
    "overlap": ["test_split.py::test_no_system_in_both_splits"],
    "famsplit": ["test_split.py::test_split_by_family"],
    "leak": ["test_family_leak.py::test_no_family_b_text_in_train", "test_family_leak.py::test_template_families_disjoint"],
    "cap": ["test_caps.py::test_oversize_leaf_raises", "test_caps.py::test_section_over_1500_raises"],
    "vault": ["test_vault.py::test_v1_leaf_at_grok_bot_path_rejected", "test_vault.py::test_v1_generator_refuses_vault_out_root",
              "test_vault.py::test_v2_vault_shaped_id_rejected", "test_vault.py::test_v3_provenance_marker_rejected",
              "test_vault.py::test_v4_md_in_vendored_code_dir_rejected"],
    "unans": ["test_qa.py::test_unanswerable_at_least_15pct"],
}
lines, ok_all = [], True
for name, expect in EXPECT.items():
    env = dict(os.environ, REDPROOF=name)
    r = subprocess.run([PY, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "tests"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    failed = sorted(set(re.findall(r"^FAILED tests/(\S+?)(?: - |$)", r.stdout, re.M)))
    summary = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
    hit = all(e in failed for e in expect)
    ok_all &= hit
    lines.append(f"## REDPROOF={name}: {'RED as expected' if hit else 'NOT RED (guard is vacuous!)'}")
    lines.append(f"   pytest exit={r.returncode}; {summary}")
    lines.append("   expected red: " + ", ".join(expect))
    lines.append("   all failed:   " + (", ".join(failed) or "(none)"))
r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=ROOT, capture_output=True, text=True)
lines.append(f"## control (no mutation): exit={r.returncode}; {r.stdout.strip().splitlines()[-1]}")
ok_all &= r.returncode == 0
lines.append(f"REDPROOF OVERALL: {'PASS' if ok_all else 'FAIL'}")
print("\n".join(lines))
sys.exit(0 if ok_all else 1)
