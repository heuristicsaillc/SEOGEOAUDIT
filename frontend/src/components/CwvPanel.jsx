// Core Web Vitals panel shown on the SEO report (populated from PSI).
import React from "react"; // React core

// Render a single metric tile with a value + unit
function Metric({ label, value, unit }) {
  return (
    <div className="cwv-metric">
      <div className="cwv-value">
        {value === null || value === undefined ? "—" : Math.round(value)}
        <span className="cwv-unit">{unit}</span>
      </div>
      <div className="cwv-label">{label}</div>
    </div>
  );
}

export default function CwvPanel({ panel }) {
  // Hide the panel entirely when PSI produced no data
  if (!panel || Object.keys(panel).length === 0) return null;

  return (
    <div className="cwv-panel">
      <h3>Core Web Vitals (PageSpeed Insights · mobile)</h3>
      <div className="cwv-grid">
        <Metric label="LCP" value={panel.lcp_ms} unit="ms" />
        <Metric label="CLS" value={panel.cls} unit="" />
        <Metric label="INP" value={panel.inp_ms} unit="ms" />
        <Metric label="TTFB" value={panel.ttfb_ms} unit="ms" />
      </div>
      {/* Lighthouse category scores when available */}
      {panel.lighthouse && (
        <div className="lighthouse">
          {Object.entries(panel.lighthouse).map(([cat, score]) => (
            <span key={cat} className="lh-badge">
              {cat}: {score === null ? "—" : score}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
