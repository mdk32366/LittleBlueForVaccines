# Little Blue for Vaccine Sales

A BIA 562 class project. It builds a one-page visual account brief for each health system, plus question answering over contracts and proposals with cited source text, delivered through a Streamlit app with downloadable PDF reports.

**Does:** sales facts and charts per health system, contract term lookup, grounded Q&A with verbatim citations, PDF reports.
**Does not:** give pricing advice, make efficacy or safety claims, or use real data. Every dataset in this repo is synthetic.
**No Salesforce connection.** The app never connects to Salesforce and stores no Salesforce credentials. A saved visit becomes a FAKE payload record in the app's own database, and the "Integration (dry run)" tab and the "Preview Salesforce request" panel only show, as text, the one Composite request (allOrNone) a real integration would make. Nothing is sent (D-0037 (no real Salesforce), D-0045 (Salesforce dry run), D-0046 (one Composite request, allOrNone)).
