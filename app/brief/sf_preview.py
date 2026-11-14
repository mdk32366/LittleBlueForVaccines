"""sf_preview.py (v0.2-f): 'Preview Salesforce request'. A pure function of (stored payload, latest setup) that shows
the sObject Tree requests a real integration would make. Nothing is sent, and this module can't send: it imports no
HTTP, socket or Salesforce library (T-0079), and it only builds strings and dicts.

D-0045 (Salesforce dry run). One request per tree in the stored lb-sf-tree-0.3 payload (AS-0070), in TREE_ORDER:
  POST {instance}/services/data/v{api}/composite/tree/{Visit__c | Event | Task}
  Authorization: Bearer <NOT CONFIGURED>      Content-Type: application/json
The body is the stored tree. With the default setup it is that tree exactly; a setup that renames an object,
relationship or the Account external-id field renames those keys and attribute types only, and a record type id adds
RecordTypeId to the Visit__c record. `stored_tree` undoes both, so T-0078 can check every preview body against the
stored payload's sha256. A 0.2 payload (Event root) is shown as stored, without a preview (NotPreviewable).
"""
from __future__ import annotations

import json

from . import payload as pl, sf_config

BANNER = "DRY RUN. Nothing is sent. No credentials are stored."
AUTH_PLACEHOLDER = "Bearer <NOT CONFIGURED>"
HEADERS = (("Authorization", AUTH_PLACEHOLDER), ("Content-Type", "application/json"))
SET_VERSION = "lb-sf-dryrun-requests-0.1"
LABELS = {"panel": "Preview Salesforce request", "download": "Download request set (.json)"}


class NotPreviewable(ValueError):
    pass


def _renames(cfg: dict) -> tuple[dict, dict]:
    """(key renames, attributes.type renames) from the payload's proposed names to the setup's names."""
    keys = {pl.CHILD_REL: cfg["outcome_relationship"], pl.ACCOUNT_REL: cfg["account_relationship"],
            pl.ACCOUNT_EXT_ID: cfg["account_external_id_field"]}
    types = {pl.ROOT_OBJECT: cfg["visit_object"], "Talking_Point_Outcome__c": cfg["outcome_object"]}
    return keys, types


def _walk(node, keys: dict, types: dict):
    if isinstance(node, list):
        return [_walk(x, keys, types) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        nk = keys.get(k, k)
        if nk in out or (nk != k and nk in node):
            raise sf_config.InvalidConfig(f"setup name {nk} collides with a payload field")
        if k == "attributes" and isinstance(v, dict) and "type" in v:
            v = dict(v, type=types.get(v["type"], v["type"]))
        out[nk] = _walk(v, keys, types)
    return out


def _names(node, keys: set, types: set) -> None:
    if isinstance(node, list):
        for x in node:
            _names(x, keys, types)
    elif isinstance(node, dict):
        for k, v in node.items():
            keys.add(k)
            if k == "attributes" and isinstance(v, dict) and "type" in v:
                types.add(v["type"])
            _names(v, keys, types)


def _check_renames(tree: dict, keys: dict, types: dict) -> None:
    """A setup name may not already be a field or type anywhere in the tree, so the rename stays one-to-one and
    stored_tree can undo it exactly."""
    have_k, have_t = set(), set()
    _names(tree, have_k, have_t)
    for src, dst in list(keys.items()) + list(types.items()):
        if dst != src and (dst in have_k or dst in have_t):
            raise sf_config.InvalidConfig(f"setup name {dst} collides with a payload field or object")


def _body(tree: dict, root: str, cfg: dict) -> dict:
    keys, types = _renames(cfg)
    _check_renames(tree, keys, types)
    body = _walk(tree, keys, types)
    if root == pl.ROOT_OBJECT and cfg.get("record_type_id"):
        for r in body["records"]:
            r["RecordTypeId"] = cfg["record_type_id"]
    return body


def stored_tree(body: dict, root: str, cfg: dict) -> dict:
    """The inverse of _body: the stored tree this preview body came from."""
    keys, types = _renames(cfg)
    body = json.loads(json.dumps(body))
    if root == pl.ROOT_OBJECT:
        for r in body["records"]:
            r.pop("RecordTypeId", None)
    return _walk(body, {v: k for k, v in keys.items()}, {v: k for k, v in types.items()})


def _object(root: str, cfg: dict) -> str:
    return cfg["visit_object"] if root == pl.ROOT_OBJECT else root


def url(root: str, cfg: dict) -> str:
    return f"{cfg['instance_url']}/services/data/v{cfg['api_version']}/composite/tree/{_object(root, cfg)}"


def _sh(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def curl(req: dict) -> str:
    """The curl equivalent, with the placeholder token. Shown as text only; never run."""
    hdr = " \\\n  ".join(f"-H {_sh(f'{k}: {v}')}" for k, v in req["headers"].items())
    return (f"curl -X {req['method']} {_sh(req['url'])} \\\n  {hdr} \\\n  "
            f"--data-binary {_sh(json.dumps(req['body'], ensure_ascii=False, separators=(',', ':')))}")


def build_requests(payload: dict, cfg: dict) -> list[dict]:
    """Every request for a stored 0.3 payload, in TREE_ORDER. Pure: no clock, no store, no network."""
    if not isinstance(payload, dict) or payload.get("lb_schema_version") != pl.SCHEMA_VERSION:
        version = payload.get("lb_schema_version") if isinstance(payload, dict) else None
        raise NotPreviewable(f"this record was saved as {version} (Event root); re-save the visit to preview the "
                             f"{pl.SCHEMA_VERSION} requests")
    pl.validate(payload)
    cfg = sf_config.validate(cfg)
    out = []
    for root in pl.TREE_ORDER:
        if root not in payload["trees"]:
            continue
        req = {"root": root, "method": "POST", "url": url(root, cfg), "headers": dict(HEADERS),
               "body": _body(payload["trees"][root], root, cfg)}
        req["curl"] = curl(req)
        out.append(req)
    return out


def request_set(payload: dict, cfg: dict, stored_sha256: str | None = None) -> dict:
    """The full request set (the download). Refuses a payload whose sha256 is not the stored one."""
    sha = pl.sha256(payload)
    if stored_sha256 is not None and sha != stored_sha256:
        raise NotPreviewable("the payload does not match its stored sha256")
    cfg = sf_config.validate(cfg)
    return {"lb_marker": pl.FAKE_MARKER, "lb_request_set": SET_VERSION, "dry_run": True, "banner": BANNER,
            "lb_visit_key": payload.get("lb_visit_key"), "payload_sha256": sha,
            "lb_schema_version": payload.get("lb_schema_version"), "setup": cfg,
            "requests": [{k: r[k] for k in ("root", "method", "url", "headers", "body")} for r in build_requests(payload, cfg)]}


def request_set_bytes(payload: dict, cfg: dict, stored_sha256: str | None = None) -> bytes:
    return (json.dumps(request_set(payload, cfg, stored_sha256), indent=2, ensure_ascii=False) + "\n").encode()
