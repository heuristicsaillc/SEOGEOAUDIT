// Top-level application: URL form, run state, and the two report tabs.
import React, { useState } from "react"; // React + local state hook
import { runAudit } from "./api.js"; // API client
import UrlForm from "./components/UrlForm.jsx"; // URL input form
import ReportTabs from "./components/ReportTabs.jsx"; // SEO/GEO tab switcher + content

export default function App() {
  // The audit result (null until the first successful run)
  const [result, setResult] = useState(null);
  // Whether an audit is currently running (drives the progress UI)
  const [loading, setLoading] = useState(false);
  // Live status message while the report is generated
  const [status, setStatus] = useState("");
  // The most recent error message, if any
  const [error, setError] = useState("");

  // Run an audit for the submitted URL and store the result/error
  async function handleAudit(url) {
    setLoading(true);
    setError("");
    setResult(null);
    setStatus("Starting…");
    try {
      const data = await runAudit(url, setStatus);
      setResult(data);
    } catch (err) {
      setError(err.message || "Audit failed.");
    } finally {
      setLoading(false);
      setStatus("");
    }
  }

  return (
    <div className="app">
      {/* Header / branding */}
      <header className="app-header">
        <h1>SEO &amp; GEO Auditor</h1>
        <p className="tagline">
          Audit any URL for Search Engine &amp; Generative Engine Optimisation.
        </p>
      </header>

      {/* URL input form */}
      <UrlForm onSubmit={handleAudit} loading={loading} />

      {/* Error banner */}
      {error && <div className="error-banner">{error}</div>}

      {/* Loading / progress indicator */}
      {loading && (
        <div className="loading">
          <div className="spinner" aria-hidden="true" />
          <div className="loading-text">
            <p className="loading-title">Generating report…</p>
            {status && <p className="loading-status">{status}</p>}
          </div>
        </div>
      )}

      {/* Results: two report tabs */}
      {result && !loading && <ReportTabs result={result} />}
    </div>
  );
}
