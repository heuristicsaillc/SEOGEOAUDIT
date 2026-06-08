// AI-citation appearance panel shown on the GEO report.
import React from "react"; // React core

export default function CitationPanel({ panel }) {
  // Hide when no citation data was produced
  if (!panel || Object.keys(panel).length === 0) return null;

  // Engines that currently cite the audited domain
  const citedBy = panel.cited_by || [];

  return (
    <div className="citation-panel">
      <h3>AI Citation Appearance</h3>
      <p className="citation-query">
        Query tested: <em>{panel.query}</em>
      </p>

      {/* Which engines cite the site */}
      <div className="cited-by">
        {citedBy.length > 0 ? (
          citedBy.map((engine) => (
            <span key={engine} className="engine-badge hit">
              {engine}
            </span>
          ))
        ) : (
          <span className="engine-badge miss">Not currently cited by tested engines</span>
        )}
      </div>

      {/* Competitor / source lists for context */}
      {panel.perplexity_sources && panel.perplexity_sources.length > 0 && (
        <div className="source-list">
          <h4>Perplexity sources</h4>
          <ul>
            {panel.perplexity_sources.map((src, i) => (
              <li key={i}>{src}</li>
            ))}
          </ul>
        </div>
      )}
      {panel.ai_overview_sources && panel.ai_overview_sources.length > 0 && (
        <div className="source-list">
          <h4>Google AI Overview sources</h4>
          <ul>
            {panel.ai_overview_sources.map((src, i) => (
              <li key={i}>{src}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
