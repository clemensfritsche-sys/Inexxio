'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Boxes, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleStock, Instance, InstanceSummary, StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { SPEC, SpecHead } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { StockBar, StockLegend } from '@/components/erp/stock-bar';
import { UnitNumbers } from '@/components/erp/unit-numbers';

const PAGE = 50;

/**
 * **Was habe ich, in welchem Zustand, unter welcher Nummer?**
 *
 * EIN Modul, zwei Aufrufe. Der Unterschied ist ausschliesslich der **Umfang der Daten**,
 * nie die Darstellung:
 *
 *   - am **Artikel**  → alles davon; die Zeilen sind seine Instanzen, aufklappbar zu den
 *     Nummern ihrer Einzelinstanzen
 *   - an der **Instanz** → diese eine Gruppe; die Zeilen sind direkt ihre Einzelinstanzen
 *
 * Die Ansicht an der Instanz ist damit exakt der Teilbaum, den man am Artikel aufklappt –
 * dieselbe Leiste, dieselbe Legende, dieselbe Aufteilung in Bestand/Historie, dasselbe
 * Verhalten beim Klick auf ein Segment. Eine zweite Fassung «nur für die Instanz» hätte
 * beim ersten neuen Zustand anders ausgesehen.
 *
 * **Kein Filter.** Ein Filter versteckt, was er nicht zeigt; hier ist die Aufteilung
 * selbst das Bedienelement – ein Segment anklicken heisst «zeig mir diese Nummern», der
 * Rest bleibt sichtbar.
 *
 * **Niemals alles auf einmal.** Instanzen kommen seitenweise, Nummern erst auf Klick und
 * auch dann seitenweise. Die Leiste oben gilt trotzdem für den **ganzen** Umfang: sie
 * kommt aus einer eigenen Aggregation und ändert ihre Länge nicht, wenn man blättert.
 *
 * **Ein Sonderfall für Einzelserialisierung existiert nicht** (PROCESS_CORE.md §2): eine
 * Einzelinstanz ist eine Instanz mit Menge 1 – dieselbe Zeile, dieselbe Leiste.
 */
export type StockScope =
  /** Alles von diesem Artikel – die Aggregation holt der Endpunkt. */
  | { kind: 'article'; objectId: number }
  /**
   * Diese eine Gruppe. Der Datensatz **liegt schon vor** (das Fenster zeigt ihn ja) und
   * trägt seine Aufstellung mit – ihn hier ein zweites Mal zu holen wäre dieselbe Frage
   * an dieselbe Stelle.
   */
  | { kind: 'instance'; record: Instance };

export function StockView({ scope }: { scope: StockScope }) {
  const articleId = scope.kind === 'article' ? scope.objectId : null;
  const [stock, setStock] = useState<ArticleStock | null>(null);
  const [rows, setRows] = useState<InstanceSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback((offset: number) => {
    if (articleId == null) return;
    setBusy(true);
    api.getArticleStock(articleId, PAGE, offset)
      .then((s) => {
        setStock(s);
        setRows((prev) => (offset === 0 ? s.instances : [...prev, ...s.instances]));
        setErr(null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [articleId]);

  useEffect(() => { setRows([]); load(0); }, [load]);

  const states = scope.kind === 'article' ? stock?.states : scope.record.states;
  const total = scope.kind === 'article' ? stock?.total : scope.record.quantity;

  if (err) {
    return (
      <Card>
        <p className="text-sm" style={{ color: 'var(--danger)' }}>{err}</p>
      </Card>
    );
  }
  if (states == null || total == null) return null;

  if (total === 0) {
    return (
      <Card total={0}>
        <p className="text-sm text-fg-3">
          Noch kein Bestand – Einzelinstanzen entstehen mit der Freigabe eines Auftrags.
        </p>
      </Card>
    );
  }

  // **Wohin ein Zustand gehört, sagt der Server** (`StockState.stock`) – die Zuordnung ist
  // eine Eigenschaft des Status (`domain/statuses.Status.stock`), keine Liste, die diese
  // Ansicht pflegt und beim nächsten neuen Zustand vergisst. Ein Zustand ohne Zuordnung
  // landet darum nicht still im falschen Block, sondern wird **gemeldet**.
  const unknown = states.filter((s) => s.stock !== 'live' && s.stock !== 'history');

  return (
    <Card total={total}>
      <div className="flex flex-col gap-2.5 pb-1">
        <StockBar states={states} height={10} />
        <StockLegend states={states} />
      </div>

      {unknown.length > 0 && <UnknownStates states={unknown} />}

      {BUCKETS.map((b) => {
        const mine = states.filter((s) => s.stock === b.stock);
        if (mine.length === 0) return null;
        return (
          <Block key={b.stock} title={b.title} count={sum(mine)} defaultOpen={b.open}>
            {scope.kind === 'instance' ? (
              // An der Instanz sind die Zeilen direkt die Einzelinstanzen – dieselbe
              // Komponente, die am Artikel eine Instanz-Zeile aufklappt.
              <UnitNumbers
                objectId={scope.record.object_id}
                statuses={mine.map((s) => s.status)}
                quantity={sum(mine)}
              />
            ) : (
              <>
                {rows
                  .filter((r) => r.states.some((s) => s.stock === b.stock))
                  .map((r) => <InstanceRow key={r.id} row={r} bucket={b.stock} />)}
                {/* Blättern gibt es nur dort, wo eine Seite Instanzen kommt. */}
                {b.stock === 'live' && stock != null && rows.length < stock.instance_total && (
                  <button
                    type="button"
                    onClick={() => load(rows.length)}
                    disabled={busy}
                    className="mt-2 self-start text-[12.5px] text-fg-3 hover:text-fg-1 disabled:opacity-50"
                  >
                    {busy ? 'lädt …' : `weitere ${stock.instance_total - rows.length} Instanzen`}
                  </button>
                )}
              </>
            )}
          </Block>
        );
      })}
    </Card>
  );
}

/**
 * Bestand ↔ Historie: zwei Fragen («was habe ich» / «was war»), nicht ein Filter. Die
 * Liste selbst ist in beiden Fällen dieselbe – nur die Zustände unterscheiden sich, und
 * welche wohin gehören, steht am Status.
 */
const BUCKETS = [
  { stock: 'live', title: 'Bestand', open: true },
  { stock: 'history', title: 'Historie', open: false },
] as const;

const sum = (states: StockState[]) => states.reduce((n, s) => n + s.quantity, 0);

/** Die Karte – dieselbe Anatomie wie die Spezifikation (Karte + Kopf + Inhalt). */
function Card({ total, children }: { total?: number; children: React.ReactNode }) {
  return (
    <div style={SPEC.card}>
      <SpecHead
        icon={Boxes}
        title="Bestand"
        right={total != null ? (
          <span className="ix-tnum font-display leading-none" style={{ fontSize: 26 }}>{total}</span>
        ) : undefined}
      />
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

/**
 * **Ein Zustand ohne Zuordnung ist ein Fehler, kein Sonderfall.** Er dürfte nicht
 * existieren: `domain/statuses.py` weist beim Import jeden Einzelinstanz-Zustand ab, der
 * nicht sagt, ob er zum Bestand oder zur Historie zählt. Taucht er trotzdem auf (Altdaten,
 * ein von Hand geschriebener Wert), wird er **benannt** – ihn in einen Block zu raten
 * wäre eine Behauptung, ihn wegzulassen ein stiller Verlust.
 */
function UnknownStates({ states }: { states: StockState[] }) {
  return (
    <div
      className="flex items-start gap-2 rounded-ds-md px-3 py-2.5 text-[12.5px]"
      style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}
    >
      <AlertTriangle size={14} style={{ flex: 'none', marginTop: 1 }} />
      <span>
        Nicht zugeordnet ({states.map((s) => `${statusCfg(s.status).label} · ${s.quantity}`).join(', ')}) –
        dieser Zustand sagt nicht, ob er zum Bestand oder zur Historie zählt.
      </span>
    </div>
  );
}

/** Ein Block: Überschrift mit Menge, darunter die Zeilen dieses Umfangs. */
function Block({ title, count, defaultOpen, children }: {
  title: string; count: number; defaultOpen: boolean; children: React.ReactNode;
}) {
  const [shown, setShown] = useState(defaultOpen);
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
        <span className="ix-tnum text-[13px] text-fg-3">{count}</span>
      </button>
      {shown && <div className="flex flex-col pb-4">{children}</div>}
    </section>
  );
}

/**
 * Eine Zeile je Instanz: Objektnummer, Menge, Leiste.
 *
 * Die Leiste ist zugleich der Griff zur Ebene darunter: ein Segment anklicken öffnet die
 * Nummern **dieses** Zustands, ein Klick auf die Zeile alle des Blocks. Damit braucht es
 * kein zusätzliches Bedienelement für etwas, das man ohnehin sieht.
 *
 * **Die Objektnummer führt zum Datensatz** (bestehende Navigation, kein eigener Weg) –
 * und weil `ObjId` den Klick abfängt, kollidiert das nicht mit dem Aufklappen.
 */
function InstanceRow({ row, bucket }: { row: InstanceSummary; bucket: string }) {
  const [pick, setPick] = useState<string | null | undefined>(undefined);
  const states = row.states.filter((s) => s.stock === bucket);
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
        <span className="ix-tnum text-[13px] whitespace-nowrap">{sum(states)}</span>
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
