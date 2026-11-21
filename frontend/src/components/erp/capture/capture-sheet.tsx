'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowLeft, ArrowUp, Camera, Check, ChevronRight, FileText, Loader2, MessageSquare, Mic, MapPin, Square, X } from 'lucide-react';
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
import { RecordingBar, recordingWord } from '@/components/erp/capture/recorder';
import { Markdown } from '@/components/erp/capture/markdown';
import { EMPTY_DRAFT, loadDraft, saveDraft, type Draft } from '@/lib/draft';
import type { Creatable } from '@/components/erp/feed-panel';
import type { ErpRecordType, Recording, Talk, TalkFile } from '@/types';
import { errorText, useAction } from '@/lib/use-action';
import { useDialog } from '@/lib/use-dialog';

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
 * Was das «+» gerade tut – EIN Zustand: bereit · nimmt auf · die KI antwortet · eine gescheiterte
 * Aufnahme ist offen. (Ob eine Aufnahme abgeschrieben wird, sagt die Liste der Aufnahmen.)
 */
type Phase =
  | { k: 'idle' }
  | { k: 'recording' }
  | { k: 'working'; steps?: string[]; said?: string }
  | { k: 'failed'; recording: Recording };

/**
 * ►►► **«+» = der Assistent – EIN Gespräch, wie das Eingabefeld bei Claude.** ◄◄◄
 * (Projektakte, Phase 5 §7.8)
 *
 * Die Eingabe: schreiben (Enter = ab, Umschalt+Enter = neue Zeile), 📷 Foto und 📄 Datei (auch
 * einfügen mit Ctrl+V oder hineinziehen; sie kommen **ins Gespräch** – die KI liest sie und bereitet
 * das Dokument vor), 📌 Stecknadel (Rückmeldung zur Software, als Chip im Feld), 🎤 Aufnehmen –
 * **das Feld bleibt stehen**, in der Leiste laufen Punkt, Zeit und Pegel; nach 30 s Stille hält es
 * von selbst. Der abgeschriebene Text kommt **in das Feld**: ergänzen, dann senden. **Vor dem Senden
 * gibt es kein Gespräch** – was im Feld steht, ist der Entwurf (`lib/draft`, bleibt beim Schliessen).
 * Darüber das Gespräch: was ich sagte, was die KI antwortet (live, Wort für Wort, mit Markdown), und
 * ihre **Vorschläge** als Karten – Öffnen, ✕. Während sie antwortet, ist ➤ der Stopp. «←» führt zur
 * Übersicht: «Offene Gespräche» und «Neu anlegen».
 *
 * Schliessen (daneben tippen, Esc) geht immer, **ausser während einer Aufnahme**. Antwortet die KI
 * erst nach dem Schliessen, meldet es sich.
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
  const [draft, setDraftState] = useState<Draft>(loadDraft);
  const [picking, setPicking] = useState(false);
  const [problem, setProblem] = useState('');
  /** Die Stecknadel fand den Artikel der Software nicht – leise gesagt, nicht verschwiegen. */
  const [homeless, setHomeless] = useState('');
  const alive = useAlive();
  const client = useQueryClient();
  const talk = useTalk(talkId).data ?? null;
  const locked = phase.k === 'recording';
  const dismiss = locked ? undefined : onClose;
  const setDraft = (next: Draft | ((d: Draft) => Draft)) => setDraftState((d) => {
    const v = typeof next === 'function' ? next(d) : next;
    saveDraft(v);
    return v;
  });
  const setPlace = (place: string) => setDraft((d) => ({ ...d, place }));
  const transcribing = useDictation(phase.k === 'recording', setDraft);

  // Escape schliesst (nicht während einer Aufnahme und nicht beim Zeigen der Stecknadel), Fokus
  // zurück, Tab im Kreis – das eine Verhalten (`lib/use-dialog`).
  const dialog = useDialog(picking ? null : dismiss, { focus: 'none' });

  const { pin, forget } = usePin({ host, hint, setPicking, setPlace, setAbout, setHomeless });
  const keep = (t: Talk) => { client.setQueryData(qk.talk(t.id), t); setTalkId(t.id); };
  const overview = () => { setPhase({ k: 'idle' }); setTalkId(null); setAbout(hint); setProblem(''); };
  const dropPlace = () => { forget(); setPlace(''); setAbout(hint); setHomeless(''); };

  /** Ein Schritt der KI, live – er steht unter dem Gespräch, bis die Antwort da ist. */
  const step = (st: string) => {
    if (alive.current) setPhase((p) => (p.k === 'working' ? { ...p, steps: [...(p.steps ?? []), st] } : p));
  };
  /** Ein Stück ihrer Antwort, Wort für Wort. */
  const piece = (t: string) => {
    if (alive.current) setPhase((p) => (p.k === 'working' ? { ...p, said: (p.said ?? '') + t } : p));
  };

  /**
   * ►► **Senden und live zuhören** – erst jetzt entsteht die Nachricht (und mit der ersten das
   * Gespräch); darunter, was die KI gerade tut, dann ihre Antwort, Wort für Wort. Antwortet sie,
   * nachdem das «+» zu ist, meldet es sich. Scheitert es, steht der Entwurf wieder im Feld. ◄◄
   */
  async function send(text: string, files: TalkFile[]): Promise<boolean> {
    const sent = draft;
    setDraft(EMPTY_DRAFT);
    setPhase({ k: 'working', steps: [] });
    setProblem('');
    let id = talkId;                              // ein neues Gespräch hat seine Nummer ab der ersten Zeile
    try {
      await api.say(sent.place ? `${sent.place}\n\n${text}` : text, {
        talk: talkId, hint: talkId ? null : about?.objectId, files, recordings: sent.recordings,
        onTalk: (x) => { id = x.id; if (alive.current) keep(x); }, onStep: step, onText: piece,
      });
      if (!alive.current) notify('Der Assistent hat geantwortet – das Gespräch steht im «+».', Date.now(), { tone: 'info' });
      return true;
    } catch (e) {
      tell('Gespräch', 'Nicht beantwortet')(e);
      // Abgewiesen (4xx): nichts ist gespeichert – der Entwurf kommt zurück. Sonst riss nur die
      // Leitung: die Nachricht steht, die KI arbeitet zu Ende (das Gespräch zeigt es).
      const refused = e instanceof ApiError && e.status >= 400 && e.status < 500;
      if (refused) setDraft((d) => (d.text || d.recordings.length ? d : sent));
      if (alive.current) {
        const why = errorText(e, 'Nicht gesendet.');
        setProblem(refused ? why : `${why} Die KI arbeitet weiter – das Gespräch zeigt ihre Antwort, sobald sie da ist.`);
        if (id) void client.invalidateQueries({ queryKey: qk.talk(id) });
      }
      return !refused;
    } finally {
      if (alive.current) setPhase({ k: 'idle' });
    }
  }
  const halt = () => { if (talkId) api.stopTalk(talkId).catch(tell('Gespräch', 'Nicht angehalten')); };

  // Beim Zeigen tritt das «+» nur beiseite (unsichtbar, nicht ausgehängt) – der getippte Text,
  // die Aufnahme, das Warten bleiben, wie sie sind.
  return createPortal(
    <div className="erp-capture-scrim" onClick={dismiss}
      style={picking ? { visibility: 'hidden', pointerEvents: 'none' } : undefined}>
      <div ref={dialog.ref} onKeyDown={dialog.onKeyDown}
        role="dialog" aria-modal="true" aria-label="Assistent" className="erp-capture-sheet"
        {...{ [PIN_UI]: 'true' }} onClick={(e) => e.stopPropagation()}>
        <div className="erp-capture-body">
          {talk && <TalkView talk={talk} phase={phase} onBack={overview} onLeave={onClose}
            onChanged={() => void client.invalidateQueries({ queryKey: qk.talk(talk.id) })} />}
          {!talk && phase.k === 'working' && <Skeleton steps={phase.steps} said={phase.said} />}
          <Composer phase={phase} draft={draft} setDraft={setDraft} about={talk ? null : about}
            talk={talk?.id ?? null} transcribing={transcribing}
            onDropPlace={dropPlace} onSend={send} onPin={pin} onHalt={talkId ? halt : undefined}
            onRecord={() => { setProblem(''); setPhase({ k: 'recording' }); }}
            onStopped={(r) => { setPhase({ k: 'idle' }); setProblem(''); remember(client, r); }}
            onMicFailed={(why) => { setPhase({ k: 'idle' }); setProblem(why); }} />
          {!talk && <HintLine about={about} onDrop={phase.k === 'idle' && about ? () => setAbout(null) : undefined} />}
          {homeless && <p className="erp-capture-hint" style={{ marginTop: -6 }}>{homeless}</p>}
          {problem && <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{problem}</p>}
          {phase.k === 'failed' && <FailedRecording recording={phase.recording} onDone={() => setPhase({ k: 'idle' })} />}
          <div className="erp-capture-rest" aria-disabled={phase.k !== 'idle' || undefined}>
            <OpenList current={talkId} onTalk={(t) => { keep(t); setPhase({ k: 'idle' }); }}
              onFailed={(r) => setPhase({ k: 'failed', recording: r })} />
            {!talk && <CreateTiles onCreate={onCreate} />}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Eine eben gestoppte Aufnahme steht sofort in der Liste – das Abschreiben beginnt ohne Warten. */
function remember(client: QueryClient, r: Recording) {
  client.setQueryData<Recording[]>(qk.openRecordings(), (list) => [r, ...(list ?? []).filter((x) => x.id !== r.id)]);
}

/**
 * ►► **Diktieren** – jede meiner Aufnahmen, die noch abgeschrieben wird, wird hier zu Ende
 * abgeschrieben (`lib/transcribe.follow`, eine Schleife je Aufnahme, auch wenn das «+» zugeht);
 * ist sie fertig, kommt ihr Text **ans Ende des Feldes** (einmal, `Draft.recordings`), die
 * Stecknadel davor. Gibt zurück, ob gerade etwas abgeschrieben wird. ◄◄
 */
function useDictation(recordingNow: boolean, setDraft: (f: (d: Draft) => Draft) => void): boolean {
  const client = useQueryClient();
  const open = useOpenRecordings().data ?? [];
  const pending = open.filter((r) => r.state === 'transcribing' || r.state === 'filing'
    || (r.state === 'recording' && !recordingNow));
  const done = open.filter((r) => r.state === 'done');
  const pendingKey = pending.map((r) => r.id).join(',');
  const doneKey = done.map((r) => r.id).join(',');
  useEffect(() => {
    const put = (r: Recording) => client.setQueryData<Recording[]>(qk.openRecordings(),
      (list) => (list ?? []).map((x) => (x.id === r.id ? r : x)));
    const runs = pending.map((r) => {
      const run = follow(r, put);
      run.promise.then(put, tell('Aufnahme', 'Nicht abgeschrieben'));
      return run;
    });
    return () => runs.forEach((run) => run.leave());
    // Eine Schleife je Aufnahme – die Liste selbst ändert sich mit jedem Zwischenstand.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingKey]);
  useEffect(() => {
    if (!done.length) return;
    setDraft((d) => {
      const fresh = done.filter((r) => !d.recordings.includes(r.id));
      if (!fresh.length) return d;
      const said = fresh.map((r) => (r.text ?? '').trim()).filter(Boolean).join('\n\n');
      return {
        text: said ? (d.text.trim() ? `${d.text.trimEnd()}\n\n${said}` : said) : d.text,
        place: d.place || fresh.find((r) => r.context)?.context || '',
        recordings: [...d.recordings, ...fresh.map((r) => r.id)],
      };
    });
    // Einmal je neu fertiger Aufnahme.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doneKey]);
  return pending.length > 0;
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
 * ►► **Die Eingabe** – das Feld bleibt immer stehen. Darin: die Stecknadel und Anhänge als Chips,
 * «schreibt ab …», solange eine Aufnahme abgeschrieben wird. Darunter die Leiste: 📷 📄 📌 … 🎤 ➤ –
 * während einer Aufnahme Punkt · Zeit · Pegel · ■, während die KI antwortet ist ➤ der Stopp.
 * Dateien kommen auch mit Ctrl+V oder per Hineinziehen. ◄◄
 */
function Composer({ phase, draft, setDraft, about, talk, transcribing, onDropPlace, onSend, onPin, onHalt,
  onRecord, onStopped, onMicFailed }: {
  phase: Phase; draft: Draft; setDraft: (f: (d: Draft) => Draft) => void; about: CaptureHint | null;
  talk: number | null; transcribing: boolean; onDropPlace: () => void;
  onSend: (text: string, files: TalkFile[]) => Promise<boolean>; onPin: () => void; onHalt?: () => void;
  onRecord: () => void; onStopped: (r: Recording) => void; onMicFailed: (why: string) => void;
}) {
  const [files, setFiles] = useState<TalkFile[]>([]);
  const [uploading, setUploading] = useState(0);
  const [over, setOver] = useState(false);
  const [mic] = useState(canRecord);
  const photo = useRef<HTMLInputElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const idle = phase.k === 'idle';
  const recording = phase.k === 'recording';
  const ready = idle && !uploading && (!!draft.text.trim() || files.length > 0);
  async function attach(list: FileList | File[] | null) {
    const picked = Array.from(list ?? []);
    if (!picked.length) return;
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
    const with_ = files;
    setFiles([]);
    // Scheitert es, kommen die Dateien zurück (den Text bringt der Entwurf zurück).
    if (!(await onSend(draft.text.trim(), with_))) setFiles((f) => (f.length ? f : with_));
  }
  return (
    <div className={over ? 'erp-composer erp-composer-drop' : 'erp-composer'}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setOver(true); } }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        if (!e.dataTransfer.files.length) return;
        e.preventDefault();
        setOver(false);
        void attach(e.dataTransfer.files);
      }}>
      {(draft.place || files.length > 0 || uploading > 0 || transcribing) && (
        <div className="erp-composer-files">
          {draft.place && (
            <span className="erp-talk-file erp-composer-pin" data-tip={draft.place}>
              <MapPin size={13} aria-hidden style={{ flex: 'none' }} />
              <span className="truncate" style={{ minWidth: 0 }}>{draft.place.replace(/^Stelle:\s*/, '')}</span>
              {idle && <button type="button" onClick={onDropPlace} aria-label="Stelle entfernen" className="erp-capture-x"><X size={12} /></button>}
            </span>
          )}
          {files.map((f) => (
            <span key={f.token} className="erp-talk-file">
              <FileText size={13} aria-hidden />{f.name}
              <button type="button" onClick={() => setFiles((x) => x.filter((y) => y.token !== f.token))}
                aria-label={`«${f.name}» entfernen`} className="erp-capture-x"><X size={12} /></button>
            </span>
          ))}
          {uploading > 0 && <span className="erp-talk-file"><Loader2 size={13} className="animate-spin" />lädt …</span>}
          {transcribing && <span className="erp-talk-file" role="status"><Loader2 size={13} className="animate-spin" />schreibt ab …</span>}
        </div>
      )}
      <TextArea name="capture" value={draft.text} onChange={(text) => setDraft((d) => ({ ...d, text }))}
        autoFocus rows={2} placeholder={recording ? 'Sprechen …' : talk ? 'Antworten …' : 'Was gibt’s? Schreiben oder aufnehmen …'}
        aria-label="Was ich dem Assistenten sage" className="erp-composer-input"
        onPaste={(e) => {
          if (!e.clipboardData.files.length) return;
          e.preventDefault();
          void attach(e.clipboardData.files);
        }}
        onKeyDownCapture={(e) => {
          if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return;
          e.preventDefault();
          void submit();
        }} />
      <div className="erp-composer-bar">
        {recording ? (
          <RecordingBar hint={about?.objectId ?? null} context={draft.place || null}
            onStopped={onStopped} onFailed={onMicFailed} />
        ) : (
          <>
            <button type="button" disabled={!idle} onClick={() => photo.current?.click()} className="erp-icbtn" aria-label="Foto" data-tip="Foto – ins Gespräch"><Camera size={18} /></button>
            <button type="button" disabled={!idle} onClick={() => file.current?.click()} className="erp-icbtn" aria-label="Datei" data-tip="Datei – ins Gespräch (auch einfügen oder hineinziehen)"><FileText size={18} /></button>
            <button type="button" disabled={!idle} onClick={onPin} className={draft.place ? 'erp-icbtn erp-icbtn-on' : 'erp-icbtn'}
              aria-label="Stelle zeigen" data-tip="Auf eine Stelle zeigen – Rückmeldung zur Software"><MapPin size={18} /></button>
            {/* Dateiwahl: begründete Ausnahme von RAW_FIELD (eslint.config.mjs) */}
            <input ref={photo} type="file" accept="image/*" capture="environment" hidden
              onChange={(e) => { void attach(e.target.files); e.target.value = ''; }} />
            <input ref={file} type="file" multiple hidden
              onChange={(e) => { void attach(e.target.files); e.target.value = ''; }} />
            <span style={{ flex: 1 }} />
            {mic && <button type="button" disabled={!idle} onClick={onRecord} className="erp-icbtn" aria-label="Aufnehmen" data-tip="Aufnehmen – der Text kommt ins Feld"><Mic size={18} /></button>}
            {phase.k === 'working' ? (
              <button type="button" disabled={!onHalt} onClick={onHalt} aria-label="Stopp" data-tip="Stopp – die KI hält an"
                className="erp-send erp-send-stop"><Square size={13} fill="currentColor" /></button>
            ) : (
              <button type="button" disabled={!ready} onClick={() => void submit()} aria-label="Senden" data-tip="Senden (Enter)"
                className={ready ? 'erp-send erp-send-go' : 'erp-send'}><ArrowUp size={18} /></button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * ►► **Das Gespräch** – was ich sagte (rechts), was die KI antwortet (links), die Vorschläge als
 * Karten, der Reihe nach. Oben «←» zur Übersicht; während die KI antwortet, ihr Text live. ◄◄
 */
function TalkView({ talk, phase, onBack, onLeave, onChanged }: {
  talk: Talk; phase: Phase; onBack: () => void; onLeave: () => void; onChanged: () => void;
}) {
  const working = phase.k === 'working';
  const steps = working ? phase.steps : undefined;
  const said = working ? phase.said : undefined;
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); },
    [talk.messages.length, talk.handgriffe.length, steps?.length, said?.length]);
  // **Erst die Antwort, dann ihre Vorschläge**: die KI bereitet einen Vorschlag vor, bevor ihr
  // Text gespeichert ist – darum steht er hinter der nächsten Antwort der KI, nicht davor.
  const answers = talk.messages.filter((m) => m.by === 'ai').map((m) => m.id);
  const after = (id: number) => (answers.find((a) => a > id) ?? id) + 0.5;
  const items = [
    ...talk.messages.map((m) => ({ order: m.id, el: <Bubble key={`m${m.id}`} m={m} /> })),
    ...talk.handgriffe.map((h) => ({ order: after(h.id),
      el: <HandgriffCard key={`h${h.id}`} h={h} onChanged={onChanged} onLeave={onLeave} /> })),
  ].sort((a, b) => a.order - b.order);
  return (
    <div className="erp-talk">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button type="button" onClick={onBack} disabled={working || phase.k === 'recording'} className="erp-icbtn"
          aria-label="Zur Übersicht" data-tip="Zur Übersicht – das Gespräch bleibt unter «Offene Gespräche»">
          <ArrowLeft size={16} />
        </button>
        <MessageSquare size={14} aria-hidden style={{ color: 'var(--fg-3)' }} />
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)', flex: 1 }}>Gespräch{talk.hint_object_id ? <> · <ObjId value={talk.hint_object_id} /></> : null}</span>
      </div>
      {items.map((x) => x.el)}
      {working && <Skeleton steps={steps} said={said} />}
      {!working && talk.problem && <p className="erp-capture-hint" role="status">{talk.problem}</p>}
      <div ref={end} />
    </div>
  );
}

function Bubble({ m }: { m: Talk['messages'][number] }) {
  return (
    <div className={m.by === 'person' ? 'erp-bubble erp-bubble-me' : 'erp-bubble'}>
      {m.by === 'ai' ? <Markdown text={m.text} /> : <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.text}</span>}
      {(m.files ?? []).map((f) => <span key={f.token} className="erp-talk-file"><FileText size={13} aria-hidden />{f.name}</span>)}
    </div>
  );
}

/**
 * ►► **Während die KI arbeitet** – was sie gerade tut, Schritt für Schritt («liest …», «bereitet vor:
 * …»), dann ihr Text, Wort für Wort; bis er kommt, die graue Form der Antwort. ◄◄
 */
function Skeleton({ steps, said }: { steps?: string[]; said?: string }) {
  return (
    <div className="erp-capture-skel" aria-busy="true" aria-label="Der Assistent antwortet">
      {(steps ?? []).length > 0 && (
        <ol className="erp-talk-steps" aria-live="polite">
          {(steps ?? []).map((st, i) => (
            <li key={i} className={i === (steps ?? []).length - 1 && !said ? 'erp-talk-step-now' : undefined}>
              {i === (steps ?? []).length - 1 && !said ? <Loader2 size={12} className="animate-spin" aria-hidden /> : <Check size={12} aria-hidden />}
              <span>{st}</span>
            </li>
          ))}
        </ol>
      )}
      {said ? <div className="erp-bubble" aria-live="polite"><Markdown text={said} /></div> : (
        <>
          <span className="erp-skel" style={{ height: 12, width: '72%' }} />
          <span className="erp-skel" style={{ height: 12, width: '54%' }} />
        </>
      )}
    </div>
  );
}

/** Eine Aufnahme, die nicht abgeschrieben werden konnte – der Grund, dann Verwerfen. */
function FailedRecording({ recording, onDone }: { recording: Recording; onDone: () => void }) {
  const { busy, run } = useAction();
  const dismiss = () => run(async () => { await api.dismissRecording(recording.id); onDone(); },
                            tell('Aufnahme', 'Nicht verworfen'));
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
function OpenList({ current, onTalk, onFailed }: {
  current: number | null; onTalk: (t: Talk) => void; onFailed: (r: Recording) => void;
}) {
  const talks = (useOpenTalks().data ?? []).filter((t) => t.id !== current);
  // Nur, was nicht abgeschrieben werden konnte – alles andere geht von selbst in die Eingabe.
  const recordings = (useOpenRecordings().data ?? []).filter((r) => r.state === 'failed');
  if (!talks.length && !recordings.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Offene Gespräche</span>
      {recordings.map((r) => (
        <button key={`r${r.id}`} type="button" onClick={() => onFailed(r)} data-tip={r.problem ?? undefined}
          className="erp-capture-row erp-capture-row-warn">
          <Mic size={15} style={{ flex: 'none', color: 'var(--danger)' }} />
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
              {open ? `${open} Vorschl${open === 1 ? 'ag' : 'äge'} · ` : t.waiting ? 'wartet · ' : ''}{when(t.at)}
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
