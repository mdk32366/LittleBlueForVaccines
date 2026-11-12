"""charts.py: matplotlib on the headless Agg backend. Each draw_* fills a given Axes, so the app and the
one-figure PDF share the same drawing code."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .facts import PFIZER  # noqa: E402
from .fmt import usd  # noqa: E402

BLUE, GREY, HIGHLIGHT = "#1f4e9c", "#9aa5b1", "#0b84d8"


def _barh(ax, labels, values, colors, title):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=colors)
    ax.set_yticks(list(y), labels, fontsize=7)
    ax.set_title(title, fontsize=9, loc="left")
    ax.tick_params(axis="x", labelsize=6)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: usd(v)))
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def draw_class_mix(ax, fs):
    s = fs.v("F2.by_class")
    _barh(ax, [k for k, _ in s], [v for _, v in s], BLUE, "F2  Dollars by class (top 5 + Other)")


def draw_mfr(ax, fs, top=8):
    s = fs.v("F4.by_mfr")[:top]
    _barh(ax, [k.title() for k, _ in s], [v for _, v in s], [HIGHLIGHT if k == PFIZER else GREY for k, _ in s],
          "F4  Dollars by mfr (Pfizer highlighted)")


def draw_trend(ax, fs, top=6):
    s = sorted(fs.v("F7.by_class"), key=lambda x: -(x[1] + x[2]))[:top]
    labels = [k for k, _, _ in s]
    x = range(len(labels))
    ax.bar([i - 0.2 for i in x], [p for _, _, p in s], 0.4, color=GREY, label="prior 12 mo")
    ax.bar([i + 0.2 for i in x], [t for _, t, _ in s], 0.4, color=BLUE, label="trailing 12 mo")
    ax.set_xticks(list(x), labels, fontsize=6, rotation=20)
    ax.tick_params(axis="y", labelsize=6)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: usd(v)))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
    ax.legend(fontsize=6, frameon=False)
    ax.set_title("F7  Trailing 12 vs prior 12 months by class", fontsize=9, loc="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def draw_facility(ax, fs, top=6):
    s = fs.v("F3.by_facility")[:top]
    _barh(ax, [k for k, _ in s], [v for _, v in s], BLUE, "F3  Dollars by facility type")


def figure(draw, fs, size=(5, 3)):
    fig, ax = plt.subplots(figsize=size)
    draw(ax, fs)
    fig.tight_layout()
    return fig
