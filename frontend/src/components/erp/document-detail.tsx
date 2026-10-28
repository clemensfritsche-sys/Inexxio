'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Clock, Download, Send, Trash2, X } from 'lucide-react';
import { api, assetUrl } from '@/lib/api';
import { qk } from '@/lib/queries';
import { statusCfg } from '@/lib/process-status';
import { when } from '@/lib/when';
import { DetailBody, DetailHeader, ReadField } from '@/components/erp/detail-frame';
import { Dialog, inputCls } from '@/components/erp/controls';
import { ErrorText } from '@/components/erp/hints';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ObjectSelect } from '@/components/erp/object-select';
import { RefChip, RefChips, mimeIcon } from '@/components/erp/documents';
import type { DocumentDetail as Doc } from '@/types';
import { tell } from '@/lib/notice';

/** Ein Datensatz zum Referenzieren – in der Form, die `ObjectSelect` kennt. */
export interface TargetOption { object_id: number; name: string }

export const findTargets = (q: string): Promise<TargetOption[]> =>
  api.documentTargets(q).then((rows) => rows.map((r) => ({ object_id: r.object_id, name: r.label })));

/**
 * ►►► **Das Papier – so, wie die Datei ist.** ◄◄◄ Ein Papier aus unserer Vorlage (Beleg,
 * Verfasstes) als HTML in einem abgeschirmten Rahmen, ein PDF im Betrachter des Browsers, ein
 * Bild als Bild; alles andere als Kachel zum Herunterladen.
 */
export function DocumentPaper({ url, mime, html, filename }: {
  url: string | null; mime: string; html?: string | null; filename?: string | null;
}) {
  const box: React.CSSProperties = {
    width: '100%', maxWidth: 440, border: '1px solid var(--border-1)', borderRadius: 4,
    background: '#fff', boxShadow: '0 1px 2px rgba(10,10,11,.06), 0 12px 40px rgba(10,10,11,.10)',
  };
  if (html) {
    return <iframe title="Dokument" sandbox="" srcDoc={html} style={{ ...box, aspectRatio: '210 / 297', display: 'block' }} />;
  }
  if (url && mime === 'application/pdf') {
    return <iframe title="Dokument" src={url} style={{ ...box, aspectRatio: '210 / 297', display: 'block' }} />;
  }
  if (url && mime.startsWith('image/')) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={filename ?? ''} style={{ ...box, display: 'block', height: 'auto' }} />;
  }
  if (url && mime.startsWith('video/')) {
    return <video src={url} controls style={{ ...box, display: 'block' }} />;
  }
  const Icon = mimeIcon(mime);
  return (
    <div style={{ ...box, aspectRatio: '210 / 297', display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: 10, color: 'var(--fg-3)' }}>
      <Icon size={34} />
      <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-2)', textAlign: 'center',
                     padding: '0 16px', overflowWrap: 'anywhere' }}>{filename || mime}</span>
    </div>
  );
}

/** Die zwei Spalten einer Dokumentseite: Papier links, Angaben rechts – schmal untereinander. */
export function DocumentLayout({ paper, children }: { paper: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
                  gap: 32, alignItems: 'start' }}>
      <div style={{ display: 'flex', justifyContent: 'center' }}>{paper}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22, minWidth: 0 }}>{children}</div>
    </div>
  );
}

export function MicroLabel({ children }: { children: React.ReactNode }) {
  return <div style={{ ...MICRO_LABEL, marginBottom: 6 }}>{children}</div>;
}

/**
 * ►►► **Die Seite eines Dokuments.** ◄◄◄ Fest sind Datei, Art und Name; ändern lassen sich nur
 * die Referenzen. «Löschen» steht erst da, wenn das Dokument nirgends mehr hängt – vorher
 * nennt der Hover den Grund (Regel 8, `can` als Satz vom Server).
 */
export function DocumentDetail({ objectId, onBack }: { objectId: number; onBack: () => void }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: qk.document(objectId),
    queryFn: ({ signal }) => api.getDocument(objectId, { signal }),
    meta: { what: 'Dokument' },
  });
  const doc = query.data ?? null;
  // Die Antwort einer Handlung IST das Dokument – sie geht direkt in den Cache.
  const setDoc = useCallback((d: Doc) => { qc.setQueryData(qk.document(objectId), d); }, [qc, objectId]);
  const [failed, setError] = useState('');
  const error = failed || (!doc && query.error ? query.error.message : '');
  const [deleting, setDeleting] = useState(false);
  const [sending, setSending] = useState(false);
  const readOnce = useRef(false);

  // **Das Lesen nachholen** – einmal, still: ohne KI freigegeben, jetzt gibt es sie.
  useEffect(() => {
    if (!doc?.read_later || readOnce.current) return;
    readOnce.current = true;
    api.readDocumentLater(objectId).then(setDoc).catch(tell('Dokument', 'Nicht gelesen'));
  }, [doc?.read_later, objectId, setDoc]);

  /** Eine Handlung – `true`, wenn sie ging; sonst steht der Grund da und ein Dialog bleibt offen. */
  async function act(run: () => Promise<Doc>): Promise<boolean> {
    setError('');
    try { setDoc(await run()); return true; } catch (e) { setError((e as Error).message); return false; }
  }

  if (!doc) {
    return <div className="flex-1 flex items-center justify-center text-sm text-fg-4">{error || 'Laden…'}</div>;
  }
  const deleted = !!doc.deleted_at;
  const url = doc.file_url ? assetUrl(doc.file_url) : null;
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <DetailHeader type="document" title={`${doc.art} · ${doc.name}`} objectId={doc.object_id}
        status={statusCfg(doc.status)} onBack={onBack}
        actions={!deleted && (
          <>
            {url && (
              <a className="erp-idbtn" href={url} download={doc.filename ?? undefined} target="_blank" rel="noreferrer"
                data-tip="Herunterladen" aria-label="Herunterladen" style={{ width: 28, height: 28 }}>
                <Download size={15} />
              </a>
            )}
            <button type="button" className="erp-idbtn" style={{ width: 28, height: 28 }}
              aria-label="Senden" data-tip="Senden – je Empfänger ein Link, auf Wunsch zum Unterschreiben"
              onClick={() => setSending(true)}>
              <Send size={15} />
            </button>
            <button type="button" className="erp-idbtn erp-idbtn-danger" style={{ width: 28, height: 28 }}
              disabled={!!doc.delete_problem} aria-label="Löschen"
              data-tip={doc.delete_problem ?? 'Löschen'} onClick={() => setDeleting(true)}>
              <Trash2 size={15} />
            </button>
          </>
        )} />
      <div className="flex-1 overflow-y-auto" style={{ background: 'var(--bg-2)', padding: '24px clamp(14px, 4vw, 28px) 88px' }}>
        <DetailBody gap={22}>
          {error && <ErrorText msg={error} />}
          {deleted ? (
            <>
              <div style={{ border: '1.5px dashed var(--border-2)', borderRadius: 12, padding: 30, textAlign: 'center' }}>
                <Trash2 size={22} style={{ color: 'var(--fg-3)' }} />
                <div style={{ font: '600 16px var(--font-display)', color: 'var(--fg-1)', marginTop: 6 }}>Inhalt gelöscht</div>
                <div style={{ fontSize: 13, color: 'var(--fg-3)', marginTop: 4 }}>
                  {when(doc.deleted_at)}{doc.deleted_by ? ` von ${doc.deleted_by}` : ''} · Grund: «{doc.delete_reason}»
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 22 }}>
                <ReadField label="Art" value={doc.art} />
                <ReadField label="Name" value={doc.name} />
              </div>
            </>
          ) : (
            <DocumentLayout paper={<DocumentPaper url={url} mime={doc.mime} html={doc.html} filename={doc.filename} />}>
              <ReadField label="Art" value={doc.art} />
              <div>
                <MicroLabel>Referenz</MicroLabel>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <RefChips refs={doc.refs ?? []}
                    onRemove={(refId) => act(() => api.removeDocumentRef(doc.object_id, refId))} />
                  <ObjectSelect<TargetOption> value={null} find={findTargets}
                    placeholder={doc.refs?.length ? 'Weiterer Datensatz – Nummer oder Name' : 'Datensatz – Nummer oder Name'}
                    onChange={(id) => { if (id) act(() => api.addDocumentRef(doc.object_id, id)); }} />
                </div>
              </div>
              <Signatures doc={doc} />
            </DocumentLayout>
          )}
        </DetailBody>
      </div>
      {sending && (
        <SendDialog doc={doc} error={failed} onClose={() => { setSending(false); setError(''); }}
          onSend={(to, sign, note) => act(() => api.sendDocument(doc.object_id, to, sign, note))
            .then((ok) => { if (ok) setSending(false); })} />
      )}
      {deleting && (
        <DeleteDialog error={failed} onClose={() => { setDeleting(false); setError(''); }}
          onConfirm={(reason) => act(() => api.deleteDocument(doc.object_id, reason))
            .then((ok) => { if (ok) setDeleting(false); })} />
      )}
    </div>
  );
}

/** Wer unterschreiben soll, und wer es getan hat – sichtbar ist die Unterschrift im Papier. */
function Signatures({ doc }: { doc: Doc }) {
  const sigs = doc.signatures ?? [];
  if (!sigs.length) return null;
  return (
    <div>
      <MicroLabel>Unterschriften</MicroLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, font: '500 13.5px var(--font-body)' }}>
        {sigs.map((s) => (
          <span key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 6,
            color: s.signed_at ? 'var(--success)' : s.declined_at ? 'var(--danger)' : 'var(--fg-3)' }}>
            {s.signed_at ? <Check size={14} /> : s.declined_at ? <X size={14} /> : <Clock size={14} />} {s.name}
            {s.signed_at ? ` · ${when(s.signed_at)}` : s.declined_at ? ` · «${s.reason ?? ''}»` : ' · angefragt'}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * **Senden** – an wen (Personen mit E-Mail), ob sie unterschreiben sollen, ein Satz dazu. Je
 * Empfänger ein Link ohne Ablauf; die Mail steht im Verlauf der Person.
 */
function SendDialog({ doc, error, onClose, onSend }: {
  doc: Doc; error: string; onClose: () => void; onSend: (to: number[], sign: boolean, note: string) => void;
}) {
  const open = (doc.signatures ?? []).filter((x) => !x.signed_at && !x.declined_at);
  const [to, setTo] = useState<{ object_id: number; name: string }[]>(
    open.map((x) => ({ object_id: x.person_object_id, name: x.name })));
  const [sign, setSign] = useState(open.length > 0);
  const [note, setNote] = useState('');
  return (
    <Dialog icon={Send} title="Senden" width={520} onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={MICRO_LABEL}>An</span>
        {to.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {to.map((x) => (
              <RefChip key={x.object_id} objectId={x.object_id} label={x.name}
                onRemove={() => setTo(to.filter((y) => y.object_id !== x.object_id))} />
            ))}
          </div>
        )}
        <ObjectSelect<{ object_id: number; name: string }> value={null} find={(q) => api.searchPeople(q, 20)}
          placeholder="Person – Nummer oder Name"
          onChange={(id, opt) => { if (id && !to.some((x) => x.object_id === id)) setTo([...to, { object_id: id, name: opt?.name ?? String(id) }]); }} />
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5, color: 'var(--fg-1)' }}>
        <input type="checkbox" checked={sign} onChange={(e) => setSign(e.target.checked)} />
        Sie sollen unterschreiben
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={MICRO_LABEL}>Ein Satz dazu</span>
        <textarea className={inputCls} rows={3} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder="z. B. Bitte bis Freitag unterschreiben." />
      </label>
      {error && <ErrorText msg={error} />}
      <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!to.length}
        style={{ height: 42, justifyContent: 'center' }} onClick={() => onSend(to.map((x) => x.object_id), sign, note.trim())}>
        <Send size={15} /> Senden{to.length > 1 ? ` (${to.length})` : ''}
      </button>
    </Dialog>
  );
}

function DeleteDialog({ error, onClose, onConfirm }: {
  error: string; onClose: () => void; onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  return (
    <Dialog icon={Trash2} title="Löschen" tone="var(--danger)" width={480} onClose={onClose}>
      <div style={{ background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 10, padding: '10px 12px', fontSize: 13 }}>
        Nicht umkehrbar: Datei und Text sind danach weg. Der Datensatz bleibt mit Art und Name.
      </div>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={MICRO_LABEL}>Grund</span>
        <input className={inputCls} value={reason} autoFocus maxLength={300}
          onChange={(e) => setReason(e.target.value)} placeholder="Warum wird es gelöscht?" />
      </label>
      {error && <ErrorText msg={error} />}
      <button type="button" className="erp-actbtn erp-actbtn-danger" disabled={!reason.trim()}
        style={{ height: 42, justifyContent: 'center' }} onClick={() => onConfirm(reason.trim())}>
        Löschen
      </button>
    </Dialog>
  );
}
