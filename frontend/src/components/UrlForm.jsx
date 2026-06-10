// URL input form with a submit button that is disabled while loading.
import React, { useState } from "react"; // React + local state

export default function UrlForm({ onSubmit, loading }) {
  // Controlled input value for the URL field
  const [url, setUrl] = useState("");

  // Handle form submission: prevent reload and bubble the URL up
  function handleSubmit(event) {
    event.preventDefault(); // Stop the browser from navigating
    const trimmed = url.trim(); // Normalise whitespace
    if (trimmed) onSubmit(trimmed); // Only run with a non-empty URL
  }

  return (
    <form className="url-form" onSubmit={handleSubmit}>
      <input
        type="text" // Free text so users can omit the scheme
        className="url-input"
        placeholder="www.example.com or https://example.com"
        value={url} // Controlled value
        onChange={(e) => setUrl(e.target.value)} // Update state on typing
        disabled={loading} // Lock input while a run is in flight
        aria-label="Website URL to audit"
      />
      <button type="submit" className="run-button" disabled={loading || !url.trim()}>
        {loading ? "Auditing…" : "Run Audit"}
      </button>
    </form>
  );
}
