"""T-0049 no Salesforce network (AS-0057 (sf payload is a database record, not a send)): the payload and store modules
import no HTTP, socket or Salesforce library, and a build-save-lookup round trip works with every socket connect
patched to raise. Mutation: net (the save path calls urllib.request.urlopen)."""
import ast
import socket
import types

import pytest

from brief import payload as pl, visit_tab, visits
from tests import visit_fixture as vf

BANNED = {"socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "websocket", "websockets",
          "simple_salesforce", "salesforce", "smtplib", "ftplib", "xmlrpc", "grpc"}
MODULES = (pl, visits, visit_tab)


@pytest.mark.parametrize("mod", MODULES, ids=lambda m: m.__name__)
def test_no_network_imports(mod):
    tree = ast.parse(open(mod.__file__).read())
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                 [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for n in names:
            assert n.split(".")[0] not in BANNED, f"{mod.__name__} imports {n}"
    for name, v in vars(mod).items():  # nothing network-shaped bound at runtime either
        if isinstance(v, types.ModuleType):
            assert v.__name__.split(".")[0] not in BANNED, f"{mod.__name__}.{name} = {v.__name__}"
        fmod = getattr(v, "__module__", "") or ""
        assert fmod.split(".")[0] not in BANNED, f"{mod.__name__}.{name} from {fmod}"
    src = open(mod.__file__).read().lower()
    assert "salesforce.com" not in src and "force.com" not in src and "https://" not in src


def test_round_trip_with_sockets_blocked(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "connect_ex", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    db = tmp_path / "v.db"
    res = visits.save_visit(db=db, **vf.visit())
    found = visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db)
    assert found["sha256"] == res["sha256"]
    visits.parse_visit_file(visits.visit_file(found))
