"""T-0038 expired marker: a contract whose end date is before the as-of date is marked in the PDF snapshot and the
Q&A tab (SYNCP000002's MSA ended 2026-05-31; as-of 2026-09-30). Live contracts carry no marker.
Re-pinned for the schema_v1 regeneration (GATE 2, the Architect's ruling): stub-v0 pins were 036 / 014 / 025, 21 expired,
live edges 094/095/096."""
import re
import subprocess

from brief import config, contracts, render, report

EXPIRED_SID, LIVE_SID = "SYNCP000002", "SYNCP000025"  # 002: expired, auto-renews (was 036)
NONE_SID = "SYNCP000021"  # expired, auto_renew False (was 014)


def test_flag_on_lookup():
    exp = contracts.lookup(EXPIRED_SID, field_key="expiration_date")
    assert exp and exp[0]["value"] == "2026-05-31" < config.AS_OF_DATE and exp[0]["expired"] is True
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
    """PDF snapshot: SYNCP000021 (expired, no auto-renew) shows [EXPIRED]; SYNCP000002 (expired, auto-renews) shows
    the auto-renew label instead; SYNCP000025 (live) shows neither. All stay one page."""
    for sid, want in ((NONE_SID, contracts.EXPIRED_MARKER), (EXPIRED_SID, contracts.AUTO_RENEW_MARKER), (LIVE_SID, None)):
        _n, rows, pdf = report.build(real_facts[sid])
        lines = " ".join(render.contract_lines(rows))
        p = tmp_path / f"{sid}.pdf"
        p.write_bytes(pdf)
        text = subprocess.run(["pdftotext", "-raw", str(p), "-"], capture_output=True, text=True).stdout
        for m in (contracts.EXPIRED_MARKER, contracts.AUTO_RENEW_MARKER):
            assert (m in lines) is (m == want), (sid, m)
        if want:  # pdftotext may wrap the label; compare with whitespace removed
            assert re.sub(r"\s+", "", want) in re.sub(r"\s+", "", text), sid
        else:
            assert "[EXPIRED]" not in text and "[TERM ENDED" not in text, sid
        assert render.pdf_page_count(pdf) == 1, sid


def test_file_count_exactly_19_and_edge_systems_live(real_facts):
    """AS-0040 (expired rule) is strictly before AS_OF_DATE: 19 MSAs (was 21 on stub-v0); the two ending on 2026-09-30
    (005, 106; were 094/095/096) are live."""
    assert len(real_facts) == 180
    expired = sorted(h["doc_id"] for sid in real_facts for h in contracts.lookup(sid, base="expiration_date") if h["expired"])
    assert len(expired) == 19, expired
    for sid in ("SYNCP000005", "SYNCP000106"):
        hits = contracts.lookup(sid, base="expiration_date")
        assert hits and all(h["value"] == config.AS_OF_DATE and h["expired"] is False for h in hits), sid
