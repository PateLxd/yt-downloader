"use client";

import { useState } from "react";
import { CheckCircle2, Clock, Download, KeyRound, Loader2, XCircle } from "lucide-react";
import { api, type JobInfo } from "@/lib/api";
import { cn, formatBytes } from "@/lib/utils";

const statusColor: Record<JobInfo["status"], string> = {
  queued: "text-amber-600",
  downloading: "text-primary",
  completed: "text-emerald-600",
  failed: "text-red-600",
};

const StatusIcon = ({ status }: { status: JobInfo["status"] }) => {
  if (status === "queued") return <Clock className="h-4 w-4" />;
  if (status === "downloading") return <Loader2 className="h-4 w-4 animate-spin" />;
  if (status === "completed") return <CheckCircle2 className="h-4 w-4" />;
  return <XCircle className="h-4 w-4" />;
};

export function JobRow({
  job,
  onCookiesNeeded,
}: {
  job: JobInfo;
  onCookiesNeeded?: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const handleDownload = async () => {
    setDownloading(true);
    try {
      // Suggested filename uses the YouTube title (with the same extension
      // as the on-disk file). The backend also sets Content-Disposition for
      // direct fetches, but the <a download> attribute on a Blob URL takes
      // precedence here so we have to send the title from the client too.
      const ext = job.filename?.includes(".")
        ? job.filename.slice(job.filename.lastIndexOf("."))
        : "";
      const base = (job.title ?? job.id).replace(/[\x00-\x1f\x7f<>:"/\\|?*]/g, "").trim();
      const suggested = `${base.slice(0, 150) || job.id}${ext}`;
      await api.downloadFile(job.id, suggested);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="truncate text-sm font-medium">
            {job.title ?? job.id}{" "}
            <span className="text-xs text-muted-foreground">({job.mode})</span>
          </div>
          <div className={cn("flex items-center gap-1 text-xs", statusColor[job.status])}>
            <StatusIcon status={job.status} />
            <span className="capitalize">{job.status}</span>
            {job.status === "downloading" && (
              <span className="text-muted-foreground">
                • {job.progress.toFixed(0)}% {job.speed ? `• ${job.speed}` : ""}{" "}
                {job.eta ? `• ETA ${job.eta}` : ""}
              </span>
            )}
            {job.status === "completed" && (
              <span className="text-muted-foreground">• {formatBytes(job.size_bytes)}</span>
            )}
            {job.status === "failed" && job.error && (
              <span className="truncate text-muted-foreground">• {job.error}</span>
            )}
          </div>
          {(job.status === "downloading" || job.status === "queued") && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${Math.max(2, job.progress)}%` }}
              />
            </div>
          )}
        </div>

        {job.status === "completed" && (
          <button className="btn-secondary" onClick={handleDownload} disabled={downloading}>
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Save
          </button>
        )}

        {job.status === "failed" && job.error_code === "cookies_required" && onCookiesNeeded && (
          <button className="btn-secondary" onClick={onCookiesNeeded}>
            <KeyRound className="h-4 w-4" />
            Update cookies
          </button>
        )}
      </div>
    </div>
  );
}
