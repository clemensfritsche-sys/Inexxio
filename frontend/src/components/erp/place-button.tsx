'use client';

import { useState } from 'react';
import { MapPin } from 'lucide-react';
import { api } from '@/lib/api';
import { useScan } from '@/components/scan/scan-provider';

/**
 * **Ablegen — die eine menschliche Ortsangabe** (PROCESS_CORE §15, SYSTEM_LOGIC O8).
 *
 * Der Endpunkt steht seit Stufe 2, mit Dienst, Regel und Wächtern — und hatte **keinen
 * einzigen Aufrufer**. Damit war der Ausgangsort einer Fuhre in der Praxis nie bekannt,
 * die Fuhre nie als Versand eingestuft und die Vergabe nie erreichbar: die Ausführung
 * verlangte etwas, das die Oberfläche nirgends anbot. Ein Endpunkt ohne Stelle ist kein
 * Feature.
 *
 * ## Zwei Scans, in dieser Reihenfolge
 *
 * 1. **Wo stehen Sie?** — freier Lookup, **ohne Vorgabewert** (O5). Ein gemerkter Ort
 *    ist die stille Fehlerklasse, bei der ein vergessener Wechsel den falschen Ort
 *    schreibt und nichts fehlschlägt. `exists` prüft nach, damit nicht jede neunstellige
 *    Zahl durchgeht.
 * 2. **Was legen Sie ab?** — die **Instanz**, denn ein Vorgang ist eine Instanz (§4.4)
 *    und nur sie trägt ein Etikett. Kennt der Aufrufer die in Frage kommenden schon
 *    (die Stücke einer Fuhre), sind sie die Kandidaten und der Scan verifiziert; sonst
 *    ist es ein freier Lookup.
 *
 * **Es ist EIN Scan-Ablauf**, kein zweiter Dialog: derselbe `useScan` wie überall, nur
 * mit zwei Schritten. Und es ändert **nichts** ausser dem Ort — kein Status, keine
 * Zugehörigkeit —, weshalb es in jedem Zustand erlaubt ist.
 */
export function PlaceButton({ instanceObjectIds, label = 'Ablegen', busy, onPlaced }: {
  /**
   * Die Instanzen, die hier in Frage kommen. **Leer** = freier Lookup (am
   * Instanz-Datensatz gibt genau eine den Ton an, im Modul sind es die der Fuhre).
   */
  instanceObjectIds?: number[];
  label?: string;
  busy?: boolean;
  /** Danach neu laden — die Ablage ändert, was die Fuhren-Vorschau zeigt. */
  onPlaced?: () => void;
}) {
  const scan = useScan();
  const [pending, setPending] = useState(false);
  const working = busy || pending;
  const known = instanceObjectIds ?? [];

  function start() {
    scan({
      steps: [
        {
          label: 'Wo stehen Sie? Halter scannen',
          // Kein Vorgabewert und keine Kandidatenliste: ein Halter ist **jede**
          // Objektnummer (O2) – Regal, Kiste, Werk, Mensch. Geprüft wird darum nur,
          // dass es den Datensatz gibt.
          exists: (id) => api.resolveObject(id).then((o) => !!o?.object_type)
            .catch(() => false),
        },
        {
          label: known.length === 1 ? `Instanz ${known[0]} scannen` : 'Instanz scannen',
          kind: 'instance',
          // Kennt der Aufrufer die Menge, ist der Scan eine **Verifikation** – dann
          // genügt eine Teileingabe, weil der Scanner anbietet, was er annimmt.
          expected: known.length ? known : undefined,
        },
      ],
      onComplete: (ids) => {
        const [holder, instance] = ids;
        if (!holder || !instance) return;
        setPending(true);
        api.placeInstance(holder, instance)
          .then(() => onPlaced?.())
          .finally(() => setPending(false));
      },
    });
  }

  return (
    <button type="button" className="erp-actbtn" style={{ height: 28 }}
      onClick={start} disabled={working}
      data-tip="Zwei Scans: wo Sie stehen, dann die Instanz. Ändert nur den Ort – nie Status oder Zugehörigkeit.">
      <MapPin size={13} /> {label}
    </button>
  );
}
