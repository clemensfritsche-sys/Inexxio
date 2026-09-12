'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Cookie, Settings2, ShieldCheck, BarChart3, X } from 'lucide-react';
import {
  getConsent,
  hasDecided,
  acceptAll,
  acceptNecessaryOnly,
  saveConsent,
  OPEN_SETTINGS_EVENT,
} from '@/lib/consent';

/**
 * Cookie-/Einwilligungs-Banner + Einstellungs-Dialog.
 *
 * Erscheint beim ersten Besuch (nicht blockierend), respektiert die Wahl und lässt
 * sich jederzeit über den Footer-Link «Cookie-Einstellungen» erneut öffnen. Bewusst
 * schlank: EINE optionale Kategorie (Statistik), «Ablehnen» ist so einfach wie
 * «Akzeptieren» (gleichwertige Buttons, keine Dark Patterns).
 */
export function CookieConsent() {
  const [showBanner, setShowBanner] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [analytics, setAnalytics] = useState(false);

  useEffect(() => {
    setShowBanner(!hasDecided());
    const openSettings = () => {
      setAnalytics(getConsent()?.analytics ?? false);
      setShowSettings(true);
    };
    window.addEventListener(OPEN_SETTINGS_EVENT, openSettings);
    return () => window.removeEventListener(OPEN_SETTINGS_EVENT, openSettings);
  }, []);

  useEffect(() => {
    if (!showSettings) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowSettings(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showSettings]);

  function handleAcceptAll() {
    acceptAll();
    setShowBanner(false);
    setShowSettings(false);
  }

  function handleNecessary() {
    acceptNecessaryOnly();
    setShowBanner(false);
    setShowSettings(false);
  }

  function handleSaveSelection() {
    saveConsent(analytics);
    setShowBanner(false);
    setShowSettings(false);
  }

  function openSettingsFromBanner() {
    setAnalytics(getConsent()?.analytics ?? false);
    setShowSettings(true);
  }

  if (!showBanner && !showSettings) return null;

  return (
    <>
      {/* ── Banner ── */}
      {showBanner && !showSettings && (
        <div style={bannerWrap} role="region" aria-label="Cookie-Hinweis">
          <div style={bannerCard}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={iconBadge}>
                <Cookie style={{ width: 20, height: 20, color: 'var(--inexxio-red)' }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h2 style={bannerTitle}>Datenschutz &amp; Cookies</h2>
                <p style={bannerText}>
                  Wir setzen nur technisch notwendige Cookies für Anmeldung und Warenkorb. Optional
                  hilft uns cookielose Statistik, die Website zu verbessern. Details in der{' '}
                  <Link href="/datenschutz" style={linkStyle}>Datenschutzerklärung</Link>.
                </p>
              </div>
            </div>
            <div style={bannerActions}>
              <button onClick={openSettingsFromBanner} style={ghostBtn} type="button">
                <Settings2 style={{ width: 15, height: 15 }} />
                Einstellungen
              </button>
              <button onClick={handleNecessary} style={secondaryBtn} type="button">
                Nur notwendige
              </button>
              <button onClick={handleAcceptAll} style={primaryBtn} type="button">
                Alle akzeptieren
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Einstellungs-Dialog ── */}
      {showSettings && (
        <div style={overlay} onClick={() => setShowSettings(false)}>
          <div
            style={dialogCard}
            role="dialog"
            aria-modal="true"
            aria-label="Cookie-Einstellungen"
            onClick={(e) => e.stopPropagation()}
          >
            <div style={dialogHeader}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Cookie style={{ width: 18, height: 18, color: 'var(--inexxio-red)' }} />
                <h2 style={dialogTitle}>Cookie-Einstellungen</h2>
              </div>
              <button onClick={() => setShowSettings(false)} aria-label="Schliessen" style={closeBtn} type="button">
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            <div style={{ padding: '8px 24px 4px' }}>
              <p style={{ font: 'var(--body-sm)', color: 'var(--fg-3)', margin: '4px 0 16px', lineHeight: 1.6 }}>
                Sie entscheiden, was wir verwenden dürfen. Ihre Wahl können Sie jederzeit hier ändern.
              </p>

              <CategoryRow
                icon={<ShieldCheck style={{ width: 18, height: 18, color: 'var(--success)' }} />}
                title="Notwendig"
                description="Anmeldung (Session), Warenkorb und das Speichern dieser Einwilligung. Ohne diese funktioniert die Website nicht – daher immer aktiv."
                locked
                checked
              />
              <CategoryRow
                icon={<BarChart3 style={{ width: 18, height: 18, color: 'var(--accent)' }} />}
                title="Statistik"
                description="Anonyme Reichweitenmessung mit Plausible Analytics – ohne Cookies, ohne personenbezogene Daten. Hilft uns, die Website zu verbessern."
                checked={analytics}
                onChange={setAnalytics}
              />
            </div>

            <div style={dialogFooter}>
              <button onClick={handleSaveSelection} style={secondaryBtn} type="button">
                Auswahl speichern
              </button>
              <button onClick={handleAcceptAll} style={primaryBtn} type="button">
                Alle akzeptieren
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Kategorie-Zeile mit Toggle ─────────────────────────────────────────────────

function CategoryRow({
  icon, title, description, checked, locked, onChange,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  checked: boolean;
  locked?: boolean;
  onChange?: (v: boolean) => void;
}) {
  return (
    <div style={categoryRow}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 34, height: 34, borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', flexShrink: 0 }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ font: '600 14px var(--font-body)', color: 'var(--fg-1)' }}>{title}</span>
          {locked && <span style={lockedPill}>Immer aktiv</span>}
        </div>
        <p style={{ font: 'var(--caption)', color: 'var(--fg-3)', margin: '3px 0 0', lineHeight: 1.55 }}>
          {description}
        </p>
      </div>
      <Toggle checked={checked} disabled={locked} onChange={onChange} />
    </div>
  );
}

function Toggle({ checked, disabled, onChange }: { checked: boolean; disabled?: boolean; onChange?: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      style={{
        position: 'relative', width: 42, height: 24, borderRadius: 999, border: 'none',
        background: checked ? 'var(--inexxio-red)' : 'var(--bg-4)',
        cursor: disabled ? 'default' : 'pointer', flexShrink: 0, transition: 'background 0.18s',
        opacity: disabled ? 0.7 : 1,
      }}
    >
      <span
        style={{
          position: 'absolute', top: 2, left: checked ? 20 : 2, width: 20, height: 20,
          borderRadius: '50%', background: '#fff', boxShadow: 'var(--shadow-sm)', transition: 'left 0.18s',
        }}
      />
    </button>
  );
}

// ─── Styles (Design-Tokens) ─────────────────────────────────────────────────────

const bannerWrap: React.CSSProperties = {
  position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 9998,
  display: 'flex', justifyContent: 'center', padding: 16, pointerEvents: 'none',
};
const bannerCard: React.CSSProperties = {
  pointerEvents: 'auto', width: '100%', maxWidth: 640, background: 'var(--bg-1)',
  border: '1px solid var(--border-2)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)',
  padding: 20, display: 'flex', flexDirection: 'column', gap: 16,
};
const iconBadge: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 40,
  borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', flexShrink: 0,
};
const bannerTitle: React.CSSProperties = { font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 };
const bannerText: React.CSSProperties = { font: 'var(--body-sm)', color: 'var(--fg-2)', margin: '4px 0 0', lineHeight: 1.6 };
const linkStyle: React.CSSProperties = { color: 'var(--inexxio-red)', textDecoration: 'underline', textUnderlineOffset: 2 };
const bannerActions: React.CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'flex-end' };

const baseBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  padding: '9px 16px', borderRadius: 'var(--r-sm)', font: '600 13px var(--font-body)',
  cursor: 'pointer', minHeight: 40,
};
const primaryBtn: React.CSSProperties = { ...baseBtn, border: 'none', background: 'var(--inexxio-red)', color: '#fff' };
const secondaryBtn: React.CSSProperties = { ...baseBtn, border: '1px solid var(--border-2)', background: 'var(--bg-1)', color: 'var(--fg-1)' };
const ghostBtn: React.CSSProperties = { ...baseBtn, border: '1px solid transparent', background: 'transparent', color: 'var(--fg-3)' };

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(10,10,11,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
const dialogCard: React.CSSProperties = {
  width: '100%', maxWidth: 500, background: 'var(--bg-1)', borderRadius: 'var(--r-lg)',
  boxShadow: 'var(--shadow-xl)', overflow: 'hidden', maxHeight: '90vh', display: 'flex', flexDirection: 'column',
};
const dialogHeader: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '18px 24px', borderBottom: '1px solid var(--border-1)',
};
const dialogTitle: React.CSSProperties = { font: '700 16px var(--font-display)', color: 'var(--fg-1)', margin: 0 };
const closeBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32,
  borderRadius: 'var(--r-sm)', border: 'none', background: 'transparent', color: 'var(--fg-3)', cursor: 'pointer',
};
const dialogFooter: React.CSSProperties = {
  display: 'flex', gap: 10, justifyContent: 'flex-end', padding: '16px 24px',
  borderTop: '1px solid var(--border-1)', marginTop: 8,
};
const categoryRow: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 0', borderTop: '1px solid var(--border-1)',
};
const lockedPill: React.CSSProperties = {
  font: '600 10px var(--font-body)', letterSpacing: '0.04em', textTransform: 'uppercase',
  color: 'var(--success)', background: 'var(--success-bg)', padding: '2px 8px', borderRadius: 999,
};
