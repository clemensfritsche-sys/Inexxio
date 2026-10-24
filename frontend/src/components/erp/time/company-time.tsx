'use client';

/**
 * ►►► **Zeiterfassung einer eigenen Gesellschaft – EINE kompakte Karte (Admin).** ◄◄◄
 *
 * Feiertage je Jahr (Vorschlag aus OpenHolidays für den Kanton, abwählen, übernehmen; ein
 * Ortsfeiertag von Hand), die Absenzarten mit ihrem Nachweis und die Regeln des Landes. Es
 * zählt nur, was übernommen ist. Fehlen die Feiertage, steht die Zahl am Symbol.
 */
import { useEffect, useState } from 'react';
import { CalendarDays, CalendarPlus, Check, ChevronLeft, ChevronRight, Clock, Download, Pencil, Plus, Scale, Trash2 } from 'lucide-react';
import { Card, ErrorText, MICRO_LABEL, TodoChip } from '@/components/erp/fields';
import { StageAction } from '@/components/erp/module-ui';
import { ApiError, api } from '@/lib/api';
import { dayShort, parseDay } from '@/lib/when';
import { todoChanged } from '@/lib/todo';
import type { CompanyTimeView, HolidayOut, TodoItem } from '@/types';
import { HR, IconButton, Note, QuietButton, ROW_FORM, Sect, TimeField, timeIcon } from './time-ui';

const GRID = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 190px), 1fr))', gap: '8px 20px' } as const;

function err(e: unknown): string {
  return e instanceof ApiError ? e.message : 'Keine Verbindung – nicht gespeichert.';
}

function Holidays({ v, company, onView, todo }: {
  v: CompanyTimeView; company: number; onView: (v: CompanyTimeView) => void; todo: TodoItem[];
}) {
  const [prop, setProp] = useState<(HolidayOut & { on: boolean })[] | null>(null);
  const [add, setAdd] = useState<{ d: string; n: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = (p: Promise<CompanyTimeView>) => {
    setBusy(true); setMsg(null);
    p.then((x) => { onView(x); setProp(null); setAdd(null); todoChanged(); })
      .catch((e) => setMsg(err(e))).finally(() => setBusy(false));
  };
  const load = () => {
    setBusy(true); setMsg(null);
    api.holidayProposal(company, v.year).then((list) => setProp(list.map((h) => ({ ...h, on: !h.taken }))))
      .catch((e) => setMsg(err(e))).finally(() => setBusy(false));
  };
  const canton = v.cantons.find(([c]) => c === v.canton);
  const year = (y: number) => api.companyTime(company, y).then(onView).catch((e) => setMsg(err(e)));
  const n = prop?.filter((h) => h.on && !h.taken).length ?? 0;
  const iso = add ? parseDay(add.d) : null;
  return (
    <Sect icon={CalendarDays} title={<>Feiertage{canton ? ` · ${canton[1]}` : ''}<TodoChip items={todo} /></>}
      info={v.vocab.texts.holidays}
      right={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <IconButton icon={ChevronLeft} label="Voriges Jahr" height={24} onClick={() => year(v.year - 1)} />
        <span className="tabular-nums" style={{ font: '600 13px var(--font-body)', minWidth: 36, textAlign: 'center' }}>{v.year}</span>
        <IconButton icon={ChevronRight} label="Nächstes Jahr" height={24} onClick={() => year(v.year + 1)} />
      </span>}>
      {v.can_edit && (
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, color: 'var(--fg-2)' }}>
          Kanton
          <select value={v.canton ?? ''} disabled={busy}
            onChange={(e) => run(api.setTimeRules(company, { canton: e.target.value || null }, v.year))}
            style={{ padding: '4px 8px', borderRadius: 8, border: '1px solid var(--border-1)', background: 'var(--bg-1)', fontSize: 13 }}>
            <option value="">–</option>
            {v.cantons.map(([c, name]) => <option key={c} value={c}>{c} · {name}</option>)}
          </select>
        </label>
      )}
      {v.holidays.length > 0 && (
        <div style={GRID}>
          {v.holidays.map((h) => (
            <span key={h.id ?? h.day} className="ix-row" style={{ display: 'flex', gap: 10, fontSize: 13, alignItems: 'center' }}>
              <span className="tabular-nums" style={{ color: 'var(--fg-3)', minWidth: 52 }}>{dayShort(h.day)}</span>
              <span style={{ color: 'var(--fg-1)', flex: 1, minWidth: 0 }} className="truncate">{h.name}</span>
              {v.can_edit && h.id != null && (
                <span className="ix-rowactions ix-actions">
                  <IconButton icon={Trash2} label="Feiertag entfernen" height={22}
                    onClick={() => run(api.removeHoliday(company, h.id as number, v.year))} />
                </span>
              )}
            </span>
          ))}
        </div>
      )}
      {!v.holidays.length && !prop && <Note>Noch keine Feiertage für {v.year}.</Note>}
      {v.can_edit && !prop && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <QuietButton icon={Download} label={`Vorschlag${canton ? ` für Kanton ${canton[0]}` : ''} laden`}
            onClick={load} disabled={busy || !v.canton} tip={v.canton ? undefined : 'Zuerst den Kanton wählen'} />
          {!add && <QuietButton icon={Plus} label="Ortsfeiertag" onClick={() => setAdd({ d: '', n: '' })} />}
        </div>
      )}
      {prop && (
        <>
          <div style={GRID}>
            {prop.map((h, i) => (
              <label key={h.day} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer',
                opacity: h.taken ? 0.55 : 1 }}>
                <input type="checkbox" checked={h.on || h.taken} disabled={h.taken}
                  onChange={() => setProp(prop.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))}
                  style={{ accentColor: 'var(--accent)', width: 15, height: 15, margin: 0 }} />
                <span className="tabular-nums" style={{ color: 'var(--fg-3)', minWidth: 52 }}>{dayShort(h.day)}</span>
                <span>{h.name}</span>
              </label>
            ))}
          </div>
          {!prop.length && <Note>Der Vorschlag ist leer – Feiertage lassen sich von Hand eintragen.</Note>}
          <StageAction icon={Check} label={`Übernehmen (${n})`} disabled={!n || busy}
            onClick={() => run(api.addHolidays(company, prop.filter((h) => h.on && !h.taken)
              .map((h) => ({ day: h.day, name: h.name })), v.year))} />
        </>
      )}
      {add && (
        <div style={ROW_FORM}>
          <TimeField id="nh-d" label="Datum" value={add.d} onChange={(d) => setAdd({ ...add, d })} bad={!iso} placeholder="TT.MM.JJJJ" width={140} />
          <TimeField id="nh-n" label="Bezeichnung" value={add.n} onChange={(x) => setAdd({ ...add, n: x })} placeholder="z. B. Ortsfeiertag" width={220} />
          <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!iso || !add.n.trim() || busy}
            onClick={() => iso && run(api.addHolidays(company, [{ day: iso, name: add.n.trim() }], v.year))}>
            <Plus size={15} />Hinzufügen</button>
        </div>
      )}
      {msg && <ErrorText msg={msg} />}
    </Sect>
  );
}

function Arts({ v, company, onView }: { v: CompanyTimeView; company: number; onView: (v: CompanyTimeView) => void }) {
  const [edit, setEdit] = useState<{ key: string; val: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const save = () => {
    if (!edit) return;
    const n = edit.val.trim() === '' ? null : Number(edit.val);
    api.setTimeRules(company, { proof: { [edit.key]: n } }, v.year)
      .then((x) => { onView(x); setEdit(null); setMsg(null); }).catch((e) => setMsg(err(e)));
  };
  return (
    <Sect icon={CalendarPlus} title="Absenzarten" info={v.vocab.texts.proof}>
      <div style={{ ...GRID, gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 230px), 1fr))' }}>
        {v.vocab.arts.map((a) => {
          const Icon = timeIcon(a.icon);
          if (edit?.key === a.key) {
            return (
              <div key={a.key} style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
                <TimeField id={`na-${a.key}`} label={`${a.label}: Nachweis ab Tag`} value={edit.val}
                  onChange={(val) => setEdit({ ...edit, val })} placeholder="leer = nie" onEnter={save} />
                <IconButton icon={Check} label="Übernehmen" height={36} onClick={save} />
              </div>
            );
          }
          const proof = a.proof ? (a.proof_from ? (a.proof_from > 1 ? `${a.proof} ab Tag ${a.proof_from}` : `${a.proof} immer`) : 'ohne Nachweis') : 'ohne Nachweis';
          return (
            <div key={a.key} className="ix-row" style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <Icon size={14} style={{ color: 'var(--fg-3)', marginTop: 2, flex: 'none' }} />
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ display: 'block', font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>{a.label}</span>
                <span style={{ display: 'block', fontSize: 12, color: 'var(--fg-3)' }}>{a.effect_label} · {proof}</span>
              </span>
              {v.can_edit && a.proof && (
                <span className="ix-rowactions ix-actions" style={{ flex: 'none' }}>
                  <IconButton icon={Pencil} label="Nachweis ändern"
                    onClick={() => setEdit({ key: a.key, val: a.proof_from ? String(a.proof_from) : '' })} />
                </span>
              )}
            </div>
          );
        })}
      </div>
      {msg && <ErrorText msg={msg} />}
    </Sect>
  );
}

export function CompanyTime({ company, todo }: { company: number; todo: TodoItem[] }) {
  const [v, setV] = useState<CompanyTimeView | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { api.companyTime(company).then(setV).catch((e) => setMsg(err(e))); }, [company]);
  return (
    <Card icon={Clock} title="Zeiterfassung" unclipped anchor="feiertage">
      {!v ? (msg ? <ErrorText msg={msg} /> : <Note>Laden…</Note>) : (
        <>
          <Holidays v={v} company={company} onView={setV} todo={todo} />
          {HR}
          <Arts v={v} company={company} onView={setV} />
          {HR}
          <Sect icon={Scale} title="Regeln · Schweiz" info={v.vocab.texts.rules}>
            <div style={GRID}>
              {v.rules.map(([k, val]) => (
                <span key={k} style={{ display: 'grid', gap: 2 }}>
                  <span style={MICRO_LABEL}>{k}</span>
                  <span style={{ fontSize: 13, color: 'var(--fg-1)' }}>{val}</span>
                </span>
              ))}
            </div>
          </Sect>
        </>
      )}
    </Card>
  );
}
