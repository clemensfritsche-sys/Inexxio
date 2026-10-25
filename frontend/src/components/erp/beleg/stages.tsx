'use client';

import { Fragment } from 'react';
import { Check } from 'lucide-react';
import type { Filled } from './shared';

/**
 * **Der Weg oben auf der Karte – vier Stationen** (`VoucherEmbed.stages`): Offerte bzw.
 * Anfrage · Zusage · Rechnung bzw. Gutschrift · Erledigt. Erreichtes trägt einen Haken,
 * die aktuelle Station ist gefüllt, eine Linie verbindet sie. Die Wörter kommen vom
 * Server; ein Storno ist keine Station (keine ist dann aktiv).
 */
export function Stages({ d }: { d: Filled }) {
  if (!d.stages.length) return null;
  return (
    <div className="flex items-center" role="list" aria-label="Stationen" style={{
      padding: '6px 0 18px', marginBottom: 24, borderBottom: '1px solid var(--border-1)',
      minWidth: 0,
    }}>
      {d.stages.map((s, i) => (
        <Fragment key={s.key}>
          {i > 0 && (
            <span aria-hidden style={{
              flex: '1 1 auto', height: 1.5, margin: '0 10px', minWidth: 8,
              background: s.done || s.active ? 'var(--fg-1)' : 'var(--border-1)',
            }} />
          )}
          <Station index={i + 1} label={s.label} done={s.done} active={s.active} />
        </Fragment>
      ))}
    </div>
  );
}

function Station({ index, label, done, active }: {
  index: number; label: string; done: boolean; active: boolean;
}) {
  return (
    <span role="listitem" className="flex items-center" style={{
      gap: 8, flex: 'none', fontSize: 12.5,
      color: active ? 'var(--fg-1)' : 'var(--fg-3)', fontWeight: active ? 600 : 400,
    }} {...(active ? { 'aria-current': 'step' as const } : {})}>
      <i aria-hidden style={{
        width: 22, height: 22, borderRadius: '50%', display: 'grid', placeItems: 'center',
        font: '600 11.5px var(--font-body)', fontStyle: 'normal',
        border: `1.5px solid ${active || done ? 'var(--fg-1)' : 'var(--border-2)'}`,
        background: active ? 'var(--fg-1)' : 'var(--bg-1)',
        color: active ? 'var(--bg-1)' : (done ? 'var(--fg-1)' : 'var(--fg-3)'),
      }}>
        {done && !active ? <Check size={12} strokeWidth={3} /> : index}
      </i>
      {/* Schmal steht nur das Wort der aktuellen Station – die Zahlen tragen den Weg. */}
      <span className={active ? undefined : 'hidden sm:inline'}>{label}</span>
    </span>
  );
}
