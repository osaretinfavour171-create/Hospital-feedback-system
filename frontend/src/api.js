const BASE = "/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = Array.isArray(body.detail)
          ? body.detail.map((d) => d.msg).join("; ")
          : body.detail;
      }
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  nurseFeedback: (payload) =>
    request("/feedback/nurse", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  whatsappText: (payload) =>
    request("/feedback/whatsapp/text", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  whatsappAudio: (formData) =>
    fetch(`${BASE}/feedback/whatsapp/audio`, {
      method: "POST",
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const body = await res.json();
          if (body.detail) detail = body.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }
      return res.json();
    }),
  metrics: () => request("/dashboard/metrics"),
  alerts: (status = "") =>
    request(`/dashboard/alerts${status ? `?status=${status}` : ""}`),
  recentFeedback: () => request("/feedback/recent"),
  resolveAlert: (id) =>
    request(`/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "RESOLVED" }),
    }),
  health: () => request("/health"),
};
