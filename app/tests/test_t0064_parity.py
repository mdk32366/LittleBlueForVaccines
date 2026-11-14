"""T-0064 (parity): every EXH1 figure the generator writes equals the app's own client_metrics fact for the same item
and level (value within 1e-9, status label exact), for all 180 systems; and the committed gen/out EXH1 TermSets are
byte-identical to an in-process regeneration. Mutations: exh_window, exh_peer_incl."""
import json
import math
import re
from pathlib import Path

import pytest

from brief import config
from tests import v1_gen

SFX = {"system": "", "state": "_state", "national": "_nat"}
TOL = 1e-9


def _fid(base, f):
    q = f["qualifier"]
    lvl, item = q["level"], q["item"]
    if base in ("exh_ratio", "exh_ratio_state", "nat_ratio"):
        return f"F13.{item.lower()}{SFX[lvl]}"
    if base in ("exh_r7_share", "exh_r7_share_state", "nat_r7_share"):
        return f"F13.r7_{q['part']}{SFX[lvl]}"
    if base in ("exh_private_share", "exh_private_share_state", "nat_private_share"):
        return f"F11.private_share{SFX[lvl]}"
    if base in ("exh_age_share", "exh_age_share_state", "nat_age_share"):
        return f"F12.{q['age']}_share{SFX[lvl]}"
    if base in ("exh_babies_total", "exh_babies_private", "exh_babies_public"):
        return f"F11.{base[4:]}"
    if base in ("exh_n_subs", "exh_n_subs_state"):
        return "F10.n_subs" + SFX[lvl]
    if base in ("exh_n_sites", "exh_n_sites_state"):
        return "F10.n_ddd" + SFX[lvl]
    return None


@pytest.fixture(scope="session")
def v1_inproc(tmp_path_factory):
    return v1_gen.regenerate(tmp_path_factory.mktemp("v1app") / "out")


def _exh_terms(root):
    return {p.name: p for p in sorted(Path(root).glob("*/docs/SYN-*-EXH1.terms.json"))}


def test_exhibit_figures_equal_app_facts(v1_inproc, real_client):
    checked, bad, seen = 0, [], set()
    for name, p in _exh_terms(v1_inproc).items():
        sid = name.split("-")[1]
        fs = real_client[sid].facts
        for k, f in json.loads(p.read_text())["fields"].items():
            fid = _fid(re.sub(r"-\d+$", "", k), f)
            if fid is None:
                continue
            seen.add(fid)
            st = f["qualifier"]["status"]
            app_st = fs.get(fid + "_st")
            if app_st is not None and app_st.value != st:
                bad.append((sid, k, fid, "status", st, app_st.value))
            if f["value"] is None:
                if fid in fs and st == "ok":
                    bad.append((sid, k, fid, "missing value", None, fs[fid].value))
                continue
            if fid not in fs:
                bad.append((sid, k, fid, "app has no value", f["value"], None))
                continue
            if not math.isclose(float(f["value"]), float(fs[fid].value), rel_tol=TOL, abs_tol=TOL):
                bad.append((sid, k, fid, "value", f["value"], fs[fid].value))
            checked += 1
    assert not bad, f"{len(bad)} parity breaks, e.g. {bad[:5]}"
    assert checked > 180 * 20, checked
    want = {f"F13.{r}{x}" for r in ("r1", "r2", "r3", "r4", "r5", "r6", "r7_flu_tdap", "r7_rsv_tdap",
                                     "r7_boostrix", "r7_flu", "r7_rsv") for x in SFX.values()}
    assert want <= seen, sorted(want - seen)  # the R1-R7 coverage this test claims, at all three levels


def test_committed_out_equals_inprocess(v1_inproc):
    new, old = _exh_terms(v1_inproc), _exh_terms(config.GEN_OUT)
    assert sorted(new) == sorted(old) and len(new) == 180
    diff = [n for n in new if new[n].read_bytes() != old[n].read_bytes()]
    assert not diff, diff[:5]
