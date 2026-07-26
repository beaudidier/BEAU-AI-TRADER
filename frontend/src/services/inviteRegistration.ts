const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

type InviteRegistrationResponse = {
  registered?: boolean;
  email_verification_required?: boolean;
  verification_sent?: boolean;
  already_verified?: boolean;
  cooldown_seconds?: number;
  message?: string;
};

type InviteRegistrationErrorResponse = InviteRegistrationResponse & {
  error?: string;
};

export class InviteRegistrationError extends Error {
  code: string;
  status: number;
  cooldownSeconds: number;

  constructor({
    code,
    status,
    message,
    cooldownSeconds = 0,
  }: {
    code: string;
    status: number;
    message: string;
    cooldownSeconds?: number;
  }) {
    super(message);
    this.name = "InviteRegistrationError";
    this.code = code;
    this.status = status;
    this.cooldownSeconds = cooldownSeconds;
  }
}

type InviteRegistrationPayload = {
  token: string;
  email: string;
  password: string;
};

let registrationRequest: Promise<InviteRegistrationResponse> | null = null;
let resendRequest: Promise<InviteRegistrationResponse> | null = null;

function humanError(
  response: Response,
  result: InviteRegistrationErrorResponse,
) {
  const code = result.error ?? "registration_failed";
  const rawMessage = result.message ?? "";
  const normalized = `${code} ${rawMessage}`.toLowerCase();
  const isRateLimited = response.status === 429
    || normalized.includes("rate limit")
    || normalized.includes("too many")
    || code === "over_email_send_rate_limit"
    || code === "over_request_rate_limit";

  if (isRateLimited) {
    return new InviteRegistrationError({
      code: "email_rate_limited",
      status: response.status,
      cooldownSeconds: result.cooldown_seconds ?? 60,
      message:
        "Too many verification emails were requested. Please wait for the countdown before trying again.",
    });
  }

  if (code === "account_exists") {
    return new InviteRegistrationError({
      code,
      status: response.status,
      message:
        "An account already exists for this email. Sign in or request another verification email.",
    });
  }

  if (code === "exhausted") {
    return new InviteRegistrationError({
      code,
      status: response.status,
      message:
        "This invite has already been used. Sign in or request another verification email.",
    });
  }

  return new InviteRegistrationError({
    code,
    status: response.status,
    message: rawMessage || "Private beta registration could not be completed.",
  });
}

async function requestInviteRegistration(
  payload: Record<string, string>,
): Promise<InviteRegistrationResponse> {
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new InviteRegistrationError({
      code: "service_unavailable",
      status: 503,
      message: "Private beta registration is temporarily unavailable.",
    });
  }
  const response = await fetch(`${supabaseUrl}/functions/v1/invite-register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": supabaseAnonKey,
    },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(
    () => ({}),
  ) as InviteRegistrationErrorResponse;
  if (!response.ok) {
    throw humanError(response, result);
  }
  return result;
}

export function registerWithInvite(
  payload: InviteRegistrationPayload,
): Promise<InviteRegistrationResponse> {
  if (registrationRequest) return registrationRequest;
  registrationRequest = requestInviteRegistration({
    action: "register",
    ...payload,
  }).finally(() => {
    registrationRequest = null;
  });
  return registrationRequest;
}

export function resendInviteVerification(payload: {
  token: string;
  email: string;
}): Promise<InviteRegistrationResponse> {
  if (resendRequest) return resendRequest;
  resendRequest = requestInviteRegistration({
    action: "resend",
    ...payload,
  }).finally(() => {
    resendRequest = null;
  });
  return resendRequest;
}
