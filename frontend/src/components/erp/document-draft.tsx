'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FileText, Loader2, PenLine, ScanLine, Sparkles, Upload } from 'lucide-react';
import { api } from '@/lib/api';
import {
  DetailBody, DetailHeader, ErrorText, HeaderAction, MICRO_LABEL, inputCls,
} from '@/components/erp/fields';
import { ObjectSelect } from '@/components/erp/object-select';
import { DocScanner } from '@/components/scan/doc-scanner';
import { ComposeChat } from '@/components/erp/compose-chat';
import { RefChip } from '@/components/erp/documents';
import {
  DocumentLayout, DocumentPaper, MicroLabel, findTargets, type TargetOption,
} from '@/components/erp/document-detail';
import type { DocumentDetail, DocumentProposal, DocumentTarget } from '@/types';

/** Woher ein Entwurf kommt – derselbe Wortschatz wie `domain/documents.SOURCES`. */
export type DraftSource = 'file' | 'scan' | 'compose' | 'mail' | 'form' | 'capture' | 'voucher';

/**
 * **Was ein Entwurf schon mitbringt**, wenn er nicht über «+» beginnt: der Anhang einer
 * Mail, das Foto der Datenerfassung, das Feld eines Moduls. Es ist trotzdem DERSELBE Entwurf
 * – ein Interface für alles.
 */
export interface DraftSeed {
  files?: Blob[];
  source?: DraftSource;
  /** Eine Zeile über den Feldern: «Aus der Mail von Peter Baumann · RE-26-4471.pdf». */
  from?: string;
  /** Der Absender, falls bekannt (Zuordnung Stufe 3). */
  sender?: number | null;
  /** Die Anforderung, aus der man kam (sie geht der Zuordnung vor). */
  hint?: string;
  /** Ein Pflichtfeld, das die Freigabe gleich setzt – mit Schloss, nicht änderbar. */
  target?: DocumentTarget & { label?: string; lock?: string };
  art?: string;
  name?: string;
}

/** Eine Referenz im Entwurf: ganzer Datensatz oder (vom Vorschlag) ein Pflichtfeld. */
interface DraftRef { object_id: number; label: string; target?: DocumentTarget; proposed?: boolean }

/**
 * ►►► **Der Entwurf eines Dokuments – lebt nur im Browser.** ◄◄◄
 *
 * Zuerst nur die drei Quellen (Scannen · Datei · Verfassen); ist die Wahl getroffen, steht
 * sie fest – wer sich vertan hat, verwirft den Entwurf. Dann liest die KI (falls es sie gibt)
 * und füllt **Art, Name und Referenz** vor; das sind gewöhnliche Felder, ohne KI tippt sie der
 * Mensch. «Freigeben» legt das Dokument an – erst dann gibt es eine Nummer (Regel 2).
 */
export function DocumentDraft({ seed, onFiled, onCancel, onOpen }: {
  seed?: DraftSeed;
  /** Freigegeben – mit dem Vorschlag, aus dem ein Modul seine Felder vorbelegt. */
  onFiled: (doc: DocumentDetail, proposal: DocumentProposal | null) => void;
  onCancel: () => void;
  /** Dieselbe Datei gibt es schon – das vorhandene Dokument öffnen. */
  onOpen?: (objectId: number) => void;
}) {
  const [files, setFiles] = useState<Blob[]>(seed?.files ?? []);
  const [source, setSource] = useState<DraftSource | null>(seed?.files?.length ? (seed.source ?? 'file') : null);
  const [art, setArt] = useState(seed?.art ?? '');
  const [name, setName] = useState(seed?.name ?? '');
  const [refs, setRefs] = useState<DraftRef[]>(seed?.target
    ? [{ object_id: seed.target.object_id, label: seed.target.label ?? String(seed.target.object_id), target: seed.target }]
    : []);
  const [proposal, setProposal] = useState<DocumentProposal | null>(null);
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [existing, setExisting] = useState<DocumentDetail | null>(null);
  /** Wer unterschreiben soll – beim Verfassen von der KI vorgeschlagen, sonst von Hand. */
  const [signers, setSigners] = useState<SignerRef[]>([]);
  /** Das verfasste Papier (Quelle «Verfassen») – es ist die Datei. */
  const [composed, setComposed] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [scanning, setScanning] = useState(false);

  // **Lesen, sobald es eine Datei gibt** – einmal je Entwurf. Gespeichert wird dabei nichts.
  // Ein verfasstes Papier liest niemand nach: die KI hat es eben geschrieben.
  useEffect(() => {
    if (!files.length || source === 'compose') return;
    let gone = false;
    setReading(true);
    api.readDraft(files, { sender: seed?.sender ?? null, hint: seed?.hint })
      .then((p) => {
        if (gone) return;
        setProposal(p);
        setArt((a) => a || p.art);
        setName((n) => n || p.name);
        setRefs((have) => {
          if (have.some((r) => r.target)) return have;
          const fresh = (p.refs ?? []).map((r): DraftRef => ({
            object_id: r.object_id, label: r.label, proposed: true,
            target: r.field ? { object_id: r.object_id, part: r.part ?? null, field: r.field, extra: {} } : undefined,
          }));
          return [...have, ...fresh.filter((f) => !have.some((h) => h.object_id === f.object_id))];
        });
      })
      .catch(() => { /* ohne Vorschlag geht es auch */ })
      .finally(() => { if (!gone) setReading(false); });
    return () => { gone = true; };
  }, [files, source, seed?.sender, seed?.hint]);

  const first = useMemo(() => files.slice(0, 1), [files]);
  const preview = useObjectUrls(first)[0] ?? null;

  function choose(list: FileList | null, how: DraftSource) {
    if (!list?.length) return;
    setSource(how);
    setFiles(Array.from(list));
  }

  async function release() {
    setBusy(true);
    setError('');
    try {
      const target = refs.find((r) => r.target)?.target ?? null;
      const res = await api.fileDocument(files, {
        art: art.trim(), name: name.trim(), source: source ?? 'file',
        refs: refs.filter((r) => !r.target).map((r) => r.object_id), target,
        text: proposal?.text, keywords: proposal?.keywords,
        facts: proposal?.facts as Record<string, unknown> | undefined,
        signers: signers.map((x) => x.object_id),
      });
      // Dieselbe Datei gibt es schon: mit einem Feld ist sie jetzt dort (der Dienst hat es
      // gesetzt), ohne Feld bietet die Seite das vorhandene Dokument an.
      if (res.existed && !target) setExisting(res.document);
      else onFiled(res.document, proposal);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = files.length > 0 && art.trim() && name.trim() && !busy;
  const why = !files.length ? 'Erst eine Quelle wählen.' : !art.trim() || !name.trim()
    ? 'Art und Name sind Pflicht – ohne KI tippt man sie selbst.' : undefined;
  const mime = files[0]?.type || (files.length > 1 ? 'application/pdf' : '');
  const lockOf = (r: DraftRef) => (r.target ? (seed?.target?.lock ?? (r.proposed ? null : 'Feld des Datensatzes')) : null);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <DetailHeader type="document" title={art || name ? `${art || '…'} · ${name || '…'}` : null}
        placeholder="Neues Dokument" objectIdText="—" objectIdHint="Die Nummer entsteht mit der Freigabe."
        onBack={onCancel}
        actions={<>
          <HeaderAction label={busy ? 'Freigeben…' : 'Freigeben'} disabled={!ready} hint={why} onClick={release} />
          <HeaderAction label="Verwerfen" tone="neutral" onClick={onCancel} />
        </>} />
      <div className="flex-1 overflow-y-auto" style={{ background: 'var(--bg-2)', padding: '24px clamp(14px, 4vw, 28px) 88px' }}>
        <DetailBody gap={22}>
          {error && <ErrorText msg={error} />}
          {existing && (
            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 12,
                          padding: 18, display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <FileText size={20} style={{ color: 'var(--accent)' }} />
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ font: '700 15px var(--font-body)', color: 'var(--fg-1)' }}>Diese Datei gibt es schon</div>
                <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{existing.art} · {existing.name}</div>
              </div>
              <HeaderAction label="Öffnen" onClick={() => (onOpen ? onOpen(existing.object_id) : onFiled(existing, proposal))} />
            </div>
          )}
          <input ref={picker} type="file" hidden onChange={(e) => choose(e.target.files, 'file')} />
          {scanning && (
            <DocScanner onCancel={() => setScanning(false)} onDone={(pages) => {
              setScanning(false);
              setSource('scan');
              setFiles(pages.map((b, i) => new File([b], `seite-${i + 1}.jpg`, { type: 'image/jpeg' })));
            }} />
          )}
          {!source && (
            <SourceTiles onScan={() => setScanning(true)} onFile={() => picker.current?.click()}
              onCompose={() => setSource('compose')} />
          )}
          {(files.length > 0 || source === 'compose') && (
            <DocumentLayout paper={source === 'compose'
              ? (composed ? <DocumentPaper url={null} mime="text/html" html={composed} /> : <ComposeHint />)
              : files.length > 1 && files.every((f) => f.type.startsWith('image/'))
                ? <Pages files={files} />
                : <DocumentPaper url={preview} mime={mime} filename={(files[0] as File).name} />}>
              {seed?.from && <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{seed.from}</div>}
              <label style={{ display: 'flex', flexDirection: 'column' }}>
                <MicroLabel>Art *</MicroLabel>
                <input className={inputCls} value={art} maxLength={80} placeholder="z. B. Lieferantenrechnung"
                  onChange={(e) => setArt(e.target.value)} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column' }}>
                <MicroLabel>Name *</MicroLabel>
                <input className={inputCls} value={name} maxLength={200}
                  placeholder="was es von anderen derselben Art unterscheidet"
                  onChange={(e) => setName(e.target.value)} />
              </label>
              <div>
                <MicroLabel>Referenz</MicroLabel>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {refs.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {refs.map((r) => (
                        <RefChip key={`${r.object_id}-${r.target?.field ?? ''}`} objectId={r.object_id} label={r.label}
                          proposed={r.proposed} lockTip={lockOf(r)}
                          onRemove={() => setRefs((rs) => rs.filter((x) => x !== r))} />
                      ))}
                    </div>
                  )}
                  <ObjectSelect<TargetOption> value={null} find={findTargets}
                    placeholder={refs.length ? 'Weiterer Datensatz – Nummer oder Name' : 'Datensatz – Nummer oder Name'}
                    onChange={(id, opt) => {
                      if (id && !refs.some((r) => r.object_id === id)) {
                        setRefs((rs) => [...rs, { object_id: id, label: opt?.name ?? String(id) }]);
                      }
                    }} />
                  {reading && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--fg-3)' }}>
                      <Loader2 size={14} className="animate-spin" /> Die KI liest … dann steht hier ihr Vorschlag.
                    </span>
                  )}
                  {!reading && proposal?.why && (
                    <span style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12.5, lineHeight: 1.45,
                                   color: 'var(--fg-2)', background: 'var(--warning-bg)', borderRadius: 8, padding: '8px 10px' }}>
                      <Sparkles size={14} style={{ color: 'var(--warning)', flex: 'none', marginTop: 2 }} />
                      <span><b style={{ color: 'var(--fg-1)' }}>Vorschlag{proposal.read ? ' der KI' : ''}.</b> {proposal.why}</span>
                    </span>
                  )}
                  {!reading && proposal && !proposal.read && (
                    <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
                      {proposal.ai_problem || (proposal.ai ? 'Die KI konnte diese Datei nicht lesen.' : 'Keine KI verfügbar.')}
                      {' '}Art und Name selbst eintragen.
                    </span>
                  )}
                </div>
              </div>
              <Signers signers={signers} onChange={setSigners} />
              {source === 'compose' && (
                <div>
                  <MicroLabel>Verfassen</MicroLabel>
                  <ComposeChat onPaper={(p) => {
                    setComposed(p.html);
                    setFiles([new File([p.html], `${p.art || 'Dokument'}.html`, { type: 'text/html' })]);
                    if (p.art) setArt(p.art);
                    if (p.name) setName(p.name);
                    setSigners((have) => [...have, ...p.signers.filter((x) => !have.some((h) => h.object_id === x.object_id))]);
                  }} />
                </div>
              )}
            </DocumentLayout>
          )}
        </DetailBody>
      </div>
    </div>
  );
}

/** Eine Person, die unterschreiben soll. */
interface SignerRef { object_id: number; name: string }

/**
 * **Wer unterschreiben soll** – mit der Freigabe verlangt; hinaus geht die Bitte mit «Senden».
 * Beim Verfassen steht für jeden eine Linie auf dem Papier.
 */
function Signers({ signers, onChange }: { signers: SignerRef[]; onChange: (s: SignerRef[]) => void }) {
  return (
    <div>
      <MicroLabel>Unterschreiben</MicroLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {signers.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {signers.map((x) => (
              <RefChip key={x.object_id} objectId={x.object_id} label={x.name}
                onRemove={() => onChange(signers.filter((y) => y.object_id !== x.object_id))} />
            ))}
          </div>
        )}
        <ObjectSelect<SignerRef> value={null} find={(q) => api.searchPeople(q, 20)}
          placeholder="Person – Nummer oder Name (niemand: leer lassen)"
          onChange={(id, opt) => {
            if (id && !signers.some((x) => x.object_id === id)) onChange([...signers, { object_id: id, name: opt?.name ?? String(id) }]);
          }} />
      </div>
    </div>
  );
}

function ComposeHint() {
  return (
    <div style={{ width: '100%', maxWidth: 440, aspectRatio: '210 / 297', border: '1.5px dashed var(--border-2)',
                  borderRadius: 4, display: 'grid', placeItems: 'center', padding: 24, textAlign: 'center',
                  fontSize: 13, color: 'var(--fg-3)' }}>
      Hier steht das Papier, sobald die KI es geschrieben hat.
    </div>
  );
}

/** Die drei Quellen – zu Beginn das Einzige, was zu sehen ist. */
function SourceTiles({ onScan, onFile, onCompose }: {
  onScan: () => void; onFile: () => void; onCompose: () => void;
}) {
  const tiles: Array<[string, string, React.ElementType, (() => void) | undefined]> = [
    ['Scannen', 'Kamera, mehrere Seiten', ScanLine, onScan],
    ['Datei', 'PDF, Bild, Excel, Video …', Upload, onFile],
    ['Verfassen', 'im Chat mit der KI', PenLine, onCompose],
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
      {tiles.map(([label, sub, Icon, run]) => (
        <button key={label} type="button" onClick={run} disabled={!run}
          data-tip={run ? undefined : 'Verfassen braucht die KI'}
          style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', borderRadius: 'var(--r-md)',
                   padding: '18px 12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                   textAlign: 'center', cursor: run ? 'pointer' : 'not-allowed', opacity: run ? 1 : 0.5,
                   boxShadow: 'var(--shadow-sm)' }}>
          <span style={{ width: 40, height: 40, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                         background: '#EEEAF4', color: '#6B5A8E' }}><Icon size={19} /></span>
          <span style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)' }}>{label}</span>
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{sub}</span>
        </button>
      ))}
    </div>
  );
}

/** Gescannte Seiten nebeneinander – beim Freigeben werden sie ein PDF. */
function Pages({ files }: { files: Blob[] }) {
  const urls = useObjectUrls(files);
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
      {urls.map((u, i) => (
        <div key={u} style={{ position: 'relative', width: 120 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={u} alt="" style={{ width: 120, aspectRatio: '210 / 297', objectFit: 'cover', objectPosition: 'top',
                                       border: '1px solid var(--border-2)', borderRadius: 4, background: '#fff' }} />
          <span style={{ ...MICRO_LABEL, position: 'absolute', left: 6, bottom: 4, color: 'var(--fg-3)' }}>{i + 1}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * **Derselbe Entwurf über einer anderen Seite** – wenn er aus einem Modul, einer Mail oder
 * der Zeiterfassung kommt. Kein zweites Interface: der Rahmen ist neu, der Inhalt derselbe.
 */
export function DraftSheet(props: React.ComponentProps<typeof DocumentDraft>) {
  // An `body` gehängt: ein Vorfahr mit `transform` (eine Modul-Karte) machte aus «fixed» sonst
  // «in der Karte».
  return <Sheet><DocumentDraft {...props} /></Sheet>;
}

/** **Ein Blatt über der ganzen Seite** – Entwurf, Vorschau eines Papiers. */
export function Sheet({ children }: { children: React.ReactNode }) {
  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 55, display: 'flex', flexDirection: 'column',
                  background: 'var(--bg-2)', paddingTop: 'env(safe-area-inset-top, 0px)' }}>
      {children}
    </div>,
    document.body,
  );
}

/**
 * **Adressen für Dateien im Browser** – angelegt und freigegeben im selben Effekt. Mit
 * `useMemo` angelegt und im Aufräumen freigegeben, blieb nach einem zweiten Lauf des Effekts
 * (StrictMode) eine freigegebene Adresse stehen: das Bild war kaputt.
 */
function useObjectUrls(files: Blob[]): string[] {
  const [urls, setUrls] = useState<string[]>([]);
  useEffect(() => {
    const made = files.map((f) => URL.createObjectURL(f));
    setUrls(made);
    return () => made.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);
  return urls;
}
