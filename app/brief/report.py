"""report.py: one entry point the app and CLI share: facts + narrative + contract snapshot -> PDF bytes."""
from . import contracts, narrative, render

SNAPSHOT = [("MSA expires", "expiration_date"), ("Auto-renew", "auto_renew"), ("Tier 1 min doses", "tier_min_doses-1"),
            ("Tier 1 rebate", "tier_rebate_pct-1"), ("Share floor", "share_floor_pct"), ("Admin fee", "admin_fee_pct")]


def contract_snapshot(system_id: str) -> list:
    rows = []
    for label, key in SNAPSHOT:
        for h in contracts.lookup(system_id, field_key=key):
            lab = label if h["doc_id"].endswith("MSA1") or key != "share_floor_pct" else "Share floor (amended)"
            rows.append({"label": lab, **h})
    return rows


def brief_contract_lines(rows) -> list:
    """Brief tab 'Contracts on file': the same lines (and marker) as the PDF snapshot, render.contract_lines."""
    return render.contract_lines(rows)


def build(fs):
    n = narrative.compose(fs)
    rows = contract_snapshot(fs.system_id)
    return n, rows, render.render_pdf_bytes(fs, n, rows)
