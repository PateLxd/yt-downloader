"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type JobInfo, type Metadata } from "@/lib/api";
import { AuthGate } from "@/components/AuthGate";
import { Topbar } from "@/components/Topbar";
import { UrlForm } from "@/components/UrlForm";
import { VideoPreview } from "@/components/VideoPreview";
import { DownloadPanel } from "@/components/DownloadPanel";
import { JobRow } from "@/components/JobRow";
import { CookiesModal, type OpenReason } from "@/components/CookiesModal";

function DashboardInner() {
  const [meta, setMeta] = useState<Metadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<JobInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [cookiesOpen, setCookiesOpen] = useState(false);
  const [cookiesReason, setCookiesReason] = useState<OpenReason | null>(null);
  // Job ids we've already surfaced as cookies_required so the modal doesn't
  // keep popping on every 3s poll tick if the user dismissed it.
  const seenJobCookieFailures = useRef<Set<string>>(new Set());
  // Mirror of `cookiesOpen` so the long-lived setInterval closure can read
  // the current value. The state variable itself is captured at mount and
  // would otherwise stay frozen at `false`.
  const cookiesOpenRef = useRef(false);

  const openCookiesModal = (reason: OpenReason) => {
    setCookiesReason(reason);
    setCookiesOpen(true);
    cookiesOpenRef.current = true;
  };

  const closeCookiesModal = () => {
    setCookiesOpen(false);
    setCookiesReason(null);
    cookiesOpenRef.current = false;
  };

  const refreshRecent = async () => {
    try {
      const [list, cap] = await Promise.all([api.listDownloads(), api.capacity()]);
      setRecent(list);
      setBusy(cap.busy);
      // Auto-open the cookies modal the first time we see a job fail for
      // cookies_required. If the user dismisses, we won't re-open for the same
      // job id.
      const cookieFail = list.find(
        (j) => j.status === "failed" && j.error_code === "cookies_required",
      );
      if (cookieFail && !seenJobCookieFailures.current.has(cookieFail.id)) {
        seenJobCookieFailures.current.add(cookieFail.id);
        if (!cookiesOpenRef.current) {
          openCookiesModal({
            kind: "job",
            message:
              cookieFail.error ??
              "A download failed because YouTube is asking for a signed-in session. Paste fresh cookies and retry.",
            jobId: cookieFail.id,
          });
        }
      }
    } catch {
      /* ignore — auth gate will redirect if needed */
    }
  };

  useEffect(() => {
    refreshRecent();
    const id = window.setInterval(refreshRecent, 3000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFetch = async (url: string) => {
    setLoading(true);
    setError(null);
    setMeta(null);
    try {
      const m = await api.metadata(url);
      setMeta(m);
    } catch (err) {
      if (err instanceof ApiError && err.code === "cookies_required") {
        openCookiesModal({ kind: "metadata", message: err.message, url });
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to fetch metadata");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCookiesSaved = async (reason: OpenReason | null) => {
    closeCookiesModal();
    // Auto-retry the action that triggered the modal so the user doesn't
    // have to click again.
    if (reason?.kind === "metadata") {
      await handleFetch(reason.url);
    }
    // For job-failure reasons, just surface a hint — the user knows what to
    // retry; we don't want to silently re-enqueue a rate-limit-consuming job.
  };

  return (
    <main className="min-h-dvh bg-muted/30">
      <Topbar />
      <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
        <section className="space-y-3">
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <UrlForm loading={loading} onSubmit={handleFetch} />
          {busy && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Server is at full capacity — please wait for some time.
            </div>
          )}
          {error && (
            <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          )}
          {loading && !meta && (
            <div className="card flex flex-col gap-4 p-4 sm:flex-row">
              <div className="skeleton h-32 w-full max-w-xs" />
              <div className="space-y-2">
                <div className="skeleton h-5 w-64" />
                <div className="skeleton h-4 w-40" />
              </div>
            </div>
          )}
          {meta && <VideoPreview meta={meta} />}
          {meta && (
            <DownloadPanel
              meta={meta}
              onSubmitted={() => {
                refreshRecent();
              }}
            />
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Recent downloads</h2>
          {recent.length === 0 ? (
            <p className="text-sm text-muted-foreground">No downloads yet.</p>
          ) : (
            <div className="space-y-2">
              {recent.slice(0, 5).map((j) => (
                <JobRow
                  key={j.id}
                  job={j}
                  onCookiesNeeded={() =>
                    openCookiesModal({
                      kind: "job",
                      message:
                        j.error ??
                        "YouTube wants a signed-in session. Paste fresh cookies and retry this download.",
                      jobId: j.id,
                    })
                  }
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <CookiesModal
        open={cookiesOpen}
        reason={cookiesReason}
        onClose={closeCookiesModal}
        onSaved={handleCookiesSaved}
      />
    </main>
  );
}

export default function Page() {
  return (
    <AuthGate>
      <DashboardInner />
    </AuthGate>
  );
}
