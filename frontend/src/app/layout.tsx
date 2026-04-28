import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YT Downloader",
  description: "Private YouTube downloader powered by yt-dlp + Valkey queue",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
