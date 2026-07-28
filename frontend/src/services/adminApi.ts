import { API_BASE_URL } from "../config";
import { supabase } from "../lib/supabase";

async function request(path: string, options: RequestInit = {}) {
  const { data } = await supabase?.auth.getSession() ?? { data: { session: null } };
  if (!data.session) throw new Error("Sign in with an owner or administrator account.");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}`, ...options.headers },
  });
  if (!response.ok) {
    if (response.status === 403) throw new Error("Owner or administrator access is required.");
    throw new Error("The admin request could not be completed.");
  }
  return response.json();
}

export const adminApi = {
  overview: (search = "", status = "", severity = "") => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (status) query.set("feedback_status", status);
    if (severity) query.set("severity", severity);
    return request(`/admin/overview?${query}`);
  },
  updateFeedback: (id: string, status: string, ownerNotes: string | null) => request(`/admin/feedback/${id}`, { method: "PATCH", body: JSON.stringify({ status, owner_notes: ownerNotes }) }),
  updateAccount: (id: string, active: boolean) => request(`/admin/testers/${id}/account`, { method: "PATCH", body: JSON.stringify({ active }) }),
  activity: (id: string) => request(`/admin/testers/${id}/activity`),
  retryJob: (eventId: string) => request("/admin/jobs/retry", { method: "POST", body: JSON.stringify({ event_id: eventId }) }),
  createInvite: (label: string) => request("/admin/invites", { method: "POST", body: JSON.stringify({ label, expires_in_days: 7, max_uses: 1 }) }),
  revokeInvite: (id: string) => request(`/admin/invites/${id}/revoke`, { method: "POST" }),
};
