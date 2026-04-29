"use client";

import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { api, type CookiesStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CookiesModal } from "./CookiesModal";

/**
 * Persistent topbar button for the YouTube cookies override.
 *
 * Shows the current source (override / file / none) so the user can tell at
 * a glance whether the app has cookies to work with, and how long the
 * runtime override has left. Clicking always opens the modal so cookies can
 * be pasted on demand — independent of whether a download has failed yet.
 *
 * Why a dedicated component (vs. inlined in Topbar): we want the button to
 * be visible on every authenticated page, but the modal it owns is heavy
 * (textarea, validation, async POST). Keeping the open/close state local to
 * this component avoids prop-drilling through Topbar and means the dashboard
 * still owns its own modal instance for auto-opens on job failure /
 * metadata cookies_required errors.
 */
export function CookiesStatusButton() {
  const [status, setStatus] = useState<CookiesStatus | null>(null);
  const [open, setOpen] = useState(false);

  const refresh = async () => {
    try {
      setStatus(await api.cookiesStatus());
    } catch {
      // Auth gate handles 401s; for any other error just leave the button
      // showing whatever we last saw.
    }
  };

  useEffect(() => {
    refresh();
    // Refresh once a minute so the override TTL countdown stays roughly
    // honest without spamming the API.
    const id = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(id);
  }, []);

  const { label, dotClass, title } = describe(status);

  return (
    <>
      <button
        type="button"
        className="btn-secondary"
        onClick={() => setOpen(true)}
        title={title}
      >
        <KeyRound className="h-4 w-4" />
        <span
          className={cn("inline-block h-2 w-2 rounded-full", dotClass)}
          aria-hidden="true"
        />
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">Cookies</span>
      </button>
      <CookiesModal
        open={open}
        reason={open ? { kind: "manual" } : null}
        onClose={() => setOpen(false)}
        onSaved={async () => {
          setOpen(false);
          await refresh();
        }}
      />
    </>
  );
}

function describe(status: CookiesStatus | null): {
  label: string;
  dotClass: string;
  title: string;
} {
  if (!status) {
    return {
      label: "Cookies",
      dotClass: "bg-muted-foreground/40",
      title: "Loading cookies status…",
    };
  }
  if (status.source === "none") {
    return {
      label: "Cookies missing",
      dotClass: "bg-red-500",
      title:
        "No YouTube cookies configured. Click to paste a cookies.txt and " +
        "make YouTube downloads work behind the bot challenge.",
    };
  }
  if (status.source === "file") {
    return {
      label: "Cookies: file",
      dotClass: "bg-emerald-500",
      title:
        "Using cookies from the on-disk file (YT_DLP_COOKIES_PATH). " +
        "Click to paste fresh cookies as a runtime override.",
    };
  }
  // status.source === "override"
  const days = formatDays(status.expires_in_seconds ?? null);
  return {
    label: days ? `Cookies: ${days} left` : "Cookies: override",
    dotClass: "bg-emerald-500",
    title:
      "Using a runtime cookies override (Valkey)" +
      (days ? `, expires in ${days}.` : ".") +
      " Click to paste fresh cookies or extend the override.",
  };
}

function formatDays(seconds: number | null): string | null {
  if (seconds === null || seconds <= 0) return null;
  const days = seconds / 86400;
  if (days >= 2) return `${Math.floor(days)}d`;
  const hours = seconds / 3600;
  if (hours >= 1) return `${Math.floor(hours)}h`;
  const minutes = Math.max(1, Math.floor(seconds / 60));
  return `${minutes}m`;
}
