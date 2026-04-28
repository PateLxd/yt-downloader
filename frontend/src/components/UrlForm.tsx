"use client";

import { useState } from "react";
import { Loader2, Search } from "lucide-react";

export function UrlForm({
  loading,
  onSubmit,
}: {
  loading: boolean;
  onSubmit: (url: string) => void;
}) {
  const [url, setUrl] = useState("");
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (url.trim()) onSubmit(url.trim());
      }}
    >
      <input
        className="input"
        placeholder="Paste a YouTube URL…"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <button className="btn-primary" disabled={loading || !url.trim()}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        Fetch
      </button>
    </form>
  );
}
