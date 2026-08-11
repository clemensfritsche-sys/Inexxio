'use client';

import { useCallback, useEffect, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleStock, InstanceSummary, StockState } from '@/types';
import { isLive } from '@/lib/process-status';
import { ObjId } from '@/components/erp/obj-id';
import { StockBar, StockLegend } from '@/components/erp/stock-bar';
import { UnitNumbers } from '@/components/erp/unit-numbers';

const PAGE = 50;

/**
 * **Reiter «Bestand» — was habe ich von diesem Artikel, in welchem Zustand, unter
 * welcher Nummer?**
 *
 * Drei Ebenen, und jede beantwortet die Frage vollständiger als die darüber:
 *
 *   1. die **Leiste** – wie viel es insgesamt gibt und wie es sich verteilt
 *   2. die **Instanzen** – unter welchen Objektnummern es liegt, je mit eigener Leiste
 *   3. die **Nummern** – welche Stücke genau, auf Klick nachgeladen
 *
 * **Kein Filter.** Ein Filter ist das Eingeständnis, dass die Standardansicht zu viel
 * Rauschen enthält; und er versteckt, was er nicht zeigt. Stattdessen ist die Aufteilung
 * selbst das Bedienelement: ein Segment der Leiste anklicken heisst «zeig mir diese
 * Nummern» – der Rest bleibt sichtbar, nur eben zurückgetreten.
 *
 * **Niemals alles auf einmal.** Die Instanzen kommen seitenweise, die Nummern erst auf
 * Klick und auch dann seitenweise. Die Leiste oben gilt trotzdem für den **ganzen**
 * Artikel: sie kommt aus einer eigenen Aggregation und ändert ihre Länge nicht, wenn man
 * blättert.
 *
 * **Ein Sonderfall für Einzelserialisierung existiert nicht** (PROCESS_CORE.md §2): eine
 * Einzelinstanz ist eine Instanz mit Menge 1. Sie bekommt dieselbe Zeile, dieselbe
 * Leiste, dieselbe Nummernliste – nur eben mit einem Stück darin.
 */
export function ArticleStockTab({ articleObjectId, unit }: {
  articleObjectId: number | null;
  /** Mengeneinheit des Artikels, für die Zahlen. */
  unit?: string | null;
}) {
  const [stock, setStock] = useState<ArticleStock | null>(null);
  const [rows, setRows] = useState<InstanceSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback((offset: number) => {
    if (!articleObjectId) return;
    setBusy(true);
    api.getArticleStock(articleObjectId, PAGE, offset)
      .then((s) => {
        setStock(s);
        setRows((prev) => (offset === 0 ? s.instances : [...prev, ...s.instances]));
        setErr(null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [articleObjectId]);

  useEffect(() => { setRows([]); load(0); }, [load]);

  if (!articleObjectId) return null;
  if (err) return <Wrap><p className="text-sm" style={{ color: 'var(--danger)' }}>{err}</p></Wrap>;
  if (!stock) return null;

  if (stock.total === 0) {
    return (
      <Wrap>
        <p className="text-sm text-fg-3">
          Noch kein Bestand – Einzelinstanzen entstehen mit der Freigabe eines Auftrags.
        </p>
      </Wrap>
    );
  }

  // Aktueller Bestand ↔ Historie: dieselbe Liste, entlang der Zustandsliste getrennt.
  // Der zweite Block erscheint an dem Tag, an dem es den ersten solchen Zustand gibt –
  // heute gibt es ihn nicht, also steht er auch nicht da.
  const live = split(stock.states, true);
  const past = split(stock.states, false);
  const liveRows = rows.filter((r) => split(r.states, true).length > 0);
  const pastRows = rows.filter((r) => split(r.states, false).length > 0);

  return (
    <Wrap>
      {/* Ebene 1 – die eine Zahl, und wie sie sich verteilt. */}
      <div className="flex flex-col gap-2.5 pb-5">
        <div className="flex items-baseline gap-2">
          <span className="ix-tnum text-[26px] font-display leading-none">{stock.total}</span>
          {unit ? <span className="text-sm text-fg-3">{unit}</span> : null}
        </div>
        <StockBar states={stock.states} height={10} />
        <StockLegend states={stock.states} unit={unit} />
      </div>

      {/* Ebene 2 + 3 – aktueller Bestand, offen. */}
      <Block
        title="Bestand"
        count={sum(live)}
        rows={liveRows}
        unit={unit}
        open
        more={rows.length < stock.instance_total}
        busy={busy}
        onMore={() => load(rows.length)}
        rest={stock.instance_total - rows.length}
      />

      {/* Und die Historie – nur, wenn es sie gibt. */}
      {past.length > 0 && (
        <Block
          title="Historie"
          count={sum(past)}
          rows={pastRows}
          unit={unit}
          open={false}
          more={false}
          busy={false}
          onMore={() => {}}
          rest={0}
        />
      )}
    </Wrap>
  );
}

function Wrap({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}
      className="flex flex-col">
      {children}
    </div>
  );
}

const sum = (states: StockState[]) => states.reduce((n, s) => n + s.quantity, 0);
const split = (states: StockState[], live: boolean) =>
  states.filter((s) => isLive(s.status) === live);

/**
 * Ein Block: Überschrift mit Menge, darunter eine Zeile je Instanz.
 *
 * Zwei Blöcke statt eines Filters – «was ich habe» und «was war» sind zwei Fragen, und
 * die zweite stellt man selten. Sie steht darum zugeklappt da, statt die erste zu
 * verlängern.
 */
function Block({ title, count, rows, unit, open, more, busy, onMore, rest }: {
  title: string;
  count: number;
  rows: InstanceSummary[];
  unit?: string | null;
  open: boolean;
  more: boolean;
  busy: boolean;
  onMore: () => void;
  rest: number;
}) {
  const [shown, setShown] = useState(open);
  const live = title === 'Bestand';

  return (
    <section className="border-t border-border-1">
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        className="flex w-full items-center gap-2 py-2.5 text-left"
      >
        <ChevronRight
          size={14}
          className="text-fg-4 transition-transform"
          style={{ transform: shown ? 'rotate(90deg)' : 'none' }}
        />
        <span className="text-[13px] font-medium">{title}</span>
        <span className="ix-tnum text-[13px] text-fg-3">
          {count}{unit ? ` ${unit}` : ''}
        </span>
        <span className="text-fg-4">·</span>
        <span className="text-[12.5px] text-fg-4">
          {rows.length} Instanz{rows.length !== 1 ? 'en' : ''}
        </span>
      </button>

      {shown && (
        <div className="flex flex-col pb-4">
          {rows.map((r) => (
            <InstanceRow key={r.id} row={r} unit={unit} live={live} />
          ))}
          {more && (
            <button
              type="button"
              onClick={onMore}
              disabled={busy}
              className="mt-2 self-start text-[12.5px] text-fg-3 hover:text-fg-1 disabled:opacity-50"
            >
              {busy ? 'lädt …' : `weitere ${rest} Instanzen`}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/**
 * Eine Zeile je Instanz: Objektnummer, Menge, Leiste.
 *
 * Die Leiste ist zugleich der Griff zur Ebene darunter: ein Segment anklicken öffnet die
 * Nummern **dieses** Zustands, ein Klick auf die Zeile alle. Damit gibt es kein
 * zusätzliches Bedienelement für etwas, das man ohnehin sieht.
 *
 * **Die Objektnummer führt zum Datensatz** (bestehende Navigation, kein eigener Weg) –
 * und weil `ObjId` den Klick abfängt, kollidiert das nicht mit dem Aufklappen.
 */
function InstanceRow({ row, unit, live }: {
  row: InstanceSummary; unit?: string | null; live: boolean;
}) {
  const [pick, setPick] = useState<string | null | undefined>(undefined);
  const states = split(row.states, live);
  const shown = pick !== undefined;

  const toggle = (status: string | null) =>
    setPick((cur) => (cur === status ? undefined : status));

  return (
    <div className="border-t border-border-1">
      <div
        role="button"
        tabIndex={0}
        onClick={() => toggle(null)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(null); } }}
        className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2 cursor-pointer"
      >
        <ChevronRight
          size={13}
          className="text-fg-4 transition-transform"
          style={{ transform: shown ? 'rotate(90deg)' : 'none', flex: 'none' }}
        />
        <ObjId value={row.object_id} />
        <span className="ix-tnum text-[13px] whitespace-nowrap">
          {sum(states)}{unit ? ` ${unit}` : ''}
        </span>
        <span className="ml-auto" style={{ flex: '1 1 120px', minWidth: 90, maxWidth: 260 }}>
          <StockBar states={states} onPick={toggle} active={pick ?? null} />
        </span>
      </div>

      {shown && (
        <div className="pb-3 pl-6">
          {/* Ein Segment fragt nach seinem Zustand, die Zeile nach denen ihres Blocks –
              nie nach «allen»: im Historien-Block wären das auch die aktuellen. */}
          <UnitNumbers
            objectId={row.object_id}
            statuses={pick ? [pick] : states.map((s) => s.status)}
            quantity={sum(states)}
            dense
          />
        </div>
      )}
    </div>
  );
}
