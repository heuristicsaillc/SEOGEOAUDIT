"""Matplotlib chart images embedded in the Performance Baseline PDF."""

from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

CHART_PRIMARY = "#2563EB"
CHART_SECONDARY = "#6366F1"
CHART_GRID = "#E5E7EB"
CHART_BG = "#FAFBFC"
CHART_TEXT = "#1F2937"
CHART_MUTED = "#6B7280"
CHART_DPI = 144


def _style_axes(ax, *, title: str, ylabel: str = "", title_size: float = 11) -> None:
    ax.set_title(title, fontsize=title_size, loc="left", color=CHART_TEXT, fontweight="600", pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=CHART_MUTED)
    ax.set_facecolor(CHART_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(CHART_GRID)
    ax.spines["bottom"].set_color(CHART_GRID)
    ax.tick_params(axis="both", labelsize=8, colors=CHART_MUTED)
    ax.grid(True, axis="y", alpha=0.55, color=CHART_GRID, linewidth=0.8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=False))


def _fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=CHART_DPI, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def mini_line_chart(title: str, labels: list[str], values: list[float], ylabel: str = "") -> bytes | None:
    """Compact line chart for Full Site Audit trend rows (Semrush-style)."""
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(3.5, 1.65))
    fig.patch.set_facecolor("white")
    ax.plot(labels, values, color=CHART_PRIMARY, linewidth=2.0, marker="o", markersize=4, markerfacecolor="white")
    _style_axes(ax, title=title, ylabel=ylabel, title_size=9)
    ax.tick_params(axis="x", labelsize=6, rotation=35)
    fig.tight_layout(pad=0.8)
    return _fig_to_png(fig)


def line_chart(title: str, labels: list[str], values: list[float], ylabel: str) -> bytes | None:
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    fig.patch.set_facecolor("white")
    ax.plot(labels, values, color=CHART_PRIMARY, linewidth=2.2, marker="o", markersize=4, markerfacecolor="white")
    ax.fill_between(range(len(values)), values, alpha=0.08, color=CHART_PRIMARY)
    _style_axes(ax, title=title, ylabel=ylabel)
    ax.tick_params(axis="x", labelsize=7, rotation=45)
    fig.tight_layout(pad=1.0)
    return _fig_to_png(fig)


def bar_chart(title: str, labels: list[str], values: list[float], ylabel: str = "") -> bytes | None:
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    fig.patch.set_facecolor("white")
    colors = [CHART_PRIMARY if i % 2 == 0 else CHART_SECONDARY for i in range(len(labels))]
    ax.bar(labels, values, color=colors, width=0.62, edgecolor="white", linewidth=0.8)
    _style_axes(ax, title=title, ylabel=ylabel)
    ax.tick_params(axis="x", labelsize=8, rotation=28)
    fig.tight_layout(pad=1.0)
    return _fig_to_png(fig)


def horizontal_bar_chart(title: str, labels: list[str], values: list[float]) -> bytes | None:
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(7.4, max(3.0, 0.32 * len(labels))))
    fig.patch.set_facecolor("white")
    y_pos = range(len(labels))
    ax.barh(list(y_pos), values, color=CHART_SECONDARY, height=0.65, edgecolor="white", linewidth=0.8)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=8, color=CHART_TEXT)
    _style_axes(ax, title=title)
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.55, color=CHART_GRID, linewidth=0.8)
    ax.grid(False, axis="y")
    fig.tight_layout(pad=1.0)
    return _fig_to_png(fig)
