// All calls to the FastAPI backend go through here.
// Vite forwards /api/* to http://localhost:8000 (see vite.config.js).

async function request(path, options = {}) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `HTTP ${res.status}`;
    throw new Error(message);
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),

  listBatches: () => request("/api/batches"),

  getBatch: (id) => request(`/api/batches/${id}`),

  getFile: (id) => request(`/api/files/${id}`),

  pdfUrl: (id) => `/api/files/${id}/pdf`,

  // action: "flag" | "approve" | "reject"
  reviewFile: (id, action, note) =>
    request(`/api/files/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, note }),
    }),

  reprocessFile: (id) => request(`/api/files/${id}/reprocess`, { method: "POST" }),

  reviewQueue: (status = "needs_review") => request(`/api/review-queue?status=${status}`),

  createBatch: (name, files) => {
    const form = new FormData();
    if (name) form.append("name", name);
    for (const file of files) form.append("files", file);
    return request("/api/batches", { method: "POST", body: form });
  },
};
