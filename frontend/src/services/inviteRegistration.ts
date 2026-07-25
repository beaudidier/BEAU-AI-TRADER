const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

type InviteRegistrationResponse = {
  registered?: boolean;
  email_verification_required?: boolean;
  message?: string;
};

export async function registerWithInvite(payload: {
  token: string;
  email: string;
  password: string;
}): Promise<InviteRegistrationResponse> {
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error("Private beta registration is temporarily unavailable.");
  }
  const response = await fetch(`${supabaseUrl}/functions/v1/invite-register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": supabaseAnonKey,
    },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({})) as InviteRegistrationResponse;
  if (!response.ok) {
    throw new Error(result.message ?? "Private beta registration could not be completed.");
  }
  return result;
}
