'use client';

/**
 * ►►► **Der Tag – Einträge und das EINE Werkzeug «Erfassen».** ◄◄◄
 *
 * Ein Tag besteht aus Einträgen: Stempel (Kommen grün, Gehen rot) und höchstens eine
 * Absenz. Eine Änderung steht an ihrer Zeile («geändert», «nachgetragen», «durch …»,
 * Einzelheiten im Hover). «Erfassen» füllt den Tag: Kommen/Gehen mit Uhrzeit oder eine
 * Absenzart – ganzer Tag oder Stunden. **Ob es geht und was es bewirkt, sagt der Server**
 * (`/entries/preview`, dieselbe Regel wie beim Speichern) – die Oberfläche rechnet nichts nach.
 */
import { useEffect, useState } from 'react';
import {
  Calendar, Check, ChevronDown, Clock, FileCheck, LogIn, LogOut, Pencil, Plus, Undo2, Upload,
} from 'lucide-react';
import { ErrorText, IconSwitch, InfoHint, Row } from '@/components/erp/fields';
import { LedgerRow, StageAction } from '@/components/erp/module-ui';
import { api, assetUrl } from '@/lib/api';
import { day as dayText, dayShort, dayTitle, parseDay } from '@/lib/when';
import type { EntryPreview, TimeAbsence, TimeDay, TimeEntryIn, TimeStamp, TimeView } from '@/types';
import {
  Dot, IconBar, IconButton, Note, Pill, QuietButton, ROW_FORM, TimeField, hm, parseClock,
  parseHm, timeIcon, vacationText,
} from './time-ui';

/** Was im Werkzeug «Erfassen» gerade steht. */
export interface Capture {
  day: string;
  what: string | null;
  scope: 'full' | 'hours';
  time: string;
  dur: string;
  until: string;
}

type Preview = EntryPreview;

function captureFor(day: string, what: string | null = null): Capture {
  return { day, what, scope: 'full', time: '', dur: '', until: dayText(day) };
}

/** Werkzeug → Eingang des Servers. */
function captureEntry(c: Capture): TimeEntryIn | null {
  if (!c.what) return null;
  if (c.what === 'in' || c.what === 'out') return { kind: c.what, day: c.day, time: c.time.trim() };
  const until = parseDay(c.until);
  const minutes = c.scope === 'hours' ? parseHm(c.dur) : null;
  if (!until || (c.scope === 'hours' && minutes == null)) return null;
  return { kind: 'absence', art: c.what, day: c.day, until, minutes };
}

function StampRow({ s, editable, onSave, onVoid }: {
  s: TimeStamp; editable: boolean;
  onSave: (time: string) => Promise<string | null>; onVoid: () => void;
}) {
  const [edit, setEdit] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const label = s.kind === 'in' ? 'Kommen' : 'Gehen';
  if (edit != null) {
    const ok = parseClock(edit) != null;
    const save = async () => { const e = await onSave(edit); if (e) setErr(e); else setEdit(null); };
    return (
      <div style={{ display: 'grid', gap: 8 }}>
        <div style={ROW_FORM}>
          <TimeField id={`st-${s.id}`} label={label} value={edit} onChange={(v) => { setEdit(v); setErr(null); }}
            info="Bleibt die Zeit gleich, ändert sich nichts." bad={!ok} placeholder="HH:MM" width={120}
            onEnter={ok ? save : undefined} />
          <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!ok} onClick={save}>
            <Check size={15} />Übernehmen</button>
          <button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onVoid}
            data-tip="Wird festgehalten, nicht gelöscht"><Undo2 size={14} />Zurücknehmen</button>
        </div>
        {err && <ErrorText msg={err} />}
      </div>
    );
  }
  const m = s.mark;
  return (
    <LedgerRow ident={<><Dot color={s.kind === 'in' ? 'var(--success)' : 'var(--danger)'} />{label}</>}
      actions={editable ? <IconButton icon={Pencil} label="Stempel korrigieren" onClick={() => setEdit(s.time)} /> : undefined}
      date={m ? <Pill tone="neutral" label={m.label} tip={m.tip}
        icon={m.kind === 'changed' ? Pencil : m.kind === 'added' ? Plus : undefined} /> : undefined}
      amount={s.time} />
  );
}

function AbsenceRow({ a, view, onVoid, onProof }: {
  a: TimeAbsence; view: TimeView; onVoid: () => void; onProof: () => void;
}) {
  const art = view.vocab.arts.find((x) => x.key === a.art);
  const Icon = timeIcon(art?.icon ?? '');
  const multi = a.day !== a.until;
  const proof = a.proof_needed && art?.proof
    ? (a.proof_url
      ? <a href={assetUrl(a.proof_url)} target="_blank" rel="noreferrer"><Pill tone="done" label={art.proof} icon={FileCheck} tip="Nachgereicht – öffnen" /></a>
      : <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          {/* «fehlt» erst ab dem Tag, ab dem er nötig ist – hochladen geht schon vorher. */}
          {a.proof_missing && <Pill tone="pending" label={`${art.proof} fehlt`} />}
          <button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onProof}
            style={{ height: 24, padding: '0 9px', fontSize: 11.5 }}
            data-tip="Scannen oder als Datei – wird ein Dokument, jederzeit nachreichbar">
            <Upload size={12} />Nachreichen
          </button>
        </span>)
    : null;
  return (
    <LedgerRow
      ident={<span data-tip={art ? `${art.effect_label}: ${art.effect_tip}` : undefined} style={{ cursor: 'help' }}>
        <Icon size={13} style={{ display: 'inline', verticalAlign: -2, marginRight: 8, color: 'var(--fg-3)' }} />
        {art?.label ?? a.art}{a.note ? ` · ${a.note}` : ''}</span>}
      meta={multi ? `${dayShort(a.day)}–${dayShort(a.until)}` : undefined}
      actions={a.can_void ? <IconButton icon={Undo2} label="Zurücknehmen – wird festgehalten, nicht gelöscht" onClick={onVoid} /> : undefined}
      date={<>{a.replaces && <Pill tone="neutral" label="ersetzt" icon={Undo2} tip={a.replaces} />}{proof}</>}
      amount={`${hm(a.minutes_on_day)} h`} />
  );
}

function CaptureTool({ view, d, cap, setCap, onSubmit, preview }: {
  view: TimeView; d: TimeDay; cap: Capture; setCap: (c: Capture | null) => void;
  onSubmit: (entry: TimeEntryIn) => Promise<string | null>; preview: Preview | null;
}) {
  const [err, setErr] = useState<string | null>(null);
  const stamps = !d.future ? [
    { value: 'in', label: 'Kommen', icon: LogIn }, { value: 'out', label: 'Gehen', icon: LogOut },
  ] : [];
  const arts = d.workday ? view.vocab.arts.map((a) => ({ value: a.key, label: a.label, icon: timeIcon(a.icon) })) : [];
  const options = [...stamps, ...arts];
  const sel = options.find((o) => o.value === cap.what);
  const isStamp = cap.what === 'in' || cap.what === 'out';
  const entry = captureEntry(cap);
  const problem = err ?? preview?.problem ?? null;
  const set = (patch: Partial<Capture>) => { setErr(null); setCap({ ...cap, ...patch }); };
  const submit = async () => { if (entry) { const e = await onSubmit(entry); if (e) setErr(e); } };
  const vac = preview?.vacation_after != null ? vacationText(preview.vacation_after, view.day_soll) : null;
  const art = view.vocab.arts.find((a) => a.key === cap.what);
  return (
    <div style={{ display: 'grid', gap: 12, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ font: '600 13.5px var(--font-body)' }}>Erfassen{sel && <> · <span style={{ color: 'var(--accent-ink)' }}>{sel.label}</span></>}</span>
        <InfoHint text={view.vocab.texts.capture} />
        <span style={{ flex: 1 }} />
        <IconButton icon={ChevronDown} label="Schliessen" onClick={() => setCap(null)} />
      </div>
      {options.length ? <IconBar value={cap.what} options={options} onChange={(v) => set({ what: v })} />
        : <Note>An diesem Tag lässt sich nichts erfassen.</Note>}
      {isStamp && (
        <div style={ROW_FORM}>
          <TimeField id="cap-time" label="Uhrzeit" value={cap.time} onChange={(v) => set({ time: v })}
            bad={parseClock(cap.time) == null} placeholder="HH:MM" width={120}
            onEnter={!problem && parseClock(cap.time) != null ? submit : undefined} />
          <button type="button" className="erp-actbtn erp-actbtn-primary" onClick={submit}
            disabled={parseClock(cap.time) == null || !!problem}><Plus size={15} />Erfassen</button>
        </div>
      )}
      {art && (
        <>
          <div style={ROW_FORM}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)', display: 'inline-flex', gap: 5, alignItems: 'center' }}>
                Umfang<InfoHint text={`${view.vocab.texts.scope} Tagessoll: ${hm(d.soll)} h.`} /></span>
              <IconSwitch value={cap.scope} onChange={(v) => set({ scope: v })} labelActiveOnly options={[
                { value: 'full', label: 'Ganzer Tag', icon: Calendar }, { value: 'hours', label: 'Stunden', icon: Clock },
              ]} />
            </div>
            {cap.scope === 'hours' && (
              <TimeField id="cap-dur" label="Dauer pro Tag" value={cap.dur} onChange={(v) => set({ dur: v })}
                bad={parseHm(cap.dur) == null} placeholder="H:MM" width={110} />
            )}
            <TimeField id="cap-until" label="Bis" value={cap.until} onChange={(v) => set({ until: v })}
              info={view.vocab.texts.until} bad={!parseDay(cap.until)} placeholder="TT.MM.JJJJ" width={140} />
          </div>
          {problem && <ErrorText msg={problem} />}
          {preview && !preview.problem && (
            <div style={{ display: 'grid', gap: 6 }}>
              {preview.replaces && <Row k="Ersetzt" v={preview.replaces}
                hint="Die neue Absenz gilt an diesen Tagen. Ferientage, an denen man krank war, kommen zurück." />}
              <Row k="Wirkung" v={art.effect_label} hint={art.effect_tip} />
              <Row k="Arbeitstage · Stunden" v={`${preview.workdays} · ${hm(preview.minutes)} h`}
                hint="Nur Arbeitstage gemäss Vertrag; Feiertage am Standort zählen nicht." />
              {vac && (art.effect !== 'fulfilled' || preview.replaces) && (
                <Row k="Ferien danach" v={`${vac.h} ${vac.d}`}
                  hint={preview.vacation_after! < 0 ? 'Ferien im Voraus – erlaubt, das Guthaben wächst täglich wieder an.'
                    : 'Guthaben heute, wenn diese Absenz gilt.'} />
              )}
            </div>
          )}
          {preview?.proof && (
            <Row k={preview.proof} v={`ab dem ${preview.proof_from}. Arbeitstag`}
              hint="Nach dem Erfassen am Eintrag nachreichen – gescannt oder als Datei, er wird ein Dokument." />
          )}
          <StageAction icon={Plus} label="Erfassen" disabled={!entry || !!problem || !preview || !preview.workdays}
            onClick={submit} />
        </>
      )}
      {isStamp && problem && <ErrorText msg={problem} />}
    </div>
  );
}

export function TimeDayDetail({ view, d, cap, setCap, preview, onEntry, onProof }: {
  view: TimeView; d: TimeDay; cap: Capture | null; setCap: (c: Capture | null) => void;
  preview: Preview | null;
  onEntry: (entry: TimeEntryIn) => Promise<string | null>;
  onProof: (absence: TimeAbsence) => void;
}) {
  const hints = d.hints.filter((h) => h !== 'open' && h !== 'proof')
    .map((h) => view.vocab.hints.find((x) => x.key === h)).filter((h) => !!h);
  const hintInfo = hints.some((h) => h?.key === 'pause') ? view.vocab.texts.pause
    : hints.length ? view.vocab.texts.limits : null;
  const editable = !d.locked && !d.future;
  const canCapture = !d.locked && (d.workday || !d.future);
  // Was ohne eigenes Formular geschieht (Zurücknehmen), meldet sich hier – nie still.
  const [err, setErr] = useState<string | null>(null);
  const act = (e: TimeEntryIn) => { setErr(null); onEntry(e).then(setErr); };
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ font: '600 14px var(--font-body)', color: 'var(--fg-1)' }}>{dayTitle(d.day)}</span>
        {hints.map((h) => h && <Pill key={h.key} tone={h.tone === 'danger' ? 'danger' : 'pending'}
          label={h.label} icon={timeIcon(h.icon)} />)}
        {hintInfo && <InfoHint text={hintInfo} />}
      </div>
      {d.locked && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)' }}>
          Abgeschlossen – Änderung über die Administration<InfoHint text={view.vocab.texts.locked} />
        </div>
      )}
      {!d.workday && !d.stamps.length && <Note>{d.holiday ? `${d.holiday} – Feiertag am Standort.` : 'Kein Arbeitstag.'}</Note>}
      {d.workday && d.future && !d.absence && <Note>Noch nichts erfasst.</Note>}
      {(d.stamps.length > 0 || d.open || d.absence) && (
        <div style={{ display: 'grid', gap: 10 }}>
          {d.stamps.map((s) => (
            <div key={s.id} style={{ display: 'grid', gap: 10 }}>
              <StampRow s={s} editable={editable}
                onSave={(time) => onEntry({ kind: s.kind, replaces_id: s.id, time })}
                onVoid={() => act({ kind: 'void', replaces_id: s.id })} />
              {/* «Gehen» fehlt – direkt unter dem Kommen, zu dem es gehört. */}
              {s.missing_out && (
                <LedgerRow ident={<><Dot color="var(--danger)" />Gehen</>}
                  actions={editable ? <IconButton icon={Plus} label="Erfassen" onClick={() => setCap(captureFor(d.day, 'out'))} /> : undefined}
                  date={<Pill tone="pending" label="fehlt" />} amount={<span style={{ color: 'var(--fg-4)' }}>–</span>} />
              )}
            </div>
          ))}
          {d.absence && <AbsenceRow a={d.absence} view={view}
            onVoid={() => act({ kind: 'void', replaces_id: d.absence!.id })}
            onProof={() => onProof(d.absence!)} />}
        </div>
      )}
      {err && <ErrorText msg={err} />}
      {cap && cap.day === d.day
        ? <CaptureTool view={view} d={d} cap={cap} setCap={setCap} preview={preview}
            onSubmit={(entry) => onEntry(entry)} />
        : canCapture && <QuietButton icon={Plus} label="Erfassen" onClick={() => setCap(captureFor(d.day))} />}
    </div>
  );
}

/** Die Vorschau zum Werkzeug – nachgeladen, sobald sich eine Eingabe ändert. */
export function usePreview(person: number, cap: Capture | null): Preview | null {
  const [p, setP] = useState<Preview | null>(null);
  const entry = cap ? captureEntry(cap) : null;
  const key = JSON.stringify(entry);
  useEffect(() => {
    setP(null);
    if (!entry) return;
    if ((entry.kind === 'in' || entry.kind === 'out') && parseClock(entry.time ?? '') == null) return;
    let live = true;
    const t = setTimeout(() => {
      api.timePreview(person, entry).then((r) => { if (live) setP(r); }).catch(() => {});
    }, 250);
    return () => { live = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [person, key]);
  return p;
}
