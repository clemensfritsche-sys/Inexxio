'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Clock, Download, Trash2, X } from 'lucide-react';
import { api, assetUrl } from '@/lib/api';
import { statusCfg } from '@/lib/process-status';
import { when } from '@/lib/when';
import {
  DetailBody, DetailHeader, Dialog, ErrorText, MICRO_LABEL, ReadField, inputCls,
} from '@/components/erp/fields';
import { ObjectSelect } from '@/components/erp/object-select';
import { RefChips, mimeIcon } from '@/components/erp/documents';
import type { DocumentDetail as Doc } from '@/types';

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
  const [doc, setDoc] = useState<Doc | null>(null);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const readOnce = useRef(false);

  const load = useCallback(() => {
    api.getDocument(objectId).then(setDoc).catch((e: Error) => setError(e.message));
  }, [objectId]);
  useEffect(() => { load(); }, [load]);

  // **Das Lesen nachholen** – einmal, still: ohne KI freigegeben, jetzt gibt es sie.
  useEffect(() => {
    if (!doc?.read_later || readOnce.current) return;
    readOnce.current = true;
    api.readDocumentLater(objectId).then(setDoc).catch(() => {});
  }, [doc?.read_later, objectId]);

  async function act(run: () => Promise<Doc>) {
    setError('');
    try { setDoc(await run()); } catch (e) { setError((e as Error).message); }
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
                <div style={{ font: '800 16px var(--font-display)', color: 'var(--fg-1)', marginTop: 6 }}>Inhalt gelöscht</div>
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
      {deleting && (
        <DeleteDialog onClose={() => setDeleting(false)}
          onConfirm={(reason) => act(() => api.deleteDocument(doc.object_id, reason)).then(() => setDeleting(false))} />
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

function DeleteDialog({ onClose, onConfirm }: { onClose: () => void; onConfirm: (reason: string) => void }) {
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
      <button type="button" className="erp-actbtn erp-actbtn-danger" disabled={!reason.trim()}
        style={{ height: 42, justifyContent: 'center' }} onClick={() => onConfirm(reason.trim())}>
        Löschen
      </button>
    </Dialog>
  );
}
