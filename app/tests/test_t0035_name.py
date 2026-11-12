"""T-0035 name, D-0033 (name): "Little Blue for Vaccine Sales" in the page title, the page header, the PDF header, README."""
import subprocess
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from brief import config, report

NAME = "Little Blue for Vaccine Sales"
APP = Path(__file__).resolve().parents[1] / "app.py"


def test_constant():
    assert config.APP_NAME == NAME


def test_page_title_and_header(monkeypatch):
    seen = {}
    real = st.set_page_config

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)
    monkeypatch.setattr(st, "set_page_config", spy)
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception
    assert seen.get("page_title") == NAME
    assert at.title[0].value == NAME


def test_pdf_header(tmp_path, real_facts):
    p = tmp_path / "r.pdf"
    p.write_bytes(report.build(real_facts["SYNCP000025"])[2])
    first = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout.splitlines()[0]
    assert first.startswith(NAME)


def test_readme():
    assert NAME in (APP.parent / "README.md").read_text()
