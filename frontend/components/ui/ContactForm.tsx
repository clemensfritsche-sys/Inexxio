"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  name: z.string().min(2, "Name muss mindestens 2 Zeichen haben"),
  email: z.string().email("Gültige E-Mail-Adresse eingeben"),
  message: z.string().min(10, "Nachricht muss mindestens 10 Zeichen haben"),
});

type FormData = z.infer<typeof schema>;

type Status = "idle" | "loading" | "success" | "error";

export default function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    setStatus("loading");
    try {
      const res = await fetch("/api/v1/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error();
      setStatus("success");
      reset();
    } catch {
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
        <p className="text-green-800 font-medium">Nachricht gesendet!</p>
        <p className="text-green-700 text-sm mt-1">
          Wir melden uns in Kürze bei Ihnen.
        </p>
        <button
          onClick={() => setStatus("idle")}
          className="mt-4 btn-secondary text-sm"
        >
          Neue Nachricht
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <div>
        <label className="label" htmlFor="name">Name *</label>
        <input
          id="name"
          {...register("name")}
          className="input"
          placeholder="Max Muster"
          autoComplete="name"
        />
        {errors.name && (
          <p className="text-red-600 text-xs mt-1">{errors.name.message}</p>
        )}
      </div>

      <div>
        <label className="label" htmlFor="email">E-Mail *</label>
        <input
          id="email"
          type="email"
          {...register("email")}
          className="input"
          placeholder="max@beispiel.ch"
          autoComplete="email"
        />
        {errors.email && (
          <p className="text-red-600 text-xs mt-1">{errors.email.message}</p>
        )}
      </div>

      <div>
        <label className="label" htmlFor="message">Nachricht *</label>
        <textarea
          id="message"
          {...register("message")}
          rows={5}
          className="input resize-none"
          placeholder="Wie können wir Ihnen helfen?"
        />
        {errors.message && (
          <p className="text-red-600 text-xs mt-1">{errors.message.message}</p>
        )}
      </div>

      {status === "error" && (
        <p className="text-red-600 text-sm">
          Fehler beim Senden. Bitte versuchen Sie es erneut.
        </p>
      )}

      <button
        type="submit"
        disabled={status === "loading"}
        className="btn-primary w-full"
      >
        {status === "loading" ? "Wird gesendet..." : "Nachricht senden"}
      </button>

      <p className="text-xs text-gray-500">
        Mit dem Absenden akzeptieren Sie unsere{" "}
        <a href="/datenschutz" className="text-brand-600 hover:underline">
          Datenschutzerklärung
        </a>
        .
      </p>
    </form>
  );
}
