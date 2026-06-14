// Thin API client wrapping the backend's /api/audit endpoints.

async function readAuditStream(response, onProgress) {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (data && data.detail) message = data.detail;
    } catch {
      // Keep default message when body is not JSON
    }
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error("Streaming is not supported in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk.trim().replace(/^data:\s*/, "");
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.type === "progress" && event.message && onProgress) {
        onProgress(event.message);
      } else if (event.type === "complete") {
        result = event.data;
      } else if (event.type === "error") {
        throw new Error(event.message || "Audit failed.");
      }
    }
  }

  if (!result) {
    throw new Error("Audit finished without a result.");
  }
  return result;
}

// POST a URL to the auditor and return the parsed AuditResponse JSON.
export async function runAudit(url, onProgress) {
  const response = await fetch("/api/audit/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  return readAuditStream(response, onProgress);
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

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${report.kind}-audit.pdf`;

  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

// POST supplementary reference PDF and trigger a browser download.
export async function downloadSupplementaryPdf({
  final_url,
  duration_seconds,
  connected,
  seo,
  geo,
  kind,
}) {
  const response = await fetch("/api/report/supplementary-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ final_url, duration_seconds, connected, seo, geo, kind }),
  });

  if (!response.ok) {
    let message = `PDF download failed (${response.status})`;
    try {
      const data = await response.json();
      if (data && data.detail) message = data.detail;
    } catch {
      // Keep the default message
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${kind}.pdf`;

  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}
