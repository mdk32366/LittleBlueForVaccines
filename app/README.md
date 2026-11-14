# Little Blue for Vaccine Sales

The account-brief app for BIA 562: pick a health system, read its brief with charts, ask about its synthetic contracts with cited spans, and download a one-page PDF report. LLM off.

- Install: `pip install -r requirements.txt`
- Run: `streamlit run app.py` (from `app/`)
- Reports from the command line: `python cli.py --system SYNCP000025 --out reports/`
- Test: `python -m pytest tests`; red-proof: `python tools/redproof.py`; headless smoke: `python tools/smoke.py`
- Deploy check (run by the deploy against its own reverse-proxy Caddyfile and Streamlit config.toml, which are not in this repository): `python tools/upload_limit_check.py --caddyfile <path> --streamlit-config <path>` (T-0062, F-0026)

Data comes from `../data/` (override with `DATA_PATH` / `NATIONAL_PATH`); contract Q&A reads `../gen/out` (override with `GEN_OUT`). Design notes are in the root `docs/`.
