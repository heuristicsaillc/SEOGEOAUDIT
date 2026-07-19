"""Build supplementary PDFs matching the three reference report layouts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO

from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.ai_health import compute_ai_search_health
from app.audit_history import AuditHistoryStore
from app.baseline_analytics import BaselineAnalytics
from app.baseline_charts import bar_chart, horizontal_bar_chart, line_chart, mini_line_chart
from app.config import get_settings
from app.developer_fixes import developer_fix_text, enrich_report
from app.models import ParameterResult, Rating, Report
from app.pdf_format import fmt_count, fmt_duration, fmt_num, fmt_pct, fmt_score, fmt_users
from app.reference_pdf_catalog import (
    CATALOG_BY_PDF,
    PDF_FILENAMES,
    RefParameter,
)
from app.reference_pdf_layout import (
    CONTENT_BOTTOM_MARGIN,
    CONTENT_TOP_MARGIN,
    MARGIN,
    PAGE_SIZE,
    TABLE_RULE,
    _format_developer_fix_html,
    audit_cover,
    audit_generated_label,
    audit_issue_table,
    baseline_cover,
    chart_image,
    data_table,
    date_range_label,
    distribution_table,
    draw_audit_page_decor,
    draw_baseline_page_number,
    executive_summary,
    issue_counts_table,
    kpi_grid,
    para,
    section_spacer,
    subsection_spacer,
    styles,
)


@dataclass
class ResolvedRow:
    name: str
    section: str
    rating: str
    detail: str
    source: str
    is_manual: bool
    manual_reason: str
    param: ParameterResult | None = None


_AI_OVERVIEW_ACTION_SKIP = frozenset(
    {
        "Site Health score",
        "AI Search Health score (percentage)",
        "AI Search Health score",
        "Crawled pages stats (Blocked/Redirect/Broken/Healthy)",
        "Crawl status inventory",
        "Pages blocked from AI search (aggregate %)",
        "AI blocked pages aggregate",
        "Top Issues list (Errors/Warnings dashboard)",
    }
)


def build_reference_pdf(
    kind: str,
    *,
    seo: Report,
    geo: Report,
    final_url: str,
    duration_seconds: float = 0.0,
    connected: bool = False,
    analytics: BaselineAnalytics | None = None,
) -> bytes:
    if kind not in CATALOG_BY_PDF:
        raise ValueError(f"Unknown supplementary PDF kind: {kind}")

    enrich_report(seo, page_url=final_url)
    enrich_report(geo, page_url=final_url)

    catalog = CATALOG_BY_PDF[kind]
    index = _index_parameters(seo, geo)
    if kind == "performance_baseline":
        rows = _resolve_baseline_rows(catalog, index, analytics, connected)
    else:
        rows = [_resolve_row(entry, index) for entry in catalog]
    by_name = {r.name: r for r in rows}
    manual_rows = [r for r in rows if r.is_manual]
    if kind == "performance_baseline" and analytics is not None:
        manual_rows = _filter_manual_with_analytics(manual_rows, analytics)

    if kind == "performance_baseline":
        return _build_baseline_pdf(
            by_name,
            manual_rows,
            seo=seo,
            final_url=final_url,
            analytics=analytics,
            connected=connected,
        )
    if kind == "site_audit_full":
        return _build_site_audit_full_pdf(rows, manual_rows, seo=seo, final_url=final_url)
    return _build_ai_search_overview_pdf(by_name, manual_rows, seo=seo, geo=geo, final_url=final_url)


def supplementary_filename(kind: str, final_url: str) -> str:
    host = (
        final_url.replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
        .replace("www.", "")
        or "site"
    )
    stem = PDF_FILENAMES.get(kind, kind)
    return f"{stem}-{host}.pdf"


def _build_baseline_pdf(
    by_name: dict[str, ResolvedRow],
    manual_rows: list[ResolvedRow],
    *,
    seo: Report,
    final_url: str,
    analytics: BaselineAnalytics | None = None,
    connected: bool = False,
) -> bytes:
    st = styles()
    range_label, generated_label = date_range_label()
    panel = seo.panel or {}
    host = _host(final_url)
    story: list = []

    story.extend(baseline_cover(st, range_label, generated_label, domain=host))
    story.append(PageBreak())
    baseline_actions = _baseline_action_items(by_name, seo, panel, page_url=final_url)
    story.extend(
        executive_summary(
            st,
            domain=host,
            report_label="Performance Baseline",
            score_badges=[("SEO score", seo.score, seo.grade)],
            score_lines=_key_metric_issue_lines(seo),
            narrative=_short_executive_overview(
                score=seo.score,
                grade=seo.grade,
                score_label="SEO score",
                action_items=baseline_actions,
                focus="performance and SEO",
            ),
            action_items=baseline_actions,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Overview", st["section_title"]))
    overview_kpis = _baseline_overview_kpis(by_name, panel, analytics)
    if overview_kpis:
        story.append(kpi_grid(overview_kpis, st, cols=3))

    if analytics and analytics.gsc_device:
        story.append(subsection_spacer())
        story.append(Paragraph("Clicks: Device", st["subsection"]))
        device_rows = [
            [r["label"], fmt_pct(r["share"]), fmt_count(r["clicks"])]
            for r in analytics.gsc_device
        ]
        story.append(
            data_table(
                ["Device", "Share", "Clicks"],
                device_rows,
                st,
                col_widths=[1.6 * inch, 1.0 * inch, 1.0 * inch],
                center_cols={1, 2},
            )
        )
        png = bar_chart(
            "Clicks by Device",
            [r["label"] for r in analytics.gsc_device],
            [r["clicks"] for r in analytics.gsc_device],
            ylabel="Clicks",
        )
        if png:
            story.append(subsection_spacer())
            story.append(chart_image(png))

    if analytics and analytics.gsc_country:
        story.append(subsection_spacer())
        story.append(Paragraph("Clicks: Country", st["subsection"]))
        country_rows = [
            [r["label"], fmt_pct(r["share"]), fmt_count(r["clicks"])]
            for r in analytics.gsc_country[:10]
        ]
        story.append(
            data_table(
                ["Country", "Share", "Clicks"],
                country_rows,
                st,
                col_widths=[2.2 * inch, 1.0 * inch, 1.0 * inch],
                center_cols={1, 2},
            )
        )

    if analytics and analytics.gsc_top_pages:
        story.append(section_spacer())
        story.append(Paragraph("Organic traffic trend (SEO performance)", st["section_title"]))
        story.append(Paragraph(para(f"US | Domain | {host}"), st["muted"]))
        page_rows = [
            [r["label"][:55], fmt_pct(r["share"]), fmt_count(r["clicks"])]
            for r in analytics.gsc_top_pages[:20]
        ]
        story.append(
            data_table(
                ["URL", "Traffic %", "Clicks"],
                page_rows,
                st,
                col_widths=[3.5 * inch, 1.0 * inch, 1.0 * inch],
                center_cols={1, 2},
            )
        )

    if analytics and analytics.ga4_channels:
        story.append(section_spacer())
        channel_rows = [
            [
                r.get("sessionDefaultChannelGroup", ""),
                fmt_count(r.get("totalUsers")),
                fmt_count(r.get("screenPageViews")),
                fmt_count(r.get("sessions")),
                _fmt_duration(r.get("averageSessionDuration")),
                _fmt_pct(r.get("engagementRate")),
            ]
            for r in analytics.ga4_channels
        ]
        traffic_block: list = [
            Paragraph("Monthly total traffic (Source – organic, direct, referral)", st["section_title"]),
            data_table(
                ["Channel", "Users", "Views", "Sessions", "Avg. Session Duration", "Engagement Rate"],
                channel_rows,
                st,
                col_widths=[1.3 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 1.1 * inch, 0.9 * inch],
            ),
        ]
        story.append(KeepTogether(traffic_block))
        png = bar_chart(
            "Traffic by Channel",
            [r.get("sessionDefaultChannelGroup", "") for r in analytics.ga4_channels[:8]],
            [float(r.get("sessions", 0) or 0) for r in analytics.ga4_channels[:8]],
            ylabel="Sessions",
        )
        if png:
            story.append(subsection_spacer())
            story.append(chart_image(png))

    if analytics and analytics.ga4_sources:
        story.append(section_spacer())
        story.append(Paragraph("Session source breakdown", st["section_title"]))
        source_rows = [
            [
                r.get("sessionSource", ""),
                fmt_count(r.get("totalUsers")),
                fmt_count(r.get("screenPageViews")),
                fmt_count(r.get("sessions")),
                _fmt_duration(r.get("averageSessionDuration")),
                _fmt_pct(r.get("engagementRate")),
            ]
            for r in analytics.ga4_sources[:20]
        ]
        story.append(
            data_table(
                ["Session Source", "Users", "Views", "Sessions", "Avg. Session Duration", "Engagement Rate"],
                source_rows,
                st,
                col_widths=[1.4 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 1.0 * inch, 0.9 * inch],
            )
        )

    if analytics is not None:
        story.append(subsection_spacer())
        story.append(Paragraph("Organic Social", st["subsection"]))
        social_rows = analytics.ga4_social or [
            {
                "sessionDefaultChannelGroup": "Organic Social",
                "totalUsers": "0",
                "sessions": "0",
                "engagementRate": "0",
            }
        ]
        story.append(
            data_table(
                ["Channel", "Users", "Sessions", "Engagement Rate"],
                [
                    [
                        r.get("sessionDefaultChannelGroup", "Organic Social"),
                        fmt_count(r.get("totalUsers", "0")),
                        fmt_count(r.get("sessions", "0")),
                        _fmt_pct(r.get("engagementRate")),
                    ]
                    for r in social_rows
                ],
                st,
                col_widths=[1.8 * inch, 1.0 * inch, 1.0 * inch, 1.2 * inch],
            )
        )

    if analytics and analytics.ga4_channels:
        story.append(subsection_spacer())
        story.append(Paragraph("Session Primary Channel Group", st["subsection"]))
        story.append(
            data_table(
                ["Channel", "Users", "Views", "Sessions", "Avg. Session Duration", "Engagement Rate"],
                [
                    [
                        r.get("sessionDefaultChannelGroup", ""),
                        fmt_count(r.get("totalUsers")),
                        fmt_count(r.get("screenPageViews")),
                        fmt_count(r.get("sessions")),
                        _fmt_duration(r.get("averageSessionDuration")),
                        _fmt_pct(r.get("engagementRate")),
                    ]
                    for r in analytics.ga4_channels
                ],
                st,
                col_widths=[1.3 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 1.1 * inch, 0.9 * inch],
            )
        )

    if analytics is not None:
        story.append(section_spacer())
        story.append(Paragraph("Top 20 Ranking Keywords — Current Position", st["section_title"]))
        story.append(Paragraph("Top Keywords", st["subsection"]))
        if analytics.gsc_keywords:
            kw_rows = [
                [
                    r["label"],
                    fmt_pct(r["ctr"]),
                    fmt_num(r["position"]),
                    fmt_count(r["clicks"]),
                    fmt_count(r["impressions"]),
                ]
                for r in analytics.gsc_keywords[:20]
            ]
            story.append(
                data_table(
                    ["Query", "Average CTR", "Average Position", "Clicks", "Impressions"],
                    kw_rows,
                    st,
                    col_widths=[1.8 * inch, 0.9 * inch, 1.0 * inch, 0.8 * inch, 1.0 * inch],
                    center_cols={1, 2, 3, 4},
                )
            )
            png = horizontal_bar_chart(
                "Top Keywords by Clicks",
                [r["label"][:40] for r in analytics.gsc_keywords[:10]],
                [r["clicks"] for r in analytics.gsc_keywords[:10]],
            )
            if png:
                story.append(Spacer(1, 0.06 * inch))
                story.append(chart_image(png, height_ratio=0.28))
        elif not analytics.gsc_keywords_ok and analytics.gsc_keywords_error:
            story.append(
                Paragraph(
                    para(_friendly_gsc_keyword_message(analytics.gsc_keywords_error)),
                    st["body"],
                )
            )
        else:
            story.append(
                Paragraph(
                    para(
                        "No keyword data in Google Search Console for this period. "
                        "Confirm the property is verified and has search impressions, then re-run the audit."
                    ),
                    st["body"],
                )
            )

    if analytics is not None and (analytics.ga4_bounce_trend or analytics.ga4_engagement_trend):
        story.append(section_spacer())
        story.append(Paragraph("Bounce rate &amp; Average engagement time", st["section_title"]))
        if analytics.ga4_bounce_trend:
            labels = [_fmt_chart_date(r.get("date", "")) for r in analytics.ga4_bounce_trend]
            values = [float(r.get("bounceRate", 0) or 0) * 100 for r in analytics.ga4_bounce_trend]
            png = line_chart("Bounce Rate Trend", labels, values, ylabel="Bounce rate (%)")
            if png:
                story.append(chart_image(png))
        if analytics.ga4_engagement_trend:
            story.append(subsection_spacer())
            elabels = [_fmt_chart_date(r.get("date", "")) for r in analytics.ga4_engagement_trend]
            evalues = [float(r.get("averageSessionDuration", 0) or 0) for r in analytics.ga4_engagement_trend]
            epng = line_chart("Average Session Duration Trend", elabels, evalues, ylabel="Seconds")
            if epng:
                story.append(chart_image(epng))
        elif connected:
            story.append(Paragraph("Average session duration trend: no daily data in the selected period.", st["body"]))

    if analytics and analytics.overview.get("screenPageViewsPerSession"):
        story.append(section_spacer())
        story.append(Paragraph("Pages per session", st["section_title"]))
        story.append(
            Paragraph(
                para(f"Average pages per session: {fmt_num(analytics.overview['screenPageViewsPerSession'])}"),
                st["body"],
            )
        )

    if analytics and analytics.ga4_devices:
        story.append(section_spacer())
        story.append(Paragraph("Mobile vs Desktop traffic split", st["section_title"]))
        story.append(Paragraph("Metrics: Device Category", st["muted"]))
        story.append(
            data_table(
                ["Device Category", "Users", "Avg. Session Duration", "Engagement Rate", "Pages / Sessions"],
                [
                    [
                        r.get("deviceCategory", ""),
                        fmt_count(r.get("totalUsers")),
                        _fmt_duration(r.get("averageSessionDuration")),
                        _fmt_pct(r.get("engagementRate")),
                        fmt_num(r.get("screenPageViewsPerSession")),
                    ]
                    for r in analytics.ga4_devices
                ],
                st,
                col_widths=[1.4 * inch, 0.9 * inch, 1.2 * inch, 1.1 * inch, 1.1 * inch],
            )
        )
        png = bar_chart(
            "Users by Device",
            [r.get("deviceCategory", "") for r in analytics.ga4_devices],
            [float(r.get("totalUsers", 0) or 0) for r in analytics.ga4_devices],
            ylabel="Users",
        )
        if png:
            story.append(subsection_spacer())
            story.append(chart_image(png))

    cwv_rows = _baseline_cwv_rows(by_name, panel, seo, page_url=final_url)
    if cwv_rows:
        story.append(section_spacer())
        story.append(Paragraph("Core Web Vitals (LCP, CLS, INP) &amp; Page load speed", st["section_title"]))
        usable = PAGE_SIZE[0] - 2 * MARGIN
        cwv_widths = [usable * 0.16, usable * 0.12, usable * 0.16, usable * 0.56]
        story.append(Paragraph("For Mobile", st["subsection"]))
        story.append(
            data_table(
                ["Metric", "Value", "Assessment", "Recommendation"],
                cwv_rows["mobile"],
                st,
                col_widths=cwv_widths,
                rating_col=2,
            )
        )
        if cwv_rows.get("desktop"):
            story.append(Spacer(1, 0.06 * inch))
            story.append(Paragraph("For Desktop", st["subsection"]))
            story.append(
                data_table(
                    ["Metric", "Value", "Assessment", "Recommendation"],
                    cwv_rows["desktop"],
                    st,
                    col_widths=cwv_widths,
                    rating_col=2,
                )
            )

    if analytics is not None:
        story.append(section_spacer())
        story.append(Paragraph("Total form submissions per month (breakdown by form type)", st["section_title"]))
        if analytics.ga4_forms:
            story.append(
                data_table(
                    ["Event", "Count"],
                    [[r.get("eventName", ""), fmt_count(r.get("eventCount"))] for r in analytics.ga4_forms],
                    st,
                    col_widths=[3.0 * inch, 1.2 * inch],
                )
            )
            png = bar_chart(
                "Form Submissions by Event",
                [r.get("eventName", "") for r in analytics.ga4_forms],
                [float(r.get("eventCount", 0) or 0) for r in analytics.ga4_forms],
                ylabel="Events",
            )
            if png:
                story.append(Spacer(1, 0.08 * inch))
                story.append(chart_image(png))
        else:
            story.append(
                Paragraph(
                    para(
                        "No form interaction events in GA4 for this period. "
                        "Enable Enhanced Measurement form interactions (form_start, form_submit) "
                        "or add custom form events."
                    ),
                    st["body"],
                )
            )

    if analytics and analytics.ga4_top_pages:
        story.append(section_spacer())
        story.append(Paragraph("Top exit pages", st["section_title"]))
        sorted_pages = sorted(
            analytics.ga4_top_pages,
            key=lambda r: float(r.get("sessions", 0) or 0),
            reverse=True,
        )[:15]
        story.append(
            data_table(
                ["Page path", "Sessions", "Bounce rate", "Views"],
                [
                    [
                        r.get("pagePath", ""),
                        fmt_count(r.get("sessions")),
                        _fmt_pct(r.get("bounceRate")),
                        fmt_count(r.get("screenPageViews")),
                    ]
                    for r in sorted_pages
                ],
                st,
                col_widths=[2.5 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch],
            )
        )


    return _render_baseline(story)


def _build_site_audit_full_pdf(
    rows: list[ResolvedRow],
    manual_rows: list[ResolvedRow],
    *,
    seo: Report,
    final_url: str,
) -> bytes:
    st = styles()
    domain = _host(final_url)
    generated = audit_generated_label()
    crawled = _crawled_pages(seo)
    story: list = []

    story.extend(audit_cover(st, "Full Site Audit Report", domain, generated))
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    by_name = {r.name: r for r in rows}
    errors = _audit_section_rows(rows, "Errors")
    warnings = _audit_section_rows(rows, "Warnings")
    notices = _audit_section_rows(rows, "Notices")
    err_count = sum(_issue_count(r) for r in errors)
    warn_count = sum(_issue_count(r) for r in warnings)
    notice_count = sum(_issue_count(r) for r in notices)
    health = max(0.0, min(100.0, seo.score))
    site_audit_actions = _site_audit_action_items(rows, seo, page_url=final_url)

    story.extend(
        executive_summary(
            st,
            domain=domain,
            report_label="Full Site Audit",
            score_badges=[("Site Health", health, seo.grade)],
            score_lines=_key_metric_issue_lines_from_counts(err_count, warn_count, notice_count),
            narrative=_short_executive_overview(
                score=health,
                grade=seo.grade,
                score_label="Site Health",
                action_items=site_audit_actions,
                focus="site audit",
            ),
            action_items=site_audit_actions,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Full Site Audit Report", st["audit_h1"]))
    story.append(Paragraph(f"Subdomain: {para(domain)}", st["audit_body"]))
    story.append(Paragraph(f"Last Update: {para(date.today().strftime('%B %d, %Y'))}", st["audit_body"]))
    story.append(Paragraph(f"Crawled Pages: {crawled}", st["audit_body"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Site Health", st["audit_h2"]))
    story.append(
        issue_counts_table(
            [
                ("Errors", err_count, "error"),
                ("Warnings", warn_count, "warning"),
                ("Notices", notice_count, "notice"),
            ],
            st,
            col_widths=[2.5 * inch, 1.0 * inch],
        )
    )
    story.append(subsection_spacer())
    story.append(
        data_table(
            ["Status", "Pages"],
            [
                ["Healthy", str(max(0, crawled - err_count - warn_count - notice_count))],
                ["Broken", "0"],
                ["Have issues", str(err_count + warn_count + notice_count)],
                ["Redirected", _redirected_pages(by_name)],
                ["Blocked", "0"],
            ],
            st,
            col_widths=[2.0 * inch, 1.0 * inch],
            center_cols={1},
        )
    )

    _append_site_audit_trend_charts(story, domain, st)

    link_buckets = _internal_link_distribution(seo)
    if link_buckets is not None:
        story.append(subsection_spacer())
        story.append(Paragraph("Internal Link Distribution", st["audit_h2"]))
        max_pages = max((int(b.get("pages", 0) or 0) for b in link_buckets), default=1)
        dist_rows = [
            (
                str(b["label"]),
                int(b["pages"]),
                f"{float(b['pct']):.2f}%",
            )
            for b in link_buckets
        ]
        story.append(distribution_table(dist_rows, st, max_pages=max_pages))
    elif crawled >= 2:
        story.append(subsection_spacer())
        story.append(Paragraph("Internal Link Distribution", st["audit_h2"]))
        story.append(
            Paragraph(
                para("Inlink distribution unavailable — re-run audit to rebuild the crawl graph."),
                st["audit_body"],
            )
        )

    if errors:
        story.append(section_spacer())
        story.append(Paragraph(f"ERRORS {err_count}", st["audit_h2_error"]))
        story.append(
            audit_issue_table(
                _audit_issue_lines(errors, seo=seo, page_url=final_url),
                st,
                severity="error",
            )
        )

    if warnings:
        story.append(section_spacer())
        story.append(Paragraph(f"WARNINGS {warn_count}", st["audit_h2_warning"]))
        story.append(
            audit_issue_table(
                _audit_issue_lines(warnings, seo=seo, page_url=final_url),
                st,
                severity="warning",
            )
        )

    if notices:
        story.append(section_spacer())
        story.append(Paragraph(f"NOTICES {notice_count}", st["audit_h2_notice"]))
        story.append(
            audit_issue_table(
                _audit_issue_lines(notices, seo=seo, page_url=final_url),
                st,
                severity="notice",
            )
        )


    return _render_audit(story, domain=domain, generated=generated)


def _build_ai_search_overview_pdf(
    by_name: dict[str, ResolvedRow],
    manual_rows: list[ResolvedRow],
    *,
    seo: Report,
    geo: Report,
    final_url: str,
) -> bytes:
    st = styles()
    domain = _host(final_url)
    generated = audit_generated_label()
    crawled = _crawled_pages(seo)
    story: list = []

    story.extend(audit_cover(st, "Site Audit: Overview", domain, generated))
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    ai_health = _ai_search_health_score(seo, geo)
    blocked_pct, blocked_n = _ai_blocked_stats(by_name, crawled)
    healthy, broken, redirected, have_issues = _crawl_status_breakdown(seo, by_name, crawled)
    ai_actions = _ai_overview_action_items(by_name, seo, geo, page_url=final_url)

    story.extend(
        executive_summary(
            st,
            domain=domain,
            report_label="AI Search Overview",
            score_badges=[("AI Search Health", ai_health, None)],
            score_lines=_key_metric_issue_lines(seo, geo),
            narrative=_short_executive_overview(
                score=ai_health,
                score_label="AI Search Health",
                action_items=ai_actions,
                focus="AI search readiness",
            ),
            action_items=ai_actions,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Site Audit: Overview", st["audit_h1"]))
    story.append(Paragraph("Pages Blocked from AI Search", st["audit_h2"]))
    story.append(Paragraph(f"Project name: {para(domain)}", st["audit_body"]))
    story.append(subsection_spacer())
    story.append(Paragraph("Crawled Pages", st["audit_h2"]))
    story.append(Paragraph(f"Project name: {para(domain)}", st["audit_body"]))
    story.append(
        data_table(
            ["Status", "Share", "Pages"],
            [
                ["Blocked", fmt_pct(blocked_pct), str(blocked_n)],
                ["Redirect", _redirect_share(by_name, crawled), str(redirected)],
                ["Have issues", fmt_pct((have_issues / crawled * 100) if crawled else 0), str(have_issues)],
                ["Broken", fmt_pct((broken / crawled * 100) if crawled else 0), str(broken)],
                ["Healthy", fmt_pct((healthy / crawled * 100) if crawled else 0), str(healthy)],
                ["Total", "100%", str(crawled)],
            ],
            st,
            col_widths=[1.6 * inch, 1.0 * inch, 1.0 * inch],
            center_cols={1, 2},
        )
    )

    bot_rows = _ai_bot_rows(by_name)
    if bot_rows:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("AI Bots Blocked Pages", st["audit_h2"]))
        story.append(
            data_table(
                ["AI Bot", "Blocked pages"],
                bot_rows,
                st,
                col_widths=[2.8 * inch, 1.2 * inch],
                center_cols={1},
            )
        )

    top_issues = _ai_top_issues(by_name, page_url=final_url)
    story.append(section_spacer())
    story.append(Paragraph("Top Issues", st["audit_h2"]))
    if top_issues:
        usable = PAGE_SIZE[0] - 2 * MARGIN
        table_data: list = []
        for issue, severity, pages, fix in top_issues:
            try:
                page_n = int(str(pages).strip() or "0")
            except ValueError:
                page_n = 0
            sev_key = severity.lower()
            if page_n <= 0:
                sev_hex = "#16A34A"
            elif sev_key in ("error", "not meeting"):
                sev_hex = "#DC2626"
            else:
                sev_hex = "#EA580C"
            fix_html = _format_developer_fix_html(str(fix)) if page_n > 0 else ""
            left_html = (
                f'<font color="{sev_hex}"><b>{para(issue)}</b></font>'
                f'<br/><font color="#767676">{para(severity)} · {para(str(pages))} pages</font>'
            )
            if fix_html:
                left_html += f'<br/><font color="#767676">{fix_html}</font>'
            table_data.append(
                [
                    Paragraph(left_html, st["issue_name"]),
                    Paragraph(para(str(pages)), st["issue_count"]),
                ]
            )
        table = Table(
            table_data,
            colWidths=[usable * 0.86, usable * 0.14],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, TABLE_RULE),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("All good — no issues found", st["audit_body"]))
        story.append(
            issue_counts_table(
                [("Errors", 0, "error"), ("Warnings", 0, "warning")],
                st,
                col_widths=[2.0 * inch, 1.0 * inch],
            )
        )

    return _render_audit(story, domain=domain, generated=generated)


def _render_baseline(story: list) -> bytes:
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=CONTENT_TOP_MARGIN,
        bottomMargin=CONTENT_BOTTOM_MARGIN,
        title="Performance Baseline",
    )
    frame = Frame(
        MARGIN,
        CONTENT_BOTTOM_MARGIN,
        PAGE_SIZE[0] - 2 * MARGIN,
        PAGE_SIZE[1] - CONTENT_TOP_MARGIN - CONTENT_BOTTOM_MARGIN,
        id="normal",
    )
    doc.addPageTemplates(
        [PageTemplate(id="baseline", frames=[frame], onPage=draw_baseline_page_number)]
    )
    doc.build(story)
    return buffer.getvalue()


def _render_audit(story: list, *, domain: str, generated: str) -> bytes:
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=CONTENT_TOP_MARGIN,
        bottomMargin=CONTENT_BOTTOM_MARGIN,
        title="SEO GEO Auditor",
    )
    frame = Frame(
        MARGIN,
        CONTENT_BOTTOM_MARGIN,
        PAGE_SIZE[0] - 2 * MARGIN,
        PAGE_SIZE[1] - CONTENT_TOP_MARGIN - CONTENT_BOTTOM_MARGIN,
        id="normal",
    )

    def _on_cover(canvas, _doc):
        pass

    def _on_content(canvas, _doc):
        if _doc.page > 1:
            draw_audit_page_decor(canvas, _doc, domain=domain, generated=generated)

    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[frame], onPage=_on_cover),
            PageTemplate(id="content", frames=[frame], onPage=_on_content),
        ]
    )
    doc.build(story)
    return buffer.getvalue()


def _index_parameters(seo: Report, geo: Report) -> dict[str, ParameterResult]:
    index: dict[str, ParameterResult] = {}
    for report in (seo, geo):
        for category in report.categories:
            for param in category.parameters:
                index[param.name] = param
    return index


def _resolve_baseline_rows(
    catalog: list[RefParameter],
    index: dict[str, ParameterResult],
    analytics: BaselineAnalytics | None,
    connected: bool,
) -> list[ResolvedRow]:
    """Resolve baseline catalog rows, preferring live GA4/GSC analytics when connected."""
    rows: list[ResolvedRow] = []
    for entry in catalog:
        row = _resolve_row(entry, index)
        if analytics is not None:
            detail = _baseline_analytics_detail(entry.name, analytics, index=index)
            if detail is not None:
                row = ResolvedRow(
                    name=entry.name,
                    section=entry.section,
                    rating="Meeting",
                    detail=detail,
                    source="GA4/GSC",
                    is_manual=False,
                    manual_reason="",
                    param=None,
                )
        elif connected and entry.name == "Organic Social traffic":
            row = ResolvedRow(
                name=entry.name,
                section=entry.section,
                rating="Manual",
                detail=entry.manual_reason,
                source="",
                is_manual=True,
                manual_reason=entry.manual_reason,
                param=None,
            )
        rows.append(row)
    return rows


def _engagement_rate_raw(
    analytics: BaselineAnalytics | None,
    index: dict[str, ParameterResult] | None = None,
) -> str | None:
    """Resolve engagementRate from GA4 overview, page report, or Pogo-sticking."""
    if analytics:
        ov = analytics.overview or {}
        val = ov.get("engagementRate")
        if val not in (None, ""):
            return str(val)
        pe = analytics.page_engagement or {}
        val = pe.get("engagementRate")
        if val not in (None, ""):
            return str(val)
    if index:
        param = index.get("Pogo-sticking risk")
        if param and param.rating not in (Rating.MANUAL, Rating.NOT_MEASURED):
            parsed = _detail_field(param.detail or "", "engagementRate") or _extract_percent(param.detail or "")
            if parsed:
                return parsed
    return None


def _baseline_analytics_detail(
    name: str,
    analytics: BaselineAnalytics,
    *,
    index: dict[str, ParameterResult] | None = None,
) -> str | None:
    """Return a detail string when live analytics satisfies a baseline metric."""
    ov = analytics.overview or {}
    pe = analytics.page_engagement or {}

    if name == "Engagement Rate":
        raw = _engagement_rate_raw(analytics, index)
        if raw is not None:
            return f"engagementRate={_fmt_pct(raw)}"
    if name == "Total Users" and ov.get("totalUsers") not in (None, ""):
        return f"totalUsers={_fmt_users(ov.get('totalUsers'))}"
    if name == "New Users" and ov.get("newUsers") not in (None, ""):
        return f"newUsers={_fmt_users(ov.get('newUsers'))}"
    if name == "Average Session Duration":
        duration = ov.get("averageSessionDuration") or pe.get("averageSessionDuration")
        if duration not in (None, ""):
            return f"averageSessionDuration={_fmt_duration(duration)}"
    if name == "Bounce Rate":
        bounce = ov.get("bounceRate") or pe.get("bounceRate")
        if bounce not in (None, ""):
            return f"bounceRate={_fmt_pct(bounce)}"
    if name == "Clicks by Device (Mobile/Desktop/Tablet)" and analytics.gsc_device:
        return f"devices={len(analytics.gsc_device)}"
    if name == "Clicks by Country" and analytics.gsc_country:
        return f"countries={len(analytics.gsc_country)}"
    if name == "Organic traffic trend (top pages traffic %)" and analytics.gsc_top_pages:
        return f"pages={len(analytics.gsc_top_pages)}"
    if name == "Traffic by source (organic/direct/referral)" and analytics.ga4_channels:
        return f"channels={len(analytics.ga4_channels)}"
    if name == "Session source breakdown (google/bing/yahoo/etc.)" and analytics.ga4_sources:
        return f"sources={len(analytics.ga4_sources)}"
    if name == "Organic Social traffic":
        total_sessions = sum(int(float(r.get("sessions", 0) or 0)) for r in analytics.ga4_social)
        return f"sessions={total_sessions} (Organic Social channel)"
    if name == "Session primary channel group" and analytics.ga4_channels:
        return f"channels={len(analytics.ga4_channels)}"
    if name == "Top ranking keywords (CTR, position, clicks, impressions)":
        if analytics.gsc_keywords:
            return f"keywords={len(analytics.gsc_keywords)}"
        if not analytics.gsc_keywords_ok and analytics.gsc_keywords_error:
            return _friendly_gsc_keyword_message(analytics.gsc_keywords_error)
        return "No query data in GSC for this period"
    if name == "Bounce rate & Average engagement time (charts)":
        bounce_days = len(analytics.ga4_bounce_trend)
        engagement_days = len(analytics.ga4_engagement_trend)
        if bounce_days or engagement_days:
            return f"bounce_days={bounce_days}; engagement_days={engagement_days}"
        return "No daily bounce or session duration data in GA4 for this period"
    if name == "Pages per session" and ov.get("screenPageViewsPerSession") not in (None, ""):
        return f"screenPageViewsPerSession={ov.get('screenPageViewsPerSession')}"
    if name == "Mobile vs Desktop traffic split" and analytics.ga4_devices:
        return f"devices={len(analytics.ga4_devices)}"
    if name in ("LCP (Core Web Vitals)", "CLS (Core Web Vitals)", "INP (Core Web Vitals)"):
        return None  # Resolved from audit PSI parameters
    if name == "Page load speed - Desktop" or name == "Page load speed - Mobile":
        return None
    if name == "Form submissions by type":
        if analytics.ga4_forms:
            return f"events={len(analytics.ga4_forms)}"
        return "No form events tracked in GA4 (enable form interactions or custom events)"
    if name == "Top exit pages" and analytics.ga4_top_pages:
        return f"pages={len(analytics.ga4_top_pages)}"
    return None


def _resolve_row(entry: RefParameter, index: dict[str, ParameterResult]) -> ResolvedRow:
    for key in entry.app_keys:
        param = index.get(key)
        if param is None:
            continue
        if param.rating in (Rating.MANUAL, Rating.NOT_MEASURED):
            continue
        detail = param.detail or param.recommendation or param.what_to_check
        if param.evidence:
            bits = [f"{k}={v}" for k, v in list(param.evidence.items())[:6]]
            if bits:
                detail = f"{detail} ({'; '.join(bits)})" if detail else "; ".join(bits)
        return ResolvedRow(
            name=entry.name,
            section=entry.section,
            rating=param.rating.value,
            detail=detail,
            source=key,
            is_manual=False,
            manual_reason="",
            param=param,
        )
    return ResolvedRow(
        name=entry.name,
        section=entry.section,
        rating="Manual",
        detail=entry.manual_reason,
        source="",
        is_manual=True,
        manual_reason=entry.manual_reason,
        param=None,
    )


def _host(final_url: str) -> str:
    return (
        final_url.replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
        .replace("www.", "")
        or "site"
    )


def _lighthouse_score(row: ResolvedRow) -> str:
    if row.param and row.param.evidence:
        perf = row.param.evidence.get("performance")
        if perf is not None:
            return fmt_score(perf)
    match = re.search(r"performance=(\d+(?:\.\d+)?)", row.detail or "")
    return fmt_score(match.group(1)) if match else ""


def _detail_field(detail: str, field: str) -> str:
    match = re.search(rf"{re.escape(field)}=([^;,]+)", detail or "", flags=re.I)
    return match.group(1).strip() if match else ""


def _extract_percent(text: str) -> str:
    match = re.search(r"([\d.]+%)", text or "")
    return match.group(1) if match else ""


def _baseline_overview_kpis(
    by_name: dict[str, ResolvedRow],
    panel: dict,
    analytics: BaselineAnalytics | None,
) -> list[tuple[str, str]]:
    kpis: list[tuple[str, str]] = []
    if analytics and analytics.overview:
        ov = analytics.overview
        engagement_raw = _engagement_rate_raw(analytics, None)
        if engagement_raw is None:
            for key in ("Engagement Rate", "Pogo-sticking risk"):
                row = by_name.get(key)
                if row and not row.is_manual:
                    engagement_raw = _detail_field(row.detail, "engagementRate") or _extract_percent(row.detail)
                    if engagement_raw:
                        break
        if engagement_raw is not None:
            kpis.append(("Engagement Rate", _fmt_pct(engagement_raw)))
        mapping = [
            ("Total Users", "totalUsers", _fmt_users),
            ("New Users", "newUsers", _fmt_users),
            ("Avg Session Duration", "averageSessionDuration", _fmt_duration),
            ("Bounce Rate", "bounceRate", _fmt_pct),
        ]
        for label, key, fmt in mapping:
            val = ov.get(key)
            if val in (None, "") and key == "averageSessionDuration":
                val = (analytics.page_engagement or {}).get("averageSessionDuration")
            if val not in (None, ""):
                kpis.append((label, fmt(val)))
    else:
        mapping = [
            ("Engagement Rate", "Engagement Rate"),
            ("Total Users", "Total Users"),
            ("New Users", "New Users"),
            ("Average Session Duration", "Average Session Duration"),
            ("Bounce Rate", "Bounce Rate"),
        ]
        for label, key in mapping:
            row = by_name.get(key)
            if not row or row.is_manual:
                continue
            if key == "Engagement Rate":
                val = _detail_field(row.detail, "engagementRate") or _extract_percent(row.detail)
                kpis.append((label, _fmt_pct(val) if val else "—"))
            elif key == "Average Session Duration":
                raw = _detail_field(row.detail, "averageSessionDuration") or row.detail[:20]
                kpis.append((label, _fmt_duration(raw) if raw else "—"))
            elif key == "Bounce Rate":
                val = _detail_field(row.detail, "bounceRate") or _extract_percent(row.detail)
                kpis.append((label, _fmt_pct(val) if val else "—"))
            else:
                raw = (row.detail or "—")[:24]
                kpis.append((label, fmt_count(raw) if raw not in ("—", "") else "—"))

    if panel.get("lcp_ms") is not None:
        kpis.append(("LCP (mobile)", f"{fmt_num(panel['lcp_ms'] / 1000)}s"))
    if panel.get("cls") is not None:
        kpis.append(("CLS (mobile)", fmt_num(panel["cls"])))
    if panel.get("inp_ms") is not None:
        kpis.append(("INP (mobile)", f"{fmt_num(panel['inp_ms'] / 1000)}s"))
    return kpis


def _trim_summary(text: str | None, *, limit: int = 900) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rsplit(" ", 1)[0] + "..."


def _short_executive_overview(
    *,
    score: float | None = None,
    grade: str | None = None,
    score_label: str = "Score",
    action_items: list[tuple[str, str, str]],
    focus: str = "SEO",
) -> str:
    """One short Overview paragraph: severity counts only — no named issue list."""
    high = sum(
        1
        for _, severity, _ in action_items
        if severity.lower() in ("not meeting", "error", "errors")
    )
    moderate = sum(
        1
        for _, severity, _ in action_items
        if severity.lower() in ("partial", "warning", "warnings")
    )
    lower = sum(
        1
        for _, severity, _ in action_items
        if severity.lower() in ("notice", "notices")
    )
    total = len(action_items)

    parts: list[str] = []
    if score is not None:
        grade_bit = f" (grade {grade})" if grade else ""
        parts.append(f"{score_label} is {float(score):.0f}%{grade_bit}.")

    if total == 0:
        parts.append(
            f"No critical {focus} issues were identified in this run. "
            "Continue monitoring the metrics in the sections below."
        )
        return " ".join(parts)

    buckets: list[str] = []
    if high:
        buckets.append(f"{high} high-priority")
    if moderate:
        buckets.append(f"{moderate} moderate")
    if lower:
        buckets.append(f"{lower} lower-priority")
    if not buckets:
        buckets.append(str(total))

    parts.append(
        f"This report highlights {total} priority area{'s' if total != 1 else ''} "
        f"({', '.join(buckets)}) that need attention. "
        "Specific findings and developer fixes are listed below."
    )
    return " ".join(parts)


def _resolved_fix(
    row: ResolvedRow,
    index: dict[str, ParameterResult] | None = None,
    *,
    page_url: str = "",
) -> str:
    param = row.param
    if param is None and index and row.source:
        param = index.get(row.source)
    if param is not None:
        text = developer_fix_text(param, page_url=page_url)
        if text:
            return text
        if param.recommendation:
            return param.recommendation
        if param.detail:
            return param.detail
    if row.detail and not row.is_manual:
        return row.detail
    return (
        f"Where: page/template for {page_url or 'the audited URL'}\n"
        "Change: Review the detailed findings in this report and apply the "
        "recommended SEO/GEO best practice."
    )


def _collect_report_action_items(
    *reports: Report,
    limit: int = 12,
    page_url: str = "",
) -> list[tuple[str, str, str]]:
    order = {"Not Meeting": 0, "Partial": 1}
    candidates: list[tuple[int, str, str, str]] = []
    for report in reports:
        for category in report.categories:
            for param in category.parameters:
                rating = param.rating.value
                if rating not in order:
                    continue
                fix = developer_fix_text(param, page_url=page_url) or param.recommendation or param.detail
                candidates.append((order[rating], param.name, rating, fix))
    candidates.sort(key=lambda item: item[0])
    return [(name, rating, fix) for _, name, rating, fix in candidates[:limit]]


def _key_metric_issue_lines_from_counts(errors: int, warnings: int, notices: int = 0) -> list[str]:
    """Executive Summary Key metric row: errors · warnings · notices."""
    return [f"{int(errors)} errors · {int(warnings)} warnings · {int(notices)} notices"]


def _key_metric_issue_lines(*reports: Report) -> list[str]:
    """Count Not Meeting / Partial parameters as errors / warnings for Key metric."""
    errors = 0
    warnings = 0
    for report in reports:
        for category in report.categories:
            for param in category.parameters:
                if param.rating == Rating.NOT_MEETING:
                    errors += 1
                elif param.rating == Rating.PARTIAL:
                    warnings += 1
    return _key_metric_issue_lines_from_counts(errors, warnings, 0)


def _baseline_action_items(
    by_name: dict[str, ResolvedRow],
    seo: Report,
    panel: dict,
    *,
    page_url: str = "",
) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    cwv_keys = (
        "LCP (Core Web Vitals)",
        "CLS (Core Web Vitals)",
        "INP (Core Web Vitals)",
        "Page load speed - Mobile",
        "Page load speed - Desktop",
    )
    for key in cwv_keys:
        row = by_name.get(key)
        if row and not row.is_manual and row.rating in ("Not Meeting", "Partial"):
            items.append((key, row.rating, _resolved_fix(row, page_url=page_url)))
    if len(items) < 8:
        for name, rating, fix in _collect_report_action_items(seo, limit=8, page_url=page_url):
            if (name, rating, fix) not in items and name not in {i[0] for i in items}:
                items.append((name, rating, fix))
            if len(items) >= 8:
                break
    return items[:8]


def _site_audit_action_items(
    rows: list[ResolvedRow],
    seo: Report,
    *,
    page_url: str = "",
) -> list[tuple[str, str, str]]:
    index: dict[str, ParameterResult] = {}
    for category in seo.categories:
        for param in category.parameters:
            index[param.name] = param
    items: list[tuple[str, str, str]] = []
    for section in ("Errors", "Warnings", "Notices"):
        for row in _audit_section_rows(rows, section):
            if row.rating not in ("Not Meeting", "Partial"):
                continue
            items.append((row.name, row.rating, _resolved_fix(row, index, page_url=page_url)))
            if len(items) >= 10:
                return items
    return items


def _is_internal_evidence_fix(text: str) -> bool:
    """Skip raw agent evidence strings that are not client-facing resolutions."""
    return bool(re.match(r"^score=\d+(?:\.\d+)?%; issues=\d+; crawled=\d+", (text or "").strip()))


def _ai_overview_action_items(
    by_name: dict[str, ResolvedRow],
    seo: Report,
    geo: Report,
    *,
    page_url: str = "",
) -> list[tuple[str, str, str]]:
    index = _index_parameters(seo, geo)
    items: list[tuple[str, str, str]] = []
    for row in by_name.values():
        if row.is_manual or row.name in _AI_OVERVIEW_ACTION_SKIP:
            continue
        if row.rating != "Not Meeting":
            continue
        fix = _resolved_fix(row, index, page_url=page_url)
        if _is_internal_evidence_fix(fix):
            continue
        items.append((row.name, row.rating, fix))
        if len(items) >= 8:
            return items
    if len(items) < 5:
        for name, rating, fix in _collect_report_action_items(seo, geo, limit=8, page_url=page_url):
            if name in _AI_OVERVIEW_ACTION_SKIP or name in {i[0] for i in items}:
                continue
            if _is_internal_evidence_fix(fix):
                continue
            items.append((name, rating, fix))
            if len(items) >= 8:
                break
    return items[:8]


def _filter_manual_with_analytics(
    manual_rows: list[ResolvedRow],
    analytics: BaselineAnalytics,
) -> list[ResolvedRow]:
    """Drop manual rows that live analytics data now satisfies."""

    def _has(name: str) -> bool:
        checks = {
            "Engagement Rate": lambda: analytics.overview.get("engagementRate")
            or analytics.page_engagement.get("engagementRate"),
            "Total Users": lambda: analytics.overview.get("totalUsers"),
            "New Users": lambda: analytics.overview.get("newUsers"),
            "Average Session Duration": lambda: analytics.overview.get("averageSessionDuration")
            or analytics.page_engagement.get("averageSessionDuration"),
            "Bounce Rate": lambda: analytics.overview.get("bounceRate")
            or analytics.page_engagement.get("bounceRate"),
            "Clicks by Device (Mobile/Desktop/Tablet)": lambda: analytics.gsc_device,
            "Clicks by Country": lambda: analytics.gsc_country,
            "Organic traffic trend (top pages traffic %)": lambda: analytics.gsc_top_pages,
            "Traffic by source (organic/direct/referral)": lambda: analytics.ga4_channels,
            "Session source breakdown (google/bing/yahoo/etc.)": lambda: analytics.ga4_sources,
            "Organic Social traffic": lambda: analytics.ga4_social,
            "Session primary channel group": lambda: analytics.ga4_channels,
            "Top ranking keywords (CTR, position, clicks, impressions)": lambda: analytics.gsc_keywords,
            "Bounce rate & Average engagement time (charts)": lambda: analytics.ga4_bounce_trend
            or analytics.ga4_engagement_trend,
            "Pages per session": lambda: analytics.overview.get("screenPageViewsPerSession"),
            "Mobile vs Desktop traffic split": lambda: analytics.ga4_devices,
            "Form submissions by type": lambda: analytics.ga4_forms,
            "Top exit pages": lambda: analytics.ga4_top_pages,
        }
        check = checks.get(name)
        return bool(check and check())

    return [row for row in manual_rows if not _has(row.name)]


def _fmt_pct(value) -> str:
    return fmt_pct(value)


def _fmt_users(value) -> str:
    return fmt_users(value)


def _fmt_duration(value) -> str:
    return fmt_duration(value)


def _fmt_chart_date(raw: str) -> str:
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[4:6]}/{raw[6:8]}"
    return raw


def _cwv_recommendation(row: ResolvedRow, *, page_url: str = "") -> str:
    """Concise improvement guidance for Partial/Not Meeting CWV rows; else em dash."""
    if row.rating not in ("Not Meeting", "Partial"):
        return "—"
    fix = _resolved_fix(row, page_url=page_url)
    if not fix:
        return "—"
    for line in fix.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("change:"):
            return stripped[len("Change:") :].strip() or fix
    return fix


def _baseline_cwv_rows(
    by_name: dict[str, ResolvedRow],
    panel: dict,
    seo: Report,
    *,
    page_url: str = "",
) -> dict[str, list[list[str]]]:
    del seo  # reserved for call-site compatibility / future panel fallbacks
    mobile: list[list[str]] = []
    desktop: list[list[str]] = []

    metric_map = [
        ("LCP (Core Web Vitals)", "LCP", "lcp_ms", True),
        ("CLS (Core Web Vitals)", "CLS", "cls", False),
        ("INP (Core Web Vitals)", "INP", "inp_ms", True),
    ]
    for label, key, panel_key, is_ms in metric_map:
        row = by_name.get(label)
        if row and not row.is_manual:
            raw = panel.get(panel_key)
            if raw is not None:
                if is_ms and isinstance(raw, (int, float)):
                    value = f"{fmt_num(raw / 1000)}s"
                else:
                    value = fmt_num(raw)
                mobile.append([key, value, row.rating, _cwv_recommendation(row, page_url=page_url)])

    load_mobile = by_name.get("Page load speed - Mobile")
    load_desktop = by_name.get("Page load speed - Desktop")
    if load_mobile and not load_mobile.is_manual:
        score = _lighthouse_score(load_mobile)
        mobile.append(
            [
                "Lighthouse performance",
                score or "—",
                load_mobile.rating,
                _cwv_recommendation(load_mobile, page_url=page_url),
            ]
        )
    if load_desktop and not load_desktop.is_manual:
        score = _lighthouse_score(load_desktop)
        desktop.append(
            [
                "Lighthouse performance",
                score or "—",
                load_desktop.rating,
                _cwv_recommendation(load_desktop, page_url=page_url),
            ]
        )

    delta = by_name.get("Mobile vs Desktop traffic split")
    if delta and not delta.is_manual:
        d_perf = _detail_field(delta.detail, "desktop perf")
        if d_perf and not desktop:
            desktop.append(
                [
                    "Lighthouse performance",
                    d_perf,
                    delta.rating,
                    _cwv_recommendation(delta, page_url=page_url),
                ]
            )

    if not mobile and not desktop:
        return {}
    return {"mobile": mobile, "desktop": desktop}


def _ai_search_health_score(seo: Report, geo: Report) -> float:
    """Return the five-pillar AI Search Health score (0-100)."""
    panel = geo.panel or {}
    stored = panel.get("ai_search_health", {}).get("score")
    if stored is not None:
        return max(0.0, min(100.0, float(stored)))
    score, _ = compute_ai_search_health(seo, geo)
    return max(0.0, min(100.0, score))


def _audit_section_rows(rows: list[ResolvedRow], section: str) -> list[ResolvedRow]:
    return [r for r in rows if r.section == section and not r.is_manual]


def _issue_count(row: ResolvedRow) -> int:
    if row.rating in ("Not Meeting", "Partial"):
        if row.param and row.param.evidence.get("count") is not None:
            try:
                return max(1, int(row.param.evidence["count"]))
            except (TypeError, ValueError):
                pass
        match = re.search(r"single_inlink_pages=(\d+)", row.detail or "")
        if match:
            return max(1, int(match.group(1)))
        return 1
    return 0


def _audit_issue_lines(
    rows: list[ResolvedRow],
    *,
    seo: Report | None = None,
    page_url: str = "",
) -> list[tuple[str, str, str, str]]:
    index: dict[str, ParameterResult] = {}
    if seo is not None:
        for category in seo.categories:
            for param in category.parameters:
                index[param.name] = param
    lines: list[tuple[str, str, str, str]] = []
    for row in rows:
        count = _issue_count(row)
        label = _audit_issue_label(row.name, count)
        fix = _resolved_fix(row, index, page_url=page_url) if count else ""
        lines.append((label, str(count), "0", fix))
    return lines


def _audit_issue_label(name: str, count: int) -> str:
    special = {
        "Robots.txt file has format errors",
        "Sitemap.xml not indicated in robots.txt",
        "Sitemap.xml not found",
        "Homepage does not use HTTPS encryption",
        "No redirect or canonical to HTTPS homepage from HTTP",
        "Llms.txt not found",
        "Llms.txt has formatting issues",
        "Robots.txt not found",
        "This page has no viewport tag",
        "AMP pages have no canonical tag",
    }
    if name in special:
        return name if count == 0 else f"{count} {name[0].lower()}{name[1:]}"
    words = name.split(" ", 1)
    if len(words) == 2 and words[0] in {"URLs", "HTTP", "AMP"}:
        prefix, rest = words
        return f"{count} {prefix} {rest[0].lower()}{rest[1:]}" if count else f"0 {prefix} {rest}"
    lowered = name[0].lower() + name[1:] if name else name
    return f"{count} {lowered}"


def _crawled_pages(seo: Report) -> int:
    for category in seo.categories:
        for param in category.parameters:
            if param.name == "Site Health score" and param.evidence.get("crawled"):
                return max(1, int(param.evidence["crawled"]))
            if param.name == "Internal link distribution" and param.evidence.get("total_pages"):
                return max(1, int(param.evidence["total_pages"]))
            if param.name == "Crawl depth":
                match = re.search(r"across (\d+) pages", param.detail or "")
                if match:
                    return max(1, int(match.group(1)))
    return 1


def _internal_link_distribution(seo: Report) -> list[dict] | None:
    for category in seo.categories:
        for param in category.parameters:
            if param.name == "Internal link distribution":
                buckets = param.evidence.get("buckets")
                if isinstance(buckets, list) and buckets:
                    return buckets
    return None


def _trend_chart_label(audited_at: datetime) -> str:
    """Format chart x-axis like Semrush overview: '13 Jun'."""
    return audited_at.strftime("%d %b").lstrip("0")


def _friendly_gsc_keyword_message(error: str) -> str:
    """Short client-facing copy instead of raw Google API exception text."""
    lower = (error or "").lower()
    if "sufficient permission" in lower or "forbidden" in lower or "403" in lower:
        return (
            "Keyword data unavailable: the connected Google account does not have access "
            "to this Search Console property. Grant access in GSC (or reconnect OAuth with "
            "the correct property) and re-run the audit."
        )
    if "not found" in lower or "404" in lower:
        return (
            "Keyword data unavailable: this site was not found in Google Search Console "
            "for the connected account. Verify the property URL matches GSC exactly."
        )
    return (
        "Keyword data unavailable from Google Search Console for this property right now. "
        "Confirm GSC access and try again."
    )


def _append_site_audit_trend_charts(story: list, domain: str, st: dict) -> None:
    """Render Semrush-style trend mini charts from SQLite audit history."""
    settings = get_settings()
    history = AuditHistoryStore().history(domain, limit=settings.audit_history_points)
    if len(history) < 2:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Site audit trends", st["audit_h2"]))
        story.append(
            Paragraph(
                para(
                    "Trend charts appear after at least two audit runs with different site health or "
                    "issue counts for this domain. Each SEO GEO Auditor run checks automatically."
                ),
                st["audit_body"],
            )
        )
        return

    labels = [_trend_chart_label(s.audited_at) for s in history]
    specs = [
        ("Site Health", [s.site_health for s in history], "%"),
        ("Errors", [float(s.errors) for s in history], "Count"),
        ("Warnings", [float(s.warnings) for s in history], "Count"),
        ("Notices", [float(s.notices) for s in history], "Count"),
    ]
    usable = PAGE_SIZE[0] - 2 * MARGIN
    col_w = (usable - 6) / 2
    images: list = []
    for title, values, ylabel in specs:
        png = mini_line_chart(title, labels, values, ylabel=ylabel)
        if png:
            images.append(chart_image(png, width=col_w))

    if not images:
        return

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Site audit trends", st["audit_h2"]))
    while len(images) < 4:
        images.append(Spacer(1, 0.01 * inch))
    grid = Table(
        [[images[0], images[1]], [images[2], images[3]]],
        colWidths=[col_w + 3, col_w + 3],
        hAlign="LEFT",
    )
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(grid)

    crawled_png = mini_line_chart(
        "Crawled Pages",
        labels,
        [float(s.crawled_pages) for s in history],
        ylabel="Pages",
    )
    if crawled_png:
        story.append(Spacer(1, 0.08 * inch))
        # Full-width but aspect-preserving (no horizontal stretch)
        story.append(chart_image(crawled_png, width=usable * 0.72))


def _site_health_score(seo: Report, by_name: dict[str, ResolvedRow]) -> float:
    for key in ("Site Health score (percentage)", "Site Health score"):
        row = by_name.get(key)
        if row and not row.is_manual:
            match = re.search(r"score=([\d.]+)%", row.detail or "")
            if match:
                return float(match.group(1))
    return max(0.0, min(100.0, seo.score))


def _crawl_status_breakdown(
    seo: Report,
    by_name: dict[str, ResolvedRow],
    crawled: int,
) -> tuple[int, int, int, int]:
    """Return healthy, broken, redirected, have_issues page counts."""
    inv = by_name.get("Crawled pages stats (Blocked/Redirect/Broken/Healthy)")
    if inv and not inv.is_manual and inv.param and inv.param.evidence:
        ev = inv.param.evidence
        return (
            int(ev.get("healthy", 0) or 0),
            int(ev.get("broken", 0) or 0),
            int(ev.get("redirected", 0) or 0),
            int(ev.get("have_issues", 0) or 0),
        )
    agg = by_name.get("Crawl status inventory")
    if agg and not agg.is_manual and agg.param and agg.param.evidence:
        ev = agg.param.evidence
        return (
            int(ev.get("healthy", 0) or 0),
            int(ev.get("broken", 0) or 0),
            int(ev.get("redirected", 0) or 0),
            int(ev.get("have_issues", 0) or 0),
        )
    broken = 0
    redirected = int(_redirected_pages(by_name))
    have_issues = 0
    for category in seo.categories:
        if category.key != "site_audit_supplement":
            continue
        for param in category.parameters:
            if param.name in ("Site Health score",):
                continue
            if param.rating in (Rating.NOT_MEETING, Rating.PARTIAL):
                have_issues += 1
    healthy = max(0, crawled - broken - redirected - min(have_issues, crawled))
    return healthy, broken, redirected, min(have_issues, crawled)


def _redirected_pages(by_name: dict[str, ResolvedRow]) -> str:
    for key in ("URLs with a temporary redirect", "URLs with a permanent redirect"):
        row = by_name.get(key)
        if row and not row.is_manual and row.rating != "Meeting":
            return "1"
    return "0"


def _redirect_share(by_name: dict[str, ResolvedRow], crawled: int) -> str:
    redirected = int(_redirected_pages(by_name))
    if crawled <= 0:
        return "0%"
    return fmt_pct((redirected / crawled * 100) if crawled else 0)


def _ai_blocked_stats(by_name: dict[str, ResolvedRow], crawled: int) -> tuple[float, int]:
    row = by_name.get("Pages blocked from AI search (aggregate %)")
    if row and not row.is_manual and row.param and row.param.evidence:
        blocked = int(row.param.evidence.get("blocked", 0) or 0)
        pct = float(row.param.evidence.get("pct", 0) or 0)
        if blocked or pct:
            return pct, blocked
    agg = by_name.get("AI blocked pages aggregate")
    if agg and not agg.is_manual and agg.param and agg.param.evidence:
        blocked = int(agg.param.evidence.get("blocked", 0) or 0)
        pct = float(agg.param.evidence.get("pct", 0) or 0)
        return pct, blocked
    if row and not row.is_manual and row.rating == "Not Meeting":
        return 100.0, crawled
    blocked = 0
    grouped = by_name.get("GPTBot / ClaudeBot / PerplexityBot")
    if grouped and not grouped.is_manual and grouped.rating != "Meeting":
        blocked = crawled
    pct = (blocked / crawled * 100) if crawled else 0.0
    return pct, blocked


def _ai_bot_rows(by_name: dict[str, ResolvedRow]) -> list[list[str]]:
    out: list[list[str]] = []
    for param_name in (
        "Google-Extended bot blocking",
        "GPTBot bot blocking",
        "ChatGPT-User bot blocking",
        "OAI-SearchBot bot blocking",
        "Googlebot blocking",
        "PerplexityBot bot blocking",
        "Perplexity-User bot blocking",
        "ClaudeBot bot blocking",
        "Claude-User bot blocking",
        "Claude-SearchBot bot blocking",
    ):
        row = by_name.get(param_name)
        if not row or row.is_manual:
            continue
        blocked = row.rating == "Not Meeting"
        label = param_name.replace(" bot blocking", "").replace(" blocking", "")
        out.append([label, "1" if blocked else "0"])
    return out


def _ai_top_issues(
    by_name: dict[str, ResolvedRow],
    *,
    page_url: str = "",
) -> list[tuple[str, str, str, str]]:
    issues: list[tuple[str, str, str, str]] = []
    for row in by_name.values():
        if row.is_manual:
            continue
        if row.rating == "Not Meeting":
            fix = _resolved_fix(row, page_url=page_url)
            issues.append(
                (
                    row.name,
                    row.section if row.section != "AI Search" else "Error",
                    "1",
                    fix,
                )
            )
    return issues[:10]
