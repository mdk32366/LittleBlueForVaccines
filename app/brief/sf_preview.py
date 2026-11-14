"""sf_preview.py (v0.2-f; one Composite request since 6c): 'Preview Salesforce request'. A pure function of (stored
payload, latest setup) that shows the request a real integration would make. Nothing is sent, and this module can't
send: it imports no HTTP, socket or Salesforce library (T-0079), and it only builds strings and dicts.

D-0046 (one Composite request, allOrNone): the stored lb-sf-tree-0.3 payload (AS-0070) becomes ONE request,
  POST {instance}/services/data/v{api}/composite
  Authorization: Bearer <NOT CONFIGURED>      Content-Type: application/json
  {"allOrNone": true, "compositeRequest": [subrequests, in order]}
AS-0072 (composite subrequest mapping) gives the order and the bodies:
  1. POST /services/data/v{api}/sobjects/{visit object}, referenceId "visit": the Visit__c record without its
     attributes and children (Account by the external-id relationship on the system id, as stored);
  2. one POST per Talking_Point_Outcome__c child, referenceId tp{i}: the child record with the master-detail field
     ({outcome_parent_field}) set to @{visit.id};
  3. the Event, then each Task, with WhatId @{visit.id} as stored.
All names come from the setup (sf_config). At most COMPOSITE_MAX (25) subrequests; more is refused (TooManySubrequests).
`check_composite` refuses a request whose first subrequest is not the visit, whose other subrequests do not point at
@{visit.id}, or whose allOrNone is not true. `stored_trees` undoes the mapping, so T-0078 rebuilds the stored payload's
sha256 from the request body (the body_drift guarantee). A 0.2 payload (Event root) is shown as stored, without a
preview (NotPreviewable).
"""
from __future__ import annotations

import json

from . import payload as pl, sf_config

BANNER = "DRY RUN. Nothing is sent. No credentials are stored."
AUTH_PLACEHOLDER = "Bearer <NOT CONFIGURED>"
HEADERS = (("Authorization", AUTH_PLACEHOLDER), ("Content-Type", "application/json"))
SET_VERSION = "lb-sf-dryrun-requests-0.2"  # 6c: one Composite request (0.1: one tree request per root)
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


COMPOSITE_MAX = 25  # Salesforce Composite: at most 25 subrequests in one request
ALL_OR_NONE = True  # one failed subrequest rolls back the whole visit


class TooManySubrequests(NotPreviewable):
    pass


def _api(cfg: dict) -> str:
    return f"/services/data/v{cfg['api_version']}"


def url(cfg: dict) -> str:
    return f"{cfg['instance_url']}{_api(cfg)}/composite"


def _sobject_url(obj: str, cfg: dict) -> str:
    return f"{_api(cfg)}/sobjects/{obj}"


def _visit_ref() -> str:
    """The referenceId of the first subrequest; VISIT_REF is its Id reference."""
    ref = "visit"
    if pl.VISIT_REF != "@{" + ref + ".id}":
        raise NotPreviewable(f"VISIT_REF {pl.VISIT_REF} does not reference the first subrequest ({ref})")
    return ref


def _sub(rec: dict, cfg: dict, extra: dict | None = None) -> dict:
    """One subrequest from one (renamed) stored record: POST to its object, referenceId from the record, body = the
    record without `attributes`, plus `extra` (a field that is already in the record is refused)."""
    body = {k: v for k, v in rec.items() if k != "attributes"}
    for k, v in (extra or {}).items():
        if k in body:
            raise sf_config.InvalidConfig(f"setup name {k} collides with a payload field")
        body[k] = v
    return {"method": "POST", "url": _sobject_url(rec["attributes"]["type"], cfg),
            "referenceId": rec["attributes"]["referenceId"], "body": body}


def _subrequests(payload: dict, cfg: dict) -> list[dict]:
    keys, types = _renames(cfg)
    trees = {}
    for root, tree in payload["trees"].items():
        _check_renames(tree, keys, types)
        trees[root] = _walk(tree, keys, types)
    visit = dict(trees[pl.ROOT_OBJECT]["records"][0])
    kids = visit.pop(cfg["outcome_relationship"], {"records": []})["records"]
    extra = {"RecordTypeId": cfg["record_type_id"]} if cfg.get("record_type_id") else None
    subs = [_sub(visit, cfg, extra)]
    subs += [_sub(k, cfg, {cfg["outcome_parent_field"]: pl.VISIT_REF}) for k in kids]
    for root in pl.TREE_ORDER[1:]:
        subs += [_sub(r, cfg) for r in trees.get(root, {"records": []})["records"]]
    return subs


def _check_count(subs: list, cfg: dict) -> None:
    if len(subs) > COMPOSITE_MAX:
        raise TooManySubrequests(f"{len(subs)} subrequests; one Composite request allows at most {COMPOSITE_MAX}. "
                                 "Record fewer talking points or follow-ups for this visit.")


def _check_all_or_none(body: dict, cfg: dict) -> None:
    if body.get("allOrNone") is not True:
        raise NotPreviewable("allOrNone must be true: the visit, outcomes, Event and Tasks succeed or fail together")


def _check_first(subs: list, cfg: dict) -> None:
    ref = _visit_ref()
    if not subs or subs[0]["referenceId"] != ref or subs[0]["url"] != _sobject_url(cfg["visit_object"], cfg):
        raise NotPreviewable(f"the first subrequest must create the {cfg['visit_object']} (referenceId {ref})")


def _check_refs(subs: list, cfg: dict) -> None:
    for s in subs[1:]:
        field = cfg["outcome_parent_field"] if s["url"] == _sobject_url(cfg["outcome_object"], cfg) else "WhatId"
        if s["body"].get(field) != pl.VISIT_REF:
            raise NotPreviewable(f"subrequest {s['referenceId']}: {field} must be {pl.VISIT_REF}")
    if len({s["referenceId"] for s in subs}) != len(subs):
        raise NotPreviewable("referenceIds must be unique")


def check_composite(body: dict, cfg: dict) -> None:
    """Refuse a composite body that a real integration must not send: more than COMPOSITE_MAX subrequests, allOrNone
    not true, the Visit__c not the first subrequest, or an outcome, Event or Task not pointing at @{visit.id}."""
    subs = body.get("compositeRequest") or []
    _check_count(subs, cfg)
    _check_all_or_none(body, cfg)
    _check_first(subs, cfg)
    _check_refs(subs, cfg)


def stored_trees(body: dict, cfg: dict) -> dict:
    """The inverse of the mapping: the stored `trees` this composite body came from (setup renames undone)."""
    keys, types = _renames(cfg)
    rkeys, rtypes = {v: k for k, v in keys.items()}, {v: k for k, v in types.items()}
    body = json.loads(json.dumps(body))
    trees: dict = {}
    visit, kids = None, []
    for s in body["compositeRequest"]:
        obj = s["url"].rsplit("/", 1)[1]
        rec = {"attributes": {"type": obj, "referenceId": s["referenceId"]}, **s["body"]}
        if obj == cfg["visit_object"]:
            if cfg.get("record_type_id"):
                rec.pop("RecordTypeId", None)
            visit = rec
        elif obj == cfg["outcome_object"]:
            rec.pop(cfg["outcome_parent_field"])
            kids.append(rec)
        else:
            trees.setdefault(obj, {"records": []})["records"].append(rec)
    if kids:
        visit[cfg["outcome_relationship"]] = {"records": kids}
    trees = {pl.ROOT_OBJECT: {"records": [visit]}, **trees}
    return {root: _walk(t, rkeys, rtypes) for root, t in trees.items()}


def _sh(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def curl(req: dict) -> str:
    """The curl equivalent, with the placeholder token. Shown as text only; never run."""
    hdr = " \\\n  ".join(f"-H {_sh(f'{k}: {v}')}" for k, v in req["headers"].items())
    return (f"curl -X {req['method']} {_sh(req['url'])} \\\n  {hdr} \\\n  "
            f"--data-binary {_sh(json.dumps(req['body'], ensure_ascii=False, separators=(',', ':')))}")


def build_requests(payload: dict, cfg: dict) -> list[dict]:
    """The request for a stored 0.3 payload: a list with ONE Composite request. Pure: no clock, no store, no network."""
    if not isinstance(payload, dict) or payload.get("lb_schema_version") != pl.SCHEMA_VERSION:
        version = payload.get("lb_schema_version") if isinstance(payload, dict) else None
        raise NotPreviewable(f"this record was saved as {version} (Event root); re-save the visit to preview the "
                             f"{pl.SCHEMA_VERSION} request")
    pl.validate(payload)
    cfg = sf_config.validate(cfg)
    body = {"allOrNone": ALL_OR_NONE, "compositeRequest": _subrequests(payload, cfg)}
    check_composite(body, cfg)
    req = {"root": "composite", "method": "POST", "url": url(cfg), "headers": dict(HEADERS), "body": body}
    req["curl"] = curl(req)
    return [req]


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
