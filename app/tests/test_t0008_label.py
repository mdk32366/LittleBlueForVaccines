"""T-0008 benchmark label: every benchmark-derived fact carries its source_label, and the PDF footer shows it."""
import subprocess

from brief import benchmark as bm, facts, report

BENCH_FACTS = {"F1.rank", "F1.n_systems", "F1.bench_share", "F6.bench_ratio", "F6.index_vs_bench",
               "F6.state_status", "F6.state_ratio", "F6.index_vs_state"}


def _pdf_text(tmp_path, fs):
    p = tmp_path / f"{fs.system_id}.pdf"
    p.write_bytes(report.build(fs)[2])
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout


def test_benchmark_facts_labelled(real_facts):
    for fs in real_facts.values():
        for k, f in fs.facts.items():
            if k in BENCH_FACTS:
                assert f.source_label in ("synthetic peers", "national"), (fs.system_id, k)
            else:
                assert f.source_label == "system", (fs.system_id, k)


def test_footer_shows_synthetic(tmp_path, real_facts):
    assert "Benchmark: synthetic peers" in _pdf_text(tmp_path, real_facts["SYNCP000025"])


def test_footer_shows_national(tmp_path, real_df):
    fs = facts.compute_all(real_df, bm.resolve(real_df, "national"))["SYNCP000025"]
    t = _pdf_text(tmp_path, fs)
    assert "Benchmark: national" in t and "rank and in-state: synthetic peers" in t
