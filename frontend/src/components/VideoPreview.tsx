"use client";

import type { Metadata } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

export function VideoPreview({ meta }: { meta: Metadata }) {
  return (
    <div className="card flex flex-col gap-4 p-4 sm:flex-row">
      {meta.thumbnail && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={meta.thumbnail}
          alt={meta.title}
          className="h-40 w-full max-w-xs flex-shrink-0 rounded-md object-cover sm:h-32"
        />
      )}
      <div className="space-y-2">
        <h2 className="text-lg font-semibold leading-tight">{meta.title}</h2>
        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          {meta.uploader && <span>{meta.uploader}</span>}
          <span>•</span>
          <span>{formatDuration(meta.duration)}</span>
        </div>
      </div>
    </div>
  );
}
