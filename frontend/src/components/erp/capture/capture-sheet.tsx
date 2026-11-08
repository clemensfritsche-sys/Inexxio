'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowUp, Camera, Check, ChevronRight, FileText, Loader2, MessageSquare, Mic, MapPin, Plus, Square, X } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { notify, tell } from '@/lib/notice';
import { when } from '@/lib/when';
import { qk } from '@/lib/queries';
import { TYPE_META } from '@/lib/erp-record';
import { useOpenRecordings, useOpenTalks, useTalk } from '@/lib/assistant';
import { canRecord } from '@/lib/use-recorder';
import { runtime } from '@/lib/recorder';
import { follow } from '@/lib/transcribe';
import { PIN_UI, describePlace, pickPlace, pinHome } from '@/lib/pin-point';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { TextArea } from '@/components/form/field';
import { HandgriffCard } from '@/components/erp/capture/handgriff-card';
import { RecordingStrip, recordingWord } from '@/components/erp/capture/recorder';
import type { Creatable } from '@/components/erp/feed-panel';
import type { ErpRecordType, Recording, Talk, TalkFile } from '@/types';
import { errorText } from '@/lib/use-action';

/** Der Datensatz, der beim Sagen offen ist – der erste Hinweis für die KI (nur seine Nummer). */
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
 * Was das «+» gerade tut – EIN Zustand: bereit · nimmt auf · arbeitet (die KI antwortet, eine
 * Aufnahme wird abgeschrieben) · eine gescheiterte Aufnahme.
 */
type Phase =
  | { k: 'idle' }
  | { k: 'recording' }
  | { k: 'working'; recording?: Recording; steps?: string[] }
  | { k: 'failed'; recording: Recording };

/**
 * ►►► **«+» = der Assistent – EIN Gespräch, wie das Eingabefeld bei Claude.** ◄◄◄
 * (Projektakte, Phase 5 §7.8)
 *
 * Oben die Eingabe: schreiben (Enter = ab, Umschalt+Enter = neue Zeile), 📷 Foto und 📄 Datei
 * (sie kommen **ins Gespräch** – die KI liest sie und bereitet das Dokument vor), 📌 Stecknadel
 * (auf eine Stelle zeigen – Rückmeldung zur Software, am Artikel «ERP» bzw. «Website»),
 * 🎤 Aufnehmen. Darunter das Gespräch: was ich sagte, was die KI antwortet, und die **Handgriffe**
 * als Karten – jeder einzeln: Ausführen, Entwurf öffnen, Ändern, Weg. Dann «Offene Gespräche» und
 * «Neu anlegen».
 *
 * **Das Fenster ändert sich nie** – man arbeitet nur darin: die Aufnahme läuft *im* Feld, während
 * die KI antwortet, steht das Skeleton dort, wo die Antwort erscheint. Schliessen (daneben tippen,
 * Esc) geht immer, **ausser während einer Aufnahme**; was offen ist, bleibt unter «Offene
 * Gespräche» (die Zahl am «+»). Antwortet die KI erst nach dem Schliessen, meldet es sich.
 */
export function CaptureSheet({ hint, onClose, onCreate, host }: {
  hint: CaptureHint | null;
  onClose: () => void;
  onCreate: (type: Creatable) => void;
  /** Wo die Stecknadel zeigt (Vorgabe: dieses Fenster). */
  host?: PinHost;
}) {
  const [phase, setPhase] = useState<Phase>({ k: 'idle' });
  const [talkId, setTalkId] = useState<number | null>(null);
  const [about, setAbout] = useState<CaptureHint | null>(hint);
  const [place, setPlace] = useState('');
  const [picking, setPicking] = useState(false);
  const [problem, setProblem] = useState('');
  /** Die Stecknadel fand den Artikel der Software nicht – leise gesagt, nicht verschwiegen. */
  const [homeless, setHomeless] = useState('');
  const alive = useAlive();
  const client = useQueryClient();
  const talk = useTalk(talkId).data ?? null;
  const locked = phase.k === 'recording';
  const dismiss = locked ? undefined : onClose;

  useEffect(() => {
    if (!dismiss || picking) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss, picking]);

  const { pin, forget } = usePin({ host, hint, setPicking, setPlace, setAbout, setHomeless });
  const keep = (t: Talk) => { client.setQueryData(qk.talk(t.id), t); setTalkId(t.id); };
  const fresh = () => { forget(); setPhase({ k: 'idle' }); setTalkId(null); setPlace(''); setAbout(hint); setProblem(''); setHomeless(''); };

  /** Ein Schritt der KI, live – er steht unter dem Gespräch, bis die Antwort da ist. */
  const step = (st: string) => {
    if (alive.current) setPhase((p) => (p.k === 'working' ? { ...p, steps: [...(p.steps ?? []), st] } : p));
  };

  /**
   * ►► **Sagen und live zuhören** – die Nachricht steht sofort im Gespräch, darunter, was die KI
   * gerade tut, dann ihre Antwort. Ohne Text (nach einer Aufnahme) antwortet sie auf das, was
   * dasteht. Antwortet sie, nachdem das «+» zu ist, meldet es sich. ◄◄
   */
  async function live(text: string, files: TalkFile[], talk: number | null): Promise<boolean> {
    setPhase({ k: 'working', steps: [] });
    setProblem('');
    let id = talk;                                // ein neues Gespräch hat seine Nummer ab der ersten Zeile
    try {
      await api.say(text, {
        talk, hint: talk ? null : about?.objectId, files,
        onTalk: (x) => { id = x.id; if (alive.current) keep(x); }, onStep: step,
      });
      if (alive.current) setPlace('');
      else notify('Der Assistent hat geantwortet – das Gespräch steht im «+».', Date.now(), { tone: 'info' });
      return true;
    } catch (e) {
      tell('Gespräch', 'Nicht beantwortet')(e);
      if (alive.current) {
        // Abgewiesen (4xx): nichts ist gespeichert – der Text kommt ins Feld zurück. Sonst riss nur
        // die Leitung: die Nachricht steht, die KI arbeitet zu Ende (das Gespräch zeigt es).
        const refused = e instanceof ApiError && e.status >= 400 && e.status < 500;
        const why = errorText(e, 'Nicht gesendet.');
        setProblem(refused ? why : `${why} Die KI arbeitet weiter – das Gespräch zeigt ihre Antwort, sobald sie da ist.`);
        if (id) void client.invalidateQueries({ queryKey: qk.talk(id) });
        return !refused;
      }
      return false;
    } finally {
      if (alive.current) setPhase({ k: 'idle' });
    }
  }
  const send = (text: string, files: TalkFile[]) => live(place ? `${place}\n\n${text}` : text, files, talkId);
  const halt = () => { if (talkId) api.stopTalk(talkId).catch(tell('Gespräch', 'Nicht angehalten')); };

  // Beim Zeigen tritt das «+» nur beiseite (unsichtbar, nicht ausgehängt) – der getippte Text,
  // die Aufnahme, das Warten bleiben, wie sie sind.
  return createPortal(
    <div className="erp-capture-scrim" onClick={dismiss}
      style={picking ? { visibility: 'hidden', pointerEvents: 'none' } : undefined}>
      <div role="dialog" aria-modal="true" aria-label="Assistent" className="erp-capture-sheet"
        {...{ [PIN_UI]: 'true' }} onClick={(e) => e.stopPropagation()}>
        <div className="erp-capture-body">
          {talk && <TalkView talk={talk} working={phase.k === 'working'} steps={phase.k === 'working' ? phase.steps : undefined}
            onStop={phase.k === 'working' && !phase.recording ? halt : undefined} onFresh={fresh}
            onChanged={() => void client.invalidateQueries({ queryKey: qk.talk(talk.id) })} />}
          {!talk && phase.k === 'working' && <Skeleton steps={phase.steps} />}
          <Composer phase={phase} place={place} about={talk ? null : about} talk={talk?.id ?? null}
            onDropPlace={() => { forget(); setPlace(''); setAbout(hint); setHomeless(''); }}
            onSend={send} onPin={pin}
            onRecord={() => { setProblem(''); setPhase({ k: 'recording' }); }}
            onStopped={(recording) => { setPhase({ k: 'working', recording }); setProblem(''); }}
            onMicFailed={(why) => { setPhase({ k: 'idle' }); setProblem(why); }} />
          {!talk && <HintLine about={about} onDrop={phase.k === 'idle' && about ? () => setAbout(null) : undefined} />}
          {homeless && <p className="erp-capture-hint" style={{ marginTop: -6 }}>{homeless}</p>}
          {problem && <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{problem}</p>}
          <Transcribing phase={phase} alive={alive}
            onTalk={(t) => { keep(t); void live('', [], t.id); }}
            onFailed={(recording) => setPhase({ k: 'failed', recording })} />
          {phase.k === 'failed' && <FailedRecording recording={phase.recording} onDone={fresh} />}
          <div className="erp-capture-rest" aria-disabled={phase.k !== 'idle' || undefined}>
            <OpenList current={talkId} onTalk={(t) => { keep(t); setPhase({ k: 'idle' }); }}
              onRecording={(r) => setPhase(r.state === 'failed' ? { k: 'failed', recording: r } : { k: 'working', recording: r })} />
            {!talk && <CreateTiles onCreate={onCreate} />}
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
  // Das laufende Zeigen (zum Aufräumen) und eine Nummer je Zeigen: eine späte Antwort der Suche
  // nach dem Artikel gilt nur, solange niemand die Stelle wieder entfernt oder neu gezeigt hat.
  const stopRef = useRef<() => void>(() => undefined);
  const turn = useRef(0);
  // Wird das «+» mitten im Zeigen entfernt: Listener, Fadenkreuz und Leiste gehen mit.
  useEffect(() => () => stopRef.current(), []);
  const pin = () => {
    const where = host ?? { doc: document, win: window, hide: () => undefined, show: () => undefined };
    const mine = ++turn.current;
    setPicking(true);
    where.hide();
    let offEsc: () => void = () => undefined;
    const back = () => { offEsc(); stopRef.current = () => undefined; where.show(); setPicking(false); };
    // Erst nach diesem Klick zeigen – sonst wählte der Klick auf 📌 schon die Stelle.
    window.setTimeout(() => {
      const stop = pickPlace(where.doc, (el) => {
        setPlace(describePlace(el, hint?.objectId, where.win));
        back();
        const name = pinHome(where.win.location.pathname);
        void homeOf(name).then((home) => {
          if (turn.current !== mine) return;
          setAbout(home);
          setHomeless(home ? '' : `Den Artikel «${name}» gibt es noch nicht – die KI legt es ab, wo es passt.`);
        }, tell(`Artikel «${name}»`, 'Nicht gefunden'));
      }, back);
      stopRef.current = () => { stop(); back(); };
      // Eingebettet bleibt der Fokus in diesem (unsichtbaren) Fenster – Esc auch hier hören.
      if (where.doc !== document) {
        const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') stopRef.current(); };
        document.addEventListener('keydown', esc, true);
        offEsc = () => document.removeEventListener('keydown', esc, true);
      }
    }, 0);
  };
  return { pin, forget: () => { turn.current += 1; } };
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
 * ►► **Die Eingabe** – Text, darunter die Leiste: 📷 📄 📌 … 🎤 ➤. Foto und Datei kommen als
 * Anhang in die nächste Nachricht (sie liegen dann im Korb). Während einer Aufnahme ist sie die
 * Aufnahme (`RecordingStrip`); während die KI antwortet, wartet sie. ◄◄
 */
function Composer({ phase, place, about, talk, onDropPlace, onSend, onPin, onRecord, onStopped, onMicFailed }: {
  phase: Phase; place: string; about: CaptureHint | null; talk: number | null; onDropPlace: () => void;
  onSend: (text: string, files: TalkFile[]) => Promise<boolean>;
  onPin: () => void; onRecord: () => void; onStopped: (r: Recording) => void; onMicFailed: (why: string) => void;
}) {
  const [text, setText] = useState('');
  const [files, setFiles] = useState<TalkFile[]>([]);
  const [uploading, setUploading] = useState(0);
  const [mic] = useState(canRecord);
  const photo = useRef<HTMLInputElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const idle = phase.k === 'idle';
  const ready = idle && !uploading && (!!text.trim() || files.length > 0);
  async function attach(list: FileList | null) {
    if (!list?.length) return;
    const picked = Array.from(list);
    setUploading((n) => n + picked.length);
    for (const f of picked) {
      try {
        const ref = await api.addTalkFile(f, f.name || 'Foto');
        setFiles((x) => [...x, ref]);
      } catch (e) { tell(`Datei «${f.name}»`, 'Nicht angehängt')(e); }
      finally { setUploading((n) => n - 1); }
    }
  }
  async function submit() {
    if (!ready) return;
    const sent = text.trim();
    const with_ = files;
    setText('');
    setFiles([]);
    // Scheitert es, kommen Text und Dateien zurück ins Feld – verloren geht nichts.
    if (!(await onSend(sent, with_))) { setText((t) => t || sent); setFiles((f) => (f.length ? f : with_)); }
  }
  if (phase.k === 'recording') {
    return <RecordingStrip hint={about?.objectId ?? null} talk={talk} context={place || null}
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
      {(files.length > 0 || uploading > 0) && (
        <div className="erp-composer-files">
          {files.map((f) => (
            <span key={f.token} className="erp-talk-file">
              <FileText size={13} aria-hidden />{f.name}
              <button type="button" onClick={() => setFiles((x) => x.filter((y) => y.token !== f.token))}
                aria-label={`«${f.name}» entfernen`} className="erp-capture-x"><X size={12} /></button>
            </span>
          ))}
          {uploading > 0 && <span className="erp-talk-file"><Loader2 size={13} className="animate-spin" />lädt …</span>}
        </div>
      )}
      <TextArea name="capture" value={text} onChange={setText} readOnly={!idle} autoFocus rows={2}
        placeholder={idle ? (talk ? 'Antworten …' : 'Was gibt’s? Schreiben oder aufnehmen …') : ''}
        aria-label="Was ich dem Assistenten sage" className="erp-composer-input"
        onKeyDownCapture={(e) => {
          if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return;
          e.preventDefault();
          void submit();
        }} />
      <div className="erp-composer-bar">
        <button type="button" disabled={!idle} onClick={() => photo.current?.click()} className="erp-icbtn" aria-label="Foto" data-tip="Foto – ins Gespräch"><Camera size={18} /></button>
        <button type="button" disabled={!idle} onClick={() => file.current?.click()} className="erp-icbtn" aria-label="Datei" data-tip="Datei – ins Gespräch"><FileText size={18} /></button>
        <button type="button" disabled={!idle} onClick={onPin} className={place ? 'erp-icbtn erp-icbtn-on' : 'erp-icbtn'}
          aria-label="Stelle zeigen" data-tip="Auf eine Stelle zeigen – Rückmeldung zur Software"><MapPin size={18} /></button>
        {/* Dateiwahl: begründete Ausnahme von RAW_FIELD (eslint.config.mjs) */}
        <input ref={photo} type="file" accept="image/*" capture="environment" hidden
          onChange={(e) => { void attach(e.target.files); e.target.value = ''; }} />
        <input ref={file} type="file" multiple hidden
          onChange={(e) => { void attach(e.target.files); e.target.value = ''; }} />
        <span style={{ flex: 1 }} />
        {mic && <button type="button" disabled={!idle} onClick={onRecord} className="erp-icbtn" aria-label="Aufnehmen" data-tip="Aufnehmen"><Mic size={18} /></button>}
        <button type="button" disabled={!ready} onClick={() => void submit()} aria-label="Senden" data-tip="Senden (Enter)"
          className={ready ? 'erp-send erp-send-go' : 'erp-send'}><ArrowUp size={18} /></button>
      </div>
    </div>
  );
}

/**
 * ►► **Das Gespräch** – was ich sagte (rechts), was die KI antwortet (links), die Handgriffe als
 * Karten, der Reihe nach. Oben «Neues Gespräch»; während die KI antwortet, das Skeleton. ◄◄
 */
function TalkView({ talk, working, steps, onStop, onFresh, onChanged }: {
  talk: Talk; working: boolean; steps?: string[]; onStop?: () => void; onFresh: () => void; onChanged: () => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); },
    [talk.messages.length, talk.handgriffe.length, steps?.length]);
  const items = [
    ...talk.messages.map((m) => ({ at: m.at, id: m.id, el: <Bubble key={`m${m.id}`} m={m} /> })),
    ...talk.handgriffe.map((h) => ({ at: h.at, id: h.id, el: <HandgriffCard key={`h${h.id}`} h={h} onChanged={onChanged} /> })),
  ].sort((a, b) => a.id - b.id);
  return (
    <div className="erp-talk">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <MessageSquare size={14} aria-hidden style={{ color: 'var(--fg-3)' }} />
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)', flex: 1 }}>Gespräch{talk.hint_object_id ? <> · <ObjId value={talk.hint_object_id} /></> : null}</span>
        <button type="button" onClick={onFresh} disabled={working} className="erp-actbtn erp-actbtn-neutral"
          style={{ height: 28, padding: '0 10px', fontSize: 12 }}><Plus size={13} />Neues Gespräch</button>
      </div>
      {items.map((x) => x.el)}
      {working && <Skeleton steps={steps} onStop={onStop} />}
      {!working && talk.problem && <p className="erp-capture-hint" role="status">{talk.problem}</p>}
      <div ref={end} />
    </div>
  );
}

function Bubble({ m }: { m: Talk['messages'][number] }) {
  return (
    <div className={m.by === 'person' ? 'erp-bubble erp-bubble-me' : 'erp-bubble'}>
      <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.text}</span>
      {(m.files ?? []).map((f) => <span key={f.token} className="erp-talk-file"><FileText size={13} aria-hidden />{f.name}</span>)}
    </div>
  );
}

/** Eine Aufnahme wird abgeschrieben – das «+» folgt ihr, bis der Text im Gespräch steht. */
function Transcribing({ phase, alive, onTalk, onFailed }: {
  phase: Phase; alive: { current: boolean }; onTalk: (t: Talk) => void; onFailed: (r: Recording) => void;
}) {
  const recording = phase.k === 'working' ? phase.recording : undefined;
  useEffect(() => {
    if (!recording) return;
    const run = follow(recording, () => undefined);
    run.promise.then((r) => {
      if (!alive.current) return;
      if (r.state === 'done' && r.talk) onTalk(r.talk); else onFailed(r);
    }, tell('Aufnahme', 'Nicht abgeschrieben'));
    return run.leave;
    // Eine Schleife je Aufnahme – die Rückrufe ändern sich mit jedem Zeichnen, die Aufnahme nicht.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recording?.id]);
  return null;
}

/**
 * ►► **Während die KI arbeitet** – was sie gerade tut, Schritt für Schritt («liest …», «bereitet vor:
 * …»), darunter die graue Form der Antwort; «Stopp» hält sie vor dem nächsten Schritt an. ◄◄
 */
function Skeleton({ steps, onStop }: { steps?: string[]; onStop?: () => void }) {
  return (
    <div className="erp-capture-skel" aria-busy="true" aria-label="Der Assistent antwortet">
      {(steps ?? []).length > 0 && (
        <ol className="erp-talk-steps" aria-live="polite">
          {(steps ?? []).map((st, i) => (
            <li key={i} className={i === (steps ?? []).length - 1 ? 'erp-talk-step-now' : undefined}>
              {i === (steps ?? []).length - 1 ? <Loader2 size={12} className="animate-spin" aria-hidden /> : <Check size={12} aria-hidden />}
              <span>{st}</span>
            </li>
          ))}
        </ol>
      )}
      <span className="erp-skel" style={{ height: 12, width: '72%' }} />
      <span className="erp-skel" style={{ height: 12, width: '54%' }} />
      {onStop && (
        <button type="button" onClick={onStop} className="erp-actbtn erp-actbtn-neutral"
          style={{ height: 28, padding: '0 10px', fontSize: 12, alignSelf: 'flex-start' }}>
          <Square size={11} aria-hidden />Stopp
        </button>
      )}
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

/** Offene Gespräche und Aufnahmen – je Zeile ein Knopf: antippen öffnet es hier, im selben Fenster. */
function OpenList({ current, onTalk, onRecording }: {
  current: number | null; onTalk: (t: Talk) => void; onRecording: (r: Recording) => void;
}) {
  const talks = (useOpenTalks().data ?? []).filter((t) => t.id !== current);
  // Fertige stehen schon als Gespräch da.
  const recordings = (useOpenRecordings().data ?? []).filter((r) => r.state !== 'done');
  if (!talks.length && !recordings.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Offene Gespräche</span>
      {recordings.map((r) => (
        <button key={`r${r.id}`} type="button" onClick={() => onRecording(r)} data-tip={r.problem ?? undefined}
          className={r.state === 'failed' ? 'erp-capture-row erp-capture-row-warn' : 'erp-capture-row'}>
          <Mic size={15} style={{ flex: 'none', color: r.state === 'failed' ? 'var(--danger)' : 'var(--fg-3)' }} />
          <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{recordingWord(r)}</span>
          <span className="tabular-nums erp-capture-when">{runtime(r.seconds * 1000)} · {when(r.at)}</span>
          <ChevronRight size={15} aria-hidden style={{ flex: 'none', color: 'var(--fg-4)' }} />
        </button>
      ))}
      {talks.map((t) => {
        const open = t.handgriffe.filter((h) => h.state === 'open' || h.state === 'waiting').length;
        return (
          <button key={`t${t.id}`} type="button" onClick={() => onTalk(t)} className="erp-capture-row">
            <MessageSquare size={15} style={{ flex: 'none', color: 'var(--fg-3)' }} />
            <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{t.messages[0]?.text || 'Gespräch'}</span>
            <span className="tabular-nums erp-capture-when">
              {open ? `${open} Handgriff${open === 1 ? '' : 'e'} · ` : t.waiting ? 'wartet · ' : ''}{when(t.at)}
            </span>
            <ChevronRight size={15} aria-hidden style={{ flex: 'none', color: 'var(--fg-4)' }} />
          </button>
        );
      })}
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
