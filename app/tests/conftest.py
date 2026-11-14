"""Fixtures + REDPROOF mutations (test-side monkeypatches only; production code has no hooks)."""
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brief import availability, benchmark as bm, clean, client_metrics, config as cfg, contracts, facts, load, narrative, render, report, switching, talking, train_guard, validator  # noqa: E402,E501
from brief import payload, visits  # noqa: E402
from tests import make_fixture, metrics_fixture  # noqa: E402

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
    elif name == "noautorenew":  # (a) drop the auto_renew check: every expired MSA falls back to [EXPIRED]
        contracts.term_ended_auto_renews = lambda *a, **k: False
    elif name == "nosamesection":  # (b) drop the same-section check
        contracts.same_section = lambda a, b: True
    elif name == "briefmarker":  # (c) hide the marker on the Brief tab only (PDF untouched)
        report.brief_contract_lines = lambda rows, marker="": [
            ln.replace(contracts.AUTO_RENEW_MARKER, "").replace(contracts.EXPIRED_MARKER, "")
            for ln in render.contract_lines(rows, marker)]
    elif name == "schema_autorenew":  # T-0041: drop auto_renew on one MSA, make it a string on another
        orig = contracts.system_terms

        def broken_terms(system_id):
            rows = orig(system_id)
            if system_id == "SYNCP000001":
                return [r for r in rows if not (r[0].endswith("-MSA1") and contracts._base(r[1]) == "auto_renew")]
            if system_id == "SYNCP000002":
                return [(d, k, dict(f, value=str(f["value"])) if d.endswith("-MSA1") and contracts._base(k) == "auto_renew"
                         else f) for d, k, f in rows]
            return rows
        contracts.system_terms = broken_terms
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
        train_guard.scan_national_mentions = lambda *a, **k: []
    elif name == "exh_window":  # T-0064: the generator's system figures use T12 instead of the FULL window
        from tests import v1_gen
        orig_add = v1_gen.PM.Acc.add

        def t12_only(self, r):
            if v1_gen.PM.SID in r and not (v1_gen.PM.T12[0] <= r["MTH_ID"] <= v1_gen.PM.T12[1]):
                return None
            return orig_add(self, r)
        v1_gen.PM.Acc.add = t12_only
    elif name == "exh_peer_incl":  # T-0064: the generator's in-state peers include the system itself
        from tests import v1_gen
        v1_gen.PM.peer_ids = lambda sid, counts: sorted(p for p, c in counts.items()
                                                        if c["state"] == counts[sid]["state"])
    elif name == "nat_profile_r1":  # T-0065 app: the app's national R1 drops MenABCWY from its numerator
        bm.R1_NUM_SUBCLASSES = ("MenB",)
    elif name == "refusal_text":  # T-0068 app: the app's refusal string drifts
        contracts.REFUSAL = "not found in the contracts"
    elif name == "footer_eats_body":  # T-0076: the last section ends at the first line after its heading
        contracts.RULE_RE = re.compile(r"^\S", re.M)
    elif name == "marker_hidden":  # T-0076: the app stops showing the documents' marker
        contracts.system_marker = lambda system_id: ""
    elif name == "guard_open":  # T-0066: refuse_training_input accepts any path
        train_guard.refuse_training_input = lambda *a, **k: None
    # v0.2-a client metrics (T-0042, T-0043, T-0044, T-0053)
    elif name == "kr_abcwy":  # T-0042: drop MenABCWY from the R1 numerator
        bm.R1_NUM_SUBCLASSES = ("MenB",)
    elif name == "kr_swap":  # T-0042: swap numerator and denominator of every ratio
        client_metrics.RATIOS = {k: (d, n) for k, (n, d) in client_metrics.RATIOS.items()}
    elif name == "invent":  # T-0043: the registry lets a NOT AVAILABLE national A8 through as the number 0
        orig_gate = availability.gate
        availability.gate = lambda key, compute: (0, "ok") if key == "A8.national" else orig_gate(key, compute)
    elif name == "ratio_neg":  # T-0044: drop the denominator <= 0 check
        def no_nonpos(num, den):
            if den < client_metrics.MIN_RATIO_DEN:
                return None, "insufficient volume"
            if num < 0:
                return None, "net returns"
            return num / den, "ok"
        client_metrics.ratio_rule = no_nonpos
    elif name == "a1_excl":  # T-0042/T-0044: A1 state reverts to the system-excluded denominator (can exceed 1)
        client_metrics.state_share = lambda sys_d, peer_d: (sys_d / peer_d, "ok") if peer_d > 0 else (None, "undefined")
    elif name == "tok_wide":  # T-0053: any F-number token is accepted
        validator.TOKEN = re.compile(r"\{(F\d+\.[a-z0-9_]+)\}")
    # v0.2-b talking points, tabs and the client email 2026-11-13 items (T-0045, T-0052, T-0055..T-0058)
    elif name == "tp_digit":  # T-0045: a literal number in a template
        talking.QUESTION = talking.QUESTION.replace("next season", "the next 12 months")
    elif name == "tp_inject":  # T-0045: a rendered point gains a number no computed fact produced
        orig_render = talking.render
        talking.render = lambda text, fs: orig_render(text, fs) + " (up 12%)"
    elif name == "tp_select":  # T-0045: must-cover threshold 25 -> 0
        talking.MUST_COVER_MIN_DEV = 0
    elif name == "tp_na":  # T-0045: status labels and NOT AVAILABLE tokens let through
        talking.allowed = lambda fid, fs: True
    elif name == "payload_fields":  # T-0045: the payload seam's field order drifts
        from dataclasses import make_dataclass
        talking.PayloadPoint = make_dataclass("PayloadPoint", ["key", "text", "metric_value", "bench_national",
                                                               "bench_state"], frozen=True)
    elif name == "tabs":  # T-0052: the Talking points tab dropped
        cfg.TABS = ["Brief", "Contract Q&A"]
    elif name == "r4_def":  # T-0055: R4 numerator back to every HepB dose
        client_metrics.RATIOS = {**client_metrics.RATIOS, "R4": ("hepb", "dtap")}
    elif name == "r6_proxy":  # T-0056: R6 numerator back to the older-adult products only
        orig_pooled = bm.pooled

        def proxy_pooled(df, *a, **k):
            out = orig_pooled(df, *a, **k)
            u, p = df["VAC_PROD_SUBCLAS_NM"], df["PROD_NM"].astype(str).str.upper()
            out["rsv"] = float(df.loc[(u == "RSV Vaccine") & p.str.contains("AREXVY|MRESVIA"), "DOSES"].sum())
            return out
        bm.pooled = proxy_pooled
    elif name == "obgyn_spec":  # T-0057: the OBGYN specialty filter moves off Women's Health
        bm.OBGYN_SPECIALTY = "Primary Care"
    elif name == "babies_swap":  # T-0058: private and total swapped
        client_metrics._babies = lambda c: (c["dtap"] / 5, c["varicella"] / 2)
    # v0.2-d visit store + FAKE Salesforce payload record (T-0047, T-0048, T-0049, T-0051, T-0059)
    elif name == "pay_drop":  # T-0047: the Event loses ActivityDate
        orig_build = payload.build_payload

        def no_date(**kw):
            p = orig_build(**kw)
            p["trees"]["Event"]["records"][0].pop("ActivityDate")
            return p
        payload.build_payload = no_date
    elif name == "pay_nofake":  # T-0047: the FAKE-SYNTHETIC marker is dropped everywhere
        orig_build = payload.build_payload

        def no_fake(**kw):
            p = orig_build(**kw)
            p["lb_marker"] = "REAL"
            for tree in p["trees"].values():
                for r in tree["records"]:
                    r["Description"] = r["Description"].replace(payload.FAKE_MARKER + " ", "")
            return p
        payload.build_payload = no_fake
    elif name == "schema_lax":  # T-0047: the schema check accepts anything
        payload.validate = lambda p: None
    elif name == "pay_none_str":  # T-0047: values are stringified, so None becomes "None" and NaN leaks through
        payload._val = lambda v: str(v)
    elif name == "hint":  # T-0047: the keyword hint never fires
        payload.mentioned_hint = lambda point, transcript: False
    elif name == "store_nopayload":  # T-0048: saving writes the visit row but no payload record
        visits._write_payload = lambda conn, key, p, now: 1
    elif name == "store_overwrite":  # T-0048: a re-save replaces version 1 instead of appending
        def overwrite(conn, key, p, now):
            conn.execute("DROP TRIGGER IF EXISTS sf_payloads_no_delete")
            conn.execute("DELETE FROM sf_payloads WHERE visit_key = ?", (key,))
            conn.execute("INSERT INTO sf_payloads (visit_key, version, created_at, schema_version, payload_json, "
                         "sha256) VALUES (?, 1, ?, ?, ?, ?)", (key, now, p["lb_schema_version"], payload.canonical(p),
                                                               payload.sha256(p)))
            return 1
        visits._write_payload = overwrite
    elif name == "store_prefix":  # T-0048: lookup matches a rep prefix (LIKE) instead of the exact key
        orig_lookup = visits.lookup

        def prefix(rep, visit_date, system_id, db=None):
            c = visits.connect(db)
            row = c.execute("SELECT rep_key FROM visits WHERE rep_key LIKE ? AND visit_date = ? AND system_id = ?",
                            (payload.rep_key(rep) + "%", visit_date, system_id.upper())).fetchone()
            c.close()
            return orig_lookup(row[0] if row else rep, visit_date, system_id, db=db)
        visits.lookup = prefix
    elif name == "store_listall":  # T-0048: a list-all function appears on the store
        visits.list_visits = lambda db=None: visits.connect(db).execute("SELECT * FROM visits").fetchall()
    elif name == "load_lax":  # T-0048: Load visit file skips validation
        visits.parse_visit_file = lambda data: {"visit": {}, "outcomes": [], "payload": {}, "visit_key": "?"}
    elif name == "backup_empty":  # T-0048: the backup writes an empty database
        import sqlite3

        def empty(dest, db=None):
            sqlite3.connect(str(dest)).close()
            return Path(dest)
        visits.backup = empty
    elif name == "net":  # T-0049: the save path reaches for the network
        import importlib
        payload.urlreq = importlib.import_module("urllib.request")
        orig_write = visits._write_payload

        def phone_home(conn, key, p, now):
            try:
                payload.urlreq.urlopen("http://127.0.0.1:9/", timeout=0.2)
            except OSError:
                pass
            return orig_write(conn, key, p, now)
        visits._write_payload = phone_home
    elif name == "trainguard_visits":  # T-0051: the visit-record refusal and scan are gone
        orig_refuse = train_guard.refuse_training_input

        def lax(path, national_sha256=None):
            if Path(path).suffix in train_guard.VISIT_SUFFIXES or "lb-visit-file" in str(path):
                return None
            return orig_refuse(path, national_sha256)
        train_guard.refuse_training_input = lax
        train_guard.scan_for_visits = lambda root: []
    elif name == "ui_lookup":  # T-0059: the tab's lookup finds nothing
        visits.lookup = lambda *a, **k: None
    elif name == "ui_banner":  # T-0059: the banner is blank
        visits.BANNER = " "
    elif name == "ui_send":  # T-0059: the save action is labelled Send
        visits.LABELS = dict(visits.LABELS, save="Send to Salesforce")
    elif name == "ro_save":  # T-0060: the Save visit path loses its store-error catch (ValueError kept)
        from brief import visit_tab
        import streamlit as st

        def typed_unguarded(**kw):
            try:
                return visits.save_visit(**kw)
            except ValueError as e:
                st.error(f"Not saved: {e}")
            return None
        visit_tab._save_typed = typed_unguarded
    elif name == "ro_save_loaded":  # T-0060: the Save loaded visit path loses its catch (as in 6b0410d)
        from brief import visit_tab
        visit_tab._save_loaded = lambda **kw: visits.save_visit(**kw)
    elif name == "ro_store_errors":  # T-0060: no store error is caught anywhere in the tab
        from brief import visit_tab
        visit_tab.STORE_ERRORS = ()
    # v0.2-c voice notes (T-0046)
    elif name == "stt_nofallback":  # T-0046: decode and engine errors propagate instead of falling back to typed
        from brief import stt
        stt.transcribe_bytes = lambda tr, data: (tr.transcribe(stt.decode_wav(data)), "")
    elif name == "stt_none":  # T-0046: LB_STT=off or a missing engine still yields a transcriber (no typed-only mode)
        from brief import stt
        orig_get = stt.get_transcriber
        stt.get_transcriber = lambda: (orig_get()[0] or stt.Stub(), "")
    elif name == "stt_decode":  # T-0046: the WAV header is ignored (any rate, width or junk is decoded)
        import numpy as np
        from brief import stt
        stt.decode_wav = lambda data: np.frombuffer(data[44:len(data) - (len(data) - 44) % 2], "<i2").astype(np.float32) / 32768.0
    elif name == "stt_offline":  # T-0046: the model is loaded by name, so faster-whisper may download it
        from brief import stt

        def online(self):
            if self._m is None:
                from faster_whisper import WhisperModel
                self._m = WhisperModel(self.model, **stt.ENGINE_ARGS)
            return self._m
        stt.FasterWhisper._engine = online
    elif name == "stt_persist":  # T-0046: the raw recording is written next to the visit store
        from brief import stt
        orig_tb = stt.transcribe_bytes

        def persist(tr, data):
            p = visits.db_path().parent / "last-recording.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return orig_tb(tr, data)
        stt.transcribe_bytes = persist
    elif name == "stt_prefill":  # T-0046: the transcript never reaches the notes box
        from brief import stt
        stt.transcribe_bytes = lambda tr, data: ("", "")
    elif name == "stt_dedupe":  # T-0046: every rerun looks like a new recording, so it is transcribed again
        import itertools
        from brief import visit_tab
        n = itertools.count()
        visit_tab._recording_id = lambda data: f"rec-{next(n)}"
    elif name == "stt_cap":  # T-0046: the transcript is not cut to the notes limit
        from brief import visit_tab
        visit_tab._merge_notes = lambda typed, text: ((f"{typed.strip()}\n{text}" if typed.strip() else text), False)
    elif name == "lookup_fixed_key":  # T-0061: the lookup Company picker gets its old fixed key back (F-0025)
        from streamlit.elements.widgets.selectbox import SelectboxMixin
        orig_sb = SelectboxMixin.selectbox

        def fixed_key(self, *a, **k):
            if str(k.get("key", "")).startswith("vr_l_sid_"):
                k["key"] = "vr_l_sid"
            return orig_sb(self, *a, **k)
        SelectboxMixin.selectbox = fixed_key
    elif name == "upload_si":  # T-0062: the upload-limit check reads Caddy's MiB as MB (base 1000)
        from tools import upload_limit_check as ulc
        ulc.CADDY_UNITS = dict(ulc.CADDY_UNITS, mib=1000 ** 2, kib=1000, gib=1000 ** 3)
    elif name:
        raise ValueError(f"unknown REDPROOF mutation {name}")


def pytest_configure(config):  # noqa: F811 (pytest hook arg name is fixed)
    config.addinivalue_line("markers", "stt: real speech-to-text model; box and server only (T-0046)")
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


# --- v0.2-a client metrics fixtures (separate FactSheets: real_facts stays F1..F8 only) ---------------------------
@pytest.fixture(scope="session")
def metrics_national(tmp_path_factory):
    p = tmp_path_factory.mktemp("nat") / bm.NATIONAL_FILE
    metrics_fixture.national_rows().to_csv(p, index=False)
    return bm.national_profile(p)


@pytest.fixture(scope="session")
def metrics_df(tmp_path_factory):
    p = tmp_path_factory.mktemp("mfx") / "metrics_fixture.csv"
    metrics_fixture.synthetic_rows().to_csv(p, index=False)
    return clean.clean(load.load_csv(p))


@pytest.fixture(scope="session")
def metrics_facts(metrics_df, metrics_national):
    return client_metrics.compute_all(metrics_df, nat=metrics_national)


@pytest.fixture(scope="session")
def real_national():
    return bm.national_profile()


@pytest.fixture(scope="session")
def real_client(real_df, real_national):
    return client_metrics.compute_all(real_df, nat=real_national)
