'use client';

import { openCookieSettings } from '@/lib/consent';

/**
 * Footer-Link, der den Cookie-Einstellungs-Dialog erneut öffnet – Pflicht für einen
 * jederzeit widerrufbaren/änderbaren Einwilligungs-Status (DSGVO/CH DSG).
 */
export function CookieSettingsLink({ className }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={openCookieSettings}
      className={className}
      style={{
        font: 'var(--body-sm)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none',
        background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
      }}
    >
      Cookie-Einstellungen
    </button>
  );
}

/** Inline-Text-Button für helle Flächen (z. B. in der Datenschutzerklärung). */
export function CookieSettingsButton({ label = 'Cookie-Einstellungen öffnen' }: { label?: string }) {
  return (
    <button
      type="button"
      onClick={openCookieSettings}
      className="font-medium text-inexxio underline underline-offset-2"
      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
    >
      {label}
    </button>
  );
}
