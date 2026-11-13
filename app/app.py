"""Little Blue for Vaccine Sales: Streamlit UI (D-0032 (Streamlit reports), D-0033 (name)). LLM off."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from brief import benchmark as bm, charts, clean, client_metrics, config, contracts, load, report, talking  # noqa: E402

st.set_page_config(page_title=config.APP_NAME, layout="wide")
st.title(config.APP_NAME)
st.caption("SYNTHETIC sales data, D-0022 (fake data). LLM off: talking points are templated; "
           "contract answers are TermSet lookups with cited spans.")

MODES = ["synthetic", "national"]
mode = st.sidebar.radio("Benchmark", MODES, index=MODES.index(bm.requested_mode()), key="benchmark",
                        format_func=lambda m: {"synthetic": "synthetic peers (default)",
                                               "national": "national file, D-0034 (national file public-real)"}[m])


@st.cache_data(show_spinner="Computing facts…")
def all_facts(path: str, mode: str, national: str):
    df = clean.clean(load.load_csv(path))
    # F1..F8 against the live benchmark, plus the client metrics (F9..F13); the national column of the comparison
    # table is always read from the national file when present (Q-M3 closed, AS-0042 (client field mapping)).
    return client_metrics.compute_all(df, bm.resolve(df, mode, national), nat=bm.national_profile(national))


fsets = all_facts(str(config.DATA_PATH), mode, str(bm.national_path()))
ids = sorted(fsets)
sid = st.sidebar.selectbox("Health system", ids, format_func=lambda s: f"{s} · {fsets[s].name}", key="system")
fs = fsets[sid]
st.sidebar.write(f"State: {fs.state} · FactSheet {fs.fs_id}")
st.sidebar.write(f"Live benchmark: **{fs.benchmark_label}**")
if fs.benchmark_note:
    st.sidebar.warning(fs.benchmark_note)

tab_brief, tab_talk, tab_qa = st.tabs(config.TABS)  # T-0052: Brief, Talking points, Contract Q&A

with tab_brief:
    st.header(f"{fs.name} ({sid})")
    c = st.columns(5)
    c[0].metric("Dollars (net)", report.narrative.render_tokens("{F1.dollars}", fs))
    c[1].metric("Doses", report.narrative.render_tokens("{F1.doses}", fs))
    c[2].metric("Rank of peers", f"{fs.v('F1.rank')} / {fs.v('F1.n_systems')}")
    c[3].metric("Pfizer share", report.narrative.render_tokens("{F4.pfizer_share}", fs))
    c[4].metric("Switching", fs.v("F5.status"))
    narr, rows, pdf = report.build(fs)
    l, r = st.columns(2)
    l.pyplot(charts.figure(charts.draw_class_mix, fs))
    r.pyplot(charts.figure(charts.draw_mfr, fs))
    l.pyplot(charts.figure(charts.draw_trend, fs))
    r.pyplot(charts.figure(charts.draw_facility, fs))
    st.subheader("Talking points")
    st.caption(f"source: {narr.source} ({'; '.join(narr.notes)})")
    for p in narr.rendered:
        st.markdown(f"- {p}")
    st.subheader("Contracts on file")
    st.caption(f"Generated contracts (synthetic), cited spans; as of {config.AS_OF_DATE}.")
    for line in report.brief_contract_lines(rows):
        st.markdown(f"- {line}")
    st.subheader("System vs state peers vs national")
    st.caption(f"State column: {client_metrics.STATE_COLUMN} (AS-0031 (in-state peers)); national column: "
               f"{client_metrics.NATIONAL_COLUMN}, pooled, benchmark only. A metric the data cannot support reads "
               "'not available: <reason>'.")
    st.dataframe(pd.DataFrame(client_metrics.table_rows(fs), columns=list(client_metrics.TABLE_COLUMNS)),
                 hide_index=True, key="comparison_table")
    st.subheader("Attributes (A5–A9)")
    st.dataframe(pd.DataFrame(client_metrics.attribute_strip(fs), columns=list(client_metrics.STRIP_COLUMNS)),
                 hide_index=True, key="attribute_strip")
    if fs.v("F5.flags"):
        st.subheader("F5 switching flags")
        st.dataframe(pd.DataFrame(fs.v("F5.flags")), hide_index=True)
    st.download_button("Download PDF report", data=pdf, file_name=f"little-blue-{sid}.pdf",
                       mime="application/pdf", key="download_pdf")
    with st.expander("FactSheet JSON"):
        st.code(fs.to_json(), language="json")

with tab_talk:
    st.subheader("Talking points (computed numbers only; LLM off)")
    st.caption("Fixed slots, up to three must-cover points (AS-0045 (must-cover selection)) and one question. "
               "Every number is a computed fact. Tick a point once it is covered.")
    for i, p in enumerate(talking.build(fs)):
        st.checkbox(p.rendered, key=f"tp_{sid}_{i}")

with tab_qa:
    st.subheader("Ask the contracts (TermSet lookup, LLM off)")
    examples = [q["question"] for q in contracts.system_questions(sid)]
    pick = st.selectbox("Example questions (from gen/out qa.jsonl)", ["(type your own)"] + examples, key="qa_pick")
    typed = st.text_input("Question", key="qa_text")
    question = typed if typed.strip() else ("" if pick == "(type your own)" else pick)
    if question:
        res = contracts.answer(sid, question)
        st.markdown(f"**Answer:** {res['answer']}")
        st.caption(res["note"])
        for h in res["citations"]:
            exp = f" · **{h['marker']}** (ended before {config.AS_OF_DATE})" if h.get("marker") else ""
            st.markdown(f"`{h['anchor']}` · {h['heading']} · span: **{h['span']}** "
                        f"({'verbatim' if h['verbatim'] else 'NOT VERBATIM'}){exp}")
            st.markdown("> " + h["clause_text"].replace(h["span"], f"**{h['span']}**", 1))
    with st.expander("All TermSet fields for this system"):  # stays collapsed (Trinity GATE 2 ruling)
        marks = contracts.system_markers(sid)
        st.dataframe(pd.DataFrame([{"doc": d, "field": k, "value": str(f["value"]), "span": f["span"],
                                    "anchor": f"{f['source']['doc_id']}#{f['source']['anchor']}",
                                    "status": marks[(d, k)]}
                                   for d, k, f in contracts.system_terms(sid)]), hide_index=True)
