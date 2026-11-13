"""Value formatting for rendered facts (renderer side only; narrative tokens never carry digits)."""


def usd(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        return f"${v / 1e6:,.2f}M"
    if a >= 1e4:
        return f"${v / 1e3:,.1f}K"
    return f"${v:,.0f}"


def fmt_fact(f) -> str:
    v = f.value
    if v is None:
        return "n/a"
    if f.unit == "usd":
        return usd(v)
    if f.unit == "doses":
        return f"{int(v):,}"
    if f.unit == "pct":
        return f"{v:+.1f}%" if f.fact_id == "F7.growth_pct" else f"{v:.1f}%"
    if f.unit == "ratio":
        return f"{v:.2f}"
    if f.unit == "index":
        return f"{v:.0f}"
    if f.unit == "int":
        return f"{int(v):,}"
    if f.unit == "pct_fine":  # v0.2 small shares, e.g. one system's share of national dollars (A1)
        return f"{v:.1f}%" if abs(v) >= 1 else f"{v:.4f}%"
    if f.unit == "median":  # v0.2 peer medians (client_metrics.py)
        return f"{int(v):,}" if float(v).is_integer() else f"{v:,.1f}"
    if f.unit == "est":     # v0.2 heuristic estimates, e.g. the client's babies estimate (A10)
        return f"~{v:,.0f}"
    return str(v)
