'use client';

/**
 * ►►► **Vertrag und Buchungen** – aufgeklappt unter «Vertrag». ◄◄◄
 *
 * Ein Vertrag gilt ab seinem Stichtag (Eintritt = erster, Austritt = 0 h); jede Änderung ist
 * ein neuer Vertrag. Buchungen bewegen Stundenkonto und Ferien direkt (Übertrag bei
 * Einführung, Auszahlung, Korrektur) und werden nie geändert – ein Fehler ist eine
 * Gegenbuchung. Anlegen darf beides nur die Administration; prüfen tut der Server.
 */
import { useState } from 'react';
import { Check, Plus } from 'lucide-react';
import { ErrorText, InfoHint } from '@/components/erp/hints';
import { MICRO_LABEL, Row } from '@/components/erp/fields';
import { LedgerRow } from '@/components/erp/module-ui';
import { useErpNav } from '@/components/erp/obj-id';
import { day as dayText, parseDay } from '@/lib/when';
import type { TimeContract, TimeContractIn, TimeEntryIn, TimeView } from '@/types';
import {
  Note, Pill, QuietButton, ROW_FORM, TimeField, WEEKDAYS, daysLabel, hm, hours, parseHm, parseSigned,
  sgn, vacationText,
} from './time-ui';

const STATE = {
  current: { tone: 'done', label: 'Aktuell' },
  planned: { tone: 'pending', label: 'Geplant' },
  replaced: { tone: 'neutral', label: 'Abgelöst' },
} as const;

function ContractRow({ c, first, daySoll }: { c: TimeContract; first: boolean; daySoll: number }) {
  const nav = useErpNav();
  const exit = c.weekly_minutes === 0;
  const company = c.company_object_id != null && (
    <button type="button" className="erp-objid" style={{ font: 'inherit', color: 'var(--accent-ink)' }}
      data-tip="Gesellschaft öffnen – Feiertage und Regeln"
      onClick={() => nav?.(c.company_object_id as number)}>{c.company_name ?? c.company_object_id}</button>
  );
  const s = STATE[c.state];
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <LedgerRow ident={`${first ? 'Eintritt' : exit ? 'Austritt' : 'ab'} ${dayText(c.valid_from)}`}
        meta={<>{!exit && `${hours(c.weekly_minutes)} h/Woche · ${daysLabel(c.workdays)} · ${Number(c.vacation_weeks) ? `${Number(c.vacation_weeks)} Wochen Ferien` : 'Ferien gesetzlich'} · `}{company}</>}
        amount={<Pill tone={s.tone} label={s.label} />} />
      {exit && c.closing_day && c.closing_account != null && c.closing_vacation != null && (
        <Row k={`Schlussstand per ${dayText(c.closing_day)}`}
          v={`${sgn(c.closing_account)} h · Ferien ${Object.values(vacationText(c.closing_vacation, daySoll)).join(' ')}`}
          hint="Stundenkonto und Ferienguthaben am letzten Arbeitstag – der Wert für die Lohnabrechnung." />
      )}
    </div>
  );
}

function NewContract({ view, onSave }: {
  view: TimeView; onSave: (c: TimeContractIn) => Promise<string | null>;
}) {
  const [from, setFrom] = useState('');
  const [hours, setHours] = useState('42');
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [weeks, setWeeks] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const iso = parseDay(from);
  const minutes = parseHm(hours);
  const exit = minutes === 0;
  const w = weeks.trim() === '' ? null : Number(weeks.replace(',', '.'));
  const ok = !!iso && minutes != null && (exit || days.length > 0) && (w == null || !Number.isNaN(w));
  const save = async () => {
    if (!ok || !iso || minutes == null) return;
    const e = await onSave({ valid_from: iso, weekly_minutes: minutes, workdays: exit ? [] : days,
      vacation_weeks: exit ? null : w != null ? String(w) : null });
    setErr(e);
  };
  return (
    <div style={{ display: 'grid', gap: 8, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
      <div style={ROW_FORM}>
        <TimeField id="nc-from" label="Gültig ab" value={from} onChange={setFrom} bad={!iso}
          placeholder="TT.MM.JJJJ" width={140}
          info="Stichtag, auch in der Zukunft («Geplant»). Gesellschaft: die der Person." />
        <TimeField id="nc-hours" label="Wochenstunden" value={hours} onChange={setHours}
          bad={minutes == null} placeholder="h" width={110} info="0 h = Austritt" />
        {!exit && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)', display: 'inline-flex', gap: 5, alignItems: 'center' }}>
              Arbeitstage<InfoHint text="An diesen Tagen gilt das Soll: Wochenstunden ÷ Anzahl Tage. Samstag oder Sonntag möglich (Sonntag braucht eine Bewilligung)." /></span>
            <div style={{ display: 'flex', gap: 4 }}>
              {WEEKDAYS.map((label, i) => {
                const on = days.includes(i);
                return (
                  <button key={label} type="button" aria-pressed={on}
                    onClick={() => setDays(on ? days.filter((x) => x !== i) : [...days, i])}
                    style={{ width: 34, height: 36, borderRadius: 8, font: '600 12px var(--font-body)', cursor: 'pointer',
                      border: `1px solid ${on ? 'var(--accent)' : 'var(--border-2)'}`,
                      background: on ? 'var(--accent-soft)' : 'var(--bg-1)', color: on ? 'var(--accent-ink)' : 'var(--fg-3)' }}>
                    {label}</button>
                );
              })}
            </div>
          </div>
        )}
        {!exit && (
          <TimeField id="nc-weeks" label="Ferienwochen" value={weeks} onChange={setWeeks}
            placeholder="gesetzlich" width={110}
            info="Leer = gesetzlich (bis zum 20. Geburtstag 5, sonst 4 Wochen, Alter am Stichtag). Mehr ist möglich, weniger nicht." />
        )}
        <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!ok} onClick={save}>
          <Plus size={15} />{exit ? 'Austritt anlegen' : 'Vertrag anlegen'}</button>
      </div>
      {!view.born && <ErrorText msg="Geburtsdatum fehlt in den Stammdaten – es bestimmt Jugendschutz und gesetzliche Ferien." />}
      {err && <ErrorText msg={err} />}
    </div>
  );
}

function NewBooking({ view, onSave }: {
  view: TimeView; onSave: (e: TimeEntryIn) => Promise<string | null>;
}) {
  const [d, setD] = useState(dayText(view.today));
  const [h, setH] = useState('');
  const [f, setF] = useState('');
  const [note, setNote] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const iso = parseDay(d);
  const hours = parseSigned(h);
  const vac = parseSigned(f);
  const ok = !!iso && hours != null && vac != null && (!!hours || !!vac) && !!note.trim();
  const save = async () => {
    if (!ok || !iso) return;
    const e = await onSave({ kind: 'booking', day: iso, minutes: hours, vacation_minutes: vac, note: note.trim() });
    setErr(e);
    if (!e) { setH(''); setF(''); setNote(''); }
  };
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={ROW_FORM}>
        <TimeField id="nb-day" label="Datum" value={d} onChange={setD} bad={!iso} placeholder="TT.MM.JJJJ" width={140} />
        <TimeField id="nb-hours" label="Stunden ±" value={h} onChange={setH} bad={hours == null}
          placeholder="±H:MM" width={110} info="Positiv = Gutschrift, negativ = Abzug (z. B. −10:00 ausbezahlt)." />
        <TimeField id="nb-vac" label="Ferien ±" value={f} onChange={setF} bad={vac == null} placeholder="±H:MM"
          width={110} info={`In Stunden, wie alles. Ein Tag = Tagessoll des Vertrags (${hm(view.day_soll)} h).`} />
        <TimeField id="nb-note" label="Grund" value={note} onChange={setNote} placeholder="z. B. Auszahlung Oktober" width={220} />
        <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!ok} onClick={save}>
          <Check size={15} />Buchen</button>
      </div>
      {err && <ErrorText msg={err} />}
    </div>
  );
}

export function TimeContracts({ view, onContract, onEntry }: {
  view: TimeView;
  onContract: (c: TimeContractIn) => Promise<string | null>;
  onEntry: (e: TimeEntryIn) => Promise<string | null>;
}) {
  const [newC, setNewC] = useState(false);
  const [newB, setNewB] = useState(false);
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'grid', gap: 10 }}>
        {view.contracts.map((c, i) => <ContractRow key={c.id} c={c} first={i === 0} daySoll={view.day_soll} />)}
        {!view.contracts.length && <Note>Noch kein Vertrag – ohne Vertrag gibt es kein Soll.</Note>}
      </div>
      {view.is_admin && (newC
        ? <NewContract view={view} onSave={async (c) => { const e = await onContract(c); if (!e) setNewC(false); return e; }} />
        : <QuietButton icon={Plus} label="Neuer Vertrag" onClick={() => setNewC(true)} />)}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Buchungen</span>
        <InfoHint text={view.vocab.texts.bookings} />
      </div>
      {view.bookings.length ? (
        <div style={{ display: 'grid', gap: 10 }}>
          {view.bookings.map((b) => {
            const parts = [b.minutes ? `${sgn(b.minutes)} h` : '',
              b.vacation_minutes ? `Ferien ${Object.values(vacationText(b.vacation_minutes, view.day_soll, true)).join(' ')}` : '']
              .filter(Boolean);
            return (
              <LedgerRow key={b.id} ident={dayText(b.day)} meta={b.note}
                date={b.by ? <span data-tip={`Gebucht von ${b.by}`} style={{ fontSize: 11.5, cursor: 'help' }}>{b.by}</span> : undefined}
                amount={parts.join(' · ')} />
            );
          })}
        </div>
      ) : <Note>Keine Buchungen.</Note>}
      {view.is_admin && (newB
        ? <NewBooking view={view} onSave={onEntry} />
        : <QuietButton icon={Plus} label="Neue Buchung" onClick={() => setNewB(true)} />)}
    </div>
  );
}
