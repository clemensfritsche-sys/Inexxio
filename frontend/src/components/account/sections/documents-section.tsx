'use client';

/**
 * «Meine Dokumente» – die Freigabe-Aufgaben des angemeldeten Nutzers als **Partei**
 * (unterschreiben/bestätigen/ablehnen). Für JEDE Rolle (Kunde, Lieferant, Mitarbeiter):
 * hier signieren externe Parteien Dokumente, zu denen sie im Auftrag benannt wurden.
 * Nicht blockierend (eine To-do-Liste, kein Gate) – im Gegensatz zum Consent-Gate.
 */

import { useEffect, useState } from 'react';
import { FileText, PenLine, Check, X, Loader2, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import type { MySignoffDocument, CompanySettings } from '@/types';
import { DocumentView } from '@/components/erp/document-editor';
import { SignaturePad } from '@/components/erp/signature-pad';
import { fmtObjId } from '@/components/erp/user-detail';

export function DocumentsSection() {
  const [docs, setDocs] = useState<MySignoffDocument[]>([]);
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getMyDocuments().then(setDocs).catch(() => setDocs([])).finally(() => setLoading(false));
    api.getPublicSettings().then(setCompany).catch(() => {});
  }, []);

  if (loading) {
    return <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-4)', fontSize: 14 }}><Loader2 size={16} className="animate-spin" /> Wird geladen…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ font: '700 18px var(--font-display)', color: 'var(--fg-1)', margin: 0 }}>Meine Dokumente</h2>
        <p style={{ fontSize: 13.5, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Dokumente, zu deren Freigabe Sie als Partei benannt wurden – hier unterschreiben oder bestätigen.
        </p>
      </div>
      {docs.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 16px', border: '1px solid var(--border-1)', borderRadius: 12, background: 'var(--bg-2)', color: 'var(--fg-3)', fontSize: 14 }}>
          <Check size={18} style={{ color: 'var(--success)' }} /> Keine offenen Freigaben.
        </div>
      ) : (
        docs.map((d) => (
          <SignoffCard key={d.signoff_id} doc={d} company={company}
            onDone={(remaining) => setDocs(remaining)} />
        ))
      )}
    </div>
  );
}

function SignoffCard({ doc, company, onDone }: {
  doc: MySignoffDocument; company: Partial<CompanySettings> | null;
  onDone: (remaining: MySignoffDocument[]) => void;
}) {
  const [mode, setMode] = useState<null | 'view' | 'sign' | 'reject'>(null);
  const [sigUrl, setSigUrl] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function act(action: 'confirm' | 'sign' | 'reject' | 'withdraw') {
    if (action === 'sign' && !sigUrl) { setErr('Bitte zuerst unterschreiben.'); return; }
    setBusy(true); setErr(null);
    try {
      const remaining = await api.actSignoff(doc.signoff_id, {
        action, signature_url: action === 'sign' ? sigUrl : null,
        reason: action === 'reject' ? (reason.trim() || null) : null,
      });
      onDone(remaining);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Aktion fehlgeschlagen'); }
    finally { setBusy(false); }
  }

  const rejected = doc.status === 'rejected';
  return (
    <div style={{ border: '1px solid var(--border-1)', borderRadius: 12, background: '#fff', overflow: 'hidden' }}>
      <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: mode ? '1px solid var(--border-1)' : 'none' }}>
        <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--accent-soft)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <FileText size={19} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '700 14.5px var(--font-body)', color: 'var(--fg-1)' }}>{doc.title}</div>
          <div style={{ fontSize: 12, color: 'var(--fg-4)', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {doc.object_number != null && <span>Nr. {fmtObjId(doc.object_number)}</span>}
            <span>{doc.action === 'sign' ? 'Unterschrift erforderlich' : 'Bestätigung erforderlich'}</span>
            {rejected && <span style={{ color: 'var(--danger)', fontWeight: 600 }}>Von Ihnen abgelehnt</span>}
          </div>
        </div>
        {!doc.actionable && !rejected ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#C8861A', fontWeight: 600 }}>
            <Clock size={13} /> Andere Partei zuerst
          </span>
        ) : (
          <button onClick={() => setMode(mode ? null : 'view')} style={openBtn}>{mode ? 'Schliessen' : 'Öffnen'}</button>
        )}
      </div>

      {mode && (
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, background: 'var(--bg-2)' }}>
          <DocumentView content={doc.content} objectNr={doc.object_number ? fmtObjId(doc.object_number) : null}
            issuedAt={doc.document_date} company={company} />

          {rejected ? (
            <button onClick={() => act('withdraw')} disabled={busy} style={ghost}>Ablehnung zurücknehmen</button>
          ) : mode === 'sign' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 14, background: '#fff', border: '1px solid var(--border-1)', borderRadius: 10 }}>
              <SignaturePad value={sigUrl} onChange={setSigUrl} signerHint="Mit Maus/Finger unterschreiben." />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => act('sign')} disabled={busy || !sigUrl} style={primary('#2563eb')}><Check size={15} /> {busy ? 'Speichert…' : 'Unterschrift abgeben'}</button>
                <button onClick={() => { setMode('view'); setSigUrl(null); }} disabled={busy} style={ghost}>Abbrechen</button>
              </div>
            </div>
          ) : mode === 'reject' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 14, background: '#fff', border: '1px solid var(--border-1)', borderRadius: 10 }}>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} placeholder="Grund der Ablehnung (optional)"
                style={{ width: '100%', padding: '9px 11px', fontSize: 14, borderRadius: 8, border: '1px solid var(--border-1)', outline: 'none', resize: 'vertical' }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => act('reject')} disabled={busy} style={primary('#dc2626')}><X size={15} /> {busy ? 'Sendet…' : 'Ablehnen'}</button>
                <button onClick={() => setMode('view')} disabled={busy} style={ghost}>Abbrechen</button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {doc.action === 'sign' ? (
                <button onClick={() => setMode('sign')} style={primary('#2563eb')}><PenLine size={15} /> Unterschreiben</button>
              ) : (
                <button onClick={() => act('confirm')} disabled={busy} style={primary('#15803D')}><Check size={15} /> {busy ? 'Speichert…' : 'Bestätigen'}</button>
              )}
              <button onClick={() => setMode('reject')} style={outline('#dc2626')}><X size={15} /> Ablehnen</button>
            </div>
          )}
          {err && <div style={{ fontSize: 12.5, color: 'var(--danger)' }}>{err}</div>}
        </div>
      )}
    </div>
  );
}

const openBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 9, border: '1px solid var(--border-1)', background: '#fff',
  color: 'var(--fg-2)', fontSize: 13, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
};
const primary = (color: string): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 16px', borderRadius: 9,
  border: 'none', background: color, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer',
});
const outline = (color: string): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 16px', borderRadius: 9,
  border: `1px solid ${color}`, background: '#fff', color, fontSize: 14, fontWeight: 700, cursor: 'pointer',
});
const ghost: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 9,
  border: '1px solid var(--border-1)', background: '#fff', color: 'var(--fg-3)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
