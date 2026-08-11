'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { InstanceUnit } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { ObjId } from '@/components/erp/obj-id';
import { UnitNumber } from '@/components/erp/unit-number';

const PAGE = 60;

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
        return (
          <div
            key={u.id}
            className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border-1 ${
              dense ? 'py-1' : 'py-1.5'
            }`}
          >
            <UnitNumber value={u.number} />
            {u.order_object_id ? (
              <span className="flex items-center gap-1.5 text-[12.5px] text-fg-3">
                <span className="text-fg-4">in</span>
                <ObjId value={u.order_object_id} />
              </span>
            ) : null}
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
