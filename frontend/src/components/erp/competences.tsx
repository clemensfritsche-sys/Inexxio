'use client';

import { Check, Plus } from 'lucide-react';
import { COMPETENCES } from '@/lib/vocab';
import { api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { todoChanged } from '@/lib/todo';
import { useAction } from '@/lib/use-action';
import { Label } from '@/components/erp/controls';
import type { UserProfile } from '@/types';

/**
 * ►►► **Was diese Person kann** – ein Feld in den Stammdaten (Projektakte «Aufgaben» §3). ◄◄◄
 * Die Liste kommt aus `domain/competences` (generiert, `lib/vocab`); gespeichert wird über das
 * bestehende Speichern der Person. Ändern darf nur, wem der Server es sagt (`may_edit`: bei
 * Mitarbeitenden der Admin); die letzte Person einer Kompetenz lehnt der Server ab – sein Satz
 * steht dann in der Meldezeile.
 */
export function Competences({ record, onSaved }: {
  record: UserProfile; onSaved: (u: UserProfile) => void;
}) {
  const { busy, run } = useAction();
  const has = new Set(record.competences ?? []);
  const edit = record.may_edit && record.object_id != null;
  const toggle = async (c: string) => {
    const next = COMPETENCES.filter((x) => (x === c ? !has.has(x) : has.has(x)));
    const saved = await run(() => api.updateErpRecord(record.object_id!, { competences: next }),
      tell('Kompetenzen', 'Nicht gespeichert'));
    if (saved) { onSaved(saved); todoChanged(); }
  };
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <Label>Kompetenzen</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {COMPETENCES.filter((c) => edit || has.has(c)).map((c) => {
          const on = has.has(c);
          const Icon = on ? Check : Plus;
          return (
            <button key={c} type="button" disabled={!edit || busy} aria-pressed={on}
              onClick={() => toggle(c)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, height: 26, padding: '0 10px',
                borderRadius: 999, font: '600 12px var(--font-body)', cursor: edit ? 'pointer' : 'default',
                background: on ? 'var(--success-bg)' : 'transparent', color: on ? 'var(--success)' : 'var(--fg-3)',
                border: on ? '1px solid transparent' : '1px dashed var(--border-2)',
              }}>
              <Icon size={12} aria-hidden />{c}
            </button>
          );
        })}
        {!edit && has.size === 0 && <span style={{ fontSize: 13, color: 'var(--fg-4)' }}>keine</span>}
      </div>
    </div>
  );
}
