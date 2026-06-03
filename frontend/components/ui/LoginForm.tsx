"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";

const schema = z.object({
  email: z.string().email("Gültige E-Mail-Adresse eingeben"),
});
type FormData = z.infer<typeof schema>;

type Step = "idle" | "loading" | "sent" | "error";

export default function LoginForm() {
  const { sendMagicLink, signInWithGoogle } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<Step>("idle");
  const [googleLoading, setGoogleLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    setStep("loading");
    setErrorMsg("");
    try {
      await sendMagicLink(data.email);
      setStep("sent");
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Fehler beim Senden. Bitte erneut versuchen."
      );
      setStep("error");
    }
  }

  async function handleGoogle() {
    setGoogleLoading(true);
    setErrorMsg("");
    try {
      await signInWithGoogle();
      router.push("/app/dashboard");
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Google Anmeldung fehlgeschlagen."
      );
      setGoogleLoading(false);
    }
  }

  if (step === "sent") {
    return (
      <div className="card p-6 text-center">
        <div className="text-4xl mb-4">✉️</div>
        <h2 className="font-semibold text-gray-900 mb-2">Link gesendet!</h2>
        <p className="text-sm text-gray-600 mb-1">
          Wir haben einen Anmelde-Link an
        </p>
        <p className="font-medium text-gray-900 mb-4">{getValues("email")}</p>
        <p className="text-xs text-gray-400">
          Der Link ist 15 Minuten gültig. Bitte überprüfen Sie auch Ihren
          Spam-Ordner.
        </p>
        <button
          onClick={() => setStep("idle")}
          className="btn-ghost text-sm mt-4"
        >
          Andere E-Mail verwenden
        </button>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-6 text-center">
        Anmelden
      </h2>

      {/* Google Sign-In */}
      <button
        onClick={handleGoogle}
        disabled={googleLoading}
        className="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-lg px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 mb-4"
      >
        <GoogleIcon />
        {googleLoading ? "Wird verbunden..." : "Mit Google anmelden"}
      </button>

      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-gray-400">oder</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Magic Link */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">
            E-Mail-Adresse
          </label>
          <input
            id="email"
            type="email"
            {...register("email")}
            className="input"
            placeholder="name@beispiel.ch"
            autoComplete="email"
            autoFocus
          />
          {errors.email && (
            <p className="text-red-600 text-xs mt-1">{errors.email.message}</p>
          )}
        </div>

        {(step === "error" || errorMsg) && (
          <p className="text-red-600 text-xs bg-red-50 rounded-lg px-3 py-2">
            {errorMsg}
          </p>
        )}

        <button
          type="submit"
          disabled={step === "loading"}
          className="btn-primary w-full"
        >
          {step === "loading" ? "Wird gesendet..." : "Magic Link senden"}
        </button>
      </form>

      <p className="text-xs text-gray-400 text-center mt-4">
        Sie erhalten einen einmaligen Link per E-Mail – kein Passwort nötig.
      </p>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path
        d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
        fill="#4285F4"
      />
      <path
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"
        fill="#34A853"
      />
      <path
        d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
        fill="#FBBC05"
      />
      <path
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
        fill="#EA4335"
      />
    </svg>
  );
}
