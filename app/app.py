"""Little Blue for Vaccine Sales: Streamlit UI (D-0032 (Streamlit reports), D-0033 (name)). LLM off."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from brief import benchmark as bm, charts, clean, config, contracts, facts, load, report  # noqa: E402

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
    return facts.compute_all(df, bm.resolve(df, mode, national))


fsets = all_facts(str(config.DATA_PATH), mode, str(bm.national_path()))
ids = sorted(fsets)
sid = st.sidebar.selectbox("Health system", ids, format_func=lambda s: f"{s} · {fsets[s].name}", key="system")
fs = fsets[sid]
st.sidebar.write(f"State: {fs.state} · FactSheet {fs.fs_id}")
st.sidebar.write(f"Live benchmark: **{fs.benchmark_label}**")
if fs.benchmark_note:
    st.sidebar.warning(fs.benchmark_note)

tab_brief, tab_qa = st.tabs(["Brief", "Contract Q&A"])

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
    if fs.v("F5.flags"):
        st.subheader("F5 switching flags")
        st.dataframe(pd.DataFrame(fs.v("F5.flags")), hide_index=True)
    st.download_button("Download PDF report", data=pdf, file_name=f"little-blue-{sid}.pdf",
                       mime="application/pdf", key="download_pdf")
    with st.expander("FactSheet JSON"):
        st.code(fs.to_json(), language="json")

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
            st.markdown(f"`{h['anchor']}` · {h['heading']} · span: **{h['span']}** "
                        f"({'verbatim' if h['verbatim'] else 'NOT VERBATIM'})")
            st.markdown("> " + h["clause_text"].replace(h["span"], f"**{h['span']}**", 1))
    with st.expander("All TermSet fields for this system"):
        st.dataframe(pd.DataFrame([{"doc": d, "field": k, "value": str(f["value"]), "span": f["span"],
                                    "anchor": f"{f['source']['doc_id']}#{f['source']['anchor']}"}
                                   for d, k, f in contracts.system_terms(sid)]), hide_index=True)
