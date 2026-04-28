"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
const TOKEN_KEY = "ytdl_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* noop */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type Format = {
  format_id: string;
  ext: string;
  resolution?: string | null;
  fps?: number | null;
  vcodec?: string | null;
  acodec?: string | null;
  filesize?: number | null;
  tbr?: number | null;
  abr?: number | null;
  note?: string | null;
  kind: "video" | "audio" | "muxed";
};

export type Metadata = {
  id: string;
  title: string;
  uploader?: string | null;
  duration?: number | null;
  thumbnail?: string | null;
  webpage_url: string;
  formats: Format[];
};

export type JobInfo = {
  id: string;
  status: "queued" | "downloading" | "completed" | "failed";
  progress: number;
  speed?: string | null;
  eta?: string | null;
  title?: string | null;
  filename?: string | null;
  size_bytes?: number | null;
  error?: string | null;
  mode?: "video" | "audio" | "clip" | null;
  created_at?: number | null;
  finished_at?: number | null;
};

export type DownloadRequest = {
  url: string;
  mode: "video" | "audio" | "clip";
  preset?: "best" | "balanced" | "saver" | "custom";
  max_height?: number | null;
  container?: "mp4" | "mkv" | "webm";
  format_id?: string | null;
  audio_bitrate?: "64" | "128" | "192" | "320";
  start?: string;
  end?: string;
};

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  metadata: (url: string) =>
    request<Metadata>("/metadata", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  capacity: () =>
    request<{ busy: boolean; active_jobs: number; max_jobs: number; message?: string | null }>(
      "/capacity"
    ),
  createDownload: (req: DownloadRequest) =>
    request<JobInfo>("/downloads", { method: "POST", body: JSON.stringify(req) }),
  listDownloads: () => request<JobInfo[]>("/downloads"),
  getJob: (id: string) => request<JobInfo>(`/downloads/${id}`),
  downloadFile: async (id: string, suggestedName: string) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/downloads/${id}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestedName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  },
};

export { API_BASE };
