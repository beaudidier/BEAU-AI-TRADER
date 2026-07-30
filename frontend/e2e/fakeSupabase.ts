const user = {
  id: "beginner-e2e-user",
  email: "beginner@example.test",
  app_metadata: {},
  user_metadata: {},
  aud: "authenticated",
  created_at: "2026-07-28T00:00:00Z",
};

const session = {
  access_token: "e2e-access-token",
  refresh_token: "e2e-refresh-token",
  expires_in: 3600,
  token_type: "bearer",
  user,
};

export const supabase = {
  auth: {
    getSession: async () => ({ data: { session } }),
    onAuthStateChange: () => ({
      data: { subscription: { unsubscribe: () => undefined } },
    }),
    signOut: async () => ({ error: null }),
  },
};
