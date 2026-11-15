"""T-0088 committed narrative hygiene (public repo): each narrative starts with the marker line
'FAKE-SYNTHETIC demo visit note: synthetic data, roles only.' and the marker leaves every hint result unchanged; the
narratives and expected.md hold no person names (an honorific / name-intro pattern list, plus the project's hygiene
names, kept here only as sha256 digests so the names themselves are not in the repo), no URL or hostname and no box
path. Each detector is checked on a planted sample first, so it can go red."""
import hashlib
import re

import pytest

from brief import payload as pl, talking
from tests import narratives_fixture as nf

CASES = nf.cases()
FILES = sorted(nf.DIR.glob("*.txt"))
NAME_SHA = {  # sha256 of each casefolded project hygiene name
    "4f31fa50e5bd5ff45684e560fc24aeee527a43739ab611c49c51098a33e2b469",
    "4ca6f6d5a544bf57c323657ad33aae1a019c775518cf4414beedb86962aea7c1",
    "934a11e602682e862b4b4d1f881ae8da1e097e3f6964bd780e5bb1fb798a6fdd",
    "f4aa0655cdb8d4fcf6f719c7a786de10556783c70bfb8ef1d78923482fe6ebbc",
    "4a2b5e1822ca11588586eb912320817f3cf0c11cd5ec8937e78a8209505f4e84",
    "1b232b3c131fc49e42a328285b77dbf602051fd1731dcac611b93bfc0764f8ba",
    "d2dae6d1b4625413eade8cafcb06d6d000fdb57d963fc3c5c497084d42288319",
    "47d9bb497099c29a05f74dc83894e6bfa64dacf3977ee777bd37f60d15059539",
    "ecd18c6a66631988cfa1ef186b61d729c1430c3e1a2503c3d83167a6d95f7b95",
}
NAME_PATTERNS = [re.compile(p) for p in (r"\b(?:Dr|Mr|Mrs|Ms|Mx|Miss|Prof)\b\.?\s+[A-Z]",
                                         r"\b(?:named|called|whose name is)\s+[A-Z][a-z]+",
                                         r"\b[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+\b")]
HOST = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|io|dev|app|ai|gov|edu|us)\b|@[a-z0-9-]+\.", re.I)
BOX_DIRS = ("work" "space", "ho" "me", "opt", "tmp", "root", "Users", "srv", "var")  # split so the repo's own hygiene
BOX_PATH = re.compile("/(?:" + "|".join(BOX_DIRS) + r")/|[A-Z]:\\\\")              # grep does not flag this detector


def _names(text: str, digests=NAME_SHA) -> list:
    words = set(re.findall(r"[a-z]+", text.casefold()))
    hits = [w for w in words if hashlib.sha256(w.encode()).hexdigest() in digests]
    return hits + [m.group(0) for p in NAME_PATTERNS for m in p.finditer(text)]


def _texts():
    return [(f.name, f.read_text()) for f in FILES] + [(nf.EXPECTED.name, nf.EXPECTED.read_text())]


def test_five_files_each_with_the_marker():
    assert [f.name[:2] for f in FILES] == ["01", "02", "03", "04", "05"]
    assert sorted(c["file"] for c in CASES.values()) == FILES
    for f in FILES:
        first, _, rest = f.read_text().partition("\n")
        assert first == nf.MARKER == "FAKE-SYNTHETIC demo visit note: synthetic data, roles only.", f.name
        assert rest.strip() and nf.MARKER not in rest


@pytest.mark.parametrize("n", sorted(CASES))
def test_marker_leaves_hints_unchanged(n, real_client):
    case = CASES[n]
    with_marker = nf.notes(case)
    without = with_marker.partition("\n")[2]
    for p in talking.payload_points(case["sid"], real_client):
        assert pl.hint_status(p, with_marker) == pl.hint_status(p, without), p.key


def test_detectors_go_red_on_planted_samples():
    planted = "zqxplanted"
    assert _names(f"Met {planted} today.", {hashlib.sha256(planted.encode()).hexdigest()}) == [planted]
    assert _names("Met Dr. Quillon at the site.") and _names("a lead named Quillon")
    assert HOST.search("see example.com") and HOST.search("https://x") and not HOST.search("Merck & Company")
    assert all(BOX_PATH.search(f"in /{d}/x") for d in BOX_DIRS) and not BOX_PATH.search("3/4 of doses")


def test_no_person_names_hosts_or_box_paths():
    for name, text in _texts():
        assert _names(text) == [], name
        assert not HOST.search(text), (name, HOST.search(text))
        assert not BOX_PATH.search(text), (name, BOX_PATH.search(text))
