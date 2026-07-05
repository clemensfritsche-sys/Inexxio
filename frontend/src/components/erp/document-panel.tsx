'use client';

import { useEffect, useState } from 'react';
import { FileText, FileDown, Hash, Send } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, DocumentContent } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { DocumentEditor, DocumentView } from '@/components/erp/document-editor';
import { PanelHeader, PrimaryButton, SaveIndicator } from '@/components/erp/fields';
import { useAutosave } from '@/lib/use-autosave';

// Panel des Dokument-Schritts im Auftrag. Der Inhalt wird HIER – während der Ausführung –
// verfasst und mit «Ausstellen» festgeschrieben (analog Datenerfassung). Nummer (= Instanz-
// Objektnummer) und Datum (= Instanz-Freigabe) kommen aus dem Auftrag.
function emptyContent(): DocumentContent {
  return { title: '', subtitle: null, sections: [] };
}

export function DocumentPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;               // 'locked' | 'active' | 'done' | 'blocked'
  stepId: number;
  onOrderUpdated: (o: Order) => void;
}) {
  const doc = order.document ?? null;
  const done = !!doc?.done;
  const nr = doc?.object_number ?? null;
  const locked = stepState === 'locked';

  const [draft, setDraft] = useState<DocumentContent>(() => (doc?.content as DocumentContent) ?? emptyContent());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Auto-Save (wie Google Docs): kein «Zwischenspeichern» mehr. Ein separater, leiser
  // Indikator; das Tippen wird NICHT blockiert (eigener `saving`-Zustand statt `busy`).
  const [savedSig, setSavedSig] = useState<string>(() => JSON.stringify((doc?.content as DocumentContent) ?? emptyContent()));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);

  // Frischen Stand nur bei WECHSEL der Fachzeile/Ausstellung übernehmen – NICHT bei jeder
  // content-Änderung (sonst würden laufende Eingaben überschrieben).
  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    if (doc?.content) { setDraft(doc.content as DocumentContent); setSavedSig(JSON.stringify(doc.content)); }
  }, [doc?.id, done]);
  /* eslint-enable react-hooks/exhaustive-deps */

  const sig = JSON.stringify(draft);
  const canAutosave = !locked && !done && !busy && sig !== savedSig;

  async function autosave() {
    setSaving(true); setErr(null);
    try {
      const updated = await api.updateOrderDocument(order.object_id as number, { step_id: stepId, content: draft, action: 'save' });
      setSavedSig(sig);
      onOrderUpdated(updated);
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Automatisches Speichern fehlgeschlagen'); }
    finally { setSaving(false); }
  }
  const flush = useAutosave(sig, canAutosave, autosave);

  async function submit(action: 'issue') {
    if (!draft.title.trim()) { setErr('Bitte einen Titel angeben'); return; }
    setBusy(true); setErr(null);
    try {
      const updated = await api.updateOrderDocument(order.object_id as number, { step_id: stepId, content: draft, action });
      setSavedSig(sig);
      onOrderUpdated(updated);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Ausstellen'); }
    finally { setBusy(false); }
  }

  async function download() {
    if (!doc?.id) return;
    setBusy(true); setErr(null);
    try { await api.openDocumentPdf(doc.id, nr); }
    catch (e) { setErr(e instanceof Error ? e.message : 'PDF konnte nicht geladen werden'); }
    finally { setBusy(false); }
  }

  // Vorschau: Zwischenstand speichern, dann das (frische) PDF öffnen.
  async function preview() {
    setBusy(true); setErr(null);
    try {
      const updated = await api.updateOrderDocument(order.object_id as number, { step_id: stepId, content: draft, action: 'save' });
      onOrderUpdated(updated);
      // Die PER-SCHRITT-Fachzeile (``doc.id``) ist massgeblich – ``updated.document`` ist
      // bei mehreren Dokument-Schritten immer der ERSTE (sonst öffnete die Vorschau das falsche).
      const freshId = doc?.id ?? updated.steps.find((s) => s.id === stepId)?.document?.id;
      if (freshId) await api.openDocumentPdf(freshId, nr);
    } catch (e) { setErr(e instanceof Error ? e.message : 'PDF-Vorschau fehlgeschlagen'); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E9E7E1', borderRadius: 12, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <PanelHeader
        icon={FileText}
        title="Dokument"
        tone="#E51A14"
        info="Inhalt hier verfassen und mit «Ausstellen» festschreiben. Die Dokumentennummer ist die Instanz-Objektnummer, das Datum die Instanz-Freigabe."
        right={nr ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#6E6E73', fontVariantNumeric: 'tabular-nums' }}>
            <Hash size={12} /> {fmtObjId(nr)}
          </span>
        ) : (
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#C8861A', background: '#FBF1DE', padding: '2px 8px', borderRadius: 999 }}>
            {done ? 'Ausgestellt' : 'Entwurf'}
          </span>
        )}
      />

      {locked ? (
        <div style={{ fontSize: 13, color: '#6E6E73' }}>
          Dieser Schritt ist noch nicht an der Reihe – zuerst die vorherigen Schritte abschliessen.
        </div>
      ) : done ? (
        <>
          <button onClick={download} disabled={busy} style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            alignSelf: 'flex-start', minHeight: 44, padding: '0 18px', borderRadius: 10,
            border: 'none', background: '#E51A14', color: '#fff', fontSize: 14, fontWeight: 600,
            cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
          }}>
            <FileDown size={16} /> {busy ? 'Wird geladen…' : 'Als PDF herunterladen'}
          </button>
          {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
          <DocumentView content={doc?.content ?? null} objectNr={nr ? fmtObjId(nr) : null} issuedAt={doc?.document_date ?? null} />
        </>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 7, minHeight: 18 }}>
            <SaveIndicator saving={saving} flash={flash} />
            <span style={{ fontSize: 11.5, color: '#6E6E73' }}>
              {saving ? 'Speichert…' : canAutosave ? 'Nicht gespeicherte Änderungen' : 'Automatisch gespeichert'}
            </span>
          </div>
          {/* Enter speichert sofort (ausser in TEXTAREAs – dort Zeilenumbruch). */}
          <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}>
            <DocumentEditor value={draft} onChange={setDraft} onPreviewPdf={preview} />
          </div>
          {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
          <PrimaryButton icon={Send} onClick={() => submit('issue')} disabled={busy} tone="success">
            {busy ? 'Wird ausgestellt…' : 'Dokument ausstellen'}
          </PrimaryButton>
        </>
      )}
    </div>
  );
}
