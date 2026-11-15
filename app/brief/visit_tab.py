"""'Visit record' tab (v0.2-d, PR 8): outcomes per talking point, typed notes, save as a FAKE Salesforce payload record,
exact-key lookup, visit file download/load. v0.2-c (PR 7) adds an optional voice recording that pre-fills the notes box
(brief/stt.py; AS-0047 (STT engine and model), AS-0059 (raw audio is not kept)). No network; nothing is sent anywhere (AS-0057 (sf payload is a database
record, not a send)). v0.2-f adds the 'Preview Salesforce request' panel after a save or a lookup: a pure function of
the stored payload and the latest dry-run setup (brief/sf_preview.py, D-0045 (Salesforce dry run)); nothing is sent.
v0.2-g, D-0047 (missed talking-point follow-up): the hint pre-fills Raised, Partially or Not raised (AS-0073); the
'Not covered yet' panel asks about every point that is not Raised: mark it not addressed with a reason (AS-0075), or
address it now in an addendum that is checked for those points only (brief/gap.py). Save stays disabled until every
point is resolved. Kept in its own module so app.py only gains one tab line and one call.
v0.2-h1, D-0048 (auto-fill visit fields, rules part): every Raised or Partially point gets a suggested Evidence quote
and Follow-up from the notes (from the addendum only when an addendum lifted the point), by the rules in
brief/autofill.py (AS-0077, AS-0078), labelled "auto (rule-based)" under a fixed caveat (AS-0079). Provenance lives in
st.session_state["vr_auto"][(sid, key, field)] = {"value", "src"}; a field whose widget value differs from its
recorded suggestion becomes `edited` and is never written again. Customer response and Quality are never written.
Nothing is stored before Save; on Save the provenance goes to outcomes_json only (AS-0080), and the 'Not covered yet'
state of that system (vr_gap) is cleared (PR 14 review N7)."""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import sqlite3

import streamlit as st

import hashlib

from . import (autofill, benchmark as bm, clean, client_metrics, config, gap, load, payload as pl, sf_config,
               sf_preview, stt, visits)


@st.cache_data(show_spinner="Computing client metrics…")
def _client_points(path: str, national: str, system_id: str) -> list:
    """Fallback talking points (until the PR 6 provider is wired): computed client ratios from PR 5's table rows."""
    df = clean.clean(load.load_csv(path))
    fsets = client_metrics.compute_all(df)
    fs = fsets.get(system_id)
    return [] if fs is None else pl.points_from_client_rows(client_metrics.table_rows(fs))


def _points(sid: str, provider):
    if provider is not None:
        try:
            return list(provider(sid)), "talking points"
        except Exception as e:  # provider trouble never blocks a visit record
            st.caption(f"talking points unavailable ({type(e).__name__}); using computed client ratios")
    return _client_points(str(config.DATA_PATH), str(bm.national_path()), sid), "computed client ratios (PR 5)"


HINT_CAPTION = {"Raised": "hint: mentioned in the notes", "Partially": "hint: only in passing in the notes",
                "Not raised": "hint: not found in the notes"}
GAP = {"title": "Not covered yet — What about these?", "mode": "How to resolve", "A": "Mark not addressed",
       "B": "Address now", "reason": "Reason", "details": "Details (required for Other)", "addendum": "Addendum",
       "check": "Check addendum"}
ADDENDUM_SEP = "\n\nAddendum {n}: {text}"  # how each round is added to the notes (D-0047)


def _gap_state(sid: str) -> dict:
    """Per-system resolutions in st.session_state["vr_gap"]: the status floor each addendum round reached, the keys
    that went through a round, and the addendum texts (D-0047)."""
    g = st.session_state.setdefault("vr_gap", {})
    return g.setdefault(sid, {"floor": {}, "addendum_keys": [], "addenda": [], "addendum_text": {}, "round": 0,
                              "msg": ""})


def _clear_gap(sid: str) -> None:
    """After a typed save (PR 14 review N7): drop this system's addenda, floors and rounds, so a later visit to the
    same system in this browser session does not inherit them."""
    st.session_state.get("vr_gap", {}).pop(sid, None)


def _full_notes(notes: str, state: dict) -> str:
    return (notes or "") + "".join(ADDENDUM_SEP.format(n=n, text=t) for n, t in enumerate(state["addenda"], 1))


AUTO_KEYS = {"evidence": "vr_ev", "follow_up": "vr_fu"}  # the only widget keys the auto-fill may write (D-0048)


def _apply_autofill(ss, sid: str, i: int, point, status: str, text: str) -> None:
    """Write the rule suggestions (autofill.suggest) into the Evidence quote and Follow-up widget state of point i
    BEFORE those widgets render. `ss` is st.session_state (a plain dict in unit tests). Per field:
    - a widget value that differs from its recorded suggestion (or a value typed before any suggestion) marks the field
      `edited`, and an edited field is never written again (edits win);
    - otherwise the field takes the current suggestion and is recorded as auto-rule;
    - a point that is no longer Raised or Partially gets an unedited suggestion withdrawn (blank).
    Only the vr_ev / vr_fu keys are written: never Customer response (vr_resp) and never Quality (vr_q)."""
    reg = ss.setdefault("vr_auto", {})
    vals = autofill.suggest(point, status, text)
    for field, prefix in AUTO_KEYS.items():
        wkey, rk = f"{prefix}_{sid}_{i}", (sid, point.key, field)
        rec, cur = reg.get(rk), ss.get(wkey)
        if rec is None and cur:
            rec = reg[rk] = {"value": None, "src": autofill.SRC_EDITED}  # the rep typed it before any suggestion
        elif rec is not None and cur is not None and cur != rec["value"]:
            rec["src"] = autofill.SRC_EDITED
        if rec is not None and rec["src"] == autofill.SRC_EDITED:
            continue
        if field in vals:
            ss[wkey] = vals[field]
            reg[rk] = {"value": vals[field], "src": autofill.SRC_AUTO}
        elif rec is not None:
            ss[wkey] = ""
            del reg[rk]


def _provenance(ss, sid: str, key: str) -> dict:
    """{"evidence": src, "follow_up": src} for outcomes_json (AS-0080): edited, auto-rule (a non-empty suggestion
    still in place) or none."""
    reg = ss.get("vr_auto", {})
    out = {}
    for field in AUTO_KEYS:
        rec = reg.get((sid, key, field))
        out[field] = (autofill.SRC_EDITED if rec and rec["src"] == autofill.SRC_EDITED else
                      autofill.SRC_AUTO if rec and rec["value"] else autofill.SRC_NONE)
    return out


def _source_text(state: dict, key: str, notes: str, lifted: bool) -> str:
    """The text the suggestions come from: the addendum text(s) this point was checked against when an addendum
    lifted its status (path B), otherwise the notes."""
    texts = (state or {}).get("addendum_text", {}).get(key) or []
    return "\n".join(texts) if lifted and texts else notes


def _outcome_controls(sid: str, points: list, notes: str, floor: dict | None = None, state: dict | None = None) -> list:
    out = []
    if points:
        st.caption(autofill.CAPTION)
    for i, p in enumerate(points):
        hinted = pl.hint_status(p, notes)
        status = gap.upgrade(hinted, (floor or {}).get(p.key, hinted))  # an addendum result stays in force
        _apply_autofill(st.session_state, sid, i, p, status, _source_text(state, p.key, notes, status != hinted))
        st.markdown(f"**{p.key}**: {p.text}")
        extra = f"; after an addendum: {status}" if status != hinted else ""
        st.caption(HINT_CAPTION[hinted] + extra)
        c = st.columns([2, 2, 1])
        addressed = c[0].selectbox("Addressed", pl.ADDRESSED, index=pl.ADDRESSED.index(status),
                                   key=f"vr_addr_{sid}_{i}_{status}")
        response = c[1].selectbox("Customer response", pl.RESPONSES, index=1, key=f"vr_resp_{sid}_{i}")
        quality = c[2].number_input("Quality (1-5)", min_value=1, max_value=5, value=3, step=1, key=f"vr_q_{sid}_{i}")
        c2 = st.columns(2)
        evidence = c2[0].text_input("Evidence quote", key=f"vr_ev_{sid}_{i}")
        follow = c2[1].text_input("Follow-up", key=f"vr_fu_{sid}_{i}")
        prov = _provenance(st.session_state, sid, p.key)
        for col, field in ((c2[0], "evidence"), (c2[1], "follow_up")):
            if prov[field] == autofill.SRC_AUTO:
                col.caption(autofill.LABEL)
        out.append(pl.Outcome(p, addressed, response, int(quality), evidence, follow, auto=prov))
    return out


def _check_addendum(sid: str, outcomes: list, keys: list, box: str) -> None:
    """'Check addendum' (on_click, so the result is in place before the next render): the second pass over the
    'Address now' points only, on the addendum text only (gap.second_pass)."""
    state = _gap_state(sid)
    text = (st.session_state.get(box) or "").strip()
    if not text:
        state["msg"] = "Type the addendum first; nothing was checked."
        return
    new = {o.point.key: o for o in gap.second_pass(outcomes, text, keys)}
    for k in keys:
        state["floor"][k] = new[k].addressed
        if k not in state["addendum_keys"]:
            state["addendum_keys"].append(k)
        state["addendum_text"].setdefault(k, []).append(text)  # v0.2-h1: the auto-fill source for this point
    state["addenda"].append(text)
    state["round"] += 1
    state["msg"] = (f"Addendum {len(state['addenda'])} checked for " +
                    ", ".join(f"{k}: {new[k].addressed}" for k in keys) + ".")


def _gap_panel(sid: str, outcomes: list, where: str, allow_b: bool = True, notes_len: int = 0) -> list:
    """'Not covered yet — What about these?': every point whose current status is not Raised (gap.uncovered). Each
    needs (A) a reason, or (B) an addendum round (typed visit only). Returns the outcomes with the reasons applied."""
    state = _gap_state(sid) if allow_b else None
    listed = gap.uncovered(outcomes)
    if not allow_b:  # a loaded visit: only the points that are not Raised and carry no valid reason (D-0047)
        listed = [o for o in listed if gap.problem(o) is not None]
    if state and state["msg"]:
        st.info(state["msg"])
    if not listed:
        return outcomes
    st.subheader(GAP["title"])
    st.caption("These talking points are not Raised yet. Mark each one not addressed with a reason" +
               (", or address it now in an addendum: only these points are checked again." if allow_b else
                ". The notes of a saved visit are not extended."))
    out = {o.point.key: o for o in outcomes}
    b_keys = []
    for o in listed:
        k = o.point.key
        st.markdown(f"**{k}** ({o.addressed}): {o.point.text}")
        mode = GAP["A"]
        if allow_b:
            mode = st.radio(GAP["mode"], (GAP["A"], GAP["B"]), index=None, horizontal=True,
                            key=f"vr_gap_mode_{where}_{sid}_{k}")
        if mode == GAP["A"]:
            c = st.columns([2, 3])
            label = c[0].selectbox(GAP["reason"], list(gap.REASONS.values()), index=None, placeholder="Pick a reason",
                                   key=f"vr_gap_reason_{where}_{sid}_{k}")
            text = c[1].text_input(GAP["details"], max_chars=gap.REASON_TEXT_MAX, key=f"vr_gap_text_{where}_{sid}_{k}")
            code = next((rc for rc, lab in gap.REASONS.items() if lab == label), None)
            out[k] = dataclasses.replace(o, reason_code=code, reason_text=(text or "").strip() or None)
        elif mode == GAP["B"]:
            b_keys.append(k)
            out[k] = dataclasses.replace(o, reason_code=None, reason_text=None)
        else:
            out[k] = dataclasses.replace(o, reason_code=None, reason_text=None)
        why = gap.problem(out[k])
        st.caption("resolved" if why is None else
                   ("to be checked against the addendum below" if mode == GAP["B"] else f"still needed: {why}"))
    if b_keys:
        budget = visits.NOTES_MAX - notes_len - 16
        if budget < 1:
            st.warning(f"No room for an addendum: the notes are at the {visits.NOTES_MAX}-character limit. "
                       "Mark these points not addressed instead.")
        else:
            box = f"vr_gap_add_{sid}_{state['round']}"
            st.text_area(f"{GAP['addendum']} (checked only for {', '.join(b_keys)})", max_chars=budget, key=box)
            cur = [out[o.point.key] for o in outcomes]
            st.button(GAP["check"], key=f"vr_gap_check_{sid}", on_click=_check_addendum, args=(sid, cur, b_keys, box))
    return [out[o.point.key] for o in outcomes]


def _blocked_warning(outcomes: list) -> list:
    blocked = gap.unresolved(outcomes)
    if blocked:
        n = len(blocked)
        st.warning(f"Not saved yet: {n} talking point{'s' if n != 1 else ''} need{'s' if n == 1 else ''} a reason "
                   f"or an addendum: {', '.join(o.point.key for o in blocked)}.")
    return blocked


def _loaded_gate(outcomes: list) -> list:
    """'Save loaded visit' stays disabled while this is not empty (D-0047; its own seam since v0.2-h1, PR 14 review N5)."""
    return _blocked_warning(outcomes)


STORE_ERRORS = (sqlite3.Error, OSError)  # the visit store can't be opened or written (AS-0050 (visits DB path))
NOT_SAVED = ("Not saved: the visit store isn't writable here ({err}). Nothing was stored and nothing was sent; "
             "the rest of this tab still works.")
LOOKUP_FAILED = "Lookup failed: the visit store can't be read here ({err})."


def _store_msg(template: str, e: Exception) -> str:
    return template.format(err=type(e).__name__)


def _save_typed(**kw):
    """'Save visit': returns the save result, or None after showing why nothing was saved."""
    try:
        return visits.save_visit(**kw)
    except ValueError as e:
        st.error(f"Not saved: {e}")
    except STORE_ERRORS as e:
        st.error(_store_msg(NOT_SAVED, e))
    return None


def _save_loaded(**kw):
    """'Save loaded visit': returns the save result, or None after showing why nothing was saved."""
    try:
        return visits.save_visit(**kw)
    except ValueError as e:
        st.error(f"Not saved: {e}")
    except STORE_ERRORS as e:
        st.error(_store_msg(NOT_SAVED, e))
    return None


def _show_record(found: dict):
    st.success(f"Visit {found['visit_key']}: version {found['version']} of {len(found['versions'])}, "
               f"sha256 {found['sha256'][:12]}…")
    v = found["visit"]
    st.markdown(f"Notes: {v['notes_text'] or '(none)'}")
    st.dataframe([{k: o[k] for k in ("key", "addressed", "response", "quality", "follow_up")} for o in v["outcomes"]],
                 hide_index=True)
    st.download_button(visits.LABELS["download"], data=visits.visit_file(found),
                       file_name=f"visit-{v['system_id']}-{v['visit_date']}.json", mime="application/json",
                       key="vr_download")
    st.code(json.dumps(found["payload"], indent=2, ensure_ascii=False), language="json")


def _preview_panel(payload: dict, stored_sha: str, where: str) -> None:
    """'Preview Salesforce request': the one Composite request a real integration would make for this stored payload
    (D-0046). Shown, never sent. Pure: (stored payload, latest setup) in, text out (T-0078)."""
    st.subheader(sf_preview.LABELS["panel"])
    st.warning(sf_preview.BANNER)
    try:
        cfg = sf_config.latest_config()["config"]
    except (sqlite3.Error, OSError, sf_config.InvalidConfig) as e:
        cfg = dict(sf_config.DEFAULTS)
        st.caption(f"Stored setup unavailable ({type(e).__name__}); previewing with the default setup.")
    try:
        reqs = sf_preview.build_requests(payload, cfg)
        data = sf_preview.request_set_bytes(payload, cfg, stored_sha)
    except (sf_preview.NotPreviewable, sf_config.InvalidConfig, pl.InvalidPayload) as e:
        st.info(f"No preview: {e}")
        return
    r = reqs[0]
    subs = r["body"]["compositeRequest"]
    st.caption(f"One Composite request (allOrNone: all {len(subs)} subrequests succeed or none do; at most "
               f"{sf_preview.COMPOSITE_MAX}). Setup: instance `{cfg['instance_url']}` (placeholder, never contacted), "
               f"API v{cfg['api_version']}. {pl.VISIT_REF} is the Id the first subrequest creates (D-0046).")
    st.markdown("\n".join(f"{i}. `{s['method']} {s['url']}` (referenceId `{s['referenceId']}`)"
                           for i, s in enumerate(subs, 1)))
    st.code(f"{r['method']} {r['url']}\n" + "\n".join(f"{k}: {v}" for k, v in r["headers"].items()), language="http")
    st.code(json.dumps(r["body"], indent=2, ensure_ascii=False), language="json")
    st.code(r["curl"], language="bash")
    st.download_button(sf_preview.LABELS["download"], data=data, mime="application/json",
                       file_name=f"sf-dryrun-requests-{payload['lb_visit_key'].rsplit('|', 1)[1]}.json",
                       key=f"vr_preview_download_{where}")


@st.cache_resource(show_spinner=False)
def _transcriber(key: tuple):
    """One transcriber per STT config per process, so the model loads once (lazy, on the first recording)."""
    return stt.get_transcriber()


def _recording_id(data: bytes) -> str:
    """sha256 of the recording: the only trace of it kept in the session (AS-0059 (raw audio is not kept))."""
    return hashlib.sha256(data).hexdigest()


def _merge_notes(typed: str, text: str) -> tuple[str, bool]:
    """Typed notes + transcript, capped at the notes limit -> (notes, was_cut)."""
    typed = typed.strip()
    merged = f"{typed}\n{text}" if typed else text
    if len(merged) > visits.NOTES_MAX:
        return merged[: visits.NOTES_MAX], True
    return merged, False


def _voice_notes() -> None:
    """Audio recorder above the notes box. The transcript pre-fills st.session_state["vr_notes"] (appended to anything
    already typed) before that widget renders; the rep edits it there. The recording itself is only read in memory."""
    tr, reason = _transcriber(stt.config_key())
    if tr is None:
        st.caption(f"voice unavailable: {reason}. Type the notes below.")
        return
    audio = st.audio_input("Record visit notes", sample_rate=stt.SAMPLE_RATE, key="vr_audio")
    if audio is None:
        return
    data = audio.getvalue()
    digest = _recording_id(data)  # only the hash is kept, to transcribe each recording once
    if st.session_state.get("vr_audio_done") == digest:
        return
    with st.spinner("Transcribing the recording…"):
        text, note = stt.transcribe_bytes(tr, data)
    st.session_state["vr_audio_done"] = digest
    if note:
        st.warning(note)
        return
    if not text:
        st.caption("The recording had no words to transcribe; type the notes below.")
        return
    merged, cut = _merge_notes(st.session_state.get("vr_notes") or "", text)
    if cut:
        st.caption(f"The transcript was cut to the {visits.NOTES_MAX}-character notes limit.")
    st.session_state["vr_notes"] = merged
    st.caption(f"Transcribed with {tr.name}. Check and edit the notes below before saving; the recording is not kept.")


def render(sid: str, fs, system_ids: list, points_provider=None) -> None:
    st.info(visits.BANNER)
    st.subheader(f"Visit record: {fs.name} ({sid})")
    c = st.columns(3)
    rep = c[0].text_input("Rep", key="vr_rep")
    vdate = c[1].date_input("Visit date", value=_dt.date.today(), key="vr_date")
    c[2].text_input("Company (health system picker)", value=sid, disabled=True, key=f"vr_company_{sid}")
    t = st.columns(2)
    start = t[0].time_input("Start time", value=_dt.time(9, 0), key="vr_start")
    duration = t[1].number_input("Duration (minutes)", min_value=1, max_value=1440, value=pl.DEFAULT_DURATION,
                                 key="vr_duration")
    _voice_notes()  # PR 7: the voice transcript pre-fills st.session_state["vr_notes"] before this widget renders
    notes = st.text_area("Visit notes (typed)", max_chars=visits.NOTES_MAX, key="vr_notes")
    points, source = _points(sid, points_provider)
    st.caption(f"Talking points from: {source}. Hints come from a keyword match on the notes; please confirm each one.")
    if not points:
        st.warning("No talking points with computed values for this system; the visit can still be saved.")
    state = _gap_state(sid)
    outcomes = _outcome_controls(sid, points, notes, state["floor"], state)
    full_notes = _full_notes(notes, state)
    outcomes = _gap_panel(sid, outcomes, "typed", allow_b=True, notes_len=len(full_notes))
    outcomes = [dataclasses.replace(o, addendum=True) if o.point.key in state["addendum_keys"] else o for o in outcomes]
    if state["addenda"]:
        st.caption("Added to the notes on save: " + " ".join(f"Addendum {n}: {t}" for n, t in
                                                              enumerate(state["addenda"], 1)))
    blocked = _blocked_warning(outcomes)
    saves = st.session_state.get("vr_saves", 0)
    if st.button(visits.LABELS["save"], key="vr_save", disabled=saves >= visits.SAVES_PER_SESSION or bool(blocked)):
        res = _save_typed(rep=rep, visit_date=vdate.isoformat(), system_id=sid, system_name=fs.name, notes=full_notes,
                          outcomes=outcomes, start_time=start.strftime("%H:%M"), duration=int(duration))
        if res is not None:
            st.session_state["vr_saves"] = saves + 1
            st.success(f"Saved visit {res['visit_key']} as payload record version {res['version']} "
                       f"(sha256 {res['sha256'][:12]}…). Nothing was sent.")
            st.session_state["vr_last_saved"] = {"payload": res["payload"], "sha256": res["sha256"]}
            _clear_gap(sid)
    last = st.session_state.get("vr_last_saved")
    if last:
        _preview_panel(last["payload"], last["sha256"], "saved")
    if saves >= visits.SAVES_PER_SESSION:
        st.caption(f"Save limit for this session reached ({visits.SAVES_PER_SESSION}).")

    st.divider()
    st.subheader("Look up a visit (exact rep, date and company)")
    lc = st.columns(3)
    l_rep = lc[0].text_input("Rep", key="vr_l_rep")
    l_date = lc[1].date_input("Visit date", value=_dt.date.today(), key="vr_l_date")
    # Keyed on the sidebar system (F-0025): with a fixed key Streamlit keeps the first value and ignores `index`.
    l_sid = lc[2].selectbox("Company", system_ids, index=system_ids.index(sid) if sid in system_ids else 0,
                            key=f"vr_l_sid_{sid}")
    if st.button(visits.LABELS["lookup"], key="vr_lookup"):
        try:
            st.session_state["vr_found"] = visits.lookup(l_rep, l_date.isoformat(), l_sid) or "none"
        except ValueError as e:
            st.session_state["vr_found"] = f"error: {e}"
        except STORE_ERRORS as e:
            st.session_state["vr_found"] = _store_msg(LOOKUP_FAILED, e)
    found = st.session_state.get("vr_found")
    if isinstance(found, dict):
        _show_record(found)
        if found["payload"] is not None:
            _preview_panel(found["payload"], found["sha256"], "found")
    elif found == "none":
        st.info("No visit for that exact rep, date and company.")
    elif found:
        st.error(found)

    st.divider()
    up = st.file_uploader(visits.LABELS["load"], type=["json"], key="vr_upload")
    if up is not None:
        try:
            loaded = visits.parse_visit_file(up.getvalue())
        except visits.InvalidVisitFile as e:
            st.error(f"Rejected visit file: {e}")
        else:
            v = loaded["visit"]
            st.success(f"Valid visit file for {loaded['visit_key']} ({len(v['outcomes'])} talking points).")
            l_outcomes = _gap_panel(v["system_id"], loaded["outcomes"], "loaded", allow_b=False)
            l_blocked = _loaded_gate(l_outcomes)
            if st.button(visits.LABELS["save_loaded"], key="vr_save_loaded",
                         disabled=saves >= visits.SAVES_PER_SESSION or bool(l_blocked)):
                res = _save_loaded(rep=v["rep"], visit_date=v["visit_date"], system_id=v["system_id"],
                                   system_name=v["system_name"], notes=v["notes"], outcomes=l_outcomes,
                                   start_time=v["start_time"], duration=v["duration"])
                if res is not None:
                    st.session_state["vr_saves"] = saves + 1
                    st.success(f"Saved loaded visit as payload record version {res['version']}. Nothing was sent.")
