import { useEffect } from "react";

import { useAuth } from "../hooks/useAuth";
import { userApi } from "../services/userApi";

function safeMessage(value: unknown) {
  if (value instanceof Error) return value.message.slice(0, 1000);
  if (typeof value === "string") return value.slice(0, 1000);
  return "An unexpected browser error occurred.";
}

function safeSource(value: string) {
  if (!value) return undefined;
  try {
    return new URL(value, window.location.origin).pathname.slice(0, 200);
  } catch {
    return "browser-script";
  }
}

function safePath(value: string) {
  return value.replace(/(\/invite\/)[^/?#\s]+/gi, "$1[REDACTED]").slice(0, 500);
}

export default function FrontendMonitoring() {
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return undefined;
    const report = (payload: {
      message: string;
      path: string;
      source?: string;
      line?: number;
      column?: number;
    }) => {
      void userApi.recordFrontendError(payload).catch(() => {
        // Monitoring is best-effort and must never interrupt the trader.
      });
    };
    const onError = (event: ErrorEvent) => {
      report({
        message: safeMessage(event.error ?? event.message),
        path: safePath(window.location.pathname),
        source: safeSource(event.filename),
        line: event.lineno || undefined,
        column: event.colno || undefined,
      });
    };
    const onUnhandled = (event: PromiseRejectionEvent) => {
      report({
        message: safeMessage(event.reason),
        path: safePath(window.location.pathname),
        source: "unhandled-promise",
      });
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, [user]);

  return null;
}
