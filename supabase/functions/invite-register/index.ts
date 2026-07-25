const allowedOrigins = new Set([
  "https://beau-ai-trader.vercel.app",
  "http://127.0.0.1:5173",
  "http://localhost:5173",
]);

function corsHeaders(request: Request) {
  const origin = request.headers.get("origin") ?? "";
  return {
    "Access-Control-Allow-Origin": allowedOrigins.has(origin)
      ? origin
      : "https://beau-ai-trader.vercel.app",
    "Access-Control-Allow-Headers": "content-type, apikey, authorization",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

function response(
  request: Request,
  status: number,
  payload: Record<string, unknown>,
) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders(request),
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

async function sha256(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function inviteRejection(
  request: Request,
  reason: "invalid" | "expired" | "revoked" | "exhausted",
) {
  const messages = {
    invalid: "This private beta invite is invalid.",
    expired: "This private beta invite has expired.",
    revoked: "This private beta invite has been revoked.",
    exhausted: "This private beta invite has already been used.",
  };
  const status = reason === "invalid" ? 404 : 410;
  return response(request, status, { error: reason, message: messages[reason] });
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(request) });
  }
  const origin = request.headers.get("origin");
  if (origin && !allowedOrigins.has(origin)) {
    return response(request, 403, {
      error: "origin_not_allowed",
      message: "Private beta registration is not available from this origin.",
    });
  }
  if (request.method !== "POST") {
    return response(request, 405, {
      error: "method_not_allowed",
      message: "This registration endpoint only accepts POST requests.",
    });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const confirmRedirect = Deno.env.get("INVITE_CONFIRM_REDIRECT") ??
    "https://beau-ai-trader.vercel.app/login?verified=1";
  if (!supabaseUrl || !serviceRoleKey) {
    return response(request, 503, {
      error: "service_unavailable",
      message: "Private beta registration is temporarily unavailable.",
    });
  }

  let payload: { token?: unknown; email?: unknown; password?: unknown };
  try {
    payload = await request.json();
  } catch {
    return response(request, 400, {
      error: "invalid_request",
      message: "Enter a valid email address and password.",
    });
  }

  const token = typeof payload.token === "string" ? payload.token.trim() : "";
  const email = typeof payload.email === "string"
    ? payload.email.trim().toLowerCase()
    : "";
  const password = typeof payload.password === "string" ? payload.password : "";
  if (token.length < 32 || token.length > 256) {
    return inviteRejection(request, "invalid");
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 320) {
    return response(request, 422, {
      error: "invalid_email",
      message: "Enter a valid email address.",
    });
  }
  if (
    password.length < 12 ||
    !/[a-z]/.test(password) ||
    !/[A-Z]/.test(password) ||
    !/[0-9]/.test(password)
  ) {
    return response(request, 422, {
      error: "weak_password",
      message:
        "Use at least 12 characters with upper-case, lower-case, and numeric characters.",
    });
  }

  const tokenHash = await sha256(token);
  const serviceHeaders = {
    "apikey": serviceRoleKey,
    "Authorization": `Bearer ${serviceRoleKey}`,
    "Content-Type": "application/json",
  };
  const inviteQuery = new URL(
    `${supabaseUrl}/rest/v1/beta_invites`,
  );
  inviteQuery.searchParams.set(
    "select",
    "id,status,expires_at,max_uses,use_count",
  );
  inviteQuery.searchParams.set("token_hash", `eq.${tokenHash}`);
  inviteQuery.searchParams.set("limit", "1");

  const inviteResponse = await fetch(inviteQuery, {
    headers: serviceHeaders,
  });
  if (!inviteResponse.ok) {
    return response(request, 503, {
      error: "service_unavailable",
      message: "Private beta registration is temporarily unavailable.",
    });
  }
  const invites = await inviteResponse.json();
  const invite = invites[0];
  if (!invite) return inviteRejection(request, "invalid");
  if (invite.status === "revoked") return inviteRejection(request, "revoked");
  if (
    invite.status === "expired" ||
    new Date(invite.expires_at).getTime() <= Date.now()
  ) {
    return inviteRejection(request, "expired");
  }
  if (
    invite.status === "used" ||
    invite.use_count >= invite.max_uses
  ) {
    return inviteRejection(request, "exhausted");
  }

  const inviteUrl = new URL(`${supabaseUrl}/auth/v1/invite`);
  inviteUrl.searchParams.set("redirect_to", confirmRedirect);
  const createResponse = await fetch(inviteUrl, {
    method: "POST",
    headers: serviceHeaders,
    body: JSON.stringify({
      email,
      data: { access: "private_beta_invite" },
    }),
  });
  if (!createResponse.ok) {
    const rateLimited = createResponse.status === 429;
    const accountExists = [400, 409, 422].includes(createResponse.status);
    const failureStatus = rateLimited ? 429 : accountExists ? 409 : 503;
    return response(request, failureStatus, {
      error: rateLimited
        ? "email_rate_limited"
        : accountExists
        ? "account_exists"
        : "verification_unavailable",
      message: rateLimited
        ? "Too many verification emails were requested. Please wait a few minutes and try again."
        : accountExists
        ? "This email already has an account. Sign in instead."
        : "The verification email could not be sent. Please try again.",
    });
  }
  const createdUser = await createResponse.json();

  const passwordResponse = await fetch(
    `${supabaseUrl}/auth/v1/admin/users/${createdUser.id}`,
    {
      method: "PUT",
      headers: serviceHeaders,
      body: JSON.stringify({ password }),
    },
  );
  if (!passwordResponse.ok) {
    await fetch(`${supabaseUrl}/auth/v1/admin/users/${createdUser.id}`, {
      method: "DELETE",
      headers: serviceHeaders,
    });
    return response(request, 503, {
      error: "account_setup_failed",
      message: "Your account could not be prepared. Please try again.",
    });
  }

  const invitedUser = await passwordResponse.json();
  if (!invitedUser?.id || invitedUser.id !== createdUser.id) {
    await fetch(`${supabaseUrl}/auth/v1/admin/users/${createdUser.id}`, {
      method: "DELETE",
      headers: serviceHeaders,
    });
    return response(request, 503, {
      error: "account_setup_failed",
      message: "Your account could not be prepared. Please try again.",
    });
  }

  const consumeResponse = await fetch(
    `${supabaseUrl}/rest/v1/rpc/consume_beta_invite`,
    {
      method: "POST",
      headers: serviceHeaders,
      body: JSON.stringify({
        p_token_hash: tokenHash,
        p_user_id: createdUser.id,
      }),
    },
  );
  const consumption = consumeResponse.ok
    ? await consumeResponse.json()
    : { ok: false, reason: "invalid" };
  if (!consumeResponse.ok || !consumption.ok) {
    await fetch(`${supabaseUrl}/auth/v1/admin/users/${createdUser.id}`, {
      method: "DELETE",
      headers: serviceHeaders,
    });
    const reason = ["expired", "revoked", "exhausted"].includes(
        consumption.reason,
      )
      ? consumption.reason
      : "invalid";
    return inviteRejection(request, reason);
  }

  return response(request, 201, {
    registered: true,
    email_verification_required: true,
    message: "Check your email to verify your account before signing in.",
  });
});
