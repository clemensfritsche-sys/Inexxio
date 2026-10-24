'use client';

/**
 * ►►► **Zeiterfassung – EINE Karte im Personendatensatz.** ◄◄◄
 *
 * Wischknopf (Kommen ↔ Gehen, mit dem Tag als Fortschritt), drei Kennzahlen (Stundenkonto ·
 * Ferien · Vertrag, aufklappbar), darunter Monat und Tag. Sichtbar nur im eigenen
 * Datensatz und für den Admin (der Server prüft es, `timekeeping.may_see`). Jede Handlung
 * antwortet mit der neuen Ansicht – es gibt keinen zweiten Zustand im Browser.
 *
 * **Nur online**: ohne Netz wird nichts gespeichert, ein Satz sagt es.
 */
import { useCallback, useEffect, useState } from 'react';
import { Briefcase, ChevronDown, ChevronRight, Clock, Sun, Timer } from 'lucide-react';
import { Card, ErrorText, InfoHint, MICRO_LABEL } from '@/components/erp/fields';
import { ApiError, api } from '@/lib/api';
import { parseDay } from '@/lib/when';
import { todoChanged } from '@/lib/todo';
import type { TimeContractIn, TimeEntryIn, TimeView } from '@/types';
import { TimeCalendar } from './time-calendar';
import { TimeContracts } from './time-contracts';
import { type Capture, TimeDayDetail, usePreview } from './time-day';
import { TimeSwipe } from './time-swipe';
import { Note, daysLabel, hours, sgn, vacationText } from './time-ui';

const OFFLINE = 'Keine Verbindung – nicht gespeichert. Bitte erneut versuchen, sobald das Netz da ist.';
const OFFLINE_SWIPE = 'Keine Verbindung – nicht gestempelt. Bitte erneut wischen, sobald das Netz da ist.';

function message(e: unknown, offline: string): string {
  return e instanceof ApiError ? e.message : offline;
}

function shiftMonth(month: string, step: number): string {
  const [y, m] = month.split('-').map(Number);
  const d = new Date(y, m - 1 + step, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function Figure({ icon: Icon, label, info, children, color }: {
  icon: React.ElementType; label: string; info: string; children: React.ReactNode; color?: string;
}) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <span style={{ width: 22, height: 22, color: 'var(--fg-4)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', flex: 'none', marginTop: 2 }}><Icon size={18} /></span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ ...MICRO_LABEL, display: 'flex', alignItems: 'center', gap: 5 }}>{label}<InfoHint text={info} /></div>
        <div className="tabular-nums" style={{ font: '600 15.5px var(--font-body)', color: color ?? 'var(--fg-1)',
          marginTop: 6, lineHeight: 1.35 }}>{children}</div>
      </div>
    </div>
  );
}

export function TimeCard({ person }: { person: number }) {
  const [view, setView] = useState<TimeView | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);
  const [sel, setSel] = useState<string | null>(null);
  const [cap, setCap] = useState<Capture | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [swipeErr, setSwipeErr] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const preview = usePreview(person, cap);

  const show = useCallback((v: TimeView) => {
    setView(v);
    setSel((s) => s ?? v.default_day);
  }, []);
  useEffect(() => {
    api.timeView(person, month).then((v) => { setLoadErr(null); show(v); })
      .catch((e) => setLoadErr(message(e, OFFLINE)));
  }, [person, month, show]);

  const swipe = async () => {
    if (!view || busy) return;
    setBusy(true); setSwipeErr(null);
    const key = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    try {
      show(await api.timeSwipe(person, view.present_since ? 'out' : 'in', key, view.month));
      todoChanged();
    } catch (e) {
      setSwipeErr(message(e, OFFLINE_SWIPE));
    } finally {
      setBusy(false);
    }
  };
  /** Ein Eintrag (mit Nachweis-Bild, falls gewählt) – `null` = geklappt, sonst der Satz. */
  const entry = async (data: TimeEntryIn, file?: File | null): Promise<string | null> => {
    try {
      const payload = { ...data };
      if (file) payload.proof_url = (await api.uploadAttachment(file)).url;
      show(await api.timeEntry(person, payload, view?.month));
      setCap(null);
      todoChanged();
      return null;
    } catch (e) {
      return message(e, OFFLINE);
    }
  };
  const proof = (absence: number, file: File) => {
    entry({ kind: 'proof', replaces_id: absence }, file).then((e) => { if (e) setSwipeErr(e); });
  };
  const contract = async (c: TimeContractIn): Promise<string | null> => {
    try {
      show(await api.timeContract(person, c, view?.month));
      todoChanged();
      return null;
    } catch (e) {
      return message(e, OFFLINE);
    }
  };

  if (!view) {
    return (
      <Card icon={Clock} title="Zeiterfassung" unclipped>
        {loadErr ? <ErrorText msg={loadErr} /> : <Note>Laden…</Note>}
      </Card>
    );
  }
  const current = view.contracts.find((c) => c.state === 'current');
  const vac = vacationText(view.vacation, view.day_soll);
  const selDay = view.days.find((d) => d.day === sel) ?? null;
  const isAbsence = !!cap?.what && cap.what !== 'in' && cap.what !== 'out';
  const until = cap && isAbsence ? parseDay(cap.until) : null;
  const pick = (d: string) => {
    // Im Werkzeug für eine Absenz setzt ein späterer Tag das «Bis».
    if (cap && isAbsence && d > cap.day) {
      setCap({ ...cap, until: d.split('-').reverse().join('.') });
      return;
    }
    setSel(d);
    setCap(null);
  };
  return (
    <Card icon={Clock} title="Zeiterfassung" info={view.vocab.texts.card} unclipped>
      {view.can_stamp && (
        <div style={{ display: 'grid', gap: 4 }}>
          <TimeSwipe present={!!view.present_since} since={view.present_since ?? null}
            lastOut={view.last_out ?? null} ist={view.today_ist} soll={view.today_soll}
            busy={busy} onSwipe={swipe} />
          {swipeErr && <ErrorText msg={swipeErr} />}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: '20px 24px' }}>
        <Figure icon={Timer} label="Stundenkonto" info={view.vocab.texts.account}
          color={view.account < 0 ? 'var(--danger)' : undefined}>{sgn(view.account)} h</Figure>
        <Figure icon={Sun} label="Ferien" info={view.vocab.texts.vacation}
          color={view.vacation < 0 ? 'var(--danger)' : undefined}>
          {vac.h} <span style={{ color: 'var(--fg-3)', fontWeight: 500 }}>{vac.d}</span></Figure>
        <Figure icon={Briefcase} label="Vertrag" info={view.vocab.texts.contract}>
          <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
            style={{ border: 0, background: 'none', padding: 0, font: 'inherit', color: 'var(--accent-ink)',
              cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            {current ? `${hours(current.weekly_minutes)} h · ${daysLabel(current.workdays)}` : 'Kein Vertrag'}
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        </Figure>
      </div>
      {open && <TimeContracts view={view} onContract={contract} onEntry={entry} />}
      {view.has_contract && (
        <>
          <div style={{ height: 1, background: 'var(--border-1)' }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 330px), 1fr))',
            gap: '24px 32px', alignItems: 'start' }}>
            <TimeCalendar month={view.month} days={view.days} vocab={view.vocab} selected={sel}
              range={cap && until ? { from: cap.day, until } : null}
              onPick={pick} onMonth={(step) => { setCap(null); setMonth(shiftMonth(view.month, step)); }} />
            <div style={{ minWidth: 0 }}>
              {selDay
                ? <TimeDayDetail view={view} d={selDay} cap={cap} setCap={setCap} preview={preview}
                    onEntry={entry} onProof={proof} />
                : <Note>Einen Tag wählen.</Note>}
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
