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

async function authFailureDetails(authResponse: Response) {
  const payload = await authResponse.json().catch(() => ({}));
  return {
    code: typeof payload?.code === "string" ? payload.code : "",
    message: typeof payload?.message === "string" ? payload.message : "",
  };
}

function isEmailRateLimit(
  status: number,
  details: { code: string; message: string },
) {
  const normalized = `${details.code} ${details.message}`.toLowerCase();
  return status === 429 ||
    details.code === "over_email_send_rate_limit" ||
    details.code === "over_request_rate_limit" ||
    normalized.includes("rate limit") ||
    normalized.includes("too many");
}

function emailRateLimitResponse(request: Request) {
  return response(request, 429, {
    error: "email_rate_limited",
    message:
      "Too many verification emails were requested. Please wait for the countdown before trying again.",
    cooldown_seconds: 60,
  });
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
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  const confirmRedirect = Deno.env.get("INVITE_CONFIRM_REDIRECT") ??
    "https://beau-ai-trader.vercel.app/login?verified=1";
  if (!supabaseUrl || !serviceRoleKey || !anonKey) {
    return response(request, 503, {
      error: "service_unavailable",
      message: "Private beta registration is temporarily unavailable.",
    });
  }

  let payload: {
    action?: unknown;
    token?: unknown;
    email?: unknown;
    password?: unknown;
  };
  try {
    payload = await request.json();
  } catch {
    return response(request, 400, {
      error: "invalid_request",
      message: "Enter a valid email address and password.",
    });
  }

  const action = payload.action === undefined || payload.action === "register"
    ? "register"
    : payload.action === "resend"
    ? "resend"
    : "";
  const token = typeof payload.token === "string" ? payload.token.trim() : "";
  const email = typeof payload.email === "string"
    ? payload.email.trim().toLowerCase()
    : "";
  const password = typeof payload.password === "string" ? payload.password : "";
  if (!action) {
    return response(request, 400, {
      error: "invalid_request",
      message: "This verification request is invalid.",
    });
  }
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
    action === "register" &&
    (
      password.length < 12 ||
      !/[a-z]/.test(password) ||
      !/[A-Z]/.test(password) ||
      !/[0-9]/.test(password)
    )
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
    action === "register" &&
    (
      invite.status === "used" ||
      invite.use_count >= invite.max_uses
    )
  ) {
    return inviteRejection(request, "exhausted");
  }

  if (action === "resend") {
    const useQuery = new URL(
      `${supabaseUrl}/rest/v1/beta_invite_uses`,
    );
    useQuery.searchParams.set("select", "user_id");
    useQuery.searchParams.set("invite_id", `eq.${invite.id}`);
    useQuery.searchParams.set("limit", "1");
    const useResponse = await fetch(useQuery, { headers: serviceHeaders });
    const uses = useResponse.ok ? await useResponse.json() : [];
    const userId = uses[0]?.user_id;
    if (!useResponse.ok || !userId) {
      return response(request, 409, {
        error: "verification_not_available",
        message:
          "A verification email cannot be resent for this invite. Sign in if your email is already confirmed.",
      });
    }

    const userResponse = await fetch(
      `${supabaseUrl}/auth/v1/admin/users/${userId}`,
      { headers: serviceHeaders },
    );
    const invitedUser = userResponse.ok ? await userResponse.json() : null;
    if (
      !invitedUser ||
      typeof invitedUser.email !== "string" ||
      invitedUser.email.toLowerCase() !== email
    ) {
      return response(request, 403, {
        error: "verification_not_available",
        message:
          "A verification email cannot be resent for these account details.",
      });
    }
    if (invitedUser.email_confirmed_at) {
      return response(request, 200, {
        already_verified: true,
        message: "Your email is already verified. You can sign in now.",
      });
    }

    const resendUrl = new URL(`${supabaseUrl}/auth/v1/otp`);
    resendUrl.searchParams.set("redirect_to", confirmRedirect);
    const resendResponse = await fetch(resendUrl, {
      method: "POST",
      headers: {
        "apikey": anonKey,
        "Authorization": `Bearer ${anonKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        create_user: false,
      }),
    });
    if (!resendResponse.ok) {
      const details = await authFailureDetails(resendResponse);
      if (isEmailRateLimit(resendResponse.status, details)) {
        return emailRateLimitResponse(request);
      }
      return response(request, 503, {
        error: "verification_unavailable",
        message:
          "Another verification email could not be sent. Please try again later.",
      });
    }

    return response(request, 200, {
      verification_sent: true,
      cooldown_seconds: 60,
      message: "Verification email sent. Check your inbox and spam folder.",
    });
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
    const details = await authFailureDetails(createResponse);
    const rateLimited = isEmailRateLimit(createResponse.status, details);
    const accountExists = createResponse.status === 409 ||
      details.code === "user_already_exists" ||
      details.code === "email_exists";
    const invalidEmail = details.code === "email_address_invalid" ||
      details.code === "validation_failed";
    if (rateLimited) return emailRateLimitResponse(request);
    const failureStatus = accountExists ? 409 : invalidEmail ? 422 : 503;
    return response(request, failureStatus, {
      error: accountExists
        ? "account_exists"
        : invalidEmail
        ? "invalid_email"
        : "verification_unavailable",
      message: accountExists
        ? "This email already has an account. Sign in instead."
        : invalidEmail
        ? "Enter a valid email address that can receive verification messages."
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
    cooldown_seconds: 60,
    message:
      "Account created. Check your inbox and spam folder to verify your email.",
  });
});
