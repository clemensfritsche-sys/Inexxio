"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function VerifyPage() {
  const { completeMagicLink } = useAuth();
  const router = useRouter();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");

  useEffect(() => {
    completeMagicLink()
      .then((ok) => {
        if (ok) {
          router.replace("/app/dashboard");
        } else {
          setStatus("error");
        }
      })
      .catch(() => setStatus("error"));
  }, [completeMagicLink, router]);

  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card p-8 text-center max-w-sm">
          <div className="text-4xl mb-4">❌</div>
          <h2 className="font-semibold text-gray-900 mb-2">Link ungültig</h2>
          <p className="text-sm text-gray-600 mb-4">
            Der Link ist abgelaufen oder wurde bereits verwendet.
          </p>
          <a href="/login" className="btn-primary block">
            Neuen Link anfordern
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card p-8 text-center max-w-sm">
        <div className="text-4xl mb-4 animate-pulse">🔑</div>
        <h2 className="font-semibold text-gray-900 mb-2">Wird verifiziert...</h2>
        <p className="text-sm text-gray-500">Einen Moment bitte.</p>
      </div>
    </div>
  );
}
