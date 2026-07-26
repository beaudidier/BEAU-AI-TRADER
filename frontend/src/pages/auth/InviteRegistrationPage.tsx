import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AuthInput } from "../../components/auth/AuthInput";
import { AuthShell } from "../../components/auth/AuthShell";
import {
  InviteRegistrationError,
  registerWithInvite,
  resendInviteVerification,
} from "../../services/inviteRegistration";

const EMAIL_COOLDOWN_KEY = "beau-invite-email-cooldown-until";
const DEFAULT_COOLDOWN_SECONDS = 60;

function storedCooldownDeadline() {
  const stored = Number(window.localStorage.getItem(EMAIL_COOLDOWN_KEY) ?? 0);
  return Number.isFinite(stored) ? stored : 0;
}

function remainingSeconds(deadline: number) {
  return Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
}

export default function InviteRegistrationPage() {
  const { token: routeToken = "" } = useParams();
  const [inviteToken] = useState(routeToken);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accountExists, setAccountExists] = useState(false);
  const [cooldownDeadline, setCooldownDeadline] = useState(
    storedCooldownDeadline,
  );
  const [cooldownSeconds, setCooldownSeconds] = useState(
    remainingSeconds(storedCooldownDeadline()),
  );
  const requestInFlight = useRef(false);

  useEffect(() => {
    if (routeToken) {
      window.history.replaceState(window.history.state, "", "/invite");
    }
  }, [routeToken]);

  useEffect(() => {
    function updateCountdown() {
      const seconds = remainingSeconds(cooldownDeadline);
      setCooldownSeconds(seconds);
      if (seconds === 0 && cooldownDeadline > 0) {
        window.localStorage.removeItem(EMAIL_COOLDOWN_KEY);
      }
    }

    updateCountdown();
    const timer = window.setInterval(updateCountdown, 250);
    return () => window.clearInterval(timer);
  }, [cooldownDeadline]);

  useEffect(() => {
    function syncCooldown(event: StorageEvent) {
      if (event.key === EMAIL_COOLDOWN_KEY) {
        setCooldownDeadline(storedCooldownDeadline());
      }
    }
    window.addEventListener("storage", syncCooldown);
    return () => window.removeEventListener("storage", syncCooldown);
  }, []);

  function startCooldown(seconds = DEFAULT_COOLDOWN_SECONDS) {
    const safeSeconds = Math.max(1, Math.ceil(seconds));
    const deadline = Date.now() + safeSeconds * 1000;
    window.localStorage.setItem(EMAIL_COOLDOWN_KEY, String(deadline));
    setCooldownDeadline(deadline);
    setCooldownSeconds(safeSeconds);
  }

  function handleRegistrationError(registrationError: unknown) {
    const knownError = registrationError instanceof InviteRegistrationError
      ? registrationError
      : null;
    if (knownError?.cooldownSeconds) {
      startCooldown(knownError.cooldownSeconds);
    }
    setAccountExists(
      knownError?.code === "account_exists"
        || knownError?.code === "exhausted",
    );
    setError(
      knownError?.message
        ?? (registrationError instanceof Error
          ? registrationError.message
          : "Private beta registration could not be completed."),
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (requestInFlight.current || loading || cooldownSeconds > 0) return;
    setError(null);
    setMessage(null);
    setAccountExists(false);
    if (!inviteToken) {
      setError("This private beta invite is invalid.");
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    requestInFlight.current = true;
    setLoading(true);
    try {
      const result = await registerWithInvite({
        token: inviteToken,
        email,
        password,
      });
      startCooldown(result.cooldown_seconds ?? DEFAULT_COOLDOWN_SECONDS);
      setMessage(
        result.message
          ?? "Account created. Check your inbox and spam folder to verify your email.",
      );
      setPassword("");
      setConfirmPassword("");
    } catch (registrationError) {
      handleRegistrationError(registrationError);
    } finally {
      requestInFlight.current = false;
      setLoading(false);
    }
  }

  async function resendVerification() {
    if (
      requestInFlight.current
      || resendLoading
      || cooldownSeconds > 0
      || !inviteToken
      || !email
    ) {
      return;
    }
    requestInFlight.current = true;
    setResendLoading(true);
    setError(null);
    try {
      const result = await resendInviteVerification({
        token: inviteToken,
        email,
      });
      startCooldown(result.cooldown_seconds ?? DEFAULT_COOLDOWN_SECONDS);
      setMessage(
        result.message
          ?? "Verification email sent. Check your inbox and spam folder.",
      );
      setAccountExists(false);
    } catch (registrationError) {
      handleRegistrationError(registrationError);
    } finally {
      requestInFlight.current = false;
      setResendLoading(false);
    }
  }

  const requestDisabled = loading || resendLoading || cooldownSeconds > 0;
  const countdownText = cooldownSeconds > 0
    ? `You can request another email in ${cooldownSeconds}s.`
    : null;

  return (
    <AuthShell title="Create your private beta account">
      <p className="mb-5 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm font-medium text-cyan-100">
        Private beta access only.
      </p>
      {message ? (
        <div className="space-y-5">
          <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm leading-6 text-emerald-100">{message}</p>
          <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-4">
            <p className="font-semibold text-slate-100">Check your inbox and spam folder</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">Email verification remains required. You cannot sign in until the confirmation link has been opened.</p>
            {countdownText && <p aria-live="polite" className="mt-3 text-sm font-medium text-cyan-200">{countdownText}</p>}
          </div>
          <button
            type="button"
            onClick={resendVerification}
            disabled={requestDisabled}
            className="h-11 w-full rounded-lg border border-cyan-400/30 bg-cyan-400/10 font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {resendLoading
              ? "Sending verification email…"
              : cooldownSeconds > 0
              ? `Resend available in ${cooldownSeconds}s`
              : "Resend verification"}
          </button>
          <Link to="/login" className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-cyan-400 font-semibold text-slate-950">Go to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <AuthInput label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <AuthInput label="Password" type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
          <AuthInput label="Confirm password" type="password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
          <p className="text-xs leading-5 text-slate-500">Use at least 12 characters with upper-case, lower-case, and numeric characters.</p>
          {error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
          {accountExists && (
            <div className="space-y-3 rounded-lg border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-sm leading-6 text-amber-100">Already registered? Sign in now, or resend verification if you have not confirmed your email yet.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Link to="/login" className="inline-flex h-10 items-center justify-center rounded-lg bg-cyan-400 px-4 text-sm font-semibold text-slate-950">Sign in</Link>
                <button
                  type="button"
                  onClick={resendVerification}
                  disabled={requestDisabled || !email}
                  className="h-10 rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {resendLoading
                    ? "Sending…"
                    : cooldownSeconds > 0
                    ? `Resend in ${cooldownSeconds}s`
                    : "Resend verification"}
                </button>
              </div>
              {countdownText && <p aria-live="polite" className="text-xs text-amber-200">{countdownText}</p>}
            </div>
          )}
          {countdownText && !accountExists && (
            <p aria-live="polite" className="text-center text-sm font-medium text-cyan-200">{countdownText}</p>
          )}
          <button
            disabled={requestDisabled}
            className="h-11 w-full rounded-lg bg-cyan-400 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading
              ? "Creating secure account…"
              : cooldownSeconds > 0
              ? `Try again in ${cooldownSeconds}s`
              : "Create private beta account"}
          </button>
        </form>
      )}
      <Link to="/login" className="mt-6 inline-flex text-sm text-cyan-300 hover:text-cyan-200">Already registered? Sign in</Link>
    </AuthShell>
  );
}
