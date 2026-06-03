"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const navLinks = [
  { href: "/", label: "Start" },
  { href: "/shop", label: "Shop" },
  { href: "/kontakt", label: "Kontakt" },
];

export default function PublicHeader() {
  const [open, setOpen] = useState(false);
  const { firebaseUser } = useAuth();

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="font-bold text-xl text-brand-700">
          Inexxio
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6">
          {navLinks.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm font-medium text-gray-600 hover:text-brand-700 transition-colors"
            >
              {l.label}
            </Link>
          ))}
          {firebaseUser ? (
            <Link href="/app/dashboard" className="btn-primary text-sm py-1.5 px-4">
              ERP öffnen
            </Link>
          ) : (
            <Link href="/login" className="btn-primary text-sm py-1.5 px-4">
              Anmelden
            </Link>
          )}
        </nav>

        {/* Mobile menu toggle */}
        <button
          className="md:hidden p-2 text-gray-600"
          onClick={() => setOpen(!open)}
          aria-label="Menü"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile nav */}
      {open && (
        <div className="md:hidden border-t border-gray-100 bg-white px-4 py-4 space-y-3">
          {navLinks.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="block text-sm font-medium text-gray-700 py-2"
              onClick={() => setOpen(false)}
            >
              {l.label}
            </Link>
          ))}
          <Link
            href={firebaseUser ? "/app/dashboard" : "/login"}
            className="btn-primary block text-center text-sm"
            onClick={() => setOpen(false)}
          >
            {firebaseUser ? "ERP öffnen" : "Anmelden"}
          </Link>
        </div>
      )}
    </header>
  );
}
