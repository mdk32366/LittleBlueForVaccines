"""T-0079 dry-run no egress (extends T-0049 (no egress) to the v0.2-f modules, AS-0057, D-0045): sf_config,
sf_preview and integration_tab import no HTTP, socket or Salesforce library and bind none at runtime; the only
salesforce.com text is the instance URL pattern and the placeholder default; setup save, load, export, import and every
preview run with every socket call and urllib's urlopen patched to raise. Mutation: net_call (urlopen added to the
preview path)."""
import re
import socket
import types
import urllib.request

import pytest

from brief import integration_tab, payload as pl, sf_config, sf_preview, visits
from tests import visit_fixture as vf
from tests.test_t0049_no_egress import BANNED

MODULES = (sf_config, sf_preview, integration_tab)
ALLOWED_SF_LINES = {"sf_config": [  # the pattern, the placeholder default and the refusal message; nothing else
    'INSTANCE_URL_RE = re.compile(r"^https://[a-z0-9-]+\\.my\\.salesforce\\.com$")',
    'DEFAULT_INSTANCE_URL = "https://example.my.salesforce.com"  # placeholder; never contacted',
    'raise InvalidConfig("instance_url: must look like https://<name>.my.salesforce.com (lowercase, no path)")']}
HOSTISH = re.compile(r"force\\?\.com|https?://", re.I)


@pytest.mark.parametrize("mod", MODULES, ids=lambda m: m.__name__)
def test_no_network_imports(mod):
    import ast
    tree = ast.parse(open(mod.__file__).read())
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                 [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for n in names:
            assert n.split(".")[0] not in BANNED, f"{mod.__name__} imports {n}"
    for name, v in vars(mod).items():
        if isinstance(v, types.ModuleType):
            assert v.__name__.split(".")[0] not in BANNED, f"{mod.__name__}.{name} = {v.__name__}"
        fmod = getattr(v, "__module__", "") or ""
        assert fmod.split(".")[0] not in BANNED, f"{mod.__name__}.{name} from {fmod}"
    short = mod.__name__.rsplit(".", 1)[1]
    lines = [ln.strip() for ln in open(mod.__file__).read().splitlines() if HOSTISH.search(ln)]
    assert lines == ALLOWED_SF_LINES.get(short, []), lines
    assert "urlopen" not in open(mod.__file__).read()


def test_setup_and_preview_with_network_blocked(tmp_path, monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("network attempted")
    for obj, attr in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "create_connection"),
                      (socket, "getaddrinfo"), (urllib.request, "urlopen")):
        monkeypatch.setattr(obj, attr, boom)
    db = tmp_path / "v.db"
    sf_config.save_config({"instance_url": "https://example-dev.my.salesforce.com"}, db=db)
    cfg = sf_config.latest_config(db)["config"]
    assert sf_config.import_config(sf_config.export_config(cfg)) == cfg
    res = visits.save_visit(db=db, **vf.visit())
    reqs = sf_preview.build_requests(res["payload"], cfg)
    assert len(reqs) == 3 and all(r["url"].startswith("https://example-dev.my.salesforce.com/") for r in reqs)
    sf_preview.request_set_bytes(res["payload"], cfg, res["sha256"])
    with pytest.raises(sf_preview.NotPreviewable):
        sf_preview.build_requests(pl.build_payload_v02(**vf.visit()), cfg)
    assert calls == []
