"""T-0094 Bluebird flag OFF by default (D-0049): config.bluebird_on() is true only for LB_BLUEBIRD=on; with the flag
off the Visit record tab is today's tab (Customer response defaults to Neutral, no Bluebird button or caption), app.py
imports the client only behind the flag, and no deploy-shaped file in the repository turns the flag on.
Mutation: bb_default_on."""
import ast
import re
from pathlib import Path

import pytest

from brief import config, visit_tab
from tests import narratives_fixture as nf

REPO = Path(__file__).resolve().parents[2]
APP = Path(nf.APP)


@pytest.mark.parametrize("env,on", [({}, False), ({"LB_BLUEBIRD": ""}, False), ({"LB_BLUEBIRD": "off"}, False),
                                    ({"LB_BLUEBIRD": "1"}, False), ({"LB_BLUEBIRD": "true"}, False),
                                    ({"LB_BLUEBIRD": "on"}, True), ({"LB_BLUEBIRD": " ON "}, True)])
def test_flag_values(env, on):
    assert config.bluebird_on(env) is on


def test_llm_mode_still_off():
    assert config.LLM_MODE == "off"


def test_apptest_flag_off_is_todays_tab(tmp_path, monkeypatch):
    monkeypatch.delenv("LB_BLUEBIRD", raising=False)
    monkeypatch.delenv("LB_BLUEBIRD_URL", raising=False)
    case = nf.cases()["01"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    n = len(case["rows"])
    assert [at.selectbox(key=f"vr_resp_{case['sid']}_{i}").value for i in range(n)] == ["Neutral"] * n
    assert visit_tab.BB_BUTTON_KEY not in [b.key for b in at.button]
    caps = [c.value for c in at.caption]
    assert visit_tab.BB["caption"] not in caps and visit_tab.BB["label"] not in caps
    assert not any(visit_tab.BB["pick"] in w.value for w in at.warning)


def test_app_imports_client_only_behind_flag():
    tree = ast.parse(APP.read_text())
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    found = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any("bluebird" in a.name for a in node.names):
            found += 1
            up = node
            while up in parents and not (isinstance(up, ast.If) and "bluebird_on" in ast.unparse(up.test)):
                up = parents[up]
            assert isinstance(up, ast.If), f"line {node.lineno}: bluebird imported outside the flag check"
    assert found == 1


DEPLOY = re.compile(r"(compose[^/]*\.ya?ml|\.env[^/]*|Dockerfile[^/]*|\.github/workflows/[^/]+\.ya?ml)$")
TURNS_ON = re.compile(r"LB_BLUEBIRD\s*[:=]\s*[\"']?on\b", re.IGNORECASE)


def test_no_deploy_file_turns_the_flag_on():
    files = [p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts
             and DEPLOY.search(p.relative_to(REPO).as_posix())]
    assert TURNS_ON.search("environment:\n  LB_BLUEBIRD: \"on\"")  # the detector flags a planted line
    for p in files:
        assert not TURNS_ON.search(p.read_text(errors="replace")), p.relative_to(REPO).as_posix()
