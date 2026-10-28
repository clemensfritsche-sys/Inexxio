'use client';

import { useCallback, useEffect, useState } from 'react';
import { Scale } from 'lucide-react';
import { api } from '@/lib/api';
import { Card, Label } from '@/components/erp/fields';
import { DocumentField } from '@/components/erp/document-field';
import type { DocumentSummary } from '@/types';

/** Die zwei Rechtstexte einer Gesellschaft – Art, Pflichtfeld, Wort. */
const TEXTS = [
  { kind: 'agb', field: 'company.agb', label: 'AGB' },
  { kind: 'datenschutz', field: 'company.privacy', label: 'Datenschutz' },
] as const;

/**
 * ►►► **AGB und Datenschutz – zwei Pflichtfelder der eigenen Gesellschaft.** ◄◄◄
 *
 * Je ein Dokument (Regel 6: änderbar, nie leer). Jedes Papier eines Belegs hängt die AGB
 * seiner Gesellschaft an; die Website zeigt die AGB der Gesellschaft zum Land des Besuchers,
 * den Datenschutz des Betreibers. Ist ein Feld leer, bietet die Karte die Vorlage an – ein
 * Mensch entscheidet, angelegt wird nie von selbst. Setzen darf nur der Admin.
 */
export function LegalTexts({ company, isAdmin }: { company: number; isAdmin: boolean }) {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    api.documentsOf(company).then(setDocs).catch(() => setDocs([]));
  }, [company]);
  useEffect(() => { load(); }, [load]);

  async function fromTemplate(kind: 'agb' | 'datenschutz') {
    setError('');
    try { await api.legalFromTemplate(company, kind); load(); } catch (e) { setError((e as Error).message); }
  }

  return (
    <Card icon={Scale} title="Rechtstexte"
      info="Die AGB stehen auf jedem Papier dieser Gesellschaft und auf der Website ihrer Länder; der Datenschutz des Betreibers gilt für die Website.">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {TEXTS.map((t) => {
          const value = docs.find((d) => (d.fields ?? []).includes(t.field))?.object_id ?? null;
          return (
            <div key={t.kind} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Label>{t.label}</Label>
              <DocumentField value={value} label={t.label} disabled={!isAdmin}
                target={{ object_id: company, part: null, field: t.field, extra: {}, label: 'Gesellschaft', lock: t.label }}
                seed={{ art: t.label }}
                onChange={() => load()} />
              {!value && isAdmin && (
                <button type="button" onClick={() => void fromTemplate(t.kind)}
                  style={{ alignSelf: 'flex-start', background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                           fontSize: 12.5, color: 'var(--accent-ink)' }}>
                  Aus Vorlage übernehmen
                </button>
              )}
            </div>
          );
        })}
        {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      </div>
    </Card>
  );
}
