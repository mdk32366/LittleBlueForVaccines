"""'Visit record' tab (v0.2-d, PR 8): outcomes per talking point, typed notes, save as a FAKE Salesforce payload record,
exact-key lookup, visit file download/load. No network; nothing is sent anywhere (AS-0057 (sf payload is a database
record, not a send)). Kept in its own module so app.py only gains one tab line and one call."""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3

import streamlit as st

from . import benchmark as bm, clean, client_metrics, config, load, payload as pl, visits


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


def _outcome_controls(sid: str, points: list, notes: str) -> list:
    out = []
    for i, p in enumerate(points):
        hint = pl.mentioned_hint(p, notes)
        st.markdown(f"**{p.key}**: {p.text}")
        st.caption("hint: mentioned in the notes" if hint else "hint: not found in the notes")
        c = st.columns([2, 2, 1])
        addressed = c[0].selectbox("Addressed", pl.ADDRESSED, index=0 if hint else 2, key=f"vr_addr_{sid}_{i}_{hint}")
        response = c[1].selectbox("Customer response", pl.RESPONSES, index=1, key=f"vr_resp_{sid}_{i}")
        quality = c[2].number_input("Quality (1-5)", min_value=1, max_value=5, value=3, step=1, key=f"vr_q_{sid}_{i}")
        c2 = st.columns(2)
        evidence = c2[0].text_input("Evidence quote", key=f"vr_ev_{sid}_{i}")
        follow = c2[1].text_input("Follow-up", key=f"vr_fu_{sid}_{i}")
        out.append(pl.Outcome(p, addressed, response, int(quality), evidence, follow))
    return out


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
    # PR 7 hook: the voice transcript pre-fills st.session_state["vr_notes"] before this widget renders.
    notes = st.text_area("Visit notes (typed)", max_chars=visits.NOTES_MAX, key="vr_notes")
    points, source = _points(sid, points_provider)
    st.caption(f"Talking points from: {source}. Hints come from a keyword match on the notes; please confirm each one.")
    if not points:
        st.warning("No talking points with computed values for this system; the visit can still be saved.")
    outcomes = _outcome_controls(sid, points, notes)
    saves = st.session_state.get("vr_saves", 0)
    if st.button(visits.LABELS["save"], key="vr_save", disabled=saves >= visits.SAVES_PER_SESSION):
        res = _save_typed(rep=rep, visit_date=vdate.isoformat(), system_id=sid, system_name=fs.name, notes=notes,
                          outcomes=outcomes, start_time=start.strftime("%H:%M"), duration=int(duration))
        if res is not None:
            st.session_state["vr_saves"] = saves + 1
            st.success(f"Saved visit {res['visit_key']} as payload record version {res['version']} "
                       f"(sha256 {res['sha256'][:12]}…). Nothing was sent.")
    if saves >= visits.SAVES_PER_SESSION:
        st.caption(f"Save limit for this session reached ({visits.SAVES_PER_SESSION}).")

    st.divider()
    st.subheader("Look up a visit (exact rep, date and company)")
    lc = st.columns(3)
    l_rep = lc[0].text_input("Rep", key="vr_l_rep")
    l_date = lc[1].date_input("Visit date", value=_dt.date.today(), key="vr_l_date")
    l_sid = lc[2].selectbox("Company", system_ids, index=system_ids.index(sid) if sid in system_ids else 0,
                            key="vr_l_sid")
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
            if st.button(visits.LABELS["save_loaded"], key="vr_save_loaded",
                         disabled=saves >= visits.SAVES_PER_SESSION):
                res = _save_loaded(rep=v["rep"], visit_date=v["visit_date"], system_id=v["system_id"],
                                   system_name=v["system_name"], notes=v["notes"], outcomes=loaded["outcomes"],
                                   start_time=v["start_time"], duration=v["duration"])
                if res is not None:
                    st.session_state["vr_saves"] = saves + 1
                    st.success(f"Saved loaded visit as payload record version {res['version']}. Nothing was sent.")
