'use client';

import type { ReactNode } from 'react';
import { ArrowLeft, X } from 'lucide-react';

/** Kopf des Blatts: links zurück oder nichts, Titel, rechts schliessen – ohne `onClose` (eine
 *  Aufnahme läuft) steht dort nichts, der Platz bleibt. */
export function SheetHead({ title, onBack, onClose }: { title: ReactNode; onBack?: () => void; onClose?: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 12px 10px 16px',
      borderBottom: '1px solid var(--border-1)' }}>
      {onBack && (
        <button type="button" onClick={onBack} aria-label="Zurück" className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
          style={{ height: 40, ['--actbtn-w' as string]: '40px', marginLeft: -4 }}>
          <ArrowLeft size={18} />
        </button>
      )}
      <h2 style={{ flex: 1, margin: 0, font: '700 16px var(--font-display)', color: 'var(--fg-1)',
        display: 'flex', alignItems: 'center', gap: 8 }}>{title}</h2>
      {onClose ? (
        <button type="button" onClick={onClose} aria-label="Schliessen" className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
          style={{ height: 40, ['--actbtn-w' as string]: '40px' }}>
          <X size={18} />
        </button>
      ) : <span aria-hidden style={{ width: 40, height: 40, flex: 'none' }} />}
    </div>
  );
}
