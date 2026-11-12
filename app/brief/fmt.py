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
    return str(v)
