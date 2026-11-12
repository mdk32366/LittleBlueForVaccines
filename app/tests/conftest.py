"""Fixtures + REDPROOF mutations (test-side monkeypatches only; production code has no hooks)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brief import benchmark as bm, clean, config as cfg, contracts, facts, load, narrative, render, switching, train_guard, validator  # noqa: E402,E501
from tests import make_fixture  # noqa: E402

SAMPLE = {"switch": None, "noswitch": None, "edge": None}


def apply_mutation(name):
    if name == "reconcile":
        orig = clean.clean
        clean.clean = lambda df: orig(df[df["DOLLARS"] >= 0])
    elif name == "ratio":
        facts.ratio_status = lambda b, a: ((b / a) if a else float("inf"), "ok")
    elif name == "switch":
        switching.MIN_Z, switching.MIN_MOVE, switching.MIN_CLASS_DOSES = 0.0, 0.0, 0
    elif name == "validator":
        validator.validate = lambda text, known: validator.Result(True, [])
    elif name == "fallback":
        orig = narrative.compose
        narrative.compose = lambda fs, llm=None: orig(fs) if llm is None else narrative.Narrative(
            [llm(fs.to_json(), timeout=20)], [], "llm", [])
    elif name == "onepage":
        from matplotlib.backends.backend_pdf import PdfPages
        import io

        def two_pages(fs, n, rows=()):
            buf = io.BytesIO()
            with PdfPages(buf) as pdf:
                pdf.savefig(render.build_figure(fs, n, rows))
                pdf.savefig(render.build_figure(fs, n, rows))
            return buf.getvalue()
        render.render_pdf_bytes = two_pages
    elif name == "label":
        bm.SYNTHETIC_LABEL = None
        render.footer_text = lambda fs: "footer"
    elif name == "name":
        cfg.APP_NAME = "Little Blue"
    elif name == "isolation":
        def leaky(system_id):
            out = {}
            for p in contracts._all_doc_paths(str(contracts.gen_out())):
                meta, secs = contracts.parse_doc(p.read_text())
                out[meta["doc_id"]] = (meta, secs, p)
            return out
        contracts.system_docs = leaky
    elif name == "expired":
        contracts.is_expired = lambda *a, **k: False
    elif name == "expired_le":  # off-by-one: "on or before" instead of strictly before the as-of date
        contracts.is_expired = lambda field_key, value, as_of=None: (contracts._base(field_key) == "expiration_date"
                                                                     and str(value) <= (as_of or cfg.AS_OF_DATE))
    elif name == "bench":
        bm.national = lambda path: bm.synthetic(load.load_csv(cfg.DATA_PATH))
        orig = bm.resolve

        def no_fallback(df, mode=None, path=None):
            if (mode or bm.requested_mode()) == "national":
                p = Path(path) if path else bm.national_path()
                if not p.exists():
                    raise FileNotFoundError(p)  # the defect: no fallback
                return bm.national(p)
            return orig(df, mode, path)
        bm.resolve = no_fallback
    elif name == "trainguard":
        train_guard.refuse_training_input = lambda *a, **k: None
        train_guard.refuse_record = lambda *a, **k: None
        train_guard.scan_for_national = lambda *a, **k: []
    elif name:
        raise ValueError(f"unknown REDPROOF mutation {name}")


def pytest_configure(config):  # noqa: F811 (pytest hook arg name is fixed)
    apply_mutation(os.environ.get("REDPROOF", ""))


@pytest.fixture(scope="session")
def fixture_csv(tmp_path_factory):
    return make_fixture.write(tmp_path_factory.mktemp("fx") / "fixture.csv")


@pytest.fixture(scope="session")
def fixture_df(fixture_csv):
    return clean.clean(load.load_csv(fixture_csv))


@pytest.fixture(scope="session")
def fixture_facts(fixture_df):
    return facts.compute_all(fixture_df)


@pytest.fixture(scope="session")
def raw_df():
    return load.load_csv(cfg.DATA_PATH)


@pytest.fixture(scope="session")
def real_df(raw_df):
    return clean.clean(raw_df)


@pytest.fixture(scope="session")
def real_facts(real_df):
    return facts.compute_all(real_df)
