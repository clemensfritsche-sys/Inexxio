'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Loader2, Mic, Paperclip, PenLine, X } from 'lucide-react';
import { api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { when } from '@/lib/when';
import { TYPE_META } from '@/lib/erp-record';
import { useOpenIntakes, useOpenRecordings } from '@/lib/proposals';
import { canRecord } from '@/lib/use-recorder';
import { runtime } from '@/lib/recorder';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ErrorText } from '@/components/erp/hints';
import { inputCls } from '@/components/erp/controls';
import { ObjId } from '@/components/erp/obj-id';
import { TextArea } from '@/components/form/field';
import { Filed } from '@/components/erp/capture/filed';
import { SheetHead } from '@/components/erp/capture/sheet-head';
import { RecorderView, Transcribe, recordingWord } from '@/components/erp/capture/recorder';
import type { Creatable } from '@/components/erp/feed-panel';
import type { ErpRecordType, Intake, Recording } from '@/types';

/** Der Datensatz, der beim Erfassen offen ist – der erste Hinweis für die KI (nur seine Nummer). */
export interface CaptureHint { objectId: number; label: string }

/** Wo das Blatt beginnt: bei den Knöpfen oder gleich bei «Abgelegt» einer offenen Erfassung. */
export type CaptureStart = { view: 'menu' } | { view: 'filed'; intake: Intake };

/** Neu anlegen – dieselben Wege wie bisher, in den Farben des Feeds. */
const CREATE: { type: Creatable; record: ErpRecordType; label: string }[] = [
  { type: 'person', record: 'user', label: 'Person' },
  { type: 'company', record: 'organization', label: 'Firma' },
  { type: 'article', record: 'article', label: 'Artikel' },
  { type: 'order', record: 'order', label: 'Auftrag' },
  // Scannen (mehrere Seiten) und Verfassen gibt es nur im Entwurf selbst.
  { type: 'document', record: 'document', label: 'Dokument' },
];

/**
 * ►►► **«+» = Erfassen** (Akte §4.4, Bauplan «Oberfläche»). ◄◄◄
 *
 * Oben **rund festhalten** – Aufnehmen · Foto · Datei · Schreiben (Aufnehmen nur, wo der
 * Browser es kann). Foto und Datei öffnen den bestehenden Dokument-Entwurf, der offene
 * Datensatz steht dort schon als Referenz. Schreiben geht an die KI (`POST /erp/intake`) und
 * endet in **«Abgelegt»**; Aufnehmen ebenso, nach «schreibt ab …» (Phase 4). Darunter, was
 * noch nicht abgelegt ist (Erfassungen und Aufnahmen), und unten **eckig neu anlegen** –
 * dieselben Entwürfe wie bisher.
 *
 * **Während einer Aufnahme ist das Blatt gesperrt**: kein Wegtippen, kein Escape, kein
 * Schliessen – der Weg hinaus ist «Stopp».
 *
 * Am Handy ein Blatt von unten (grosse Tippziele, das Textfeld hat sofort den Fokus); am
 * Schreibtisch dasselbe Blatt über der Liste.
 */
export function CaptureSheet({ start, hint, onClose, onCreate, onFiles }: {
  start: CaptureStart;
  hint: CaptureHint | null;
  onClose: () => void;
  onCreate: (type: Creatable) => void;
  /** Foto oder Datei gewählt – der Dokument-Entwurf übernimmt (mit dem Hinweis als Referenz). */
  onFiles: (files: File[], hint: CaptureHint | null) => void;
}) {
  const [view, setView] = useState<CaptureStart | { view: 'write' } | { view: 'record' }
    | { view: 'transcribe'; recording: Recording }>(start);
  // Der Hinweis lässt sich wegnehmen – wer am Handy aus der Liste kommt, meint vielleicht nichts.
  const [about, setAbout] = useState<CaptureHint | null>(hint);
  const locked = view.view === 'record';
  const dismiss = locked ? undefined : onClose;
  useEffect(() => {
    if (!dismiss) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss]);

  return createPortal(
    <div className="erp-capture-scrim" onClick={dismiss}>
      <div role="dialog" aria-modal="true" aria-label="Erfassen" className="erp-capture-sheet"
        onClick={(e) => e.stopPropagation()}>
        {view.view === 'menu' && (
          <Menu about={about} onDropHint={() => setAbout(null)} onClose={onClose}
            onWrite={() => setView({ view: 'write' })} onRecord={() => setView({ view: 'record' })}
            onFiles={(f) => onFiles(f, about)} onCreate={onCreate}
            onIntake={(intake) => setView({ view: 'filed', intake })}
            onRecording={(recording) => setView({ view: 'transcribe', recording })} />
        )}
        {view.view === 'record' && (
          <RecorderView hint={about?.objectId ?? null} onClose={onClose}
            onStopped={(recording) => setView({ view: 'transcribe', recording })} />
        )}
        {view.view === 'transcribe' && (
          <Transcribe recording={view.recording} onClose={onClose}
            onFiled={(intake) => setView({ view: 'filed', intake })} />
        )}
        {view.view === 'write' && (
          <Write about={about} onDropHint={() => setAbout(null)} onBack={() => setView({ view: 'menu' })}
            onClose={onClose}
            onFiled={(intake) => setView({ view: 'filed', intake })} />
        )}
        {view.view === 'filed' && <Filed intake={view.intake} onClose={onClose} />}
      </div>
    </div>,
    document.body,
  );
}

/** «zu 100000123 · Hans Muster ✕» – wohin die KI zuerst schaut. */
function HintLine({ about, onDrop }: { about: CaptureHint | null; onDrop?: () => void }) {
  if (!about) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--fg-3)', minWidth: 0 }}>
      <span style={{ flex: 'none' }}>zu</span>
      <ObjId value={about.objectId} />
      <span className="truncate" style={{ minWidth: 0 }}>{about.label}</span>
      <button type="button" onClick={onDrop} disabled={!onDrop} aria-label="Ohne diesen Datensatz"
        data-tip={onDrop ? 'Ohne diesen Datensatz' : undefined}
        style={{ display: 'flex', background: 'none', border: 'none', padding: 4, cursor: onDrop ? 'pointer' : 'default',
          color: 'var(--fg-4)', visibility: onDrop ? 'visible' : 'hidden' }}>
        <X size={13} />
      </button>
    </div>
  );
}

function Menu({ about, onDropHint, onClose, onWrite, onRecord, onFiles, onCreate, onIntake, onRecording }: {
  about: CaptureHint | null; onDropHint: () => void; onClose: () => void; onWrite: () => void;
  onRecord: () => void; onFiles: (files: File[]) => void; onCreate: (type: Creatable) => void;
  onIntake: (i: Intake) => void; onRecording: (r: Recording) => void;
}) {
  // Ein Knopf, der nie etwas kann, steht nicht da: ohne MediaRecorder kein «Aufnehmen».
  const [mic] = useState(canRecord);
  const photo = useRef<HTMLInputElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const pick = (list: FileList | null) => { if (list?.length) onFiles(Array.from(list)); };
  return (
    <>
      <SheetHead title="Erfassen" onClose={onClose} />
      <div style={{ padding: '18px 16px 20px', display: 'flex', flexDirection: 'column', gap: 18, overflowY: 'auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-around', gap: 8 }}>
            {mic && <RoundAction icon={Mic} label="Aufnehmen" onClick={onRecord} strong />}
            <RoundAction icon={Camera} label="Foto" onClick={() => photo.current?.click()} />
            <RoundAction icon={Paperclip} label="Datei" onClick={() => file.current?.click()} />
            <RoundAction icon={PenLine} label="Schreiben" onClick={onWrite} strong={!mic} />
          </div>
          <input ref={photo} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => pick(e.target.files)} />
          <input ref={file} type="file" hidden onChange={(e) => pick(e.target.files)} />
          <HintLine about={about} onDrop={onDropHint} />
        </div>
        <OpenIntakes onOpen={onIntake} onRecording={onRecording} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Neu anlegen</span>
          <div className="erp-capture-create">
            {CREATE.map(({ type, record, label }) => {
              const meta = TYPE_META[record];
              const Icon = meta.icon;
              return (
                <button key={type} type="button" onClick={() => onCreate(type)} className="erp-capture-tile"
                  style={{ background: meta.bg, color: meta.fg }}>
                  <Icon size={20} />
                  <span>{label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

/** Ein runder Knopf zum Festhalten – gross genug für den Daumen (64 px). */
function RoundAction({ icon: Icon, label, onClick, strong }: {
  icon: typeof Camera; label: string; onClick: () => void; strong?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} className="erp-capture-round">
      <span className={strong ? 'erp-capture-round-dot erp-capture-round-strong' : 'erp-capture-round-dot'}><Icon size={24} /></span>
      <span>{label}</span>
    </button>
  );
}

/** Was noch nicht abgelegt ist – antippen öffnet «Abgelegt»; eine Aufnahme, die noch
 *  abgeschrieben wird (oder fehlschlug), öffnet «schreibt ab …» und fragt weiter nach. */
function OpenIntakes({ onOpen, onRecording }: { onOpen: (i: Intake) => void; onRecording: (r: Recording) => void }) {
  const open = useOpenIntakes().data ?? [];
  // Fertige stehen schon als offene Erfassung da.
  const recordings = (useOpenRecordings().data ?? []).filter((r) => r.state !== 'done');
  if (!open.length && !recordings.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Nicht abgelegt</span>
      {recordings.map((r) => (
        <button key={`r${r.id}`} type="button" onClick={() => onRecording(r)} data-tip={r.problem ?? undefined}
          className={r.state === 'failed' ? 'erp-capture-row erp-capture-row-warn' : 'erp-capture-row'}>
          <Mic size={15} style={{ flex: 'none', color: r.state === 'failed' ? 'var(--danger)' : 'var(--fg-3)' }} />
          <span className="truncate" style={{ flex: 1, minWidth: 0 }}>
            {recordingWord(r)}{r.state === 'failed' && r.problem ? ` – ${r.problem}` : ''}
          </span>
          <span className="tabular-nums" style={{ flex: 'none', fontSize: 12, color: 'var(--fg-4)' }}>
            {runtime(r.seconds * 1000)} · {when(r.at)}
          </span>
        </button>
      ))}
      {open.map((i) => (
        <button key={`i${i.id}`} type="button" onClick={() => onOpen(i)} className="erp-capture-row">
          <PenLine size={15} style={{ flex: 'none', color: 'var(--fg-3)' }} />
          <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{i.text}</span>
          <span className="tabular-nums" style={{ flex: 'none', fontSize: 12, color: 'var(--fg-4)' }}>{when(i.at)}</span>
        </button>
      ))}
    </div>
  );
}

/**
 * **Schreiben** – ein Textfeld, sofort im Fokus; «Ablegen» (oder Ctrl/⌘+Enter) gibt es der KI.
 * Solange sie ablegt, steht der Text still da und darunter «legt ab …» – nichts springt.
 * Scheitert die Anfrage, bleibt der Text im Feld: verloren geht nichts.
 */
function Write({ about, onDropHint, onBack, onClose, onFiled }: {
  about: CaptureHint | null; onDropHint: () => void; onBack: () => void; onClose: () => void;
  onFiled: (i: Intake) => void;
}) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ready = !!text.trim() && !busy;
  async function file() {
    if (!ready) return;
    setBusy(true);
    setError('');
    try {
      onFiled(await api.intake(text.trim(), about?.objectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht abgelegt.');
      tell('Erfassung', 'Nicht abgelegt')(e);
      setBusy(false);
    }
  }
  return (
    <>
      <SheetHead title="Schreiben" onBack={busy ? undefined : onBack} onClose={onClose} />
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <TextArea name="text" value={text} onChange={setText} readOnly={busy} autoFocus rows={6}
          placeholder="Was ist passiert, was soll man wissen?" aria-label="Was festgehalten wird"
          // 16 px: darunter zoomt das iPhone beim Fokus ins Feld.
          className={inputCls} style={{ fontSize: 16, lineHeight: 1.45, resize: 'vertical' }}
          onKeyUp={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void file(); }} />
        <HintLine about={about} onDrop={busy ? undefined : onDropHint} />
        {error && <ErrorText msg={error} />}
        <button type="button" onClick={() => void file()} disabled={!ready}
          className="erp-actbtn erp-actbtn-primary" style={{ height: 48, fontSize: 15 }}>
          {busy ? <><Loader2 size={17} className="animate-spin" />legt ab …</> : 'Ablegen'}
        </button>
        {/* Der Platz steht von Anfang an – «legt ab …» schiebt nichts. */}
        <p aria-live="polite" style={{ margin: 0, minHeight: 36, fontSize: 12.5, color: 'var(--fg-3)',
          textAlign: 'center', visibility: busy ? 'visible' : 'hidden' }}>
          Die KI sucht, wohin der Text gehört – das kann bis zu einer Minute dauern.
        </p>
      </div>
    </>
  );
}
