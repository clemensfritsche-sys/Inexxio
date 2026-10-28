'use client';

import { useState } from 'react';
import { FilePlus2, FileText, Lock } from 'lucide-react';
import { api } from '@/lib/api';
import { formatObjectId } from '@/lib/utils';
import { ObjectSelect } from '@/components/erp/object-select';
import { useErpNav } from '@/components/erp/obj-id';
import { DraftSheet, type DraftSeed } from '@/components/erp/document-draft';
import type { DocumentDetail, DocumentProposal, DocumentTarget } from '@/types';

/** Ein Dokument zum Wählen – in der Form, die `ObjectSelect` kennt. */
export interface DocumentOption { object_id: number; name: string }

export const findDocuments = (q: string): Promise<DocumentOption[]> =>
  api.getDocuments(q, 20).then((rows) => rows.map((d) => ({ object_id: d.object_id, name: `${d.art} · ${d.name}` })));

/**
 * ►►► **Ein Pflichtfeld, in dem ein Dokument steht** (Regel 6: änderbar, nie leer). ◄◄◄
 *
 * Lieferantenrechnung, Ausfuhrnachweis, Nachweis einer Absenz, AGB, Datenschutz: überall
 * dieselbe Form. Steht ein Dokument im Feld, zeigt es sich mit Nummer (Klick öffnet es); sonst
 * wählt man ein vorhandenes (Nummer oder Name – etwa den Anhang einer Mail, der schon
 * freigegeben ist) oder legt mit «Neu» eines an – über DENSELBEN Entwurf wie überall, das Feld
 * als Referenz mit Schloss. Gesetzt wird das Feld vom Dienst, in derselben Transaktion wie die
 * Freigabe; die Werte, die die KI abgelesen hat, reichen wir an das Modul weiter.
 */
export function DocumentField({ value, label, target, seed, disabled, onChange }: {
  value: number | null | undefined;
  /** Was im Feld steht – «Rechnung», «AGB» … */
  label: string;
  target: DocumentTarget & { label?: string; lock?: string };
  seed?: Omit<DraftSeed, 'target'>;
  disabled?: boolean;
  onChange: (doc: DocumentDetail, proposal: DocumentProposal | null) => void;
}) {
  const nav = useErpNav();
  const [drafting, setDrafting] = useState(false);
  const [changing, setChanging] = useState(false);
  const [error, setError] = useState('');

  async function pick(objectId: number) {
    setError('');
    try {
      onChange(await api.setDocumentField(objectId, target), null);
      setChanging(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
      {value && !changing ? (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={() => nav?.(value)} disabled={!nav}
            data-tip={`Pflichtfeld – ändern ja, leeren nie`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999,
                     border: '1px solid var(--border-2)', background: 'var(--bg-1)', cursor: nav ? 'pointer' : 'default',
                     font: '500 13px var(--font-body)', color: 'var(--fg-1)' }}>
            <FileText size={13} style={{ color: 'var(--fg-3)' }} />
            <span className="erp-objid" style={{ font: '500 13px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
              {formatObjectId(value)}
            </span>
            {label}
            <Lock size={12} style={{ color: 'var(--fg-4)' }} />
          </button>
          {!disabled && (
            <button type="button" onClick={() => setChanging(true)}
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                       fontSize: 12.5, color: 'var(--accent-ink)' }}>ändern</button>
          )}
        </span>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', minWidth: 0 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <ObjectSelect<DocumentOption> value={null} find={findDocuments} disabled={disabled}
              placeholder="Dokument – Nummer oder Name" onChange={(id) => { if (id) void pick(id); }} />
          </div>
          <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={disabled}
            style={{ height: 36, flex: 'none' }} onClick={() => setDrafting(true)}>
            <FilePlus2 size={14} /> Neu
          </button>
          {changing && (
            <button type="button" className="erp-actbtn erp-actbtn-neutral" style={{ height: 36, flex: 'none' }}
              onClick={() => setChanging(false)}>Abbrechen</button>
          )}
        </div>
      )}
      {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      {drafting && (
        <DraftSheet seed={{ ...seed, target }} onCancel={() => setDrafting(false)}
          onFiled={(doc, proposal) => { setDrafting(false); setChanging(false); onChange(doc, proposal); }} />
      )}
    </div>
  );
}

/**
 * **Was die KI abgelesen hat, als Wert eines Formularfelds** – Betrag ohne Tausender-Zeichen
 * und Währung, alles andere wie gedruckt. Leer bleibt leer: vorbelegt wird nur, was da ist.
 */
export function readValue(proposal: DocumentProposal | null, key: string): string {
  const raw = String((proposal?.values as Record<string, unknown> | undefined)?.[key] ?? '').trim();
  if (key !== 'amount') return raw;
  const num = raw.replace(/[^0-9.,-]/g, '').replace(/[’']/g, '');
  return /,\d{1,2}$/.test(num) ? num.replace(/\./g, '').replace(',', '.') : num.replace(/,/g, '');
}

/** **Ein Dokument als Verweis in einer Zeile** – Nummer, Klick öffnet es. */
export function DocLink({ objectId, label }: { objectId: number; label: string }) {
  const nav = useErpNav();
  return (
    <button type="button" onClick={() => nav?.(objectId)} disabled={!nav}
      data-tip={formatObjectId(objectId)}
      style={{ background: 'none', border: 'none', padding: 0, cursor: nav ? 'pointer' : 'default',
               font: 'inherit', color: 'var(--accent-ink)' }}>{label}</button>
  );
}
