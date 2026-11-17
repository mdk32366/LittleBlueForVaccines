"""qa_panel.py (v0.2-h3, D-0050): the Bluebird part of the Contract Q&A tab, shown only when the flag is on. The provider
comes from app.py (bluebird_qa.provider(), imported behind the flag); this module imports no model client.

One click on 'Ask Bluebird' sends the question once; the checked result is kept per (system, question) for the
session, so reruns do not ask again. The rule-based TermSet lookup is still shown under it (app.py), for comparison and
as the fallback when the model is down or its answer is rejected."""
from __future__ import annotations

import streamlit as st

QA = {"subheader": "Ask the contracts (Bluebird, with cited spans)",
      "caption": ("Bluebird, the local contract model, reads this system's contract text and answers with quoted "
                  "spans. Every quoted span is checked word for word against the clause it cites, and an answer that "
                  "fails a check is not shown. A checked quote is real but can still be the wrong one: in a "
                  "200-question test through this tab, 132 answers were right and 41 of the 133 answers shown were "
                  "wrong. Always read the cited clause. The rule-based TermSet lookup is shown below for comparison."),
      "cross": ("Questions that set the contract against the account's figures are often answered wrongly "
                "(4 of 18 right in testing). Check the cited clauses before using this answer."),
      "button": "Ask Bluebird",
      "prompt": "Click 'Ask Bluebird' to have the local model answer this question (a few seconds on the server CPU).",
      "spinner": "Bluebird is reading this system's contracts...",
      "termset": "TermSet lookup (rule-based, for comparison)",
      "down": "Bluebird unavailable",
      "rejected": "Bluebird's answer was not used",
      "refusal": "Bluebird found no answer in this system's contract text."}
BUTTON_KEY = "qa_bb_ask"
STATE_KEY = "qa_bb"


def _ask(sid: str, question: str, provider) -> None:
    with st.spinner(QA["spinner"]):
        st.session_state.setdefault(STATE_KEY, {})[(sid, question)] = provider(sid, question)


def render(sid: str, question: str, provider) -> None:
    """The button and, once asked, the checked answer for (sid, question)."""
    st.button(QA["button"], key=BUTTON_KEY, on_click=_ask, args=(sid, question, provider))
    res = st.session_state.get(STATE_KEY, {}).get((sid, question))
    if res is None:
        st.caption(QA["prompt"])
        return
    took = f" · {res['seconds']} s" if res.get("seconds") is not None else ""
    if res["status"] == "down":
        st.warning(f"{QA['down']}: {res['reason']}. The TermSet lookup below still works.")
        return
    if res["status"] == "rejected":
        st.warning(f"{QA['rejected']}: {res['reason']}. See the TermSet lookup below.")
        return
    if res["status"] == "refusal":
        st.markdown(f"**Bluebird answer:** {res['answer']}")
        st.caption((f"Bluebird does not answer this: {res['reason']}." if res.get("reason") else QA["refusal"]) + took)
        return
    if res.get("route") == "cross":
        st.warning(QA["cross"])
    shown = res["template"]
    for c in res["citations"]:
        shown = shown.replace("{%s}" % c["slot"], f"**{c['span']}**")
    st.markdown(f"**Bluebird answer:** {shown}")
    n = len(res["citations"])
    st.caption(f"Bluebird (local model) · {n} quoted span{'s' if n != 1 else ''}, each found word for word in the "
               f"cited clause{took}")
    for c in res["citations"]:
        st.markdown(f"`{c['anchor']}` · {c['heading']} · span: **{c['span']}**")
        st.markdown("> " + c["clause_text"].replace(c["span"], f"**{c['span']}**", 1))
