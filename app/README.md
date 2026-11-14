# Little Blue for Vaccine Sales

The account-brief app for BIA 562: pick a health system, read its brief with charts, ask about its synthetic contracts with cited spans, and download a one-page PDF report. LLM off.

- Install: `pip install -r requirements.txt`
- Run: `streamlit run app.py` (from `app/`)
- Reports from the command line: `python cli.py --system SYNCP000025 --out reports/`
- Test: `python -m pytest tests`; red-proof: `python tools/redproof.py`; headless smoke: `python tools/smoke.py`
- Deploy check (run by the deploy against its own reverse-proxy Caddyfile and Streamlit config.toml, which are not in this repository): `python tools/upload_limit_check.py --caddyfile <path> --streamlit-config <path>` (T-0062, F-0026)

There is no Salesforce connection. The Visit record tab stores a FAKE payload record, and the "Integration (dry run)" tab and "Preview Salesforce request" panel only show the one Composite request (allOrNone) a real integration would make; nothing is sent and no credentials are stored (D-0045 (Salesforce dry run), D-0046 (one Composite request, allOrNone)).

Data comes from `../data/` (override with `DATA_PATH` / `NATIONAL_PATH`); contract Q&A reads `../gen/out` (override with `GEN_OUT`). Design notes are in the root `docs/`.
