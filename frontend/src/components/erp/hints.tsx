'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, Info } from 'lucide-react';

// ►►► **Was erklärt oder meldet** – Hover-Blase (`Tooltip`), ⓘ (`InfoHint`), Fehlerzeile
// (`ErrorText`). Erklärungen gehören in den Hover, nicht in die Fläche. ◄◄◄

// ─── Hover-Hilfen: Erklärungen/Infotexte gehören in den Hover, nicht in die Fläche ──

/** Leichter Hover-/Fokus-Tooltip (dunkle Sprechblase). Trägt erklärende Texte, ohne
 *  die Oberfläche zu fluten – «weniger ist mehr». */
export function Tooltip({ text, children, side = 'top' }: {
  text: string; children: ReactNode; side?: 'top' | 'bottom';
}) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)} onBlur={() => setShow(false)}>
      {children}
      {show && (
        <span role="tooltip" style={{
          position: 'absolute', zIndex: 50, left: '50%', transform: 'translateX(-50%)',
          ...(side === 'top' ? { bottom: '100%', marginBottom: 7 } : { top: '100%', marginTop: 7 }),
          padding: '7px 10px', borderRadius: 7, background: 'var(--bg-dark)', color: 'var(--fg-on-dark)',
          fontSize: 11, fontWeight: 500, lineHeight: 1.4, width: 'max-content', maxWidth: 240,
          textAlign: 'left', whiteSpace: 'normal', boxShadow: '0 6px 18px rgba(0,0,0,0.22)', pointerEvents: 'none',
        }}>{text}</span>
      )}
    </span>
  );
}

/** Dezentes ⓘ-Symbol; die Erklärung erscheint im Hover. Ersetzt Infotext-Blöcke. */
export function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <Info size={13} style={{ color: 'var(--fg-4)', cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  );
}

export function ErrorText({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: 'var(--danger)' }}>
      <AlertCircle size={11} /> {msg}
    </div>
  );
}
