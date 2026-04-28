"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="mx-auto max-w-5xl space-y-3 p-6">
        <div className="skeleton h-8 w-40" />
        <div className="skeleton h-32 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
