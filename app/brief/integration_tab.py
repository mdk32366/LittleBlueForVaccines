"""'Integration (dry run)' tab (v0.2-f): the Salesforce dry-run setup form. NON-SECRET fields only, saved append-only
in the app DB (brief/sf_config.py). D-0045 (Salesforce dry run), AS-0071 (dry-run setup, non-secret fields only).
There is no Salesforce connection: nothing here opens a connection or sends anything, the instance URL is never
contacted, no input is a password field, and no action is labelled Send (T-0079, T-0080)."""
from __future__ import annotations

import sqlite3

import streamlit as st

from . import sf_config, sf_preview

STORE_ERRORS = (sqlite3.Error, OSError)
SAVES_PER_SESSION = 30  # same cap as visit saves (AS-0058 (open visit store, no passcode) mitigation)


def _latest():
    try:
        return sf_config.latest_config(), None
    except STORE_ERRORS as e:
        return {"id": None, "config": dict(sf_config.DEFAULTS), "sha256": None, "created_at": None}, type(e).__name__
    except sf_config.InvalidConfig as e:
        return {"id": None, "config": dict(sf_config.DEFAULTS), "sha256": None, "created_at": None}, str(e)


def _save(cfg: dict, done: str):
    saves = st.session_state.get("ig_saves", 0)
    if saves >= SAVES_PER_SESSION:
        st.error(f"Not saved: the setup save limit for this session ({SAVES_PER_SESSION}) is reached.")
        return
    try:
        res = sf_config.save_config(cfg)
    except sf_config.InvalidConfig as e:
        st.error(f"Not saved: {e}")
    except STORE_ERRORS as e:
        st.error(f"Not saved: the app DB isn't writable here ({type(e).__name__}). Nothing was stored.")
    else:
        st.session_state["ig_saves"] = saves + 1
        st.success(f"{done} as setup record {res['id']} (sha256 {res['sha256'][:12]}…). Nothing was sent.")


def render() -> None:
    st.warning(sf_preview.BANNER)
    st.subheader("Salesforce integration (dry run)")
    st.caption("There is no Salesforce connection. This setup only shapes the 'Preview Salesforce request' panel on "
               "the Visit record tab. Non-secret fields only: a value that looks like a token, key or password is "
               "refused. Every object and field API name is a proposal (AS-0070).")
    latest, err = _latest()
    if err:
        st.caption(f"Stored setup unavailable ({err}); showing the defaults.")
    cur = latest["config"]
    st.markdown(f"**Auth method (display only):** {sf_config.AUTH_METHOD_DISPLAY}")
    rev = latest["id"] or 0  # widget keys follow the stored setup so a save or load refreshes the form
    L = sf_config.LABELS
    with st.form(key=f"ig_form_{rev}"):
        vals = {}
        for f in ("instance_url", "api_version", "visit_object", "outcome_object", "outcome_relationship",
                  "outcome_parent_field", "account_relationship", "account_external_id_field", "record_type_id"):
            vals[f] = st.text_input(L[f], value=cur[f], key=f"ig_{f}_{rev}")
        vals["owner_mapping"] = st.selectbox(L["owner_mapping"], sf_config.OWNER_MAPPINGS,
                                             index=sf_config.OWNER_MAPPINGS.index(cur["owner_mapping"]),
                                             key=f"ig_owner_mapping_{rev}")
        submitted = st.form_submit_button(L["save"])
    if submitted:
        _save(vals, "Saved setup")
        latest, _ = _latest()
    who = (f"setup record {latest['id']}, saved {latest['created_at']}" if latest["id"] else
           "the defaults (no setup saved yet)")
    st.caption(f"In use: {who}. Instance URL default `{sf_config.DEFAULT_INSTANCE_URL}` is a placeholder; API version "
               f"default {sf_config.DEFAULT_API_VERSION}.")
    st.download_button(L["download"], data=sf_config.export_config(latest["config"]),
                       file_name="little-blue-sf-dryrun-setup.json", mime="application/json", key="ig_download")
    up = st.file_uploader(L["load"], type=["json"], key="ig_upload")
    if up is not None:
        try:
            loaded = sf_config.import_config(up.getvalue())
        except sf_config.InvalidConfig as e:
            st.error(f"Rejected setup file: {e}")
        else:
            st.success("Valid setup file (non-secret fields only).")
            if st.button(L["save_loaded"], key="ig_save_loaded"):
                _save(loaded, "Saved loaded setup")
