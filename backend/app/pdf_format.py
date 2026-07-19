"""Shared number/text formatting for professional PDF reports."""

from __future__ import annotations


def _to_float(value) -> float:
    """Parse ints/floats/numeric strings (optionally with a trailing %)."""
    if isinstance(value, str):
        value = value.strip().replace(",", "").rstrip("%")
    return float(value)


def fmt_num(value, *, decimals: int = 2, default: str = "—") -> str:
    """Format a number with fixed decimals."""
    try:
        return f"{_to_float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return default if value in (None, "") else str(value)


def fmt_score(value, *, decimals: int = 2, default: str = "—") -> str:
    """Format a 0–100 score with fixed decimals."""
    try:
        return f"{_to_float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return default


def fmt_pct(value, *, decimals: int = 2, default: str = "—") -> str:
    """Format a percent. Values ≤ 1 are treated as ratios."""
    try:
        raw = value
        had_percent = isinstance(raw, str) and "%" in raw
        v = _to_float(raw)
        # Ratios (0–1) become percents; already-percent values (or strings with %) stay as-is.
        if not had_percent and v <= 1:
            v *= 100
        return f"{v:.{decimals}f}%"
    except (TypeError, ValueError):
        return default if value in (None, "") else str(value)


def fmt_count(value, *, default: str = "—") -> str:
    """Format a count/metric for tables: whole numbers as ints, else 2 decimals."""
    try:
        v = _to_float(value)
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v)):,}"
        return f"{v:.2f}"
    except (TypeError, ValueError):
        return default if value in (None, "") else str(value)


def fmt_users(value, *, default: str = "—") -> str:
    """Format a user/count metric (K for thousands)."""
    try:
        v = _to_float(value)
        if abs(v) >= 1000:
            return f"{v / 1000:.2f}K"
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.2f}"
    except (TypeError, ValueError):
        return default if value in (None, "") else str(value)


def fmt_duration(value, *, default: str = "—") -> str:
    """Format seconds as Xm Ys."""
    try:
        seconds = float(value)
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs:02d}s"
    except (TypeError, ValueError):
        return default if value in (None, "") else str(value)


def fmt_ms(value, *, decimals: int = 2, default: str = "—") -> str:
    """Format milliseconds."""
    try:
        return f"{float(value):.{decimals}f} ms"
    except (TypeError, ValueError):
        return default


def fmt_seconds_from_ms(value, *, decimals: int = 2, default: str = "—") -> str:
    """Format a millisecond value as seconds."""
    try:
        return f"{float(value) / 1000:.{decimals}f}s"
    except (TypeError, ValueError):
        return default
