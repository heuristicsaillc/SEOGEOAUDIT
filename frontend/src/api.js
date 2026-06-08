// Thin API client wrapping the backend's /api/audit endpoint.

// POST a URL to the auditor and return the parsed AuditResponse JSON.
export async function runAudit(url) {
  // Issue the audit request to the backend (proxied to :8000 in dev)
  const response = await fetch("/api/audit", {
    method: "POST", // The audit endpoint is a POST
    headers: { "Content-Type": "application/json" }, // JSON body
    body: JSON.stringify({ url }), // The URL to audit
  });

  // Non-2xx responses carry a FastAPI {detail} error message
  if (!response.ok) {
    let message = `Request failed (${response.status})`; // Default message
    try {
      const data = await response.json(); // Try to read the error detail
      if (data && data.detail) message = data.detail; // Use the server message
    } catch {
      // Ignore JSON parse errors and keep the default message
    }
    throw new Error(message); // Surface the error to the caller
  }

  return response.json(); // Parsed AuditResponse
}

// POST one report to /api/report/pdf and trigger a browser download.
export async function downloadReportPdf({ final_url, duration_seconds, connected, report }) {
  const response = await fetch("/api/report/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ final_url, duration_seconds, connected, report }),
  });

  if (!response.ok) {
    let message = `PDF download failed (${response.status})`;
    try {
      const data = await response.json();
      if (data && data.detail) message = data.detail;
    } catch {
      // Keep the default message
    }
    if (response.status === 405) {
      message =
        "PDF download failed (405 Method Not Allowed). Restart the backend server so it loads the latest code, then try again.";
    }
    throw new Error(message);
  }

  const blob = await response.blob(); // PDF bytes from the server
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${report.kind}-audit.pdf`;

  const url = URL.createObjectURL(blob); // Temporary object URL for the download
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
