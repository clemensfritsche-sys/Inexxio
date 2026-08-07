'use client';

import { useEffect, useState } from 'react';
import { ClipboardCheck, Check, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Capture } from '@/types';
import { Card } from '@/components/erp/fields';
import { localDateTime } from '@/lib/utils';

/**
 * **Was an dieser Einzelinstanz erfasst wurde** – die Historie, sonst nichts.
 *
 * Erfasst wird im **Prozess**: wenn das Stück vor einem Datenerfassungs-Modul steht und
 * jemand bestätigt. Hier gab es früher ein zweites Formular, mit dem man an jedem Stück
 * jederzeit erfassen konnte – eine Erfassung ohne Anlass und eine zweite Tür zu derselben
 * Sache. Sie ist entfallen; geblieben ist der Nachweis.
 *
 * **Eingefroren**: kein Bearbeiten, kein Löschen – dafür gibt es keinen Endpunkt. Eine
 * Korrektur wäre eine neue Erfassung.
 */
export function CapturePanel({ number }: { number: string }) {
  const [rows, setRows] = useState<Capture[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    setError(null);
    api.getCaptures(number)
      .then((h) => { if (!dead) setRows(h); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [number]);

  if (error) {
    return (
      <Card icon={ClipboardCheck} title="Datenerfassung">
        <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>
      </Card>
    );
  }
  if (rows === null) return null;

  return (
    <Card icon={ClipboardCheck} title="Datenerfassung">
      {rows.length === 0 ? (
        <p className="text-sm text-fg-3">
          An diesem Stück wurde noch nichts erfasst. Erfasst wird im Prozess – an einem
          Datenerfassungs-Modul, vor dem es steht.
        </p>
      ) : (
        <div className="flex flex-col">
          {rows.map((c) => (
            <div key={c.id} className="flex flex-col gap-1 py-2 border-t border-border-1">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Verdict result={c.result} />
                <span className="font-medium">{c.step_name ?? 'Datenerfassung'}</span>
                <span className="flex-1" />
                <span className="text-fg-4 text-xs">{localDateTime(c.created_at)}</span>
              </div>
              {/* Der Punkt trägt die Bezeichnung, der Wert die Messung. Ohne die
                  Definition stünden hier nur Schlüssel und Rohwerte. */}
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-fg-3">
                {(c.points ?? []).map((p) => (
                  <span key={p.key}>
                    {p.label}: <strong style={{ color: 'var(--fg-2)' }}>
                      {display((c.values as Record<string, unknown>)[p.key])}
                    </strong>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/** Ein erfasster Wert für die Anzeige. Ja/Nein liest sich als Wort, ein Bild als «erfasst». */
function display(value: unknown): string {
  if (value === true) return 'ja';
  if (value === false) return 'nein';
  if (value == null || value === '') return '–';
  const text = Array.isArray(value) ? value.join(', ') : String(value);
  return /^(https?:|\/)/.test(text) ? 'erfasst' : text;
}

/** `null` heisst «nichts Bewertbares erfasst» – dann steht hier bewusst nichts. */
function Verdict({ result }: { result: string | null | undefined }) {
  if (!result) return <span className="text-fg-3 text-xs">ohne Urteil</span>;
  const ok = result === 'passed';
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-ds-sm text-xs font-medium"
      style={{
        color: ok ? 'var(--success)' : 'var(--danger)',
        background: ok ? 'var(--success-bg)' : 'var(--danger-bg)',
      }}
    >
      {ok ? <Check size={12} /> : <X size={12} />}
      {ok ? 'bestanden' : 'nicht bestanden'}
    </span>
  );
}
