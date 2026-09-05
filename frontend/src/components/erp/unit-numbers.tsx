'use client';

import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { VERBAUT } from '@/lib/status-catalog';
import type { Genealogy, GenealogyPart, InstanceUnit } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { ObjId } from '@/components/erp/obj-id';
import { UnitNumber } from '@/components/erp/unit-number';
import { PlaceTrail } from '@/components/erp/place-trail';

const PAGE = 60;

/**
 * **Woraus besteht dieses Stück – und worin steckt es?**
 *
 * Beides ist eine **Ableitung** über den Ereignis-Log (`services/genealogy`), kein
 * gespeichertes Feld: die Stückliste sind die Stücke, die denselben Auftrag als
 * «Verbaut» verlassen haben.
 *
 * **Ein ausgebautes Teil bleibt in der Liste** und wird als ausgebaut gezeigt. Das ist
 * der Punkt, an dem die Ableitung aus dem Log zählt: «Verbaut» ist aufhebbar (eine
 * Demontage holt das Zahnrad zurück), und läse die Liste den heutigen Zustand,
 * verschwände das Teil rückwirkend aus der Vergangenheit des Getriebes.
 *
 * Der Auftrag steht immer dabei – über ihn läuft die Zuordnung, und bei mehreren
 * Erzeugnissen in einem Auftrag ist er die genauere Aussage.
 */
function GenealogyView({ data }: { data: Genealogy }) {
  const line = (p: GenealogyPart, gone: boolean) => (
    <div key={p.unit_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1">
      <UnitNumber value={p.number} />
      <span className="text-[12.5px] text-fg-3">{p.article_name}</span>
      {p.order_object_id ? <ObjId value={p.order_object_id} /> : null}
      {gone && (
        <span className="ml-auto text-[12.5px] text-fg-4"
          data-tip="Das Teil wurde später wieder ausgebaut. Es bleibt in der Stückliste – was verbaut WAR, bleibt verbaut gewesen.">
          ausgebaut
        </span>
      )}
    </div>
  );

  if (data.parts.length === 0 && data.built_into.length === 0) {
    return <p className="py-1 text-[12.5px] text-fg-4">Keine Verbindung zu anderen Stücken.</p>;
  }
  return (
    <div className="flex flex-col gap-2 pb-1">
      {data.parts.length > 0 && (
        <div>
          <p className="ix-eyebrow text-fg-4">Stückliste</p>
          {data.parts.map((p) => line(p, !p.still_in))}
        </div>
      )}
      {data.built_into.map((host, i) => (
        <div key={host.order_object_id ?? i}>
          <p className="ix-eyebrow text-fg-4">Verbaut in</p>
          {host.products.length === 0
            ? (
              <p className="py-1 text-[12.5px] text-fg-4">
                In Auftrag <ObjId value={host.order_object_id ?? 0} /> verbaut – dort hat
                kein Stück den Auftrag weiterlaufend verlassen.
              </p>
            )
            : host.products.map((p) => line(p, false))}
        </div>
      ))}
    </div>
  );
}

/**
 * **Die Nummern der Einzelinstanzen — die unterste Ebene, seitenweise.**
 *
 * Eine Zeile ist ein **Stück**: seine Nummer, sein Zustand, und – wenn es gerade läuft –
 * der Auftrag, in dem es steckt. Mehr gibt es über ein Stück nicht zu sagen, ohne es zu
 * öffnen.
 *
 * **Sie lädt erst, wenn sie gebraucht wird, und nie alles.** Eine Charge über 5000 Stück
 * hat 5000 Nummern; sie auf Vorrat mitzuliefern macht jede Instanz-Zeile so teuer wie die
 * ganze Charge. Der Server gibt sie darum seitenweise heraus
 * (`GET /erp/instances/{id}/units`), und dies ist die **einzige** Stelle, die sie zeigt –
 * im Bestand des Artikels wie im Instanz-Datensatz. Zwei Listen für dieselbe Sache liefen
 * beim ersten neuen Feld auseinander, und eine davon wäre wieder die unbegrenzte.
 *
 * **Der Zustand steht als Wort da, nicht als Badge.** In einer Liste gleichartiger Zeilen
 * ist eine gefüllte Pille je Zeile lauter als der Inhalt; die Farbe trägt die Bedeutung,
 * das Wort benennt sie. Fragt die Liste ohnehin nach genau **einem** Zustand (man hat ein
 * Segment der Leiste angeklickt), entfällt es ganz – dann sagt es in jeder Zeile dasselbe.
 */
export function UnitNumbers({ objectId, statuses, quantity, dense }: {
  /** Objektnummer der **Instanz**, deren Stücke gezeigt werden. */
  objectId: number;
  /** Nur Stücke in diesen Zuständen. Leer/fehlend = alle. */
  statuses?: readonly string[];
  /** Wie viele es insgesamt sind – für die Zeile «weitere laden», bevor geladen wurde. */
  quantity?: number;
  dense?: boolean;
}) {
  const [rows, setRows] = useState<InstanceUnit[]>([]);
  const [total, setTotal] = useState<number>(quantity ?? 0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // **Aufgeklappt wird eines nach dem anderen**, und geladen wird erst dann: die
  // Genealogie eines Stücks ist je Stück eine eigene Abfrage über den Log.
  const [open, setOpen] = useState<number | null>(null);
  const [tree, setTree] = useState<Record<number, Genealogy>>({});

  // Die Zustands-Menge ist Teil der Frage, also gehört sie in die Abhängigkeit – als
  // Zeichenkette, weil ein frisch gebautes Array bei jedem Rendern ein anderes ist.
  const key = (statuses ?? []).join(',');
  const load = useCallback((offset: number) => {
    setBusy(true);
    api.getInstanceUnits(objectId, {
      statuses: key ? key.split(',') : undefined, limit: PAGE, offset,
    })
      .then((page) => {
        setTotal(page.total);
        setRows((prev) => (offset === 0 ? page.units : [...prev, ...page.units]));
        setErr(null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [objectId, key]);

  // Wechselt die Frage, ist es eine andere Liste – nicht eine längere.
  useEffect(() => { setRows([]); load(0); }, [load]);

  if (err) return <p className="text-[12.5px]" style={{ color: 'var(--danger)' }}>{err}</p>;
  if (rows.length === 0 && busy) {
    return <p className="text-[12.5px] text-fg-4">Nummern werden geladen …</p>;
  }
  if (rows.length === 0) {
    return <p className="text-[12.5px] text-fg-4">Keine Einzelinstanzen.</p>;
  }

  return (
    <div className="flex flex-col">
      {rows.map((u) => {
        const cfg = statusCfg(u.status);
        // **Ein Pfeil nur, wo etwas dahinterliegt.** Entweder steckt etwas darin
        // (`parts_count`, für die ganze Seite in zwei Abfragen ermittelt) oder es steckt
        // selbst in etwas (`verbaut`). Ein Pfeil an jeder von 5000 Zeilen, hinter dem
        // nichts liegt, wäre ein Versprechen, das die Liste nicht halten kann.
        const linked = u.parts_count > 0 || u.status === VERBAUT;
        const isOpen = open === u.id;
        return (
          <div key={u.id} className={`border-t border-border-1 ${dense ? 'py-1' : 'py-1.5'}`}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {linked ? (
                <button
                  type="button"
                  aria-expanded={isOpen}
                  aria-label={`Verbindungen von ${u.number}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    const next = isOpen ? null : u.id;
                    setOpen(next);
                    if (next !== null && !tree[u.id]) {
                      api.getUnitGenealogy(objectId, u.suffix)
                        .then((g) => setTree((prev) => ({ ...prev, [u.id]: g })))
                        .catch(() => setOpen(null));
                    }
                  }}
                  className="-ml-1 text-fg-4 hover:text-fg-1"
                >
                  {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              ) : null}
              <UnitNumber value={u.number} />
              {u.order_object_id ? (
                <span className="flex items-center gap-1.5 text-[12.5px] text-fg-3">
                  <span className="text-fg-4">in</span>
                  <ObjId value={u.order_object_id} />
                </span>
              ) : null}
              {/* **Wo es liegt** – der Halter, die Kette im Hover. Der Ort hängt am
                  Stück, nicht an der Gruppe: zwei Schrauben derselben Charge dürfen an
                  zwei Orten liegen, und genau darum steht er hier und nicht oben. */}
              <PlaceTrail place={u.place} />
              {(statuses ?? []).length !== 1 && (
                <span
                  className="ml-auto flex items-center gap-1.5 text-[12.5px]"
                  style={{ color: cfg.color }}
                >
                  <span className="rounded-full" style={{
                    width: 6, height: 6, background: cfg.color, flex: 'none',
                  }} />
                  {cfg.label}
                </span>
              )}
            </div>
            {isOpen && (
              <div className="mt-1 border-l border-border-1 pl-3">
                {tree[u.id]
                  ? <GenealogyView data={tree[u.id]} />
                  : <p className="py-1 text-[12.5px] text-fg-4">wird geladen …</p>}
              </div>
            )}
          </div>
        );
      })}

      {rows.length < total && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); load(rows.length); }}
          disabled={busy}
          className="mt-1 self-start text-[12.5px] text-fg-3 hover:text-fg-1 disabled:opacity-50"
        >
          {busy ? 'lädt …' : `weitere ${total - rows.length} Nummern`}
        </button>
      )}
    </div>
  );
}
