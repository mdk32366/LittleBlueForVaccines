# Little Blue for Vaccine Sales

The account-brief app for BIA 562: pick a health system, read its brief with charts, ask about its synthetic contracts with cited spans, and download a one-page PDF report. LLM off.

- Install: `pip install -r requirements.txt`
- Run: `streamlit run app.py` (from `app/`)
- Reports from the command line: `python cli.py --system SYNCP000025 --out reports/`
- Test: `python -m pytest tests`; red-proof: `python tools/redproof.py`; headless smoke: `python tools/smoke.py`

Data comes from `../data/` (override with `DATA_PATH` / `NATIONAL_PATH`); contract Q&A reads `../gen/out` (override with `GEN_OUT`). Design notes are in the root `docs/`.
