// Switches between the SEO and GEO reports as two tabs, with PDF download actions.
import React, { useState } from "react"; // React + tab state
import { downloadReportPdf } from "../api.js"; // PDF export API
import ReportView from "./ReportView.jsx"; // Renders a single report

export default function ReportTabs({ result }) {
  // Which tab is active: "seo" or "geo"
  const [active, setActive] = useState("seo");
  // Which PDF is currently being generated (null | "seo" | "geo")
  const [downloading, setDownloading] = useState(null);
  // Last PDF download error message
  const [downloadError, setDownloadError] = useState("");

  // The currently selected report object
  const report = active === "seo" ? result.seo : result.geo;

  // Request a PDF for the given report kind and save it via the browser
  async function handleDownload(kind) {
    setDownloading(kind); // Show loading on the clicked button
    setDownloadError(""); // Clear any previous error
    try {
      const payload = {
        final_url: result.final_url,
        duration_seconds: result.duration_seconds,
        connected: result.connected,
        report: kind === "seo" ? result.seo : result.geo,
      };
      await downloadReportPdf(payload); // Triggers the file download
    } catch (err) {
      setDownloadError(err.message || "PDF download failed."); // Surface the error
    } finally {
      setDownloading(null); // Re-enable buttons
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
