"use client";

import { useMemo, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import {
  api,
  ApiError,
  type DownloadRequest,
  type Metadata,
  type JobInfo,
} from "@/lib/api";
import { cn, formatBytes, formatDuration } from "@/lib/utils";

type Tab = "video" | "audio" | "clip";

const presets: Array<{
  id: NonNullable<DownloadRequest["preset"]>;
  label: string;
  desc: string;
}> = [
  { id: "best", label: "Best (4K)", desc: "Up to 2160p" },
  { id: "balanced", label: "Balanced (1080p)", desc: "Recommended" },
  { id: "saver", label: "Data Saver (480p)", desc: "Smallest file" },
];

const audioBitrates: Array<NonNullable<DownloadRequest["audio_bitrate"]>> = [
  "64",
  "128",
  "192",
  "320",
];

function pickEstimate(meta: Metadata, preset: NonNullable<DownloadRequest["preset"]>) {
  const cap = preset === "best" ? 2160 : preset === "balanced" ? 1080 : 480;
  let best: number | null = null;
  for (const f of meta.formats) {
    if (f.kind === "audio") continue;
    const h = parseInt(String(f.resolution ?? "").replace(/p$/, ""), 10);
    if (!h || h > cap) continue;
    const size = f.filesize ?? null;
    if (size && (!best || size > best)) best = size;
  }
  return best;
}

export function DownloadPanel({
  meta,
  onSubmitted,
}: {
  meta: Metadata;
  onSubmitted: (job: JobInfo) => void;
}) {
  const [tab, setTab] = useState<Tab>("video");
  const [preset, setPreset] = useState<NonNullable<DownloadRequest["preset"]>>("balanced");
  const [bitrate, setBitrate] = useState<NonNullable<DownloadRequest["audio_bitrate"]>>("192");
  const [start, setStart] = useState("0:00:00");
  const [end, setEnd] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const estimate = useMemo(() => pickEstimate(meta, preset), [meta, preset]);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const req: DownloadRequest = {
        url: meta.webpage_url,
        mode: tab,
        preset: tab === "audio" ? undefined : preset,
        audio_bitrate: tab === "audio" ? bitrate : undefined,
        container: tab === "audio" ? undefined : "mp4",
        start: tab === "clip" ? start : undefined,
        end: tab === "clip" ? end || undefined : undefined,
      };
      const job = await api.createDownload(req);
      onSubmitted(job);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError("Server is busy at full capacity — please wait for some time.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to start download");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const tabs: Tab[] = ["video", "audio", "clip"];
  return (
    <div className="card space-y-4 p-4">
      <div className="flex gap-1 rounded-md border border-border bg-muted/40 p-1 text-sm">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 capitalize transition",
              tab === t ? "bg-background shadow-sm font-medium" : "text-muted-foreground"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "video" && (
        <div className="grid gap-2 sm:grid-cols-3">
          {presets.map((p) => (
            <button
              key={p.id}
              onClick={() => setPreset(p.id)}
              className={cn(
                "rounded-md border p-3 text-left transition",
                preset === p.id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <div className="text-sm font-semibold">{p.label}</div>
              <div className="text-xs text-muted-foreground">{p.desc}</div>
            </button>
          ))}
        </div>
      )}

      {tab === "audio" && (
        <div className="grid grid-cols-4 gap-2">
          {audioBitrates.map((b) => (
            <button
              key={b}
              onClick={() => setBitrate(b)}
              className={cn(
                "rounded-md border px-3 py-2 text-sm transition",
                bitrate === b
                  ? "border-primary bg-primary/5 font-medium"
                  : "border-border hover:border-primary/50"
              )}
            >
              {b} kbps
            </button>
          ))}
        </div>
      )}

      {tab === "clip" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              Start (HH:MM:SS)
            </label>
            <input className="input" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              End (HH:MM:SS, optional)
            </label>
            <input className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="sm:col-span-2 grid gap-2 sm:grid-cols-3">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => setPreset(p.id)}
                className={cn(
                  "rounded-md border p-2 text-left text-sm transition",
                  preset === p.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
              >
                <div className="font-medium">{p.label}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {tab === "video" && (
            <>
              ~{formatBytes(estimate)} • duration {formatDuration(meta.duration)}
            </>
          )}
          {tab === "audio" && <>MP3 • duration {formatDuration(meta.duration)}</>}
          {tab === "clip" && <>Trimmed segment • container MP4</>}
        </span>
        <span className="badge">Format: {tab === "audio" ? "MP3" : "MP4"}</span>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      <button className="btn-primary w-full" onClick={submit} disabled={submitting}>
        {submitting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        Start download
      </button>
    </div>
  );
}
