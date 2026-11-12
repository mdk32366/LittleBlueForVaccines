"""T-0006 one page: the PDF has exactly one page for every system in the synthetic file (180 renders)."""
import subprocess

from brief import narrative, render, report


def test_page_counter_counts():
    assert render.pdf_page_count(b"/Type /Pages /Type /Page /Type /Page") == 2


def test_all_180_one_page(real_facts):
    assert len(real_facts) == 180
    for sid, fs in sorted(real_facts.items()):
        _n, _r, pdf = report.build(fs)
        assert render.pdf_page_count(pdf) == 1, sid


def test_pdfinfo_agrees(tmp_path, real_facts):
    fs = real_facts["SYNCP000025"]
    p = tmp_path / "x.pdf"
    p.write_bytes(report.build(fs)[2])
    out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
    assert "Pages:           1" in out


def test_points_truncate_with_ellipsis():
    lines = render.fit_points(["word " * 400])
    assert len(lines) == render.POINT_LINES and lines[-1].endswith("…")
