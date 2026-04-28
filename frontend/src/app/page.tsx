"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type JobInfo, type Metadata } from "@/lib/api";
import { AuthGate } from "@/components/AuthGate";
import { Topbar } from "@/components/Topbar";
import { UrlForm } from "@/components/UrlForm";
import { VideoPreview } from "@/components/VideoPreview";
import { DownloadPanel } from "@/components/DownloadPanel";
import { JobRow } from "@/components/JobRow";

function DashboardInner() {
  const [meta, setMeta] = useState<Metadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<JobInfo[]>([]);
  const [busy, setBusy] = useState(false);

  const refreshRecent = async () => {
    try {
      const [list, cap] = await Promise.all([api.listDownloads(), api.capacity()]);
      setRecent(list);
      setBusy(cap.busy);
    } catch {
      /* ignore — auth gate will redirect if needed */
    }
  };

  useEffect(() => {
    refreshRecent();
    const id = window.setInterval(refreshRecent, 3000);
    return () => window.clearInterval(id);
  }, []);

  const handleFetch = async (url: string) => {
    setLoading(true);
    setError(null);
    setMeta(null);
    try {
      const m = await api.metadata(url);
      setMeta(m);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to fetch metadata");
    } finally {
      setLoading(false);
    }
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
                <JobRow key={j.id} job={j} />
              ))}
            </div>
          )}
        </section>
      </div>
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
