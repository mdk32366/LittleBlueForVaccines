"""T-0065 (national used as specified; replaces T-0025 for gen, D-0042 (T-0025 retired for gen)). The national file
feeds the generator as pooled totals only (D-0041 (national file is generator and training input)): the manifest
records its sha256, EXH1 states the app's national pins in §11-12 for every system, the generator raises on a missing
or altered file, only the listed columns are read, and no national row is copied into gen/out."""
import hashlib
import shutil

import pytest

from bia562gen import national as NAT
from bia562gen.specs.schema_v1 import SchemaV1Spec

from .v1_helpers import docs, terms

SPEC_COLUMNS = ("MTH_ID", "PROD_NM", "MFR_NM", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "VAC_AGE_GRP_NM",
                "BAC_CHNL_SPEC_DESC", "BAC_CORP_PAR_ORG_TYP_DESC", "DOSES", "DOLLARS")  # spec §4, verbatim
# The app's pins (spec §4; app/tests T-0042 / T-0055..T-0058): R1-R6, the two R7 ratios over Tdap, private share
PINS = {"R1": 0.5483, "R2": 1.2570, "R3": 5.6960, "R4": 0.5956, "R5": 0.1928, "R6": 0.0802,
        "R7_FLU_TDAP": 0.3452, "R7_RSV_TDAP": 0.2629}
PRIVATE_SHARE = 0.641
NAT_ROWS = 45462


def test_manifest_benchmark_source(v1_out):
    import json
    m = json.loads((v1_out / "manifest.json").read_text())
    bs = m["benchmark_source"]
    assert bs.get("sha256") == hashlib.sha256(NAT.DEFAULT_PATH.read_bytes()).hexdigest() == NAT.RECORDED_SHA256
    assert bs["rows"] == NAT_ROWS and bs["file"] == NAT.NATIONAL_FILE
    assert m["systems_source"]["sha256"] != bs["sha256"]


def test_national_pins_in_every_exhibit(v1_out):
    ex = terms(v1_out, "EXH")
    assert len(ex) == 180
    first = None
    for sid, f in ex.items():
        nat = {k: (v["value"], v["span"], v["qualifier"]) for k, v in f.items() if v["source"]["anchor"].split(".")[0] == "11"}
        ratios = {v[2]["item"]: v[0] for k, v in nat.items() if k.startswith("nat_ratio-")}
        assert {k: round(v, 4) for k, v in ratios.items()} == PINS, sid
        assert round(nat["nat_private_share"][0] / 100, 3) == PRIVATE_SHARE, sid
        first = first or nat
        assert nat == first, f"{sid}: national figures differ between systems"
    for did, (_m, secs) in docs(v1_out, "EXH").items():
        assert "11" in secs and "12" in secs, did
        assert any("National R1 " in s["text"] for a, s in secs.items() if a.split(".")[0] == "11"), did


def test_missing_national_file_raises(tmp_path):
    with pytest.raises(NAT.NationalInputError, match="missing"):
        SchemaV1Spec(national_path=tmp_path / NAT.NATIONAL_FILE)


def test_altered_national_file_raises(tmp_path):
    p = tmp_path / NAT.NATIONAL_FILE
    p.write_bytes(NAT.DEFAULT_PATH.read_bytes() + b"\n")
    with pytest.raises(NAT.NationalInputError, match="sha256"):
        SchemaV1Spec(national_path=p)


def test_only_listed_columns_are_read(tmp_path):
    assert tuple(NAT.USED_COLUMNS) == SPEC_COLUMNS
    assert "SEASON_DESC" not in NAT.USED_COLUMNS and "VAC_FRZ_IND" not in NAT.USED_COLUMNS
    # functional: scrambling the unused columns changes nothing the generator sees
    import csv
    src = NAT.DEFAULT_PATH
    dst = tmp_path / "scrambled.csv"
    with open(src, newline="", encoding="utf-8-sig") as f, open(dst, "w", newline="", encoding="utf-8") as g:
        r = csv.DictReader(f)
        w = csv.DictWriter(g, r.fieldnames)
        w.writeheader()
        for i, row in enumerate(r):
            row["SEASON_DESC"], row["VAC_FRZ_IND"] = f"S{i % 7}", str(i % 2)
            w.writerow(row)
    assert NAT.load(dst, expected_sha256=None)["pooled"] == NAT.load()["pooled"]


def test_no_national_row_copied(v1_out):
    rows = set(NAT.DEFAULT_PATH.read_text(encoding="utf-8-sig").splitlines()[1:])
    assert len(rows) > 40000
    for p in sorted(v1_out.rglob("*")):
        if p.is_file():
            hit = rows.intersection(p.read_text().splitlines())
            assert not hit, f"{p.name} carries a national row"


def test_spec_constructor_is_fail_closed_copy(tmp_path):
    """A byte-identical copy at another path is the national file by its sha256 and is accepted."""
    p = tmp_path / "copy.csv"
    shutil.copy(NAT.DEFAULT_PATH, p)
    assert SchemaV1Spec(national_path=p).nat["source"]["sha256"] == NAT.RECORDED_SHA256
