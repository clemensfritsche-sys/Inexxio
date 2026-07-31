'use client';

/**
 * Consent-Gate – blockierendes Pop-up für **zu bestätigende Pflichtdokumente**
 * (AGB, Datenschutz, Lieferantenvereinbarung …). Für JEDE angemeldete Rolle (Mitarbeiter,
 * Lieferant, Kunde, Admin). Solange offene Bestätigungen bestehen, überlagert das Gate die
 * gesamte Oberfläche – man kann nichts anderes tun, bis quittiert ist.
 *
 * Versioniert: die «Version» eines Dokuments ist die Objektnummer der gültigen Instanz
 * (`services/legal.resolve`). Wird eine neue Fassung veröffentlicht, taucht die Bestätigung
 * automatisch wieder auf. Selbst-enthalten (eigenes Auth-Handling) – mountbar in jedem Layout.
 */

import { useEffect, useState } from 'react';
import { ShieldCheck, Loader2 } from 'lucide-react';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import type { PendingDocument, CompanySettings } from '@/types';
import { DocumentView } from '@/components/erp/document-editor';
import { formatObjectId } from '@/lib/utils';

export function ConsentGate() {
  const [pending, setPending] = useState<PendingDocument[]>([]);
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);
  const [busy, setBusy] = useState(false);
  const [read, setRead] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const list = await api.getPendingDocuments();
        if (!cancelled) setPending(list);
      } catch { if (!cancelled) setPending([]); }
    }
    const unsub = onAuthChange(async (fbUser) => {
      if (!fbUser) { if (!cancelled) setPending([]); return; }
      try {
        const token = await fbUser.getIdToken();
        api.setToken(token);
        await refresh();
      } catch { if (!cancelled) setPending([]); }
    });
    // Beim Zurückkehren auf den Tab neu prüfen: so erscheint eine neu veröffentlichte
    // Anerkennungspflicht sofort (z. B. beim Testen mit einem zweiten Konto), ohne Neu-Login.
    const onFocus = () => { void refresh(); };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    api.getPublicSettings().then((s) => { if (!cancelled) setCompany(s); }).catch(() => {});
    return () => {
      cancelled = true; unsub();
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onFocus);
    };
  }, []);

  // Hintergrund-Scroll sperren, solange das Gate offen ist.
  useEffect(() => {
    if (pending.length === 0) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [pending.length]);

  // Beim Wechsel auf das nächste Dokument die «gelesen»-Bestätigung zurücksetzen.
  const doc = pending[0];
  useEffect(() => { setRead(false); setErr(null); }, [doc?.kind, doc?.object_number]);

  if (!doc) return null;

  async function accept() {
    if (!doc) return;
    setBusy(true); setErr(null);
    try {
      // Publikums-Dokument (kind='document') braucht die Objektnummer als Version.
      const remaining = await api.acknowledgeDocument(doc.kind, doc.object_number);
      setPending(remaining);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Bestätigung fehlgeschlagen');
    } finally { setBusy(false); }
  }

  return (
    <div role="dialog" aria-modal="true" style={{
      position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(15,23,42,0.78)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, maxWidth: 780, width: '100%', maxHeight: '92vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 24px 60px rgba(0,0,0,0.35)',
      }}>
        <header style={{ padding: '16px 22px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <ShieldCheck size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Bitte bestätigen: {doc.title}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>
              Zur weiteren Nutzung müssen die aktuellen Bedingungen bestätigt werden.
              {pending.length > 1 && <> · noch {pending.length} Dokument(e)</>}
            </div>
          </div>
        </header>

        <div style={{ overflowY: 'auto', padding: '20px 22px', background: '#FAFAF8' }}>
          {doc.content ? (
            <DocumentView
              content={doc.content}
              objectNr={doc.object_number ? formatObjectId(doc.object_number) : null}
              issuedAt={doc.document_date}
              company={company}
            />
          ) : (
            <p style={{ fontSize: 14, color: '#64748b' }}>Dokument «{doc.title}» ist zu bestätigen.</p>
          )}
        </div>

        <footer style={{ padding: '14px 22px', borderTop: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {err && <div style={{ fontSize: 13, color: '#dc2626' }}>{err}</div>}
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 9, fontSize: 13, color: '#334155', cursor: 'pointer' }}>
            <input type="checkbox" checked={read} onChange={(e) => setRead(e.target.checked)} style={{ marginTop: 2 }} />
            <span>Ich habe die <strong>{doc.title}</strong> gelesen und akzeptiere sie.</span>
          </label>
          <button type="button" onClick={accept} disabled={!read || busy}
            style={{
              alignSelf: 'flex-end', display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '10px 20px', borderRadius: 9, border: 'none',
              background: (!read || busy) ? '#cbd5e1' : '#2563eb', color: '#fff',
              fontSize: 14, fontWeight: 600, cursor: (!read || busy) ? 'not-allowed' : 'pointer',
            }}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
            Akzeptieren
          </button>
        </footer>
      </div>
    </div>
  );
}
