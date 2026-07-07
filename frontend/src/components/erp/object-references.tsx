'use client';

/**
 * Reiter «Verwendung» – generisch für JEDEN ERP-Objekttyp (Benutzer, Instanz, Lagerplatz,
 * Unternehmen): «Wer zeigt auf diese Objektnummer?» – aktuell hier **verortete** Instanzen
 * (gehalten/gelagert/enthalten) + Prozessschritte, die sie als Ziel referenzieren.
 *
 * Löst das allgemeine Thema «was liegt/referenziert auf X» über EINE Objektnummer statt
 * je Datensatztyp – dieselbe Optik wie der «Dokumente»-Reiter (`ObjectDocuments`).
 */

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ObjectReference } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { localDate } from '@/lib/utils';

export function ObjectReferences({ objectId, emptyHint }: {
  objectId: number | null | undefined;
  emptyHint?: string;
}) {
  const [refs, setRefs] = useState<ObjectReference[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (objectId == null) { setRefs([]); return; }
    setRefs(null);
    api.getObjectReferences(objectId)
      .then((r) => { if (!cancelled) setRefs(r); })
      .catch(() => { if (!cancelled) setRefs([]); });
    return () => { cancelled = true; };
  }, [objectId]);

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 2 }}>
        Hier verortet / referenziert
      </div>
      {refs === null ? (
        <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>
      ) : refs.length === 0 ? (
        <div style={{ fontSize: 13, color: '#94a3b8' }}>{emptyHint ?? 'Nichts verortet, kein Prozessschritt referenziert diese Objektnummer.'}</div>
      ) : refs.map((r, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{r.kind}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>{localDate(r.at)}</div>
          </div>
          <span style={{ fontSize: 12 }}><ObjId value={r.object_id} /></span>
        </div>
      ))}
    </div>
  );
}
