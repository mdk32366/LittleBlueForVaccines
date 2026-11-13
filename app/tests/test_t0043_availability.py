"""T-0043 availability registry (spec §3.4): every client item has an entry at every level; NOT AVAILABLE items render
"not available: <reason>" and never a digit; the state column is labelled synthetic peers. Mutation: invent."""
import re

from brief import availability as av, client_metrics as cm

DIGIT = re.compile(r"\d")
# PR 6 note: R4 (the client's interim definition) and R6 (full RSV Vaccine subclass, older-adult proxy dropped)
# left the NOT AVAILABLE list per the client email 2026-11-13; the PR 5-era pins for them are updated here.
NA_KEYS = {"A1M.national", "A5.state", "A6.state", "A6.national", "A7.national", "A8.national", "A9.national",
           "SYSKEY.national", "UNIVERSE.national"}
DERIVED_KEYS = ({"A5.national", "A7.system", "A7.state", "A9.system", "A9.state"}
                | {f"{i}.{lvl}" for i in ("A10", "A11", "R4", "R5", "R6", "R7", "R7_FLU_TDAP", "R7_RSV_TDAP")
                   for lvl in av.LEVELS})
# every fact id the client metrics write for a level, by registry key (series facts included)
LEVEL_FACTS = {"A7.national": ["F10.n_subs_nat"], "A8.national": ["F10.n_ddd_nat"], "A9.national": []}


def test_every_item_has_an_entry_at_every_level():
    want = {f"A{i}" for i in range(1, 12)} | {"A1M"} | {f"R{i}" for i in range(1, 8)} | {"R7_FLU_TDAP", "R7_RSV_TDAP", "SYSKEY", "UNIVERSE", "HD"}
    assert set(av.ITEMS) == want
    assert set(av.REGISTRY) == {f"{i}.{lvl}" for i in want for lvl in av.LEVELS}
    for key, e in av.REGISTRY.items():
        assert e.status in (av.OK, av.DERIVED, av.NA), key
        assert e.reason and not DIGIT.search(e.reason), key  # reasons are digit-free


def test_not_available_and_derived_sets():
    assert {k for k, e in av.REGISTRY.items() if e.status == av.NA} == NA_KEYS
    assert {k for k, e in av.REGISTRY.items() if e.status == av.DERIVED} == DERIVED_KEYS
    assert isinstance(av.gate("A8.national", lambda: (1.0, "ok")), av.NotAvailable)  # never computed


def test_not_available_never_a_number(real_client, metrics_facts):
    for fsets in (real_client, metrics_facts):
        for fs in fsets.values():
            for key, fids in LEVEL_FACTS.items():
                for fid in fids:
                    assert fid not in fs.facts, (fs.system_id, fid)
                    assert fs.v(fid + "_st") == cm.NA_STATUS, (fs.system_id, fid)
            for k, f in fs.facts.items():  # no value fact behind a "not available" status
                if k.endswith("_st") and f.value == cm.NA_STATUS:
                    assert k[:-3] not in fs.facts, (fs.system_id, k)
            for item, fid in (("A7", "F10.n_subs_nat"), ("A8", "F10.n_ddd_nat"), ("A6", "F10.parent_state_nat")):
                txt = cm.cell(fs, item, "national", fid)
                assert txt == av.render_na(f"{item}.national") and not DIGIT.search(txt), (fs.system_id, txt)


def test_table_and_strip_render_not_available(real_client):
    fs = real_client["SYNCP000025"]
    rows = {r["metric"].split()[0]: r for r in cm.table_rows(fs)}
    assert "R6_OLDER" not in rows and rows["R4"]["system"] == "0.00"  # PR 6: R4 is computed (synthetic HepB Ped is 0)
    assert rows["A1M"][cm.NATIONAL_COLUMN].startswith("not available: ")
    assert not DIGIT.search(rows["A1M"][cm.NATIONAL_COLUMN])
    strip = {r["attribute"].split()[0]: r for r in cm.attribute_strip(fs)}
    assert strip["A1M"][cm.NATIONAL_COLUMN].startswith("not available: ")
    for item in ("A6", "A7", "A8", "A9"):
        assert strip[item][cm.NATIONAL_COLUMN].startswith("not available: ")
        assert not DIGIT.search(strip[item][cm.NATIONAL_COLUMN])
    assert strip["A8"]["system"] == "13"
    assert rows["R1"]["system"] == "0.62" and rows["R1"][cm.NATIONAL_COLUMN] == "0.55"


def test_column_labels():
    assert cm.STATE_COLUMN == "synthetic peers (state)" and cm.NATIONAL_COLUMN == "national (D-0034)"
    assert cm.TABLE_COLUMNS == ("metric", "system", "synthetic peers (state) (n)", "national (D-0034)",
                                "index vs state", "index vs national", "status")
    assert cm.LABEL == {"system": "system", "state": "synthetic peers", "national": "national"}
