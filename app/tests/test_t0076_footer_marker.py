"""T-0076 (footer parse and marker display): `contracts.parse_doc` stops the last section at the footer rule without
dropping body text, for a hand-built document (header MARKER, body, footer MARKER, in that order) and for every
gen/out document; and the documents' MARKER reaches the Q&A tab, the Brief tab and the PDF reports.
Mutations: footer_eats_body, marker_hidden."""
import json
import re
import subprocess
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import config, contracts, report

MARKER = "SYNTHETIC TRAINING DOCUMENT. NOT A REAL AGREEMENT. Terms are invented."
APP = str(Path(__file__).resolve().parents[1] / "app.py")
DOC = ("---\n" + 'doc_id: "SYN-SYNCPX-MSA1"\nsystem_id: "SYNCPX"\n' + "---\n\n# Master Supply Agreement\n\n"
       f"{MARKER}\n\n> stamp line\n\n## 1. Parties\n\nFirst body line.\n\n## 2. Term\n\nLast body line one.\n"
       "Last body line two - with a dash.\n\n---\n\n" + MARKER + "\n")


def test_hand_built_order_and_no_body_dropped():
    assert DOC.index(MARKER) < DOC.index("## 1. Parties") < DOC.index("Last body line two") < DOC.rindex(MARKER)
    meta, secs = contracts.parse_doc(DOC)
    assert meta["doc_id"] == "SYN-SYNCPX-MSA1"
    assert secs["1"]["text"] == "First body line."
    assert secs["2"]["text"] == "Last body line one.\nLast body line two - with a dash."
    assert all(MARKER not in s["text"] and "---" not in s["text"] for s in secs.values())
    assert contracts.doc_marker(DOC) == MARKER


def test_every_gen_out_doc_keeps_its_body():
    paths = sorted(Path(config.GEN_OUT).glob("*/docs/SYN-*.md"))
    assert len(paths) == 623
    for p in paths:
        t = p.read_text()
        _m, secs = contracts.parse_doc(t)
        body = t[t.index("\n## "):t.rindex("\n---\n")]
        want = [ln for ln in body.split("\n") if ln.strip() and not ln.startswith("## ")]
        got = [ln for s in secs.values() for ln in s["text"].split("\n") if ln.strip()]
        assert got == want, p.name
        assert contracts.doc_marker(t) == MARKER, p.name


def test_marker_reaches_qa_answer_and_reports(tmp_path, real_facts):
    for sid in ("SYNCP000001", "SYNCP000025", "SYNCP000036"):
        assert contracts.system_marker(sid) == MARKER, sid
        res = contracts.answer(sid, "When does the MSA expire?")
        assert res["citations"] and res["marker"] == MARKER, sid
        _n, rows, pdf = report.build(real_facts[sid])
        assert report.brief_contract_lines(rows, contracts.system_marker(sid))[0] == MARKER
        p = tmp_path / f"{sid}.pdf"
        p.write_bytes(pdf)
        text = subprocess.run(["pdftotext", "-raw", str(p), "-"], capture_output=True, text=True).stdout
        assert re.sub(r"\s+", "", MARKER) in re.sub(r"\s+", "", text), sid


def test_marker_on_qa_and_brief_tabs():
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.selectbox(key="system").set_value("SYNCP000001").run()
    at.text_input(key="qa_text").input("When does the MSA expire?").run()
    assert not at.exception
    brief = " ".join(m.value for m in at.tabs[0].markdown)
    qa = " ".join(m.value for m in at.tabs[2].markdown)
    assert MARKER in brief, "Brief tab"
    assert MARKER in qa and "June 30, 2027" in qa, "Q&A tab"


def test_committed_reports_show_marker():
    d = Path(__file__).resolve().parents[1] / "evidence" / "reports"
    for sid in ("SYNCP000001", "SYNCP000025", "SYNCP000036"):
        text = subprocess.run(["pdftotext", "-raw", str(d / f"little-blue-{sid}.pdf"), "-"], capture_output=True,
                              text=True).stdout
        assert re.sub(r"\s+", "", MARKER) in re.sub(r"\s+", "", text), sid
        fs = json.loads((d / f"FS-{sid}-{config.AS_OF}.json").read_text())
        assert fs["system_id"] == sid
