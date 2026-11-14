"""sf_config.py (v0.2-f): the Salesforce dry-run setup. NON-SECRET fields only, stored append-only in the app DB.

D-0045 (Salesforce dry run): the owner chose "Save setup in the app DB, non-secret fields only". AS-0071 (dry-run setup,
non-secret fields only) lists the fields; every __c and __r name in them is a proposal (AS-0070).
- The setup is validated against schemas/sf_integration_config.schema.json (JSON Schema 2020-12,
  additionalProperties: false). The instance URL must match INSTANCE_URL_RE; the default is the placeholder
  DEFAULT_INSTANCE_URL, which is never contacted (nothing in the app opens a connection: T-0079).
- Any value that looks like a credential is refused (`looks_secret`): a JWT, a long base64 or hex run, the word
  Bearer, or an org session id (00D... followed by "!"). There is no password-type input anywhere (T-0080).
- `sf_integration_config` rows are append-only (triggers refuse UPDATE and DELETE); the latest row is the setup in
  use. There is no secret column (T-0077 pins the columns). JSON export and import use the same validation.
- The auth method is display only: nothing is configured, and no credential can be entered or stored.
This module imports no HTTP, socket or Salesforce library (T-0079).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import jsonschema

from . import payload as pl, visits

CONFIG_VERSION = "lb-sf-config-0.1"
SCHEMA_PATH = pl.SCHEMA_PATH.parent / "sf_integration_config.schema.json"
INSTANCE_URL_RE = re.compile(r"^https://[a-z0-9-]+\.my\.salesforce\.com$")
DEFAULT_INSTANCE_URL = "https://example.my.salesforce.com"  # placeholder; never contacted
DEFAULT_API_VERSION = "62.0"  # AS-0071: a documented default (Salesforce REST API v62.0); only shown in the preview URL
API_VERSION_RE = re.compile(r"^[1-9][0-9]\.0$")
RECORD_TYPE_RE = re.compile(r"^([A-Za-z0-9]{15}|[A-Za-z0-9]{18})?$")
AUTH_METHOD_DISPLAY = ("OAuth 2.0 JWT bearer flow (planned). Not configured: this app stores no credentials and has "
                       "no field to enter one.")
OWNER_MAPPINGS = ("<NOT MAPPED: records stay with the integration user>",
                  "<PLACEHOLDER: rep key to a Salesforce user, not configured>")
FIELDS = ("instance_url", "api_version", "visit_object", "outcome_object", "outcome_relationship",
          "account_relationship", "account_external_id_field", "record_type_id", "owner_mapping")
DEFAULTS = {"lb_config_version": CONFIG_VERSION, "instance_url": DEFAULT_INSTANCE_URL,
            "api_version": DEFAULT_API_VERSION, "visit_object": pl.ROOT_OBJECT,
            "outcome_object": "Talking_Point_Outcome__c", "outcome_relationship": pl.CHILD_REL,
            "account_relationship": pl.ACCOUNT_REL, "account_external_id_field": pl.ACCOUNT_EXT_ID,
            "record_type_id": "", "owner_mapping": OWNER_MAPPINGS[0]}
LABELS = {"instance_url": "Instance URL (placeholder; never contacted)", "api_version": "API version",
          "visit_object": "Visit object API name", "outcome_object": "Talking point outcome object API name",
          "outcome_relationship": "Outcomes relationship name (master-detail, on the visit)",
          "account_relationship": "Account relationship name (on the visit)",
          "account_external_id_field": "Account external-id field (matched on the system id)",
          "record_type_id": "Record type id (optional, 15 or 18 characters)",
          "owner_mapping": "Owner mapping (placeholder)",
          "save": "Save setup (non-secret fields only)", "download": "Download setup (.json)",
          "load": "Load setup file (.json)", "save_loaded": "Save loaded setup"}
SECRET_NAME_RE = re.compile(r"secret|token|passw|pwd|credential|private|session|bearer|api_?key|client_?id|consumer|"
                            r"auth|cert|signing|refresh", re.I)  # no config field or column may be named like this

_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*|"
                  r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_HEX = re.compile(r"[0-9a-fA-F]{32,}")
_B64 = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_BEARER = re.compile(r"\bbearer\b", re.I)
_SESSION = re.compile(r"00D[A-Za-z0-9]{12,15}!")
_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z ]*(PRIVATE )?KEY-----|\bsk-[A-Za-z0-9]{16,}")

DDL = """
CREATE TABLE IF NOT EXISTS sf_integration_config (
  id             INTEGER PRIMARY KEY,
  created_at     TEXT NOT NULL,
  config_version TEXT NOT NULL,
  config_json    TEXT NOT NULL,
  sha256         TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS sf_integration_config_no_update BEFORE UPDATE ON sf_integration_config
  BEGIN SELECT RAISE(ABORT, 'sf_integration_config rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS sf_integration_config_no_delete BEFORE DELETE ON sf_integration_config
  BEGIN SELECT RAISE(ABORT, 'sf_integration_config rows are append-only'); END;
"""


class InvalidConfig(ValueError):
    pass


def looks_secret(value) -> bool:
    """True when a value looks like a credential: a JWT, a long base64 or hex run, 'Bearer', an org session id
    (00D...!) or a key block. API names (letters, digits, single underscores, a __c/__r suffix) never match."""
    s = str(value or "")
    if _BEARER.search(s) or _SESSION.search(s) or _JWT.search(s) or _HEX.search(s) or _KEY_BLOCK.search(s):
        return True
    for run in _B64.findall(s):
        mixed = any(c.isdigit() for c in run) + any(c.islower() for c in run) + any(c.isupper() for c in run)
        if mixed >= 2 and "__" not in run:
            return True
    return False


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validate(cfg: dict) -> dict:
    """Return the setup as stored (defaults filled for missing keys) or raise InvalidConfig. Order: the credential
    check on every value, the instance URL pattern, then the JSON Schema."""
    if not isinstance(cfg, dict):
        raise InvalidConfig("setup must be a JSON object")
    full = {**DEFAULTS, **{k: v for k, v in cfg.items()}}
    for k, v in full.items():
        if looks_secret(v) or looks_secret(k):
            raise InvalidConfig(f"{k}: refused, the value looks like a token, key or password. This dry run stores "
                                "no credentials.")
    for k in FIELDS:
        if isinstance(full[k], str):
            full[k] = full[k].strip()
    if not INSTANCE_URL_RE.match(str(full["instance_url"])):
        raise InvalidConfig("instance_url: must look like https://<name>.my.salesforce.com (lowercase, no path)")
    try:
        jsonschema.validate(full, schema(), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        raise InvalidConfig(f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}") from None
    names = [full[k] for k in ("visit_object", "outcome_object", "outcome_relationship", "account_relationship",
                               "account_external_id_field")]
    if len(set(names)) != len(names):
        raise InvalidConfig("object, relationship and field API names must all differ")
    return full


def canonical(cfg: dict) -> str:
    return json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256(cfg: dict) -> str:
    return hashlib.sha256(canonical(cfg).encode()).hexdigest()


def connect(db=None):
    conn = visits.connect(db)
    conn.executescript(DDL)
    return conn


def save_config(cfg: dict, db=None) -> dict:
    """Validate and append the setup as a new row. Returns id, sha256 and the stored setup."""
    full = validate(cfg)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = connect(db)
    try:
        with conn:
            cur = conn.execute("INSERT INTO sf_integration_config (created_at, config_version, config_json, sha256) "
                               "VALUES (?, ?, ?, ?)", (now, CONFIG_VERSION, canonical(full), sha256(full)))
            rid = cur.lastrowid
    finally:
        conn.close()
    return {"id": rid, "sha256": sha256(full), "config": full, "created_at": now}


def latest_config(db=None) -> dict:
    """The newest stored setup, or the defaults (id None) when none is stored. A stored row is re-validated."""
    if not visits.db_path(db).exists():
        return {"id": None, "config": dict(DEFAULTS), "sha256": sha256(DEFAULTS), "created_at": None}
    conn = connect(db)
    try:
        row = conn.execute("SELECT * FROM sf_integration_config ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    if row is None:
        return {"id": None, "config": dict(DEFAULTS), "sha256": sha256(DEFAULTS), "created_at": None}
    cfg = validate(json.loads(row["config_json"]))
    return {"id": row["id"], "config": cfg, "sha256": row["sha256"], "created_at": row["created_at"]}


def export_config(cfg: dict) -> bytes:
    """'Download setup (.json)': the validated setup, nothing else."""
    return (json.dumps(validate(cfg), indent=2, ensure_ascii=False) + "\n").encode()


def import_config(data: bytes) -> dict:
    """'Load setup file': JSON, every key known, the credential check, the URL pattern and the schema."""
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError) as e:
        raise InvalidConfig(f"not JSON: {e}") from None
    if not isinstance(doc, dict):
        raise InvalidConfig("setup must be a JSON object")
    unknown = sorted(set(doc) - set(DEFAULTS))
    if unknown:
        raise InvalidConfig(f"unknown setup fields: {', '.join(unknown)}")
    return validate(doc)
