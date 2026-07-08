'use client';

import { useEffect, useState } from 'react';
import { FileText, FileDown, Hash, Send, PenLine, Check, X, RotateCcw, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings, Order, DocumentContent, SignoffView, UserProfile } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { DocumentEditor, DocumentView } from '@/components/erp/document-editor';
import { SignaturePad } from '@/components/erp/signature-pad';
import { PanelHeader, PrimaryButton, SaveIndicator } from '@/components/erp/fields';
import { AiWriteAssist } from '@/components/ai/write-assist';
import { useAutosave } from '@/lib/use-autosave';

// Panel des Dokument-Schritts im Auftrag. Der Inhalt wird HIER – während der Ausführung –
// verfasst und mit «Ausstellen» festgeschrieben (issued). Danach signieren die Freigabe-
// Parteien; erst wenn ALLE signiert haben, ist das Dokument freigegeben (done). Nummer
// (= Instanz-Objektnummer) und Datum (= Instanz-Freigabe) kommen aus dem Auftrag.
function emptyContent(): DocumentContent {
  return { title: '', subtitle: null, sections: [] };
}

export function DocumentPanel({ order, stepState, stepId, company, onOrderUpdated }: {
  order: Order;
  stepState: string;               // 'locked' | 'active' | 'done' | 'blocked'
  stepId: number;
  company?: Partial<CompanySettings> | null;   // Briefkopf/Fusszeile (Online = PDF)
  onOrderUpdated: (o: Order) => void;
}) {
  // Step-spezifisches Embed bevorzugen (mehrere Dokument-Schritte je Auftrag möglich);
  // Fallback auf das Kurzform-``order.document`` (erster Schritt).
  const doc = order.steps?.find((s) => s.id === stepId)?.document ?? order.document ?? null;
  const done = !!doc?.done;              // vollständig freigegeben (alle Parteien signiert)
  const issued = !!doc?.issued;          // Inhalt festgeschrieben (Unterschriften laufen)
  const nr = doc?.object_number ?? null;
  const locked = stepState === 'locked';
  const signoffs: SignoffView[] = doc?.signoffs ?? [];

  const [me, setMe] = useState<UserProfile | null>(null);
  useEffect(() => { api.getMe().then(setMe).catch(() => {}); }, []);

  const [draft, setDraft] = useState<DocumentContent>(() => (doc?.content as DocumentContent) ?? emptyContent());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedSig, setSavedSig] = useState<string>(() => JSON.stringify((doc?.content as DocumentContent) ?? emptyContent()));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    if (doc?.content) { setDraft(doc.content as DocumentContent); setSavedSig(JSON.stringify(doc.content)); }
  }, [doc?.id, issued]);
  /* eslint-enable react-hooks/exhaustive-deps */

  const sig = JSON.stringify(draft);
  // Auto-Save nur solange NICHT ausgestellt (danach ist der Inhalt eingefroren).
  const canAutosave = !locked && !issued && !busy && !saving && sig !== savedSig;

  async function autosave() {
    setSaving(true); setErr(null);
    try {
      const updated = await api.updateOrderDocument(order.object_id as number, { step_id: stepId, content: draft, action: 'save' });
      setSavedSig(sig);
      onOrderUpdated(updated);
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch (e) {
      if (!issued) setErr(e instanceof Error ? e.message : 'Automatisches Speichern fehlgeschlagen');
    } finally { setSaving(false); }
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

  async function withdraw() {
    if (!confirm('Ausstellung zurücknehmen? Der Inhalt wird wieder editierbar und alle bisherigen Freigaben verfallen.')) return;
    setBusy(true); setErr(null);
    try {
      const updated = await api.withdrawOrderDocument(order.object_id as number, stepId);
      onOrderUpdated(updated);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Zurücknehmen fehlgeschlagen'); }
    finally { setBusy(false); }
  }

  async function download() {
    if (!doc?.id) return;
    setBusy(true); setErr(null);
    try { await api.openDocumentPdf(doc.id, nr); }
    catch (e) { setErr(e instanceof Error ? e.message : 'PDF konnte nicht geladen werden'); }
    finally { setBusy(false); }
  }

  async function preview() {
    setBusy(true); setErr(null);
    try {
      const updated = await api.updateOrderDocument(order.object_id as number, { step_id: stepId, content: draft, action: 'save' });
      onOrderUpdated(updated);
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
        info="Inhalt verfassen und mit «Ausstellen» festschreiben. Danach geben die benannten Parteien frei; erst wenn alle unterschrieben/bestätigt haben, ist das Dokument freigegeben."
        right={nr ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#6E6E73', fontVariantNumeric: 'tabular-nums' }}>
            <Hash size={12} /> {fmtObjId(nr)}
          </span>
        ) : (
          <StatusPill done={done} issued={issued} />
        )}
      />

      {locked ? (
        <div style={{ fontSize: 13, color: '#6E6E73' }}>
          Dieser Schritt ist noch nicht an der Reihe – zuerst die vorherigen Schritte abschliessen.
        </div>
      ) : done ? (
        <>
          <button onClick={download} disabled={busy} style={dlBtn(busy)}>
            <FileDown size={16} /> {busy ? 'Wird geladen…' : 'Als PDF herunterladen'}
          </button>
          {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
          <DocumentView content={doc?.content ?? null} objectNr={nr ? fmtObjId(nr) : null} issuedAt={doc?.document_date ?? null} company={company} signoffs={signoffs} />
        </>
      ) : issued ? (
        /* Ausgestellt – Inhalt eingefroren, Freigaben laufen. */
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', background: '#FBF1DE', border: '1px solid #EBD9CF', borderRadius: 8, fontSize: 12.5, color: '#8A5A1A' }}>
            <ShieldCheck size={15} style={{ flexShrink: 0 }} />
            <span>Ausgestellt – der Inhalt ist festgeschrieben. Das Dokument wird freigegeben, sobald alle Parteien unterschrieben/bestätigt haben.</span>
          </div>
          <SignoffList order={order} signoffs={signoffs} sequential={!!doc?.sign_sequential} meObjectId={me?.object_id ?? null} onOrderUpdated={onOrderUpdated} />
          <button onClick={withdraw} disabled={busy} style={withdrawBtn}>
            <RotateCcw size={14} /> Ausstellung zurücknehmen
          </button>
          {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
          <DocumentView content={doc?.content ?? null} objectNr={nr ? fmtObjId(nr) : null} issuedAt={doc?.document_date ?? null} company={company} signoffs={signoffs} />
        </>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 7, minHeight: 18 }}>
            <SaveIndicator saving={saving} flash={flash} />
            <span style={{ fontSize: 11.5, color: '#6E6E73' }}>
              {saving ? 'Speichert…' : canAutosave ? 'Nicht gespeicherte Änderungen' : 'Automatisch gespeichert'}
            </span>
          </div>
          <AiWriteAssist current={draft} onResult={setDraft} />
          <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}>
            <DocumentEditor value={draft} onChange={setDraft} onPreviewPdf={preview} company={company} />
          </div>
          {signoffs.length > 0 && (
            <div style={{ fontSize: 11.5, color: '#6E6E73', display: 'flex', alignItems: 'center', gap: 6 }}>
              <PenLine size={12} /> Nach dem Ausstellen geben {signoffs.length} Partei{signoffs.length === 1 ? '' : 'en'} frei.
            </div>
          )}
          {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
          <PrimaryButton icon={Send} onClick={() => submit('issue')} disabled={busy || saving} tone="success">
            {busy ? 'Wird ausgestellt…' : 'Dokument ausstellen'}
          </PrimaryButton>
        </>
      )}
    </div>
  );
}

function StatusPill({ done, issued }: { done: boolean; issued: boolean }) {
  const label = done ? 'Freigegeben' : issued ? 'Freigaben laufen' : 'Entwurf';
  const [bg, fg] = done ? ['#DCFCE7', '#15803D'] : issued ? ['#FBF1DE', '#C8861A'] : ['#FBF1DE', '#C8861A'];
  return (
    <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: fg, background: bg, padding: '2px 8px', borderRadius: 999 }}>
      {label}
    </span>
  );
}

// ─── Freigabe-Parteien: Status je Partei + Aktionen für die eigene Partei ──────
function SignoffList({ order, signoffs, sequential, meObjectId, onOrderUpdated }: {
  order: Order; signoffs: SignoffView[]; sequential: boolean;
  meObjectId: number | null; onOrderUpdated: (o: Order) => void;
}) {
  if (signoffs.length === 0) {
    return <div style={{ fontSize: 12.5, color: '#6E6E73' }}>Keine Freigabe-Parteien – bereits freigegeben.</div>;
  }
  // Bei sequenzieller Freigabe ist nur die erste noch offene Partei an der Reihe.
  const firstPendingId = signoffs.filter((s) => s.status === 'pending')
    .sort((a, b) => a.order_index - b.order_index || a.id - b.id)[0]?.id ?? null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6E6E73' }}>
        Freigabe-Parteien{sequential ? ' · der Reihe nach' : ''}
      </div>
      {signoffs.map((s, i) => (
        <SignoffRow key={s.id} order={order} signoff={s} index={i} isMine={meObjectId != null && s.signer_object_id === meObjectId}
          myTurn={!sequential || s.id === firstPendingId} onOrderUpdated={onOrderUpdated} />
      ))}
    </div>
  );
}

function SignoffRow({ order, signoff, index, isMine, myTurn, onOrderUpdated }: {
  order: Order; signoff: SignoffView; index: number; isMine: boolean; myTurn: boolean;
  onOrderUpdated: (o: Order) => void;
}) {
  const s = signoff;
  const [mode, setMode] = useState<null | 'sign' | 'reject'>(null);
  const [sigUrl, setSigUrl] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const statusChip = s.status === 'signed'
    ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#15803D', fontWeight: 700, fontSize: 12 }}><Check size={13} /> {s.action === 'sign' ? 'Unterschrieben' : 'Bestätigt'}</span>
    : s.status === 'rejected'
      ? <span style={{ color: '#dc2626', fontWeight: 700, fontSize: 12 }}>Abgelehnt</span>
      : <span style={{ color: '#C8861A', fontWeight: 600, fontSize: 12 }}>Ausstehend</span>;

  async function act(action: 'confirm' | 'sign' | 'reject' | 'withdraw') {
    if (action === 'sign' && !sigUrl) { setErr('Bitte zuerst unterschreiben.'); return; }
    setBusy(true); setErr(null);
    try {
      const updated = await api.actOrderDocumentSignoff(order.object_id as number, s.id, {
        action, signature_url: action === 'sign' ? sigUrl : null, reason: action === 'reject' ? (reason.trim() || null) : null,
      });
      setMode(null); setSigUrl(null); setReason('');
      onOrderUpdated(updated);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Aktion fehlgeschlagen'); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ border: `1px solid ${isMine && s.status === 'pending' && myTurn ? '#2563eb' : '#E9E7E1'}`, borderRadius: 10, padding: 11, background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#6E6E73', minWidth: 16 }}>{index + 1}.</span>
        <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: '#0A0A0B', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {s.signer_name ?? `Objekt ${fmtObjId(s.signer_object_id)}`}
          {isMine && <span style={{ marginLeft: 6, fontSize: 10.5, fontWeight: 700, color: '#2563eb', textTransform: 'uppercase' }}>Sie</span>}
        </span>
        {statusChip}
      </div>
      {s.status === 'rejected' && s.reason && (
        <div style={{ fontSize: 11.5, color: '#dc2626', marginTop: 4, paddingLeft: 24 }}>{s.reason}</div>
      )}

      {/* Aktionen nur für die eigene Partei */}
      {isMine && s.status !== 'signed' && (
        <div style={{ marginTop: 9, paddingLeft: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {!myTurn && s.status === 'pending' && (
            <div style={{ fontSize: 11.5, color: '#C8861A' }}>Eine andere Partei ist zuerst an der Reihe.</div>
          )}
          {myTurn && mode === null && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {s.action === 'sign' ? (
                <button onClick={() => setMode('sign')} disabled={busy} style={actBtn('#2563eb')}><PenLine size={14} /> Unterschreiben</button>
              ) : (
                <button onClick={() => act('confirm')} disabled={busy} style={actBtn('#15803D')}><Check size={14} /> Bestätigen</button>
              )}
              <button onClick={() => setMode('reject')} disabled={busy} style={actBtn('#dc2626', true)}><X size={14} /> Ablehnen</button>
            </div>
          )}
          {myTurn && mode === 'sign' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <SignaturePad value={sigUrl} onChange={setSigUrl} signerHint="Mit Maus/Finger unterschreiben." />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => act('sign')} disabled={busy || !sigUrl} style={actBtn('#2563eb')}><Check size={14} /> {busy ? 'Speichert…' : 'Unterschrift abgeben'}</button>
                <button onClick={() => { setMode(null); setSigUrl(null); }} disabled={busy} style={ghostBtn}>Abbrechen</button>
              </div>
            </div>
          )}
          {mode === 'reject' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
                placeholder="Grund der Ablehnung (optional)"
                style={{ width: '100%', padding: '8px 10px', fontSize: 13, borderRadius: 8, border: '1px solid #E9E7E1', outline: 'none', resize: 'vertical' }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => act('reject')} disabled={busy} style={actBtn('#dc2626')}><X size={14} /> {busy ? 'Sendet…' : 'Ablehnen'}</button>
                <button onClick={() => { setMode(null); setReason(''); }} disabled={busy} style={ghostBtn}>Abbrechen</button>
              </div>
            </div>
          )}
          {s.status === 'rejected' && myTurn && mode === null && (
            <button onClick={() => act('withdraw')} disabled={busy} style={ghostBtn}><RotateCcw size={13} /> Ablehnung zurücknehmen</button>
          )}
          {err && <div style={{ fontSize: 11.5, color: '#dc2626' }}>{err}</div>}
        </div>
      )}
      {/* Eigene, bereits erfolgte Unterschrift zurückziehen */}
      {isMine && s.status === 'signed' && (
        <div style={{ marginTop: 8, paddingLeft: 24 }}>
          <button onClick={() => act('withdraw')} disabled={busy} style={ghostBtn}><RotateCcw size={13} /> Zurückziehen</button>
        </div>
      )}
    </div>
  );
}

const dlBtn = (busy: boolean): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
  alignSelf: 'flex-start', minHeight: 44, padding: '0 18px', borderRadius: 10,
  border: 'none', background: '#E51A14', color: '#fff', fontSize: 14, fontWeight: 600,
  cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
});
const withdrawBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 7, alignSelf: 'flex-start',
  padding: '8px 13px', borderRadius: 9, border: '1px solid #E9E7E1', background: '#fff',
  color: '#6E6E73', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
};
const actBtn = (color: string, outline = false): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 13px', borderRadius: 9,
  border: outline ? `1px solid ${color}` : 'none', background: outline ? '#fff' : color,
  color: outline ? color : '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer',
});
const ghostBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 13px', borderRadius: 9,
  border: '1px solid #E9E7E1', background: '#fff', color: '#6E6E73', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
};
