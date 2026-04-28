"use client";

import { useEffect, useState } from "react";
import { api, type JobInfo } from "@/lib/api";
import { AuthGate } from "@/components/AuthGate";
import { Topbar } from "@/components/Topbar";
import { JobRow } from "@/components/JobRow";

function QueueInner() {
  const [jobs, setJobs] = useState<JobInfo[] | null>(null);
  const [capacity, setCapacity] = useState<{ active_jobs: number; max_jobs: number; busy: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [list, cap] = await Promise.all([api.listDownloads(), api.capacity()]);
        if (cancelled) return;
        setJobs(list);
        setCapacity(cap);
      } catch {
        /* noop */
      }
    };
    tick();
    const id = window.setInterval(tick, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <main className="min-h-dvh bg-muted/30">
      <Topbar />
      <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Queue</h1>
          {capacity && (
            <span className="badge">
              {capacity.active_jobs}/{capacity.max_jobs} active
            </span>
          )}
        </header>
        {capacity?.busy && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Please wait for some time — server is at full capacity.
          </div>
        )}
        {jobs === null && (
          <div className="space-y-2">
            <div className="skeleton h-16 w-full" />
            <div className="skeleton h-16 w-full" />
          </div>
        )}
        {jobs && jobs.length === 0 && (
          <p className="text-sm text-muted-foreground">No jobs.</p>
        )}
        {jobs && jobs.length > 0 && (
          <div className="space-y-2">
            {jobs.map((j) => (
              <JobRow key={j.id} job={j} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

export default function QueuePage() {
  return (
    <AuthGate>
      <QueueInner />
    </AuthGate>
  );
}
