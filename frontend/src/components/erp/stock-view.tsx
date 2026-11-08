'use client';

import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { AlertTriangle, Boxes, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import type { Instance, InstanceSummary, StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { SPEC, SpecHead } from '@/components/erp/detail-frame';
import { ObjId } from '@/components/erp/obj-id';
import { StockBar } from '@/components/erp/stock-bar';
import { UnitNumbers } from '@/components/erp/unit-numbers';
import { Skeleton } from './skeleton';

const PAGE = 50;

/**
 * **Was habe ich, in welchem Zustand, unter welcher Nummer?** EIN Modul, zwei Umfänge:
 * am **Artikel** sind die Zeilen seine Instanzen, an der **Instanz** direkt ihre
 * Einzelinstanzen – dieselbe Darstellung.
 *
 * **Kein Filter**: die Leiste ist das Bedienelement, der Rest bleibt sichtbar. **Niemals
 * alles auf einmal**: Instanzen seitenweise, Nummern erst auf Klick; die Leiste gilt für
 * den ganzen Umfang (eigene Aggregation). Kein Sonderfall für Einzelserialisierung (§2).
 */
type StockScope =
  /** Alles von diesem Artikel – die Aggregation holt der Endpunkt. */
  | { kind: 'article'; objectId: number }
  /** Diese eine Gruppe – der Datensatz liegt schon vor und trägt seine Aufstellung mit. */
  | { kind: 'instance'; record: Instance };

export function StockView({ scope }: { scope: StockScope }) {
  const articleId = scope.kind === 'article' ? scope.objectId : null;
  // Seitenweise: jede Seite bringt die Aufstellung des ganzen Umfangs mit, die Zeilen
  // wachsen. Nach einem Auftrag lädt sie über `lib/feed.TOUCHES` nach.
  const query = useInfiniteQuery({
    queryKey: qk.stock(articleId ?? 0),
    queryFn: ({ pageParam, signal }) => api.getArticleStock(articleId!, PAGE, pageParam, { signal }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.instances.length, 0);
      return loaded < last.instance_total ? loaded : undefined;
    },
    enabled: articleId != null,
    meta: { what: 'Bestand' },
  });
  const stock = query.data?.pages.at(-1) ?? null;
  const rows = query.data?.pages.flatMap((p) => p.instances) ?? [];
  const busy = query.isFetchingNextPage;
  const err = !stock && query.error ? query.error.message : null;
  /** **Welcher Zustand offen ist – genau einer, keiner zu Beginn**; ein zweiter Klick schliesst. */
  const [picked, setPicked] = useState<string | null>(null);
  const toggle = (status: string) =>
    setPicked((cur) => (cur === status ? null : status));

  const states = scope.kind === 'article' ? stock?.states : scope.record.states;
  const total = scope.kind === 'article' ? stock?.total : scope.record.quantity;

  if (err) {
    return (
      <StockCard>
        <p className="text-sm" style={{ color: 'var(--danger)' }}>{err}</p>
      </StockCard>
    );
  }
  if (states == null || total == null) {
    return <StockCard><Skeleton block={28} lines={2} label="Bestand wird geladen" /></StockCard>;
  }

  if (total === 0) {
    return (
      <StockCard>
        <p className="text-sm text-fg-3">Kein Bestand</p>
      </StockCard>
    );
  }

  // **Ein Zustand ohne Zuordnung ist ein Fehler** und wird gemeldet, nicht einsortiert.
  const unknown = states.filter((s) => s.stock !== 'live' && s.stock !== 'history');
  const open = states.find((s) => s.status === picked) ?? null;

  return (
    <StockCard>
      {/* ►►► **Die Leiste IST das Bedienelement** ◄◄◄ – mit Beschriftungen, darunter genau
          **ein** Ausschnitt. Welche Zustände es gibt, sagt `states` vom Server (Reihenfolge
          des `CATALOG`); zwei gleichzeitig offen gibt es nicht. */}
      <StockBar states={states} height={10} onPick={toggle} active={picked} />

      {unknown.length > 0 && (
        <div className="pt-3"><UnknownStates states={unknown} /></div>
      )}

      {open && (
        <section className="mt-3 flex flex-col border-t border-border-1 pt-1">
          {scope.kind === 'instance' ? (
            // An der Instanz direkt die Einzelinstanzen – dieselbe Komponente wie am Artikel.
            <UnitNumbers
              objectId={scope.record.object_id}
              statuses={[open.status]}
              quantity={open.quantity}
            />
          ) : (
            <>
              {rows
                .filter((r) => r.states.some((x) => x.status === open.status))
                .map((r) => <InstanceRow key={r.id} row={r} status={open.status} />)}
              {stock != null && rows.length < stock.instance_total && (
                <button
                  type="button"
                  onClick={() => void query.fetchNextPage()}
                  disabled={busy}
                  className="mt-2 self-start text-[12.5px] text-fg-3 hover:text-fg-1 disabled:opacity-50"
                >
                  {busy ? 'lädt …' : `weitere ${stock.instance_total - rows.length} Instanzen`}
                </button>
              )}
            </>
          )}
        </section>
      )}
    </StockCard>
  );
}

const sum = (states: StockState[]) => states.reduce((n, s) => n + s.quantity, 0);

/** Die Karte – wie die Spezifikation; **ohne eine Gesamtzahl** (sie zählte auch Historie). */
function StockCard({ children }: { children: React.ReactNode }) {
  return (
    <div style={SPEC.card}>
      <SpecHead icon={Boxes} title="Bestand" />
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

/**
 * **Ein Zustand ohne Zuordnung ist ein Fehler** (`domain/statuses.py` lässt ihn nicht zu) –
 * taucht er doch auf, wird er **benannt**, nicht geraten und nicht weggelassen.
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

/**
 * Eine Zeile je Instanz **innerhalb einer Zustands-Gruppe**: Objektnummer und ihre Menge in
 * **diesem** Zustand (die Instanz hat keinen Zustand, ihre Stücke schon). Aufklappen zeigt
 * die Nummern dieses Zustands; die Objektnummer (`ObjId`) führt zum Datensatz.
 */
function InstanceRow({ row, status }: { row: InstanceSummary; status: string }) {
  const [shown, setShown] = useState(false);
  const states = row.states.filter((s) => s.status === status);

  const toggle = () => setShown((v) => !v);

  // Die Trennlinie schliesst die Zeile ab; die eröffnende gehört dem Ausschnitt (`section`).
  return (
    <div className="border-b border-border-1">
      <div
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
        className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2 cursor-pointer"
      >
        <ChevronRight
          size={13}
          className="text-fg-4 transition-transform"
          style={{ transform: shown ? 'rotate(90deg)' : 'none', flex: 'none' }}
        />
        <ObjId value={row.object_id} />
        <span className="ix-tnum text-[13px] whitespace-nowrap">{sum(states)}</span>
      </div>

      {shown && (
        <div className="pb-3 pl-6">
          {/* Genau der Zustand dieser Gruppe – nie «alle». */}
          <UnitNumbers
            objectId={row.object_id}
            statuses={[status]}
            quantity={sum(states)}
            dense
          />
        </div>
      )}
    </div>
  );
}
