# BIA 562 synthetic contract generator

This makes fake (D-0022, fake data) contracts, TermSet sidecars and Q&A ground truth for Little Blue for Vaccine Sales.

- Generate: `python tools/gen_contracts.py --seed 562 --out out/` (reads `../data/BIA_562_Synthetic_Sales_Data.csv`; override with `--systems-csv`)
- Test: `pip install -r requirements.txt && python -m pytest tests`
- Red-proof (each guard goes red under a deliberate defect): `python tools/redproof.py`

See the root `docs/` (architecture, decisions, assumptions, testplan, findings).
