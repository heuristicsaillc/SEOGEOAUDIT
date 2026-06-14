"""Bucket crawled pages by incoming internal link count (Semrush-style distribution)."""

from __future__ import annotations

from typing import Callable

_BUCKETS: list[tuple[str, Callable[[int], bool]]] = [
    ("0 links", lambda n: n == 0),
    ("1 link", lambda n: n == 1),
    ("2 - 10 links", lambda n: 2 <= n <= 10),
    ("11 - 50 links", lambda n: 11 <= n <= 50),
    ("51 - 100 links", lambda n: 51 <= n <= 100),
    ("More than 100 links", lambda n: n > 100),
]


def compute_internal_link_distribution(
    crawled_urls: list[str],
    inlink_counts: dict[str, int],
) -> list[dict[str, float | int | str]]:
    """Return bucket rows: label, pages, pct."""
    total = len(crawled_urls) or 1
    rows: list[dict[str, float | int | str]] = []
    for label, pred in _BUCKETS:
        pages = sum(1 for url in crawled_urls if pred(inlink_counts.get(url, 0)))
        rows.append(
            {
                "label": label,
                "pages": pages,
                "pct": round(pages / total * 100, 2),
            }
        )
    return rows


def count_single_inlink_pages(crawled_urls: list[str], inlink_counts: dict[str, int]) -> int:
    return sum(1 for url in crawled_urls if inlink_counts.get(url, 0) == 1)
