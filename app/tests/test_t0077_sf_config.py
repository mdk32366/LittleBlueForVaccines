"""T-0077 dry-run setup (D-0045 (Salesforce dry run), AS-0071 (dry-run setup, non-secret fields only)): the defaults
validate and the instance URL default is the placeholder; an off-pattern instance URL is refused; any token-shaped
value (JWT, long base64 or hex, Bearer, 00D...! session id, key block) is refused in every field; the record type id
is 15 or 18 alphanumeric characters; the schema and the table have no secret field or column; sf_integration_config is
append-only and the latest row is in use; JSON export and import round-trip and refuse unknown or secret fields.
Mutations: secret_ok (a token-shaped value accepted), secret_col (a secret column added to the config schema),
url_lax (an off-pattern instance URL accepted)."""
import json
import re
import sqlite3

import pytest

from brief import sf_config as sc

TOKENS = ["eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJkZW1vIiwic3ViIjoiZGVtbyJ9.c2lnbmF0dXJlLWZha2UtZm9yLXRlc3Rz",
          "Bearer abc123", "bearer x", "00D000000000001!AQ0AQFakeSessionValueForTestsOnly000",
          "0123456789abcdef0123456789abcdef", "QWxhZGRpbjpvcGVuIHNlc2FtZQ9xY3ZhbHVlZm9ydGVzdHM=",
          "-----BEGIN PRIVATE KEY-----", "sk-0123456789abcdefABCDEF"]
BAD_URLS = ["http://example.my.salesforce.com", "https://Example.my.salesforce.com", "https://example.my.salesforce.com/",
            "https://example.my.salesforce.com/services", "https://example.salesforce.com",
            "https://example.lightning.force.com", "https://example.my.salesforce.com.evil.test",
            "https://evil.test/.my.salesforce.com", "https://ex_ample.my.salesforce.com", "https://.my.salesforce.com",
            "https://example.my.salesforce.com:8443", "https://user@example.my.salesforce.com", ""]


@pytest.fixture
def db(tmp_path):
    return tmp_path / "visits.db"


def test_defaults_and_placeholder():
    cfg = sc.validate({})
    assert cfg == sc.DEFAULTS and set(cfg) == set(sc.FIELDS) | {"lb_config_version"}
    assert cfg["instance_url"] == sc.DEFAULT_INSTANCE_URL == "https://example.my.salesforce.com"
    assert cfg["api_version"] == sc.DEFAULT_API_VERSION == "62.0"
    assert (cfg["visit_object"], cfg["outcome_relationship"]) == ("Visit__c", "Talking_Point_Outcomes__r")
    assert cfg["owner_mapping"].startswith("<") and cfg["record_type_id"] == ""
    assert "no credentials" in sc.AUTH_METHOD_DISPLAY and "auth_method" not in cfg  # display only, never stored


def test_instance_url_pattern():
    for good in ("https://example.my.salesforce.com", "https://example-dev-ed.my.salesforce.com",
                 "https://a1.my.salesforce.com"):
        assert sc.validate({"instance_url": good})["instance_url"] == good
    for bad in BAD_URLS:
        with pytest.raises(sc.InvalidConfig):
            sc.validate({"instance_url": bad})
    assert sc.INSTANCE_URL_RE.pattern == r"^https://[a-z0-9-]+\.my\.salesforce\.com$"


@pytest.mark.parametrize("field", ["instance_url", "api_version", "visit_object", "outcome_object",
                                   "outcome_relationship", "outcome_parent_field", "account_relationship", "account_external_id_field",
                                   "record_type_id", "owner_mapping"])
def test_secret_values_refused(field):
    for tok in TOKENS:
        assert sc.looks_secret(tok), tok
        with pytest.raises(sc.InvalidConfig, match="looks like a token"):
            sc.validate({field: tok})
    for name in ("Visit__c", "Talking_Point_Outcomes__r", "LB_System_Id__c", "012000000000000AAA",
                 "https://example.my.salesforce.com", "62.0", sc.OWNER_MAPPINGS[1]):
        assert not sc.looks_secret(name), name


def test_record_type_and_names():
    assert sc.validate({"record_type_id": "012000000000000"})["record_type_id"] == "012000000000000"
    assert sc.validate({"record_type_id": "012000000000000AAA"})["record_type_id"] == "012000000000000AAA"
    for bad in [{"record_type_id": "0120000000000000"}, {"record_type_id": "012-00000000000"},
                {"api_version": "62"}, {"api_version": "v62.0"}, {"visit_object": "Visit"},
                {"outcome_relationship": "Outcomes__c"}, {"account_external_id_field": "Ext Id__c"},
                {"outcome_object": "Visit__c"}, {"owner_mapping": "someone"}, {"auth_method": "jwt"}, []]:
        with pytest.raises(sc.InvalidConfig):
            sc.validate(bad)


def test_no_secret_fields_or_columns(db):
    sch = sc.schema()
    assert sch["additionalProperties"] is False
    props = set(sch["properties"])
    assert props == set(sc.DEFAULTS), props ^ set(sc.DEFAULTS)
    assert not [p for p in props if sc.SECRET_NAME_RE.search(p)], props
    conn = sc.connect(db)
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(sf_integration_config)")]
    finally:
        conn.close()
    assert cols == ["id", "created_at", "config_version", "config_json", "sha256"], cols
    assert not [c for c in cols if sc.SECRET_NAME_RE.search(c)]
    with pytest.raises(sc.InvalidConfig):  # the schema itself refuses an extra field
        sc.validate({"client_secret": "x"})


def test_store_append_only_and_latest(db):
    assert sc.latest_config(db)["id"] is None and sc.latest_config(db)["config"] == sc.DEFAULTS
    a = sc.save_config({"instance_url": "https://example-dev.my.salesforce.com"}, db=db)
    b = sc.save_config({"instance_url": "https://example-uat.my.salesforce.com", "record_type_id": "012000000000000"},
                       db=db)
    latest = sc.latest_config(db)
    assert latest["id"] == b["id"] > a["id"] and latest["config"]["instance_url"].startswith("https://example-uat.")
    assert latest["sha256"] == sc.sha256(latest["config"]) == b["sha256"]
    with pytest.raises(sc.InvalidConfig):
        sc.save_config({"record_type_id": TOKENS[0]}, db=db)
    c = sqlite3.connect(db)
    try:
        assert c.execute("SELECT COUNT(*) FROM sf_integration_config").fetchone()[0] == 2
        for sql in ("UPDATE sf_integration_config SET config_json = '{}'", "DELETE FROM sf_integration_config"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)
    finally:
        c.close()
    src = open(sc.__file__).read()  # the config store reads its own table only (the visit store stays unlisted)
    sel = [ln for ln in src.splitlines() if "SELECT" in ln and "FROM" in ln and "RAISE" not in ln]
    assert sel and all("FROM sf_integration_config" in ln for ln in sel), sel


def test_export_import_round_trip():
    cfg = sc.validate({"instance_url": "https://example-dev.my.salesforce.com", "owner_mapping": sc.OWNER_MAPPINGS[1]})
    data = sc.export_config(cfg)
    assert sc.import_config(data) == cfg and json.loads(data) == cfg
    for bad in (b"not json", b"[]", json.dumps(dict(cfg, client_secret="x")).encode(),
                json.dumps(dict(cfg, record_type_id=TOKENS[1])).encode(),
                json.dumps(dict(cfg, instance_url="https://example.test")).encode()):
        with pytest.raises(sc.InvalidConfig):
            sc.import_config(bad)
    assert not re.search(r"secret|token|password", data.decode(), re.I)
