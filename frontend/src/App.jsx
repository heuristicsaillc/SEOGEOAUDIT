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
  // The most recent error message, if any
  const [error, setError] = useState("");

  // Run an audit for the submitted URL and store the result/error
  async function handleAudit(url) {
    setLoading(true); // Enter the loading state
    setError(""); // Clear any previous error
    setResult(null); // Clear the previous result
    try {
      const data = await runAudit(url); // Call the backend
      setResult(data); // Store the two reports
    } catch (err) {
      setError(err.message || "Audit failed."); // Surface the error
    } finally {
      setLoading(false); // Leave the loading state
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
          <p>Crawling, rendering and running 15 analysis agents…</p>
        </div>
      )}

      {/* Results: two report tabs */}
      {result && !loading && <ReportTabs result={result} />}
    </div>
  );
}
