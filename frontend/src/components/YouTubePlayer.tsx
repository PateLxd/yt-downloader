"use client";

import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";

// Minimal subset of the YouTube IFrame API we touch. Typed loosely on
// purpose so we don't have to ship a full @types/youtube definition.
type YTPlayer = {
  getCurrentTime: () => number;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  destroy: () => void;
};

type YTApi = {
  Player: new (
    el: HTMLElement,
    opts: {
      videoId?: string;
      playerVars?: Record<string, number | string>;
      events?: Record<string, (e: unknown) => void>;
    }
  ) => YTPlayer;
};

declare global {
  interface Window {
    YT?: YTApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}

// One-shot loader for the IFrame API script. Subsequent components share
// the same promise.
let ytApiPromise: Promise<YTApi> | null = null;

function loadYouTubeApi(): Promise<YTApi> {
  if (typeof window === "undefined") return Promise.reject(new Error("ssr"));
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (ytApiPromise) return ytApiPromise;

  ytApiPromise = new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      if (window.YT) resolve(window.YT);
    };
    if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
      const tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      tag.async = true;
      document.body.appendChild(tag);
    }
  });
  return ytApiPromise;
}

export type YouTubePlayerHandle = {
  getCurrentTime: () => number;
  seekTo: (seconds: number) => void;
};

type Props = {
  videoId: string;
  className?: string;
};

export const YouTubePlayer = forwardRef<YouTubePlayerHandle, Props>(function YouTubePlayer(
  { videoId, className },
  ref
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<YTPlayer | null>(null);

  useImperativeHandle(
    ref,
    () => ({
      getCurrentTime: () => {
        try {
          return playerRef.current?.getCurrentTime?.() ?? 0;
        } catch {
          return 0;
        }
      },
      seekTo: (seconds: number) => {
        try {
          playerRef.current?.seekTo?.(seconds, true);
        } catch {
          /* player not ready */
        }
      },
    }),
    []
  );

  useEffect(() => {
    let cancelled = false;
    loadYouTubeApi().then((YT) => {
      if (cancelled || !containerRef.current) return;
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* noop */
      }
      playerRef.current = new YT.Player(containerRef.current, {
        videoId,
        playerVars: {
          rel: 0,
          modestbranding: 1,
          playsinline: 1,
        },
      });
    });
    return () => {
      cancelled = true;
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* noop */
      }
      playerRef.current = null;
    };
  }, [videoId]);

  return (
    <div className={className}>
      <div className="aspect-video w-full overflow-hidden rounded-md bg-black">
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
});
