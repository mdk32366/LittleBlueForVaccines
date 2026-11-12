"""T-0038 expired marker: a contract whose end date is before the as-of date is marked in the PDF snapshot and the
Q&A tab (SYNCP000036's MSA ended 2026-08-31; as-of 2026-09-30). Live contracts carry no marker."""
import subprocess

from brief import config, contracts, render, report

EXPIRED_SID, LIVE_SID = "SYNCP000036", "SYNCP000025"


def test_flag_on_lookup():
    exp = contracts.lookup(EXPIRED_SID, field_key="expiration_date")
    assert exp and exp[0]["value"] == "2026-08-31" < config.AS_OF_DATE and exp[0]["expired"] is True
    live = contracts.lookup(LIVE_SID, field_key="expiration_date")
    assert live and live[0]["expired"] is False


def test_rule_edges():
    assert contracts.is_expired("expiration_date", "2026-09-29")
    assert not contracts.is_expired("expiration_date", config.AS_OF_DATE)
    assert not contracts.is_expired("effective_date", "2020-01-01")


def test_qa_citation_flagged():
    res = contracts.answer(EXPIRED_SID, "When does the MSA expire?")
    assert res["citations"] and all(h["expired"] for h in res["citations"])
    assert not any(h["expired"] for h in contracts.answer(LIVE_SID, "When does the MSA expire?")["citations"])


def test_pdf_snapshot_marked_and_one_page(tmp_path, real_facts):
    for sid, want in ((EXPIRED_SID, True), (LIVE_SID, False)):
        _n, rows, pdf = report.build(real_facts[sid])
        lines = render.contract_lines(rows)
        assert any(contracts.EXPIRED_MARKER in ln for ln in lines) is want, sid
        p = tmp_path / f"{sid}.pdf"
        p.write_bytes(pdf)
        text = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
        assert (contracts.EXPIRED_MARKER in text) is want, sid
        assert render.pdf_page_count(pdf) == 1, sid


def test_file_count_exactly_21_and_edge_systems_live(real_facts):
    """AS-0040 (expired rule) is strictly before AS_OF_DATE: 21 of 180 MSAs; the three ending on 2026-09-30 are live."""
    assert len(real_facts) == 180
    expired = sorted(h["doc_id"] for sid in real_facts for h in contracts.lookup(sid, base="expiration_date") if h["expired"])
    assert len(expired) == 21, expired
    for sid in ("SYNCP000094", "SYNCP000095", "SYNCP000096"):
        hits = contracts.lookup(sid, base="expiration_date")
        assert hits and all(h["value"] == config.AS_OF_DATE and h["expired"] is False for h in hits), sid
