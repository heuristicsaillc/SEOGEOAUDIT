// Switches between the SEO and GEO reports as two tabs, with PDF download actions.
import React, { useState } from "react"; // React + tab state
import { downloadReportPdf, downloadSupplementaryPdf } from "../api.js"; // PDF export API
import ReportView from "./ReportView.jsx"; // Renders a single report

const SUPPLEMENTARY_REPORTS = [
  {
    kind: "performance_baseline",
    label: "Performance Baseline (Traffic & Web Vitals)",
  },
  { kind: "site_audit_full", label: "Heuristics AI Full Site Audit" },
  { kind: "ai_search_overview", label: "Heuristics AI Search Overview" },
];

export default function ReportTabs({ result }) {
  // Which tab is active: "seo" or "geo"
  const [active, setActive] = useState("seo");
  // Which PDF is currently being generated (null | kind string)
  const [downloading, setDownloading] = useState(null);
  // Whether the supplementary-reports menu is open
  const [moreOpen, setMoreOpen] = useState(false);
  // Last PDF download error message
  const [downloadError, setDownloadError] = useState("");

  // The currently selected report object
  const report = active === "seo" ? result.seo : result.geo;

  const basePayload = {
    final_url: result.final_url,
    duration_seconds: result.duration_seconds,
    connected: result.connected,
  };

  async function downloadKind(kind) {
    if (kind === "seo" || kind === "geo") {
      await downloadReportPdf({
        ...basePayload,
        report: kind === "seo" ? result.seo : result.geo,
      });
      return;
    }
    await downloadSupplementaryPdf({
      ...basePayload,
      seo: result.seo,
      geo: result.geo,
      kind,
    });
  }

  // Request a PDF for the given report kind and save it via the browser
  async function handleDownload(kind) {
    setDownloading(kind);
    setDownloadError("");
    setMoreOpen(false);
    try {
      await downloadKind(kind);
    } catch (err) {
      setDownloadError(err.message || "PDF download failed.");
    } finally {
      setDownloading(null);
    }
  }

  async function handleDownloadAll() {
    setDownloading("all");
    setDownloadError("");
    setMoreOpen(false);
    try {
      const kinds = ["seo", "geo", ...SUPPLEMENTARY_REPORTS.map((r) => r.kind)];
      for (const kind of kinds) {
        await downloadKind(kind);
      }
    } catch (err) {
      setDownloadError(err.message || "PDF download failed.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="report-tabs">
      {/* Run metadata bar */}
      <div className="meta-bar">
        <span>
          Audited: <strong>{result.final_url}</strong>
        </span>
        <span>{result.connected ? "Connected property (GA4/GSC)" : "Public crawl"}</span>
        <span>{result.duration_seconds}s</span>
      </div>

      {/* PDF download actions — available once results are on screen */}
      <div className="download-bar">
        <span className="download-label">Download reports:</span>
        <button
          type="button"
          className="download-button"
          disabled={downloading !== null}
          onClick={() => handleDownload("seo")}
        >
          {downloading === "seo" ? "Generating SEO PDF…" : "Download SEO PDF"}
        </button>
        <button
          type="button"
          className="download-button"
          disabled={downloading !== null}
          onClick={() => handleDownload("geo")}
        >
          {downloading === "geo" ? "Generating GEO PDF…" : "Download GEO PDF"}
        </button>
        <div className="download-more">
          <button
            type="button"
            className="download-button download-more-toggle"
            disabled={downloading !== null}
            onClick={() => setMoreOpen((open) => !open)}
            aria-expanded={moreOpen}
            aria-haspopup="menu"
          >
            {downloading === "all"
              ? "Generating all PDFs…"
              : "More reports ▾"}
          </button>
          {moreOpen && (
            <div className="download-more-menu" role="menu">
              {SUPPLEMENTARY_REPORTS.map((item) => (
                <button
                  key={item.kind}
                  type="button"
                  className="download-more-item"
                  role="menuitem"
                  disabled={downloading !== null}
                  onClick={() => handleDownload(item.kind)}
                >
                  {downloading === item.kind ? "Generating…" : item.label}
                </button>
              ))}
              <button
                type="button"
                className="download-more-item download-more-all"
                role="menuitem"
                disabled={downloading !== null}
                onClick={handleDownloadAll}
              >
                Download all 5 PDFs
              </button>
            </div>
          )}
        </div>
      </div>
      {downloadError && <div className="error-banner">{downloadError}</div>}

      {/* Tab buttons with the score baked into each label */}
      <div className="tab-buttons">
        <button
          className={active === "seo" ? "tab active" : "tab"}
          onClick={() => setActive("seo")}
        >
          SEO Report · {result.seo.score} ({result.seo.grade})
        </button>
        <button
          className={active === "geo" ? "tab active" : "tab"}
          onClick={() => setActive("geo")}
        >
          GEO Report · {result.geo.score} ({result.geo.grade})
        </button>
      </div>

      {/* The active report */}
      <ReportView report={report} />
    </div>
  );
}
