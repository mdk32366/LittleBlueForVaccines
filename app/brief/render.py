"""render.py: the one-page letter PDF is ONE matplotlib figure (§0 item 5, D-0004 (single-figure PDF)), so it is one page
by construction. Talking points sit in a fixed box and truncate with an ellipsis."""
import io
import textwrap

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42  # TrueType: text stays extractable (T-0008 / T-0035 read it back)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from . import charts, config, contracts  # noqa: E402
from .fmt import fmt_fact  # noqa: E402

LETTER = (8.5, 11)
POINT_WIDTH = 62     # characters per wrapped line in the points box
POINT_LINES = 26     # line budget for the points box


def header_text() -> str:
    return f"{config.APP_NAME} | Account Brief"


def footer_text(fs) -> str:
    bench = (f"Benchmark: {fs.benchmark_label}" + (", D-0034 (national file public-real)" if fs.benchmark == "national"
                                                  else f" ({fs.v('F1.n_systems')} systems)")
             + (" [fallback]" if fs.benchmark_note else ""))
    return (f"{bench} | rank and in-state: {config.BENCH_LABEL} | SYNTHETIC sales data, D-0022 (fake data) | "
            f"mix and volume only, no pricing advice | as of {fs.as_of} | {fs.fs_id}")


def fit_points(points, width=POINT_WIDTH, max_lines=POINT_LINES) -> list:
    lines = []
    for p in points:
        w = textwrap.wrap(p, width) or [""]
        w = ["• " + w[0]] + ["  " + x for x in w[1:]]
        lines.extend(w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def contract_lines(contract_rows) -> list:
    out = []
    for r in contract_rows[:6]:
        mark = f" {contracts.EXPIRED_MARKER}" if r.get("expired") else ""
        out.append(f"{r['label']}: {r['span']}{mark}  ({r['anchor']})")
    return out or ["No generated contracts found for this system."]


def build_figure(fs, narrative, contract_rows=()):
    fig = plt.figure(figsize=LETTER)
    fig.text(0.05, 0.965, header_text(), fontsize=15, weight="bold", color=charts.BLUE)
    fig.text(0.05, 0.945, f"{fs.name} ({fs.system_id}), {fs.state}   SYNTHETIC", fontsize=10)
    tiles = [("Dollars (net)", fmt_fact(fs.facts["F1.dollars"])), ("Doses", fmt_fact(fs.facts["F1.doses"])),
             ("Rank of peers", f"{fs.v('F1.rank')} / {fs.v('F1.n_systems')}"),
             ("Pfizer share", fmt_fact(fs.facts["F4.pfizer_share"])), ("Switching", "flagged" if fs.v("F5.n_flags") else "none"),
             ("MenB:MenACWY", fmt_fact(fs.facts["F6.ratio"]) if "F6.ratio" in fs.facts else fs.v("F6.status"))]
    for i, (k, v) in enumerate(tiles):
        x = 0.05 + i * 0.152
        fig.text(x, 0.915, k, fontsize=7, color="#555555")
        fig.text(x, 0.897, v, fontsize=10, weight="bold")
    charts.draw_class_mix(fig.add_axes([0.17, 0.66, 0.30, 0.19]), fs)
    charts.draw_mfr(fig.add_axes([0.66, 0.66, 0.28, 0.19]), fs)
    charts.draw_trend(fig.add_axes([0.08, 0.40, 0.40, 0.19]), fs)
    charts.draw_facility(fig.add_axes([0.66, 0.40, 0.28, 0.19]), fs)
    fig.text(0.05, 0.335, "Talking points (templated from fact tokens; LLM off)", fontsize=9, weight="bold")
    fig.text(0.05, 0.325, "\n".join(fit_points(narrative.rendered)), fontsize=7, va="top", family="DejaVu Sans")
    fig.text(0.56, 0.335, "Contracts on file (generated, cited)", fontsize=9, weight="bold")
    fig.text(0.56, 0.325, "\n".join(textwrap.fill(x, 52) for x in contract_lines(list(contract_rows))),
             fontsize=6.5, va="top")
    fig.text(0.05, 0.03, "\n".join(textwrap.wrap(footer_text(fs), 150)), fontsize=6.5, color="#555555", va="bottom")
    return fig


def render_pdf_bytes(fs, narrative, contract_rows=()) -> bytes:
    fig = build_figure(fs, narrative, contract_rows)
    buf = io.BytesIO()
    with PdfPages(buf, metadata={"Title": f"{config.APP_NAME}: {fs.system_id}", "Creator": config.APP_NAME}) as pdf:
        pdf.savefig(fig)
    plt.close(fig)
    return buf.getvalue()


def pdf_page_count(data: bytes) -> int:
    import re
    return len(re.findall(rb"/Type\s*/Page\b(?!s)", data))
