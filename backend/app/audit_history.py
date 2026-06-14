"""SQLite history of Full Site Audit metrics for trend charts (saved on each audit when changed)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.config import PROJECT_ROOT, Settings, get_settings
from app.crawl import registrable_host
from app.models import Report


@dataclass(frozen=True)
class SiteAuditSnapshot:
    """One stored audit run used as a point on Full Site Audit trend charts."""

    domain: str
    audited_at: datetime
    site_health: float
    crawled_pages: int
    errors: int
    warnings: int
    notices: int
    healthy_pages: int
    broken_pages: int
    have_issues: int
    redirected: int
    blocked: int


def default_db_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw = getattr(settings, "audit_history_db_path", "") or str(
        PROJECT_ROOT / "backend" / "data" / "audit_history.db"
    )
    return Path(raw)


def _metrics_tuple(snapshot: SiteAuditSnapshot) -> tuple:
    return (
        snapshot.site_health,
        snapshot.crawled_pages,
        snapshot.errors,
        snapshot.warnings,
        snapshot.notices,
        snapshot.healthy_pages,
        snapshot.broken_pages,
        snapshot.have_issues,
        snapshot.redirected,
        snapshot.blocked,
    )


class AuditHistoryStore:
    """Persist and query Full Site Audit snapshots per domain."""

    def __init__(self, db_path: Path | None = None, settings: Settings | None = None) -> None:
        self._path = db_path or default_db_path(settings)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_snapshots'"
            ).fetchone():
                columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_snapshots)")}
                if "week_start" in columns:
                    self._migrate_from_weekly_schema(conn)

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    audited_at TEXT NOT NULL,
                    site_health REAL NOT NULL,
                    crawled_pages INTEGER NOT NULL,
                    errors INTEGER NOT NULL,
                    warnings INTEGER NOT NULL,
                    notices INTEGER NOT NULL,
                    healthy_pages INTEGER NOT NULL,
                    broken_pages INTEGER NOT NULL,
                    have_issues INTEGER NOT NULL,
                    redirected INTEGER NOT NULL,
                    blocked INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_snapshots_domain_at "
                "ON audit_snapshots(domain, audited_at)"
            )

    def _migrate_from_weekly_schema(self, conn: sqlite3.Connection) -> None:
        """Convert legacy one-row-per-week table to per-change run history."""
        legacy_rows = conn.execute(
            "SELECT * FROM audit_snapshots ORDER BY domain, audited_at"
        ).fetchall()
        conn.execute("DROP TABLE audit_snapshots")
        conn.execute(
            """
            CREATE TABLE audit_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                audited_at TEXT NOT NULL,
                site_health REAL NOT NULL,
                crawled_pages INTEGER NOT NULL,
                errors INTEGER NOT NULL,
                warnings INTEGER NOT NULL,
                notices INTEGER NOT NULL,
                healthy_pages INTEGER NOT NULL,
                broken_pages INTEGER NOT NULL,
                have_issues INTEGER NOT NULL,
                redirected INTEGER NOT NULL,
                blocked INTEGER NOT NULL
            )
            """
        )
        seen: dict[str, tuple] = {}
        for row in legacy_rows:
            snap = _row_to_snapshot(row, legacy=True)
            key = snap.domain
            metrics = _metrics_tuple(snap)
            if seen.get(key) == metrics:
                continue
            seen[key] = metrics
            self._insert(conn, snap)

    def _insert(self, conn: sqlite3.Connection, snapshot: SiteAuditSnapshot) -> None:
        conn.execute(
            """
            INSERT INTO audit_snapshots (
                domain, audited_at,
                site_health, crawled_pages, errors, warnings, notices,
                healthy_pages, broken_pages, have_issues, redirected, blocked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.domain,
                snapshot.audited_at.astimezone(timezone.utc).isoformat(),
                snapshot.site_health,
                snapshot.crawled_pages,
                snapshot.errors,
                snapshot.warnings,
                snapshot.notices,
                snapshot.healthy_pages,
                snapshot.broken_pages,
                snapshot.have_issues,
                snapshot.redirected,
                snapshot.blocked,
            ),
        )

    def latest(self, domain: str) -> SiteAuditSnapshot | None:
        key = registrable_host(domain) if "." in domain else domain
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM audit_snapshots
                WHERE domain = ?
                ORDER BY audited_at DESC
                LIMIT 1
                """,
                (key,),
            ).fetchone()
        return _row_to_snapshot(row) if row else None

    def save_if_changed(self, snapshot: SiteAuditSnapshot) -> bool:
        """Insert a row when metrics differ from the last stored run for this domain."""
        previous = self.latest(snapshot.domain)
        if previous is not None and _metrics_tuple(previous) == _metrics_tuple(snapshot):
            return False
        with self._connect() as conn:
            self._insert(conn, snapshot)
        return True

    def history(self, domain: str, *, limit: int = 12) -> list[SiteAuditSnapshot]:
        """Return up to `limit` snapshots oldest-first."""
        key = registrable_host(domain) if "." in domain else domain
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_snapshots
                WHERE domain = ?
                ORDER BY audited_at DESC
                LIMIT ?
                """,
                (key, limit),
            ).fetchall()
        return [_row_to_snapshot(row) for row in reversed(rows)]


def build_site_audit_snapshot(seo: Report, geo: Report, final_url: str) -> SiteAuditSnapshot:
    """Derive snapshot metrics using the same rules as the Full Site Audit PDF."""
    from app.reference_pdf_catalog import SITE_AUDIT_FULL_PARAMS
    from app.reference_pdf_export import (
        _audit_section_rows,
        _crawled_pages,
        _index_parameters,
        _issue_count,
        _redirected_pages,
        _resolve_row,
        _site_health_score,
    )

    domain = registrable_host(urlparse(final_url).netloc)
    index = _index_parameters(seo, geo)
    rows = [_resolve_row(entry, index) for entry in SITE_AUDIT_FULL_PARAMS]
    by_name = {r.name: r for r in rows}
    errors = _audit_section_rows(rows, "Errors")
    warnings = _audit_section_rows(rows, "Warnings")
    notices = _audit_section_rows(rows, "Notices")
    err_count = sum(_issue_count(r) for r in errors)
    warn_count = sum(_issue_count(r) for r in warnings)
    notice_count = sum(_issue_count(r) for r in notices)
    crawled = _crawled_pages(seo)
    health = _site_health_score(seo, by_name)
    redirected = int(_redirected_pages(by_name) or 0)
    have_issues = err_count + warn_count + notice_count
    healthy = max(0, crawled - have_issues)

    return SiteAuditSnapshot(
        domain=domain,
        audited_at=datetime.now(timezone.utc),
        site_health=round(health, 1),
        crawled_pages=crawled,
        errors=err_count,
        warnings=warn_count,
        notices=notice_count,
        healthy_pages=healthy,
        broken_pages=0,
        have_issues=have_issues,
        redirected=redirected,
        blocked=0,
    )


def save_audit_snapshot(
    seo: Report,
    geo: Report,
    final_url: str,
    store: AuditHistoryStore | None = None,
) -> tuple[SiteAuditSnapshot, bool]:
    """Build metrics and persist only when they changed since the last audit run."""
    snapshot = build_site_audit_snapshot(seo, geo, final_url)
    saved = (store or AuditHistoryStore()).save_if_changed(snapshot)
    return snapshot, saved


def _row_to_snapshot(row: sqlite3.Row, *, legacy: bool = False) -> SiteAuditSnapshot:
    audited_raw = row["audited_at"]
    audited_at = datetime.fromisoformat(audited_raw)
    if audited_at.tzinfo is None:
        audited_at = audited_at.replace(tzinfo=timezone.utc)
    return SiteAuditSnapshot(
        domain=row["domain"],
        audited_at=audited_at,
        site_health=float(row["site_health"]),
        crawled_pages=int(row["crawled_pages"]),
        errors=int(row["errors"]),
        warnings=int(row["warnings"]),
        notices=int(row["notices"]),
        healthy_pages=int(row["healthy_pages"]),
        broken_pages=int(row["broken_pages"]),
        have_issues=int(row["have_issues"]),
        redirected=int(row["redirected"]),
        blocked=int(row["blocked"]),
    )
