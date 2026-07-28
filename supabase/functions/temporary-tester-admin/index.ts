const allowedOrigins = new Set([
  "https://beau-ai-trader.vercel.app",
  "http://127.0.0.1:5173",
]);

function reply(request: Request, status: number, payload: Record<string, unknown>) {
  const origin = request.headers.get("origin") ?? "";
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": allowedOrigins.has(origin)
        ? origin
        : "https://beau-ai-trader.vercel.app",
      "Access-Control-Allow-Headers": "apikey, authorization, content-type",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Vary": "Origin",
    },
  });
}

function temporaryPassword() {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  return `${btoa(String.fromCharCode(...bytes)).replaceAll("/", "A").replaceAll("+", "b").replaceAll("=", "")}aA7`;
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return reply(request, 204, {});
  if (request.method !== "POST") return reply(request, 405, { error: "method_not_allowed" });
  const origin = request.headers.get("origin");
  if (origin && !allowedOrigins.has(origin)) return reply(request, 403, { error: "origin_not_allowed" });

  const url = Deno.env.get("SUPABASE_URL");
  const anon = Deno.env.get("SUPABASE_ANON_KEY");
  const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !anon || !service) return reply(request, 503, { error: "unavailable" });
  const bearer = request.headers.get("authorization") ?? "";
  const callerResponse = await fetch(`${url}/auth/v1/user`, {
    headers: { apikey: anon, Authorization: bearer },
  });
  const caller = callerResponse.ok ? await callerResponse.json() : null;
  if (!caller?.id) return reply(request, 401, { error: "unauthorized" });

  const serviceHeaders = {
    apikey: service,
    Authorization: `Bearer ${service}`,
    "Content-Type": "application/json",
  };
  const adminQuery = new URL(`${url}/rest/v1/private_beta_memberships`);
  adminQuery.searchParams.set("select", "role");
  adminQuery.searchParams.set("user_id", `eq.${caller.id}`);
  adminQuery.searchParams.set("active", "eq.true");
  adminQuery.searchParams.set("role", "in.(OWNER,ADMIN)");
  const adminRows = await (await fetch(adminQuery, { headers: serviceHeaders })).json();
  if (!adminRows.length) return reply(request, 403, { error: "forbidden" });

  const body = await request.json().catch(() => ({}));
  const action = typeof body.action === "string" ? body.action : "";
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const targetUserId = typeof body.user_id === "string" ? body.user_id : "";
  const audit = async (target: string, auditAction: string, expiresAt?: string) => {
    await fetch(`${url}/rest/v1/temporary_beta_account_audit`, {
      method: "POST",
      headers: serviceHeaders,
      body: JSON.stringify({
        actor_user_id: caller.id,
        target_user_id: target,
        action: auditAction,
        expires_at: expiresAt ?? null,
      }),
    });
  };

  if (action === "create") {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return reply(request, 422, { error: "invalid_request" });
    const password = temporaryPassword();
    const expiresAt = new Date(Date.now() + 7 * 86400_000).toISOString();
    const createdResponse = await fetch(`${url}/auth/v1/admin/users`, {
      method: "POST",
      headers: serviceHeaders,
      body: JSON.stringify({
        email,
        password,
        email_confirm: true,
        user_metadata: { temporary_beta: true, temporary_beta_expires_at: expiresAt },
      }),
    });
    const created = createdResponse.ok ? await createdResponse.json() : null;
    if (!created?.id) return reply(request, 409, { error: "account_unavailable" });
    await fetch(`${url}/rest/v1/private_beta_memberships`, {
      method: "POST",
      headers: { ...serviceHeaders, Prefer: "resolution=merge-duplicates" },
      body: JSON.stringify({
        user_id: created.id,
        role: "TESTER",
        active: true,
        temporary: true,
        expires_at: expiresAt,
      }),
    });
    await audit(created.id, "created", expiresAt);
    return reply(request, 201, { user_id: created.id, email, temporary_password: password, expires_at: expiresAt });
  }

  if (!targetUserId) return reply(request, 422, { error: "invalid_request" });
  const membershipUrl = `${url}/rest/v1/private_beta_memberships?user_id=eq.${targetUserId}&role=eq.TESTER&temporary=eq.true`;
  const membershipResponse = await fetch(`${membershipUrl}&select=*`, { headers: serviceHeaders });
  const memberships = membershipResponse.ok ? await membershipResponse.json() : [];
  const membership = memberships[0];
  if (!membership) return reply(request, 404, { error: "temporary_tester_not_found" });

  if (action === "rotate_password") {
    const password = temporaryPassword();
    const updated = await fetch(`${url}/auth/v1/admin/users/${targetUserId}`, {
      method: "PUT",
      headers: serviceHeaders,
      body: JSON.stringify({ password }),
    });
    if (!updated.ok) return reply(request, 503, { error: "rotation_failed" });
    await audit(targetUserId, "password_rotated", membership.expires_at);
    return reply(request, 200, { temporary_password: password });
  }
  if (action === "extend_expiry" && !membership.expiry_extended_once) {
    const expiresAt = new Date(new Date(membership.expires_at).getTime() + 7 * 86400_000).toISOString();
    await fetch(membershipUrl, {
      method: "PATCH",
      headers: serviceHeaders,
      body: JSON.stringify({ expires_at: expiresAt, expiry_extended_once: true }),
    });
    await audit(targetUserId, "expiry_extended", expiresAt);
    return reply(request, 200, { expires_at: expiresAt });
  }
  if (action === "revoke") {
    await fetch(membershipUrl, { method: "PATCH", headers: serviceHeaders, body: JSON.stringify({ active: false }) });
    await audit(targetUserId, "revoked", membership.expires_at);
    return reply(request, 200, { revoked: true });
  }
  if (action === "delete") {
    await audit(targetUserId, "deleted", membership.expires_at);
    const deleted = await fetch(`${url}/auth/v1/admin/users/${targetUserId}`, { method: "DELETE", headers: serviceHeaders });
    return reply(request, deleted.ok ? 200 : 503, deleted.ok ? { deleted: true } : { error: "delete_failed" });
  }
  return reply(request, 409, { error: "action_not_available" });
});
