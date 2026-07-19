"""Matplotlib chart images embedded in the Performance Baseline / Site Audit PDFs."""

from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

# Professional consulting palette
CHART_PRIMARY = "#1D4ED8"
CHART_SECONDARY = "#0F766E"
CHART_GRID = "#E2E8F0"
CHART_BG = "#FFFFFF"
CHART_PLOT_BG = "#F8FAFC"
CHART_TEXT = "#0F172A"
CHART_MUTED = "#64748B"
CHART_DPI = 160
SERIES_COLORS = ["#1D4ED8", "#0F766E", "#B45309", "#7C3AED", "#BE123C", "#0369A1"]


def _apply_rc() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"],
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.edgecolor": CHART_GRID,
            "axes.linewidth": 0.8,
            "figure.facecolor": CHART_BG,
            "axes.facecolor": CHART_PLOT_BG,
            "text.color": CHART_TEXT,
            "axes.labelcolor": CHART_MUTED,
            "xtick.color": CHART_MUTED,
            "ytick.color": CHART_MUTED,
        }
    )


def _y_tick_label(v: float, _p=None) -> str:
    """Compact y labels: integers when whole, else 2 decimals."""
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v))}"
    return f"{v:.2f}"


def _style_axes(
    ax,
    *,
    title: str,
    ylabel: str = "",
    title_size: float = 11,
    integer_y: bool = False,
) -> None:
    ax.set_title(title, fontsize=title_size, loc="left", color=CHART_TEXT, fontweight="600", pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8, color=CHART_MUTED, labelpad=4)
    ax.set_facecolor(CHART_PLOT_BG)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(CHART_GRID)
    ax.spines["bottom"].set_color(CHART_GRID)
    ax.tick_params(axis="both", labelsize=7, colors=CHART_MUTED, length=3, width=0.6)
    ax.grid(True, axis="y", alpha=0.85, color=CHART_GRID, linewidth=0.7, linestyle="--")
    ax.set_axisbelow(True)
    if integer_y:
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    else:
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=False))
    ax.yaxis.set_major_formatter(FuncFormatter(_y_tick_label))


def _values_are_integerish(values: list[float]) -> bool:
    return all(abs(v - round(v)) < 1e-6 for v in values)


def _fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=CHART_DPI,
        bbox_inches="tight",
        facecolor=CHART_BG,
        edgecolor="none",
        pad_inches=0.18,
    )
    plt.close(fig)
    return buf.getvalue()


def _annotate_bars(ax, bars, *, horizontal: bool = False) -> None:
    for bar in bars:
        if horizontal:
            width = bar.get_width()
            ax.text(
                width,
                bar.get_y() + bar.get_height() / 2,
                f" {_y_tick_label(width)}",
                va="center",
                ha="left",
                fontsize=7,
                color=CHART_MUTED,
            )
        else:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                _y_tick_label(height),
                va="bottom",
                ha="center",
                fontsize=7,
                color=CHART_MUTED,
            )


def mini_line_chart(title: str, labels: list[str], values: list[float], ylabel: str = "") -> bytes | None:
    """Compact line chart for Full Site Audit trend rows (correct aspect, no stretch)."""
    if not labels or not values:
        return None
    _apply_rc()
    # Wider canvas so half-page embedding stays sharp and unstretched
    fig, ax = plt.subplots(figsize=(4.4, 2.35))
    xs = list(range(len(values)))
    ax.plot(
        xs,
        values,
        color=CHART_PRIMARY,
        linewidth=2.0,
        marker="o",
        markersize=5,
        markerfacecolor="white",
        markeredgewidth=1.3,
        markeredgecolor=CHART_PRIMARY,
        zorder=3,
    )
    ax.fill_between(xs, values, alpha=0.10, color=CHART_PRIMARY, zorder=2)
    _style_axes(
        ax,
        title=title,
        ylabel=ylabel,
        title_size=10,
        integer_y=_values_are_integerish(values),
    )
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=7, rotation=0)
    # Keep first/last labels readable; avoid clipping the right edge
    ax.margins(x=0.06)
    if values:
        lo, hi = min(values), max(values)
        pad = max((hi - lo) * 0.15, 1.0 if hi <= 20 else hi * 0.08)
        ax.set_ylim(max(0, lo - pad * 0.2), hi + pad)
    fig.subplots_adjust(left=0.14, right=0.96, top=0.82, bottom=0.22)
    return _fig_to_png(fig)


def line_chart(title: str, labels: list[str], values: list[float], ylabel: str) -> bytes | None:
    if not labels or not values:
        return None
    _apply_rc()
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    xs = list(range(len(values)))
    ax.plot(
        xs,
        values,
        color=CHART_PRIMARY,
        linewidth=2.3,
        marker="o",
        markersize=5,
        markerfacecolor="white",
        markeredgewidth=1.4,
        markeredgecolor=CHART_PRIMARY,
        zorder=3,
    )
    ax.fill_between(xs, values, alpha=0.12, color=CHART_PRIMARY, zorder=2)
    if values:
        latest = values[-1]
        ax.annotate(
            _y_tick_label(latest),
            xy=(len(values) - 1, latest),
            xytext=(6, 8),
            textcoords="offset points",
            fontsize=8,
            color=CHART_PRIMARY,
            fontweight="600",
        )
    _style_axes(ax, title=title, ylabel=ylabel, integer_y=_values_are_integerish(values))
    ax.set_xticks(xs)
    # Show a readable subset of x labels when many points
    if len(labels) > 8:
        step = max(1, len(labels) // 6)
        shown = [lbl if i % step == 0 or i == len(labels) - 1 else "" for i, lbl in enumerate(labels)]
        ax.set_xticklabels(shown, fontsize=7, rotation=25, ha="right")
    else:
        ax.set_xticklabels(labels, fontsize=7, rotation=20, ha="right")
    ax.margins(x=0.04)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.86, bottom=0.22)
    return _fig_to_png(fig)


def bar_chart(title: str, labels: list[str], values: list[float], ylabel: str = "") -> bytes | None:
    if not labels or not values:
        return None
    _apply_rc()
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    colors = [SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(len(labels))]
    bars = ax.bar(labels, values, color=colors, width=0.58, edgecolor="white", linewidth=0.9, zorder=3)
    _style_axes(ax, title=title, ylabel=ylabel, integer_y=_values_are_integerish(values))
    _annotate_bars(ax, bars, horizontal=False)
    ax.tick_params(axis="x", labelsize=8, rotation=20)
    if values:
        ax.set_ylim(0, max(values) * 1.18 if max(values) > 0 else 1)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.86, bottom=0.24)
    return _fig_to_png(fig)


def horizontal_bar_chart(title: str, labels: list[str], values: list[float]) -> bytes | None:
    if not labels or not values:
        return None
    _apply_rc()
    fig, ax = plt.subplots(figsize=(7.4, max(3.1, 0.38 * len(labels))))
    y_pos = list(range(len(labels)))
    colors = [SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(len(labels))]
    bars = ax.barh(y_pos, values, color=colors, height=0.62, edgecolor="white", linewidth=0.9, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8, color=CHART_TEXT)
    _style_axes(ax, title=title, integer_y=_values_are_integerish(values))
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.85, color=CHART_GRID, linewidth=0.7, linestyle="--")
    ax.grid(False, axis="y")
    _annotate_bars(ax, bars, horizontal=True)
    if values:
        ax.set_xlim(0, max(values) * 1.22 if max(values) > 0 else 1)
    fig.subplots_adjust(left=0.28, right=0.96, top=0.88, bottom=0.10)
    return _fig_to_png(fig)
