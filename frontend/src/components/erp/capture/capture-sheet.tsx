'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, ArrowUp, Camera, ChevronRight, FileText, Mic, MapPin, PenLine, X } from 'lucide-react';
import { api } from '@/lib/api';
import { notify, tell } from '@/lib/notice';
import { when } from '@/lib/when';
import { TYPE_META } from '@/lib/erp-record';
import { useOpenIntakes, useOpenRecordings } from '@/lib/proposals';
import { canRecord } from '@/lib/use-recorder';
import { runtime } from '@/lib/recorder';
import { follow } from '@/lib/transcribe';
import { PIN_UI, describePlace, pickPlace, pinHome } from '@/lib/pin-point';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { TextArea } from '@/components/form/field';
import { FiledBody } from '@/components/erp/capture/filed';
import { RecordingStrip, recordingWord } from '@/components/erp/capture/recorder';
import type { Creatable } from '@/components/erp/feed-panel';
import type { ErpRecordType, Intake, Recording } from '@/types';

/** Der Datensatz, der beim Erfassen offen ist – der erste Hinweis für die KI (nur seine Nummer). */
export interface CaptureHint { objectId: number; label: string }

/** Wo die Stecknadel zeigt: im eigenen Fenster (ERP) oder im Fenster dahinter (Website). */
export interface PinHost { doc: Document; win: Window; hide: () => void; show: () => void }

/** Neu anlegen – dieselben Wege wie bisher, in den Farben des Feeds. */
const CREATE: { type: Creatable; record: ErpRecordType; label: string }[] = [
  { type: 'person', record: 'user', label: 'Person' },
  { type: 'company', record: 'organization', label: 'Firma' },
  { type: 'article', record: 'article', label: 'Artikel' },
  { type: 'order', record: 'order', label: 'Auftrag' },
  { type: 'document', record: 'document', label: 'Dokument' },
];

/**
 * Was das «+» gerade tut – EIN Zustand: bereit · nimmt auf · arbeitet (die KI legt ab, eine
 * Aufnahme wird abgeschrieben) · das Ergebnis («Abgelegt») · eine gescheiterte Aufnahme.
 */
type Phase =
  | { k: 'idle' }
  | { k: 'recording' }
  | { k: 'working'; recording?: Recording }
  | { k: 'result'; intake: Intake }
  | { k: 'failed'; recording: Recording };

/**
 * ►►► **«+» = Erfassen – EINE Ansicht, wie das Eingabefeld bei Claude.** ◄◄◄
 *
 * Oben die Eingabe: schreiben (Enter = ab an die KI, Umschalt+Enter = neue Zeile), 📷 Foto und
 * 📄 Datei (beide springen in den **Dokument-Entwurf** – Kamera mit Blatterkennung bzw.
 * Dateiwahl, der offene Datensatz als Referenz), 📌 Stecknadel (auf eine Stelle der Oberfläche
 * zeigen – eine Rückmeldung zur Software, Notiz am Artikel «ERP» bzw. «Website»), 🎤 Aufnehmen.
 * Darunter, was nicht abgelegt ist, und «Neu anlegen» wie bisher.
 *
 * **Das Fenster ändert sich nie** – man arbeitet nur darin: die Aufnahme läuft *im* Feld (Punkt,
 * Zeit, Pegel; Absenden wird Stopp), danach steht das Skeleton genau dort, wo «Abgelegt»
 * erscheint, und füllt sich. «Stimmt so» oder «Verwerfen», dann ist das Feld wieder frei.
 * Was gerade nicht geht, wird blass – nichts verschwindet, nichts springt.
 *
 * Schliessen (daneben tippen, Esc) geht immer, **ausser während einer Aufnahme** (der Weg hinaus
 * ist Stopp). Schliesst man, während die KI arbeitet, läuft es weiter und meldet sich; es steht
 * dann im «+» unter «Nicht abgelegt» (die Zahl am Knopf).
 */
export function CaptureSheet({ hint, onClose, onCreate, onFiles, onFileJump, onScan, host }: {
  hint: CaptureHint | null;
  onClose: () => void;
  onCreate: (type: Creatable) => void;
  /** Datei gewählt – der Dokument-Entwurf übernimmt (mit dem Hinweis als Referenz). */
  onFiles: (files: File[], hint: CaptureHint | null) => void;
  /** Statt der Dateiwahl hier gleich in den Entwurf springen (eingebettet: die Datei lässt sich
   *  nicht ins ERP mitnehmen, also wird sie dort gewählt). */
  onFileJump?: () => void;
  /** Foto – der Dokument-Entwurf beginnt mit der Kamera. */
  onScan: (hint: CaptureHint | null) => void;
  /** Wo die Stecknadel zeigt (Vorgabe: dieses Fenster). */
  host?: PinHost;
}) {
  const [phase, setPhase] = useState<Phase>({ k: 'idle' });
  const [about, setAbout] = useState<CaptureHint | null>(hint);
  const [place, setPlace] = useState('');
  const [picking, setPicking] = useState(false);
  const [problem, setProblem] = useState('');
  /** Die Stecknadel fand den Artikel der Software nicht – leise gesagt, nicht verschwiegen. */
  const [homeless, setHomeless] = useState('');
  const alive = useAlive();
  const locked = phase.k === 'recording';
  const dismiss = locked ? undefined : onClose;

  useEffect(() => {
    if (!dismiss || picking) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss, picking]);

  const reset = () => { setPhase({ k: 'idle' }); setPlace(''); setAbout(hint); setProblem(''); setHomeless(''); };
  const pin = usePin({ host, hint, setPicking, setPlace, setAbout, setHomeless });

  /** Text an die KI – kommt die Antwort, nachdem das «+» zu ist, meldet es sich. */
  async function send(text: string): Promise<boolean> {
    const body = place ? `${place}\n\n${text}` : text;
    setPhase({ k: 'working' });
    setProblem('');
    try {
      const intake = await api.intake(body, about?.objectId);
      if (alive.current) setPhase({ k: 'result', intake });
      else notify('Erfassung abgelegt bereit – sie wartet im «+» auf «Stimmt so».', Date.now(), { tone: 'info' });
      return true;
    } catch (e) {
      tell('Erfassung', 'Nicht abgelegt')(e);
      if (alive.current) {
        setPhase({ k: 'idle' });
        setProblem(e instanceof Error ? e.message : 'Nicht abgelegt.');
      }
      return false;
    }
  }

  function transcribe(recording: Recording) {
    setPhase({ k: 'working', recording });
    setProblem('');
  }

  if (picking) return null;
  return createPortal(
    <div className="erp-capture-scrim" onClick={dismiss}>
      <div role="dialog" aria-modal="true" aria-label="Erfassen" className="erp-capture-sheet"
        {...{ [PIN_UI]: 'true' }} onClick={(e) => e.stopPropagation()}>
        <div className="erp-capture-body">
          <Composer phase={phase} place={place} about={about} onDropPlace={() => { setPlace(''); setAbout(hint); setHomeless(''); }}
            onSend={send} onScan={() => onScan(about)} onFiles={(f) => onFiles(f, about)} onFileJump={onFileJump} onPin={pin}
            onRecord={() => { setProblem(''); setPhase({ k: 'recording' }); }}
            onStopped={transcribe} onMicFailed={(why) => { setPhase({ k: 'idle' }); setProblem(why); }} />
          <HintLine about={about} onDrop={phase.k === 'idle' && about ? () => setAbout(null) : undefined} />
          {homeless && <p className="erp-capture-hint" style={{ marginTop: -6 }}>{homeless}</p>}
          {problem && <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{problem}</p>}
          <Work phase={phase} alive={alive} onDone={reset} onClose={onClose}
            onResult={(intake) => setPhase({ k: 'result', intake })}
            onFailed={(recording) => setPhase({ k: 'failed', recording })} />
          <div className="erp-capture-rest" aria-disabled={phase.k !== 'idle' || undefined}>
            <OpenList onIntake={(intake) => setPhase({ k: 'result', intake })}
              onRecording={(r) => setPhase(r.state === 'failed' ? { k: 'failed', recording: r } : { k: 'working', recording: r })} />
            <CreateTiles onCreate={onCreate} />
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Lebt das Fenster noch? (Eine Antwort, die nach dem Schliessen kommt, meldet sich.) */
function useAlive() {
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  return alive;
}

/**
 * ►► **Die Stecknadel** – das «+» tritt beiseite, man zeigt auf die Stelle, das «+» kommt
 * zurück mit «Stelle: …» im Feld. Der Hinweis wird der Artikel der Software («ERP» auf
 * `/erp`, sonst «Website»); gibt es ihn (noch) nicht, legt die KI ab, wo es passt. ◄◄
 */
function usePin({ host, hint, setPicking, setPlace, setAbout, setHomeless }: {
  host?: PinHost; hint: CaptureHint | null; setPicking: (b: boolean) => void;
  setPlace: (s: string) => void; setAbout: (h: CaptureHint | null) => void; setHomeless: (s: string) => void;
}) {
  return () => {
    const where = host ?? { doc: document, win: window, hide: () => undefined, show: () => undefined };
    setPicking(true);
    where.hide();
    const back = () => { where.show(); setPicking(false); };
    // Erst nach diesem Klick zeigen – sonst wählte der Klick auf 📌 schon die Stelle.
    window.setTimeout(() => {
      pickPlace(where.doc, (el) => {
        setPlace(describePlace(el, hint?.objectId, where.win));
        back();
        const name = pinHome(where.win.location.pathname);
        void homeOf(name).then((home) => {
          setAbout(home);
          setHomeless(home ? '' : `Den Artikel «${name}» gibt es noch nicht – die KI legt es ab, wo es passt.`);
        }, (e: unknown) => {
          tell(`Artikel «${name}»`, 'Nicht gefunden')(e);
          setAbout(null);
        });
      }, back);
    }, 0);
  };
}

/** Der Artikel, der die Software ist («ERP», «Website») – gesucht wie jedes Referenzfeld. */
async function homeOf(name: string): Promise<CaptureHint | null> {
  const found = await api.documentTargets(name);
  const hit = found.find((r) => r.type === 'article' && r.label.trim().toLowerCase()
    .replace(/^artikel\s*·\s*/, '') === name.toLowerCase());
  return hit ? { objectId: hit.object_id, label: name } : null;
}

/** «zu 100000123 · Hans Muster ✕» – wohin die KI zuerst schaut. */
function HintLine({ about, onDrop }: { about: CaptureHint | null; onDrop?: () => void }) {
  if (!about) return null;
  return (
    <div className="erp-capture-hint">
      <span style={{ flex: 'none' }}>zu</span>
      <ObjId value={about.objectId} />
      <span className="truncate" style={{ minWidth: 0 }}>{about.label}</span>
      {onDrop && (
        <button type="button" onClick={onDrop} aria-label="Ohne diesen Datensatz" data-tip="Ohne diesen Datensatz"
          className="erp-capture-x"><X size={13} /></button>
      )}
    </div>
  );
}

/**
 * ►► **Die Eingabe** – Text, darunter die Leiste: 📷 📄 📌 … 🎤 ➤. Während einer Aufnahme ist
 * sie die Aufnahme (`RecordingStrip`); während die KI arbeitet, wartet sie leer. ◄◄
 */
function Composer({ phase, place, about, onDropPlace, onSend, onScan, onFiles, onFileJump, onPin, onRecord, onStopped, onMicFailed }: {
  phase: Phase; place: string; about: CaptureHint | null; onDropPlace: () => void;
  onSend: (text: string) => Promise<boolean>; onScan: () => void; onFiles: (f: File[]) => void; onFileJump?: () => void;
  onPin: () => void; onRecord: () => void; onStopped: (r: Recording) => void; onMicFailed: (why: string) => void;
}) {
  const [text, setText] = useState('');
  const [mic] = useState(canRecord);
  const file = useRef<HTMLInputElement>(null);
  const idle = phase.k === 'idle';
  const ready = idle && !!text.trim();
  async function submit() {
    if (!ready) return;
    const sent = text.trim();
    setText('');
    // Scheitert es, kommt der Text zurück ins Feld – verloren geht nichts.
    if (!(await onSend(sent))) setText((t) => t || sent);
  }
  if (phase.k === 'recording') {
    return <RecordingStrip hint={about?.objectId ?? null} context={place || null}
      onStopped={onStopped} onFailed={onMicFailed} />;
  }
  return (
    <div className={idle ? 'erp-composer' : 'erp-composer erp-composer-wait'}>
      {place && (
        <div className="erp-composer-place">
          <MapPin size={14} aria-hidden style={{ flex: 'none' }} />
          <span style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>{place}</span>
          {idle && <button type="button" onClick={onDropPlace} aria-label="Stelle entfernen" className="erp-capture-x"><X size={13} /></button>}
        </div>
      )}
      <TextArea name="capture" value={text} onChange={setText} readOnly={!idle} autoFocus rows={2}
        placeholder={idle ? 'Was gibt’s? Schreiben oder aufnehmen …' : ''} aria-label="Was festgehalten wird"
        className="erp-composer-input"
        onKeyDownCapture={(e) => {
          if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return;
          e.preventDefault();
          void submit();
        }} />
      <div className="erp-composer-bar">
        <button type="button" disabled={!idle} onClick={onScan} className="erp-icbtn" aria-label="Foto" data-tip="Foto – ein Blatt wird erkannt"><Camera size={18} /></button>
        <button type="button" disabled={!idle} onClick={() => (onFileJump ? onFileJump() : file.current?.click())} className="erp-icbtn" aria-label="Datei" data-tip="Datei"><FileText size={18} /></button>
        <button type="button" disabled={!idle} onClick={onPin} className={place ? 'erp-icbtn erp-icbtn-on' : 'erp-icbtn'}
          aria-label="Stelle zeigen" data-tip="Auf eine Stelle zeigen – Rückmeldung zur Software"><MapPin size={18} /></button>
        <input ref={file} type="file" hidden onChange={(e) => { if (e.target.files?.length) onFiles(Array.from(e.target.files)); }} />
        <span style={{ flex: 1 }} />
        {mic && <button type="button" disabled={!idle} onClick={onRecord} className="erp-icbtn" aria-label="Aufnehmen" data-tip="Aufnehmen"><Mic size={18} /></button>}
        <button type="button" disabled={!ready} onClick={() => void submit()} aria-label="Ablegen" data-tip="Ablegen (Enter)"
          className={ready ? 'erp-send erp-send-go' : 'erp-send'}><ArrowUp size={18} /></button>
      </div>
    </div>
  );
}

/**
 * ►► **Der Platz unter der Eingabe** – während die KI arbeitet das Skeleton in der Form von
 * «Abgelegt», dann «Abgelegt» selbst; bei einer gescheiterten Aufnahme ihr Grund. ◄◄
 */
function Work({ phase, alive, onDone, onClose, onResult, onFailed }: {
  phase: Phase; alive: RefObject<boolean>; onDone: () => void; onClose: () => void;
  onResult: (i: Intake) => void; onFailed: (r: Recording) => void;
}) {
  const recording = phase.k === 'working' ? phase.recording : undefined;
  useEffect(() => {
    if (!recording) return;
    const run = follow(recording, () => undefined);
    run.promise.then((r) => {
      if (!alive.current) return;
      if (r.state === 'done' && r.intake) onResult(r.intake); else onFailed(r);
    }, tell('Aufnahme', 'Nicht abgeschrieben'));
    return run.leave;
    // Eine Schleife je Aufnahme – die Rückrufe ändern sich mit jedem Zeichnen, die Aufnahme nicht.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recording?.id]);
  if (phase.k === 'working') return <Skeleton />;
  if (phase.k === 'result') return <FiledBody intake={phase.intake} onDone={onDone} onLeave={onClose} />;
  if (phase.k === 'failed') return <FailedRecording recording={phase.recording} onDone={onDone} />;
  return null;
}

/** Die Form von «Abgelegt», grau – ein Teil, ein Vorschlag, die zwei Knöpfe. */
function Skeleton() {
  return (
    <div className="erp-capture-skel" aria-busy="true" aria-label="Die KI legt ab">
      <div className="erp-capture-part">
        <span className="erp-skel" style={{ height: 22, width: '58%', borderRadius: 999 }} />
        <span className="erp-skel" style={{ height: 12, width: '96%' }} />
        <span className="erp-skel" style={{ height: 12, width: '88%' }} />
        <span className="erp-skel" style={{ height: 12, width: '64%' }} />
      </div>
      <span className="erp-skel" style={{ height: 40, borderRadius: 10 }} />
      <div style={{ display: 'flex', gap: 8 }}>
        <span className="erp-skel" style={{ height: 44, flex: 1, borderRadius: 10 }} />
        <span className="erp-skel" style={{ height: 44, flex: 1, borderRadius: 10 }} />
      </div>
    </div>
  );
}

/** Eine Aufnahme, die nicht abgeschrieben werden konnte – der Grund, dann Verwerfen. */
function FailedRecording({ recording, onDone }: { recording: Recording; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  async function dismiss() {
    setBusy(true);
    try { await api.dismissRecording(recording.id); onDone(); }
    catch (e) { tell('Aufnahme', 'Nicht verworfen')(e); setBusy(false); }
  }
  return (
    <div className="erp-capture-part" role="alert">
      <p className="erp-capture-problem" style={{ margin: 0 }}>
        <AlertCircle size={15} aria-hidden />{recording.problem || 'Die Aufnahme liess sich nicht abschreiben.'}
      </p>
      <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>{runtime(recording.seconds * 1000)} · {when(recording.at)}</span>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" onClick={onDone} className="erp-actbtn erp-actbtn-neutral" style={{ height: 44, flex: 1 }}>Zurück</button>
        <button type="button" onClick={() => void dismiss()} disabled={busy} className="erp-actbtn erp-actbtn-primary"
          style={{ height: 44, flex: 1 }}>Verwerfen</button>
      </div>
    </div>
  );
}

/** Was noch nicht abgelegt ist – je Zeile ein Knopf: antippen öffnet es hier, im selben Fenster. */
function OpenList({ onIntake, onRecording }: { onIntake: (i: Intake) => void; onRecording: (r: Recording) => void }) {
  const open = useOpenIntakes().data ?? [];
  // Fertige stehen schon als offene Erfassung da.
  const recordings = (useOpenRecordings().data ?? []).filter((r) => r.state !== 'done');
  if (!open.length && !recordings.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Nicht abgelegt</span>
      {recordings.map((r) => (
        <button key={`r${r.id}`} type="button" onClick={() => onRecording(r)} data-tip={r.problem ?? undefined}
          className={r.state === 'failed' ? 'erp-capture-row erp-capture-row-warn' : 'erp-capture-row'}>
          <Mic size={15} style={{ flex: 'none', color: r.state === 'failed' ? 'var(--danger)' : 'var(--fg-3)' }} />
          <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{recordingWord(r)}</span>
          <span className="tabular-nums erp-capture-when">{runtime(r.seconds * 1000)} · {when(r.at)}</span>
          <ChevronRight size={15} aria-hidden style={{ flex: 'none', color: 'var(--fg-4)' }} />
        </button>
      ))}
      {open.map((i) => (
        <button key={`i${i.id}`} type="button" onClick={() => onIntake(i)} className="erp-capture-row">
          <PenLine size={15} style={{ flex: 'none', color: 'var(--fg-3)' }} />
          <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{i.parts[0]?.subject || i.text}</span>
          <span className="tabular-nums erp-capture-when">{when(i.at)}</span>
          <ChevronRight size={15} aria-hidden style={{ flex: 'none', color: 'var(--fg-4)' }} />
        </button>
      ))}
    </div>
  );
}

/** «Neu anlegen» – wie bisher, eckig in den Farben des Feeds. */
function CreateTiles({ onCreate }: { onCreate: (type: Creatable) => void }) {
  return (
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
  );
}
