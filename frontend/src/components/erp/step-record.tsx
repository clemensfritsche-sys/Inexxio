'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Check, Keyboard, Minus, ScanLine } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import type { RecordEntry, RecordValue } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { UnitNumber } from '@/components/erp/unit-number';
import { localDateTime } from '@/lib/utils';

/**
 * ►►► **Ein abgeschlossenes Modul zeigt lückenlos, was in ihm passiert ist.** ◄◄◄
 *
 * Die Regel gilt für **alle** Module – heute und künftig (Testnotiz #717). Darum steht
 * sie an genau einer Stelle: hier, und im Server als **eine** Ableitung über den
 * Ereignis-Log (`services/record`). Ein Protokoll je Modultyp wäre dieselbe Ansicht
 * n-mal, und die (n+1)-te fehlte beim nächsten Typ – genau die Sorte Lücke, die man erst
 * bemerkt, wenn jemand einen Nachweis braucht.
 *
 * **Ein Eintrag ist ein Vorgang, kein Stück.** Ein Stück kann dasselbe Modul mehrfach
 * passieren (nach einem «nicht bestanden» wird erneut erfasst) – beides ist passiert,
 * also steht beides da. Zusammengefasst überschriebe die Wiederholung die Vergangenheit.
 *
 * **Erst auf Klick, nie auf Vorrat.** Die Karte rendert ihren Inhalt nur aufgeklappt;
 * geladen wird darum genau dann. Bei einer 6000er-Charge wären es tausende Einträge in
 * jeder Auftrags-Antwort.
 */
export function StepRecord({ orderObjectId, stepId }: {
  orderObjectId: number;
  stepId: number;
}) {
  const [rows, setRows] = useState<RecordEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    api.stepRecord(orderObjectId, stepId)
      .then((r) => { if (!dead) { setRows(r.entries ?? []); setTotal(r.total ?? 0); } })
      .catch((e) => { if (!dead) setErr(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [orderObjectId, stepId]);

  if (err) return <p className="text-xs" style={{ color: 'var(--danger)' }}>{err}</p>;
  if (rows === null) {
    return <p className="text-xs" style={{ color: 'var(--fg-4)' }}>lädt …</p>;
  }
  if (rows.length === 0) {
    return (
      <p className="text-xs" style={{ color: 'var(--fg-4)' }}>
        Hier ist noch nichts passiert.
      </p>
    );
  }

  return (
    <div className="flex flex-col">
      {/* ►►► **Die Liste sagt, WAS sie ist** (Testnotiz #801). ◄◄◄
          Ohne Überschrift stand hier eine Einzelinstanz mit einem Namen und einer
          Uhrzeit – und die Frage «warum steht die hier?» war völlig berechtigt: sie ist
          der **Nachweis** dieses Moduls, aber nichts sagte das. Bei einem Modul, das am
          Stück nichts ändert (ein Geldvorgang), bleibt genau das übrig: wer wann was
          bestätigt hat. Das ist die Aussage – man muss sie nur lesen können.

          Sie steht als Versalien-Mikro-Label über der Liste, wie jede Abschnitts-Marke
          im Haus, und nennt die Gesamtzahl statt sie zu verschweigen. */}
      <div className="flex items-baseline gap-2" style={{ marginBottom: 4 }}>
        <span style={{
          font: '700 11px var(--font-body)', textTransform: 'uppercase',
          letterSpacing: '.07em', color: 'var(--fg-4)',
        }}>Was hier passiert ist</span>
        <span className="ix-tnum text-[11px]" style={{ color: 'var(--fg-4)' }}
          data-tip="Ein Eintrag ist ein Vorgang, kein Stück – ein Stück kann dasselbe
                    Modul mehrfach passieren.">
          {total} {total === 1 ? 'Vorgang' : 'Vorgänge'}
        </span>
      </div>
      {rows.map((e, i) => <Row key={`${e.number}-${e.at}-${i}`} entry={e} first={i === 0} />)}
      {rows.length < total && (
        <p className="mt-1.5 text-[11.5px]" style={{ color: 'var(--fg-4)' }}>
          {rows.length} von {total} Vorgängen – die neuesten stehen weiter unten.
        </p>
      )}
    </div>
  );
}

/** Ein Vorgang: **wer, wann, womit bestätigt** – und darunter jede erfasste Angabe. */
function Row({ entry, first }: { entry: RecordEntry; first: boolean }) {
  // **Nur eine Änderung ist eine Aussage** (Testnotiz #726). Ein Durchläufer
  // (Datenerfassung, Bewegen) führt «Im Prozess» → «Im Prozess»; in jeder Zeile stünde
  // dasselbe Wort. Gefragt wird nach den **Daten**, nicht nach dem Modultyp – die
  // Oberfläche muss nicht wissen, welcher Typ was tut.
  const changed = !!entry.status_after && entry.status_after !== entry.status_before;
  const cfg = changed && entry.status_after ? statusCfg(entry.status_after) : null;
  const values = entry.values ?? [];
  return (
    <div className="flex flex-col gap-1 py-1.5"
      style={first ? undefined : { borderTop: '1px solid var(--border-1)' }}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <UnitNumber value={entry.number} />
        {/* **Wie bestätigt wurde**, sagt ein Symbol – ohne den Vermerk wäre die Tastatur
            von der Kamera hinterher nicht zu unterscheiden (§4.4). */}
        {entry.verification === 'scan' && (
          <ScanLine size={12} style={{ color: 'var(--fg-4)' }} data-tip="Gescannt" />
        )}
        {entry.verification === 'manual' && (
          <Keyboard size={12} style={{ color: 'var(--warning)' }}
            data-tip="Von Hand bestätigt – erlaubt, protokolliert, und als das erkennbar" />
        )}
        {entry.result === 'failed' && (
          <span className="flex items-center gap-1 text-[11.5px]" style={{ color: 'var(--danger)' }}>
            <AlertTriangle size={12} /> nicht bestanden
          </span>
        )}
        {entry.result === 'passed' && (
          <Check size={12} style={{ color: 'var(--success)' }} data-tip="Bestanden" />
        )}
        {!entry.sampled && (
          <span className="flex items-center gap-1 text-[11.5px]" style={{ color: 'var(--fg-4)' }}
            data-tip="Ausserhalb der Ziehung – ohne Erfassung durchgelaufen (§9.3)">
            <Minus size={12} /> nicht gezogen
          </span>
        )}
        {entry.into && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
            verbaut in <UnitNumber value={entry.into} />
          </span>
        )}
        {cfg && (
          <span className="ml-auto flex items-center gap-1.5 text-[11.5px]"
            style={{ color: cfg.color }}>
            <span className="rounded-full" style={{
              width: 6, height: 6, background: cfg.color, flex: 'none',
            }} />
            {cfg.label}
          </span>
        )}
      </div>

      {values.length > 0 && (
        <div className="flex flex-col gap-1" style={{
          marginLeft: 10, paddingLeft: 10, borderLeft: '1px solid var(--border-1)',
        }}>
          {values.map((v) => <Value key={v.key} value={v} />)}
        </div>
      )}

      <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
        {[entry.actor, localDateTime(entry.at)].filter(Boolean).join(' · ')}
      </span>
    </div>
  );
}

/**
 * Ein erfasster Wert – **mit seiner Frage**. Bild und Unterschrift stehen als Bild da:
 * ein Nachweis, der als Pfad geschrieben ist, ist keiner, den man liest.
 */
function Value({ value }: { value: RecordValue }) {
  const tone = value.ok === false ? 'var(--danger)'
    : value.ok === true ? 'var(--success)' : 'var(--fg-2)';
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <span className="text-[11.5px]" style={{ color: 'var(--fg-4)' }}>{value.label}</span>
      {value.type === 'photo' || value.type === 'signature' ? (
        <Media value={value.value} label={value.label} />
      ) : (
        <span className="text-xs" style={{ color: tone }}>{describe(value)}</span>
      )}
    </div>
  );
}

function Media({ value, label }: { value: unknown; label: string }) {
  const url = typeof value === 'string' && value ? value : null;
  if (!url) return <span className="text-xs" style={{ color: 'var(--fg-4)' }}>—</span>;
  return (
    <a href={attachmentUrl(url)} target="_blank" rel="noopener noreferrer"
      className="rounded-ds-md overflow-hidden inline-block"
      style={{ width: 56, height: 56, border: '1px solid var(--border-1)' }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={attachmentUrl(url)} alt={label}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </a>
  );
}

/** Der Wert als Wort – **ohne Deutung**: gezeigt wird, was erfasst wurde. */
function describe(value: RecordValue): string {
  const raw = value.value;
  if (raw === true) return 'gut';
  if (raw === false) return 'schlecht';
  if (raw === null || raw === undefined || raw === '') return '—';
  return String(raw);
}
