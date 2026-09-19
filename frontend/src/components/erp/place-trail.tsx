'use client';

import { formatObjectId } from '@/lib/utils';
import { TYPE_META } from '@/lib/erp-record';
import { ObjId } from '@/components/erp/obj-id';
import type { ErpRecordType, UnitPlace } from '@/types';

/**
 * **Wo ein Stück liegt — der Halter in der Zeile, die Kette im Hover.**
 *
 * Ein Ort ist oft verschachtelt: die Schraube liegt im Behälter, der im Regal, das im
 * Werk Nord steht. Die ganze Kette in jede Zeile zu schreiben wäre bei sechzig Zeilen
 * eine Wand aus Text, in der die eigentliche Angabe untergeht — und bei einer 5000er-
 * Charge sechzig Mal derselbe Satz.
 *
 * Darum die Rangfolge, die im Haus überall gilt: **die Aussage steht da, die Erklärung
 * steht im Hover.** In der Zeile der unmittelbare Halter (das ist die Antwort auf «wo
 * hole ich es»), im Hover der Weg bis zur Adresse (das ist die Antwort auf «wo ist das
 * überhaupt»).
 *
 * **Das Symbol kommt aus `TYPE_META`**, derselben Zuordnung, aus der es der Feed und
 * jeder Detail-Kopf nimmt. Eine zweite Liste «Symbol je Halter-Typ» wäre dieselbe
 * Aussage ein zweites Mal — und die erste, die man beim nächsten Typ vergisst.
 *
 * **Standortlos ist ein regulärer Zustand**, kein fehlender Wert: ein frisch erzeugtes
 * Stück liegt nirgends, bis ein Modul es irgendwohin bringt. Es steht als leises
 * Zeichen da statt als Lücke — eine Lücke sähe aus, als hätte die Anzeige versagt.
 */
export function PlaceTrail({ place }: { place?: UnitPlace | null }) {
  const holder = place?.holder;
  if (!holder) {
    return (
      <span
        className="text-[12.5px] text-fg-4"
        data-tip="Noch keinem Ort zugewiesen – das Stück liegt nirgends, bis ein Modul es bewegt."
      >
        —
      </span>
    );
  }

  // Ein Halter-Typ, den diese Oberfläche nicht kennt, käme aus einem neueren Backend
  // und bekommt schlicht kein Symbol – die Nummer und der Name tragen die Aussage.
  //
  // **Ein Träger ist ein Stück einer Instanz**, also trägt er deren Symbol: geöffnet
  // wird die Instanz, denn ein Stück hat keinen eigenen Datensatz. Nur sein *Name* ist
  // genauer (`100000123-3`) – und den zieht die Anzeige der Objektnummer vor.
  const kind = (holder.kind === 'unit' ? 'instance' : holder.kind) as ErpRecordType;
  const Icon = TYPE_META[kind]?.icon;
  const chain = place?.chain ?? [holder];
  const name = (s: { object_id: number; number?: string | null }) =>
    s.number ?? formatObjectId(s.object_id);

  return (
    <span
      className="flex min-w-0 items-center gap-1.5 text-[12.5px] text-fg-3"
      // Die **ganze** Kette, von innen nach aussen. Sie endet bei dem Halter, der eine
      // Anschrift trägt – dort ist der Ort in der Welt, alles davor ist die
      // Verschachtelung darin.
      data-tip={chain.map((s) => `${s.label} ${name(s)}`).join('  ›  ')}
    >
      {Icon ? <Icon size={13} className="flex-none text-fg-4" /> : null}
      <ObjId value={holder.object_id} label={holder.number ?? undefined} />
      <span className="truncate">{holder.label}</span>
      {chain.length > 1 ? <span className="flex-none text-fg-4">›&nbsp;…</span> : null}
    </span>
  );
}
