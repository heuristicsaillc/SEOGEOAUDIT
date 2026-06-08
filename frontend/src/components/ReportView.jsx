// Renders a complete report: score header, narrative, panel, and category tables.
import React from "react"; // React core
import ScoreHeader from "./ScoreHeader.jsx"; // Score + grade badge
import CategoryTable from "./CategoryTable.jsx"; // One table per category
import CwvPanel from "./CwvPanel.jsx"; // SEO-only Core Web Vitals panel
import CitationPanel from "./CitationPanel.jsx"; // GEO-only AI-citation panel

export default function ReportView({ report }) {
  return (
    <div className="report-view">
      {/* Final score + grade */}
      <ScoreHeader report={report} />

      {/* Gemini-generated prioritized narrative summary */}
      {report.summary && (
        <div className="summary">
          <h3>Summary &amp; Top Fixes</h3>
          {/* Preserve newlines from the narrative */}
          <p style={{ whiteSpace: "pre-wrap" }}>{report.summary}</p>
        </div>
      )}

      {/* Report-specific panel: CWV for SEO, citations for GEO */}
      {report.kind === "seo" ? (
        <CwvPanel panel={report.panel} />
      ) : (
        <CitationPanel panel={report.panel} />
      )}

      {/* Every category as a table */}
      {report.categories.map((category) => (
        <CategoryTable key={category.key} category={category} />
      ))}
    </div>
  );
}
