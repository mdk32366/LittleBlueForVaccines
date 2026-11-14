"""The five committed visit narratives (tests/fixtures/narratives, v0.2-g, D-0047) and the planted coverage tables in
their expected.md, parsed verbatim. Synthetic notes, roles only (T-0088)."""
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent / "fixtures" / "narratives"
EXPECTED = DIR / "expected.md"
MARKER = "FAKE-SYNTHETIC demo visit note: synthetic data, roles only."
PLANTED = {"covered": "Raised", "missed": "Not raised", "partial": "Partially"}  # planted value -> panel status


def cases() -> dict:
    """{"01": {"file": Path, "sid": "SYNCP000025", "rows": [(key, app_text, planted, sentence), ...]}, ...}"""
    out, cur = {}, None
    for line in EXPECTED.read_text().splitlines():
        m = re.match(r"^- \*\*File:\*\* `narratives/((\d\d)-(SYNCP\d{6})-[^`]+\.txt)`", line)
        if m:
            cur = out.setdefault(m.group(2), {"file": DIR / m.group(1), "sid": m.group(3), "rows": []})
            continue
        if cur is not None and line.startswith("| ") and not line.startswith("| Key") and not line.startswith("| ---"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            assert len(cells) == 4, line
            cur["rows"].append(tuple(cells))
    return out


def notes(case: dict) -> str:
    return case["file"].read_text()


def planted_gaps(case: dict) -> dict:
    """{key: status} for every planted row that is not covered, in table order."""
    return {k: PLANTED[p] for k, _, p, _ in case["rows"] if p != "covered"}


APP = str(Path(__file__).resolve().parents[1] / "app.py")
PANEL_ROW = re.compile(r"^\*\*(\S+)\*\* \((Raised|Partially|Not raised)\): ")


def app_with_notes(tmp_path, monkeypatch, case: dict, rep: str = "Demo Rep"):
    """An AppTest of the whole app on a temporary visit store, the case's system picked, the narrative typed into the
    Visit notes box."""
    import datetime

    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value(case["sid"]).run()
    at.text_input(key="vr_rep").input(rep).run()
    at.date_input(key="vr_date").set_value(datetime.date(2026, 11, 18)).run()
    at.text_area(key="vr_notes").input(notes(case)).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def panel(at) -> dict:
    """{key: status} as the 'Not covered yet' panel lists them, in order."""
    out = {}
    for m in at.markdown:
        hit = PANEL_ROW.match(m.value)
        if hit:
            out[hit.group(1)] = hit.group(2)
    return out


def mode_key(sid: str, key: str, where: str = "typed") -> str:
    return f"vr_gap_mode_{where}_{sid}_{key}"


def reason_key(sid: str, key: str, where: str = "typed") -> str:
    return f"vr_gap_reason_{where}_{sid}_{key}"


def text_key(sid: str, key: str, where: str = "typed") -> str:
    return f"vr_gap_text_{where}_{sid}_{key}"
