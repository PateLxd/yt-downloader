"use client";

import { useMemo, useRef, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import {
  api,
  ApiError,
  type DownloadRequest,
  type Format,
  type Metadata,
  type JobInfo,
} from "@/lib/api";
import { cn, formatBytes, formatDuration } from "@/lib/utils";
import { YouTubePlayer, type YouTubePlayerHandle } from "./YouTubePlayer";

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

function sortVideoFormats(formats: Format[]): Format[] {
  return [...formats]
    .filter((f) => f.kind !== "audio")
    .sort((a, b) => {
      const ha = parseInt(String(a.resolution ?? "").replace(/p$/, ""), 10) || 0;
      const hb = parseInt(String(b.resolution ?? "").replace(/p$/, ""), 10) || 0;
      if (hb !== ha) return hb - ha;
      const fa = a.fps ?? 0;
      const fb = b.fps ?? 0;
      if (fb !== fa) return fb - fa;
      return (b.filesize ?? 0) - (a.filesize ?? 0);
    });
}

function describeFormat(f: Format): string {
  const parts: string[] = [];
  parts.push(`${f.resolution ?? "?"}${f.fps && f.fps > 30 ? `${Math.round(f.fps)}` : ""}`);
  parts.push(f.ext);
  if (f.kind === "video") parts.push("video-only");
  if (f.vcodec && f.vcodec !== "none") {
    const codec = f.vcodec.split(".")[0];
    parts.push(codec);
  }
  if (f.tbr) parts.push(`${Math.round(f.tbr)} kbps`);
  return parts.filter(Boolean).join(" · ");
}

function parseTime(input: string): number | null {
  const s = input.trim();
  if (!s) return null;
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  const parts = s.split(":").map((p) => parseFloat(p));
  if (parts.some(Number.isNaN)) return null;
  let secs = 0;
  for (const p of parts) secs = secs * 60 + p;
  return secs;
}

function formatTime(seconds: number): string {
  const t = Math.max(0, Math.floor(seconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// Pull the YouTube video ID out of a webpage URL. Returns null for non-YouTube
// URLs so the clip tab can fall back to numeric inputs only.
function extractYouTubeId(url: string): string | null {
  try {
    const u = new URL(url);
    if (u.hostname === "youtu.be") return u.pathname.slice(1) || null;
    if (u.hostname.endsWith("youtube.com")) {
      if (u.pathname === "/watch") return u.searchParams.get("v");
      const m = u.pathname.match(/^\/(?:embed|shorts|live)\/([^/?#]+)/);
      if (m) return m[1];
    }
  } catch {
    /* invalid url */
  }
  return null;
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
  const [formatId, setFormatId] = useState<string | "">("");
  const [bitrate, setBitrate] = useState<NonNullable<DownloadRequest["audio_bitrate"]>>("192");
  const [start, setStart] = useState("0:00:00");
  const [end, setEnd] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const videoFormats = useMemo(() => sortVideoFormats(meta.formats), [meta.formats]);
  const youTubeId = useMemo(() => extractYouTubeId(meta.webpage_url), [meta.webpage_url]);
  const playerRef = useRef<YouTubePlayerHandle | null>(null);

  const selectedFormat = useMemo(
    () => meta.formats.find((f) => f.format_id === formatId) ?? null,
    [meta.formats, formatId]
  );

  const estimate = useMemo(
    () => (selectedFormat?.filesize ?? pickEstimate(meta, preset)),
    [meta, preset, selectedFormat]
  );

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const req: DownloadRequest = {
        url: meta.webpage_url,
        mode: tab,
        preset: tab === "audio" ? undefined : formatId ? "custom" : preset,
        format_id: tab === "audio" ? undefined : formatId || undefined,
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

  const setFromPlayer = (which: "start" | "end") => {
    const t = playerRef.current?.getCurrentTime();
    if (typeof t !== "number") return;
    const formatted = formatTime(t);
    if (which === "start") setStart(formatted);
    else setEnd(formatted);
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
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPreset(p.id);
                  setFormatId("");
                }}
                className={cn(
                  "rounded-md border p-3 text-left transition",
                  preset === p.id && !formatId
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
              >
                <div className="text-sm font-semibold">{p.label}</div>
                <div className="text-xs text-muted-foreground">{p.desc}</div>
              </button>
            ))}
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              Or pick an exact format
            </label>
            <select
              className="input w-full"
              value={formatId}
              onChange={(e) => setFormatId(e.target.value)}
            >
              <option value="">— use preset above —</option>
              {videoFormats.map((f) => (
                <option key={f.format_id} value={f.format_id}>
                  {describeFormat(f)} · {formatBytes(f.filesize)}
                </option>
              ))}
            </select>
            {selectedFormat && (
              <p className="text-xs text-muted-foreground">
                Selected: {describeFormat(selectedFormat)} · {formatBytes(selectedFormat.filesize)}
                {selectedFormat.kind === "video" && " (will be muxed with best audio)"}
              </p>
            )}
          </div>
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
        <div className="space-y-3">
          {youTubeId ? (
            <>
              <YouTubePlayer ref={playerRef} videoId={youTubeId} />
              <p className="text-xs text-muted-foreground">
                Use the player&apos;s seek bar to find your start/end, then tap the buttons below.
              </p>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              Inline preview is only available for YouTube URLs. Enter timestamps manually below.
            </p>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-muted-foreground">
                  Start (HH:MM:SS)
                </label>
                {youTubeId && (
                  <button
                    type="button"
                    onClick={() => setFromPlayer("start")}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Use current ▾
                  </button>
                )}
              </div>
              <input className="input" value={start} onChange={(e) => setStart(e.target.value)} />
              {youTubeId && (
                <button
                  type="button"
                  onClick={() => {
                    const t = parseTime(start);
                    if (t !== null) playerRef.current?.seekTo(t);
                  }}
                  className="text-xs text-muted-foreground hover:text-primary hover:underline"
                >
                  Seek player to start
                </button>
              )}
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-muted-foreground">
                  End (HH:MM:SS, optional)
                </label>
                {youTubeId && (
                  <button
                    type="button"
                    onClick={() => setFromPlayer("end")}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Use current ▾
                  </button>
                )}
              </div>
              <input className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
              {youTubeId && (
                <button
                  type="button"
                  onClick={() => {
                    const t = parseTime(end);
                    if (t !== null) playerRef.current?.seekTo(t);
                  }}
                  className="text-xs text-muted-foreground hover:text-primary hover:underline"
                >
                  Seek player to end
                </button>
              )}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPreset(p.id);
                  setFormatId("");
                }}
                className={cn(
                  "rounded-md border p-2 text-left text-sm transition",
                  preset === p.id && !formatId
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
